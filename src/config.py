"""
应用配置管理
使用Pydantic Settings进行配置验证和管理
"""
from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """应用配置"""
    
    # 基本配置
    APP_NAME: str = Field(default="Guanshan Intelligence System", env="APP_NAME")
    VERSION: str = Field(default="1.0.0", env="VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    WORKERS: int = Field(default=4, env="WORKERS")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # 安全配置
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        env="ALLOWED_ORIGINS"
    )
    
    # MongoDB配置
    MONGODB_URL: str = Field(..., env="MONGODB_URL")
    MONGODB_DB_NAME: str = Field(default="intelligent_system", env="MONGODB_DB_NAME")
    MONGODB_MAX_POOL_SIZE: int = Field(default=100, env="MONGODB_MAX_POOL_SIZE")
    MONGODB_MIN_POOL_SIZE: int = Field(default=10, env="MONGODB_MIN_POOL_SIZE")
    
    # MariaDB配置
    MARIADB_URL: str = Field(..., env="MARIADB_URL")
    MARIADB_POOL_SIZE: int = Field(default=20, env="MARIADB_POOL_SIZE")
    MARIADB_MAX_OVERFLOW: int = Field(default=10, env="MARIADB_MAX_OVERFLOW")
    MARIADB_POOL_TIMEOUT: int = Field(default=30, env="MARIADB_POOL_TIMEOUT")
    
    # Redis配置
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    REDIS_DECODE_RESPONSES: bool = Field(default=True, env="REDIS_DECODE_RESPONSES")
    
    # RabbitMQ配置
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@localhost:5672/", env="RABBITMQ_URL")
    RABBITMQ_EXCHANGE: str = Field(default="intelligent_system", env="RABBITMQ_EXCHANGE")
    RABBITMQ_QUEUE_PREFIX: str = Field(default="is_", env="RABBITMQ_QUEUE_PREFIX")
    
    # Firecrawl配置 - API密钥从环境变量读取，绝不硬编码
    FIRECRAWL_API_KEY: str = Field(..., env="FIRECRAWL_API_KEY")
    FIRECRAWL_BASE_URL: str = Field(default="https://api.firecrawl.dev", env="FIRECRAWL_BASE_URL")
    FIRECRAWL_TIMEOUT: int = Field(default=30, env="FIRECRAWL_TIMEOUT")
    FIRECRAWL_MAX_RETRIES: int = Field(default=3, env="FIRECRAWL_MAX_RETRIES")
    
    # LLM配置
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4", env="OPENAI_MODEL")
    CLAUDE_API_KEY: Optional[str] = Field(default=None, env="CLAUDE_API_KEY")
    CLAUDE_MODEL: str = Field(default="claude-3-opus", env="CLAUDE_MODEL")
    
    # 向量数据库配置
    VECTOR_DB_TYPE: str = Field(default="qdrant", env="VECTOR_DB_TYPE")
    QDRANT_URL: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    QDRANT_API_KEY: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    QDRANT_COLLECTION: str = Field(default="documents", env="QDRANT_COLLECTION")
    
    # RAG配置
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")
    EMBEDDING_DIMENSION: int = Field(default=1536, env="EMBEDDING_DIMENSION")
    CHUNK_SIZE: int = Field(default=1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=200, env="CHUNK_OVERLAP")
    TOP_K_RETRIEVAL: int = Field(default=5, env="TOP_K_RETRIEVAL")
    RERANK_MODEL: Optional[str] = Field(default=None, env="RERANK_MODEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    @validator("FIRECRAWL_API_KEY")
    def validate_api_key(cls, v):
        """验证API密钥格式"""
        if not v or v == "your-firecrawl-api-key-here":
            raise ValueError("请提供有效的Firecrawl API密钥")
        return v


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()