"""
Action ID映射管理器

解析reaper_actions.md文件，构建关键词到Action ID的映射
支持模糊匹配和优先级排序
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ActionInfo:
    """Action信息"""
    action_id: int
    description: str
    keywords: List[str]
    category: str


class ActionMapper:
    """管理Action ID与语义关键词的映射"""

    def __init__(self, actions_file: str = None):
        """
        初始化Action映射器

        Args:
            actions_file: reaper_actions.md文件路径，如果为None则自动查找
        """
        if actions_file is None:
            # 自动查找文件
            current_dir = os.path.dirname(os.path.abspath(__file__))
            actions_file = os.path.join(current_dir, "..", "..", "data", "reaper_actions.md")

        self.actions_file = actions_file
        self.actions: Dict[int, ActionInfo] = {}  # action_id -> ActionInfo
        self.keyword_index: Dict[str, List[Tuple[int, float]]] = {}  # keyword -> [(action_id, confidence), ...]
        self.category_index: Dict[str, List[int]] = {}  # category -> [action_id, ...]

        self._load_actions()
        self._build_indexes()

    def _load_actions(self):
        """解析reaper_actions.md文件"""
        if not os.path.exists(self.actions_file):
            logger.warning(f"Action映射文件不存在: {self.actions_file}")
            return

        try:
            with open(self.actions_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            current_category = "未知"
            in_table = False
            table_header_found = False

            for line in lines:
                line = line.rstrip('\n')

                # 检测分类标题 (## 1. 播放与导航 (Transport & Navigation))
                if line.startswith('## '):
                    # 提取分类名称，移除数字和点
                    # 格式: ## 1. 播放与导航 (Transport & Navigation)
                    category_match = re.match(r'##\s*\d+\.\s*(.*?)(?:\s*\(.*?\))?$', line)
                    if category_match:
                        current_category = category_match.group(1).strip()
                        logger.debug(f"检测到分类: {current_category}")
                        in_table = False
                        table_header_found = False
                    continue

                # 检测表格开始 (包含表头行)
                if '|' in line and ('Action ID' in line or '功能描述' in line):
                    in_table = True
                    table_header_found = True
                    continue

                # 检测表格分隔符行
                if in_table and '|' in line and (':---' in line or '---' in line):
                    continue

                # 处理表格数据行
                if in_table and '|' in line:
                    # 解析表格行: | Action ID | 功能描述 | 语义关键词 (触发词) |
                    # 支持加粗标记: **40001** 或普通数字
                    table_pattern = r'\|\s*\*{0,2}(\d+)\*{0,2}\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|'
                    match = re.match(table_pattern, line)
                    if not match:
                        continue

                    action_id_str, description, keywords_str = match.groups()

                    # 过滤空行和无效数据
                    if not action_id_str or not action_id_str.strip().isdigit():
                        continue

                    # 解析Action ID
                    try:
                        action_id = int(action_id_str.strip())
                    except ValueError:
                        logger.warning(f"无效的Action ID: {action_id_str}")
                        continue

                    # 解析关键词
                    keywords = self._parse_keywords(keywords_str)

                    # 创建ActionInfo
                    action_info = ActionInfo(
                        action_id=action_id,
                        description=description.strip(),
                        keywords=keywords,
                        category=current_category
                    )

                    self.actions[action_id] = action_info
                    logger.debug(f"加载Action: {action_id} - {description} ({current_category})")

                elif in_table and not line.strip():
                    # 空行，可能是表格结束
                    continue
                elif in_table and line.strip() and not '|' in line:
                    # 非表格行，退出表格模式
                    in_table = False
                    table_header_found = False

            logger.info(f"成功加载 {len(self.actions)} 个Action，分类: {set(info.category for info in self.actions.values())}")

        except Exception as e:
            logger.error(f"解析Action映射文件失败: {e}")

    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """解析关键词字符串"""
        keywords = []
        if not keywords_str:
            return keywords

        # 分割关键词：支持中文逗号、英文逗号、顿号、分号
        raw_keywords = re.split(r'[，,、;]', keywords_str)

        for raw_keyword in raw_keywords:
            keyword = raw_keyword.strip()
            if keyword:
                # 清理括号内容
                keyword = re.sub(r'\s*\(.*?\)', '', keyword)
                # 清理多余空格
                keyword = ' '.join(keyword.split())
                if keyword:
                    keywords.append(keyword)

        return keywords

    def _build_indexes(self):
        """构建索引"""
        # 清空索引
        self.keyword_index.clear()
        self.category_index.clear()

        for action_id, action_info in self.actions.items():
            # 构建关键词索引
            for keyword in action_info.keywords:
                # 关键词归一化：小写、去除空格
                normalized_keyword = keyword.lower().replace(' ', '')

                if normalized_keyword not in self.keyword_index:
                    self.keyword_index[normalized_keyword] = []

                # 置信度：关键词匹配度
                confidence = 1.0  # 完全匹配

                self.keyword_index[normalized_keyword].append((action_id, confidence))

            # 构建分类索引
            category = action_info.category
            if category not in self.category_index:
                self.category_index[category] = []
            self.category_index[category].append(action_id)

        logger.debug(f"构建索引完成：关键词 {len(self.keyword_index)} 个，分类 {len(self.category_index)} 个")

    def find_action_id(self, user_input: str) -> Optional[Tuple[int, float]]:
        """
        基于用户输入查找最匹配的Action ID

        Args:
            user_input: 用户输入的自然语言指令

        Returns:
            Optional[Tuple[int, float]]: (action_id, confidence) 或 None
        """
        if not self.actions:
            logger.warning("Action映射未加载")
            return None

        # 归一化用户输入
        normalized_input = user_input.lower().replace(' ', '')

        # 收集所有匹配的Action ID和分数
        scores: Dict[int, float] = {}

        # 遍历所有关键词，计算匹配分数
        for keyword, action_matches in self.keyword_index.items():
            # 计算该关键词的匹配分数
            keyword_score = 0.0

            # 1. 完全匹配：关键词在用户输入中
            if keyword in normalized_input:
                # 分数基于关键词长度：更长的关键词更具体，得分更高
                keyword_score = 2.0 + (len(keyword) * 0.01)  # 基础分2.0 + 长度奖励
            # 2. 部分匹配：关键词的部分在用户输入中
            else:
                # 将关键词分割成单词（如果有关键词包含空格）
                keyword_parts = keyword.split()
                if len(keyword_parts) > 1:
                    # 多词关键词：检查每个部分是否在用户输入中
                    matched_parts = sum(1 for part in keyword_parts if part in normalized_input)
                    if matched_parts > 0:
                        # 部分匹配分数较低，但匹配的部分越多分数越高
                        keyword_score = 1.0 * (matched_parts / len(keyword_parts))
                else:
                    # 单关键词：检查部分匹配（至少3个字符）
                    if len(keyword) >= 3:
                        for i in range(len(keyword) - 2):
                            substring = keyword[i:i+3]
                            if substring in normalized_input:
                                keyword_score = 0.6  # 部分匹配置信度较低
                                break

            # 如果有关键词匹配，将分数分配给对应的Action
            if keyword_score > 0:
                for action_id, base_confidence in action_matches:
                    # 最终分数 = 基础置信度 * 关键词匹配分数
                    final_score = base_confidence * keyword_score
                    if action_id not in scores:
                        scores[action_id] = 0.0
                    scores[action_id] += final_score  # 累加多个关键词的分数

        # 如果没有匹配，返回None
        if not scores:
            return None

        # 选择分数最高的匹配
        best_action_id, best_score = max(scores.items(), key=lambda x: x[1])

        # 归一化分数到[0, 1]范围（除以可能的最大分数）
        # 最大分数假设：每个关键词完全匹配得1.0，但可能有多个关键词
        # 简单归一化：如果分数超过2.0，则限制为1.0
        normalized_confidence = min(1.0, best_score / 2.0)

        logger.info(f"匹配Action: {best_action_id} (分数: {best_score:.2f}, 置信度: {normalized_confidence:.2f})")

        return (best_action_id, normalized_confidence)

    def get_action_info(self, action_id: int) -> Optional[ActionInfo]:
        """获取指定Action ID的信息"""
        return self.actions.get(action_id)

    def get_actions_by_category(self, category: str) -> List[ActionInfo]:
        """获取指定分类的所有Action"""
        action_ids = self.category_index.get(category, [])
        return [self.actions[action_id] for action_id in action_ids if action_id in self.actions]

    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self.category_index.keys())

    def search_actions(self, query: str, limit: int = 10) -> List[Tuple[ActionInfo, float]]:
        """
        搜索Action

        Args:
            query: 搜索查询
            limit: 返回结果数量限制

        Returns:
            List[Tuple[ActionInfo, float]]: (Action信息, 匹配分数)
        """
        results = []
        normalized_query = query.lower()

        for action_info in self.actions.values():
            score = 0.0

            # 检查描述是否包含查询
            if normalized_query in action_info.description.lower():
                score += 0.5

            # 检查关键词是否包含查询
            for keyword in action_info.keywords:
                if normalized_query in keyword.lower():
                    score += 1.0
                elif any(part in normalized_query for part in keyword.lower().split() if len(part) > 2):
                    score += 0.3

            # 检查分类是否包含查询
            if normalized_query in action_info.category.lower():
                score += 0.2

            if score > 0:
                results.append((action_info, score))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_stats(self) -> Dict[str, any]:
        """获取统计信息"""
        return {
            "total_actions": len(self.actions),
            "total_keywords": len(self.keyword_index),
            "categories": list(self.category_index.keys()),
            "categories_count": {cat: len(ids) for cat, ids in self.category_index.items()}
        }