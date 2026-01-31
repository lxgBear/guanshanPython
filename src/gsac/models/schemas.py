"""
gs-ai-crawl 数据模型定义

定义系统中使用的所有Pydantic模型，包括:
- OSINT搜索的6要素意图解析
- 分层关键词组
- 相关性验证结果
- 来源分类结果
"""

from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# OSINT 搜索核心数据模型 (按设计文档)
# ============================================================================


class ParsedIntent(BaseModel):
    """解析后的意图 (6要素)

    用于 parse_intent 节点输出，描述用户查询的完整意图

    Attributes:
        investigation_target: 调查对象 - 核心搜索目标
        time_range: 时间范围 - 如 "2025-11", "last week", None表示无限制
        source_type_constraint: 信息源约束 - 如 "西方主流媒体", "官方来源", "all"
        output_format: 输出格式 - 期望的输出形式
        tool_constraint: 工具限制 - 特定工具要求，如 "only_news"
        investigation_type: 调查类型 - 事件/态势感知/实体画像
    """

    investigation_target: str = Field(description="调查对象 - 用户查询的核心目标")
    time_range: str | None = Field(
        default=None,
        description="时间范围约束，如 '2025-11', 'last week'，None表示无时间限制",
    )
    source_type_constraint: str = Field(
        default="all",
        description="信息源约束，如 '西方主流媒体', '官方来源', 'all' 表示无限制",
    )
    output_format: str = Field(
        default="summary",
        description="期望输出格式: summary, detailed, list, timeline",
    )
    tool_constraint: str | None = Field(
        default=None,
        description="工具限制，如 'only_news', 'no_social_media'",
    )
    investigation_type: Literal["event", "situation_awareness", "entity_profile"] = Field(
        default="situation_awareness",
        description="调查类型: event(事件调查), situation_awareness(态势感知), entity_profile(实体画像)",
    )


class KeywordGroup(BaseModel):
    """分层关键词组

    用于 generate_keywords 节点输出，支持多层搜索策略

    分层策略:
    - Layer 0: 官方来源 (site: 限定)
    - Layer 1: 本地主流媒体
    - Layer 2: 区域媒体
    - Layer 3: 国际主流
    - Layer 4: 智库/学术
    - Layer 5: 百科/档案 (最宽泛)
    """

    keywords: list[str] = Field(
        description="关键词列表",
        min_length=1,
    )
    layer: int = Field(
        default=5,
        ge=0,
        le=5,
        description="关键词层级: 0(官方/最精确) ~ 5(百科/最宽泛)",
    )
    language: Literal["zh", "en", "mixed"] = Field(
        default="mixed",
        description="语言: zh(中文), en(英文), mixed(混合)",
    )
    search_type: Literal["web", "news"] = Field(
        default="web",
        description="搜索类型: web(网页), news(新闻)",
    )
    site_constraint: str | None = Field(
        default=None,
        description="站点限制，如 'site:gov.cn', 'site:bbc.com'",
    )


class RelevanceResult(BaseModel):
    """相关性验证结果

    用于 validate_relevance 节点输出，记录4步验证法的判断结果

    4步判断流程:
    1. 回顾原始意图
    2. 核心要素匹配检查 (地点/事件/时间/来源)
    3. 偏离判定 (丢弃/降级)
    4. 输出结果
    """

    url: str = Field(description="内容URL")
    title: str = Field(description="内容标题")
    relevance: Literal["keep", "downgrade", "discard"] = Field(
        description="相关性判定: keep(保留), downgrade(降级), discard(丢弃)"
    )
    reason: str = Field(description="判定理由，说明为何做出此判断")
    matched_elements: list[str] = Field(
        default_factory=list,
        description="匹配的要素列表，如 ['地点:四川', '事件:大桥坍塌', '时间:2025-11']",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="判定置信度",
    )


class ClassifiedSource(BaseModel):
    """分类后的来源

    用于 classify_sources 节点输出，完成来源分类和可信度评估

    分类体系:
    - official: 政府/官方机构
    - local_mainstream: 本地主流媒体
    - intl_mainstream: 国际主流媒体
    - think_tank: 智库/学术
    - other: 其他
    """

    url: str = Field(description="来源URL")
    title: str = Field(description="来源标题")
    category: Literal["official", "local_mainstream", "intl_mainstream", "think_tank", "other"] = (
        Field(description="来源分类")
    )
    credibility_score: float = Field(
        ge=0.0,
        le=1.0,
        description="可信度评分 (0.0-1.0)",
    )
    time_confidence: Literal["HIGH", "MEDIUM", "LOW", "REJECTED"] = Field(
        default="MEDIUM",
        description="时间置信度: HIGH(明确时间), MEDIUM(可推断), LOW(不确定), REJECTED(时间不符)",
    )
    content_summary: str = Field(
        default="",
        description="内容摘要 (100字以内)",
    )
    relevance_status: Literal["keep", "downgrade"] = Field(
        default="keep",
        description="相关性状态 (从验证节点继承)",
    )
    source_domain: str = Field(
        default="",
        description="来源域名",
    )
    published_date: str | None = Field(
        default=None,
        description="发布日期 (如果可提取)",
    )


class ScrapedContent(BaseModel):
    """抓取的完整内容

    用于 deep_scrape 节点输出
    """

    url: str = Field(description="页面URL")
    title: str = Field(default="", description="页面标题")
    markdown: str | None = Field(default=None, description="Markdown内容")
    html: str | None = Field(default=None, description="HTML内容")
    metadata: dict = Field(default_factory=dict, description="元数据")
    scrape_success: bool = Field(default=True, description="抓取是否成功")
    error_message: str | None = Field(default=None, description="错误信息")


# ============================================================================
# 搜索配置和任务模型
# ============================================================================


class SearchConfig(BaseModel):
    """搜索配置"""

    max_keywords: int = Field(default=5, ge=1, le=20, description="最大关键词数量")
    max_results_per_keyword: int = Field(
        default=10, ge=1, le=50, description="每个关键词的最大结果数"
    )
    enable_deep_scrape: bool = Field(default=True, description="是否启用深度抓取")
    max_scrape_urls: int = Field(default=5, ge=1, le=20, description="深度抓取的最大URL数")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="去重相似度阈值")
    enable_summary: bool = Field(default=True, description="是否生成摘要")
    time_filter: str | None = Field(
        default=None, description="时间过滤: qdr:h, qdr:d, qdr:w, qdr:m, qdr:y"
    )
    location: str | None = Field(default=None, description="地理位置过滤")
    sources: list[str] = Field(default_factory=lambda: ["web"], description="搜索来源")
    output_format: Literal["markdown", "json", "structured"] = Field(
        default="markdown", description="输出格式"
    )
    # OSINT特有配置
    min_source_count: int = Field(
        default=3, ge=1, le=10, description="最小来源数量 (少于此数触发expand_search)"
    )
    max_iterations: int = Field(default=3, ge=1, le=5, description="最大搜索迭代次数")


class SearchTask(BaseModel):
    """单个搜索任务"""

    keyword: str = Field(description="搜索关键词")
    source: str = Field(default="web", description="搜索来源")
    limit: int = Field(default=10, ge=1, le=50, description="结果数量限制")
    tbs: str | None = Field(default=None, description="时间过滤参数")
    location: str | None = Field(default=None, description="地理位置")
    site_constraint: str | None = Field(default=None, description="站点限制")
    layer: int = Field(default=5, ge=0, le=5, description="关键词层级")


class SearchResult(BaseModel):
    """搜索结果

    v4.9.0: 添加 source_name 和 layer_name 字段用于媒体来源映射
    """

    url: str = Field(description="结果URL")
    title: str = Field(description="结果标题")
    description: str | None = Field(default=None, description="结果描述")
    content: str | None = Field(default=None, description="结果内容")
    markdown: str | None = Field(default=None, description="Markdown格式内容")
    html: str | None = Field(default=None, description="HTML格式内容")
    source: str = Field(default="web", description="来源类型 (web/news/images)")
    source_name: str = Field(default="", description="媒体来源英文名称 (如 BBC, CNN)")
    keyword: str = Field(default="", description="来源关键词")
    source_domain: str = Field(default="", description="来源域名")
    layer_name: str = Field(default="", description="媒体来源中文名称 (如 英国广播公司新闻)")
    published_date: str | None = Field(default=None, description="发布日期")
    layer: int = Field(default=5, ge=0, le=5, description="关键词层级")
    score: float | None = Field(default=None, description="相关性评分 (0.0-1.0)")


# ============================================================================
# 输出模型
# ============================================================================


class OSINTSearchOutput(BaseModel):
    """OSINT搜索输出

    最终输出格式，包含完整的搜索结果和元数据
    """

    query: str = Field(description="原始查询")
    parsed_intent: ParsedIntent | None = Field(default=None, description="解析的意图")
    classified_sources: list[ClassifiedSource] = Field(
        default_factory=list, description="分类后的来源列表"
    )
    summary: str | None = Field(default=None, description="搜索结果摘要")
    total_found: int = Field(default=0, description="找到的总结果数")
    validated_count: int = Field(default=0, description="通过验证的结果数")
    discarded_count: int = Field(default=0, description="被丢弃的结果数")
    iteration_count: int = Field(default=0, description="搜索迭代次数")
    confidence_score: float = Field(default=0.0, description="整体置信度评分")
    keywords_used: list[str] = Field(default_factory=list, description="使用的关键词")
    execution_time: float = Field(default=0.0, description="执行时间(秒)")
    errors: list[str] = Field(default_factory=list, description="错误信息列表")


class CrawlOutput(BaseModel):
    """兼容旧API的输出格式"""

    query: str = Field(description="原始查询")
    summary: str | None = Field(default=None, description="结果摘要")
    results: list[SearchResult] = Field(default_factory=list, description="搜索结果列表")
    scraped_contents: list[ScrapedContent] = Field(default_factory=list, description="深度抓取内容")
    total_found: int = Field(default=0, description="找到的总结果数")
    keywords_used: list[str] = Field(default_factory=list, description="使用的关键词")
    execution_time: float = Field(default=0.0, description="执行时间(秒)")
    format: str = Field(default="markdown", description="输出格式")
    errors: list[str] | None = Field(default=None, description="错误信息列表")


class CrawlConfig(BaseModel):
    """用户调用时的配置参数"""

    # 覆盖全局配置
    firecrawl_api_key: str | None = Field(default=None, description="Firecrawl API密钥")
    llm_provider: str | None = Field(default=None, description="LLM提供者")
    llm_model: str | None = Field(default=None, description="LLM模型")

    # 搜索配置
    max_keywords: int = Field(default=5, ge=1, le=20, description="最大关键词数量")
    max_results_per_keyword: int = Field(
        default=10, ge=1, le=50, description="每个关键词的最大结果数"
    )
    enable_deep_scrape: bool = Field(default=True, description="是否启用深度抓取")
    max_scrape_urls: int = Field(default=5, ge=1, le=20, description="深度抓取的最大URL数")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="去重相似度阈值")

    # 过滤配置
    time_range: Literal["h", "d", "w", "m", "y"] | None = Field(
        default=None, description="时间范围过滤"
    )
    location: str | None = Field(default=None, description="地理位置")
    sources: list[str] = Field(default_factory=lambda: ["web"], description="搜索来源")

    # 输出配置
    output_format: Literal["markdown", "json", "structured"] = Field(
        default="markdown", description="输出格式"
    )
    enable_summary: bool = Field(default=True, description="是否生成摘要")

    # 性能配置
    timeout: int = Field(default=60, ge=10, le=300, description="超时时间(秒)")

    # OSINT特有配置
    min_source_count: int = Field(default=3, ge=1, le=10, description="最小来源数量")
    max_iterations: int = Field(default=3, ge=1, le=5, description="最大搜索迭代次数")

    def to_search_config(self) -> SearchConfig:
        """转换为内部SearchConfig"""
        return SearchConfig(
            max_keywords=self.max_keywords,
            max_results_per_keyword=self.max_results_per_keyword,
            enable_deep_scrape=self.enable_deep_scrape,
            max_scrape_urls=self.max_scrape_urls,
            similarity_threshold=self.similarity_threshold,
            enable_summary=self.enable_summary,
            time_filter=f"qdr:{self.time_range}" if self.time_range else None,
            location=self.location,
            sources=self.sources,
            output_format=self.output_format,
            min_source_count=self.min_source_count,
            max_iterations=self.max_iterations,
        )


class OSINTSearchConfig(BaseModel):
    """OSINT搜索配置

    用于 OSINT 搜索工作流的配置参数，控制搜索行为和质量

    Attributes:
        max_keywords: 每次搜索的最大关键词组数量
        max_results_per_keyword: 每个关键词的最大搜索结果数
        max_scrape_urls: 深度抓取的最大URL数
        similarity_threshold: 去重时的相似度阈值
        max_iterations: 扩展搜索的最大迭代次数
        min_source_count: 触发扩展搜索的最小来源数量阈值
    """

    # 搜索控制
    max_keywords: int = Field(
        default=5,
        ge=1,
        le=20,
        description="每次搜索的最大关键词组数量",
    )
    max_results_per_keyword: int = Field(
        default=10,
        ge=1,
        le=50,
        description="每个关键词的最大搜索结果数",
    )

    # 抓取控制
    max_scrape_urls: int = Field(
        default=10,
        ge=1,
        le=50,
        description="深度抓取的最大URL数量",
    )

    # 去重控制
    similarity_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="去重时的相似度阈值 (0.0-1.0)",
    )

    # 迭代控制
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="扩展搜索的最大迭代次数",
    )
    min_source_count: int = Field(
        default=3,
        ge=1,
        le=20,
        description="触发扩展搜索的最小来源数量阈值",
    )

    # LLM配置覆盖
    llm_provider: str | None = Field(
        default=None,
        description="LLM提供者覆盖",
    )
    llm_model: str | None = Field(
        default=None,
        description="LLM模型覆盖",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="LLM API密钥覆盖",
    )

    # Firecrawl配置
    firecrawl_api_key: str | None = Field(
        default=None,
        description="Firecrawl API密钥覆盖",
    )

    # 超时配置
    timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="总体超时时间(秒)",
    )
