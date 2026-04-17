"""
P0 安全模块
- 飞书 webhook 签名验证
- 消息去重（内存 LRU + 可选 Redis）
"""
import hashlib
import hmac
import time
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# 1. 飞书签名验证
# ───────────────────────────────────────────────

class FeishuSignatureVerifier:
    """
    验证飞书 webhook 请求签名。

    飞书签名算法：
        signature = HMAC-SHA256(timestamp + "\n" + nonce + "\n" + body, app_secret)

    请求头字段：
        X-Lark-Request-Timestamp  — Unix 时间戳（秒）
        X-Lark-Request-Nonce      — 随机字符串
        X-Lark-Signature          — 十六进制签名
    """

    def __init__(self, app_secret: str, max_timestamp_diff: int = 300):
        """
        Args:
            app_secret:          飞书应用的 App Secret
            max_timestamp_diff:  允许的最大时间差（秒），默认 5 分钟，防重放攻击
        """
        if not app_secret:
            raise ValueError("app_secret 不能为空")
        self.app_secret = app_secret.encode("utf-8")
        self.max_timestamp_diff = max_timestamp_diff

    def verify(
        self,
        timestamp: str,
        nonce: str,
        body: bytes,
        signature: str,
    ) -> tuple[bool, str]:
        """
        验证签名。

        Args:
            timestamp:   X-Lark-Request-Timestamp 头的值
            nonce:       X-Lark-Request-Nonce 头的值
            body:        原始请求体（bytes，必须是未解析的原始内容）
            signature:   X-Lark-Signature 头的值

        Returns:
            (is_valid, reason)  — reason 在失败时说明原因
        """
        # 1. 时间戳合法性
        try:
            ts = int(timestamp)
        except (ValueError, TypeError):
            return False, "timestamp 格式非法"

        diff = abs(time.time() - ts)
        if diff > self.max_timestamp_diff:
            return False, f"timestamp 超出允许范围（差 {diff:.0f}s）"

        # 2. 计算期望签名
        message = f"{timestamp}\n{nonce}\n".encode("utf-8") + body
        expected = hmac.new(self.app_secret, message, hashlib.sha256).hexdigest()

        # 3. 常量时间比较，防止时序攻击
        if not hmac.compare_digest(expected, signature.lower()):
            return False, "签名不匹配"

        return True, "ok"


# ───────────────────────────────────────────────
# 2. 消息去重
# ───────────────────────────────────────────────

class MessageDeduplicator:
    """
    消息去重器，防止飞书重发导致重复回复。

    优先使用 Redis（分布式），不可用时退回内存 LRU。
    TTL 默认 60 秒，超出后同一 message_id 会被重新处理
    （实际上飞书重发窗口在 30 秒内，60 秒绰绰有余）。
    """

    def __init__(self, ttl: int = 60, max_memory_size: int = 2000):
        """
        Args:
            ttl:              消息 ID 的保留时长（秒）
            max_memory_size:  内存模式下最多保存的条数
        """
        self.ttl = ttl
        self.max_memory_size = max_memory_size
        self._redis = self._try_connect_redis()
        self._cache: OrderedDict[str, float] = OrderedDict()  # 内存回退

        if self._redis:
            logger.info("消息去重：使用 Redis 后端")
        else:
            logger.warning("消息去重：Redis 不可用，使用内存 LRU（单进程有效）")

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def is_duplicate(self, message_id: str) -> bool:
        """
        检查 message_id 是否已处理过。
        若未处理，自动标记为已处理并返回 False。
        若已处理，返回 True（调用方应直接返回 200 但不执行业务逻辑）。
        """
        if not message_id:
            return False

        if self._redis:
            return self._redis_check_and_set(message_id)
        return self._memory_check_and_set(message_id)

    def stats(self) -> dict:
        """返回当前去重缓存的状态，方便健康检查接口暴露。"""
        if self._redis:
            try:
                size = self._redis.dbsize()
                return {"backend": "redis", "approx_keys": size}
            except Exception:
                pass
        self._evict_expired()
        return {"backend": "memory", "cached": len(self._cache)}

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    @staticmethod
    def _try_connect_redis():
        """尝试连接 Redis，失败则静默返回 None。"""
        try:
            import redis, os
            r = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD"),
                db=int(os.getenv("REDIS_DB", 0)),
                socket_connect_timeout=2,
                decode_responses=True,
            )
            r.ping()
            return r
        except Exception:
            return None

    def _redis_check_and_set(self, message_id: str) -> bool:
        """利用 Redis SET NX + TTL 实现原子性去重。"""
        key = f"feishu:msg:{message_id}"
        try:
            # SET key 1 NX EX ttl — 仅在 key 不存在时设置
            result = self._redis.set(key, 1, nx=True, ex=self.ttl)
            # result=True 表示设置成功（首次），result=None 表示已存在（重复）
            return result is None
        except Exception as e:
            logger.error(f"Redis 去重操作失败，降级到内存：{e}")
            return self._memory_check_and_set(message_id)

    def _memory_check_and_set(self, message_id: str) -> bool:
        """内存 LRU 去重，先清理过期条目再检查。"""
        self._evict_expired()

        now = time.time()
        if message_id in self._cache:
            return True  # 重复

        # 超出容量时，淘汰最早的条目
        if len(self._cache) >= self.max_memory_size:
            self._cache.popitem(last=False)

        self._cache[message_id] = now + self.ttl
        return False

    def _evict_expired(self):
        """清理内存缓存中的过期条目。"""
        now = time.time()
        expired = [mid for mid, exp in self._cache.items() if exp <= now]
        for mid in expired:
            del self._cache[mid]
