"""
MCP 客户端：实现 Model Context Protocol 客户端
连接到 MCP 服务器，发现和调用可用工具

注意：需要安装 mcp Python 库（已添加到 requirements.txt）
如果 mcp 库不可用，客户端将降级到无工具模式
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

# MCP 工具状态枚举
class ToolStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"

# 工具元数据数据类
@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    parameters: Dict[str, Any]
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# 工具调用结果数据类
@dataclass
class ToolResult:
    """工具调用结果"""
    success: bool
    output: Any
    tool_name: str
    error_message: Optional[str] = None
    execution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPClient:
    """
    MCP 协议客户端

    连接到 MCP 服务器，支持：
    - 工具发现和元数据获取
    - 工具调用执行
    - 错误处理和重试
    - 连接状态监控

    配置通过环境变量：
    - MCP_SERVER_URL: MCP 服务器地址 (stdio://path/to/server 或 http://localhost:8080)
    - TOOL_TIMEOUT: 工具调用超时时间（秒，默认30）
    - ENABLE_TOOL_CACHE: 是否启用工具缓存（默认true）
    """

    def __init__(self, server_url: Optional[str] = None):
        """
        初始化 MCP 客户端

        Args:
            server_url: MCP 服务器 URL，如果为 None 则从环境变量读取
        """
        self.server_url = server_url or os.getenv("MCP_SERVER_URL")
        self.timeout = int(os.getenv("TOOL_TIMEOUT", "30"))
        self.enable_cache = os.getenv("ENABLE_TOOL_CACHE", "true").lower() == "true"

        # 内部状态
        self._client = None
        self._tools: Dict[str, ToolMetadata] = {}
        self._connected = False
        self._last_error = None
        self._tool_cache: Dict[str, Any] = {}

        # 检查 mcp 库是否可用
        self._has_mcp = self._check_mcp_available()

        logger.info(f"MCP 客户端初始化: server_url={self.server_url}, has_mcp={self._has_mcp}")

    def _check_mcp_available(self) -> bool:
        """检查 mcp 库是否可用"""
        try:
            import mcp
            return True
        except ImportError:
            logger.warning("mcp 库未安装，工具功能将不可用。请运行: pip install mcp")
            return False

    async def connect(self) -> bool:
        """
        连接到 MCP 服务器

        Returns:
            bool: 连接是否成功
        """
        if not self._has_mcp:
            logger.error("无法连接：mcp 库未安装")
            return False

        if not self.server_url:
            logger.error("无法连接：未配置 MCP_SERVER_URL")
            return False

        try:
            import mcp

            logger.info(f"正在连接到 MCP 服务器: {self.server_url}")

            # 根据 URL 协议选择连接方式
            if self.server_url.startswith("stdio://"):
                # stdio 连接
                server_path = self.server_url[8:]  # 移除 "stdio://"
                self._client = await mcp.stdio_client(server_path)
            elif self.server_url.startswith("http://") or self.server_url.startswith("https://"):
                # HTTP 连接
                self._client = await mcp.http_client(self.server_url)
            else:
                logger.error(f"不支持的 MCP 服务器协议: {self.server_url}")
                return False

            # 初始化连接
            await self._client.initialize()

            # 发现可用工具
            await self.discover_tools()

            self._connected = True
            self._last_error = None

            logger.info(f"MCP 连接成功，发现 {len(self._tools)} 个工具")
            return True

        except Exception as e:
            self._connected = False
            self._last_error = str(e)
            logger.error(f"MCP 连接失败: {e}")
            return False

    async def discover_tools(self) -> Dict[str, ToolMetadata]:
        """
        发现 MCP 服务器提供的工具

        Returns:
            Dict[str, ToolMetadata]: 工具名称到元数据的映射
        """
        if not self._connected or not self._client:
            logger.warning("未连接到 MCP 服务器，无法发现工具")
            return {}

        try:
            import mcp

            # 获取工具列表
            tools_response = await self._client.list_tools()

            self._tools.clear()

            for tool_info in tools_response.tools:
                tool_meta = ToolMetadata(
                    name=tool_info.name,
                    description=tool_info.description or "",
                    parameters=tool_info.inputSchema or {},
                    input_schema=tool_info.inputSchema,
                    output_schema=tool_info.outputSchema,
                )
                self._tools[tool_info.name] = tool_meta

            logger.info(f"发现 {len(self._tools)} 个工具: {list(self._tools.keys())}")
            return self._tools

        except Exception as e:
            logger.error(f"工具发现失败: {e}")
            return {}

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult: 工具调用结果
        """
        if not self._connected or not self._client:
            error_msg = "未连接到 MCP 服务器"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message=error_msg
            )

        if tool_name not in self._tools:
            error_msg = f"工具不存在: {tool_name}"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message=error_msg
            )

        import time
        start_time = time.time()

        try:
            import mcp

            logger.info(f"调用工具: {tool_name}，参数: {arguments}")

            # 执行工具调用
            result = await self._client.call_tool(tool_name, arguments)

            execution_time = time.time() - start_time

            logger.info(f"工具调用成功: {tool_name}，执行时间: {execution_time:.2f}s")

            return ToolResult(
                success=True,
                output=result.content if hasattr(result, 'content') else result,
                tool_name=tool_name,
                execution_time=execution_time
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            error_msg = f"工具调用超时: {tool_name} (>{self.timeout}s)"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message=error_msg,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"工具调用失败: {tool_name} - {e}"
            logger.error(error_msg)
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message=error_msg,
                execution_time=execution_time
            )

    async def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        同步版本的工具调用（包装异步调用）

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult: 工具调用结果
        """
        try:
            return await self.call_tool(tool_name, arguments)
        except Exception as e:
            logger.error(f"同步工具调用异常: {e}")
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message=str(e)
            )

    def get_tools(self) -> Dict[str, ToolMetadata]:
        """
        获取可用工具列表

        Returns:
            Dict[str, ToolMetadata]: 工具名称到元数据的映射
        """
        return self._tools.copy()

    def get_tool(self, tool_name: str) -> Optional[ToolMetadata]:
        """
        获取特定工具的元数据

        Args:
            tool_name: 工具名称

        Returns:
            Optional[ToolMetadata]: 工具元数据，如果不存在则返回 None
        """
        return self._tools.get(tool_name)

    def is_connected(self) -> bool:
        """检查是否已连接到 MCP 服务器"""
        return self._connected

    def get_status(self) -> Dict[str, Any]:
        """
        获取客户端状态

        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "connected": self._connected,
            "server_url": self.server_url,
            "tool_count": len(self._tools),
            "has_mcp": self._has_mcp,
            "last_error": self._last_error,
            "tools": list(self._tools.keys())
        }

    async def disconnect(self):
        """断开 MCP 连接"""
        if self._client:
            try:
                await self._client.close()
                logger.info("MCP 连接已断开")
            except Exception as e:
                logger.error(f"断开连接时出错: {e}")
            finally:
                self._client = None
                self._connected = False
                self._tools.clear()


# 同步包装器类（用于非异步环境）
class SyncMCPClient:
    """
    MCP 客户端的同步包装器

    提供同步接口，内部使用异步事件循环
    """

    def __init__(self, server_url: Optional[str] = None):
        self._async_client = MCPClient(server_url)
        self._loop = None

    def connect(self) -> bool:
        """同步连接"""
        if not self._loop:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        return self._loop.run_until_complete(self._async_client.connect())

    def discover_tools(self) -> Dict[str, ToolMetadata]:
        """同步发现工具"""
        if not self._loop:
            return {}
        return self._loop.run_until_complete(self._async_client.discover_tools())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """同步调用工具"""
        if not self._loop:
            return ToolResult(
                success=False,
                output=None,
                tool_name=tool_name,
                error_message="事件循环未初始化"
            )
        return self._loop.run_until_complete(
            self._async_client.call_tool_sync(tool_name, arguments)
        )

    def get_tools(self) -> Dict[str, ToolMetadata]:
        """同步获取工具列表"""
        return self._async_client.get_tools()

    def get_tool(self, tool_name: str) -> Optional[ToolMetadata]:
        """同步获取工具元数据"""
        return self._async_client.get_tool(tool_name)

    def is_connected(self) -> bool:
        """同步检查连接状态"""
        return self._async_client.is_connected()

    def get_status(self) -> Dict[str, Any]:
        """同步获取状态"""
        return self._async_client.get_status()

    def disconnect(self):
        """同步断开连接"""
        if self._loop:
            self._loop.run_until_complete(self._async_client.disconnect())
            self._loop.close()
            self._loop = None


# 全局 MCP 客户端实例
_mcp_client_instance: Optional[SyncMCPClient] = None

def get_mcp_client() -> SyncMCPClient:
    """
    获取全局 MCP 客户端实例（单例模式）

    Returns:
        SyncMCPClient: MCP 客户端实例
    """
    global _mcp_client_instance

    if _mcp_client_instance is None:
        _mcp_client_instance = SyncMCPClient()

    return _mcp_client_instance

def init_mcp_client() -> bool:
    """
    初始化全局 MCP 客户端

    Returns:
        bool: 初始化是否成功
    """
    client = get_mcp_client()

    # 检查是否启用了工具功能
    use_tools = os.getenv("USE_TOOLS", "false").lower() == "true"
    if not use_tools:
        logger.info("工具功能已禁用 (USE_TOOLS=false)")
        return False

    # 尝试连接
    if client.connect():
        logger.info("MCP 客户端初始化成功")
        return True
    else:
        logger.warning("MCP 客户端初始化失败，工具功能将不可用")
        return False