"""
security.py 单元测试
运行：python -m pytest test_security.py -v
"""
import time
import hmac
import hashlib
import pytest
from security import FeishuSignatureVerifier, MessageDeduplicator


# ───────────────────────────────────────────────
# FeishuSignatureVerifier 测试
# ───────────────────────────────────────────────

SECRET = "test_app_secret_123"

def _make_sig(secret, timestamp, nonce, body: bytes) -> str:
    message = f"{timestamp}\n{nonce}\n".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class TestSignatureVerifier:
    def setup_method(self):
        self.v = FeishuSignatureVerifier(SECRET, max_timestamp_diff=300)

    def test_valid_signature(self):
        ts    = str(int(time.time()))
        nonce = "abc123"
        body  = b'{"type":"event_callback"}'
        sig   = _make_sig(SECRET, ts, nonce, body)
        ok, reason = self.v.verify(ts, nonce, body, sig)
        assert ok, reason

    def test_wrong_signature(self):
        ts    = str(int(time.time()))
        nonce = "abc123"
        body  = b'{"type":"event_callback"}'
        ok, reason = self.v.verify(ts, nonce, body, "deadbeef")
        assert not ok
        assert "签名不匹配" in reason

    def test_expired_timestamp(self):
        ts    = str(int(time.time()) - 400)   # 超出 300s 窗口
        nonce = "abc123"
        body  = b'{}'
        sig   = _make_sig(SECRET, ts, nonce, body)
        ok, reason = self.v.verify(ts, nonce, body, sig)
        assert not ok
        assert "timestamp 超出" in reason

    def test_future_timestamp_within_window(self):
        ts    = str(int(time.time()) + 10)    # 轻微时钟偏差
        nonce = "xyz"
        body  = b'{"hello":"world"}'
        sig   = _make_sig(SECRET, ts, nonce, body)
        ok, _  = self.v.verify(ts, nonce, body, sig)
        assert ok

    def test_invalid_timestamp_format(self):
        ok, reason = self.v.verify("not-a-number", "n", b"body", "sig")
        assert not ok
        assert "格式非法" in reason

    def test_empty_secret_raises(self):
        with pytest.raises(ValueError):
            FeishuSignatureVerifier("")

    def test_case_insensitive_signature(self):
        ts    = str(int(time.time()))
        nonce = "n1"
        body  = b"data"
        sig   = _make_sig(SECRET, ts, nonce, body).upper()   # 大写
        ok, _ = self.v.verify(ts, nonce, body, sig)
        assert ok


# ───────────────────────────────────────────────
# MessageDeduplicator 测试（内存模式）
# ───────────────────────────────────────────────

class TestMessageDeduplicator:
    def setup_method(self):
        self.dedup = MessageDeduplicator(ttl=1, max_memory_size=5)

    def test_first_seen_not_duplicate(self):
        assert self.dedup.is_duplicate("msg-001") is False

    def test_second_seen_is_duplicate(self):
        self.dedup.is_duplicate("msg-002")
        assert self.dedup.is_duplicate("msg-002") is True

    def test_expired_message_reprocessed(self):
        self.dedup.is_duplicate("msg-003")
        time.sleep(1.1)                          # 等 TTL 过期
        assert self.dedup.is_duplicate("msg-003") is False   # 应视为新消息

    def test_different_ids_not_duplicate(self):
        self.dedup.is_duplicate("msg-A")
        assert self.dedup.is_duplicate("msg-B") is False

    def test_lru_eviction_when_full(self):
        # 填满缓存（容量 5）
        for i in range(5):
            self.dedup.is_duplicate(f"msg-{i}")
        # 插入第 6 条，应淘汰最早的 msg-0
        self.dedup.is_duplicate("msg-5")
        # msg-0 被淘汰后，再次处理不应被认定为重复
        assert self.dedup.is_duplicate("msg-0") is False

    def test_empty_message_id_not_duplicate(self):
        assert self.dedup.is_duplicate("") is False
        assert self.dedup.is_duplicate(None) is False

    def test_stats_returns_dict(self):
        s = self.dedup.stats()
        assert "backend" in s
        assert s["backend"] == "memory"
