"""
REAPER指令意图数据类

定义REAPER指令解析的结果结构
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class ReaperIntent:
    """REAPER指令意图"""
    type: str  # "ACTION" 或 "CUSTOM"
    action: str  # 对于ACTION类型是"ACTION"，对于CUSTOM类型是操作名如"GAIN"
    value: Optional[str] = None  # 参数值，如Action ID或增益值
    keywords: List[str] = None  # 匹配的关键词
    confidence: float = 0.0  # 匹配置信度

    def __post_init__(self):
        """初始化后处理"""
        if self.keywords is None:
            self.keywords = []

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReaperIntent":
        """从字典创建实例"""
        return cls(
            type=data.get("type", ""),
            action=data.get("action", ""),
            value=data.get("value"),
            keywords=data.get("keywords", []),
            confidence=data.get("confidence", 0.0)
        )

    def is_valid(self) -> bool:
        """检查意图是否有效"""
        if not self.type or not self.action:
            return False

        if self.type == "ACTION" and not self.value:
            return False

        return True

    def __str__(self) -> str:
        """字符串表示"""
        if self.type == "ACTION":
            return f"ReaperIntent(type={self.type}, action={self.action}, value={self.value}, confidence={self.confidence:.2f})"
        else:
            return f"ReaperIntent(type={self.type}, action={self.action}, value={self.value}, confidence={self.confidence:.2f})"