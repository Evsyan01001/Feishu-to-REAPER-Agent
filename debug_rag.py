import sys
import os

# 确保能找到当前目录下的文件
sys.path.append(os.getcwd())

print("--- 开始深度诊断 ---")
try:
    from rag_engine import RAGEngine
    print("正在尝试实例化 RAGEngine...")
    rag = RAGEngine()
    print("✅ RAG 引擎初始化完全正常！")
except Exception:
    import traceback
    print("❌ 捕获到真实错误堆栈：")
    traceback.print_exc()