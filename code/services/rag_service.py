"""
RAG检索服务
统一封装知识库检索能力，支持懒加载、多数据源接入
"""
import os
import logging
from typing import Optional, Dict, Any, List

from .base_service import BaseService

logger = logging.getLogger(__name__)

class RAGService(BaseService):
    """RAG检索服务"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        self.rag_engine = None
        self._has_rag = True  # 标记RAG是否可用
        self.lazy_load = self.config.get("lazy_load", True)  # 是否懒加载

    def initialize(self) -> bool:
        """初始化RAG服务"""
        if not self.lazy_load:
            return self._load_rag_engine()
        
        logger.info("RAG服务已初始化（懒加载模式，首次调用时实际加载）")
        self._initialized = True
        return True

    def cleanup(self) -> None:
        """清理服务资源"""
        if self.rag_engine:
            try:
                # 如果RAG引擎有清理方法则调用
                if hasattr(self.rag_engine, 'cleanup'):
                    self.rag_engine.cleanup()
            except:
                pass
        self.rag_engine = None
        self._initialized = False

    def _load_rag_engine(self) -> bool:
        """加载RAG引擎"""
        if not self._has_rag:
            return False
            
        if self.rag_engine:
            return True
            
        try:
            from services.rag_engine import RAGEngine
            self.rag_engine = RAGEngine()
            logger.info("RAG引擎加载成功")
            return True
        except ImportError as e:
            logger.error(f"无法导入 RAG 引擎：{e}")
            self._has_rag = False
            return False
        except Exception as e:
            logger.error(f"RAG 引擎初始化失败：{e}")
            self._has_rag = False
            return False

    def search(
        self,
        query: str,
        k: int = 5,
        return_format: str = "structured",
        min_confidence: float = 0.1
    ) -> Optional[Dict[str, Any]]:
        """
        检索知识库
        :param query: 用户查询
        :param k: 返回结果数量
        :param return_format: 返回格式：structured/raw/text
        :param min_confidence: 最小置信度，低于此值返回None
        :return: 检索结果
        """
        if not self._initialized:
            logger.error("RAG服务未初始化")
            return None
            
        # 懒加载RAG引擎
        if not self.rag_engine and not self._load_rag_engine():
            return None
            
        try:
            result = self.rag_engine.search(query, k=k, return_format=return_format)
            
            # 置信度过滤
            if result and result.get("confidence", 0) < min_confidence:
                logger.debug(f"RAG检索结果置信度({result.get('confidence', 0):.3f})低于阈值({min_confidence})，忽略")
                return None
                
            if result:
                logger.info(f"RAG 检索成功，置信度={result.get('confidence', 0):.3f}，来源数={len(result.get('sources', []))}")
            
            return result
            
        except Exception as e:
            logger.error(f"RAG 检索失败：{e}")
            return None

    def get_context(self, query: str, k: int = 5, min_confidence: float = 0.1) -> str:
        """获取格式化的上下文文本，直接用于LLM输入"""
        result = self.search(query, k=k, min_confidence=min_confidence)
        if not result:
            return ""
            
        context = result.get("answer", "")
        sources = result.get("sources", [])
        
        if sources:
            context += "\n\n参考来源：\n"
            for i, source in enumerate(sources[:3]):  # 最多显示3个来源
                if isinstance(source, dict):
                    title = source.get("title", f"来源{i+1}")
                    context += f"- {title}\n"
                else:
                    context += f"- {str(source)}\n"
        
        return context

    def reload_index(self) -> bool:
        """重新加载知识库索引"""
        if not self.rag_engine:
            return False
            
        try:
            if hasattr(self.rag_engine, 'reload_index'):
                self.rag_engine.reload_index()
                logger.info("RAG索引已重新加载")
                return True
            return False
        except Exception as e:
            logger.error(f"重新加载RAG索引失败: {e}")
            return False

    @property
    def is_available(self) -> bool:
        """RAG服务是否可用"""
        return self._has_rag and (self.rag_engine is not None or self.lazy_load)
