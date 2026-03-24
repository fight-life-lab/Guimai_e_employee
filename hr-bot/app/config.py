"""Application configuration."""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Base directory
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Application
    app_name: str = "hr-bot"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 3111  # 使用端口3111

    # LLM Settings - 本地vLLM部署的Qwen模型
    vllm_host: str = "localhost"  # 使用localhost连接vLLM
    vllm_port: int = 8002  # vLLM服务端口
    vllm_model: str = "qwen-14b-chat"  # 本地部署的模型名称
    openai_api_base: str = "http://localhost:8002/v1"  # vLLM OpenAI兼容API
    openai_api_key: str = "not-needed"  # 本地模型不需要API key

    # Remote LLM Settings - 远程大模型API (用于处理长文本)
    remote_llm_url: str = "http://180.97.200.118:30071/v1/chat/completions"
    remote_llm_api_key: str = "z3oK7bN9xPqW2mT8rYvL5tF1cJ4hD6gA0eS2uI3nQk"
    remote_llm_model: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"

    # Embedding Model
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    embedding_device: str = "cuda"

    # Vector Database - 本地ChromaDB
    chroma_db_path: str = "./data/chroma_db"
    chroma_collection_name: str = "hr_knowledge"
    chroma_host: str = "121.229.172.161"
    chroma_port: int = 8001

    # MySQL Database - 本地Docker部署，数据不出域
    mysql_host: str = "121.229.172.161"
    mysql_port: int = 3306
    mysql_database: str = "hr_employee_db"
    mysql_user: str = "hr_user"
    mysql_password: str = "hr_password"

    # Feishu Webhook
    feishu_webhook_url: Optional[str] = None
    feishu_webhook_secret: Optional[str] = None

    # Alert Settings
    contract_alert_days: int = 30
    performance_threshold: float = 60.0

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/hr-bot.log"
    
    # Data Security - 数据不出域配置
    data_local_only: bool = True  # 强制所有数据在本地处理
    allow_external_api: bool = False  # 禁止调用外部API

    @property
    def vllm_url(self) -> str:
        """Get vLLM service URL."""
        return f"http://{self.vllm_host}:{self.vllm_port}"
    
    @property
    def chroma_url(self) -> str:
        """Get ChromaDB service URL."""
        return f"http://{self.chroma_host}:{self.chroma_port}"
    
    @property
    def database_url(self) -> str:
        """Get MySQL database URL."""
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    @property
    def is_feishu_configured(self) -> bool:
        """Check if Feishu webhook is configured."""
        return bool(self.feishu_webhook_url and self.feishu_webhook_secret)
    
    @property
    def is_local_model(self) -> bool:
        """确认使用的是本地模型（数据不出域）."""
        # 检查API base是否指向本地/内网地址
        local_hosts = ['localhost', '127.0.0.1', '192.168.', '10.', '172.16.', '121.229.172.161']
        return any(host in self.openai_api_base for host in local_hosts)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
