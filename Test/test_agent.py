#!/usr/bin/env python
"""
Feishu Agent 测试脚本
用于验证各个组件的功能
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_imports():
    """测试导入"""
    print("1. 测试导入...")
    try:
        import requests
        from flask import Flask
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.embeddings import HuggingFaceEmbeddings
        from langchain.vectorstores import Chroma
        print("  ✓ 所有依赖导入成功")
        return True
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}")
        print("  请运行: pip install -r requirements.txt")
        return False

def test_env_vars():
    """测试环境变量"""
    print("\n2. 测试环境变量...")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key and deepseek_key != "your_deepseek_api_key_here":
        print("  ✓ DeepSeek API 密钥已设置")
    else:
        print("  ⚠ DeepSeek API 密钥未设置（部分功能受限）")

    feishu_app_id = os.getenv("FEISHU_APP_ID")
    feishu_secret = os.getenv("FEISHU_APP_SECRET")
    if feishu_app_id and feishu_app_id != "your_feishu_app_id":
        print("  ✓ 飞书 App ID 已设置")
    else:
        print("  ⚠ 飞书 App ID 未设置（飞书功能不可用）")

    return True

def test_data_dir():
    """测试数据目录"""
    print("\n3. 测试数据目录...")
    data_dir = "data"
    if os.path.exists(data_dir) and os.listdir(data_dir):
        print(f"  ✓ 数据目录存在，包含 {len(os.listdir(data_dir))} 个文件")
        for f in os.listdir(data_dir):
            print(f"    - {f}")
        return True
    else:
        print("  ⚠ 数据目录为空，请将文档放入 data/ 目录")
        return False

def test_rag_engine():
    """测试 RAG 引擎"""
    print("\n4. 测试 RAG 引擎...")
    try:
        from rag_engine import RAGEngine
        rag = RAGEngine()
        print("  ✓ RAG 引擎初始化成功")

        # 测试构建向量数据库
        print("  构建向量数据库...")
        rag.build_vectorstore(force_rebuild=False)
        print("  ✓ 向量数据库构建/加载成功")

        # 测试查询
        test_query = "什么是人工智能？"
        results = rag.search(test_query, k=2)
        if results:
            print(f"  ✓ 知识库检索成功，找到 {len(results)} 个结果")
            for i, (content, score) in enumerate(results, 1):
                print(f"    结果 {i} (相似度: {score:.3f}): {content[:80]}...")
        else:
            print("  ⚠ 未找到相关结果（知识库可能为空）")

        return True
    except Exception as e:
        print(f"  ✗ RAG 引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_deepseek_api():
    """测试 DeepSeek API"""
    print("\n5. 测试 DeepSeek API...")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key or deepseek_key == "your_deepseek_api_key_here":
        print("  ⚠ DeepSeek API 密钥未设置，跳过测试")
        return None

    try:
        from main import DeepSeekAPI
        api = DeepSeekAPI(deepseek_key)

        messages = [
            {"role": "system", "content": "你是一个有帮助的助手。"},
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ]

        print("  调用 DeepSeek API...")
        response = api.chat_completion(messages, temperature=0.7, max_tokens=100)

        if response:
            print(f"  ✓ DeepSeek API 调用成功")
            print(f"    回复: {response}")
            return True
        else:
            print("  ✗ DeepSeek API 返回空响应")
            return False
    except Exception as e:
        print(f"  ✗ DeepSeek API 测试失败: {e}")
        return False

def test_feishu_agent():
    """测试飞书 Agent"""
    print("\n6. 测试飞书 Agent...")
    try:
        from main import FeishuAgent
        agent = FeishuAgent()
        print("  ✓ Feishu Agent 初始化成功")

        # 测试处理消息
        test_message = "人工智能是什么？"
        print(f"  测试消息处理: '{test_message}'")
        result = agent.process_message(test_message)

        if result.get("success"):
            print(f"  ✓ 消息处理成功")
            print(f"    来源: {result.get('source')}")
            print(f"    使用知识库: {result.get('has_context')}")
            print(f"    回答长度: {len(result.get('answer', ''))} 字符")

            # 显示前100个字符
            answer_preview = result.get('answer', '')[:100]
            if len(result.get('answer', '')) > 100:
                answer_preview += "..."
            print(f"    回答预览: {answer_preview}")

            return True
        else:
            print(f"  ✗ 消息处理失败")
            return False
    except Exception as e:
        print(f"  ✗ Feishu Agent 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("Feishu Agent Demo 测试套件")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("导入测试", test_imports()))
    results.append(("环境变量", test_env_vars()))
    results.append(("数据目录", test_data_dir()))
    results.append(("RAG 引擎", test_rag_engine()))
    results.append(("DeepSeek API", test_deepseek_api()))
    results.append(("飞书 Agent", test_feishu_agent()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)

    passed = 0
    total = len(results)

    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败" if success is False else "⚠ 跳过"
        print(f"{name:20} {status}")
        if success:
            passed += 1

    print(f"\n总计: {passed}/{total} 项测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！Feishu Agent Demo 已准备好运行。")
        print("\n运行以下命令启动:")
        print("  python main.py          # 命令行模式")
        print("  USE_WEBHOOK=true python main.py  # Webhook 模式")
    else:
        print("\n⚠ 部分测试未通过，请检查上述错误信息。")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)