"""LangGraph 搜索状态模型 (v4.16.0)

定义 SearchState 和相关数据结构，支持多用户隔离

v4.16.0: 添加 intent_filter_results 字段 (意图筛选结果)
"""

from typing import TypedDict, List, Dict, Optional, Annotated, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import operator


class SearchLayer(Enum):
    """搜索层级枚举"""
    OFFICIAL = 0      # 官方来源
    MAINSTREAM = 1    # 主流媒体
    REGIONAL = 2      # 周边地区
    INTERNATIONAL = 3 # 国际权威
    THINK_TANK = 4    # 智库分析


LAYER_NAMES = {
    SearchLayer.OFFICIAL: "官方来源",
    SearchLayer.MAINSTREAM: "主流媒体",
    SearchLayer.REGIONAL: "周边地区",
    SearchLayer.INTERNATIONAL: "国际权威",
    SearchLayer.THINK_TANK: "智库分析",
}


@dataclass
class DiscoveredSource:
    """发现的官方来源

    用于存储 Claude 动态发现的当事方官方信息来源
    """
    party_name: str          # 当事方名称 (如: "美国", "日本")
    party_type: str          # country | organization | person
    party_code: str          # ISO 国家代码 (如: "US", "JP")

    # Layer 0: 官方来源
    official_gov: List[str] = field(default_factory=list)      # ["whitehouse.gov", "state.gov"]
    official_agency: List[str] = field(default_factory=list)   # ["reuters.com", "apnews.com"]

    # Layer 1: 主流媒体
    local_mainstream: List[str] = field(default_factory=list)  # ["nytimes.com", "cnn.com"]

    # 语言
    primary_language: str = "en"  # "en", "ja", "zh"

    # 元数据
    discovery_time: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 0.7  # 0.0-1.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "party_name": self.party_name,
            "party_type": self.party_type,
            "party_code": self.party_code,
            "official_gov": self.official_gov,
            "official_agency": self.official_agency,
            "local_mainstream": self.local_mainstream,
            "primary_language": self.primary_language,
            "discovery_time": self.discovery_time.isoformat() if self.discovery_time else None,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DiscoveredSource":
        """从字典创建"""
        discovery_time = data.get("discovery_time")
        if isinstance(discovery_time, str):
            discovery_time = datetime.fromisoformat(discovery_time)

        return cls(
            party_name=data.get("party_name", ""),
            party_type=data.get("party_type", "country"),
            party_code=data.get("party_code", ""),
            official_gov=data.get("official_gov", []),
            official_agency=data.get("official_agency", []),
            local_mainstream=data.get("local_mainstream", []),
            primary_language=data.get("primary_language", "en"),
            discovery_time=discovery_time or datetime.utcnow(),
            confidence=data.get("confidence", 0.7),
        )


@dataclass
class SearchResult:
    """搜索结果

    LangGraph 内部使用的搜索结果数据结构
    """
    url: str
    title: str
    snippet: str
    source_domain: str

    # 分层信息
    layer: int = 0                    # 0-4
    layer_name: str = "官方来源"       # "官方来源", "主流媒体" 等
    source_tier: int = 1              # 1-6 可信度层级

    # 评分
    relevance_score: float = 0.5      # 相关性分数
    credibility_score: float = 0.5    # 可信度分数
    final_score: float = 0.0          # 综合分数

    # 内容
    markdown_content: Optional[str] = None
    html_content: Optional[str] = None

    # 元数据
    language: str = "en"
    published_date: Optional[str] = None
    fetched_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source_domain": self.source_domain,
            "layer": self.layer,
            "layer_name": self.layer_name,
            "source_tier": self.source_tier,
            "relevance_score": self.relevance_score,
            "credibility_score": self.credibility_score,
            "final_score": self.final_score,
            "markdown_content": self.markdown_content,
            "html_content": self.html_content,
            "language": self.language,
            "published_date": self.published_date,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SearchResult":
        """从字典创建"""
        fetched_at = data.get("fetched_at")
        if isinstance(fetched_at, str):
            fetched_at = datetime.fromisoformat(fetched_at)

        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            snippet=data.get("snippet", ""),
            source_domain=data.get("source_domain", ""),
            layer=data.get("layer", 0),
            layer_name=data.get("layer_name", "官方来源"),
            source_tier=data.get("source_tier", 1),
            relevance_score=data.get("relevance_score", 0.5),
            credibility_score=data.get("credibility_score", 0.5),
            final_score=data.get("final_score", 0.0),
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            language=data.get("language", "en"),
            published_date=data.get("published_date"),
            fetched_at=fetched_at,
        )


@dataclass
class LayerSearchResult:
    """单层搜索结果"""
    layer: int
    layer_name: str
    queries_executed: List[str] = field(default_factory=list)
    results: List[SearchResult] = field(default_factory=list)
    execution_time_ms: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "layer": self.layer,
            "layer_name": self.layer_name,
            "queries_executed": self.queries_executed,
            "results": [r.to_dict() for r in self.results],
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


# ==============================================================================
# v4.8.0: 规则化架构迁移 - 状态字段版本控制
# ==============================================================================
# v4.8.0: 移除 LLM 意图和关键词生成，使用基于规则的查询分析
# 移除 ParsedIntent 和 KeywordGroup 类型，改用简单字段
RULES_BASED_VERSION = "4.8.0"  # 标记规则化架构版本




class SearchState(TypedDict, total=False):
    """LangGraph 搜索状态

    多用户隔离设计:
    - user_id: 必需字段，用于数据隔离
    - log_id: 包含用户标识的 thread_id
    """

    # === 用户隔离 (必需) ===
    user_id: str                              # 用户ID (必需，用于数据隔离)

    # === 输入 ===
    query: str                                # 原始查询
    search_options: Dict                      # 搜索选项

    # === 查询分析 ===
    analysis: Dict                            # Claude 分析结果 (v4.6.0 保留兼容）
    parties: List[str]                        # 识别的���事方
    keywords: List[str]                       # 提取的关键词 (v4.6.0 保留兼容）
    keywords_en: List[str]                    # 英文关键词 (v4.6.0 保留兼容）
    time_range: str                           # 时间范围 (qdr:d, qdr:w, qdr:m)
    target_languages: List[str]               # 目标语言 (支持17种: zh, en, ja, ko, fr, de, es, it, pt, nl, ru, ar, tr, hi, ur, vi, th, id, ms)
    search_domains: List[str]                 # 意图检测的搜索域名

    # === v4.8.0: 规则化架构字段 =====
    # 媒体类型约束（用于域名过滤，不作为关键词）
    source_type_constraint: Optional[str]         # "西方主流媒体", "当地媒体" 等
    # 架构版本控制
    rules_based_version: Optional[str]         # RULES_BASED_VERSION

    # === v4.9.0: LLM 驱动的查询理解 =====
    # LLM 解释的查询理解结果
    llm_interpretation: Optional[Dict]           # LLM 对查询的理解和解��结果
    # firecrawl 搜索配置（由 LLM 生成）
    firecrawl_search_config: Optional[List[Dict]]  # Firecrawl API 搜索配置列表

    # === v4.17.0: 重试搜索配置 =====
    # 搜索重试控制
    should_retry: bool = False               # 是否需要重试
    # 被过滤结果记录（用于分析）
    filtered_out_results: List[Dict] = field(default_factory=list)  # 被过滤掉的结果

    # === v4.11.0: 两步关键词生成架构 =====
    # Step 1: 关键词生成节点输出
    keyword_generation: Optional[Dict]           # 关键词生成结果
    # 结构:
    # {
    #   "intent": {                              # 理解意图
    #     "source_type": "西方主流媒体",
    #     "content_depth": "报道+反应",
    #     "time_requirement": "无限制"
    #   },
    #   "event": {                               # 确认事件
    #     "type": "突发事件|持续事态|历史追溯|人物背景",
    #     "time": "2025年11月11日",
    #     "location": "四川阿坝",
    #     "parties": ["中国"]
    #   },
    #   "keyword_atoms": [                       # 关键词原子
    #     {"original": "四川阿坝", "atoms": ["Sichuan", "Aba"]}
    #   ],
    #   "keyword_expansions": {                  # 关键词扩展
    #     "Aba": {
    #       "synonyms": ["Aba Tibetan", "Tibetan area"],
    #       "related": ["Tibetan Autonomous Prefecture"],
    #       "variations": {"zh": "阿坝", "en": "Aba"}
    #     }
    #   },
    #   "tiered_keywords": {                     # 分层关键词
    #     "tier_1": ["Sichuan bridge collapse November 2025"],
    #     "tier_2": ["Hongqi Bridge collapse Sichuan"],
    #     "tier_3": ["Sichuan bridge collapse analysis"]
    #   },
    #   "search_directions": [                   # 搜索方向
    #     {"direction": "事件核心", "keywords": [...], "priority": 1},
    #     {"direction": "扩大范围", "keywords": [...], "priority": 2}
    #   ]
    # }

    # === 分层搜索配置 (v4.4.0: 由 Claude 分析生成) ===
    layer_search_config: Dict[str, Dict]      # 每层的语言和关键词配置
    # 结构示例:
    # {
    #   "layer_0_1": {"language": "zh", "keywords": ["四川阿坝"], "enabled": true},
    #   "layer_2": {"language": "ja", "keywords": ["四川省阿壩"], "enabled": true},
    #   "layer_3": {"language": "en", "keywords": ["Sichuan Aba"], "enabled": true},
    #   "layer_4": {"language": "en", "keywords": ["Sichuan China"], "enabled": true},
    # }

    # === 并行搜索配置 ===
    enabled_layers: List[int]                 # 启用的搜索层级 ([0, 1, 2, 3, 4])

    # === 源发现 ===
    discovered_sources: Dict[str, Dict]       # 发现的官方来源 (JSON 序列化)

    # === 分层搜索结果 (可累加) ===
    layer_results: Annotated[
        Dict[int, Dict],                      # layer_id -> LayerSearchResult (JSON)
        operator.or_                          # 字典合并
    ]

    # === 聚合结果 ===
    aggregated_results: List[Dict]            # 去重聚合后的结果 (JSON)
    # v4.16.0: 每个结果包含 intent_score 字段 (0.0-1.0) 用于排序

    # === 验证结果 ===
    validation_scores: Dict[str, float]       # URL → 验证分数
    cross_validation_done: bool
    filtered_count: Optional[int]              # v4.6.0: 相关性过滤掉的结果数量

    # === 质量门控 (v3.7.2) ===
    quality_metrics: Dict                      # 质量指标
    quality_gate_passed: bool                  # 质量门控是否通过
    quality_gate_reason: str                   # 质量检查失败原因
    quality_check_done: bool                   # 质量检查是否完成
    should_retry_search: bool                  # 是否需要重试
    search_retry_count: int                    # 当前重试次数
    retry_strategy: str                        # 重试策略

    # === 最终输出 ===
    final_results: List[Dict]                 # 最终排序结果 (JSON)
    statistics: Dict                          # 统计信息

    # === 元数据 ===
    log_id: str                               # 搜索记录ID (包含 user_id)
    status: str                               # pending | running | completed | failed
    error_message: Optional[str]              # 错误信息
    started_at: Optional[str]                 # ISO 格式时间
    completed_at: Optional[str]               # ISO 格式时间

    # === Human-in-the-loop ===
    needs_review: bool                        # 是否需要人工审核
    review_completed: bool                    # 审核是否完成


def create_initial_state(
    query: str,
    user_id: str,
    log_id: str,
    options: Optional[Dict] = None,
) -> SearchState:
    """创建初始搜索状态

    Args:
        query: 搜索查询
        user_id: 用户ID (必需)
        log_id: 日志ID (应包含用户标识)
        options: 搜索选项

    Returns:
        初始化的 SearchState

    Raises:
        ValueError: 如果 user_id 为空
    """
    if not user_id:
        raise ValueError("user_id is required for creating search state")

    # 从 options 中提取目标语言 (v4.3.0: 智能语言检测)
    opts = options or {}

    # 优先使用外部传入的语言配置，否则智能检测
    if "target_languages" in opts:
        initial_languages = opts["target_languages"]
    else:
        # 延迟导入避免循环依赖
        from .languages import get_default_languages_for_query
        initial_languages = get_default_languages_for_query(query)

    return SearchState(
        # 用户隔离
        user_id=user_id,

        # 输入
        query=query,
        search_options=opts,

        # 查询分析 (待填充)
        analysis={},
        parties=[],
        keywords=[],
        keywords_en=[],              # v4.6.0: 英文关键词 (保留兼容）
        time_range="qdr:m",
        target_languages=initial_languages,    # 使用传入的语言配置
        search_domains=[],           # 意图检测域名

        # v4.8.0: 规则化架构字段 (初始化)
        source_type_constraint=None,  # 待 QueryAnalyzer 填充
        rules_based_version=RULES_BASED_VERSION,

        # 分层搜索配置 (v4.4.0: 由 QueryAnalyzer 填充)
        layer_search_config={},

        # 并行搜索配置
        enabled_layers=[0, 1, 2, 3, 4],  # 默认启用所有5层

        # 源发现 (待填充)
        discovered_sources={},

        # 分层结果 (待填充)
        layer_results={},

        # 聚合结果 (待填充)
        # v4.16.0: 每个结果将包含 intent_score 字段
        aggregated_results=[],

        # 验证 (待填充)
        validation_scores={},
        cross_validation_done=False,
        filtered_count=None,  # v4.6.0: 相关性过滤掉的结果数量

        # 质量门控 (v3.7.2, 待填充)
        quality_metrics={},
        quality_gate_passed=False,
        quality_gate_reason="",
        quality_check_done=False,
        should_retry_search=False,
        search_retry_count=0,
        retry_strategy="",

        # v4.17.0: 重试和过滤结果
        should_retry=False,            # 两步架构重试控制
        filtered_out_results=[],      # 被过滤掉的结果（用于分析）

        # 最终输出 (待填充)
        final_results=[],
        statistics={},

        # 元数据
        log_id=log_id,
        status="pending",
        error_message=None,
        started_at=datetime.utcnow().isoformat(),
        completed_at=None,

        # 人工审核
        needs_review=False,
        review_completed=False,
    )
