"""
OSINT Search LangGraph StateGraph 定义

定义Agent工作流图结构和编译

工作流程:
    START
      │
      ▼
    parse_intent (LLM解析意图6要素)
      │
      ▼
    generate_keywords (LLM生成分层关键词Layer 0-5)
      │
      ▼
    generate_validation_rules (LLM生成动态验证规则 - V4新增)
      │
      ▼ (fan_out_search - 并行)
    execute_single_search [N个并行任务]
      │
      ▼
    merge_deduplicate (URL+标题去重)
      │
      ▼ (route_by_source_count)
    ┌─────────────────┬────────────────┐
    │ count < 3       │ count >= 3     │
    │ iteration < 3   │                │
    ▼                 ▼                │
    expand_search     scrape_single_url (并行抓取)
    │                 │                │
    └──► generate_keywords              │
                      ▼                │
                    validate_relevance (V4验证: 必要条件AND + 置信度OR)
                      │
                      ▼
                    classify_sources (LLM来源分类)
                      │
                      ▼
                     END
"""

import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..models.schemas import OSINTSearchConfig
from ..models.state import OSINTSearchState
from .nodes import (
    classify_sources,
    execute_single_search,
    expand_search,
    fan_out_scrape,
    fan_out_search,
    generate_keywords,
    generate_validation_rules,
    merge_deduplicate,
    parse_intent,
    route_by_source_count,
    scrape_single_url,
    validate_relevance,
)


def create_osint_search_graph() -> StateGraph:
    """
    创建OSINT搜索工作流图

    工作流程:
    START → parse_intent → generate_keywords → generate_validation_rules
        → [fan_out_search] → execute_single_search (并行) → merge_deduplicate
        → [route_by_source_count]
        → (expand_search → generate_keywords) 或 (scrape_single_url)
        → validate_relevance (使用动态验证规则) → classify_sources → END

    Returns:
        StateGraph实例
    """
    # 创建图
    builder = StateGraph(OSINTSearchState)

    # ===== 添加节点 =====
    # 意图解析
    builder.add_node("parse_intent", parse_intent)

    # 关键词生成
    builder.add_node("generate_keywords", generate_keywords)

    # 动态验证规则生成 (V4新增)
    builder.add_node("generate_validation_rules", generate_validation_rules)

    # 搜索执行(单个关键词组)
    builder.add_node("execute_single_search", execute_single_search)

    # 去重合并
    builder.add_node("merge_deduplicate", merge_deduplicate)

    # 扩展搜索(当结果不足时)
    builder.add_node("expand_search", expand_search)

    # 深度抓取(单个URL)
    builder.add_node("scrape_single_url", scrape_single_url)

    # 相关性验证
    builder.add_node("validate_relevance", validate_relevance)

    # 来源分类
    builder.add_node("classify_sources", classify_sources)

    # ===== 添加边 =====

    # START → parse_intent
    builder.add_edge(START, "parse_intent")

    # parse_intent → generate_keywords
    builder.add_edge("parse_intent", "generate_keywords")

    # generate_keywords → generate_validation_rules (V4新增)
    builder.add_edge("generate_keywords", "generate_validation_rules")

    # generate_validation_rules → fan_out_search (并行搜索)
    # fan_out_search 返回 Send 对象列表，分发到 execute_single_search
    builder.add_conditional_edges(
        "generate_validation_rules",
        fan_out_search,
        ["execute_single_search"],
    )

    # execute_single_search → merge_deduplicate
    builder.add_edge("execute_single_search", "merge_deduplicate")

    # merge_deduplicate → 条件路由
    # route_by_source_count 返回 "expand_search" 或 "deep_scrape"
    # 注意：深度抓取需要使用 fan_out_scrape 来并行分发
    def route_with_fan_out(state):
        """路由决策 + 深度抓取并行分发"""
        route = route_by_source_count(state)
        if route == "deep_scrape":
            # 返回并行 Send 任务
            return fan_out_scrape(state)
        return route

    builder.add_conditional_edges(
        "merge_deduplicate",
        route_with_fan_out,
        {
            "expand_search": "expand_search",
            "scrape_single_url": "scrape_single_url",  # fan_out_scrape 返回 Send 到这个节点
        },
    )

    # expand_search → generate_keywords (循环回去继续搜索)
    builder.add_edge("expand_search", "generate_keywords")

    # scrape_single_url → validate_relevance
    # 注意: 由于使用fan_out_scrape，这里需要处理并行抓取结果聚合
    # LangGraph会自动聚合Annotated[list, operator.add]字段
    builder.add_edge("scrape_single_url", "validate_relevance")

    # validate_relevance → classify_sources
    builder.add_edge("validate_relevance", "classify_sources")

    # classify_sources → END
    builder.add_edge("classify_sources", END)

    return builder


def compile_osint_graph(
    checkpointer: Any | None = None,
) -> CompiledStateGraph:
    """
    编译OSINT搜索工作流图

    Args:
        checkpointer: 可选的检查点存储器，用于持久化状态

    Returns:
        编译后的图
    """
    builder = create_osint_search_graph()

    if checkpointer:
        return builder.compile(checkpointer=checkpointer)

    return builder.compile()


# 默认编译图(单例)
_default_osint_graph: CompiledStateGraph | None = None


def get_osint_graph() -> CompiledStateGraph:
    """
    获取默认编译图(单例模式)

    Returns:
        编译后的图
    """
    global _default_osint_graph
    if _default_osint_graph is None:
        _default_osint_graph = compile_osint_graph()
    return _default_osint_graph


def create_osint_initial_state(
    query: str,
    config: OSINTSearchConfig | None = None,
) -> OSINTSearchState:
    """
    创建OSINT搜索初始状态

    Args:
        query: 用户查询
        config: OSINT搜索配置

    Returns:
        初始状态字典
    """
    # 使用默认配置
    if config is None:
        config = OSINTSearchConfig()

    return OSINTSearchState(
        # 输入
        user_query=query,
        # 意图解析
        parsed_intent=None,
        # 关键词
        keyword_groups=[],
        # 搜索结果
        raw_results=[],
        deduplicated_results=[],
        # 深度抓取
        scraped_contents=[],
        # 相关性验证
        validation_rules=None,  # V4新增: LLM生成的动态验证规则
        relevance_results=[],
        validated_results=[],
        discarded_count=0,
        # 分类
        classified_sources=[],
        # 控制流
        iteration_count=0,
        confidence_score=0.0,
        # 调试和错误
        error_messages=[],
        messages=[],
        # 配置(通过metadata传递)
        metadata={
            "start_time": time.time(),
            "config": {
                "max_keywords": config.max_keywords,
                "max_results_per_keyword": config.max_results_per_keyword,
                "max_scrape_urls": config.max_scrape_urls,
                "similarity_threshold": config.similarity_threshold,
                "max_iterations": config.max_iterations,
            },
        },
    )


async def run_osint_search(
    query: str,
    config: OSINTSearchConfig | None = None,
    graph: CompiledStateGraph | None = None,
) -> OSINTSearchState:
    """
    运行OSINT搜索工作流

    Args:
        query: 用户查询
        config: OSINT搜索配置
        graph: 可选的自定义图

    Returns:
        最终状态
    """
    if graph is None:
        graph = get_osint_graph()

    initial_state = create_osint_initial_state(query, config)

    # 执行图
    final_state = await graph.ainvoke(initial_state)

    return final_state


async def stream_osint_search(
    query: str,
    config: OSINTSearchConfig | None = None,
    graph: CompiledStateGraph | None = None,
):
    """
    流式运行OSINT搜索工作流

    Args:
        query: 用户查询
        config: OSINT搜索配置
        graph: 可选的自定义图

    Yields:
        工作流事件
    """
    if graph is None:
        graph = get_osint_graph()

    initial_state = create_osint_initial_state(query, config)

    # 流式执行
    async for event in graph.astream(initial_state):
        yield event


# ============================================================================
# 兼容旧API (保持向后兼容)
# ============================================================================

# 旧的CrawlState导入
from ..models.schemas import CrawlConfig  # noqa: E402


def create_crawl_graph() -> StateGraph:
    """
    创建爬取工作流图 (兼容旧API)

    注意: 此函数已废弃，请使用 create_osint_search_graph()

    Returns:
        StateGraph实例
    """
    import warnings

    warnings.warn(
        "create_crawl_graph() is deprecated, use create_osint_search_graph() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return create_osint_search_graph()


def compile_graph(
    checkpointer: Any | None = None,
) -> CompiledStateGraph:
    """
    编译工作流图 (兼容旧API)

    注意: 此函数已废弃，请使用 compile_osint_graph()
    """
    import warnings

    warnings.warn(
        "compile_graph() is deprecated, use compile_osint_graph() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return compile_osint_graph(checkpointer)


def get_graph() -> CompiledStateGraph:
    """
    获取默认编译图 (兼容旧API)

    注意: 此函数已废弃，请使用 get_osint_graph()
    """
    import warnings

    warnings.warn(
        "get_graph() is deprecated, use get_osint_graph() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_osint_graph()


def create_initial_state(
    query: str,
    config: CrawlConfig | None = None,
) -> OSINTSearchState:
    """
    创建初始状态 (兼容旧API)

    注意: 此函数已废弃，请使用 create_osint_initial_state()
    """
    import warnings

    warnings.warn(
        "create_initial_state() is deprecated, use create_osint_initial_state() instead",
        DeprecationWarning,
        stacklevel=2,
    )

    # 转换旧配置到新配置
    search_config = None
    if config:
        search_config = OSINTSearchConfig(
            max_keywords=config.max_keywords,
            max_results_per_keyword=config.max_results_per_keyword,
            max_scrape_urls=config.max_scrape_urls,
        )

    # 使用新的OSINT状态创建函数
    return create_osint_initial_state(query, search_config)


async def run_crawl(
    query: str,
    config: CrawlConfig | None = None,
    graph: CompiledStateGraph | None = None,
) -> OSINTSearchState:
    """
    运行爬取工作流 (兼容旧API)

    注意: 此函数已废弃，请使用 run_osint_search()
    """
    import warnings

    warnings.warn(
        "run_crawl() is deprecated, use run_osint_search() instead",
        DeprecationWarning,
        stacklevel=2,
    )

    if graph is None:
        graph = get_graph()

    initial_state = create_initial_state(query, config)
    final_state = await graph.ainvoke(initial_state)
    return final_state


async def stream_crawl(
    query: str,
    config: CrawlConfig | None = None,
    graph: CompiledStateGraph | None = None,
):
    """
    流式运行爬取工作流 (兼容旧API)

    注意: 此函数已废弃，请使用 stream_osint_search()
    """
    import warnings

    warnings.warn(
        "stream_crawl() is deprecated, use stream_osint_search() instead",
        DeprecationWarning,
        stacklevel=2,
    )

    if graph is None:
        graph = get_graph()

    initial_state = create_initial_state(query, config)
    async for event in graph.astream(initial_state):
        yield event
