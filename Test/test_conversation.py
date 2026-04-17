"""
conversation.py 单元测试
运行：python -m pytest test_conversation.py -v
"""
import time
import pytest
from conversation import ConversationSession, ConversationManager, Message


# ─────────────────────────────────────────────────────────────────────────────
# ConversationSession
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationSession:

    def test_add_messages_and_turn_count(self):
        s = ConversationSession("u1")
        s.add_user_message("你好")
        assert s.turn_count == 0        # assistant 还没回复，轮次不增加
        s.add_assistant_message("你好！")
        assert s.turn_count == 1
        assert len(s.messages) == 2

    def test_get_messages_for_api_format(self):
        s = ConversationSession("u1")
        s.add_user_message("问题")
        s.add_assistant_message("答案")
        msgs = s.get_messages_for_api()
        assert msgs == [
            {"role": "user",      "content": "问题"},
            {"role": "assistant", "content": "答案"},
        ]
        # 不含 ts 字段
        assert "ts" not in msgs[0]

    def test_trim_removes_oldest_turn(self):
        s = ConversationSession("u1")
        # 写入 3 轮
        for i in range(3):
            s.add_user_message(f"问{i}")
            s.add_assistant_message(f"答{i}")
        assert len(s.messages) == 6

        s.trim(max_turns=2)
        assert len(s.messages) == 4
        # 最旧的一轮（问0/答0）被删除，剩下问1/答1/问2/答2
        assert s.messages[0].content == "问1"

    def test_trim_no_op_when_within_limit(self):
        s = ConversationSession("u1")
        s.add_user_message("q")
        s.add_assistant_message("a")
        s.trim(max_turns=5)
        assert len(s.messages) == 2     # 未变化

    def test_is_expired(self):
        s = ConversationSession("u1")
        assert not s.is_expired(idle_timeout=30)
        # 手动将 last_active 拨到过去
        s.last_active = time.time() - 31
        assert s.is_expired(idle_timeout=30)

    def test_json_roundtrip(self):
        s = ConversationSession("u99")
        s.add_user_message("序列化测试")
        s.add_assistant_message("反序列化成功")
        raw = s.to_json()
        restored = ConversationSession.from_json(raw)
        assert restored.user_id == "u99"
        assert restored.turn_count == 1
        assert len(restored.messages) == 2
        assert restored.messages[0].content == "序列化测试"
        assert restored.messages[1].role == "assistant"

    def test_get_messages_with_max_turns_limit(self):
        s = ConversationSession("u1")
        for i in range(5):
            s.add_user_message(f"q{i}")
            s.add_assistant_message(f"a{i}")
        # 只取最近 2 轮
        msgs = s.get_messages_for_api(max_turns=2)
        assert len(msgs) == 4
        assert msgs[0]["content"] == "q3"

    def test_summary_fields(self):
        s = ConversationSession("u1")
        s.add_user_message("hi")
        summary = s.summary()
        assert "user_id"    in summary
        assert "turn_count" in summary
        assert "msg_count"  in summary


# ─────────────────────────────────────────────────────────────────────────────
# ConversationManager（内存模式）
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationManager:

    def setup_method(self):
        self.mgr = ConversationManager(
            max_turns=3,
            idle_timeout=2,     # 2 秒超时，方便测试
            max_sessions=5,
        )

    def test_get_or_create_new_session(self):
        s = self.mgr.get_or_create("user_a")
        assert s.user_id == "user_a"
        assert len(s.messages) == 0

    def test_session_persists_across_calls(self):
        s = self.mgr.get_or_create("user_b")
        s.add_user_message("你好")
        s.add_assistant_message("你好！")
        self.mgr.save(s)

        s2 = self.mgr.get_or_create("user_b")
        assert len(s2.messages) == 2
        assert s2.messages[0].content == "你好"

    def test_different_users_isolated(self):
        s1 = self.mgr.get_or_create("user_x")
        s1.add_user_message("x 的消息")
        self.mgr.save(s1)

        s2 = self.mgr.get_or_create("user_y")
        assert len(s2.messages) == 0

    def test_session_resets_after_timeout(self):
        s = self.mgr.get_or_create("user_c")
        s.add_user_message("旧消息")
        s.add_assistant_message("旧回复")
        self.mgr.save(s)

        time.sleep(2.1)   # 等待超时

        s_new = self.mgr.get_or_create("user_c")
        assert len(s_new.messages) == 0   # 新会话，历史已清空

    def test_trim_on_save(self):
        s = self.mgr.get_or_create("user_d")
        # 写入超过 max_turns(3) 的轮次
        for i in range(5):
            s.add_user_message(f"q{i}")
            s.add_assistant_message(f"a{i}")
        self.mgr.save(s)

        s_reloaded = self.mgr.get_or_create("user_d")
        # 最多保留 3 轮 = 6 条
        assert len(s_reloaded.messages) <= 6

    def test_delete_session(self):
        s = self.mgr.get_or_create("user_e")
        s.add_user_message("要被删的消息")
        self.mgr.save(s)
        self.mgr.delete("user_e")

        s_new = self.mgr.get_or_create("user_e")
        assert len(s_new.messages) == 0

    def test_lru_eviction_when_full(self):
        # 填满 5 个会话
        for i in range(5):
            s = self.mgr.get_or_create(f"evict_user_{i}")
            s.add_user_message("msg")
            self.mgr.save(s)

        # 插入第 6 个，应淘汰最早的
        s6 = self.mgr.get_or_create("evict_user_5")
        s6.add_user_message("new")
        self.mgr.save(s6)
        assert len(self.mgr._store) <= 5

    def test_stats_returns_dict(self):
        stat = self.mgr.stats()
        assert "backend"         in stat
        assert "active_sessions" in stat
        assert stat["backend"]   == "memory"
