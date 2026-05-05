"""
REAPER音频工作站控制器

整合指令解析器、Action映射器和文件通信器，提供完整的REAPER指令处理流程。
"""

import logging
from typing import Dict, Any, Optional, Tuple
from .instruction_parser import ReaperInstructionParser
from .action_mapper import ActionMapper
from .file_communicator import FileCommunicator
from .reaper_intent import ReaperIntent

logger = logging.getLogger(__name__)


class ReaperController:
    """独立REAPER音频工作站控制器"""

    def __init__(self, actions_file: str = None, cmd_file: str = None):
        """
        初始化REAPER控制器

        Args:
            actions_file: reaper_actions.md文件路径，如果为None则自动查找
            cmd_file: 通信文件路径，如果为None则使用默认路径
        """
        logger.info("初始化REAPER控制器")

        # 初始化组件
        self.parser = ReaperInstructionParser()
        self.mapper = ActionMapper(actions_file)
        self.communicator = FileCommunicator(cmd_file)

        # 检查组件状态
        self._check_components()

    def _check_components(self):
        """检查组件状态"""
        logger.info("检查REAPER控制器组件状态")

        # 检查Action映射器
        stats = self.mapper.get_stats()
        logger.info(f"Action映射器状态: {stats['total_actions']}个Action, {stats['total_keywords']}个关键词")

        # 检查文件通信器
        file_info = self.communicator.get_file_info()
        logger.info(f"文件通信器状态: 路径={file_info['path']}, 存在={file_info['exists']}")

        # 测试文件访问
        if not file_info.get("exists", False):
            logger.warning(f"通信文件不存在: {file_info['path']}")
        else:
            logger.info(f"通信文件已存在: {file_info['path']}")

    def process_command(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户自然语言指令

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"处理REAPER指令: {user_input}")

        try:
            # 1. 解析用户输入，匹配Action ID或自定义操作
            intent = self.parser.parse(user_input)

            # 2. 根据意图类型生成指令
            if intent.type == "ACTION":
                # 查找Action ID
                result = self.mapper.find_action_id(user_input)
                if result is None:
                    return {
                        "success": False,
                        "error": "未找到匹配的Action ID",
                        "suggestion": self._suggest_actions(user_input),
                        "intent": intent.to_dict()
                    }

                action_id, confidence = result
                command = f"ACTION|{action_id}"
                intent.value = str(action_id)
                intent.confidence = confidence

            elif intent.type == "CUSTOM":
                # 生成自定义操作指令
                if intent.value:
                    command = f"{intent.action}|{intent.value}"
                else:
                    command = intent.action
            else:
                return {
                    "success": False,
                    "error": f"无法识别的指令类型: {intent.type}",
                    "intent": intent.to_dict()
                }

            # 3. 通过文件通信器发送指令
            success, message = self.communicator.send_command(command)

            # 4. 返回结果
            result = {
                "success": success,
                "command": command,
                "intent": intent.to_dict(),
                "message": message if success else f"指令发送失败: {message}"
            }

            logger.info(f"REAPER指令处理完成: 成功={success}, 指令={command}")
            return result

        except Exception as e:
            logger.error(f"REAPER指令处理失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"指令处理失败: {str(e)}",
                "suggestion": "请尝试更简单的指令，如'播放'、'暂停'、'录音'等"
            }

    def process_command_with_fallback(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户指令，包含降级策略

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"处理REAPER指令（带降级策略）: {user_input}")

        try:
            # 首先尝试正常处理
            return self.process_command(user_input)

        except Exception as e:
            logger.warning(f"REAPER指令处理失败，尝试降级处理: {e}")

            # 降级策略：简化解析
            simplified_result = self._simplified_process(user_input)
            if simplified_result.get("success"):
                logger.info("降级处理成功")
                return simplified_result

            # 如果还是失败，返回错误信息和建议
            return {
                "success": False,
                "error": f"指令处理失败: {str(e)}",
                "suggestion": self._suggest_actions(user_input),
                "available_operations": self._get_available_operations()
            }

    def _simplified_process(self, user_input: str) -> Dict[str, Any]:
        """
        简化处理流程

        Args:
            user_input: 用户输入

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 尝试直接匹配关键词
            input_lower = user_input.lower()

            # 常见指令的直接映射
            direct_mappings = {
                "播放": "ACTION|40001",
                "暂停": "ACTION|40001",  # 播放/暂停是同一个Action
                "停止": "ACTION|40002",
                "录音": "ACTION|1013",
                "停止录音": "ACTION|1014",
                "导出": "EXPORT",
                "音量调大": "GAIN|3",
                "音量调小": "GAIN|-3",
                "降噪": "DENOISE|1",
            }

            for keyword, command in direct_mappings.items():
                if keyword in input_lower:
                    success, message = self.communicator.send_command(command)

                    # 解析命令类型
                    if command.startswith("ACTION|"):
                        intent_type = "ACTION"
                        action = "ACTION"
                        value = command.split("|")[1]
                    elif "|" in command:
                        intent_type = "CUSTOM"
                        parts = command.split("|")
                        action = parts[0]
                        value = parts[1] if len(parts) > 1 else None
                    else:
                        intent_type = "CUSTOM"
                        action = command
                        value = None

                    return {
                        "success": success,
                        "command": command,
                        "intent": {
                            "type": intent_type,
                            "action": action,
                            "value": value,
                            "keywords": [keyword],
                            "confidence": 0.7
                        },
                        "message": message if success else f"指令发送失败: {message}"
                    }

            return {"success": False, "error": "无法简化处理"}

        except Exception as e:
            logger.error(f"简化处理失败: {e}")
            return {"success": False, "error": f"简化处理失败: {str(e)}"}

    def _suggest_actions(self, user_input: str) -> str:
        """
        根据用户输入提供Action建议

        Args:
            user_input: 用户输入

        Returns:
            str: 建议文本
        """
        try:
            # 检查是否是模糊请求
            vague_patterns = ["怎么", "如何", "操作", "help", "帮助", "列出", "list", "所有", "全部"]
            if any(pattern in user_input.lower() for pattern in vague_patterns):
                # 返回所有操作类别的帮助
                return self._get_operation_help()

            # 搜索相关Action
            results = self.mapper.search_actions(user_input, limit=5)
            if results:
                suggestions = []
                for action_info, score in results:
                    suggestions.append(f"- {action_info.description} (ID: {action_info.action_id})")

                return f"找不到完全匹配的Action，以下可能是您需要的:\n" + "\n".join(suggestions)
            else:
                return "找不到相关Action，请尝试其他关键词或查看可用操作列表。"

        except Exception as e:
            logger.error(f"生成建议失败: {e}")
            return "无法生成建议，请查看可用操作列表。"

    def _get_operation_help(self) -> str:
        """获取操作帮助信息"""
        try:
            categories = self.mapper.get_all_categories()
            custom_ops = self.parser.get_custom_operations_info()

            lines = ["📋 REAPER控制器支持的指令类型:\n"]

            # 自定义操作
            if custom_ops:
                lines.append("【自定义操作】")
                for op, info in custom_ops.items():
                    desc = info.get("description", "未知操作")
                    default = info.get("default_value")
                    default_str = f" (默认: {default})" if default else ""
                    lines.append(f"  • {op}: {desc}{default_str}")
                lines.append("")

            # Action分类
            if categories:
                lines.append("【Action操作】")
                for category in categories:
                    actions = self.mapper.get_actions_by_category(category)
                    action_names = [a.description for a in actions[:5]]
                    lines.append(f"  • {category}: {', '.join(action_names)}")

            lines.append("\n💡 示例指令: '播放音频', '音量调大3分贝', '导出', '声像偏左50%'")
            lines.append("输入 'help' 或 '怎么操作' 查看此帮助信息")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"生成帮助信息失败: {e}")
            return "无法生成帮助信息。"

    def _get_available_operations(self) -> Dict[str, Any]:
        """获取可用操作列表"""
        try:
            # 获取自定义操作信息
            custom_ops = self.parser.get_custom_operations_info()

            # 获取Action分类
            categories = self.mapper.get_all_categories()
            category_actions = {}
            for category in categories:
                actions = self.mapper.get_actions_by_category(category)
                category_actions[category] = [
                    {"id": action.action_id, "description": action.description}
                    for action in actions[:10]  # 每个分类最多显示10个
                ]

            return {
                "custom_operations": custom_ops,
                "action_categories": category_actions,
                "total_actions": self.mapper.get_stats()["total_actions"]
            }

        except Exception as e:
            logger.error(f"获取可用操作失败: {e}")
            return {"error": str(e)}

    def check_health(self) -> Dict[str, Any]:
        """检查控制器健康状态"""
        health_info = {
            "status": "healthy",
            "components": {}
        }

        try:
            # 检查Action映射器
            stats = self.mapper.get_stats()
            health_info["components"]["action_mapper"] = {
                "status": "healthy" if stats["total_actions"] > 0 else "warning",
                "total_actions": stats["total_actions"],
                "total_keywords": stats["total_keywords"]
            }

            # 检查文件通信器
            file_info = self.communicator.get_file_info()
            health_info["components"]["file_communicator"] = {
                "status": "healthy" if file_info.get("exists", False) else "warning",
                "file_path": file_info["path"],
                "file_exists": file_info.get("exists", False),
                "platform": file_info.get("platform", "unknown")
            }

            # 检查指令解析器
            health_info["components"]["instruction_parser"] = {
                "status": "healthy",
                "reaper_keywords_count": len(self.parser.REAPER_KEYWORDS),
                "custom_operations_count": len(self.parser.CUSTOM_OPERATIONS)
            }

            # 总体状态
            all_healthy = all(
                comp["status"] == "healthy"
                for comp in health_info["components"].values()
            )
            health_info["status"] = "healthy" if all_healthy else "degraded"

        except Exception as e:
            health_info["status"] = "unhealthy"
            health_info["error"] = str(e)

        return health_info

    def get_stats(self) -> Dict[str, Any]:
        """获取控制器统计信息"""
        stats = {
            "controller": {
                "initialized": True,
                "version": "1.0.0"
            }
        }

        try:
            # 合并各组件统计
            stats.update(self.mapper.get_stats())
            stats["file_communicator"] = self.communicator.get_file_info()
            stats["instruction_parser"] = self.parser.get_custom_operations_info()

        except Exception as e:
            stats["error"] = str(e)

        return stats