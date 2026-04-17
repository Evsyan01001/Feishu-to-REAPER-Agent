"""
多轮对话上下文管理
- ConversationSession  : 单个用户的对话会话
- ConversationManager  : 所有用户会话的统一管理器（Redis 优先，内存回退）

设计原则：
  1. 对话历史只存 user / assistant 两种角色，system prompt 由调用方每次注入
  2. 超出 max_turns 时滚动删除最早一轮（一轮 = 一条 user + 一条 assistant）
  3. idle_timeout 秒无活动后会话自动过期，下次消息开启新会话
  4. Redis 不可用时无缝降级到内存字典，接口完全一致
"""

import json
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from collections import OrderedDict

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────────────────
DEFAULT_MAX_TURNS    = 10     # 保留最近 N 轮，避免 context 过长
DEFAULT_IDLE_TIMEOUT = 1800   # 30 分钟无活动后重置会话
DEFAULT_MAX_SESSIONS = 5000   # 内存模式下最多保存的会话数


# ── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str       # "user" | "assistant"
    content: str
    ts: float = field(default_factory=time.time)

    def to_api_dict(self) -> dict:
        """返回 DeepSeek / OpenAI 兼容的消息格式（不含 ts）"""
        return {"role": self.role, "content": self.content}


@dataclass
class ConversationSession:
    user_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    turn_count: int = 0       # 完整轮次数（user + assistant 各一条 = 1 轮）

    # ── 写入 ────────────────────────────────────────────────────────────────

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))
        self.last_active = time.time()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role="assistant", content=content))
        self.last_active = time.time()
        self.turn_count += 1

    def trim(self, max_turns: int) -> None:
        """
        超出 max_turns 时，从头部删除最早的完整一轮（user + assistant）。
        保留结构完整性：messages 始终以 user 开头，成对出现。
        """
        # 每轮 2 条消息
        max_messages = max_turns * 2
        while len(self.messages) > max_messages:
            # 从头部删除一轮（2 条）
            self.messages = self.messages[2:]

    # ── 读取 ────────────────────────────────────────────────────────────────

    def get_messages_for_api(self, max_turns: Optional[int] = None) -> List[dict]:
        """
        返回适合直接传给 DeepSeek API 的 messages 列表。
        max_turns 可临时限制窗口大小（不修改存储）。
        """
        msgs = self.messages
        if max_turns is not None:
            msgs = msgs[-(max_turns * 2):]
        return [m.to_api_dict() for m in msgs]

    def is_expired(self, idle_timeout: int) -> bool:
        return (time.time() - self.last_active) > idle_timeout

    def summary(self) -> dict:
        return {
            "user_id":     self.user_id,
            "turn_count":  self.turn_count,
            "msg_count":   len(self.messages),
            "last_active": self.last_active,
            "age_seconds": int(time.time() - self.created_at),
        }

    # ── 序列化（用于 Redis 存储）────────────────────────────────────────────

    def to_json(self) -> str:
        data = {
            "user_id":     self.user_id,
            "messages":    [asdict(m) for m in self.messages],
            "created_at":  self.created_at,
            "last_active": self.last_active,
            "turn_count":  self.turn_count,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "ConversationSession":
        data = json.loads(raw)
        session = cls(
            user_id=data["user_id"],
            created_at=data["created_at"],
            last_active=data["last_active"],
            turn_count=data["turn_count"],
        )
        session.messages = [Message(**m) for m in data["messages"]]
        return session


# ── 管理器 ────────────────────────────────────────────────────────────────────

class ConversationManager:
    """
    多用户会话管理器。

    用法：
        mgr = ConversationManager()

        # 处理用户消息前：取出历史
        session = mgr.get_or_create(user_id)
        session.add_user_message(user_text)
        history = session.get_messages_for_api()

        # 拿到 AI 回复后：写回历史
        session.add_assistant_message(ai_reply)
        mgr.save(session)

    .env 配置项：
        CONV_MAX_TURNS      最多保留轮数，默认 10
        CONV_IDLE_TIMEOUT   空闲超时秒数，默认 1800
        CONV_MAX_SESSIONS   内存模式最大会话数，默认 5000
        REDIS_HOST / PORT / PASSWORD / DB  （与 security.py 共享）
    """

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        idle_timeout: int = DEFAULT_IDLE_TIMEOUT,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
    ):
        self.max_turns   = max_turns
        self.idle_timeout = idle_timeout
        self.max_sessions = max_sessions

        self._redis = self._try_connect_redis()
        # 内存回退：user_id -> ConversationSession（OrderedDict 保证 LRU 顺序）
        self._store: OrderedDict[str, ConversationSession] = OrderedDict()

        backend = "Redis" if self._redis else "内存（单进程）"
        logger.info(f"ConversationManager 初始化完成，后端：{backend}，"
                    f"max_turns={max_turns}，idle_timeout={idle_timeout}s")

    # ── 主要接口 ─────────────────────────────────────────────────────────────

    def get_or_create(self, user_id: str) -> ConversationSession:
        """
        获取用户会话。若不存在或已超时，则创建新会话。
        """
        session = self._load(user_id)

        if session is None:
            session = ConversationSession(user_id=user_id)
            logger.info(f"[会话] 新建会话：user_id={user_id}")
        elif session.is_expired(self.idle_timeout):
            turns = session.turn_count
            session = ConversationSession(user_id=user_id)
            logger.info(f"[会话] 超时重置：user_id={user_id}，旧会话共 {turns} 轮")

        return session

    def save(self, session: ConversationSession) -> None:
        """将会话持久化，并执行轮次裁剪。"""
        session.trim(self.max_turns)
        self._persist(session)

    def delete(self, user_id: str) -> None:
        """主动清除某用户的会话（如用户发送 /reset 指令）。"""
        if self._redis:
            self._redis.delete(self._key(user_id))
        else:
            self._store.pop(user_id, None)
        logger.info(f"[会话] 已清除：user_id={user_id}")

    def stats(self) -> dict:
        """返回当前会话统计，供健康检查接口使用。"""
        if self._redis:
            try:
                # 只统计 feishu:conv:* 前缀的 key
                keys = self._redis.keys("feishu:conv:*")
                return {"backend": "redis", "active_sessions": len(keys)}
            except Exception:
                pass
        # 内存模式：先清理过期会话
        self._evict_expired_memory()
        return {"backend": "memory", "active_sessions": len(self._store)}

    # ── 内部实现 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _key(user_id: str) -> str:
        return f"feishu:conv:{user_id}"

    def _load(self, user_id: str) -> Optional[ConversationSession]:
        if self._redis:
            try:
                raw = self._redis.get(self._key(user_id))
                return ConversationSession.from_json(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis 读取会话失败，降级到内存：{e}")

        return self._store.get(user_id)

    def _persist(self, session: ConversationSession) -> None:
        if self._redis:
            try:
                self._redis.set(
                    self._key(session.user_id),
                    session.to_json(),
                    ex=self.idle_timeout + 60,   # Redis TTL 略大于 idle_timeout
                )
                return
            except Exception as e:
                logger.error(f"Redis 写入会话失败，降级到内存：{e}")

        # 内存存储：超容量时淘汰最早的
        if session.user_id not in self._store and len(self._store) >= self.max_sessions:
            self._store.popitem(last=False)
        self._store[session.user_id] = session
        self._store.move_to_end(session.user_id)   # 标记为最近使用

    def _evict_expired_memory(self) -> None:
        expired = [
            uid for uid, s in self._store.items()
            if s.is_expired(self.idle_timeout)
        ]
        for uid in expired:
            del self._store[uid]

    @staticmethod
    def _try_connect_redis():
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
