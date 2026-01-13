"""
NL Search 功能配置

设计说明:
- 使用 Pydantic Settings 进行配置管理
- 支持环境变量覆盖
- 功能开关默认关闭

v2.2.0: 添加可扩展的语言配置架构，支持更多语言选择
"""
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from dataclasses import dataclass


# ==================== 语言配置 ====================

@dataclass(frozen=True)
class LanguageInfo:
    """语言信息元数据

    用于前端展示和语言验证

    Attributes:
        code: ISO 639-1 语言代码 (如 "zh", "en")
        name: 语言英文名称
        native_name: 语言本地名称
        region: 主要使用区域
        firecrawl_supported: Firecrawl API 是否支持该语言
    """
    code: str
    name: str
    native_name: str
    region: str
    firecrawl_supported: bool = True


# 支持的语言列表 (按区域分组，便于前端展示)
# Firecrawl Search API 支持大多数主流语言
SUPPORTED_LANGUAGES: Dict[str, LanguageInfo] = {
    # 东亚语言 (East Asian)
    "zh": LanguageInfo("zh", "Chinese", "中文", "East Asia"),
    "ja": LanguageInfo("ja", "Japanese", "日本語", "East Asia"),
    "ko": LanguageInfo("ko", "Korean", "한국어", "East Asia"),

    # 西欧语言 (Western European)
    "en": LanguageInfo("en", "English", "English", "Global"),
    "de": LanguageInfo("de", "German", "Deutsch", "Western Europe"),
    "fr": LanguageInfo("fr", "French", "Français", "Western Europe"),
    "es": LanguageInfo("es", "Spanish", "Español", "Western Europe"),
    "pt": LanguageInfo("pt", "Portuguese", "Português", "Western Europe"),
    "it": LanguageInfo("it", "Italian", "Italiano", "Western Europe"),
    "nl": LanguageInfo("nl", "Dutch", "Nederlands", "Western Europe"),

    # 东欧语言 (Eastern European)
    "ru": LanguageInfo("ru", "Russian", "Русский", "Eastern Europe"),
    "pl": LanguageInfo("pl", "Polish", "Polski", "Eastern Europe"),
    "uk": LanguageInfo("uk", "Ukrainian", "Українська", "Eastern Europe"),
    "cs": LanguageInfo("cs", "Czech", "Čeština", "Eastern Europe"),

    # 中东语言 (Middle Eastern)
    "ar": LanguageInfo("ar", "Arabic", "العربية", "Middle East"),
    "he": LanguageInfo("he", "Hebrew", "עברית", "Middle East"),
    "tr": LanguageInfo("tr", "Turkish", "Türkçe", "Middle East"),
    "fa": LanguageInfo("fa", "Persian", "فارسی", "Middle East"),

    # 南亚语言 (South Asian)
    "hi": LanguageInfo("hi", "Hindi", "हिन्दी", "South Asia"),
    "bn": LanguageInfo("bn", "Bengali", "বাংলা", "South Asia"),
    "ta": LanguageInfo("ta", "Tamil", "தமிழ்", "South Asia"),

    # 东南亚语言 (Southeast Asian)
    "vi": LanguageInfo("vi", "Vietnamese", "Tiếng Việt", "Southeast Asia"),
    "th": LanguageInfo("th", "Thai", "ไทย", "Southeast Asia"),
    "id": LanguageInfo("id", "Indonesian", "Bahasa Indonesia", "Southeast Asia"),
    "ms": LanguageInfo("ms", "Malay", "Bahasa Melayu", "Southeast Asia"),
    "my": LanguageInfo("my", "Burmese", "မြန်မာ", "Southeast Asia"),

    # 北欧语言 (Nordic)
    "sv": LanguageInfo("sv", "Swedish", "Svenska", "Nordic"),
    "no": LanguageInfo("no", "Norwegian", "Norsk", "Nordic"),
    "da": LanguageInfo("da", "Danish", "Dansk", "Nordic"),
    "fi": LanguageInfo("fi", "Finnish", "Suomi", "Nordic"),
}

# 默认语言列表 (东亚 + 英语 - 适合OSINT情报分析)
DEFAULT_LANGUAGES = ["zh", "en", "ja", "ko"]

# 区域分组 (用于前端分组展示)
LANGUAGE_REGIONS = {
    "East Asia": ["zh", "ja", "ko"],
    "Global": ["en"],
    "Western Europe": ["de", "fr", "es", "pt", "it", "nl"],
    "Eastern Europe": ["ru", "pl", "uk", "cs"],
    "Middle East": ["ar", "he", "tr", "fa"],
    "South Asia": ["hi", "bn", "ta"],
    "Southeast Asia": ["vi", "th", "id", "ms", "my"],
    "Nordic": ["sv", "no", "da", "fi"],
}


def get_supported_language_codes() -> set:
    """获取所有支持的语言代码集合"""
    return set(SUPPORTED_LANGUAGES.keys())


def get_language_info(code: str) -> Optional[LanguageInfo]:
    """获取语言信息"""
    return SUPPORTED_LANGUAGES.get(code)


def is_language_supported(code: str) -> bool:
    """检查语言是否支持"""
    return code in SUPPORTED_LANGUAGES


def get_languages_for_api() -> List[Dict[str, Any]]:
    """获取语言列表（用于API响应）

    Returns:
        格式化的语言列表，包含分组信息
    """
    result = []
    for code, info in SUPPORTED_LANGUAGES.items():
        result.append({
            "code": info.code,
            "name": info.name,
            "native_name": info.native_name,
            "region": info.region,
            "is_default": code in DEFAULT_LANGUAGES
        })
    return result


def get_languages_by_region() -> Dict[str, List[Dict[str, str]]]:
    """按区域分组获取语言列表

    Returns:
        按区域分组的语言字典
    """
    result = {}
    for region, codes in LANGUAGE_REGIONS.items():
        result[region] = [
            {
                "code": code,
                "name": SUPPORTED_LANGUAGES[code].name,
                "native_name": SUPPORTED_LANGUAGES[code].native_name
            }
            for code in codes if code in SUPPORTED_LANGUAGES
        ]
    return result


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

    # ==================== LLM 配置 (api.gpt.ge) ====================

    llm_api_key: Optional[str] = Field(
        default=None,
        description="api.gpt.ge API Key (统一密钥)",
        env="NL_SEARCH_LLM_API_KEY"
    )

    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API Base URL (官方: https://api.openai.com/v1)",
        env="NL_SEARCH_LLM_BASE_URL"
    )

    llm_model: str = Field(
        default="gpt-4o",
        description="LLM 模型名称 (用于查询分解)",
        env="NL_SEARCH_LLM_MODEL"
    )

    search_model: str = Field(
        default="gpt-5-search",
        description="搜索模型名称 (用于网页搜索，官方: gpt-5-search)",
        env="NL_SEARCH_SEARCH_MODEL"
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

    # ==================== 搜索配置 ====================

    max_search_results: int = Field(
        default=50,
        description="搜索最大结果数（GPT搜索返回数量，不限制）",
        ge=1,
        le=100,
        env="NL_SEARCH_MAX_SEARCH_RESULTS"
    )

    search_max_tokens: int = Field(
        default=2000,
        description="搜索响应最大 token 数",
        ge=500,
        le=4096,
        env="NL_SEARCH_SEARCH_MAX_TOKENS"
    )

    # ==================== Reasoning 配置 ====================

    reasoning_enabled: bool = Field(
        default=True,
        description="是否启用推理功能（思维链）",
        env="NL_SEARCH_REASONING_ENABLED"
    )

    reasoning_effort: str = Field(
        default="medium",
        description="推理努力程度: low/medium/high",
        env="NL_SEARCH_REASONING_EFFORT"
    )

    # ==================== API 配置 ====================

    use_responses_api: bool = Field(
        default=True,
        description="是否使用 Responses API (推荐，支持 gpt-5-search 的完整功能)",
        env="NL_SEARCH_USE_RESPONSES_API"
    )

    # ==================== 多问题搜索配置 ====================

    multi_search_enabled: bool = Field(
        default=True,
        description="是否启用多问题分解搜索模式",
        env="NL_SEARCH_MULTI_SEARCH_ENABLED"
    )

    multi_search_sub_queries_count: int = Field(
        default=4,
        description="多问题分解的子问题数量",
        ge=2,
        le=10,
        env="NL_SEARCH_MULTI_SEARCH_SUB_QUERIES_COUNT"
    )

    multi_search_max_concurrent: int = Field(
        default=5,
        description="多问题搜索模式的最大并发抓取数",
        ge=1,
        le=10,
        env="NL_SEARCH_MULTI_SEARCH_MAX_CONCURRENT"
    )

    multi_search_aggregation_limit: int = Field(
        default=20,
        description="多问题搜索聚合后的最大结果数",
        ge=5,
        le=100,
        env="NL_SEARCH_MULTI_SEARCH_AGGREGATION_LIMIT"
    )

    multi_search_frequency_bonus: float = Field(
        default=0.1,
        description="URL出现频率加分（每次额外出现的加分）",
        ge=0.0,
        le=0.5,
        env="NL_SEARCH_MULTI_SEARCH_FREQUENCY_BONUS"
    )

    multi_search_frequency_bonus_max: float = Field(
        default=0.3,
        description="URL出现频率加分的最大值",
        ge=0.0,
        le=1.0,
        env="NL_SEARCH_MULTI_SEARCH_FREQUENCY_BONUS_MAX"
    )

    # ==================== 质量过滤配置 ====================

    score_threshold: float = Field(
        default=0.6,
        description="搜索结果分数阈值（低于此分数不爬取，节省成本）",
        ge=0.0,
        le=1.0,
        env="NL_SEARCH_SCORE_THRESHOLD"
    )

    # v3.7.2: 质量门控配置
    min_results_for_save: int = Field(
        default=3,
        description="保存到数据库的最小结果数量（质量门控阈值）",
        ge=1,
        le=20,
        env="NL_SEARCH_MIN_RESULTS_FOR_SAVE"
    )

    enable_quality_gate: bool = Field(
        default=True,
        description="是否启用质量门控（结果不足时发出警告）",
        env="NL_SEARCH_ENABLE_QUALITY_GATE"
    )

    filter_pdf_urls: bool = Field(
        default=True,
        description="是否过滤 PDF 文件 URL（.pdf结尾的链接）",
        env="NL_SEARCH_FILTER_PDF_URLS"
    )

    excluded_url_extensions: List[str] = Field(
        default=[".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".zip", ".rar"],
        description="需要过滤的 URL 文件扩展名列表",
        env="NL_SEARCH_EXCLUDED_URL_EXTENSIONS"
    )

    excluded_domains: List[str] = Field(
        default=[
            # 百科类 - 仅供理解背景，不得作为报告信息源引用
            "wikipedia.org",      # 维基百科 (所有语言版本)
            "baike.baidu.com",    # 百度百科
            "britannica.com",     # 大英百科全书
            "baike.sogou.com",    # 搜狗百科
            "baike.so.com",       # 360百科
        ],
        description="需要过滤的域名列表（百科类来源，仅供理解背景，不得作为报告引用）",
        env="NL_SEARCH_EXCLUDED_DOMAINS"
    )

    # ==================== 查询优化配置 ====================

    enable_query_optimization: bool = Field(
        default=True,
        description="是否启用 Claude 查询优化（使用解析的关键词优化搜索词）",
        env="NL_SEARCH_ENABLE_QUERY_OPTIMIZATION"
    )

    query_optimization_strategy: str = Field(
        default="keywords",
        description="查询优化策略: keywords=使用关键词, entities=使用实体, both=两者结合",
        env="NL_SEARCH_QUERY_OPTIMIZATION_STRATEGY"
    )

    # ==================== 时间过滤配置 ====================

    default_time_filter: str = Field(
        default="qdr:m",
        description="默认时间过滤 (qdr:h=1小时, qdr:d=1天, qdr:w=1周, qdr:m=1月, qdr:y=1年)",
        env="NL_SEARCH_DEFAULT_TIME_FILTER"
    )

    enable_time_filter: bool = Field(
        default=True,
        description="是否启用默认时间过滤",
        env="NL_SEARCH_ENABLE_TIME_FILTER"
    )

    # ==================== Scrape 配置 ====================

    scrape_timeout: int = Field(
        default=15,
        description="抓取超时时间(秒，降低以避免阻塞)",
        ge=5,
        le=300,
        env="NL_SEARCH_SCRAPE_TIMEOUT"
    )

    scrape_max_concurrent: int = Field(
        default=5,
        description="最大并发抓取数（提高并发度）",
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

    # ==================== Claude API 配置 (多语言搜索) ====================

    unified_analyzer_enabled: bool = Field(
        default=True,
        description="是否启用统一查询分析器 (复用 LangGraph QueryAnalyzerNode 的优秀 Prompt)",
        env="NL_SEARCH_UNIFIED_ANALYZER_ENABLED"
    )

    claude_enabled: bool = Field(
        default=False,
        description="是否启用 Claude 多语言搜索功能 (UnifiedQueryAnalyzer 未启用时使用)",
        env="NL_SEARCH_CLAUDE_ENABLED"
    )

    claude_base_url: str = Field(
        default="http://23.106.129.19:2828/api",
        description="Claude API Base URL (代理 API)",
        env="ANTHROPIC_BASE_URL"
    )

    claude_api_key: Optional[str] = Field(
        default=None,
        description="Claude API Key (代理 API Token)",
        env="ANTHROPIC_AUTH_TOKEN"
    )

    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude 模型名称",
        env="CLAUDE_MODEL"
    )

    claude_timeout: int = Field(
        default=60,
        description="Claude API 超时时间(秒)",
        ge=10,
        le=300,
        env="NL_SEARCH_CLAUDE_TIMEOUT"
    )

    claude_max_tokens: int = Field(
        default=1500,
        description="Claude 响应最大 token 数",
        ge=500,
        le=4096,
        env="NL_SEARCH_CLAUDE_MAX_TOKENS"
    )

    # ==================== 多语言搜索配置 ====================

    multilang_enabled: bool = Field(
        default=True,
        description="是否启用多语言搜索",
        env="NL_SEARCH_MULTILANG_ENABLED"
    )

    multilang_languages: List[str] = Field(
        default=DEFAULT_LANGUAGES,
        description="默认启用的语言列表。支持30+种语言，使用 /nl-search/languages API 获取完整列表",
        env="NL_SEARCH_MULTILANG_LANGUAGES"
    )

    multilang_results_per_lang: int = Field(
        default=5,
        description="每种语言的搜索结果数",
        ge=1,
        le=20,
        env="NL_SEARCH_MULTILANG_RESULTS_PER_LANG"
    )

    multilang_enable_summary: bool = Field(
        default=True,
        description="是否生成 Claude 汇总分析",
        env="NL_SEARCH_MULTILANG_ENABLE_SUMMARY"
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

    def validate_api_config(self) -> bool:
        """验证 api.gpt.ge 配置是否完整"""
        return (
            self.llm_api_key is not None
            and len(self.llm_api_key) > 0
            and self.llm_base_url is not None
        )

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
