"""
gs-ai-crawl Agent模块

提供OSINT搜索LangGraph工作流定义和执行功能
"""

from .graph import (
    # 兼容旧API (已废弃)
    compile_graph,
    # 新OSINT API
    compile_osint_graph,
    create_crawl_graph,
    create_initial_state,
    create_osint_initial_state,
    create_osint_search_graph,
    get_graph,
    get_osint_graph,
    run_crawl,
    run_osint_search,
    stream_crawl,
    stream_osint_search,
)
from .nodes import (
    # 输出模型
    ClassifiedSourceListOutput,
    ClassifiedSourceOutput,
    ExpandedKeywordsOutput,
    IntentOutput,
    KeywordGroupOutput,
    KeywordsOutput,
    RelevanceListOutput,
    RelevanceOutput,
    # OSINT节点 (新)
    classify_sources,
    execute_single_search,
    expand_search,
    fan_out_scrape,
    fan_out_search,
    generate_keywords,
    merge_deduplicate,
    parse_intent,
    route_by_source_count,
    scrape_single_url,
    validate_relevance,
)

__all__ = [
    # ===== 新OSINT API =====
    # Graph构建
    "create_osint_search_graph",
    "compile_osint_graph",
    "get_osint_graph",
    # 状态和执行
    "create_osint_initial_state",
    "run_osint_search",
    "stream_osint_search",
    # OSINT节点
    "parse_intent",
    "generate_keywords",
    "execute_single_search",
    "merge_deduplicate",
    "expand_search",
    "scrape_single_url",
    "validate_relevance",
    "classify_sources",
    # 路由和分发
    "route_by_source_count",
    "fan_out_search",
    "fan_out_scrape",
    # 输出模型
    "IntentOutput",
    "KeywordGroupOutput",
    "KeywordsOutput",
    "RelevanceOutput",
    "RelevanceListOutput",
    "ClassifiedSourceOutput",
    "ClassifiedSourceListOutput",
    "ExpandedKeywordsOutput",
    # ===== 兼容旧API (已废弃) =====
    "compile_graph",
    "create_crawl_graph",
    "create_initial_state",
    "get_graph",
    "run_crawl",
    "stream_crawl",
]
