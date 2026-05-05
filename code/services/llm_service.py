"""
LLM服务
统一封装大语言模型API调用，支持多模型切换、流式响应
"""
import os
import json
import requests
import logging
from typing import List, Dict, Optional, Generator, Any

from .base_service import BaseService

logger = logging.getLogger(__name__)

class LLMService(BaseService):
    """LLM服务"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.api_key = self.config.get("api_key", os.getenv("DEEPSEEK_API_KEY"))
        self.base_url = self.config.get("base_url", "https://api.deepseek.com/v1")
        self.model = self.config.get("model", os.getenv("MODEL_NAME", "deepseek-chat"))
        self.default_temperature = self.config.get("temperature", 0.7)
        self.default_max_tokens = self.config.get("max_tokens", 2000)

    def initialize(self) -> bool:
        """初始化LLM服务"""
        if not self.api_key:
            logger.warning("LLM API密钥未配置，LLM服务将不可用")
            self._initialized = False
            return False
        
        logger.info(f"LLM服务初始化完成，模型：{self.model}，API地址：{self.base_url}")
        self._initialized = True
        return True

    def cleanup(self) -> None:
        """清理服务资源"""
        self._initialized = False

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Optional[Generator[str, None, None] | str | Dict[str, Any]]:
        """
        聊天补全接口
        :param messages: 消息列表，格式为[{"role": "user/assistant/system", "content": "xxx"}]
        :param temperature: 温度参数
        :param max_tokens: 最大生成长度
        :param stream: 是否使用流式响应
        :return: 流式响应生成器，或非流式的完整响应字符串
        """
        if not self._initialized:
            logger.error("LLM服务未初始化")
            return None
        
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model":       self.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
            "stream":      stream,
        }
        
        # 添加工具调用参数
        if tools and not stream:  # 工具调用暂不支持流式响应
            data["tools"] = tools
            data["tool_choice"] = tool_choice
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                stream=stream,
                timeout=30,
            )
            response.raise_for_status()
            
            if stream:
                return self._parse_stream_response(response)
            else:
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"LLM API调用失败：{e}")
            return None

    def _parse_stream_response(self, response) -> Generator[str, None, None]:
        """解析流式响应"""
        for line in response.iter_lines():
            if not line:
                continue
            
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]
            
            if line == "[DONE]":
                break
            
            try:
                chunk = json.loads(line)
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
            except json.JSONDecodeError:
                continue

    def set_model(self, model_name: str) -> None:
        """切换模型"""
        self.model = model_name
        logger.info(f"已切换LLM模型为：{model_name}")

    def set_api_key(self, api_key: str) -> None:
        """更新API密钥"""
        self.api_key = api_key
        self.initialize()  # 重新初始化
