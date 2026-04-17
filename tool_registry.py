"""
工具注册表：管理和协调 MCP 工具

提供工具匹配、选择、缓存和监控功能
与 MCPClient 协同工作，提供更高级的工具管理
"""

import os
import json
import logging
import time
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum

from mcp_client import ToolMetadata, ToolResult, get_mcp_client

logger = logging.getLogger(__name__)


# 工具匹配结果数据类
@dataclass
class ToolMatch:
    """工具匹配结果"""
    tool_name: str
    confidence: float  # 0.0 到 1.0
    matched_keywords: List[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 工具调用统计数据类
@dataclass
class ToolStats:
    """工具调用统计"""
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0.0
    last_called_at: Optional[float] = None

    def record_call(self, success: bool, execution_time: float = 0.0):
        """记录工具调用"""
        self.call_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        self.total_execution_time += execution_time
        self.last_called_at = time.time()

    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.call_count == 0:
            return 0.0
        return self.success_count / self.call_count

    def get_avg_execution_time(self) -> float:
        """获取平均执行时间"""
        if self.call_count == 0:
            return 0.0
        return self.total_execution_time / self.call_count

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolRegistry:
    """
    工具注册表

    主要功能：
    1. 工具发现和缓存
    2. 工具匹配和选择
    3. 工具调用统计
    4. 工具元数据管理
    5. 工具健康检查

    配置通过环境变量：
    - TOOL_MATCH_THRESHOLD: 工具匹配置信度阈值（默认0.3）
    - TOOL_CACHE_TTL: 工具缓存TTL（秒，默认300）
    - ENABLE_TOOL_STATS: 是否启用工具统计（默认true）
    """

    def __init__(self):
        self.mcp_client = get_mcp_client()
        self._tools: Dict[str, ToolMetadata] = {}
        self._tool_stats: Dict[str, ToolStats] = {}
        self._tool_keywords: Dict[str, Set[str]] = {}
        self._last_discovery_time = 0

        # 配置参数
        self.match_threshold = float(os.getenv("TOOL_MATCH_THRESHOLD", "0.3"))
        self.cache_ttl = int(os.getenv("TOOL_CACHE_TTL", "300"))
        self.enable_stats = os.getenv("ENABLE_TOOL_STATS", "true").lower() == "true"

        # 初始化关键词提取器
        self._init_keyword_extractor()

        logger.info(f"工具注册表初始化: match_threshold={self.match_threshold}, cache_ttl={self.cache_ttl}")

    def _init_keyword_extractor(self):
        """初始化关键词提取器"""
        # 常见工具相关关键词
        self._common_tool_keywords = {
            # 文件操作
            "文件", "打开", "保存", "读取", "写入", "删除", "重命名", "复制", "移动",
            # 网络操作
            "下载", "上传", "请求", "获取", "发送", "接收", "连接",
            # 系统操作
            "运行", "执行", "启动", "停止", "重启", "安装", "卸载", "更新",
            # 数据处理
            "查询", "搜索", "过滤", "排序", "转换", "计算", "分析", "统计",
            # 其他
            "创建", "修改", "设置", "配置", "检查", "验证", "测试", "监控"
        }

    def discover_tools(self, force_refresh: bool = False) -> Dict[str, ToolMetadata]:
        """
        发现可用工具

        Args:
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            Dict[str, ToolMetadata]: 工具名称到元数据的映射
        """
        current_time = time.time()

        # 检查缓存是否过期
        cache_expired = (current_time - self._last_discovery_time) > self.cache_ttl

        if force_refresh or not self._tools or cache_expired:
            try:
                # 确保 MCP 客户端已连接
                if not self.mcp_client.is_connected():
                    logger.warning("MCP 客户端未连接，尝试重新连接")
                    if not self.mcp_client.connect():
                        logger.error("MCP 客户端连接失败")
                        return self._tools

                # 发现工具
                tools = self.mcp_client.discover_tools()
                self._tools = tools
                self._last_discovery_time = current_time

                # 为每个工具提取关键词
                self._update_tool_keywords()

                # 初始化统计信息
                self._init_tool_stats()

                logger.info(f"发现 {len(self._tools)} 个工具")
                return tools

            except Exception as e:
                logger.error(f"工具发现失败: {e}")
                # 返回缓存的工具（如果有）
                return self._tools

        else:
            logger.debug(f"使用缓存的工具列表 ({len(self._tools)} 个工具)")
            return self._tools

    def _update_tool_keywords(self):
        """更新工具关键词"""
        self._tool_keywords.clear()

        for tool_name, tool_meta in self._tools.items():
            keywords = set()

            # 从工具名称提取关键词
            name_keywords = self._extract_keywords(tool_name)
            keywords.update(name_keywords)

            # 从工具描述提取关键词
            if tool_meta.description:
                desc_keywords = self._extract_keywords(tool_meta.description)
                keywords.update(desc_keywords)

            # 添加常见工具关键词
            for common_keyword in self._common_tool_keywords:
                if common_keyword in tool_name.lower() or (
                    tool_meta.description and common_keyword in tool_meta.description.lower()
                ):
                    keywords.add(common_keyword)

            self._tool_keywords[tool_name] = keywords

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        if not text:
            return []

        # 转换为小写
        text_lower = text.lower()

        # 提取单词（中英文混合）
        # 中文：匹配中文字符
        # 英文：匹配单词字符
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', text_lower)
        english_words = re.findall(r'\b[a-z]+\b', text_lower)

        # 组合并去重
        all_words = chinese_words + english_words

        # 过滤停用词和短词
        stop_words = {"的", "了", "在", "是", "和", "与", "或", "为", "对", "这", "那", "有", "就", "也", "都"}
        filtered_words = [
            word for word in all_words
            if word not in stop_words and len(word) > 1
        ]

        return filtered_words

    def _init_tool_stats(self):
        """初始化工具统计信息"""
        for tool_name in self._tools:
            if tool_name not in self._tool_stats:
                self._tool_stats[tool_name] = ToolStats(tool_name)

    def match_tools(self, user_query: str, top_k: int = 3) -> List[ToolMatch]:
        """
        匹配用户查询到相关工具

        Args:
            user_query: 用户查询
            top_k: 返回最多匹配结果数量

        Returns:
            List[ToolMatch]: 匹配结果列表，按置信度降序排序
        """
        # 确保有最新的工具列表
        self.discover_tools()

        if not self._tools:
            logger.warning("没有可用工具进行匹配")
            return []

        # 提取查询关键词
        query_keywords = set(self._extract_keywords(user_query))
        if not query_keywords:
            logger.debug("无法从查询中提取关键词")
            return []

        matches = []

        for tool_name, tool_keywords in self._tool_keywords.items():
            # 计算关键词匹配度
            if not tool_keywords:
                continue

            # 计算交集
            intersection = query_keywords.intersection(tool_keywords)
            if not intersection:
                continue

            # 计算置信度（交集大小 / 查询关键词总数）
            confidence = len(intersection) / len(query_keywords)

            # 考虑工具描述的完整性
            tool_meta = self._tools.get(tool_name)
            if tool_meta and tool_meta.description:
                # 描述越详细，可能越相关
                desc_length_factor = min(len(tool_meta.description) / 100, 1.0)
                confidence = confidence * 0.7 + desc_length_factor * 0.3

            # 考虑工具使用频率（如果启用统计）
            if self.enable_stats and tool_name in self._tool_stats:
                stats = self._tool_stats[tool_name]
                if stats.call_count > 0:
                    # 成功率高的工具获得小幅加成
                    success_rate = stats.get_success_rate()
                    confidence = confidence * 0.9 + success_rate * 0.1

            if confidence >= self.match_threshold:
                match = ToolMatch(
                    tool_name=tool_name,
                    confidence=confidence,
                    matched_keywords=list(intersection),
                    reason=f"匹配到关键词: {', '.join(intersection)}"
                )
                matches.append(match)

        # 按置信度降序排序
        matches.sort(key=lambda x: x.confidence, reverse=True)

        # 限制返回数量
        result = matches[:top_k]

        if result:
            logger.info(f"工具匹配结果: {[f'{m.tool_name}({m.confidence:.2f})' for m in result]}")
        else:
            logger.debug(f"没有匹配的工具 (阈值: {self.match_threshold})")

        return result

    def get_best_tool_match(self, user_query: str) -> Optional[ToolMatch]:
        """
        获取最佳工具匹配

        Args:
            user_query: 用户查询

        Returns:
            Optional[ToolMatch]: 最佳匹配结果，如果没有则返回 None
        """
        matches = self.match_tools(user_query, top_k=1)
        return matches[0] if matches else None

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        调用工具并记录统计信息

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult: 工具调用结果
        """
        start_time = time.time()

        # 执行工具调用
        result = self.mcp_client.call_tool(tool_name, arguments)

        execution_time = time.time() - start_time

        # 记录统计信息
        if self.enable_stats:
            if tool_name not in self._tool_stats:
                self._tool_stats[tool_name] = ToolStats(tool_name)

            self._tool_stats[tool_name].record_call(
                success=result.success,
                execution_time=execution_time
            )

            logger.info(f"工具调用统计更新: {tool_name}, 成功率: "
                       f"{self._tool_stats[tool_name].get_success_rate():.2f}")

        return result

    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """
        获取工具元数据

        Args:
            tool_name: 工具名称

        Returns:
            Optional[ToolMetadata]: 工具元数据
        """
        return self._tools.get(tool_name)

    def get_all_tools(self) -> Dict[str, ToolMetadata]:
        """
        获取所有工具

        Returns:
            Dict[str, ToolMetadata]: 所有工具元数据
        """
        self.discover_tools()  # 确保有最新数据
        return self._tools.copy()

    def get_tool_names(self) -> List[str]:
        """
        获取所有工具名称

        Returns:
            List[str]: 工具名称列表
        """
        self.discover_tools()
        return list(self._tools.keys())

    def get_tool_stats(self, tool_name: str) -> Optional[ToolStats]:
        """
        获取工具统计信息

        Args:
            tool_name: 工具名称

        Returns:
            Optional[ToolStats]: 工具统计信息
        """
        return self._tool_stats.get(tool_name)

    def get_all_stats(self) -> Dict[str, ToolStats]:
        """
        获取所有工具统计信息

        Returns:
            Dict[str, ToolStats]: 所有工具统计信息
        """
        return self._tool_stats.copy()

    def get_registry_status(self) -> Dict[str, Any]:
        """
        获取注册表状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        self.discover_tools()

        total_calls = 0
        total_success = 0
        total_errors = 0

        for stats in self._tool_stats.values():
            total_calls += stats.call_count
            total_success += stats.success_count
            total_errors += stats.error_count

        return {
            "tool_count": len(self._tools),
            "connected": self.mcp_client.is_connected(),
            "last_discovery": self._last_discovery_time,
            "match_threshold": self.match_threshold,
            "total_calls": total_calls,
            "total_success": total_success,
            "total_errors": total_errors,
            "tool_names": self.get_tool_names()
        }

    def format_tool_info_for_prompt(self, tool_name: str) -> str:
        """
        格式化工具信息用于提示词

        Args:
            tool_name: 工具名称

        Returns:
            str: 格式化的工具信息
        """
        tool_meta = self.get_tool_metadata(tool_name)
        if not tool_meta:
            return f"工具 '{tool_name}' 不存在"

        info_lines = [
            f"工具名称: {tool_meta.name}",
            f"描述: {tool_meta.description or '无描述'}",
        ]

        if tool_meta.parameters:
            info_lines.append("参数:")
            for param_name, param_info in tool_meta.parameters.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get("type", "未知")
                    param_desc = param_info.get("description", "")
                    info_lines.append(f"  - {param_name} ({param_type}): {param_desc}")
                else:
                    info_lines.append(f"  - {param_name}: {param_info}")

        return "\n".join(info_lines)

    def format_all_tools_for_prompt(self) -> str:
        """
        格式化所有工具信息用于提示词

        Returns:
            str: 格式化的所有工具信息
        """
        tools = self.get_all_tools()
        if not tools:
            return "当前没有可用的工具。"

        formatted_tools = []
        for tool_name, tool_meta in tools.items():
            formatted = self.format_tool_info_for_prompt(tool_name)
            formatted_tools.append(formatted)

        return "\n\n".join(formatted_tools)


# 全局工具注册表实例
_tool_registry_instance: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """
    获取全局工具注册表实例（单例模式）

    Returns:
        ToolRegistry: 工具注册表实例
    """
    global _tool_registry_instance

    if _tool_registry_instance is None:
        _tool_registry_instance = ToolRegistry()

    return _tool_registry_instance

def init_tool_registry() -> bool:
    """
    初始化工具注册表

    Returns:
        bool: 初始化是否成功
    """
    registry = get_tool_registry()

    # 检查是否启用了工具功能
    use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
    if not use_tools:
        logger.info("工具功能已禁用，跳过工具注册表初始化")
        return False

    # 发现工具
    tools = registry.discover_tools()
    if tools:
        logger.info(f"工具注册表初始化成功，发现 {len(tools)} 个工具")
        return True
    else:
        logger.warning("工具注册表初始化失败，未发现工具")
        return False