"""
Query 核心循环
处理查询的完整生命周期：权限校验 → RAG检索 → 工具调用 → LLM生成 → 结果返回
"""
import logging
import types
from typing import Dict, Any, Optional, Generator

from services.permission_service import PermissionService
from services.llm_service import LLMService
from services.rag_service import RAGService
from context.context_manager import ContextManager
from tools.tool_manager import ToolManager
from services.conversation_service import ConversationSession

logger = logging.getLogger(__name__)

class QueryLoop:
    """查询核心循环，统一处理所有查询请求"""
    
    def __init__(
        self,
        llm_service: LLMService,
        rag_service: RAGService,
        permission_service: PermissionService,
        context_manager: ContextManager,
        tool_manager: ToolManager
    ):
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.permission_service = permission_service
        self.context_manager = context_manager
        self.tool_manager = tool_manager
        
        # 特殊指令处理
        self.special_commands = {
            "/update_prompt": self._handle_update_prompt,
        }

    def execute(
        self,
        user_input: str,
        session: ConversationSession,
        stream: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行查询核心流程
        :param user_input: 用户输入
        :param session: 用户会话对象
        :param stream: 是否流式输出
        :return: 统一格式的查询结果
        """
        # 1. 预处理：检查特殊指令
        special_result = self._check_special_commands(user_input)
        if special_result:
            return special_result
            
        # 2. 权限校验
        pass_result, permission_msg = self.permission_service.check_permission(user_input)
        if pass_result is False:
            return {
                "success": False,
                "answer": f"❌ 权限校验失败：{permission_msg}",
                "source": "permission.deny",
                "has_context": False,
                "rag_confidence": 0.0,
                "save_session": False
            }
        elif pass_result is None:
            return {
                "success": False,
                "answer": f"⚠️ {permission_msg}",
                "source": "permission.confirm_required",
                "has_context": False,
                "rag_confidence": 0.0,
                "save_session": False
            }
            
        # 3. 添加用户消息到会话
        session.add_user_message(user_input)
        
        # 4. 工具匹配与调用
        tool_result = self._try_invoke_tools(user_input, session)
        if tool_result:
            return tool_result
            
        # 5. RAG检索
        context = ""
        rag_result = None
        if self.rag_service.is_available:
            try:
                rag_result = self.rag_service.search(user_input)
                if rag_result:
                    context = rag_result.get("answer", "")
            except Exception as e:
                logger.error(f"RAG检索失败: {e}")
                
        # 6. 构建上下文消息
        messages = self.context_manager.build_messages(
            system_prompt=self.context_manager.get_system_prompt(),
            history=session.get_messages_for_api()[:-1],  # 排除当前用户消息，我们会手动拼接RAG
            user_input=user_input,
            context=context
        )
        
        # 7. 调用LLM生成回复，优先判断是否需要工具调用
        answer = None
        if self.llm_service.is_initialized:
            # 先获取所有工具的schema，用于Function Calling
            tools_schema = self._get_tools_schema()
            
            if tools_schema and not stream:  # 工具调用使用非流式
                # 第一次调用LLM，判断是否需要调用工具
                llm_response = self.llm_service.chat_completion(
                    messages, 
                    stream=False,
                    tools=tools_schema,
                    tool_choice="auto"
                )
                
                # 检查是否是工具调用响应
                if isinstance(llm_response, dict) and "tool_calls" in llm_response.get("choices", [{}])[0].get("message", {}):
                    # 处理工具调用
                    tool_call = llm_response["choices"][0]["message"]["tool_calls"][0]
                    tool_name = tool_call["function"]["name"]
                    tool_params = json.loads(tool_call["function"]["arguments"])
                    
                    # 找到对应的工具并执行
                    tool = self.tool_manager.get_tool(tool_name)
                    if tool:
                        try:
                            execute_result = tool.execute(tool_params)
                            return {
                                "success": execute_result.get("success", False),
                                "answer": execute_result.get("message", str(execute_result)),
                                "source": f"tool.{tool.tool_id}",
                                "has_context": False,
                                "tool_result": execute_result,
                                "assistant_message": execute_result.get("message", str(execute_result)),
                                "save_session": True
                            }
                        except Exception as e:
                            logger.error(f"工具调用失败: {e}")
                            answer = f"❌ 工具执行失败：{str(e)}"
                else:
                    # 不是工具调用，使用正常响应
                    answer = llm_response
            else:
                # 流式响应或无工具，正常调用
                answer = self.llm_service.chat_completion(messages, stream=stream)
            
        # 8. 处理结果
        if answer:
            result = {
                "success": True,
                "answer": answer,
                "is_stream": stream,
                "session": session,
                "has_context": bool(context),
                "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
                "rag_sources": rag_result.get("sources", []) if rag_result else [],
                "rag_type": rag_result.get("type", "unknown") if rag_result else "unknown",
                "source": "llm.rag" if context else "llm.only",
                "save_session": False  # 流式响应需要调用方迭代完成后手动保存
            }
            
            # 非流式响应直接保存会话
            if not stream and not isinstance(answer, (Generator, types.GeneratorType)):
                result["assistant_message"] = answer
                result["save_session"] = True
                
            return result
            
        # 9. 降级回复：LLM不可用时使用RAG结果
        fallback = self._get_fallback_response(context)
        return {
            "success": bool(context),
            "answer": fallback,
            "has_context": bool(context),
            "rag_confidence": rag_result.get("confidence", 0) if rag_result else 0,
            "rag_sources": rag_result.get("sources", []) if rag_result else [],
            "rag_type": rag_result.get("type", "unknown") if rag_result else "unknown",
            "source": "rag.only" if context else "fallback",
            "assistant_message": fallback,
            "save_session": True
        }

    def _check_special_commands(self, user_input: str) -> Optional[Dict[str, Any]]:
        """检查并处理特殊指令"""
        cmd = user_input.strip()
        if cmd in self.special_commands:
            return self.special_commands[cmd]()
        return None

    def _handle_update_prompt(self) -> Dict[str, Any]:
        """处理更新提示词指令"""
        if self.context_manager.reload_system_prompt():
            return {
                "success": True,
                "answer": "✅ 系统指令已刷新！现在我已加载最新的 custom_rules.md 逻辑。",
                "source": "system.command",
                "has_context": False,
                "save_session": False
            }
        else:
            return {
                "success": False,
                "answer": "❌ 刷新失败，请检查 custom_rules.md 是否存在。",
                "source": "system.command",
                "has_context": False,
                "save_session": False
            }

    def _get_tools_schema(self) -> list[Dict[str, Any]]:
        """获取所有工具的Function Calling Schema"""
        tools = []
        for tool in self.tool_manager.list_tools():
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": tool["parameters"],
                        "required": [k for k, v in tool["parameters"].items() if v.get("required", False)]
                    }
                }
            }
            tools.append(tool_schema)
        return tools

    def _try_invoke_tools(self, user_input: str, session: ConversationSession) -> Optional[Dict[str, Any]]:
        """尝试匹配并调用工具"""
        tool = self.tool_manager.match_tool(user_input)
        if not tool:
            return None
            
        try:
            # 解析意图和参数
            params = tool.parse_intent(user_input, session=session)
            if params is None:
                return None
                
            # 执行工具
            execute_result = tool.execute(params)
            
            return {
                "success": execute_result.get("success", False),
                "answer": execute_result.get("message", str(execute_result)),
                "source": f"tool.{tool.tool_id}",
                "has_context": False,
                "tool_result": execute_result,
                "assistant_message": execute_result.get("message", str(execute_result)),
                "save_session": True
            }
        except Exception as e:
            logger.error(f"工具调用失败: {e}")
            return {
                "success": False,
                "answer": f"❌ 工具执行失败：{str(e)}",
                "source": f"tool.{tool.tool_id}.error",
                "has_context": False,
                "save_session": False
            }

    def _get_fallback_response(self, context: str) -> str:
        """生成降级回复"""
        if context:
            return f"根据知识库信息：\n\n{context[:500]}..."
        return "AI 服务暂时不可用，请稍后再试。"
