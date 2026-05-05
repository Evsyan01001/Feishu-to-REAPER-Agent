"""
会话管理服务
负责多用户多轮对话会话的管理，支持Redis和内存两种存储后端
"""
import os
import time
import json
import logging
from typing import List, Optional, Dict, Any
from collections import OrderedDict
from dataclasses import dataclass, field, asdict

from .base_service import BaseService

logger = logging.getLogger(__name__)

# 常量
DEFAULT_MAX_TURNS    = 10     # 保留最近 N 轮，避免 context 过长
DEFAULT_IDLE_TIMEOUT = 1800   # 30 分钟无活动后重置会话
DEFAULT_MAX_SESSIONS = 5000   # 内存模式下最多保存的会话数

@dataclass
class Message:
    """消息数据结构"""
    role: str       # "user" | "assistant"
    content: str
    ts: float = field(default_factory=time.time)

    def to_api_dict(self) -> dict:
        """返回 DeepSeek / OpenAI 兼容的消息格式（不含 ts）"""
        return {"role": self.role, "content": self.content}

@dataclass
class ConversationSession:
    """单个用户的对话会话"""
    user_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    turn_count: int = 0       # 完整轮次数（user + assistant 各一条 = 1 轮）

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append(Message(role="user", content=content))
        self.last_active = time.time()

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.messages.append(Message(role="assistant", content=content))
        self.last_active = time.time()
        self.turn_count += 1

    def trim(self, max_turns: int) -> None:
        """超出 max_turns 时，从头部删除最早的完整一轮"""
        max_messages = max_turns * 2
        while len(self.messages) > max_messages:
            self.messages = self.messages[2:]

    def get_messages_for_api(self, max_turns: Optional[int] = None) -> List[dict]:
        """返回适合直接传给 LLM API 的 messages 列表"""
        msgs = self.messages
        if max_turns is not None:
            msgs = msgs[-(max_turns * 2):]
        return [m.to_api_dict() for m in msgs]

    def is_expired(self, idle_timeout: int) -> bool:
        """检查会话是否已过期"""
        return (time.time() - self.last_active) > idle_timeout

    def summary(self) -> dict:
        """返回会话摘要"""
        return {
            "user_id":     self.user_id,
            "turn_count":  self.turn_count,
            "msg_count":   len(self.messages),
            "last_active": self.last_active,
            "age_seconds": int(time.time() - self.created_at),
        }

    def to_json(self) -> str:
        """序列化到JSON"""
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
        """从JSON反序列化"""
        data = json.loads(raw)
        session = cls(
            user_id=data["user_id"],
            created_at=data["created_at"],
            last_active=data["last_active"],
            turn_count=data["turn_count"],
        )
        session.messages = [Message(**m) for m in data["messages"]]
        return session

class ConversationService(BaseService):
    """会话管理服务"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.max_turns = self.config.get("max_turns", int(os.getenv("CONV_MAX_TURNS", DEFAULT_MAX_TURNS)))
        self.idle_timeout = self.config.get("idle_timeout", int(os.getenv("CONV_IDLE_TIMEOUT", DEFAULT_IDLE_TIMEOUT)))
        self.max_sessions = self.config.get("max_sessions", int(os.getenv("CONV_MAX_SESSIONS", DEFAULT_MAX_SESSIONS)))
        
        self._redis = None
        self._store: OrderedDict[str, ConversationSession] = OrderedDict()  # 内存回退存储

    def initialize(self) -> bool:
        """初始化服务，尝试连接Redis"""
        try:
            self._redis = self._try_connect_redis()
            backend = "Redis" if self._redis else "内存（单进程）"
            logger.info(f"会话管理服务初始化完成，后端：{backend}，"
                       f"max_turns={self.max_turns}，idle_timeout={self.idle_timeout}s")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"会话管理服务初始化失败: {e}")
            return False

    def cleanup(self) -> None:
        """清理服务资源"""
        if self._redis:
            try:
                self._redis.close()
            except:
                pass
        self._store.clear()
        self._initialized = False

    def get_or_create(self, user_id: str) -> ConversationSession:
        """获取用户会话，不存在或已超时则创建新会话"""
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
        """保存会话，自动裁剪轮次"""
        session.trim(self.max_turns)
        self._persist(session)

    def delete(self, user_id: str) -> None:
        """删除用户会话"""
        if self._redis:
            try:
                self._redis.delete(self._key(user_id))
            except Exception as e:
                logger.error(f"Redis 删除会话失败: {e}")
        else:
            self._store.pop(user_id, None)
        logger.info(f"[会话] 已清除：user_id={user_id}")

    def stats(self) -> dict:
        """获取会话统计信息"""
        if self._redis:
            try:
                keys = self._redis.keys("feishu:conv:*")
                return {"backend": "redis", "active_sessions": len(keys)}
            except Exception:
                pass
        # 内存模式先清理过期会话
        self._evict_expired_memory()
        return {"backend": "memory", "active_sessions": len(self._store)}

    @staticmethod
    def _key(user_id: str) -> str:
        """生成Redis存储Key"""
        return f"feishu:conv:{user_id}"

    def _load(self, user_id: str) -> Optional[ConversationSession]:
        """加载用户会话"""
        if self._redis:
            try:
                raw = self._redis.get(self._key(user_id))
                return ConversationSession.from_json(raw) if raw else None
            except Exception as e:
                logger.error(f"Redis 读取会话失败，降级到内存：{e}")
        
        return self._store.get(user_id)

    def _persist(self, session: ConversationSession) -> None:
        """持久化会话"""
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
        """清理内存中过期的会话"""
        expired = [
            uid for uid, s in self._store.items()
            if s.is_expired(self.idle_timeout)
        ]
        for uid in expired:
            del self._store[uid]

    @staticmethod
    def _try_connect_redis():
        """尝试连接Redis"""
        try:
            import redis
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
