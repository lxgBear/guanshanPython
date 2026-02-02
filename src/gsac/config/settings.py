"""
gs-ai-crawl 配置管理

使用 pydantic-settings 管理配置，支持环境变量和.env文件
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置 - 支持环境变量和.env文件"""

    model_config = SettingsConfigDict(
        env_prefix="GS_CRAWL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ===== Firecrawl配置 =====
    firecrawl_api_key: str = Field(
        default="",
        description="Firecrawl API密钥",
    )
    firecrawl_base_url: str = Field(
        default="https://api.firecrawl.dev",
        description="Firecrawl API地址",
    )

    # ===== LLM配置 =====
    llm_provider: Literal["openai", "anthropic", "ollama", "custom_claude"] = Field(
        default="openai",
        description="LLM提供者 (openai, anthropic, ollama, custom_claude)",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM模型名称",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="LLM API密钥(可从环境变量读取)",
    )
    llm_base_url: str | None = Field(
        default=None,
        description="LLM API地址(用于Ollama或代理)",
    )
    llm_temperature: float = Field(
        default=0.1,
        ge=0,
        le=2,
        description="LLM温度参数",
    )

    # ===== 自定义Claude API配置 =====
    custom_claude_base_url: str = Field(
        default="https://api.codeable.icu",
        description="自定义Claude API基础URL",
    )
    custom_claude_api_key: str | None = Field(
        default=None,
        description="自定义Claude API密钥",
    )
    custom_claude_model: str = Field(
        default="claude-opus-4-5-20251101",
        description="自定义Claude模型名称",
    )

    # ===== 搜索默认配置 =====
    default_max_keywords: int = Field(
        default=5,
        ge=1,
        le=20,
        description="默认最大关键词数量",
    )
    default_max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="每个关键词的默认最大结果数",
    )
    default_timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="默认超时时间(秒)",
    )

    # ===== 并发配置 =====
    max_concurrent_searches: int = Field(
        default=5,
        ge=1,
        le=20,
        description="最大并发搜索数",
    )
    max_concurrent_scrapes: int = Field(
        default=3,
        ge=1,
        le=10,
        description="最大并发抓取数",
    )

    # ===== 日志配置 =====
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="日志级别",
    )
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


# 便捷访问
settings = get_settings()
