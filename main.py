"""
Feishu Agent 主程序
集成：飞书机器人 · RAG 知识库 · DeepSeek API · P0 安全 · 多轮对话

改动标注：
  # [P0]   — 签名验证 / 消息去重
  # [CONV] — 多轮对话上下文
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# # --- 新增：屏蔽警告和强制离线 ---
# import warnings
# warnings.filterwarnings("ignore") 
# os.environ['TRANSFORMERS_OFFLINE'] = '1'
# os.environ['HF_HUB_OFFLINE'] = '1'

try:
    import requests
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    logger.warning("缺少 Flask 依赖，请运行：pip install flask requests")

try:
    from rag_engine import RAGEngine
    HAS_RAG = True
except ImportError as e:
    HAS_RAG = False
    logger.error(f"无法导入 RAG 引擎：{e}")

# [P0]   安全模块
from security import FeishuSignatureVerifier, MessageDeduplicator
# [CONV] 多轮对话模块
from conversation import ConversationManager


# ─────────────────────────────────────────────────────────────────────────────
# DeepSeek API 客户端（与原版相同）
# ─────────────────────────────────────────────────────────────────────────────

class DeepSeekAPI:
    def __init__(self, api_key: str = None):
        self.api_key  = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1"
        self.model    = os.getenv("MODEL_NAME", "deepseek-chat")

    def chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        if not self.api_key:
            logger.error("DeepSeek API 密钥未设置")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model":       self.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败：{e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# FeishuAgent
# ─────────────────────────────────────────────────────────────────────────────

# 特殊指令：用户可发送这些文本主动重置会话
RESET_COMMANDS = {"/reset", "/新对话", "/清除记忆", "重置对话"}

SYSTEM_PROMPT = """你是游戏音频设计师，仅基于提供的参考资料回答问题。
如果参考资料足够，提取关键信息直接回答，不要添加"根据参考资料"等废话。
如果资料不足，明确说"参考资料中未找到相关信息，建议查阅[具体手册]"。
回答格式：1-2句核心答案 + 可选的关键参数/设置建议。保持简洁专业。
你能记住本次对话中用户之前问过的问题，可以自然地引用上下文。"""


class FeishuAgent:
    def __init__(self):
        self.app_id     = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.rag        = None
        self.deepseek   = None

        # [CONV] 多轮对话管理器
        self.conv_manager = ConversationManager(
            max_turns    = int(os.getenv("CONV_MAX_TURNS",    10)),
            idle_timeout = int(os.getenv("CONV_IDLE_TIMEOUT", 1800)),
            max_sessions = int(os.getenv("CONV_MAX_SESSIONS", 5000)),
        )

        self._init_components()

    def _init_components(self):
        if HAS_RAG:
            try:
                self.rag = RAGEngine()
                logger.info("RAG 引擎初始化成功")
            except Exception as e:
                logger.error(f"RAG 引擎初始化失败：{e}")
        else:
            logger.warning("RAG 引擎不可用")

        if os.getenv("DEEPSEEK_API_KEY"):
            self.deepseek = DeepSeekAPI()
            logger.info("DeepSeek API 初始化成功")
        else:
            logger.warning("DeepSeek API 密钥未设置，部分功能受限")

    # ── 核心：处理用户消息 ────────────────────────────────────────────────────

    def process_message(
        self,
        user_message: str,
        user_id: str = "cli_user",   # [CONV] 必须传入，用于会话隔离
    ) -> Dict[str, Any]:
        logger.info(f"处理消息：user_id={user_id}，内容={user_message!r}")

        # ── [CONV-1] 检查重置指令 ────────────────────────────────────────────
        if user_message.strip() in RESET_COMMANDS:
            self.conv_manager.delete(user_id)
            return {
                "success": True,
                "answer":  "✅ 对话已重置，我们重新开始吧！",
                "source":  "system",
                "has_context": False,
                "rag_confidence": 0.0,
                "rag_sources":   [],
                "rag_type":      "system",
            }

        # ── [CONV-2] 取出历史会话 ─────────────────────────────────────────────
        session = self.conv_manager.get_or_create(user_id)
        session.add_user_message(user_message)

        # ── RAG 检索 ──────────────────────────────────────────────────────────
        context    = ""
        rag_result = None
        if self.rag:
            try:
                rag_result = self.rag.search(user_message, k=5, return_format="structured")
                if rag_result and rag_result.get("confidence", 0) > 0.1:
                    context = rag_result.get("answer", "")
                    logger.info(
                        f"RAG 检索成功，置信度={rag_result.get('confidence', 0):.3f}，"
                        f"来源数={len(rag_result.get('sources', []))}"
                    )
            except Exception as e:
                logger.error(f"RAG 检索失败：{e}")

        # ── [CONV-3] 构建 messages（system + 历史 + 当轮 RAG 注入）────────────
        #
        # 结构：
        #   [ system ]
        #   [ ...历史 user/assistant 轮次（不含本轮 user）... ]
        #   [ user：本轮问题 + RAG 参考信息 ]
        #
        # 注意：本轮的 user message 已经通过 session.add_user_message 写入，
        # 这里从历史里取"除了最后一条（本轮 user）"之外的部分作为历史，
        # 然后单独构造含 RAG 的本轮 user message，拼在最后。

        history_messages = session.get_messages_for_api()   # 含本轮 user
        past_messages    = history_messages[:-1]             # 历史轮次（不含本轮）

        rag_block = (
            f"\n\n参考信息：\n{context}"
            if context
            else "\n\n参考信息：暂无相关参考信息。"
        )
        current_user_content = f"用户问题：{user_message}{rag_block}\n\n请用中文回答："

        api_messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + past_messages
            + [{"role": "user", "content": current_user_content}]
        )

        # ── 调用 DeepSeek ─────────────────────────────────────────────────────
        answer = None
        if self.deepseek:
            answer = self.deepseek.chat_completion(api_messages)

        # ── [CONV-4] 将 AI 回复写回会话并保存 ──────────────────────────────────
        if answer:
            session.add_assistant_message(answer)
            self.conv_manager.save(session)
            logger.info(
                f"[CONV] 会话已保存：user_id={user_id}，"
                f"共 {session.turn_count} 轮，{len(session.messages)} 条消息"
            )
            return {
                "success":        True,
                "answer":         answer,
                "has_context":    bool(context),
                "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
                "rag_sources":    rag_result.get("sources",    []) if rag_result else [],
                "rag_type":       rag_result.get("type",  "unknown") if rag_result else "unknown",
                "source":         "deepseek_rag" if context else "deepseek_only",
                "turn_count":     session.turn_count,   # [CONV] 供调试使用
            }

        # ── 降级回复 ──────────────────────────────────────────────────────────
        # DeepSeek 不可用时，不写回会话（避免污染历史）
        fallback = (
            f"根据知识库信息：\n\n{context[:500]}..."
            if context
            else "AI 服务暂时不可用，请稍后再试。"
        )
        return {
            "success":        bool(context),
            "answer":         fallback,
            "has_context":    bool(context),
            "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
            "rag_sources":    rag_result.get("sources",    []) if rag_result else [],
            "rag_type":       rag_result.get("type",  "unknown") if rag_result else "unknown",
            "source":         "rag_only" if context else "fallback",
            "turn_count":     session.turn_count,
        }

    # ── 飞书 API ───────────────────────────────────────────────────────────────

    def get_tenant_access_token(self) -> Optional[str]:
        if not self.app_id or not self.app_secret:
            logger.error("飞书 App ID 或 Secret 未设置")
            return None
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                return result["tenant_access_token"]
            logger.error(f"获取访问令牌失败：{result}")
        except Exception as e:
            logger.error(f"获取访问令牌时出错：{e}")
        return None

    def reply_to_feishu(self, message_id: str, content: str, token: str = None) -> bool:
        if not token:
            token = self.get_tenant_access_token()
        if not token:
            return False
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "content":  json.dumps({"text": content}),
                    "msg_type": "text",
                },
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 0:
                logger.info("成功回复飞书消息")
                return True
            logger.error(f"回复飞书消息失败：{result}")
        except Exception as e:
            logger.error(f"回复飞书消息时出错：{e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Flask Webhook
# ─────────────────────────────────────────────────────────────────────────────

if HAS_FLASK:
    app = Flask(__name__)

    _verifier: Optional[FeishuSignatureVerifier] = None
    _dedup:    Optional[MessageDeduplicator]     = None

    def get_verifier() -> Optional[FeishuSignatureVerifier]:
        global _verifier
        if _verifier is None:
            secret = os.getenv("FEISHU_APP_SECRET")
            if secret:
                _verifier = FeishuSignatureVerifier(secret)
            else:
                logger.error("[P0] FEISHU_APP_SECRET 未设置，签名验证已禁用！")
        return _verifier

    def get_dedup() -> MessageDeduplicator:
        global _dedup
        if _dedup is None:
            _dedup = MessageDeduplicator(
                ttl=int(os.getenv("DEDUP_TTL", 60)),
                max_memory_size=int(os.getenv("DEDUP_MAX_MEMORY", 2000)),
            )
        return _dedup

    @app.route('/webhook/feishu', methods=['POST'])
    def feishu_webhook():
        try:
            raw_body = request.get_data()

            # [P0] 签名验证
            verifier = get_verifier()
            if verifier:
                valid, reason = verifier.verify(
                    request.headers.get("X-Lark-Request-Timestamp", ""),
                    request.headers.get("X-Lark-Request-Nonce",     ""),
                    raw_body,
                    request.headers.get("X-Lark-Signature",         ""),
                )
                if not valid:
                    logger.warning(f"[P0] 签名验证失败：{reason} | IP={request.remote_addr}")
                    return jsonify({"code": 0}), 200

            data = request.json
            if not data:
                return jsonify({"code": 1, "msg": "invalid json"}), 400

            logger.info(f"收到飞书 webhook：{json.dumps(data, ensure_ascii=False)}")

            if data.get("type") == "url_verification":
                return jsonify({"challenge": data.get("challenge")})

            if data.get("type") == "event_callback":
                event        = data.get("event", {})
                if event.get("type") == "message":
                    message_id   = event.get("message_id")
                    user_message = event.get("text", "").strip()
                    user_id      = event.get("sender", {}).get("user_id")

                    # [P0] 消息去重
                    if get_dedup().is_duplicate(message_id):
                        logger.info(f"[P0] 重复消息已忽略：message_id={message_id}")
                        return jsonify({"code": 0}), 200

                    if user_message and user_id:
                        # [CONV] user_id 传入，实现会话隔离
                        result = agent.process_message(user_message, user_id)
                        if message_id and result.get("success"):
                            agent.reply_to_feishu(message_id, result["answer"])

                return jsonify({"code": 0, "msg": "success"})

            return jsonify({"code": 1, "msg": "unsupported event type"})

        except Exception as e:
            logger.error(f"处理 webhook 时出错：{e}")
            return jsonify({"code": 500, "msg": "internal server error"}), 500

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status":  "healthy",
            "service": "feishu_agent",
            "dedup":   get_dedup().stats(),
            "conv":    agent.conv_manager.stats(),          # [CONV]
            "signature_verification": get_verifier() is not None,
        })

else:
    app = None


# ─────────────────────────────────────────────────────────────────────────────
# 命令行模式（支持多轮对话）
# ─────────────────────────────────────────────────────────────────────────────

def cli_mode():
    print("=" * 55)
    print("Feishu Agent 命令行模式（多轮对话已启用）")
    print(f"重置指令：{' / '.join(RESET_COMMANDS)}")
    print("=" * 55)

    cli_user_id = "cli_user"

    while True:
        try:
            print("\n请输入问题（输入 'quit' 退出）：")
            user_input = input("> ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break
            if not user_input:
                continue

            result = agent.process_message(user_input, cli_user_id)

            print("\n" + "─" * 55)
            print(result["answer"])
            print(f"\n来源：{result['source']}  |  "
                  f"对话轮次：{result.get('turn_count', 0)}  |  "
                  f"RAG 置信度：{result.get('rag_confidence', 0):.2f}")
            if result.get("has_context"):
                print("✓ 使用了知识库信息")
            print("─" * 55)

        except KeyboardInterrupt:
            print("\n\n程序已终止")
            break
        except Exception as e:
            print(f"发生错误：{e}")


if __name__ == "__main__":
    # 选择使用基础 Agent 还是工具感知 Agent
    use_tool_agent = os.getenv("USE_TOOL_AGENT", "false").lower() == "true"
    if use_tool_agent:
        try:
            from tool_agent import get_tool_aware_agent
            agent = get_tool_aware_agent()
            print("✅ 使用工具感知 Agent（工具功能已启用）")
        except ImportError as e:
            print(f"⚠️  无法导入工具感知 Agent，回退到基础 Agent: {e}")
            agent = FeishuAgent()
    else:
        agent = FeishuAgent()
        print("ℹ️  使用基础 Agent")

    use_webhook = os.getenv("USE_WEBHOOK", "false").lower() == "true"

    if use_webhook and HAS_FLASK:
        print("启动 Feishu Agent Webhook 服务器（P0 安全 + 多轮对话已启用）...")
        app.run(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", 5000)),
            debug=False,
        )
    else:
        cli_mode()
