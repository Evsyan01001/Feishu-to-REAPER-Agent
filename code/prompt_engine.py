"""
提示词引擎：处理工具相关的提示词工程

由于 DeepSeek API 不支持 function calling，
需要通过提示词工程将工具上下文和结果整合到对话中。

主要功能：
1. 工具上下文注入
2. 工具结果整合
3. 系统提示词增强
4. 工具调用指导
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

from tool_registry import ToolRegistry, get_tool_registry
from tool_orchestrator import ToolIntent, ToolResult, get_tool_orchestrator

logger = logging.getLogger(__name__)


class PromptEngine:
    """
    提示词引擎

    负责处理工具相关的提示词工程，包括：
    - 将可用工具信息注入系统提示词
    - 将工具调用结果整合到用户消息
    - 生成工具调用指导
    - 处理工具调用失败场景

    配置通过环境变量：
    - TOOL_PROMPT_ENHANCEMENT: 是否启用提示词增强（默认true）
    - MAX_TOOLS_IN_PROMPT: 提示词中最多包含的工具数（默认5）
    - TOOL_RESULT_FORMAT: 工具结果格式（默认"detailed"）
    """

    def __init__(self):
        self.tool_registry = get_tool_registry()
        self.tool_orchestrator = get_tool_orchestrator()

        # 配置参数
        self.enhance_prompt = os.getenv("TOOL_PROMPT_ENHANCEMENT", "true").lower() == "true"
        self.max_tools_in_prompt = int(os.getenv("MAX_TOOLS_IN_PROMPT", "5"))
        self.tool_result_format = os.getenv("TOOL_RESULT_FORMAT", "detailed")

        # 基础系统提示词模板
        self.base_system_prompt = """你是游戏音频设计师，仅基于提供的参考资料回答问题。
            如果参考资料足够，提取关键信息直接回答，不要添加"根据参考资料"等废话。
            如果资料不足，明确说"参考资料中未找到相关信息，建议查阅[具体手册]"。
            回答格式：1-2句核心答案 + 可选的关键参数/设置建议。保持简洁专业。
            你能记住本次对话中用户之前问过的问题，可以自然地引用上下文。"""

        # 工具增强系统提示词模板
        self.tool_enhanced_system_prompt = """你是游戏音频设计师，也是一个智能助手，可以调用各种工具来帮助你完成任务。

        # 核心能力
        1. **专业知识**：基于提供的参考资料回答游戏音频设计问题
        2. **工具调用**：你可以调用以下工具来获取信息、执行操作或完成任务
        3. **问题解决**：结合专业知识和工具能力，提供全面准确的解决方案

        # 可用工具
        {tools_context}

        # 工具使用指南
        1. **工具选择**：当用户的问题需要特定工具时，我会自动调用合适的工具
        2. **结果整合**：工具调用结果会自动提供给你，你需要理解和解释这些结果
        3. **专业结合**：将工具结果与你的专业知识结合，提供完整回答
        4. **错误处理**：如果工具调用失败，我会明确告知，你可以基于现有知识回答或建议替代方案

        # 回答要求
        1. **简洁专业**：1-2句核心答案 + 关键参数/设置建议
        2. **工具透明**：如果使用了工具，可以简要提及（如："根据XX工具的分析结果..."）
        3. **参考资料优先**：优先使用提供的参考资料，工具结果作为补充
        4. **上下文连贯**：自然地引用对话历史

        现在，请基于以上指导原则回答用户问题。"""

        logger.info(f"提示词引擎初始化: enhance_prompt={self.enhance_prompt}, "
                   f"max_tools_in_prompt={self.max_tools_in_prompt}")

    def get_system_prompt(self) -> str:
        """
        获取系统提示词

        Returns:
            str: 系统提示词
        """
        if not self.enhance_prompt:
            return self.base_system_prompt

        # 检查是否启用了工具功能
        use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
        if not use_tools:
            return self.base_system_prompt

        # 获取工具上下文
        tools_context = self._get_tools_context()
        if not tools_context:
            return self.base_system_prompt

        # 生成增强版系统提示词
        enhanced_prompt = self.tool_enhanced_system_prompt.format(
            tools_context=tools_context
        )

        return enhanced_prompt

    def _get_tools_context(self) -> str:
        """
        获取工具上下文

        Returns:
            str: 工具上下文字符串
        """
        try:
            # 获取可用工具
            tools = self.tool_registry.get_all_tools()
            if not tools:
                return "当前没有可用的工具。"

            # 限制工具数量
            tool_items = list(tools.items())[:self.max_tools_in_prompt]

            # 格式化工具信息
            tool_descriptions = []
            for tool_name, tool_meta in tool_items:
                desc = f"- **{tool_name}**: {tool_meta.description or '无描述'}"
                if tool_meta.parameters:
                    # 简要显示参数
                    param_summary = []
                    for param_name, param_info in tool_meta.parameters.items():
                        if isinstance(param_info, dict):
                            param_type = param_info.get("type", "string")
                            param_summary.append(f"{param_name}({param_type})")
                        else:
                            param_summary.append(param_name)
                    if param_summary:
                        desc += f"\n  参数: {', '.join(param_summary)}"
                tool_descriptions.append(desc)

            # 如果有更多工具，添加备注
            if len(tools) > self.max_tools_in_prompt:
                remaining = len(tools) - self.max_tools_in_prompt
                tool_descriptions.append(f"\n...还有 {remaining} 个其他工具可用")

            return "\n".join(tool_descriptions)

        except Exception as e:
            logger.error(f"获取工具上下文失败: {e}")
            return "工具上下文获取失败。"

    def enhance_user_message(
        self,
        user_message: str,
        tool_intent: Optional[ToolIntent] = None,
        tool_result: Optional[ToolResult] = None,
        rag_context: Optional[str] = None
    ) -> str:
        """
        增强用户消息，整合工具相关信息

        Args:
            user_message: 原始用户消息
            tool_intent: 工具调用意图（可选）
            tool_result: 工具调用结果（可选）
            rag_context: RAG检索上下文（可选）

        Returns:
            str: 增强后的用户消息
        """
        enhanced_parts = []

        # 1. 原始用户问题
        enhanced_parts.append(f"用户问题：{user_message}")

        # 2. RAG上下文（如果有）
        if rag_context:
            enhanced_parts.append(f"\n知识库参考信息：\n{rag_context}")
        else:
            enhanced_parts.append("\n知识库参考信息：暂无相关参考信息。")

        # 3. 工具调用信息（如果有）
        if tool_intent and tool_result:
            tool_info = self._format_tool_execution_info(tool_intent, tool_result)
            enhanced_parts.append(f"\n工具调用信息：\n{tool_info}")
        elif tool_intent and not tool_result:
            # 只有意图，没有结果（可能是检测到意图但未执行）
            tool_info = self._format_tool_intent_info(tool_intent)
            enhanced_parts.append(f"\n检测到工具意图：\n{tool_info}")
        elif self.enhance_prompt:
            # 没有工具调用，但提示词已增强
            enhanced_parts.append("\n工具状态：未检测到需要工具调用的需求。")

        # 4. 回答要求
        enhanced_parts.append("\n请用中文回答，结合以上所有信息提供专业、准确的回答。")

        return "\n".join(enhanced_parts)

    def _format_tool_execution_info(self, intent: ToolIntent, result: ToolResult) -> str:
        """
        格式化工具执行信息

        Args:
            intent: 工具调用意图
            result: 工具调用结果

        Returns:
            str: 格式化的工具执行信息
        """
        lines = []

        # 工具基本信息
        lines.append(f"工具名称：{intent.tool_name}")
        lines.append(f"调用置信度：{intent.confidence:.2f}")

        # 参数信息
        if intent.parameters:
            lines.append(f"调用参数：{json.dumps(intent.parameters, ensure_ascii=False)}")

        # 执行结果
        lines.append(f"执行状态：{'成功' if result.success else '失败'}")

        if result.execution_time:
            lines.append(f"执行时间：{result.execution_time:.2f}秒")

        # 输出结果
        if result.success:
            output_str = self._format_tool_output(result.output)
            lines.append(f"工具输出：\n{output_str}")
        else:
            lines.append(f"错误信息：{result.error_message or '未知错误'}")

        return "\n".join(lines)

    def _format_tool_intent_info(self, intent: ToolIntent) -> str:
        """
        格式化工具意图信息

        Args:
            intent: 工具调用意图

        Returns:
            str: 格式化的工具意图信息
        """
        lines = []

        lines.append(f"检测到可能需要的工具：{intent.tool_name}")
        lines.append(f"匹配置信度：{intent.confidence:.2f}")

        if intent.match_info and intent.match_info.matched_keywords:
            keywords = ", ".join(intent.match_info.matched_keywords)
            lines.append(f"匹配关键词：{keywords}")

        if intent.parameters:
            lines.append(f"建议参数：{json.dumps(intent.parameters, ensure_ascii=False)}")

        lines.append("注意：此工具尚未执行，如有需要请明确指示。")

        return "\n".join(lines)

    def _format_tool_output(self, output: Any) -> str:
        """
        格式化工具输出

        Args:
            output: 工具输出

        Returns:
            str: 格式化的工具输出
        """
        if output is None:
            return "（无输出）"

        # 如果是字符串，尝试美化
        if isinstance(output, str):
            output_str = output.strip()

            # 尝试解析JSON
            if output_str.startswith(('{', '[')):
                try:
                    parsed = json.loads(output_str)
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    pass

            return output_str

        # 如果是字典或列表，转换为JSON字符串
        elif isinstance(output, (dict, list)):
            try:
                return json.dumps(output, ensure_ascii=False, indent=2)
            except:
                return str(output)

        # 其他类型直接转换为字符串
        else:
            return str(output)

    def create_tool_guidance_prompt(self, user_query: str) -> Tuple[str, Optional[ToolIntent]]:
        """
        创建工具调用指导提示词

        当检测到工具调用意图但需要用户确认时使用

        Args:
            user_query: 用户查询

        Returns:
            Tuple[str, Optional[ToolIntent]]: (指导提示词, 检测到的意图)
        """
        # 检测工具意图
        intent = self.tool_orchestrator.detect_intent(user_query)
        if not intent:
            return "未检测到需要工具调用的需求。", None

        # 构建指导提示词
        tool_meta = self.tool_registry.get_tool_metadata(intent.tool_name)

        guidance_lines = [
            f"我检测到您的问题可能需要使用 **{intent.tool_name}** 工具。",
            f"",
            f"**工具描述**: {tool_meta.description if tool_meta else '无描述'}",
            f"**匹配置信度**: {intent.confidence:.2f}",
        ]

        if intent.parameters:
            guidance_lines.append(f"**检测到的参数**: {json.dumps(intent.parameters, ensure_ascii=False)}")

        guidance_lines.extend([
            f"",
            f"**请确认**:",
            f"1. 您是否需要我执行这个工具？",
            f"2. 参数是否正确？是否需要调整？",
            f"",
            f"回复格式示例：",
            f"- \"执行工具，参数不变\"",
            f"- \"执行工具，将参数X改为Y\"",
            f"- \"不需要工具，直接回答\"",
        ])

        return "\n".join(guidance_lines), intent

    def handle_tool_error(self, error_message: str, user_query: str) -> str:
        """
        处理工具错误，生成用户友好的错误消息

        Args:
            error_message: 错误消息
            user_query: 用户查询

        Returns:
            str: 用户友好的错误消息
        """
        # 分析错误类型
        error_lower = error_message.lower()

        if "timeout" in error_lower or "超时" in error_lower:
            return f"工具调用超时。请稍后重试，或简化您的请求。\n原始错误: {error_message}"

        elif "connection" in error_lower or "连接" in error_lower:
            return f"无法连接到工具服务。请检查网络连接或稍后重试。\n原始错误: {error_message}"

        elif "not found" in error_lower or "不存在" in error_lower:
            return f"请求的工具不存在或不可用。\n原始错误: {error_message}"

        elif "permission" in error_lower or "权限" in error_lower:
            return f"没有执行此工具的权限。\n原始错误: {error_message}"

        elif "parameter" in error_lower or "参数" in error_lower:
            return f"工具参数错误。请检查参数格式或提供必要参数。\n原始错误: {error_message}"

        else:
            return f"工具调用失败: {error_message}\n我将尝试基于现有知识回答您的问题。"

    def prepare_messages_for_ai(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        tool_intent: Optional[ToolIntent] = None,
        tool_result: Optional[ToolResult] = None,
        rag_context: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        准备发送给 AI 的消息列表

        Args:
            user_message: 用户消息
            conversation_history: 对话历史
            tool_intent: 工具调用意图
            tool_result: 工具调用结果
            rag_context: RAG 上下文

        Returns:
            List[Dict[str, str]]: 消息列表
        """
        messages = []

        # 1. 系统提示词
        system_prompt = self.get_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        # 2. 对话历史（不含当前轮次）
        # 注意：当前轮次的用户消息将通过增强消息添加
        if conversation_history:
            # 过滤掉当前的用户消息（如果有）
            history_for_api = conversation_history.copy()
            messages.extend(history_for_api)

        # 3. 当前轮次的增强用户消息
        enhanced_message = self.enhance_user_message(
            user_message=user_message,
            tool_intent=tool_intent,
            tool_result=tool_result,
            rag_context=rag_context
        )
        messages.append({"role": "user", "content": enhanced_message})

        logger.debug(f"准备 AI 消息完成，共 {len(messages)} 条消息")

        return messages

    def get_engine_status(self) -> Dict[str, Any]:
        """
        获取引擎状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "enhance_prompt": self.enhance_prompt,
            "max_tools_in_prompt": self.max_tools_in_prompt,
            "tool_result_format": self.tool_result_format,
            "base_prompt_length": len(self.base_system_prompt),
            "tool_registry_available": bool(self.tool_registry.get_all_tools())
        }


# 全局提示词引擎实例
_prompt_engine_instance: Optional[PromptEngine] = None

def get_prompt_engine() -> PromptEngine:
    """
    获取全局提示词引擎实例（单例模式）

    Returns:
        PromptEngine: 提示词引擎实例
    """
    global _prompt_engine_instance

    if _prompt_engine_instance is None:
        _prompt_engine_instance = PromptEngine()

    return _prompt_engine_instance

def init_prompt_engine() -> bool:
    """
    初始化提示词引擎

    Returns:
        bool: 初始化是否成功
    """
    engine = get_prompt_engine()

    # 检查是否启用了工具功能
    use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
    if not use_tools:
        logger.info("工具功能已禁用，使用基础提示词引擎")
        return True  # 基础提示词引擎总是可用的

    logger.info("提示词引擎初始化成功")
    return True