"""
gs-ai-crawl OSINT搜索 LangGraph状态定义

定义Agent执行过程中的完整状态结构，支持:
- 6要素意图解析
- 分层关键词搜索
- 相关性验证
- 来源分类
- 迭代扩展搜索
"""

import operator
from typing import Annotated

from langgraph.graph import add_messages
from typing_extensions import TypedDict

from .schemas import (
    ClassifiedSource,
    CrawlOutput,
    KeywordGroup,
    OSINTSearchOutput,
    ParsedIntent,
    RelevanceResult,
    ScrapedContent,
    SearchConfig,
    SearchResult,
    SearchTask,
    ValidationRules,
)


class MissingElements(TypedDict, total=False):
    """缺失要素信息

    用于检测用户输入中缺少的关键要素

    Attributes:
        time_range: 是否缺少时间范围
        location: 是否缺少地点信息
        entity_name: 是否缺少实体名称
        source_type: 是否缺少来源约束
    """

    time_range: bool
    location: bool
    entity_name: bool
    source_type: bool


class UserProvidedElements(TypedDict, total=False):
    """用户补充的要素

    用于存储用户通过交互提供的额外信息

    Attributes:
        time_range: 用户提供的时间范围
        location: 用户提供的地点信息
        entity_name: 用户提供的实体名称
        source_type: 用户提供的来源类型
    """

    time_range: str | None
    location: str | None
    entity_name: str | None
    source_type: str | None


class OSINTSearchState(TypedDict):
    """OSINT Search Graph 完整状态

    使用 Annotated 实现并行执行时的状态自动聚合

    状态分组:
    - 输入: 用户原始查询
    - 要素澄清: 缺失要素检测和用户补充
    - 意图解析: 6要素意图结构
    - 关键词: 分层关键词组
    - 搜索结果: 原始结果和去重结果
    - 深度抓取: 抓取的完整内容
    - 相关性验证: 验证结果和保留列表
    - 分类: 分类后的来源列表
    - 控制流: 迭代计数和置信度
    - 调试: 错误信息和调试消息
    """

    # ===== 输入 =====
    user_query: str  # 用户原始查询

    # ===== 要素澄清 (新增) =====
    skip_element_clarification: bool  # 是否跳过要素询问（泛搜索模式）
    user_provided_elements: UserProvidedElements | None  # 用户补充的要素
    clarification_needed: bool  # 是否需要澄清
    clarification_questions: list[str] | None  # 澄清问题列表
    missing_elements: MissingElements | None  # 缺失要素详情

    # ===== 意图解析 =====
    parsed_intent: ParsedIntent | None  # 解析后的意图(6要素)

    # ===== 关键词 =====
    # 使用 operator.add 实现分层关键词组的自动聚合
    keyword_groups: Annotated[list[KeywordGroup], operator.add]

    # ===== 搜索结果 =====
    # 原始结果支持并行搜索的自动聚合
    raw_results: Annotated[list[SearchResult], operator.add]
    deduplicated_results: list[SearchResult]  # 去重后结果

    # ===== 深度抓取 =====
    # 抓取内容支持并行抓取的自动聚合
    scraped_contents: Annotated[list[ScrapedContent], operator.add]

    # ===== 相关性验证 =====
    validation_rules: ValidationRules | None  # LLM生成的动态验证规则
    relevance_results: list[RelevanceResult]  # 验证结果列表
    validated_results: list[SearchResult]  # 通过验证的结果
    discarded_count: int  # 丢弃数量统计

    # ===== 分类 =====
    classified_sources: list[ClassifiedSource]  # 分类后的来源

    # ===== 控制流 =====
    iteration_count: int  # 搜索迭代次数 (用于expand_search循环控制)
    confidence_score: float  # 整体置信度评分

    # ===== 调试和错误 =====
    error_messages: Annotated[list[str], operator.add]  # 错误信息(支持聚合)
    messages: Annotated[list, add_messages]  # 调试消息(LangGraph标准消息格式)

    # ===== 元数据 =====
    metadata: dict  # 执行元数据 (配置、时间戳等)


# 保留旧的CrawlState以支持向后兼容
class CrawlState(TypedDict):
    """
    兼容旧API的LangGraph Agent状态定义

    @deprecated 推荐使用 OSINTSearchState
    """

    # ===== 输入 =====
    query: str  # 用户原始查询

    # ===== 意图解析结果 =====
    intent: ParsedIntent | None  # 解析后的意图
    keywords: list[str]  # 生成的搜索关键词
    search_config: SearchConfig | None  # 搜索配置

    # ===== 搜索执行 =====
    search_tasks: list[SearchTask]  # 待执行的搜索任务
    raw_results: Annotated[list[SearchResult], operator.add]

    # ===== 处理结果 =====
    deduplicated_results: list[SearchResult]  # 去重后结果
    scraped_content: list[ScrapedContent]  # 深度抓取内容

    # ===== 输出 =====
    final_output: CrawlOutput | None  # 最终格式化输出

    # ===== 元数据 =====
    errors: Annotated[list[str], operator.add]  # 错误信息(支持聚合)
    metadata: dict  # 执行元数据


# 导出状态类型供节点函数使用
__all__ = [
    # 主要状态类型
    "OSINTSearchState",
    "CrawlState",
    # 数据模型 (方便节点直接导入)
    "ParsedIntent",
    "KeywordGroup",
    "SearchResult",
    "ScrapedContent",
    "RelevanceResult",
    "ValidationRules",
    "ClassifiedSource",
    "SearchConfig",
    "SearchTask",
    "CrawlOutput",
    "OSINTSearchOutput",
]
