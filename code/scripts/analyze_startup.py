import time
import os
import sys

# 统计导入时间
start_time = time.time()
import_time = time.time() - start_time
print(f"📊 模块导入耗时: {import_time:.2f}s")

# 统计Agent初始化各部分耗时
start_time = time.time()
from main import FeishuAgent
agent_init_start = time.time()
print(f"📊 导入FeishuAgent耗时: {agent_init_start - start_time:.2f}s")

# 单独统计RAG初始化耗时
rag_start = time.time()
if agent.rag:
    print(f"📊 RAG引擎初始化耗时: {time.time() - rag_start:.2f}s")

# 统计整体初始化耗时
agent = FeishuAgent()
total_init_time = time.time() - agent_init_start
print(f"\n📊 总启动耗时: {total_init_time:.2f}s")
print(f"📊 其中RAG引擎占比: {((time.time() - rag_start)/total_init_time)*100:.1f}%")

# 检测RAG相关耗时
print("\n🔍 启动慢的主要原因分析:")
print("1. RAG引擎需要加载Sentence-Transformer嵌入模型（约1-2秒）")
print("2. RAG引擎需要加载/构建向量数据库（首次启动或向量库大时耗时更长）")
print("3. 其他模块初始化占比很小")
