"""
REPL 交互模式
交互式多轮对话界面
"""
import sys
import os
import types
from typing import Generator, Any, Dict

class ReplMode:
    def __init__(self, engine, stream: bool = True):
        self.engine = engine
        self.stream = stream
        self.user_id = "cli_user"
        self.running = False
        
        # 特殊指令
        self.commands = {
            "/reset": "重置对话",
            "/clear": "清屏",
            "/help": "显示帮助",
            "/exit": "退出程序",
            "/quit": "退出程序"
        }

    def run(self):
        """启动REPL模式"""
        self.running = True
        self._print_welcome()
        
        while self.running:
            try:
                print("\n请输入问题：")
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                    
                # 处理特殊指令
                if self._handle_command(user_input):
                    continue
                    
                # 处理用户查询
                result = self.engine.query(user_input, user_id=self.user_id, stream=self.stream)
                self._display_result(result)
                
            except KeyboardInterrupt:
                print("\n\n输入 /exit 退出程序")
            except EOFError:
                break
            except Exception as e:
                print(f"\n❌ 发生错误：{e}")
                
        print("\n👋 再见！")

    def _print_welcome(self):
        """打印欢迎信息"""
        print("=" * 60)
        print("🎵 Feishu Agent - 游戏音频剪辑助手 (REPL 模式)")
        print(f"支持指令：{' / '.join(self.commands.keys())}")
        print("=" * 60)

    def _handle_command(self, user_input: str) -> bool:
        """处理特殊指令，返回True表示已处理，不需要继续查询"""
        cmd = user_input.lower()
        
        if cmd in ["/exit", "/quit", "q"]:
            self.running = False
            return True
            
        if cmd == "/reset":
            self.engine.reset_session(self.user_id)
            print("✅ 对话已重置，我们重新开始吧！")
            return True
            
        if cmd == "/clear":
            os.system('clear' if os.name == 'posix' else 'cls')
            return True
            
        if cmd == "/help":
            self._print_help()
            return True
            
        return False

    def _print_help(self):
        """打印帮助信息"""
        print("\n📖 帮助信息：")
        for cmd, desc in self.commands.items():
            print(f"  {cmd:<10} {desc}")
        print("\n其他输入将作为查询内容发送给AI。")

    def _display_result(self, result: Dict[str, Any]):
        """显示查询结果"""
        print("\n" + "─" * 60)
        
        answer = result.get("answer", "")
        if isinstance(answer, (Generator, types.GeneratorType)):
            # 流式输出
            print("AI 回复：", end="", flush=True)
            full_answer = []
            for chunk in answer:
                if chunk:
                    print(chunk, end="", flush=True)
                    full_answer.append(chunk)
            print()
            final_answer = "".join(full_answer)
        else:
            # 非流式输出
            print("AI 回复：")
            print(answer)
            final_answer = answer
            
        # 显示附加信息
        source = result.get("source", "unknown")
        turn_count = result.get("turn_count", 0)
        rag_confidence = result.get("rag_confidence", 0)
        
        print(f"\n来源：{source} | 对话轮次：{turn_count} | RAG置信度：{rag_confidence:.2f}")
        if result.get("has_context"):
            print("✓ 使用了知识库信息")
            
        if result.get("success") is False and result.get("answer"):
            print(f"\n⚠️  {result.get('answer')}")
            
        print("─" * 60)
