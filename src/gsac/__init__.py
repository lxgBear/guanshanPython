"""
gsac: 基于LangGraph + Firecrawl的AI驱动智能搜索Agent

提供简洁的API用于自然语言驱动的网络搜索和数据提取。

基本用法:
    >>> from gsac import crawl, acrawl, astream, search
    >>>
    >>> # 同步调用
    >>> result = crawl("Python web框架对比")
    >>>
    >>> # 异步调用
    >>> result = await acrawl("AI最新进展")
    >>>
    >>> # 流式输出
    >>> async for event in astream("技术趋势"):
    ...     print(event)
    >>>
    >>> # 简单搜索
    >>> results = search("FastAPI", limit=10)
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Literal

from .agent.graph import get_graph, run_crawl, stream_crawl
from .models.schemas import CrawlConfig, CrawlOutput, SearchResult
from .processors.formatter import format_results
from .tools.search import search_sync

__version__ = "0.1.0"
__author__ = "gsac team"

__all__ = [
    # 版本信息
    "__version__",
    # 核心API
    "crawl",
    "acrawl",
    "astream",
    "search",
    # 配置
    "CrawlConfig",
    # 输出模型
    "CrawlOutput",
    "SearchResult",
    # 格式化
    "format_results",
    # 高级API
    "create_agent",
    "get_graph",
    # 内部转换函数 (CLI使用)
    "_convert_osint_state_to_output",
]


def crawl(
    query: str,
    *,
    max_keywords: int = 5,
    max_results_per_keyword: int = 10,
    enable_deep_scrape: bool = False,
    max_scrape_urls: int = 3,
    similarity_threshold: float = 0.8,
    enable_summary: bool = True,
    output_format: Literal["markdown", "json", "structured"] = "markdown",
) -> str:
    """
    同步执行智能搜索

    将自然语言查询转换为搜索关键词，执行搜索并返回格式化结果。

    Args:
        query: 自然语言查询，如 "Python web框架对比"
        max_keywords: 最大关键词数量，默认5
        max_results_per_keyword: 每个关键词的最大结果数，默认10
        enable_deep_scrape: 是否启用深度抓取，默认False
        max_scrape_urls: 深度抓取的最大URL数，默认3
        similarity_threshold: 去重相似度阈值，默认0.8
        enable_summary: 是否生成摘要，默认True
        output_format: 输出格式 (markdown/json/structured)，默认markdown

    Returns:
        格式化后的搜索结果字符串

    Examples:
        >>> result = crawl("Python web框架对比")
        >>> print(result)

        >>> result = crawl("AI最新进展", enable_deep_scrape=True, output_format="json")
    """
    config = CrawlConfig(
        max_keywords=max_keywords,
        max_results_per_keyword=max_results_per_keyword,
        enable_deep_scrape=enable_deep_scrape,
        max_scrape_urls=max_scrape_urls,
        similarity_threshold=similarity_threshold,
        enable_summary=enable_summary,
        output_format=output_format,
    )

    # 运行异步函数
    final_state = asyncio.run(_run_crawl_async(query, config))

    # 从新的OSINT状态转换为CrawlOutput
    output = _convert_osint_state_to_output(query, final_state)
    return format_results(output, output_format)


async def acrawl(
    query: str,
    *,
    max_keywords: int = 5,
    max_results_per_keyword: int = 10,
    enable_deep_scrape: bool = False,
    max_scrape_urls: int = 3,
    similarity_threshold: float = 0.8,
    enable_summary: bool = True,
    output_format: Literal["markdown", "json", "structured"] = "markdown",
) -> CrawlOutput:
    """
    异步执行智能搜索

    将自然语言查询转换为搜索关键词，执行搜索并返回结构化结果。

    Args:
        query: 自然语言查询
        max_keywords: 最大关键词数量
        max_results_per_keyword: 每个关键词的最大结果数
        enable_deep_scrape: 是否启用深度抓取
        max_scrape_urls: 深度抓取的最大URL数
        similarity_threshold: 去重相似度阈值
        enable_summary: 是否生成摘要
        output_format: 输出格式

    Returns:
        CrawlOutput对象，包含所有搜索结果和元数据

    Examples:
        >>> result = await acrawl("Python web框架对比")
        >>> print(result.summary)
        >>> for r in result.results:
        ...     print(r.title, r.url)
    """
    config = CrawlConfig(
        max_keywords=max_keywords,
        max_results_per_keyword=max_results_per_keyword,
        enable_deep_scrape=enable_deep_scrape,
        max_scrape_urls=max_scrape_urls,
        similarity_threshold=similarity_threshold,
        enable_summary=enable_summary,
        output_format=output_format,
    )

    final_state = await _run_crawl_async(query, config)

    # 从新的OSINT状态转换为CrawlOutput
    return _convert_osint_state_to_output(query, final_state)


async def astream(
    query: str,
    *,
    max_keywords: int = 5,
    max_results_per_keyword: int = 10,
    enable_deep_scrape: bool = False,
    max_scrape_urls: int = 3,
    similarity_threshold: float = 0.8,
    enable_summary: bool = True,
) -> AsyncIterator[dict[str, Any]]:
    """
    流式执行智能搜索

    实时返回搜索过程中的每个步骤事件。

    Args:
        query: 自然语言查询
        max_keywords: 最大关键词数量
        max_results_per_keyword: 每个关键词的最大结果数
        enable_deep_scrape: 是否启用深度抓取
        max_scrape_urls: 深度抓取的最大URL数
        similarity_threshold: 去重相似度阈值
        enable_summary: 是否生成摘要

    Yields:
        包含节点名称和状态更新的事件字典

    Examples:
        >>> async for event in astream("AI最新进展"):
        ...     node_name = list(event.keys())[0]
        ...     print(f"完成节点: {node_name}")
    """
    config = CrawlConfig(
        max_keywords=max_keywords,
        max_results_per_keyword=max_results_per_keyword,
        enable_deep_scrape=enable_deep_scrape,
        max_scrape_urls=max_scrape_urls,
        similarity_threshold=similarity_threshold,
        enable_summary=enable_summary,
    )

    async for event in stream_crawl(query, config):
        yield event


def search(
    query: str,
    *,
    limit: int = 10,
    time_range: str | None = None,
) -> list[SearchResult]:
    """
    简单搜索API

    直接执行关键词搜索，不进行意图解析和关键词生成。

    Args:
        query: 搜索关键词
        limit: 返回结果数量限制，默认10
        time_range: 时间范围过滤 (h/d/w/m/y)，默认None

    Returns:
        搜索结果列表

    Examples:
        >>> results = search("FastAPI", limit=5)
        >>> for r in results:
        ...     print(r.title, r.url)

        >>> results = search("Python新闻", time_range="w")  # 最近一周
    """
    return search_sync(query, limit=limit, time_range=time_range)


def create_agent(
    checkpointer: Any | None = None,
) -> Any:
    """
    创建自定义Agent实例

    用于需要自定义配置或持久化状态的高级用例。

    Args:
        checkpointer: 可选的检查点存储器，用于持久化状态

    Returns:
        编译后的LangGraph图

    Examples:
        >>> from langgraph.checkpoint.memory import MemorySaver
        >>> agent = create_agent(checkpointer=MemorySaver())
        >>> result = await agent.ainvoke(initial_state)
    """
    from .agent.graph import compile_graph

    return compile_graph(checkpointer=checkpointer)


async def _run_crawl_async(query: str, config: CrawlConfig) -> Any:
    """内部异步执行函数"""
    return await run_crawl(query, config)


def _convert_osint_state_to_output(
    query: str, state: dict[str, Any], include_scraped_content: bool = False
) -> CrawlOutput:
    """
    将OSINT搜索状态转换为CrawlOutput格式

    用于保持与旧API的兼容性

    Args:
        query: 搜索查询
        state: OSINT状态字典
        include_scraped_content: 是否包含抓取的原始HTML和Markdown内容
    """
    import time

    # 提取关键词
    keyword_groups = state.get("keyword_groups", [])
    keywords_used = []
    for group in keyword_groups:
        if hasattr(group, "keywords"):
            keywords_used.extend(group.keywords)
        elif isinstance(group, dict):
            keywords_used.extend(group.get("keywords", []))

    # 提取搜索结果 (优先使用验证后的结果，如果没有则使用去重后的结果)
    results = state.get("validated_results", []) or state.get("deduplicated_results", [])

    # 提取错误信息
    errors = state.get("error_messages", [])

    # 计算执行时间
    metadata = state.get("metadata", {})
    start_time = metadata.get("start_time", time.time())
    execution_time = time.time() - start_time

    # 生成摘要（从分类来源提取）
    summary = None
    classified_sources = state.get("classified_sources", [])
    if classified_sources:
        summaries = []
        for source in classified_sources[:3]:  # 取前3个来源的摘要
            if hasattr(source, "content_summary") and source.content_summary:
                summaries.append(source.content_summary)
            elif isinstance(source, dict) and source.get("content_summary"):
                summaries.append(source["content_summary"])
        if summaries:
            summary = "\n\n".join(summaries)

    # 提取抓取的原始内容（如果启用）
    scraped_contents = []
    if include_scraped_content:
        raw_scraped = state.get("scraped_contents", [])
        for content in raw_scraped:
            if hasattr(content, "model_copy"):
                # Pydantic模型，直接添加
                scraped_contents.append(content)
            elif isinstance(content, dict):
                # 字典格式，转换为ScrapedContent
                from gsac.models.schemas import ScrapedContent

                scraped_contents.append(
                    ScrapedContent(
                        url=content.get("url", ""),
                        title=content.get("title", ""),
                        markdown=content.get("markdown"),
                        html=content.get("html"),
                        metadata=content.get("metadata", {}),
                        scrape_success=content.get("scrape_success", True),
                        error_message=content.get("error_message"),
                    )
                )

    return CrawlOutput(
        query=query,
        keywords_used=keywords_used if keywords_used else [query],
        results=results,
        scraped_contents=scraped_contents,
        total_found=len(results),
        execution_time=execution_time,
        summary=summary,
        errors=errors if errors else None,
    )
