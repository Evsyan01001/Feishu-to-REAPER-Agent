"""
权限校验服务
负责操作风险分级、权限控制、危险操作拦截
"""
import os
import json
import re
import logging
from enum import Enum
from typing import Optional, Dict, Tuple, Any

from .base_service import BaseService

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """风险级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class PermissionService(BaseService):
    """权限校验服务"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.config_path = self.config.get("config_path", "../config/permissions.json")
        self.permission_config = {}

    def initialize(self) -> bool:
        """初始化权限配置"""
        try:
            self.permission_config = self._load_config()
            logger.info(f"权限校验服务初始化完成，配置文件：{self.config_path}")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"权限校验服务初始化失败: {e}")
            return False

    def cleanup(self) -> None:
        """清理服务资源"""
        self.permission_config.clear()
        self._initialized = False

    def _load_config(self) -> Dict:
        """加载权限配置，不存在则创建默认配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        # 默认配置
        default_config = {
            "whitelist_operations": [],
            "deny_operations": [
                "rm -rf",
                "sudo",
                "format",
                "mkfs",
                "dd if=",
                "chmod 777 /",
                "shutdown",
                "reboot",
                "删除所有轨道",
                "清空工程",
                "rm *.rpp",
                "删除工程文件"
            ]
        }
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        return default_config

    def get_risk_level(self, operation: str) -> RiskLevel:
        """评估操作的风险级别"""
        operation_lower = operation.lower()
        
        # 低风险关键词
        low_risk_keywords = [
            "查询", "搜索", "解释", "什么是", "怎么用", "如何", "推荐",
            "帮助", "说明", "介绍", "术语", "参数", "知识库", "rag"
        ]
        if any(keyword in operation for keyword in low_risk_keywords):
            return RiskLevel.LOW
        
        # 高风险关键词（正则匹配）
        high_risk_keywords = [
            "reaper", "导出音频", "修改工程", "保存工程", "执行命令",
            "写文件", "创建文件", "修改文件", "删除文件", "删除",
            "修改配置", "更新配置", "设置", "安装", "pip install",
            "conda install", "执行脚本", "运行命令", "创建.*轨道",
            "删除.*轨道", "移动.*轨道", "拆分.*音频", "合并.*音频",
            "导出工程", "渲染.*音频", "批量处理", "替换.*音频",
            "修改.*音频", "编辑.*音频", "创建音频轨道", "删除音频轨道"
        ]
        if any(re.search(keyword.lower(), operation_lower) for keyword in high_risk_keywords):
            return RiskLevel.HIGH
        
        return RiskLevel.MEDIUM

    def check_permission(self, operation: str) -> Tuple[Optional[bool], str]:
        """
        检查操作权限
        :param operation: 用户操作内容
        :return: (是否允许: True/允许 False/拒绝 None/需要二次确认, 提示信息)
        """
        risk_level = self.get_risk_level(operation)
        
        operation_lower = operation.lower()
        # 检查禁止操作列表
        if any(deny_op.lower() in operation_lower for deny_op in self.permission_config["deny_operations"]):
            return False, "操作被禁止：包含危险系统命令或危险音频操作"
        
        # 低风险操作自动放行
        if risk_level == RiskLevel.LOW:
            return True, "低风险操作，自动放行"
        
        # 检查白名单
        if any(op in operation for op in self.permission_config["whitelist_operations"]):
            return True, "白名单操作，自动放行"
        
        # 高风险操作需要二次确认
        if risk_level == RiskLevel.HIGH:
            return None, "该操作属于高风险操作，需要您二次确认后执行"
        
        # 中风险操作自动放行
        return True, "中风险操作，自动放行"

    def reload_config(self) -> bool:
        """重新加载配置文件"""
        try:
            self.permission_config = self._load_config()
            logger.info("权限配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"重新加载权限配置失败: {e}")
            return False

    def add_deny_operation(self, operation: str) -> bool:
        """添加禁止操作"""
        if operation not in self.permission_config["deny_operations"]:
            self.permission_config["deny_operations"].append(operation)
            self._save_config()
            return True
        return False

    def add_whitelist_operation(self, operation: str) -> bool:
        """添加白名单操作"""
        if operation not in self.permission_config["whitelist_operations"]:
            self.permission_config["whitelist_operations"].append(operation)
            self._save_config()
            return True
        return False

    def _save_config(self) -> None:
        """保存配置到文件"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.permission_config, f, indent=2, ensure_ascii=False)
