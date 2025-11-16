"""
NL Search 功能配置

设计说明:
- 使用 Pydantic Settings 进行配置管理
- 支持环境变量覆盖
- 功能开关默认关闭
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class NLSearchConfig(BaseSettings):
    """NL Search 功能配置

    所有配置项支持环境变量覆盖，使用 NL_SEARCH_ 前缀。

    Example:
        # .env 文件
        NL_SEARCH_ENABLED=true
        NL_SEARCH_LLM_API_KEY=sk-xxx
        NL_SEARCH_GPT5_SEARCH_API_KEY=xxx
    """

    # ==================== 功能开关 ====================

    enabled: bool = Field(
        default=False,
        description="功能开关 (默认关闭)",
        env="NL_SEARCH_ENABLED"
    )

    # ==================== LLM 配置 ====================

    llm_api_key: Optional[str] = Field(
        default=None,
        description="LLM API Key (OpenAI/Claude)",
        env="NL_SEARCH_LLM_API_KEY"
    )

    llm_model: str = Field(
        default="gpt-4",
        description="LLM 模型名称",
        env="NL_SEARCH_LLM_MODEL"
    )

    llm_temperature: float = Field(
        default=0.7,
        description="LLM 温度参数 (0.0-2.0)",
        ge=0.0,
        le=2.0,
        env="NL_SEARCH_LLM_TEMPERATURE"
    )

    llm_max_tokens: int = Field(
        default=500,
        description="LLM 最大 token 数",
        ge=1,
        le=4096,
        env="NL_SEARCH_LLM_MAX_TOKENS"
    )

    # ==================== GPT-5 搜索配置 ====================

    gpt5_search_api_key: Optional[str] = Field(
        default=None,
        description="GPT-5 Search API Key",
        env="NL_SEARCH_GPT5_SEARCH_API_KEY"
    )

    gpt5_max_results: int = Field(
        default=10,
        description="GPT-5 搜索最大结果数",
        ge=1,
        le=50,
        env="NL_SEARCH_GPT5_MAX_RESULTS"
    )

    # ==================== Scrape 配置 ====================

    scrape_timeout: int = Field(
        default=30,
        description="抓取超时时间(秒)",
        ge=5,
        le=300,
        env="NL_SEARCH_SCRAPE_TIMEOUT"
    )

    scrape_max_concurrent: int = Field(
        default=3,
        description="最大并发抓取数",
        ge=1,
        le=10,
        env="NL_SEARCH_SCRAPE_MAX_CONCURRENT"
    )

    # ==================== 业务配置 ====================

    max_results_per_query: int = Field(
        default=20,
        description="每次查询最大结果数",
        ge=1,
        le=100,
        env="NL_SEARCH_MAX_RESULTS_PER_QUERY"
    )

    enable_auto_scrape: bool = Field(
        default=True,
        description="是否自动抓取内容",
        env="NL_SEARCH_ENABLE_AUTO_SCRAPE"
    )

    # ==================== 性能配置 ====================

    query_timeout: int = Field(
        default=30,
        description="查询超时时间(秒)",
        ge=5,
        le=300,
        env="NL_SEARCH_QUERY_TIMEOUT"
    )

    cache_ttl: int = Field(
        default=3600,
        description="缓存过期时间(秒)",
        ge=0,
        le=86400,
        env="NL_SEARCH_CACHE_TTL"
    )

    class Config:
        """Pydantic Settings 配置"""
        env_prefix = "NL_SEARCH_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量

    def is_enabled(self) -> bool:
        """检查功能是否启用"""
        return self.enabled

    def validate_llm_config(self) -> bool:
        """验证 LLM 配置是否完整"""
        return self.llm_api_key is not None and len(self.llm_api_key) > 0

    def validate_gpt5_config(self) -> bool:
        """验证 GPT-5 配置是否完整"""
        return self.gpt5_search_api_key is not None and len(self.gpt5_search_api_key) > 0

    def __repr__(self) -> str:
        """字符串表示（隐藏敏感信息）"""
        return (
            f"<NLSearchConfig("
            f"enabled={self.enabled}, "
            f"llm_model={self.llm_model}, "
            f"max_results={self.max_results_per_query})>"
        )


# 全局配置实例
nl_search_config = NLSearchConfig()
