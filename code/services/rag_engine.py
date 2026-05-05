"""
RAG 引擎：负责知识库的加载、嵌入和检索
针对团队协作进行了接口标准化
"""
import warnings
import os
warnings.filterwarnings("ignore") 
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
import glob
import json
from typing import List, Tuple, Optional, Dict, Any
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")

# --- rag_engine.py 顶部修改 ---


import glob
# ... 后续 import 不变

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

try:
    import chromadb
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_community.document_loaders import (
        TextLoader,
        UnstructuredMarkdownLoader,
        PyPDFLoader,
    )
    HAS_DEPS = True
except ImportError as e:
    print(f"RAG 依赖加载失败：{e}") # 添加这一行
    raise e # 改成直接抛出原汁原味的错误

class RAGEngine:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, "..", "data")
        self.vector_db_dir = os.path.join(current_dir, "..", "vector_db")
        self.embeddings: Optional[Any] = None
        self.vectorstore: Optional[Any] = None
        
        # if not HAS_DEPS:
        #     raise ImportError("缺少必要依赖：pip install langchain-community chromadb sentence-transformers pypdf")

        self._init_embeddings()
        

        # 自动初始化：如果库存在就加载，不存在就尝试构建
        if os.path.exists(self.vector_db_dir) and os.listdir(self.vector_db_dir):
            self._load_vectorstore()
        else:
            print("首次运行，正在构建向量数据库...")
            self.build_vectorstore()

    def _init_embeddings(self):
        # 针对 M4/M5 芯片，虽然使用 CPU，但确保模型轻量
        model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs={'normalize_embeddings': False}
        )

    def _load_vectorstore(self):
        self.vectorstore = Chroma(
            persist_directory=self.vector_db_dir,
            embedding_function=self.embeddings
        )

    # --- C板块核心接口：为A板块提供的标准问答接口 ---
    def search(
        self,
        query: str,
        k: int = 5,
        confidence_threshold: float = 0.65,
        return_format: str = "structured"
    ) -> dict:
        """
        统一检索入口

        Args:
            query: 查询文本
            k: 返回结果数量
            confidence_threshold: 置信度阈值
            return_format:
                - "structured": 返回完整结构化字典
                - "simple": 返回 (内容, 得分) 列表
                - "text": 返回纯文本答案

        Returns:
            根据 return_format 返回对应格式的结果
        """


        if not self.vectorstore:
            structured_result = {
                "answer": "知识库未初始化",
                "confidence": 0.0,
                "sources": [],
                "type": "error",
                "timestamp": self._get_timestamp(),
                "version": "1.0"
            }
            return self._format_result(structured_result, return_format)

        try:
            # 使用带分数的搜索，用于置信度过滤
            results = self.vectorstore.similarity_search_with_score(query, k=k*2)  # 多取一些用于过滤

            if not results:
                structured_result = {
                    "answer": "在知识库中未找到相关信息",
                    "confidence": 0.0,
                    "sources": [],
                    "type": "unknown",
                    "timestamp": self._get_timestamp(),
                    "version": "1.0"
                }
                return self._format_result(structured_result, return_format)

            # 过滤低置信度结果
            filtered_results = [(doc, score) for doc, score in results if score >= confidence_threshold]

            if not filtered_results:
                # 如果没有高置信度结果，返回最高分结果但标记低置信度
                best_doc, best_score = results[0]
                structured_result = {
                    "answer": f"未找到高度相关信息。最相关的内容：{best_doc.page_content[:100]}...",
                    "confidence": best_score,
                    "sources": [{"file": best_doc.metadata.get('source', 'unknown'), "score": best_score}],
                    "type": self._classify_query_type(query),
                    "timestamp": self._get_timestamp(),
                    "version": "1.0"
                }
                return self._format_result(structured_result, return_format)

            # 只取前k个结果
            filtered_results = filtered_results[:k]

            # 合并内容，优先使用高置信度内容
            context_parts = []
            sources = []
            total_score = 0

            for i, (doc, score) in enumerate(filtered_results):
                # 清洗检索内容，去除冗余信息
                cleaned_content = self._clean_retrieved_content(doc.page_content, query)
                context_parts.append(cleaned_content)
                sources.append({
                    "file": doc.metadata.get('source', 'unknown'),
                    "score": float(score),
                    "excerpt": cleaned_content[:150] + ("..." if len(cleaned_content) > 150 else "")
                })
                total_score += score

            avg_confidence = total_score / len(filtered_results)

            # 生成精简回答，根据查询类型优化格式
            raw_context = "\n".join(context_parts)
            simplified_answer = self._generate_answer(raw_context, query)

            structured_result = {
                "answer": simplified_answer,
                "confidence": avg_confidence,
                "sources": sources,
                "type": self._classify_query_type(query),
                "timestamp": self._get_timestamp(),
                "version": "1.0"
            }
            return self._format_result(structured_result, return_format)

        except Exception as e:
            structured_result = {
                "answer": f"检索出错: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "type": "error",
                "timestamp": self._get_timestamp(),
                "version": "1.0"
            }
            return self._format_result(structured_result, return_format)

    # --- 辅助方法 ---


    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _classify_query_type(self, query: str) -> str:
        """分类查询类型"""
        query_lower = query.lower()
        concept_keywords = ["什么是", "定义", "解释", "概念", "meaning", "definition"]
        technique_keywords = ["如何", "怎么", "步骤", "方法", "技巧", "how to", "technique"]
        troubleshooting_keywords = ["问题", "错误", "故障", "解决", "修复", "为什么", "problem", "error", "fix"]

        if any(kw in query_lower for kw in troubleshooting_keywords):
            return "troubleshooting"
        elif any(kw in query_lower for kw in technique_keywords):
            return "technique"
        elif any(kw in query_lower for kw in concept_keywords):
            return "concept"
        else:
            return "general"

    def _format_result(self, structured_result: dict, return_format: str) -> Any:
        """
        根据return_format格式化结果

        Args:
            structured_result: 结构化结果字典
            return_format: "structured"|"simple"|"text"

        Returns:
            格式化后的结果
        """
        if return_format == "structured":
            return structured_result
        elif return_format == "simple":
            # 返回 (内容, 得分) 列表
            result_list = [
                (structured_result["answer"], structured_result["confidence"])
            ]
            # 添加来源信息
            for source in structured_result.get("sources", []):
                result_list.append((source.get("file", "unknown"), source.get("score", 0.0)))
            return result_list
        elif return_format == "text":
            return structured_result.get("answer", "")
        else:
            # 默认返回结构化格式
            return structured_result

    def _clean_retrieved_content(self, content: str, query: str) -> str:
        """
        清洗检索内容，去除冗余信息

        Args:
            content: 原始检索内容
            query: 用户查询

        Returns:
            清洗后的内容
        """
        # 移除常见的AI套话和冗余解释
        redundant_patterns = [
            "在音频处理中，",
            "通常情况下，",
            "一般来说，",
            "需要注意的是，",
            "简单来说，",
            "具体而言，",
            "总而言之，",
            "综上所述，"
        ]

        cleaned = content
        for pattern in redundant_patterns:
            cleaned = cleaned.replace(pattern, "")

        # 如果内容以"什么是"开头，提取定义部分
        if "什么是" in query and "：" in cleaned:
            # 提取冒号后的定义部分
            parts = cleaned.split("：", 1)
            if len(parts) > 1:
                cleaned = parts[1].strip()

        # 提取参数模式：数字+单位（如-20dB, 15ms, 2.5:1）
        import re
        param_pattern = r'(-?\d+(?:\.\d+)?)\s*(?:dB|ms|:1|Hz|kHz|%)'
        params = re.findall(param_pattern, cleaned)
        if params and "参数" in query or "设置" in query:
            # 如果是参数查询，优先返回参数
            return " ".join([f"{param}" for param in params])

        # 移除多余的空格和换行
        cleaned = " ".join(cleaned.split())

        return cleaned[:500]  # 限制长度

    def _generate_answer(self, context: str, query: str) -> str:
        """
        根据上下文和查询生成精简回答

        Args:
            context: 检索到的上下文
            query: 用户查询

        Returns:
            精简回答
        """
        query_type = self._classify_query_type(query)

        if query_type == "concept":
            # 概念查询：提取第一句定义
            sentences = context.split('。')
            if sentences:
                return sentences[0].strip() + "。"

        elif query_type == "technique":
            # 技术查询：提取步骤或参数
            lines = context.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ["步骤", "方法", "参数", "设置"]):
                    return line.strip()

        elif query_type == "troubleshooting":
            # 问题解决：提取解决方案
            lines = context.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ["解决", "修复", "检查", "调整"]):
                    return line.strip()

        # 默认：取第一段相关内容
        paragraphs = context.split('\n\n')
        for para in paragraphs:
            if len(para.strip()) > 30:
                return para.strip()[:200] + ("..." if len(para.strip()) > 200 else "")

        return context[:150] + ("..." if len(context) > 150 else "")

    def _summarize_context(self, context: str, query: str) -> str:
        """
        [已弃用] 简化检索到的上下文，生成初步回答
        使用 _generate_answer(context, query) 代替
        后续由main.py的AI进一步优化
        """
        import warnings
        warnings.warn(
            "_summarize_context 已弃用，请使用 _generate_answer",
            DeprecationWarning,
            stacklevel=2
        )
        return self._generate_answer(context, query)

    def check_health(self) -> dict:
        """
        检查RAG引擎健康状态
        返回: {"doc_count": int, "index_status": str, "version": str}
        """
        try:
            if not self.vectorstore:
                return {"doc_count": 0, "index_status": "not_initialized", "version": "1.0"}

            count = self.vectorstore._collection.count()
            return {
                "doc_count": count,
                "index_status": "healthy" if count > 0 else "empty",
                "version": "1.0",
                "timestamp": self._get_timestamp()
            }
        except Exception as e:
            return {"doc_count": 0, "index_status": f"error: {str(e)}", "version": "1.0"}

    # --- 以下保持你原有的逻辑，但增加了健壮性 ---
    def load_documents(self) -> List:
        documents = []
        # 增加对 Mac 隐藏文件的过滤
        patterns = ["**/*.txt", "**/*.md", "**/*.pdf", "**/*.json"]
        for p in patterns:
            for file_path in glob.glob(os.path.join(self.data_dir, p), recursive=True):
                if ".DS_Store" in file_path: continue
                # 跳过术语表，已单独加载
                if "audio_glossary.json" in file_path or "fallback_knowledge.json" in file_path:
                    continue

                try:
                    if file_path.endswith('.txt'):
                        loader = TextLoader(file_path, encoding='utf-8')
                        documents.extend(loader.load())
                    elif file_path.endswith('.md'):
                        loader = UnstructuredMarkdownLoader(file_path)
                        documents.extend(loader.load())
                    elif file_path.endswith('.pdf'):
                        loader = PyPDFLoader(file_path)
                        documents.extend(loader.load())
                    elif file_path.endswith('.json'):
                        # JSON文件特殊处理
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            # 将JSON内容转换为文本
                            if isinstance(data, dict):
                                json_text = json.dumps(data, ensure_ascii=False, indent=2)
                                from langchain_core.documents import Document
                                doc = Document(
                                    page_content=json_text,
                                    metadata={"source": file_path}
                                )
                                documents.append(doc)
                        except json.JSONDecodeError:
                            print(f"JSON文件解析失败: {file_path}")
                except Exception as e:
                    print(f"跳过损坏文件 {file_path}: {e}")
        return documents

    def build_vectorstore(self):
        docs = self.load_documents()
        if not docs: return
        
        # 针对音频专业知识，调整 chunk_size
        # 概念解释用较小块（300），设计指南用较大块（600）
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        chunks = text_splitter.split_documents(docs)
        
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.vector_db_dir
        )
        print(f"✅ 知识库构建成功！当前索引块数量: {len(chunks)}")

# --- 方便测试使用 ---
if __name__ == "__main__":
    rag = RAGEngine()
    # 模拟队友 A 的调用方式
    context = rag.search("如何进行降噪处理？", return_format="text") 
    print("--- 检索到的背景知识 ---")
    print(context)