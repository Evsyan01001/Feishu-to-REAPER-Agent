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
import types
from typing import Dict, Any, Optional, Generator
from dotenv import load_dotenv

load_dotenv()

class PromptManager:
    def __init__(self, file_path="instructions.md"):
        self.file_path = os.path.join(os.path.dirname(__file__), "..", file_path)
        # 初始化时直接一个最基础的，不读文件，确保启动最快
        self._cached_prompt = "你是一个专业的游戏音频设计师。"
        self._has_loaded = False

    def get_prompt(self):
        """获取当前提示词（默认从内存读）"""
        return self._cached_prompt

    def reload(self):
        """主动触发更新：只有调用这个方法，才会去读硬盘"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._cached_prompt = f.read().strip()
                    self._has_loaded = True
                print("🔄 [System] 指令文件已手动同步到内存")
                return True
            except Exception as e:
                print(f"❌ 同步失败: {e}")
        return False

prompt_manager = PromptManager()

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

    def chat_completion_stream(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Generator[str, None, None]:
        if not self.api_key:
            print("DeepSeek API 密钥未设置")
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
            "stream":       True,
        }
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                # 移除 'data: ' 前缀
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    line = line[6:]

                # 检查是否结束
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"DeepSeek API 流式调用失败：{e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# FeishuAgent
# ─────────────────────────────────────────────────────────────────────────────

# 特殊指令：用户可发送这些文本主动重置会话
RESET_COMMANDS = {"/reset", "/新对话", "/清除记忆", "重置对话"}

SYSTEM_PROMPT = prompt_manager.get_prompt()


class FeishuAgent:
    def __init__(self):
        self.app_id     = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.rag        = None
        self.deepseek   = None
        self.reaper_controller = True  # REAPER控制器

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

        # 初始化REAPER控制器
        self._init_reaper_controller()

    # ── REAPER控制器相关方法 ──────────────────────────────────────────────────

    def _init_reaper_controller(self):
        """初始化REAPER控制器"""
        # 检查是否启用REAPER控制器
        enable_reaper = os.getenv("ENABLE_REAPER_CONTROLLER", "false").lower() == "true"
        if not enable_reaper:
            logger.info("REAPER控制器未启用（设置ENABLE_REAPER_CONTROLLER=true启用）")
            return

        try:
            from reaper_controller import ReaperController
            self.reaper_controller = ReaperController()
            logger.info("REAPER控制器初始化成功")
        except ImportError as e:
            logger.warning(f"REAPER控制器导入失败: {e}")
        except Exception as e:
            logger.error(f"REAPER控制器初始化失败: {e}")

    def _try_process_reaper_command(self, user_input: str) -> Optional[Dict[str, Any]]:
        """尝试处理REAPER指令"""
        if not self.reaper_controller:
            return None

        # 使用REAPER控制器的指令解析器检测是否为REAPER指令
        try:
            if not self.reaper_controller.parser.is_reaper_command(user_input):
                return None
        except AttributeError:
            # 如果parser不存在，回退到简单关键词检测
            reaper_keywords = ["播放", "暂停", "录音", "轨道", "音量", "导出", "剪切", "复制", "粘贴"]
            if not any(keyword in user_input for keyword in reaper_keywords):
                return None

        # 调用REAPER控制器处理
        return self.reaper_controller.process_command(user_input)

    def _build_reaper_response(self, reaper_result: Dict[str, Any], session) -> Dict[str, Any]:
        """构建REAPER指令响应"""
        success = reaper_result.get("success", False)

        if success:
            answer = f"✅ {reaper_result.get('message', '指令已执行')}"
        else:
            error_msg = reaper_result.get("error", "未知错误")
            suggestion = reaper_result.get("suggestion", "")
            answer = f"❌ REAPER指令处理失败: {error_msg}"
            if suggestion:
                answer += f"\n\n建议: {suggestion}"

        return {
            "success": success,
            "answer": answer,
            "source": "reaper_controller",
            "has_context": False,
            "rag_confidence": 0.0,
            "rag_sources": [],
            "rag_type": "system",
            "turn_count": session.turn_count,
            "reaper_command": reaper_result.get("command"),
            "reaper_intent": reaper_result.get("intent", {})
        }

    # ── 核心：处理用户消息 ────────────────────────────────────────────────────

    def process_message(
        self,
        user_message: str,
        user_id: str = "cli_user",   # [CONV] 必须传入，用于会话隔离
    ) -> Dict[str, Any]:
        logger.info(f"处理消息：user_id={user_id}，内容={user_message!r}")

        if user_message.strip() == "/update_prompt":
            if prompt_manager.reload():
                # 同步更新全局变量（可选，为了双重保险）
                global SYSTEM_PROMPT
                SYSTEM_PROMPT = prompt_manager.get_prompt()
                return {"answer": "✅ 系统指令已刷新！现在我已加载最新的 instructions.md 逻辑。", "source": "System"}
            else:
                return {"answer": "❌ 刷新失败，请检查 instructions.md 是否存在。", "source": "System"}
            

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

        current_system_prompt = prompt_manager.get_prompt()
        messages = [{"role": "system", "content": prompt_manager.get_prompt()}] # 动态获取

        # ── REAPER指令处理 ──────────────────────────────────────────────────────
        reaper_result = self._try_process_reaper_command(user_message)
        if reaper_result and reaper_result.get("success"):
            # 如果是REAPER指令，直接返回结果，不调用AI
            return self._build_reaper_response(reaper_result, session)

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

        # --- 这里统一使用 prompt_manager.get_prompt() ---
        api_messages = (
            [{"role": "system", "content": prompt_manager.get_prompt()}]
            + past_messages
            + [{"role": "user", "content": current_user_content}]
        )

        # ── 调用 DeepSeek ─────────────────────────────────────────────────────
        answer = None
        if self.deepseek:
            answer = self.deepseek.chat_completion_stream(api_messages)

        # ── [CONV-4] 将 AI 回复写回会话并保存 ──────────────────────────────────
        if answer:
            return {
                "success":        True,
                "answer":         answer,
                "is_stream":      True,  # [CONV] 供前端区分是否流式响应
                "session":         session,  # [CONV] 供前端在流式过程中更新会话状态    
                "has_context":    bool(context),
                "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
                "rag_sources":    rag_result.get("sources",    []) if rag_result else [],
                "rag_type":       rag_result.get("type",  "unknown") if rag_result else "unknown",
                "source":         "deepseek_rag" if context else "deepseek_only",
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
            if user_input.lower() in ['quit', 'exit', 'q']: break
            if not user_input: continue

            result = agent.process_message(user_input, cli_user_id)

            print("\n" + "─" * 55)

            # 判断是否为流式结果
            if isinstance(result.get("answer"), (Generator, types.GeneratorType)):
                print("AI 回复：", end="", flush=True)
                full_answer = []

                # 1. 真正的流式迭代发生在这里
                for chunk in result["answer"]:
                    print(chunk, end="", flush=True)
                    full_answer.append(chunk)
                print()  # 输出完成后换行
                
                # 2. 迭代完成后，合并成完整字符串
                final_answer = "".join(full_answer)

                # 3. 更新 session 并保存，这会触发 turn_count += 1
                curr_session = result["session"]
                curr_session.add_assistant_message(final_answer)
                agent.conv_manager.save(curr_session)

                # 4. 获取最新的轮次
                actual_turns = curr_session.turn_count
            else:
                print(result["answer"])
                actual_turns = result.get("turn_count", 0)

            print(f"\n来源：{result['source']}  |  "
                  f"对话轮次：{actual_turns}  |  "
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
    agent = FeishuAgent()
    print("ℹ️  使用基础 Agent")
    cli_mode()
