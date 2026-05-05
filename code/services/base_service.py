"""
基础服务抽象基类
定义所有服务的统一接口规范
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseService(ABC):
    """所有服务的基类"""
    
    @abstractmethod
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        服务初始化
        :param config: 服务配置字典
        """
        self.config = config or {}
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化服务资源
        :return: 初始化是否成功
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """清理服务资源"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """服务是否已初始化"""
        return self._initialized
