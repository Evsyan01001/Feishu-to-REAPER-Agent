"""
工具协调器：协调工具调用流程

负责：
1. 工具意图检测
2. 工具参数提取
3. 工具调用执行
4. 工具结果处理
5. 错误处理和降级
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict

from mcp_client import ToolResult
from tool_registry import ToolRegistry, ToolMatch, get_tool_registry

logger = logging.getLogger(__name__)


# 工具调用意图数据类
@dataclass
class ToolIntent:
    """工具调用意图"""
    tool_name: str
    confidence: float
    parameters: Dict[str, Any]
    raw_query: str
    match_info: Optional[ToolMatch] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 工具调用上下文数据类
@dataclass
class ToolContext:
    """工具调用上下文"""
    intent: ToolIntent
    registry: ToolRegistry
    user_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolOrchestrator:
    """
    工具协调器

    协调工具调用的完整流程：
    1. 检测用户查询中的工具调用意图
    2. 提取工具调用参数
    3. 执行工具调用
    4. 处理工具调用结果
    5. 提供错误处理和降级策略

    配置通过环境变量：
    - TOOL_INTENT_THRESHOLD: 意图检测阈值（默认0.4）
    - MAX_TOOL_CALLS_PER_QUERY: 每个查询最大工具调用数（默认2）
    - ENABLE_PARAM_EXTRACTION: 是否启用参数提取（默认true）
    """

    def __init__(self):
        self.tool_registry = get_tool_registry()

        # 配置参数
        self.intent_threshold = float(os.getenv("TOOL_INTENT_THRESHOLD", "0.4"))
        self.max_tool_calls = int(os.getenv("MAX_TOOL_CALLS_PER_QUERY", "2"))
        self.enable_param_extraction = os.getenv("ENABLE_PARAM_EXTRACTION", "true").lower() == "true"

        # 参数提取模式
        self._param_patterns = self._init_param_patterns()

        logger.info(f"工具协调器初始化: intent_threshold={self.intent_threshold}, "
                   f"max_tool_calls={self.max_tool_calls}")

    def _init_param_patterns(self) -> Dict[str, re.Pattern]:
        """初始化参数提取正则表达式模式"""
        patterns = {
            # 键值对参数：参数名=参数值
            "key_value": re.compile(r'(\w+)=([^,\s]+)'),

            # 引号参数：参数名="参数值"
            "quoted_key_value": re.compile(r'(\w+)="([^"]*)"'),

            # 单引号参数：参数名='参数值'
            "single_quoted_key_value": re.compile(r"(\w+)='([^']*)'"),

            # 简单值参数：直接值（无参数名）
            "simple_value": re.compile(r'\b([a-zA-Z0-9_\-\.]+)\b'),

            # 数字参数
            "number": re.compile(r'\b(\d+)\b'),

            # 文件路径参数
            "file_path": re.compile(r'\b([a-zA-Z0-9_\-\./\\]+\.(txt|json|yaml|yml|md|csv))\b'),

            # URL参数
            "url": re.compile(r'(https?://[^\s]+)'),
        }
        return patterns

    def detect_intent(self, user_query: str, user_id: Optional[str] = None) -> Optional[ToolIntent]:
        """
        检测工具调用意图

        Args:
            user_query: 用户查询
            user_id: 用户ID（用于上下文）

        Returns:
            Optional[ToolIntent]: 工具调用意图，如果没有检测到则返回 None
        """
        if not user_query or not user_query.strip():
            logger.debug("用户查询为空，跳过意图检测")
            return None

        # 获取工具匹配
        tool_match = self.tool_registry.get_best_tool_match(user_query)
        if not tool_match:
            logger.debug(f"未找到匹配的工具: {user_query[:50]}...")
            return None

        # 检查置信度阈值
        if tool_match.confidence < self.intent_threshold:
            logger.debug(f"工具匹配置信度过低: {tool_match.tool_name} ({tool_match.confidence:.2f} < {self.intent_threshold})")
            return None

        # 提取参数
        parameters = {}
        if self.enable_param_extraction:
            parameters = self.extract_parameters(user_query, tool_match.tool_name)

        # 创建意图对象
        intent = ToolIntent(
            tool_name=tool_match.tool_name,
            confidence=tool_match.confidence,
            parameters=parameters,
            raw_query=user_query,
            match_info=tool_match
        )

        logger.info(f"检测到工具意图: {intent.tool_name} (置信度: {intent.confidence:.2f}), "
                   f"参数: {parameters}")
        return intent

    def extract_parameters(self, user_query: str, tool_name: str) -> Dict[str, Any]:
        """
        从用户查询中提取工具参数

        Args:
            user_query: 用户查询
            tool_name: 工具名称

        Returns:
            Dict[str, Any]: 提取的参数
        """
        # 获取工具元数据
        tool_meta = self.tool_registry.get_tool_metadata(tool_name)
        if not tool_meta:
            logger.warning(f"无法获取工具元数据: {tool_name}")
            return {}

        # 初始化参数字典
        parameters = {}

        # 如果工具有预定义的参数模式，尝试提取
        if tool_meta.parameters:
            for param_name, param_info in tool_meta.parameters.items():
                # 尝试提取参数值
                param_value = self._extract_param_by_name(user_query, param_name, param_info)
                if param_value is not None:
                    parameters[param_name] = param_value

        # 如果未提取到参数，尝试通用参数提取
        if not parameters:
            parameters = self._extract_generic_parameters(user_query)

        return parameters

    def _extract_param_by_name(self, query: str, param_name: str, param_info: Dict[str, Any]) -> Any:
        """
        按参数名称提取参数值

        Args:
            query: 用户查询
            param_name: 参数名称
            param_info: 参数信息

        Returns:
            Any: 参数值，如果未找到则返回 None
        """
        param_name_lower = param_name.lower()
        query_lower = query.lower()

        # 检查查询中是否包含参数名
        if param_name_lower not in query_lower:
            return None

        # 获取参数类型
        param_type = param_info.get("type", "string")

        # 基于参数类型提取值
        if param_type == "string":
            return self._extract_string_param(query, param_name)
        elif param_type in ["integer", "number"]:
            return self._extract_number_param(query, param_name)
        elif param_type == "boolean":
            return self._extract_boolean_param(query, param_name)
        elif param_type == "array":
            return self._extract_array_param(query, param_name)
        else:
            # 默认提取字符串
            return self._extract_string_param(query, param_name)

    def _extract_string_param(self, query: str, param_name: str) -> Optional[str]:
        """提取字符串参数"""
        # 查找参数名后面的内容
        pattern = re.compile(rf'{re.escape(param_name)}\s*[:=]\s*["\']?([^"\'\s,]+)["\']?', re.IGNORECASE)
        match = pattern.search(query)
        if match:
            return match.group(1)
        return None

    def _extract_number_param(self, query: str, param_name: str) -> Optional[Union[int, float]]:
        """提取数字参数"""
        # 查找参数名后面的数字
        pattern = re.compile(rf'{re.escape(param_name)}\s*[:=]\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
        match = pattern.search(query)
        if match:
            value = match.group(1)
            if '.' in value:
                return float(value)
            else:
                return int(value)
        return None

    def _extract_boolean_param(self, query: str, param_name: str) -> Optional[bool]:
        """提取布尔参数"""
        # 查找参数名后面的布尔值
        pattern = re.compile(rf'{re.escape(param_name)}\s*[:=]\s*(true|false|yes|no|1|0)', re.IGNORECASE)
        match = pattern.search(query)
        if match:
            value = match.group(1).lower()
            if value in ['true', 'yes', '1']:
                return True
            elif value in ['false', 'no', '0']:
                return False
        return None

    def _extract_array_param(self, query: str, param_name: str) -> Optional[List]:
        """提取数组参数"""
        # 查找参数名后面的数组（逗号分隔）
        pattern = re.compile(rf'{re.escape(param_name)}\s*[:=]\s*\[([^\]]+)\]', re.IGNORECASE)
        match = pattern.search(query)
        if match:
            array_str = match.group(1)
            # 分割逗号分隔的值
            items = [item.strip().strip('"\'').strip("'") for item in array_str.split(',')]
            return items
        return None

    def _extract_generic_parameters(self, query: str) -> Dict[str, Any]:
        """通用参数提取"""
        parameters = {}

        # 尝试提取键值对参数
        for pattern_name, pattern in self._param_patterns.items():
            matches = pattern.findall(query)
            if matches:
                for match in matches:
                    if isinstance(match, tuple) and len(match) == 2:
                        # 键值对
                        key, value = match
                        parameters[key] = value
                    elif isinstance(match, str):
                        # 简单值
                        # 为简单值生成通用键名
                        key = f"arg{len(parameters) + 1}"
                        parameters[key] = match

        return parameters

    def execute_tool(self, intent: ToolIntent, context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """
        执行工具调用

        Args:
            intent: 工具调用意图
            context: 额外上下文信息

        Returns:
            ToolResult: 工具调用结果
        """
        if not intent or not intent.tool_name:
            logger.error("无效的工具意图")
            return ToolResult(
                success=False,
                output=None,
                tool_name="unknown",
                error_message="无效的工具意图"
            )

        # 合并参数：意图参数 + 上下文参数
        all_parameters = intent.parameters.copy()
        if context:
            # 从上下文中提取相关参数
            context_params = self._extract_params_from_context(context, intent.tool_name)
            all_parameters.update(context_params)

        # 执行工具调用
        logger.info(f"执行工具调用: {intent.tool_name}, 参数: {all_parameters}")
        result = self.tool_registry.call_tool(intent.tool_name, all_parameters)

        # 记录调用结果
        self._record_tool_execution(intent, result, all_parameters)

        return result

    def _extract_params_from_context(self, context: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """从上下文中提取参数"""
        params = {}

        # 从上下文中提取可能相关的信息
        # 例如：用户ID、会话历史、时间戳等
        if "user_id" in context:
            params["user_id"] = context["user_id"]

        if "timestamp" in context:
            params["timestamp"] = context["timestamp"]

        # 可以根据工具名称添加特定上下文参数
        if "file" in tool_name.lower() and "current_directory" in context:
            params["base_dir"] = context["current_directory"]

        return params

    def _record_tool_execution(self, intent: ToolIntent, result: ToolResult, parameters: Dict[str, Any]):
        """记录工具执行信息"""
        # 这里可以记录到日志、数据库或监控系统
        log_data = {
            "tool": intent.tool_name,
            "confidence": intent.confidence,
            "parameters": parameters,
            "success": result.success,
            "execution_time": result.execution_time,
            "error": result.error_message
        }

        if result.success:
            logger.info(f"工具执行成功: {json.dumps(log_data, ensure_ascii=False)}")
        else:
            logger.error(f"工具执行失败: {json.dumps(log_data, ensure_ascii=False)}")

    def format_tool_result(self, result: ToolResult, intent: Optional[ToolIntent] = None) -> str:
        """
        格式化工具调用结果

        Args:
            result: 工具调用结果
            intent: 工具调用意图（可选）

        Returns:
            str: 格式化的结果字符串
        """
        if not result.success:
            error_msg = result.error_message or "未知错误"
            return f"❌ 工具调用失败: {error_msg}"

        # 格式化成功结果
        output = result.output

        # 尝试解析JSON输出
        if isinstance(output, str) and output.strip().startswith(('{', '[')):
            try:
                parsed = json.loads(output)
                # 美化JSON输出
                output = json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass  # 保持原样

        # 构建结果消息
        lines = [f"✅ 工具调用成功: {result.tool_name}"]

        if result.execution_time:
            lines.append(f"⏱️ 执行时间: {result.execution_time:.2f}秒")

        lines.append(f"📊 输出结果:")
        lines.append("```")

        # 限制输出长度
        if isinstance(output, str) and len(output) > 1000:
            lines.append(output[:1000] + "...\n(输出已截断)")
        else:
            lines.append(str(output))

        lines.append("```")

        return "\n".join(lines)

    def process_query(
        self,
        user_query: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[ToolIntent], Optional[ToolResult], Optional[str]]:
        """
        处理用户查询，执行完整的工具调用流程

        Args:
            user_query: 用户查询
            user_id: 用户ID
            context: 额外上下文

        Returns:
            Tuple[Optional[ToolIntent], Optional[ToolResult], Optional[str]]:
            (意图, 结果, 格式化结果)
        """
        # 检测意图
        intent = self.detect_intent(user_query, user_id)
        if not intent:
            logger.debug("未检测到工具调用意图")
            return None, None, None

        # 执行工具
        result = self.execute_tool(intent, context)

        # 格式化结果
        formatted_result = self.format_tool_result(result, intent)

        return intent, result, formatted_result

    def get_orchestrator_status(self) -> Dict[str, Any]:
        """
        获取协调器状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        registry_status = self.tool_registry.get_registry_status()

        return {
            "intent_threshold": self.intent_threshold,
            "max_tool_calls": self.max_tool_calls,
            "enable_param_extraction": self.enable_param_extraction,
            "registry_status": registry_status
        }


# 全局工具协调器实例
_tool_orchestrator_instance: Optional[ToolOrchestrator] = None

def get_tool_orchestrator() -> ToolOrchestrator:
    """
    获取全局工具协调器实例（单例模式）

    Returns:
        ToolOrchestrator: 工具协调器实例
    """
    global _tool_orchestrator_instance

    if _tool_orchestrator_instance is None:
        _tool_orchestrator_instance = ToolOrchestrator()

    return _tool_orchestrator_instance

def init_tool_orchestrator() -> bool:
    """
    初始化工具协调器

    Returns:
        bool: 初始化是否成功
    """
    orchestrator = get_tool_orchestrator()

    # 检查是否启用了工具功能
    use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
    if not use_tools:
        logger.info("工具功能已禁用，跳过工具协调器初始化")
        return False

    # 检查工具注册表是否已初始化
    registry = get_tool_registry()
    if not registry.get_all_tools():
        logger.warning("工具注册表未初始化或未发现工具，工具协调器功能受限")
        return False

    logger.info("工具协调器初始化成功")
    return True