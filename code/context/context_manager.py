"""
上下文系统
统一管理系统提示词、对话历史、上下文压缩、提示词模板
"""
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ContextManager:
    """上下文管理器"""
    
    def __init__(self, prompt_file_path: Optional[str] = None):
        self.prompt_file_path = prompt_file_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "custom_rules.md"
        )
        self._system_prompt = "你是一个专业的游戏音频设计师，擅长使用REAPER进行音频剪辑、音效制作、混音等工作。"
        self._has_loaded = False
        
        # 懒加载，第一次使用时才读取文件
        self._load_prompt_if_needed()

    def _load_prompt_if_needed(self) -> None:
        """懒加载系统提示词"""
        if self._has_loaded:
            return
            
        if os.path.exists(self.prompt_file_path):
            try:
                with open(self.prompt_file_path, "r", encoding="utf-8") as f:
                    self._system_prompt = f.read().strip()
                self._has_loaded = True
                logger.info(f"系统提示词加载完成，文件: {self.prompt_file_path}")
            except Exception as e:
                logger.error(f"加载系统提示词失败: {e}")
        else:
            logger.warning(f"系统提示词文件不存在: {self.prompt_file_path}，使用默认提示词")

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        self._load_prompt_if_needed()
        return self._system_prompt

    def reload_system_prompt(self) -> bool:
        """重新加载系统提示词"""
        self._has_loaded = False
        self._load_prompt_if_needed()
        return self._has_loaded

    def build_messages(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        user_input: str,
        context: str = "",
        max_history_turns: int = 10
    ) -> List[Dict[str, str]]:
        """
        构建发送给LLM的消息数组
        :param system_prompt: 系统提示词
        :param history: 历史对话消息列表
        :param user_input: 当前用户输入
        :param context: RAG检索到的上下文信息
        :param max_history_turns: 最大历史轮次，避免上下文过长
        :return: 格式化的消息列表
        """
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        # 添加历史消息（最多保留max_history_turns轮）
        if history:
            max_messages = max_history_turns * 2
            if len(history) > max_messages:
                history = history[-max_messages:]
            messages.extend(history)
            
        # 构建当前用户消息，附加上下文信息
        if context:
            user_content = f"用户问题：{user_input}\n\n参考信息：\n{context}\n\n请用中文回答："
        else:
            user_content = f"用户问题：{user_input}\n\n请用中文回答："
            
        messages.append({"role": "user", "content": user_content})
        
        return messages

    def compress_context(self, messages: List[Dict[str, str]], max_tokens: int = 4000) -> List[Dict[str, str]]:
        """
        上下文压缩，避免token超限（待实现）
        后续可以实现：
        1. 摘要压缩：对旧的历史对话进行LLM摘要
        2. 滑动窗口：只保留最近的N轮对话
        3. 重要性过滤：只保留和当前查询相关的历史消息
        """
        # 目前先使用简单的滑动窗口
        if len(messages) > 20:  # 10轮对话
            # 保留系统提示词 + 最近8轮对话
            return [messages[0]] + messages[-16:]
        return messages
