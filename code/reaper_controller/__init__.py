"""
REAPER音频工作站控制器模块

提供自然语言到REAPER指令的转换功能，支持：
1. 解析用户自然语言指令
2. 匹配reaper_actions.md中的Action ID
3. 生成listen.lua可识别的指令格式
4. 通过文件系统与REAPER通信
"""

from .reaper_intent import ReaperIntent
from .action_mapper import ActionMapper
from .instruction_parser import ReaperInstructionParser
from .file_communicator import FileCommunicator
from .reaper_controller import ReaperController

__all__ = [
    "ReaperIntent",
    "ActionMapper",
    "ReaperInstructionParser",
    "FileCommunicator",
    "ReaperController"
]

__version__ = "1.0.0"