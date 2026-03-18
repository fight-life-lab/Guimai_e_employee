"""Knowledge base builder for processing HR documents."""

import os
from pathlib import Path
from typing import List, Optional

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    CSVLoader,
    DirectoryLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import get_settings


class KnowledgeBuilder:
    """Builder for HR knowledge base."""

    def __init__(self):
        """Initialize the knowledge builder."""
        self.settings = get_settings()
        self.embeddings = None
        self.vector_store = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", "。", "；", " ", ""],
        )

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        """Get or create embeddings model."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.settings.embedding_model,
                model_kwargs={"device": self.settings.embedding_device},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self.embeddings

    def load_csv(self, file_path: str) -> List[Document]:
        """Load documents from CSV file.

        Args:
            file_path: Path to CSV file

        Returns:
            List of documents
        """
        loader = CSVLoader(
            file_path=file_path,
            encoding="utf-8",
            source_column="name" if "name" in self._get_csv_columns(file_path) else None,
        )
        documents = loader.load()

        # Add metadata
        for doc in documents:
            doc.metadata["source_type"] = "csv"
            doc.metadata["file_name"] = os.path.basename(file_path)

        return documents

    def load_markdown(self, file_path: str) -> List[Document]:
        """Load documents from Markdown file.

        Args:
            file_path: Path to Markdown file

        Returns:
            List of documents
        """
        loader = UnstructuredMarkdownLoader(file_path, encoding="utf-8")
        documents = loader.load()

        # Add metadata
        for doc in documents:
            doc.metadata["source_type"] = "markdown"
            doc.metadata["file_name"] = os.path.basename(file_path)

        return documents

    def load_text(self, file_path: str) -> List[Document]:
        """Load documents from text file.

        Args:
            file_path: Path to text file

        Returns:
            List of documents
        """
        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()

        # Add metadata
        for doc in documents:
            doc.metadata["source_type"] = "text"
            doc.metadata["file_name"] = os.path.basename(file_path)

        return documents

    def load_directory(
        self, directory_path: str, glob_pattern: str = "**/*"
    ) -> List[Document]:
        """Load all documents from a directory.

        Args:
            directory_path: Path to directory
            glob_pattern: Glob pattern for file matching

        Returns:
            List of documents
        """
        documents = []
        path = Path(directory_path)

        for file_path in path.glob(glob_pattern):
            if file_path.is_file():
                try:
                    if file_path.suffix.lower() == ".csv":
                        documents.extend(self.load_csv(str(file_path)))
                    elif file_path.suffix.lower() in [".md", ".markdown"]:
                        documents.extend(self.load_markdown(str(file_path)))
                    elif file_path.suffix.lower() in [".txt", ".text"]:
                        documents.extend(self.load_text(str(file_path)))
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")

        return documents

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks.

        Args:
            documents: List of documents to split

        Returns:
            List of document chunks
        """
        return self.text_splitter.split_documents(documents)

    def build_vector_store(
        self,
        documents: List[Document],
        persist_directory: Optional[str] = None,
    ) -> Chroma:
        """Build vector store from documents.

        Args:
            documents: List of documents
            persist_directory: Directory to persist vector store

        Returns:
            Chroma vector store
        """
        if persist_directory is None:
            persist_directory = self.settings.chroma_db_path

        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)

        # Create vector store
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self._get_embeddings(),
            persist_directory=persist_directory,
            collection_name=self.settings.chroma_collection_name,
        )

        # Persist vector store
        vector_store.persist()

        self.vector_store = vector_store
        return vector_store

    def load_vector_store(
        self, persist_directory: Optional[str] = None
    ) -> Optional[Chroma]:
        """Load existing vector store.

        Args:
            persist_directory: Directory where vector store is persisted

        Returns:
            Chroma vector store or None if not exists
        """
        if persist_directory is None:
            persist_directory = self.settings.chroma_db_path

        if not os.path.exists(persist_directory):
            return None

        try:
            vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=self._get_embeddings(),
                collection_name=self.settings.chroma_collection_name,
            )
            self.vector_store = vector_store
            return vector_store
        except Exception as e:
            print(f"Error loading vector store: {e}")
            return None

    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to existing vector store.

        Args:
            documents: List of documents to add
        """
        if self.vector_store is None:
            self.load_vector_store()

        if self.vector_store is None:
            raise ValueError("Vector store not initialized. Call build_vector_store first.")

        self.vector_store.add_documents(documents)
        self.vector_store.persist()

    def search(self, query: str, k: int = 5) -> List[Document]:
        """Search vector store.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant documents
        """
        if self.vector_store is None:
            self.load_vector_store()

        if self.vector_store is None:
            raise ValueError("Vector store not initialized.")

        return self.vector_store.similarity_search(query, k=k)

    def _get_csv_columns(self, file_path: str) -> List[str]:
        """Get column names from CSV file."""
        import csv

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return reader.fieldnames or []


def build_knowledge_base(
    data_dir: str = "./data/documents",
    persist_dir: Optional[str] = None,
) -> Chroma:
    """Build knowledge base from data directory.

    Args:
        data_dir: Directory containing documents
        persist_dir: Directory to persist vector store

    Returns:
        Chroma vector store
    """
    builder = KnowledgeBuilder()

    # Load documents
    print(f"Loading documents from {data_dir}...")
    documents = builder.load_directory(data_dir)
    print(f"Loaded {len(documents)} documents")

    if not documents:
        raise ValueError(f"No documents found in {data_dir}")

    # Split documents
    print("Splitting documents...")
    chunks = builder.split_documents(documents)
    print(f"Created {len(chunks)} chunks")

    # Build vector store
    print("Building vector store...")
    vector_store = builder.build_vector_store(chunks, persist_dir)
    print("Knowledge base built successfully!")

    return vector_store


if __name__ == "__main__":
    # Example usage
    build_knowledge_base()
