"""LangGraph 搜索配置

集中管理所有配置项，支持环境变量覆盖
"""

from dataclasses import dataclass, field
from typing import List, Dict
import os

from .languages import (
    COUNTRY_TO_LANGUAGES,
    get_all_supported_languages,
    get_primary_languages,
    get_asian_languages,
    get_european_languages,
)


@dataclass
class LangGraphSearchConfig:
    """LangGraph 搜索配置"""

    # ===== Claude 配置 =====
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096

    # ===== Firecrawl 配置 =====
    firecrawl_api_key: str = field(
        default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", "fc-791acc51e2284efc9080a2bcf338565c")
    )
    firecrawl_timeout: int = 60  # 增加 Firecrawl 超时时间

    # ===== 搜索配置 =====
    max_parties: int = 5               # 最大当事方数量
    max_domains_per_layer: int = 10    # 每层最大域名数
    results_per_query: int = 100       # 每次查询结果数

    # ===== 分层配置 =====
    enable_layer_0: bool = True        # 官方来源
    enable_layer_1: bool = True        # 主流媒体
    enable_layer_2: bool = True        # 周边地区
    enable_layer_3: bool = True        # 国际权威
    enable_layer_4: bool = True        # 智库分析

    # ===== 验证配置 =====
    enable_validation: bool = True
    min_results_for_validation: int = 5
    validation_threshold: float = 0.7

    # ===== 质量门控配置 (v3.7.2) =====
    enable_quality_gate: bool = True
    min_results: int = 3                 # 最小结果数量
    min_quality_score: float = 0.6      # 最小质量分数
    max_search_retries: int = 3         # 最大重试次数

    # ===== 人工审核配置 =====
    enable_human_review: bool = False
    review_threshold: float = 0.5

    # ===== 源发现配置 =====
    verify_discovered_sources: bool = True

    # ===== 检查点配置 =====
    enable_checkpointing: bool = True
    checkpoint_type: str = "sqlite"    # sqlite | postgres
    checkpoint_db_path: str = "data/langgraph_checkpoints.db"
    checkpoint_db_url: str = field(
        default_factory=lambda: os.getenv("CHECKPOINT_DB_URL", "")
    )

    # ===== 性能配置 =====
    max_concurrent_searches: int = 5
    search_timeout: int = 300  # 5分钟 - 5层搜索+质量门控需要更长时间
    enable_parallel_layers: bool = True  # 启用5层并行执行

    # ===== 预定义来源 =====
    international_media: List[str] = field(default_factory=lambda: [
        "reuters.com", "apnews.com", "afp.com",
        "bbc.com", "cnn.com", "nytimes.com",
        "theguardian.com", "washingtonpost.com",
        "aljazeera.com", "dw.com",
    ])

    think_tanks: List[str] = field(default_factory=lambda: [
        "csis.org", "rand.org", "brookings.edu",
        "cfr.org", "carnegieendowment.org",
        "heritage.org", "aei.org",
        "iseas.edu.sg", "aspi.org.au",
    ])

    # ===== 语言配置 (v3.7.2: 扩展支持20+种语言) =====
    # 支持的语言列表
    supported_languages: List[str] = field(
        default_factory=lambda: get_all_supported_languages()
    )
    # 主要语言（使用最广泛）
    primary_languages: List[str] = field(
        default_factory=lambda: get_primary_languages()
    )
    # 亚洲语言
    asian_languages: List[str] = field(
        default_factory=lambda: get_asian_languages()
    )
    # 欧洲语言
    european_languages: List[str] = field(
        default_factory=lambda: get_european_languages()
    )
    # 国家/地区到语言的映射（引用 languages 模块）
    country_to_languages: Dict[str, List[str]] = field(
        default_factory=lambda: COUNTRY_TO_LANGUAGES
    )
    # 兼容旧版: 国家到主要语言的映射
    party_language_map: dict = field(default_factory=lambda: {
        "美国": "en", "英国": "en", "澳大利亚": "en", "加拿大": "en",
        "中国": "zh", "台湾": "zh", "香港": "zh", "澳门": "zh",
        "日本": "ja",
        "韩国": "ko", "朝鲜": "ko",
        "俄罗斯": "ru",
        "法国": "fr",
        "德国": "de",
        "西班牙": "es",
        "意大利": "it",
        "葡萄牙": "pt", "巴西": "pt",
        "荷兰": "nl",
        "土耳其": "tr",
        "印度": "hi",
        "巴基斯坦": "ur",
        "越南": "vi",
        "泰国": "th",
        "印尼": "id",
        "马来西亚": "ms",
        "沙特": "ar", "阿联酋": "ar", "埃及": "ar",
    })

    # 新增: 获取国家对应的语言列表
    def get_languages_for_country(self, country: str) -> List[str]:
        """获取国家/地区对应的语言列表

        Args:
            country: 国家名称（中文）

        Returns:
            语言代码列表
        """
        return self.country_to_languages.get(country, ["zh"])  # 默认中文

    # 新增: 检查语言是否支持
    def is_language_supported(self, lang_code: str) -> bool:
        """检查语言代码是否支持

        Args:
            lang_code: ISO 639-1 语言代码

        Returns:
            是否支持
        """
        return lang_code in self.supported_languages

    @classmethod
    def from_env(cls) -> "LangGraphSearchConfig":
        """从环境变量加载配置"""
        return cls(
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", "fc-791acc51e2284efc9080a2bcf338565c"),
            enable_validation=os.getenv("ENABLE_VALIDATION", "true").lower() == "true",
            enable_human_review=os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true",
            checkpoint_type=os.getenv("CHECKPOINT_TYPE", "sqlite"),
            max_concurrent_searches=int(os.getenv("MAX_CONCURRENT_SEARCHES", "5")),
            search_timeout=int(os.getenv("SEARCH_TIMEOUT", "300")),  # 默认5分钟
        )

    def get_enabled_layers(self) -> List[int]:
        """获取启用的搜索层级"""
        layers = []
        if self.enable_layer_0:
            layers.append(0)
        if self.enable_layer_1:
            layers.append(1)
        if self.enable_layer_2:
            layers.append(2)
        if self.enable_layer_3:
            layers.append(3)
        if self.enable_layer_4:
            layers.append(4)
        return layers

    def get_layer_weight(self, layer: int) -> float:
        """获取层级权重 (层级越低，权重越高)"""
        weight_map = {
            0: 1.0,   # 官方来源最高
            1: 0.9,   # 主流媒体
            2: 0.7,   # 周边地区
            3: 0.85,  # 国际权威
            4: 0.75,  # 智库分析
        }
        return weight_map.get(layer, 0.5)

    def get_layer_credibility(self, layer: int) -> float:
        """获取层级基础可信度"""
        credibility_map = {
            0: 0.95,  # 官方来源
            1: 0.85,  # 主流媒体
            2: 0.75,  # 周边地区
            3: 0.85,  # 国际权威
            4: 0.80,  # 智库分析
        }
        return credibility_map.get(layer, 0.6)

    def get_layer_tier(self, layer: int) -> int:
        """获取层级对应的来源等级"""
        tier_map = {
            0: 1,  # 官方来源 → Tier 1
            1: 2,  # 主流媒体 → Tier 2
            2: 3,  # 周边地区 → Tier 3
            3: 2,  # 国际权威 → Tier 2
            4: 3,  # 智库分析 → Tier 3
        }
        return tier_map.get(layer, 4)
