"""
CLI 入口层
支持三种运行模式：
1. REPL交互模式：默认模式，交互式多轮对话
2. 单次查询模式：-p 参数直接执行查询并退出
3. SDK/Bridge模式：提供Python API供其他程序调用
"""
import os
import sys
import argparse
from typing import Optional, Dict, Any

# 导入核心引擎
from engine.query_engine import QueryEngine
from cli.repl import ReplMode
from cli.single_query import SingleQueryMode

def main():
    parser = argparse.ArgumentParser(description="Feishu Agent - 游戏音频剪辑助手")
    parser.add_argument("-p", "--prompt", help="单次查询模式，直接输入查询内容")
    parser.add_argument("--no-stream", action="store_true", help="禁用流式输出")
    parser.add_argument("--config", help="指定配置文件路径")
    parser.add_argument("--reset", action="store_true", help="重置当前会话")
    
    args = parser.parse_args()
    
    # 初始化查询引擎
    engine = QueryEngine(config_path=args.config)
    
    if args.reset:
        engine.reset_session()
        print("✅ 会话已重置")
        return
    
    # 模式路由
    if args.prompt:
        # 单次查询模式
        mode = SingleQueryMode(engine, stream=not args.no_stream)
        mode.run(args.prompt)
    else:
        # REPL交互模式
        mode = ReplMode(engine, stream=not args.no_stream)
        mode.run()

if __name__ == "__main__":
    main()
