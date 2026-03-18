"""Application configuration."""

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

    # Application
    app_name: str = "hr-bot"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM Settings
    vllm_host: str = "localhost"
    vllm_port: int = 8002
    vllm_model: str = "qwen-14b-chat"
    openai_api_base: str = "http://localhost:8002/v1"
    openai_api_key: str = "not-needed"

    # Embedding Model
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    embedding_device: str = "cuda"

    # Vector Database
    chroma_db_path: str = "./data/chroma_db"
    chroma_collection_name: str = "hr_knowledge"

    # MySQL Database
    database_url: str = "mysql+aiomysql://hr_user:hr_password@localhost:3306/hr_employee_db"

    # Feishu Configuration
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_verification_token: Optional[str] = None
    feishu_encrypt_key: Optional[str] = None
    feishu_webhook_url: Optional[str] = None
    feishu_webhook_secret: Optional[str] = None

    # Alert Settings
    contract_alert_days: int = 30
    performance_threshold: float = 60.0

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/hr-bot.log"

    @property
    def vllm_url(self) -> str:
        """Get vLLM service URL."""
        return f"http://{self.vllm_host}:{self.vllm_port}"

    @property
    def is_feishu_configured(self) -> bool:
        """Check if Feishu is configured."""
        return bool(self.feishu_app_id and self.feishu_app_secret)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
