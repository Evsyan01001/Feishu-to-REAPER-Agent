"""
工具管理器
统一管理所有已注册的工具，提供匹配、调用能力
"""
import os
import importlib
import logging
from typing import Dict, List, Optional, Any
from .base_tool import BaseTool

logger = logging.getLogger(__name__)

class ToolManager:
    """工具管理器"""
    
    def __init__(self, auto_load: bool = True):
        self.tools: Dict[str, BaseTool] = {}
        
        if auto_load:
            self._load_builtin_tools()

    def register_tool(self, tool: BaseTool) -> None:
        """注册工具"""
        if tool.tool_id in self.tools:
            logger.warning(f"工具 {tool.tool_id} 已存在，将被覆盖")
        self.tools[tool.tool_id] = tool
        logger.debug(f"已注册工具: {tool.tool_id} - {tool.name}")

    def unregister_tool(self, tool_id: str) -> bool:
        """注销工具"""
        if tool_id in self.tools:
            del self.tools[tool_id]
            logger.debug(f"已注销工具: {tool_id}")
            return True
        return False

    def match_tool(self, user_input: str) -> Optional[BaseTool]:
        """根据用户输入匹配最适合的工具"""
        user_input_lower = user_input.lower()
        
        # 简单关键词匹配，后续可以优化为语义匹配
        for tool in self.tools.values():
            if any(keyword.lower() in user_input_lower for keyword in tool.keywords):
                logger.debug(f"匹配到工具: {tool.tool_id}")
                return tool
                
        return None

    def get_tool(self, tool_id: str) -> Optional[BaseTool]:
        """根据ID获取工具"""
        return self.tools.get(tool_id)

    def list_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具列表"""
        return [
            {
                "tool_id": tool.tool_id,
                "name": tool.name,
                "description": tool.description,
                "keywords": tool.keywords,
                "parameters": tool.parameters
            }
            for tool in self.tools.values()
        ]

    def _load_builtin_tools(self) -> None:
        """自动加载内置工具"""
        # 加载REAPER相关工具
        try:
            from tools.reaper.create_track import CreateTrackTool
            from tools.reaper.delete_track import DeleteTrackTool
            from tools.reaper.split_audio import SplitAudioTool
            from tools.reaper.export_audio import ExportAudioTool
            from tools.reaper.execute_reaper_lua import ExecuteReaperLuaTool
            
            self.register_tool(CreateTrackTool())
            self.register_tool(DeleteTrackTool())
            self.register_tool(SplitAudioTool())
            self.register_tool(ExportAudioTool())
            self.register_tool(ExecuteReaperLuaTool())
            logger.info("REAPER工具加载完成")
        except Exception as e:
            logger.debug(f"加载REAPER工具失败: {e}")
            
        # 加载其他内置工具
        try:
            from tools.file.file_operations import FileReadTool, FileWriteTool
            self.register_tool(FileReadTool())
            self.register_tool(FileWriteTool())
            logger.info("文件工具加载完成")
        except Exception as e:
            logger.debug(f"加载文件工具失败: {e}")
