"""
工具基类
所有工具/技能都需要继承此类，实现统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseTool(ABC):
    """所有工具的基类"""
    
    # 工具元信息，子类必须实现
    tool_id: str = ""          # 工具唯一ID
    name: str = ""             # 工具名称
    description: str = ""      # 工具描述
    keywords: List[str] = []   # 触发关键词
    parameters: Dict[str, Any] = {}  # 参数定义 {参数名: {type: str, required: bool, description: str}}

    @abstractmethod
    def parse_intent(self, user_input: str, **context) -> Optional[Dict[str, Any]]:
        """
        解析用户意图，提取执行参数
        :param user_input: 用户输入内容
        :param context: 上下文信息（session、历史消息等）
        :return: 解析后的参数字典，解析失败返回None
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具功能
        :param params: 解析后的参数
        :return: 执行结果 {"success": bool, "message": str, ...其他自定义字段}
        """
        pass
