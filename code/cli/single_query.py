"""
单次查询模式
支持通过命令行参数直接执行查询并输出结果，适合脚本调用
"""
import sys
import types
from typing import Generator, Any, Dict

class SingleQueryMode:
    def __init__(self, engine, stream: bool = True):
        self.engine = engine
        self.stream = stream
        self.user_id = "cli_single_query"

    def run(self, prompt: str):
        """执行单次查询"""
        try:
            result = self.engine.query(prompt, user_id=self.user_id, stream=self.stream)
            self._output_result(result)
        except Exception as e:
            print(f"❌ 查询失败：{e}", file=sys.stderr)
            sys.exit(1)

    def _output_result(self, result: Dict[str, Any]):
        """输出查询结果"""
        answer = result.get("answer", "")
        
        if isinstance(answer, (Generator, types.GeneratorType)):
            # 流式输出
            full_answer = []
            for chunk in answer:
                if chunk:
                    print(chunk, end="", flush=True)
                    full_answer.append(chunk)
            print()
            final_answer = "".join(full_answer)
        else:
            # 非流式输出
            print(answer)
            final_answer = answer
            
        # 如果有错误，返回非0退出码
        if result.get("success") is False:
            sys.exit(1)
