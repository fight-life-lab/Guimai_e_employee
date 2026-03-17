"""简化版知识库模块 - 核心功能：存数据 + 查询

使用示例:
    from app.knowledge.simple_kb import SimpleKnowledgeBase

    # 初始化知识库
    kb = SimpleKnowledgeBase()

    # 方式1: 从文件加载数据
    kb.add_from_file("./data/employees.csv")
    kb.add_from_file("./data/policy.md")

    # 方式2: 直接添加文本
    kb.add_text("张三的合同将于2025年6月30日到期", source="合同信息")

    # 查询
    results = kb.search("谁的合同要到期了？", top_k=3)
    for doc in results:
        print(doc.page_content)
"""

import os
from pathlib import Path
from typing import List, Optional, Union

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


class SimpleKnowledgeBase:
    """简化版知识库 - 支持存储和查询功能"""

    def __init__(
        self,
        db_path: str = "./data/chroma_db",
        collection_name: str = "hr_knowledge",
        embedding_model: str = "BAAI/bge-base-zh-v1.5",
        device: str = "cpu",
    ):
        """初始化知识库

        Args:
            db_path: 向量数据库保存路径
            collection_name: 集合名称
            embedding_model: Embedding模型名称
            device: 运行设备 (cpu/cuda)
        """
        self.db_path = db_path
        self.collection_name = collection_name

        # 初始化 Embedding 模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )

        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", " ", ""],
        )

        # 加载或创建向量数据库
        self.vector_store = self._load_or_create_store()

    def _load_or_create_store(self) -> Chroma:
        """加载现有数据库或创建新的"""
        os.makedirs(self.db_path, exist_ok=True)

        if os.path.exists(os.path.join(self.db_path, "chroma.sqlite3")):
            # 加载现有数据库
            return Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings,
                collection_name=self.collection_name,
            )
        else:
            # 创建空数据库
            return Chroma(
                persist_directory=self.db_path,
                embedding_function=self.embeddings,
                collection_name=self.collection_name,
            )

    def add_from_file(self, file_path: str) -> int:
        """从文件添加数据到知识库

        Args:
            file_path: 文件路径 (支持 csv, md, txt)

        Returns:
            添加的文档数量
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 根据文件类型选择加载器
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            loader = CSVLoader(file_path=str(file_path), encoding="utf-8")
        elif suffix in [".md", ".markdown"]:
            loader = UnstructuredMarkdownLoader(str(file_path), encoding="utf-8")
        elif suffix in [".txt", ".text"]:
            loader = TextLoader(str(file_path), encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

        # 加载文档
        documents = loader.load()

        # 添加元数据
        for doc in documents:
            doc.metadata["source_file"] = file_path.name
            doc.metadata["source_type"] = suffix.lstrip(".")

        # 分割长文档
        chunks = self.text_splitter.split_documents(documents)

        # 添加到向量库
        self.vector_store.add_documents(chunks)
        self.vector_store.persist()

        return len(chunks)

    def add_from_directory(self, dir_path: str, pattern: str = "**/*") -> int:
        """从目录批量添加文件

        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式

        Returns:
            添加的总文档数量
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"目录不存在: {dir_path}")

        total_chunks = 0
        supported_exts = {".csv", ".md", ".markdown", ".txt", ".text"}

        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in supported_exts:
                try:
                    chunks = self.add_from_file(str(file_path))
                    total_chunks += chunks
                    print(f"✓ 已加载: {file_path.name} ({chunks} 片段)")
                except Exception as e:
                    print(f"✗ 加载失败: {file_path.name} - {e}")

        return total_chunks

    def add_text(self, text: str, source: str = "manual", metadata: Optional[dict] = None) -> None:
        """直接添加文本到知识库

        Args:
            text: 文本内容
            source: 来源标识
            metadata: 额外元数据
        """
        doc = Document(
            page_content=text,
            metadata={"source": source, **(metadata or {})},
        )

        # 分割长文本
        chunks = self.text_splitter.split_documents([doc])

        # 添加到向量库
        self.vector_store.add_documents(chunks)
        self.vector_store.persist()

    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """搜索知识库

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            相关文档列表
        """
        return self.vector_store.similarity_search(query, k=top_k)

    def search_with_score(self, query: str, top_k: int = 5) -> List[tuple]:
        """带相似度分数的搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            (文档, 相似度分数) 元组列表，分数越低越相似
        """
        return self.vector_store.similarity_search_with_score(query, k=top_k)

    def delete_collection(self) -> None:
        """删除整个集合（清空知识库）"""
        self.vector_store.delete_collection()
        self.vector_store = self._load_or_create_store()

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        count = self.vector_store._collection.count()
        return {
            "total_documents": count,
            "db_path": self.db_path,
            "collection_name": self.collection_name,
        }


# 便捷函数
def quick_search(query: str, db_path: str = "./data/chroma_db", top_k: int = 5) -> List[Document]:
    """快速搜索已有知识库（无需初始化）"""
    kb = SimpleKnowledgeBase(db_path=db_path)
    return kb.search(query, top_k=top_k)
