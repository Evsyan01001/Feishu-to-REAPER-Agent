"""
工具感知的 Feishu Agent

继承自 FeishuAgent，添加工具调用能力
通过提示词工程解决 DeepSeek 不支持 function calling 的限制
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Tuple, List

# 导入基础 Agent
try:
    from main import FeishuAgent, RESET_COMMANDS, SYSTEM_PROMPT
except ImportError as e:
    logging.error(f"无法导入 FeishuAgent: {e}")
    raise

# 导入工具相关模块
from tool_registry import get_tool_registry, init_tool_registry
from tool_orchestrator import get_tool_orchestrator, init_tool_orchestrator, ToolIntent, ToolResult
from prompt_engine import get_prompt_engine, init_prompt_engine
from mcp_client import init_mcp_client

logger = logging.getLogger(__name__)


class ToolAwareFeishuAgent(FeishuAgent):
    """
    工具感知的 Feishu Agent

    在原有 FeishuAgent 基础上添加：
    1. MCP 客户端连接和工具发现
    2. 工具意图检测和执行
    3. 提示词工程整合工具上下文
    4. 工具结果处理和错误恢复

    配置通过环境变量：
    - USE_TOOLS: 是否启用工具功能（默认false）
    - AUTO_EXECUTE_TOOLS: 是否自动执行检测到的工具（默认true）
    - TOOL_CONFIRMATION_THRESHOLD: 工具确认阈值（默认0.6）
    """

    def __init__(self):
        """初始化工具感知 Agent"""
        # 先调用父类初始化
        super().__init__()

        # 工具功能配置
        self.use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
        self.auto_execute_tools = os.getenv("AUTO_EXECUTE_TOOLS", "true").lower() == "true"
        self.tool_confirmation_threshold = float(os.getenv("TOOL_CONFIRMATION_THRESHOLD", "0.6"))

        # 工具组件
        self.tool_registry = None
        self.tool_orchestrator = None
        self.prompt_engine = None

        # 工具调用状态
        self._tool_components_initialized = False
        self._tool_enabled = False

        # 初始化工具组件
        self._init_tool_components()

        logger.info(f"工具感知 Agent 初始化: use_tools={self.use_tools}, "
                   f"auto_execute_tools={self.auto_execute_tools}")

    def _init_tool_components(self):
        """初始化工具相关组件"""
        if not self.use_tools:
            logger.info("工具功能已禁用，跳过工具组件初始化")
            return

        try:
            # 初始化 MCP 客户端
            mcp_initialized = init_mcp_client()
            if not mcp_initialized:
                logger.warning("MCP 客户端初始化失败，工具功能将不可用")
                return

            # 初始化工具注册表
            registry_initialized = init_tool_registry()
            if not registry_initialized:
                logger.warning("工具注册表初始化失败，工具功能将不可用")
                return

            # 初始化工具协调器
            orchestrator_initialized = init_tool_orchestrator()
            if not orchestrator_initialized:
                logger.warning("工具协调器初始化失败，工具功能将受限")
                # 仍然继续，因为可能只需要基本功能

            # 初始化提示词引擎
            prompt_engine_initialized = init_prompt_engine()
            if not prompt_engine_initialized:
                logger.warning("提示词引擎初始化失败，将使用基础提示词")
                # 仍然继续，使用基础功能

            # 获取组件实例
            self.tool_registry = get_tool_registry()
            self.tool_orchestrator = get_tool_orchestrator()
            self.prompt_engine = get_prompt_engine()

            self._tool_components_initialized = True
            self._tool_enabled = True

            logger.info("工具组件初始化成功")
            self._log_tool_status()

        except Exception as e:
            logger.error(f"工具组件初始化失败: {e}")
            self._tool_enabled = False

    def _log_tool_status(self):
        """记录工具状态"""
        if not self._tool_enabled or not self.tool_registry:
            return

        tools = self.tool_registry.get_all_tools()
        registry_status = self.tool_registry.get_registry_status()

        logger.info(f"工具状态: 已连接={registry_status.get('connected', False)}, "
                   f"工具数量={len(tools)}")

        # 记录可用工具（前5个）
        if tools:
            tool_names = list(tools.keys())[:5]
            logger.info(f"可用工具: {', '.join(tool_names)}"
                       f"{'...' if len(tools) > 5 else ''}")

    # ── 重写核心消息处理方法 ────────────────────────────────────────────────────

    def process_message(
        self,
        user_message: str,
        user_id: str = "cli_user",
    ) -> Dict[str, Any]:
        """
        处理用户消息（工具感知版本）

        扩展原有流程，添加：
        1. 工具意图检测
        2. 工具调用执行
        3. 提示词工程整合
        4. 工具结果处理

        Args:
            user_message: 用户消息
            user_id: 用户ID

        Returns:
            Dict[str, Any]: 处理结果，包含工具调用信息
        """
        logger.info(f"工具感知处理消息: user_id={user_id}，内容={user_message!r}")

        # ── [CONV-1] 检查重置指令 ────────────────────────────────────────────────
        if user_message.strip() in RESET_COMMANDS:
            self.conv_manager.delete(user_id)
            return {
                "success": True,
                "answer": "✅ 对话已重置，我们重新开始吧！",
                "source": "system",
                "has_context": False,
                "rag_confidence": 0.0,
                "rag_sources": [],
                "rag_type": "system",
                "tool_used": False,
                "tool_result": None,
            }

        # ── [CONV-2] 取出历史会话 ────────────────────────────────────────────────
        session = self.conv_manager.get_or_create(user_id)
        session.add_user_message(user_message)

        # ── RAG 检索 ────────────────────────────────────────────────────────────
        context = ""
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

        # ── 工具处理 ────────────────────────────────────────────────────────────
        tool_intent = None
        tool_result = None
        tool_processed = False

        if self._tool_enabled and self.tool_orchestrator:
            tool_intent, tool_result, tool_processed = self._process_tools(
                user_message, user_id, context
            )

        # ── 构建 AI 消息 ─────────────────────────────────────────────────────────
        api_messages = self._build_ai_messages(
            session=session,
            user_message=user_message,
            rag_context=context,
            tool_intent=tool_intent,
            tool_result=tool_result
        )

        # ── 调用 DeepSeek ───────────────────────────────────────────────────────
        answer = None
        if self.deepseek:
            answer = self.deepseek.chat_completion(api_messages)

        # ── [CONV-4] 将 AI 回复写回会话并保存 ────────────────────────────────────
        if answer:
            session.add_assistant_message(answer)
            self.conv_manager.save(session)
            logger.info(
                f"[CONV] 会话已保存：user_id={user_id}，"
                f"共 {session.turn_count} 轮，{len(session.messages)} 条消息"
            )

            # 构建返回结果
            return self._build_response(
                answer=answer,
                has_context=bool(context),
                rag_result=rag_result,
                tool_intent=tool_intent,
                tool_result=tool_result,
                tool_processed=tool_processed,
                session=session
            )

        # ── 降级回复 ────────────────────────────────────────────────────────────
        # DeepSeek 不可用时，不写回会话（避免污染历史）
        fallback = self._build_fallback_response(context, rag_result)
        return {
            "success": bool(context),
            "answer": fallback,
            "has_context": bool(context),
            "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
            "rag_sources": rag_result.get("sources", []) if rag_result else [],
            "rag_type": rag_result.get("type", "unknown") if rag_result else "unknown",
            "source": "rag_only" if context else "fallback",
            "turn_count": session.turn_count,
            "tool_used": tool_processed,
            "tool_result": tool_result.to_dict() if tool_result else None,
        }

    def _process_tools(
        self,
        user_message: str,
        user_id: str,
        rag_context: str
    ) -> Tuple[Optional[ToolIntent], Optional[ToolResult], bool]:
        """
        处理工具调用

        Args:
            user_message: 用户消息
            user_id: 用户ID
            rag_context: RAG上下文

        Returns:
            Tuple[Optional[ToolIntent], Optional[ToolResult], bool]:
            (工具意图, 工具结果, 是否处理了工具)
        """
        try:
            # 检测工具意图
            intent = self.tool_orchestrator.detect_intent(user_message, user_id)
            if not intent:
                logger.debug("未检测到工具调用意图")
                return None, None, False

            logger.info(f"检测到工具意图: {intent.tool_name} (置信度: {intent.confidence:.2f})")

            # 检查是否需要用户确认
            need_confirmation = (
                not self.auto_execute_tools or
                intent.confidence < self.tool_confirmation_threshold
            )

            if need_confirmation:
                # 这里可以添加用户确认逻辑
                # 目前版本中，我们记录日志但不阻止执行
                logger.info(f"工具需要确认: {intent.tool_name} (置信度: {intent.confidence:.2f} < {self.tool_confirmation_threshold})")
                # 继续执行，但标记为需要确认

            # 执行工具
            context = {
                "user_id": user_id,
                "rag_context": rag_context,
                "auto_execute": self.auto_execute_tools
            }
            result = self.tool_orchestrator.execute_tool(intent, context)

            logger.info(f"工具执行完成: {intent.tool_name}, 成功={result.success}")

            return intent, result, True

        except Exception as e:
            logger.error(f"工具处理失败: {e}")
            return None, None, False

    def _build_ai_messages(
        self,
        session,
        user_message: str,
        rag_context: str,
        tool_intent: Optional[ToolIntent] = None,
        tool_result: Optional[ToolResult] = None
    ) -> List[Dict[str, str]]:
        """
        构建发送给 AI 的消息列表

        Args:
            session: 对话会话
            user_message: 用户消息
            rag_context: RAG上下文
            tool_intent: 工具意图
            tool_result: 工具结果

        Returns:
            List[Dict[str, str]]: 消息列表
        """
        # 获取历史消息
        history_messages = session.get_messages_for_api()  # 含本轮 user
        past_messages = history_messages[:-1] if history_messages else []  # 历史轮次（不含本轮）

        # 使用提示词引擎构建消息
        if self.prompt_engine and self._tool_enabled:
            messages = self.prompt_engine.prepare_messages_for_ai(
                user_message=user_message,
                conversation_history=past_messages,
                tool_intent=tool_intent,
                tool_result=tool_result,
                rag_context=rag_context
            )
        else:
            # 降级：使用原有逻辑
            rag_block = (
                f"\n\n参考信息：\n{rag_context}"
                if rag_context
                else "\n\n参考信息：暂无相关参考信息。"
            )
            current_user_content = f"用户问题：{user_message}{rag_block}\n\n请用中文回答："

            messages = (
                [{"role": "system", "content": SYSTEM_PROMPT}]
                + past_messages
                + [{"role": "user", "content": current_user_content}]
            )

        logger.debug(f"构建了 {len(messages)} 条 AI 消息")
        return messages

    def _build_response(
        self,
        answer: str,
        has_context: bool,
        rag_result: Optional[Dict[str, Any]],
        tool_intent: Optional[ToolIntent],
        tool_result: Optional[ToolResult],
        tool_processed: bool,
        session
    ) -> Dict[str, Any]:
        """
        构建返回响应

        Args:
            answer: AI回答
            has_context: 是否有RAG上下文
            rag_result: RAG结果
            tool_intent: 工具意图
            tool_result: 工具结果
            tool_processed: 是否处理了工具
            session: 对话会话

        Returns:
            Dict[str, Any]: 响应字典
        """
        response = {
            "success": True,
            "answer": answer,
            "has_context": has_context,
            "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
            "rag_sources": rag_result.get("sources", []) if rag_result else [],
            "rag_type": rag_result.get("type", "unknown") if rag_result else "unknown",
            "source": "deepseek_rag" if has_context else "deepseek_only",
            "turn_count": session.turn_count,
            "tool_used": tool_processed,
        }

        # 添加工具信息
        if tool_intent:
            response["tool_intent"] = {
                "tool_name": tool_intent.tool_name,
                "confidence": tool_intent.confidence,
                "parameters": tool_intent.parameters,
            }

        if tool_result:
            response["tool_result"] = {
                "success": tool_result.success,
                "tool_name": tool_result.tool_name,
                "execution_time": tool_result.execution_time,
                "error_message": tool_result.error_message,
            }

            # 根据工具结果调整source
            if tool_result.success:
                response["source"] = "deepseek_tool_rag" if has_context else "deepseek_tool"
            else:
                response["source"] = "deepseek_tool_error"

        return response

    def _build_fallback_response(self, context: str, rag_result: Optional[Dict[str, Any]]) -> str:
        """
        构建降级回复

        Args:
            context: RAG上下文
            rag_result: RAG结果

        Returns:
            str: 降级回复
        """
        if context:
            # 有RAG上下文
            return f"根据知识库信息：\n\n{context[:500]}..."
        else:
            # 无上下文
            return "AI 服务暂时不可用，请稍后再试。"

    # ── 工具相关辅助方法 ─────────────────────────────────────────────────────────

    def get_tool_status(self) -> Dict[str, Any]:
        """
        获取工具状态

        Returns:
            Dict[str, Any]: 工具状态信息
        """
        if not self._tool_enabled:
            return {
                "enabled": False,
                "reason": "工具功能已禁用",
                "use_tools": self.use_tools,
                "components_initialized": self._tool_components_initialized
            }

        status = {
            "enabled": True,
            "use_tools": self.use_tools,
            "auto_execute_tools": self.auto_execute_tools,
            "tool_confirmation_threshold": self.tool_confirmation_threshold,
            "components_initialized": self._tool_components_initialized,
        }

        # 添加组件状态
        if self.tool_registry:
            status["tool_registry"] = self.tool_registry.get_registry_status()

        if self.tool_orchestrator:
            status["tool_orchestrator"] = self.tool_orchestrator.get_orchestrator_status()

        if self.prompt_engine:
            status["prompt_engine"] = self.prompt_engine.get_engine_status()

        return status

    def list_tools(self) -> Dict[str, Any]:
        """
        列出所有可用工具

        Returns:
            Dict[str, Any]: 工具列表
        """
        if not self._tool_enabled or not self.tool_registry:
            return {"available": False, "tools": [], "reason": "工具功能未启用"}

        tools = self.tool_registry.get_all_tools()
        return {
            "available": True,
            "tool_count": len(tools),
            "tools": {name: meta.to_dict() for name, meta in tools.items()}
        }

    def test_tool_connection(self) -> Dict[str, Any]:
        """
        测试工具连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        if not self._tool_enabled:
            return {
                "success": False,
                "message": "工具功能未启用",
                "use_tools": self.use_tools
            }

        try:
            # 测试 MCP 连接
            from mcp_client import get_mcp_client
            client = get_mcp_client()
            client_status = client.get_status()

            # 测试工具发现
            tools = self.tool_registry.discover_tools(force_refresh=True)

            return {
                "success": True,
                "message": "工具连接测试成功",
                "mcp_client": client_status,
                "tools_discovered": len(tools),
                "tool_names": list(tools.keys())[:10]  # 只显示前10个
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"工具连接测试失败: {str(e)}",
                "error": str(e)
            }


# 全局工具感知 Agent 实例
_tool_aware_agent_instance: Optional[ToolAwareFeishuAgent] = None

def get_tool_aware_agent() -> ToolAwareFeishuAgent:
    """
    获取全局工具感知 Agent 实例（单例模式）

    Returns:
        ToolAwareFeishuAgent: 工具感知 Agent 实例
    """
    global _tool_aware_agent_instance

    if _tool_aware_agent_instance is None:
        _tool_aware_agent_instance = ToolAwareFeishuAgent()

    return _tool_aware_agent_instance