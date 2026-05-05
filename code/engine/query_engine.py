"""
QueryEngine 会话引擎
统一管理会话生命周期，所有上层模式（REPL/单次查询/SDK/飞书Webhook）都通过此引擎交互
"""
import os
import logging
from typing import Optional, Dict, Any, Generator
from dotenv import load_dotenv

# 导入核心服务
from services.conversation_service import ConversationService
from services.permission_service import PermissionService
from services.llm_service import LLMService
from services.rag_service import RAGService

# 导入核心组件
from core.query_loop import QueryLoop
from context.context_manager import ContextManager
from tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)

class QueryEngine:
    """会话引擎，对外提供统一查询接口"""
    
    def __init__(self, config_path: Optional[str] = None):
        # 加载环境变量
        load_dotenv(config_path)
        
        # 初始化核心服务
        self.conversation_service = ConversationService()
        self.permission_service = PermissionService()
        self.llm_service = LLMService()
        self.rag_service = RAGService()
        
        # 初始化核心组件
        self.context_manager = ContextManager()
        self.tool_manager = ToolManager()
        
        # 初始化查询核心循环
        self.query_loop = QueryLoop(
            llm_service=self.llm_service,
            rag_service=self.rag_service,
            permission_service=self.permission_service,
            context_manager=self.context_manager,
            tool_manager=self.tool_manager
        )
        
        # 初始化所有服务
        self._initialize_services()

    def _initialize_services(self) -> None:
        """初始化所有依赖服务"""
        logger.info("正在初始化QueryEngine服务...")
        
        self.conversation_service.initialize()
        self.permission_service.initialize()
        self.llm_service.initialize()
        self.rag_service.initialize()
        
        logger.info("QueryEngine初始化完成")

    def query(
        self,
        user_input: str,
        user_id: str = "default_user",
        stream: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一查询入口，所有上层模式都通过此方法查询
        :param user_input: 用户输入内容
        :param user_id: 用户ID，用于会话隔离
        :param stream: 是否使用流式响应
        :param kwargs: 其他扩展参数
        :return: 统一格式的查询结果
        """
        logger.info(f"收到查询请求: user_id={user_id}, input={user_input[:100]}...")
        
        # 1. 获取或创建用户会话
        session = self.conversation_service.get_or_create(user_id)
        
        try:
            # 2. 执行核心查询循环
            result = self.query_loop.execute(
                user_input=user_input,
                session=session,
                stream=stream,
                **kwargs
            )
            
            # 3. 保存会话更新
            if result.get("save_session", True):
                # 如果是流式响应，调用方需要在迭代完成后手动保存
                if not isinstance(result.get("answer"), (Generator, types.GeneratorType)):
                    if result.get("assistant_message"):
                        session.add_assistant_message(result["assistant_message"])
                    self.conversation_service.save(session)
            
            result["turn_count"] = session.turn_count
            return result
            
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            return {
                "success": False,
                "answer": f"处理失败：{str(e)}",
                "source": "engine.error",
                "has_context": False,
                "rag_confidence": 0.0,
                "turn_count": session.turn_count
            }

    def reset_session(self, user_id: str = "default_user") -> None:
        """重置用户会话"""
        self.conversation_service.delete(user_id)
        logger.info(f"会话已重置: user_id={user_id}")

    def get_session_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """获取会话统计信息"""
        if user_id:
            session = self.conversation_service.get_or_create(user_id)
            return session.summary()
        return self.conversation_service.stats()

    def cleanup(self) -> None:
        """清理所有服务资源"""
        logger.info("正在关闭QueryEngine...")
        self.conversation_service.cleanup()
        self.permission_service.cleanup()
        self.llm_service.cleanup()
        self.rag_service.cleanup()
        logger.info("QueryEngine已关闭")

    # SDK模式快捷方法
    def __enter__(self):
        """支持with语句使用"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """with语句退出时自动清理"""
        self.cleanup()
