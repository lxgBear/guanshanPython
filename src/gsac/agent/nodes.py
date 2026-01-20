"""
OSINT Search LangGraph 节点实现

定义Agent工作流的8个核心节点:
1. parse_intent - 意图解析(6要素)
2. generate_keywords - 分层关键词生成
3. execute_single_search - 单个搜索执行(并行)
4. merge_deduplicate - 合并去重
5. expand_search - 扩展搜索(条件节点)
6. scrape_single_url - 深度抓取(并行)
7. validate_relevance - 相关性验证
8. classify_sources - 来源分类

每个节点都有:
- 完整的日志记录
- 错误处理和降级策略
- 输入输出类型标注
"""

import asyncio
from typing import Any, Literal
from urllib.parse import urlparse

from langgraph.types import Send
from pydantic import BaseModel

from ..llm.prompts import (
    CLASSIFY_SOURCE_PROMPT,
    EXPAND_KEYWORDS_PROMPT,
    INTENT_PARSE_PROMPT,
    KEYWORD_GEN_PROMPT_V2,
    RELEVANCE_VALIDATE_PROMPT,
)
from ..llm.provider import get_llm
from .validation_rules import (
    ValidationConfig,
    calculate_relevance_score,
    get_validation_config,
)
from ..models.schemas import (
    ClassifiedSource,
    KeywordGroup,
    ParsedIntent,
    RelevanceResult,
    ScrapedContent,
    SearchResult,
    SearchTask,
)
from ..models.state import OSINTSearchState
from ..processors.deduplicator import deduplicate_results
from ..tools.scrape import scrape_url
from ..tools.search import execute_search_task
from ..utils.errors import (
    ErrorSeverity,
    NodeError,
    NodeErrorType,
)
from ..utils.logging import (
    get_logger,
    log_node_end,
    log_node_error,
    log_node_fallback,
    log_node_retry,
    log_node_start,
)

# ============================================================================
# 结构化输出模型 (用于LLM with_structured_output)
# ============================================================================


class IntentOutput(BaseModel):
    """意图解析输出结构 (6要素)"""

    investigation_target: str
    time_range: str | None = None
    source_type_constraint: str = "all"
    output_format: str = "summary"
    tool_constraint: str | None = None
    investigation_type: Literal["event", "situation_awareness", "entity_profile"] = (
        "situation_awareness"
    )


class KeywordGroupOutput(BaseModel):
    """单个关键词组输出"""

    keywords: list[str]
    layer: int = 5
    language: Literal["zh", "en", "mixed"] = "mixed"
    search_type: Literal["web", "news"] = "web"
    site_constraint: str | None = None


class KeywordsOutput(BaseModel):
    """关键词生成输出结构"""

    keyword_groups: list[KeywordGroupOutput]


class RelevanceOutput(BaseModel):
    """单条相关性验证输出"""

    url: str
    title: str
    relevance: Literal["keep", "downgrade", "discard"]
    reason: str
    matched_elements: list[str] = []
    confidence: float = 0.5


class RelevanceListOutput(BaseModel):
    """相关性验证列表输出"""

    results: list[RelevanceOutput]


class ClassifiedSourceOutput(BaseModel):
    """单条来源分类输出"""

    url: str
    title: str
    category: Literal["official", "local_mainstream", "intl_mainstream", "think_tank", "other"]
    credibility_score: float
    time_confidence: Literal["HIGH", "MEDIUM", "LOW", "REJECTED"] = "MEDIUM"
    content_summary: str = ""
    relevance_status: Literal["keep", "downgrade"] = "keep"
    source_domain: str = ""
    published_date: str | None = None


class ClassifiedSourceListOutput(BaseModel):
    """来源分类列表输出"""

    sources: list[ClassifiedSourceOutput]


class ExpandedKeywordsOutput(BaseModel):
    """扩展关键词输出"""

    keywords: list[str]


# ============================================================================
# 节点1: parse_intent - 意图解析(6要素)
# ============================================================================


async def parse_intent(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点1: 解析用户查询意图(6要素)

    输入: user_query
    输出: parsed_intent

    6要素:
    - investigation_target: 调查对象
    - time_range: 时间范围
    - source_type_constraint: 信息源约束
    - output_format: 输出格式
    - tool_constraint: 工具限制
    - investigation_type: 调查类型
    """
    logger = get_logger("parse_intent")
    start_time = log_node_start(logger, "parse_intent", ["user_query"])

    query = state.get("user_query", "")

    # 输入验证
    if not query or not query.strip():
        log_node_error(
            logger,
            "parse_intent",
            NodeError(
                error_type=NodeErrorType.INVALID_INPUT,
                message="user_query为空或无效",
                severity=ErrorSeverity.ERROR,
                node_name="parse_intent",
                recoverable=False,
            ),
        )
        raise NodeError(
            error_type=NodeErrorType.INVALID_INPUT,
            message="user_query为空或无效",
            severity=ErrorSeverity.ERROR,
            node_name="parse_intent",
            recoverable=False,
        )

    max_retries = 3
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            llm = get_llm()
            chain = INTENT_PARSE_PROMPT | llm.with_structured_output(IntentOutput)
            result: IntentOutput = await chain.ainvoke({"query": query})

            # 构建 ParsedIntent
            intent = ParsedIntent(
                investigation_target=result.investigation_target,
                time_range=result.time_range,
                source_type_constraint=result.source_type_constraint,
                output_format=result.output_format,
                tool_constraint=result.tool_constraint,
                investigation_type=result.investigation_type,
            )

            log_node_end(
                logger,
                "parse_intent",
                ["parsed_intent"],
                start_time,
                {"investigation_target": intent.investigation_target},
            )

            return {
                "parsed_intent": intent,
                "messages": [f"[parse_intent] 解析完成: {intent.investigation_target}"],
            }

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                log_node_retry(logger, "parse_intent", attempt + 1, max_retries, e)
                await asyncio.sleep(2**attempt)  # 指数退避
            else:
                log_node_error(logger, "parse_intent", e, {"query": query[:100]})

    # 降级处理: 使用基础意图解析
    log_node_fallback(
        logger,
        "parse_intent",
        f"LLM失败: {last_error}",
        "使用基础意图解析",
    )

    fallback_intent = _fallback_parse_intent(query)

    log_node_end(
        logger,
        "parse_intent",
        ["parsed_intent"],
        start_time,
        {"fallback": True},
    )

    return {
        "parsed_intent": fallback_intent,
        "error_messages": [f"意图解析LLM失败，使用降级解析: {last_error}"],
        "messages": [f"[parse_intent] 降级解析: {fallback_intent.investigation_target}"],
    }


def _fallback_parse_intent(query: str) -> ParsedIntent:
    """LLM失败时的降级意图解析"""
    return ParsedIntent(
        investigation_target=query,
        time_range=None,
        source_type_constraint="all",
        output_format="summary",
        tool_constraint=None,
        investigation_type="situation_awareness",
    )


# ============================================================================
# 节点2: generate_keywords - 分层关键词生成
# ============================================================================


async def generate_keywords(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点2: 生成分层关键词

    输入: parsed_intent
    输出: keyword_groups

    分层策略 (Layer 0-5):
    - Layer 0: 官方来源
    - Layer 1: 本地主流媒体
    - Layer 2: 区域媒体
    - Layer 3: 国际主流
    - Layer 4: 智库/学术
    - Layer 5: 百科/档案
    """
    logger = get_logger("generate_keywords")
    start_time = log_node_start(logger, "generate_keywords", ["parsed_intent"])

    intent = state.get("parsed_intent")

    if not intent:
        log_node_error(
            logger,
            "generate_keywords",
            NodeError(
                error_type=NodeErrorType.MISSING_REQUIRED_FIELD,
                message="parsed_intent为空",
                severity=ErrorSeverity.ERROR,
                node_name="generate_keywords",
                recoverable=False,
            ),
        )
        raise NodeError(
            error_type=NodeErrorType.MISSING_REQUIRED_FIELD,
            message="parsed_intent为空",
            severity=ErrorSeverity.ERROR,
            node_name="generate_keywords",
            recoverable=False,
        )

    max_retries = 3
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            llm = get_llm()
            # 使用V2版本的关键词生成Prompt，避免site: OR链和确保实体名称出现
            chain = KEYWORD_GEN_PROMPT_V2 | llm.with_structured_output(KeywordsOutput)

            result: KeywordsOutput = await chain.ainvoke(
                {
                    "investigation_target": intent.investigation_target,
                    "time_range": intent.time_range or "无限制",
                    "source_type_constraint": intent.source_type_constraint,
                    "investigation_type": intent.investigation_type,
                    "tool_constraint": intent.tool_constraint or "无",
                }
            )

            # 转换为 KeywordGroup 模型
            keyword_groups = []
            for group in result.keyword_groups:
                kg = KeywordGroup(
                    keywords=group.keywords,
                    layer=group.layer,
                    language=group.language,
                    search_type=group.search_type,
                    site_constraint=group.site_constraint,
                )
                keyword_groups.append(kg)

            log_node_end(
                logger,
                "generate_keywords",
                ["keyword_groups"],
                start_time,
                {"group_count": len(keyword_groups)},
            )

            return {
                "keyword_groups": keyword_groups,
                "messages": [f"[generate_keywords] 生成 {len(keyword_groups)} 组关键词"],
            }

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                log_node_retry(logger, "generate_keywords", attempt + 1, max_retries, e)
                await asyncio.sleep(2**attempt)
            else:
                log_node_error(logger, "generate_keywords", e)

    # 降级处理
    log_node_fallback(
        logger,
        "generate_keywords",
        f"LLM失败: {last_error}",
        "使用基础关键词生成",
    )

    fallback_groups = _fallback_generate_keywords(intent)

    log_node_end(
        logger,
        "generate_keywords",
        ["keyword_groups"],
        start_time,
        {"fallback": True},
    )

    return {
        "keyword_groups": fallback_groups,
        "error_messages": [f"关键词生成LLM失败，使用降级生成: {last_error}"],
        "messages": ["[generate_keywords] 降级生成关键词"],
    }


def _fallback_generate_keywords(intent: ParsedIntent) -> list[KeywordGroup]:
    """LLM失败时的降级关键词生成"""
    base_keyword = intent.investigation_target
    return [
        KeywordGroup(
            keywords=[base_keyword],
            layer=5,
            language="mixed",
            search_type="web",
            site_constraint=None,
        )
    ]


# ============================================================================
# 时间范围转换函数
# ============================================================================


def _convert_time_range_to_tbs(time_range: str | None) -> str | None:
    """
    将意图时间范围转换为Firecrawl tbs参数

    支持的格式:
    - "2025-11-11" -> "cdr:1,cd_min:11/11/2025,cd_max:11/11/2025" (精确日期)
    - "2025-11" -> "cdr:1,cd_min:11/1/2025,cd_max:11/30/2025" (年月)
    - "past_week" -> "qdr:w" (相对时间)
    - None -> None

    Args:
        time_range: 意图中的时间范围字符串

    Returns:
        Firecrawl tbs 参数字符串
    """
    import re
    from datetime import datetime, timedelta

    if not time_range:
        return None

    # 精确日期: 2025-11-11
    if re.match(r"^\d{4}-\d{2}-\d{2}$", time_range):
        parts = time_range.split("-")
        date_str = f"{parts[1]}/{parts[2]}/{parts[0]}"
        return f"cdr:1,cd_min:{date_str},cd_max:{date_str}"

    # 年月: 2025-11
    if re.match(r"^\d{4}-\d{2}$", time_range):
        year, month = time_range.split("-")
        year_int = int(year)
        month_int = int(month)

        # 计算月末日期
        if month_int == 12:
            end_day = 31
        else:
            next_month = datetime(year_int, month_int + 1, 1)
            end_day = (next_month - timedelta(days=1)).day

        return f"cdr:1,cd_min:{month}/1/{year},cd_max:{month}/{end_day}/{year}"

    # 相对时间
    time_map = {
        "past_hour": "qdr:h",
        "past_day": "qdr:d",
        "past_week": "qdr:w",
        "past_month": "qdr:m",
        "past_year": "qdr:y",
        "last_hour": "qdr:h",
        "last_day": "qdr:d",
        "last_week": "qdr:w",
        "last_month": "qdr:m",
        "last_year": "qdr:y",
    }

    return time_map.get(time_range.lower(), "qdr:m")


# ============================================================================
# 并行搜索分发函数
# ============================================================================


def fan_out_search(state: OSINTSearchState) -> list[Send]:
    """
    并行搜索分发 (V2 修复版)

    将关键词组转换为搜索任务并分发给并行执行

    修复:
    - 使用 _convert_time_range_to_tbs 正确转换时间范围
    - 不再使用 site: OR 链
    - site_constraint 正确处理为单个域名
    """
    keyword_groups = state.get("keyword_groups", [])
    intent = state.get("parsed_intent")

    # 修复: 从意图中获取时间范围并转换
    time_range = intent.time_range if intent else None
    tbs = _convert_time_range_to_tbs(time_range)

    sends = []
    for group in keyword_groups:
        # 为每个关键词创建搜索任务
        for keyword in group.keywords:
            # 构建完整的搜索关键词
            # 修复: 如果有 site_constraint，正确添加 site: 前缀
            search_keyword = keyword
            if group.site_constraint and group.site_constraint.strip():
                # 确保只有一个 site: 约束，不是 OR 链
                site = group.site_constraint.strip()
                if not site.startswith("site:"):
                    site = f"site:{site}"
                search_keyword = f"{site} {keyword}"

            task = SearchTask(
                keyword=search_keyword,
                source=group.search_type,
                limit=10,
                tbs=tbs,  # 修复: 使用转换后的时间参数
                site_constraint=group.site_constraint,
                layer=group.layer,
            )

            sends.append(Send("execute_single_search", {"task": task}))

    return sends


# ============================================================================
# 节点3: execute_single_search - 单个搜索执行(并行)
# ============================================================================


async def execute_single_search(state: dict[str, Any]) -> dict[str, Any]:
    """
    节点3: 执行单个搜索任务

    输入: task (SearchTask)
    输出: raw_results (支持并行聚合)

    支持并行Fan-out执行，结果通过 operator.add 自动合并
    """
    logger = get_logger("execute_single_search")
    task: SearchTask = state["task"]

    start_time = log_node_start(
        logger,
        "execute_single_search",
        ["task"],
        {"keyword": task.keyword, "layer": task.layer},
    )

    max_retries = 3
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            results = await execute_search_task(task)

            # 添加layer信息到每个结果
            for r in results:
                r.layer = task.layer

            log_node_end(
                logger,
                "execute_single_search",
                ["raw_results"],
                start_time,
                {"result_count": len(results), "keyword": task.keyword},
            )

            return {"raw_results": results}

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                log_node_retry(logger, "execute_single_search", attempt + 1, max_retries, e)
                await asyncio.sleep(2**attempt)
            else:
                log_node_error(
                    logger,
                    "execute_single_search",
                    e,
                    {"keyword": task.keyword},
                )

    # 搜索失败返回空结果，不阻塞其他并行搜索
    log_node_fallback(
        logger,
        "execute_single_search",
        f"搜索失败: {last_error}",
        "返回空结果",
    )

    return {
        "raw_results": [],
        "error_messages": [f"搜索失败 [{task.keyword}]: {last_error}"],
    }


# ============================================================================
# 节点4: merge_deduplicate - 合并去重
# ============================================================================


async def merge_deduplicate(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点4: 合并去重搜索结果

    输入: raw_results (来自并行搜索的聚合结果)
    输出: deduplicated_results

    去重策略:
    - URL精确去重(标准化后)
    - 标题相似度去重(阈值0.8)
    """
    logger = get_logger("merge_deduplicate")
    start_time = log_node_start(logger, "merge_deduplicate", ["raw_results"])

    raw_results = state.get("raw_results", [])

    if not raw_results:
        log_node_end(
            logger,
            "merge_deduplicate",
            ["deduplicated_results"],
            start_time,
            {"input_count": 0, "output_count": 0},
        )
        return {
            "deduplicated_results": [],
            "messages": ["[merge_deduplicate] 无原始结果"],
        }

    try:
        # 过滤无效结果
        valid_results = []
        for r in raw_results:
            if r.url and r.title:
                valid_results.append(r)
            else:
                logger.warning(
                    "invalid_result_skipped",
                    url=r.url if r else None,
                    title=r.title if r else None,
                )

        # 执行去重
        deduplicated = deduplicate_results(valid_results, similarity_threshold=0.8)

        log_node_end(
            logger,
            "merge_deduplicate",
            ["deduplicated_results"],
            start_time,
            {"input_count": len(raw_results), "output_count": len(deduplicated)},
        )

        return {
            "deduplicated_results": deduplicated,
            "messages": [f"[merge_deduplicate] {len(raw_results)} → {len(deduplicated)} 条结果"],
        }

    except Exception as e:
        log_node_error(logger, "merge_deduplicate", e)
        # 降级: 返回原始结果
        return {
            "deduplicated_results": raw_results[:50],  # 限制数量
            "error_messages": [f"去重失败: {e}"],
        }


# ============================================================================
# 条件路由: route_by_source_count
# ============================================================================


def route_by_source_count(
    state: OSINTSearchState,
) -> Literal["expand_search", "deep_scrape"]:
    """
    条件路由: 根据来源数量决定下一步

    - 少于3个来源 → expand_search (扩展搜索)
    - 3个或更多来源 → deep_scrape (深度抓取)
    - 最大迭代次数(3次)后强制进入抓取

    注意: 返回值必须与 graph.py 中的条件边映射键匹配
    """
    logger = get_logger("route_by_source_count")

    deduplicated = state.get("deduplicated_results", [])
    iteration = state.get("iteration_count", 0)

    count = len(deduplicated)

    # 防止无限循环
    if iteration >= 3:
        logger.info(
            "route_decision",
            route="deep_scrape",
            reason="max_iterations_reached",
            iteration=iteration,
            source_count=count,
        )
        return "deep_scrape"

    if count < 3:
        logger.info(
            "route_decision",
            route="expand_search",
            reason="insufficient_sources",
            source_count=count,
        )
        return "expand_search"

    logger.info(
        "route_decision",
        route="deep_scrape",
        reason="sufficient_sources",
        source_count=count,
    )
    return "deep_scrape"


# ============================================================================
# 节点5: expand_search - 扩展搜索
# ============================================================================


async def expand_search(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点5: 扩展搜索

    输入: parsed_intent, iteration_count
    输出: keyword_groups (更宽泛的关键词)

    当搜索结果不足时，放宽约束条件扩大搜索范围
    """
    logger = get_logger("expand_search")
    start_time = log_node_start(logger, "expand_search", ["parsed_intent", "iteration_count"])

    intent = state.get("parsed_intent")
    iteration = state.get("iteration_count", 0)
    existing_groups = state.get("keyword_groups", [])

    # 收集已使用的关键词
    used_keywords = []
    for group in existing_groups:
        used_keywords.extend(group.keywords)

    if not intent:
        log_node_error(
            logger,
            "expand_search",
            NodeError(
                error_type=NodeErrorType.MISSING_REQUIRED_FIELD,
                message="parsed_intent为空",
                severity=ErrorSeverity.ERROR,
                node_name="expand_search",
            ),
        )
        raise NodeError(
            error_type=NodeErrorType.MISSING_REQUIRED_FIELD,
            message="parsed_intent为空",
            severity=ErrorSeverity.ERROR,
            node_name="expand_search",
        )

    try:
        llm = get_llm()
        chain = EXPAND_KEYWORDS_PROMPT | llm.with_structured_output(ExpandedKeywordsOutput)

        result: ExpandedKeywordsOutput = await chain.ainvoke(
            {
                "investigation_target": intent.investigation_target,
                "iteration_count": iteration + 1,
                "used_keywords": ", ".join(used_keywords) if used_keywords else "无",
            }
        )

        # 创建Layer 5关键词组
        expanded_group = KeywordGroup(
            keywords=result.keywords,
            layer=5,
            language="mixed",
            search_type="web",
            site_constraint=None,
        )

        log_node_end(
            logger,
            "expand_search",
            ["keyword_groups", "iteration_count"],
            start_time,
            {"new_keywords": len(result.keywords)},
        )

        return {
            "keyword_groups": [expanded_group],
            "iteration_count": iteration + 1,
            "messages": [f"[expand_search] 迭代{iteration + 1}: 扩展搜索"],
        }

    except Exception as e:
        log_node_error(logger, "expand_search", e)
        log_node_fallback(logger, "expand_search", str(e), "使用简单扩展策略")

        # 降级: 简单扩展策略
        fallback_group = _fallback_expand_search(intent, iteration)

        return {
            "keyword_groups": [fallback_group],
            "iteration_count": iteration + 1,
            "error_messages": [f"扩展搜索LLM失败: {e}"],
            "messages": ["[expand_search] 降级扩展搜索"],
        }


def _fallback_expand_search(intent: ParsedIntent, iteration: int) -> KeywordGroup:
    """LLM失败时的降级扩展策略"""
    base = intent.investigation_target

    # 根据迭代次数使用不同策略
    expansion_strategies = [
        [base],
        [base, f"{base} news", f"{base} report"],
        [base, f"{base} latest", f"{base} update"],
    ]

    keywords = expansion_strategies[min(iteration, 2)]

    return KeywordGroup(
        keywords=keywords,
        layer=5,
        language="mixed",
        search_type="web",
        site_constraint=None,
    )


# ============================================================================
# 并行抓取分发函数
# ============================================================================


def fan_out_scrape(state: OSINTSearchState) -> list[Send]:
    """
    并行抓取分发

    将去重后的URL分发给并行抓取
    """
    deduplicated = state.get("deduplicated_results", [])

    # 限制最大抓取数量
    max_scrape = 10
    urls_to_scrape = deduplicated[:max_scrape]

    return [Send("scrape_single_url", {"url": r.url, "title": r.title}) for r in urls_to_scrape]


# ============================================================================
# 节点6: scrape_single_url - 深度抓取(并行)
# ============================================================================


async def scrape_single_url(state: dict[str, Any]) -> dict[str, Any]:
    """
    节点6: 抓取单个URL内容

    输入: url, title
    输出: scraped_contents (支持并行聚合)

    支持并行执行，结果通过 operator.add 自动合并
    """
    logger = get_logger("scrape_single_url")
    url = state.get("url", "")
    title = state.get("title", "")

    start_time = log_node_start(logger, "scrape_single_url", ["url"], {"url": url[:100]})

    if not url:
        log_node_end(logger, "scrape_single_url", [], start_time, {"skipped": True})
        return {"scraped_contents": []}

    max_retries = 2
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            content = await scrape_url(url)

            if content and (content.markdown or content.html):
                log_node_end(
                    logger,
                    "scrape_single_url",
                    ["scraped_contents"],
                    start_time,
                    {"url": url[:50], "has_content": True},
                )
                return {"scraped_contents": [content]}
            else:
                logger.warning("empty_content", url=url[:100])
                return {"scraped_contents": []}

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                log_node_retry(logger, "scrape_single_url", attempt + 1, max_retries, e)
                await asyncio.sleep(2**attempt)
            else:
                log_node_error(logger, "scrape_single_url", e, {"url": url[:100]})

    # 抓取失败，记录但不阻塞
    log_node_fallback(logger, "scrape_single_url", str(last_error), "跳过该URL")

    # 返回失败记录
    failed_content = ScrapedContent(
        url=url,
        title=title,
        markdown=None,
        html=None,
        scrape_success=False,
        error_message=str(last_error),
    )

    return {
        "scraped_contents": [failed_content],
        "error_messages": [f"抓取失败 [{url[:50]}]: {last_error}"],
    }


# ============================================================================
# 节点7: validate_relevance - 相关性验证 (V3 硬规则实现)
# ============================================================================


async def validate_relevance(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点7: 验证相关性 (V3 硬规则实现)

    输入: scraped_contents, parsed_intent
    输出: relevance_results, validated_results, discarded_count, confidence_score

    V3 验证策略 (混合模式):
    1. 硬规则预过滤 - 快速排除明显无关结果
    2. 置信度评分 - 基于标记匹配计算分数
    3. 阈值判定 - 根据置信度决定 keep/downgrade/discard

    相比旧版改进:
    - 不再完全依赖LLM，硬规则保证基础质量
    - 降级时不再保留所有结果，仍使用硬规则过滤
    - 添加 confidence_score 到输出
    """
    logger = get_logger("validate_relevance")
    start_time = log_node_start(logger, "validate_relevance", ["scraped_contents", "parsed_intent"])

    scraped = state.get("scraped_contents", [])
    intent = state.get("parsed_intent")
    deduplicated = state.get("deduplicated_results", [])

    if not scraped and not deduplicated:
        log_node_end(
            logger,
            "validate_relevance",
            ["relevance_results", "validated_results", "discarded_count"],
            start_time,
            {"input_count": 0},
        )
        return {
            "relevance_results": [],
            "validated_results": [],
            "discarded_count": 0,
            "confidence_score": 0.0,
            "messages": ["[validate_relevance] 无内容需要验证"],
        }

    # 获取验证配置 (根据意图动态选择)
    config = get_validation_config(intent)

    # 提取来源约束 (用于媒体过滤)
    source_constraint = intent.source_type_constraint if intent else None

    # 构建待验证内容映射
    content_map = _build_content_map(scraped, deduplicated)

    relevance_results: list[RelevanceResult] = []
    validated_results: list[SearchResult] = []
    downgraded_results: list[SearchResult] = []
    discarded_count = 0
    total_score = 0.0

    for r in deduplicated:
        url = r.url
        title = r.title
        content = content_map.get(url, r.description or "")[:2000]  # 截断长内容

        # V3 硬规则验证 (新增 source_constraint 参数)
        score, decision, reason = calculate_relevance_score(
            title=title,
            content=content,
            url=url,
            config=config,
            source_constraint=source_constraint,
        )

        # 回写分数到 SearchResult
        r.score = score

        relevance_results.append(
            RelevanceResult(
                url=url,
                title=title,
                relevance=decision,
                reason=f"[V3硬规则] {reason}",
                confidence=score,
                matched_elements=[],  # 硬规则不提取匹配要素
            )
        )

        if decision == "keep":
            validated_results.append(r)
            total_score += score
            logger.info(
                "result_validated",
                url=url[:80],
                decision="keep",
                score=round(score, 2),
            )
        elif decision == "downgrade":
            downgraded_results.append(r)
            total_score += score * 0.5  # 降级结果贡献一半分数
            logger.info(
                "result_downgraded",
                url=url[:80],
                decision="downgrade",
                score=round(score, 2),
            )
        else:
            discarded_count += 1
            logger.info(
                "result_discarded",
                url=url[:80],
                decision="discard",
                reason=reason[:100],
            )

    # 合并结果 (保留结果 + 降级结果)
    all_validated = validated_results + downgraded_results

    # 计算整体置信度
    confidence_score = total_score / len(deduplicated) if deduplicated else 0.0

    log_node_end(
        logger,
        "validate_relevance",
        ["relevance_results", "validated_results", "discarded_count", "confidence_score"],
        start_time,
        {
            "keep": len(validated_results),
            "downgrade": len(downgraded_results),
            "discard": discarded_count,
            "confidence": round(confidence_score, 2),
        },
    )

    return {
        "relevance_results": relevance_results,
        "validated_results": all_validated,
        "discarded_count": discarded_count,
        "confidence_score": confidence_score,
        "messages": [
            f"[validate_relevance] V3验证: {len(validated_results)} 保留, "
            f"{len(downgraded_results)} 降级, {discarded_count} 丢弃"
        ],
    }


def _build_content_map(
    scraped: list[ScrapedContent], deduplicated: list[SearchResult]
) -> dict[str, str]:
    """构建 URL 到内容的映射

    优先使用抓取的 markdown 内容，否则使用搜索结果的 description

    Args:
        scraped: 抓取的内容列表
        deduplicated: 去重后的搜索结果

    Returns:
        URL -> 内容文本的映射
    """
    content_map: dict[str, str] = {}

    # 首先添加抓取内容
    for content in scraped:
        if content.scrape_success and content.markdown:
            content_map[content.url] = content.markdown

    # 补充搜索结果的描述
    for r in deduplicated:
        if r.url not in content_map and r.description:
            content_map[r.url] = r.description

    return content_map


def _build_contents_string(scraped: list[ScrapedContent], deduplicated: list[SearchResult]) -> str:
    """构建待验证内容字符串 (用于LLM验证)"""
    parts = []

    # 添加抓取内容
    for i, content in enumerate(scraped[:20], 1):
        if content.scrape_success and content.markdown:
            parts.append(f"{i}. URL: {content.url}")
            parts.append(f"   标题: {content.title}")
            parts.append(f"   内容摘要: {content.markdown[:500]}...")
            parts.append("")

    # 如果没有抓取内容，使用搜索结果
    if not parts:
        for i, r in enumerate(deduplicated[:20], 1):
            parts.append(f"{i}. URL: {r.url}")
            parts.append(f"   标题: {r.title}")
            if r.description:
                parts.append(f"   描述: {r.description}")
            parts.append("")

    return "\n".join(parts)


# ============================================================================
# 节点8: classify_sources - 来源分类
# ============================================================================


async def classify_sources(state: OSINTSearchState) -> dict[str, Any]:
    """
    节点8: 来源分类和可信度评估

    输入: validated_results, scraped_contents
    输出: classified_sources, confidence_score

    分类体系:
    - official: 政府/官方机构
    - local_mainstream: 本地主流媒体
    - intl_mainstream: 国际主流媒体
    - think_tank: 智库/学术
    - other: 其他
    """
    logger = get_logger("classify_sources")
    start_time = log_node_start(
        logger, "classify_sources", ["validated_results", "scraped_contents"]
    )

    validated = state.get("validated_results", [])
    scraped = state.get("scraped_contents", [])
    intent = state.get("parsed_intent")
    relevance_results = state.get("relevance_results", [])

    if not validated:
        log_node_end(
            logger,
            "classify_sources",
            ["classified_sources", "confidence_score"],
            start_time,
            {"input_count": 0},
        )
        return {
            "classified_sources": [],
            "confidence_score": 0.0,
            "messages": ["[classify_sources] 无内容需要分类"],
        }

    # 构建内容字符串
    contents_str = _build_classify_contents_string(validated, scraped, relevance_results)

    try:
        llm = get_llm()
        chain = CLASSIFY_SOURCE_PROMPT | llm.with_structured_output(ClassifiedSourceListOutput)

        result: ClassifiedSourceListOutput = await chain.ainvoke(
            {
                "time_range": intent.time_range if intent else "无限制",
                "source_type_constraint": intent.source_type_constraint if intent else "all",
                "contents": contents_str,
            }
        )

        # 空指针检查 (修复 LLM 返回 None 的情况)
        if result is None or not hasattr(result, "sources") or result.sources is None:
            raise ValueError("LLM 返回无效结果，触发降级分类")

        # 转换为 ClassifiedSource 模型
        classified = []
        total_credibility = 0.0

        for s in result.sources:
            cs = ClassifiedSource(
                url=s.url,
                title=s.title,
                category=s.category,
                credibility_score=s.credibility_score,
                time_confidence=s.time_confidence,
                content_summary=s.content_summary,
                relevance_status=s.relevance_status,
                source_domain=s.source_domain or _extract_domain(s.url),
                published_date=s.published_date,
            )
            classified.append(cs)
            total_credibility += s.credibility_score

        # 计算整体置信度
        confidence_score = total_credibility / len(classified) if classified else 0.0

        log_node_end(
            logger,
            "classify_sources",
            ["classified_sources", "confidence_score"],
            start_time,
            {"classified_count": len(classified), "confidence": confidence_score},
        )

        return {
            "classified_sources": classified,
            "confidence_score": confidence_score,
            "messages": [
                f"[classify_sources] 分类 {len(classified)} 条来源, 置信度 {confidence_score:.2f}"
            ],
        }

    except Exception as e:
        log_node_error(logger, "classify_sources", e)
        log_node_fallback(logger, "classify_sources", str(e), "使用基于域名的简单分类")

        # 降级: 基于域名的简单分类
        classified = _fallback_classify_sources(validated, relevance_results)
        confidence_score = (
            sum(c.credibility_score for c in classified) / len(classified) if classified else 0.0
        )

        log_node_end(
            logger,
            "classify_sources",
            ["classified_sources", "confidence_score"],
            start_time,
            {"fallback": True},
        )

        return {
            "classified_sources": classified,
            "confidence_score": confidence_score,
            "error_messages": [f"来源分类LLM失败: {e}"],
            "messages": ["[classify_sources] 降级分类"],
        }


def _build_classify_contents_string(
    validated: list[SearchResult],
    scraped: list[ScrapedContent],
    relevance_results: list[RelevanceResult],
) -> str:
    """构建待分类内容字符串"""
    parts = []

    # 创建URL到相关性状态的映射
    relevance_map = {r.url: r.relevance for r in relevance_results}

    for i, r in enumerate(validated[:20], 1):
        parts.append(f"{i}. URL: {r.url}")
        parts.append(f"   标题: {r.title}")
        parts.append(f"   域名: {_extract_domain(r.url)}")
        parts.append(f"   相关性: {relevance_map.get(r.url, 'keep')}")

        # 添加抓取内容摘要(如果有)
        for s in scraped:
            if s.url == r.url and s.markdown:
                parts.append(f"   内容摘要: {s.markdown[:300]}...")
                break

        parts.append("")

    return "\n".join(parts)


def _extract_domain(url: str) -> str:
    """从URL提取域名"""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def _fallback_classify_sources(
    validated: list[SearchResult],
    relevance_results: list[RelevanceResult],
) -> list[ClassifiedSource]:
    """基于域名的简单分类"""
    official_patterns = [".gov", ".edu", ".org", ".un.org", ".int"]
    mainstream_patterns = [
        "bbc.com",
        "cnn.com",
        "reuters.com",
        "nytimes.com",
        "washingtonpost.com",
        "xinhuanet.com",
        "people.com.cn",
        "chinadaily.com.cn",
    ]
    think_tank_patterns = [".edu", "brookings", "rand", "csis", "cfr.org"]

    # 相关性映射
    relevance_map = {r.url: r.relevance for r in relevance_results}

    classified = []
    for r in validated:
        domain = _extract_domain(r.url).lower()

        # 判断分类
        if any(p in domain for p in official_patterns):
            category = "official"
            score = 0.9
        elif any(p in domain for p in mainstream_patterns):
            category = "intl_mainstream"
            score = 0.8
        elif any(p in domain for p in think_tank_patterns):
            category = "think_tank"
            score = 0.85
        else:
            category = "other"
            score = 0.5

        relevance_status = relevance_map.get(r.url, "keep")
        if relevance_status == "discard":
            relevance_status = "downgrade"

        classified.append(
            ClassifiedSource(
                url=r.url,
                title=r.title,
                category=category,
                credibility_score=score,
                time_confidence="MEDIUM",
                content_summary="",
                relevance_status=relevance_status,
                source_domain=domain,
                published_date=r.published_date,
            )
        )

    return classified


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # OSINT核心节点
    "parse_intent",
    "generate_keywords",
    "execute_single_search",
    "merge_deduplicate",
    "expand_search",
    "scrape_single_url",
    "validate_relevance",
    "classify_sources",
    # 路由和分发函数
    "fan_out_search",
    "fan_out_scrape",
    "route_by_source_count",
]
