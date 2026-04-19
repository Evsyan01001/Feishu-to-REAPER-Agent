"""
REAPER指令解析器

解析自然语言REAPER指令，匹配关键词，判断指令类型（ACTION或CUSTOM），提取参数。
"""

import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from .reaper_intent import ReaperIntent

logger = logging.getLogger(__name__)


class ReaperInstructionParser:
    """解析自然语言REAPER指令"""

    # 自定义操作关键词映射
    CUSTOM_OPERATIONS = {
        "GAIN": {
            "keywords": ["音量", "增益", "调大", "调小", "增大", "减小", "分贝", "db", "gain", "volume"],
            "value_patterns": [
                r"([+-]?\d+(?:\.\d+)?)\s*(?:分贝|db|dB|dBFS)?",
                r"调[大减小](?:\s*([+-]?\d+(?:\.\d+)?)\s*(?:分贝|db|dB|dBFS)?)?",
                r"(?:增加|减少|增大|减小)\s*([+-]?\d+(?:\.\d+)?)\s*(?:分贝|db|dB|dBFS)?",
                r"(?:gain|volume)\s*([+-]?\d+(?:\.\d+)?)\s*(?:db|dB|dBFS)?",
            ],
            "default_value": "3",  # 默认增益值
        },
        "DENOISE": {
            "keywords": ["降噪", "去噪", "消除噪音", "噪声", "denoise", "noise reduction"],
            "value_patterns": [
                r"([+-]?\d+(?:\.\d+)?)\s*(?:级|等级|level)?",
                r"(?:设置|调整|设为)\s*([+-]?\d+(?:\.\d+)?)\s*(?:级|等级|level)?",
                r"(?:denoise|noise reduction)\s*([+-]?\d+(?:\.\d+)?)\s*(?:level)?",
            ],
            "default_value": "1",  # 默认降噪等级
        },
        "EXPORT": {
            "keywords": ["导出", "输出", "渲染", "出片", "保存文件", "export", "render", "save file"],
            "value_patterns": [],  # 导出操作通常不需要参数
            "default_value": None,
        },
        "PAN": {
            "keywords": ["声像", "左右", "平衡", "偏左", "偏右", "pan", "panning", "stereo balance"],
            "value_patterns": [
                r"([+-]?\d+(?:\.\d+)?)\s*(?:百分比|%|percent)?",
                r"([+-]?\d+(?:\.\d+)?)\s*(?:左|右)?",
                r"(?:调整|设置|设为)\s*([+-]?\d+(?:\.\d+)?)\s*(?:百分比|%|percent)?",
                r"(?:pan|balance)\s*([+-]?\d+(?:\.\d+)?)\s*(?:%|percent)?",
            ],
            "default_value": "0",  # 居中
        },
        "EQ": {
            "keywords": ["均衡器", "音频均衡", "eq", "频率调节", "低频调节", "高频调节", "中频调节", "equalizer", "bass boost", "treble boost", "mid boost"],
            "value_patterns": [
                r"([+-]?\d+(?:\.\d+)?)\s*(?:分贝|db|dB|dBFS)?",
                r"(?:调整|设置|增加|减少)\s*([+-]?\d+(?:\.\d+)?)\s*(?:分贝|db|dB|dBFS)?",
                r"(?:eq|equalizer)\s*([+-]?\d+(?:\.\d+)?)\s*(?:db|dB|dBFS)?",
            ],
            "default_value": "0",  # 无增益
        },
    }

    # REAPER操作关键词（用于检测是否为REAPER指令）
    REAPER_KEYWORDS = [
        "播放", "暂停", "录音", "轨道", "音量", "导出", "剪切", "复制", "粘贴",
        "撤销", "重做", "静音", "独奏", "新建", "删除", "拆分", "吸附", "循环",
        "标记", "跳转", "开始", "停止", "增益", "降噪", "渲染", "工程", "文件",
        "play", "pause", "record", "track", "volume", "export", "cut", "copy", "paste",
        "undo", "redo", "mute", "solo", "new", "delete", "split", "snap", "loop",
        "marker", "jump", "start", "stop", "gain", "denoise", "render", "project", "file",
        "声像", "平衡", "eq", "均衡", "pan", "equalizer", "bass", "treble", "mid", "frequency"
    ]

    def __init__(self):
        """初始化指令解析器"""
        logger.info("REAPER指令解析器初始化")

    def is_reaper_command(self, user_input: str) -> bool:
        """
        判断用户输入是否为REAPER操作指令

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            bool: 如果是REAPER指令返回True
        """
        if not user_input or not isinstance(user_input, str):
            return False

        # 转换为小写进行匹配
        input_lower = user_input.lower()

        # 检查是否包含REAPER关键词
        for keyword in self.REAPER_KEYWORDS:
            if keyword.lower() in input_lower:
                return True

        return False

    def parse(self, user_input: str) -> ReaperIntent:
        """
        解析用户自然语言指令

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            ReaperIntent: 解析出的意图对象
        """
        if not user_input or not isinstance(user_input, str):
            return ReaperIntent(
                type="UNKNOWN",
                action="UNKNOWN",
                keywords=[],
                confidence=0.0
            )

        logger.info(f"解析REAPER指令: {user_input}")

        # 首先尝试匹配自定义操作
        custom_intent = self._parse_custom_operation(user_input)
        if custom_intent and custom_intent.is_valid():
            logger.info(f"识别为自定义操作: {custom_intent}")
            return custom_intent

        # 如果不是自定义操作，则认为是ACTION操作
        # 提取关键词用于后续Action匹配
        keywords = self._extract_keywords(user_input)

        return ReaperIntent(
            type="ACTION",
            action="ACTION",
            value=None,  # Action ID由ActionMapper确定
            keywords=keywords,
            confidence=0.8  # 默认置信度
        )

    def _parse_custom_operation(self, user_input: str) -> Optional[ReaperIntent]:
        """
        解析自定义操作（GAIN, DENOISE, EXPORT）

        Args:
            user_input: 用户输入

        Returns:
            Optional[ReaperIntent]: 解析出的意图对象，如果不是自定义操作则返回None
        """
        input_lower = user_input.lower()

        # 收集所有匹配的操作和关键词
        matches: List[Tuple[str, str, str]] = []  # [(operation, keyword, value), ...]

        for operation, config in self.CUSTOM_OPERATIONS.items():
            # 检查是否包含该操作的关键词
            for keyword in config["keywords"]:
                if keyword.lower() in input_lower:
                    # 尝试提取参数值
                    value = self._extract_custom_value(user_input, config["value_patterns"])
                    # 如果没有提取到值，使用默认值
                    if value is None and config["default_value"] is not None:
                        value = config["default_value"]
                    matches.append((operation, keyword, value))

        # 选择最长关键词的匹配（更具体的操作优先）
        if matches:
            best_match = max(matches, key=lambda x: len(x[1]))
            operation, keyword, value = best_match
            config = self.CUSTOM_OPERATIONS[operation]

            # 对于EXPORT操作，如果没有参数，value为None
            if operation == "EXPORT" and value is None:
                value = ""

            logger.info(f"识别到自定义操作: {operation}, 参数: {value}")

            return ReaperIntent(
                type="CUSTOM",
                action=operation,
                value=value,
                keywords=[keyword],
                confidence=0.9
            )

        return None

    def _extract_custom_value(self, user_input: str, patterns: List[str]) -> Optional[str]:
        """
        从用户输入中提取自定义操作的参数值

        Args:
            user_input: 用户输入
            patterns: 正则表达式模式列表

        Returns:
            Optional[str]: 提取的参数值，如果未找到则返回None
        """
        for pattern in patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                # 提取第一个捕获组
                for group in match.groups():
                    if group is not None:
                        return group.strip()

        # 如果没有匹配到模式，尝试提取数字
        number_matches = re.findall(r'([+-]?\d+(?:\.\d+)?)', user_input)
        if number_matches:
            return number_matches[0]

        return None

    def _extract_keywords(self, user_input: str) -> List[str]:
        """
        从用户输入中提取关键词

        Args:
            user_input: 用户输入

        Returns:
            List[str]: 提取的关键词列表
        """
        keywords = []

        # 去除标点符号
        cleaned_input = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', user_input)

        # 分词（简单空格分割）
        words = cleaned_input.split()

        # 中文可能需要更复杂的分词，这里先简单处理
        for word in words:
            word = word.strip()
            if word and len(word) > 1:  # 过滤单字
                # 检查是否是REAPER关键词
                if any(keyword.lower() == word.lower() for keyword in self.REAPER_KEYWORDS):
                    keywords.append(word)

        return keywords

    def get_custom_operations_info(self) -> Dict[str, Any]:
        """获取自定义操作信息"""
        info = {}
        for operation, config in self.CUSTOM_OPERATIONS.items():
            info[operation] = {
                "keywords": config["keywords"],
                "default_value": config["default_value"],
                "description": {
                    "GAIN": "调整音量增益（单位：分贝）",
                    "DENOISE": "降噪处理（等级：1-10）",
                    "EXPORT": "导出音频文件",
                    "PAN": "调整声像平衡（-100左到+100右）",
                    "EQ": "调整均衡器增益（单位：分贝）"
                }.get(operation, "未知操作")
            }
        return info