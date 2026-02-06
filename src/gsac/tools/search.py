"""
Firecrawl 搜索工具

封装搜索相关的高级功能
"""

from typing import Any
from urllib.parse import urlparse

from ..models.schemas import SearchResult, SearchTask
from .client import FirecrawlClient, get_firecrawl_client


def _extract_domain(url: str) -> str:
    """从 URL 提取域名

    Args:
        url: 完整 URL

    Returns:
        域名（小写，去除 www. 前缀）
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 去除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _extract_published_date(item: Any) -> str | None:
    """从搜索结果项提取发布日期

    Args:
        item: 搜索结果项（对象或字典）

    Returns:
        发布日期字符串，如果未找到则返回 None
    """
    # 尝试多种可能的字段名
    date_fields = [
        "publishedDate",
        "published_date",
        "date",
        "pubDate",
        "datePublished",
        "publish_date",
        "created",
        "createdAt",
        "created_at",
    ]

    for field in date_fields:
        # 尝试从对象属性获取
        if hasattr(item, field):
            val = getattr(item, field, None)
            if val:
                return str(val)
        # 尝试从字典键获取
        if isinstance(item, dict) and field in item:
            val = item.get(field)
            if val:
                return str(val)

    # 尝试从 metadata 中获取
    metadata = getattr(item, "metadata", None) or (item.get("metadata") if isinstance(item, dict) else None)
    if metadata:
        for field in date_fields:
            val = metadata.get(field) if isinstance(metadata, dict) else getattr(metadata, field, None)
            if val:
                return str(val)

    return None


async def execute_search_task(
    task: SearchTask,
    client: FirecrawlClient | None = None,
) -> list[SearchResult]:
    """
    执行单个搜索任务

    Args:
        task: 搜索任务配置
        client: Firecrawl客户端

    Returns:
        搜索结果列表
    """
    if client is None:
        client = get_firecrawl_client()

    try:
        response = client.search(
            query=task.keyword,
            limit=task.limit,
            sources=[task.source] if task.source else None,
            tbs=task.tbs,
            location=task.location,
            # v0.1.1: 添加 scrape_options 以获取完整的 markdown 内容而非仅摘要
            scrape_options={
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        )

        results: list[SearchResult] = []
        data = response.get("data", response)

        # 处理 Firecrawl v2 SearchData 对象
        if hasattr(data, "web") or hasattr(data, "news") or hasattr(data, "images"):
            # SearchData 对象有 .web, .news, .images 属性
            for source_type in ["web", "news", "images"]:
                source_results = getattr(data, source_type, None) or []
                for item in source_results:
                    url = getattr(item, "url", "") or ""
                    results.append(
                        SearchResult(
                            url=url,
                            title=getattr(item, "title", "") or "",
                            description=getattr(item, "description", "") or getattr(item, "snippet", "") or "",
                            content=getattr(item, "markdown", "") or getattr(item, "content", "") or "",
                            source=source_type,
                            keyword=task.keyword,
                            score=0.0,
                            source_domain=_extract_domain(url),
                            published_date=_extract_published_date(item),
                            layer=task.layer,
                        )
                    )
        elif isinstance(data, dict):
            # 处理 web/news/images 分类返回 (dict格式)
            for source_type in ["web", "news", "images"]:
                source_results = data.get(source_type, [])
                for item in source_results:
                    url = item.get("url", "")
                    results.append(
                        SearchResult(
                            url=url,
                            title=item.get("title", ""),
                            description=item.get("description", item.get("snippet", "")),
                            content=item.get("markdown", item.get("content", "")),
                            source=source_type,
                            keyword=task.keyword,
                            score=0.0,
                            source_domain=_extract_domain(url),
                            published_date=_extract_published_date(item),
                            layer=task.layer,
                        )
                    )
        elif isinstance(data, list):
            # 处理扁平列表返回
            for item in data:
                url = item.get("url", "")
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        content=item.get("markdown", item.get("content", "")),
                        source=task.source,
                        keyword=task.keyword,
                        score=0.0,
                        source_domain=_extract_domain(url),
                        published_date=_extract_published_date(item),
                        layer=task.layer,
                    )
                )

        return results

    except Exception as e:
        # 返回空结果，错误信息由上层处理
        raise RuntimeError(f"搜索失败 [{task.keyword}]: {e!s}") from e


def search_sync(
    query: str,
    limit: int = 10,
    sources: list[str] | None = None,
    time_range: str | None = None,
    location: str | None = None,
) -> list[SearchResult]:
    """
    同步搜索接口

    Args:
        query: 搜索查询
        limit: 结果数量限制
        sources: 搜索来源
        time_range: 时间范围 h/d/w/m/y
        location: 地理位置

    Returns:
        搜索结果列表
    """
    client = get_firecrawl_client()
    tbs = f"qdr:{time_range}" if time_range else None

    response = client.search(
        query=query,
        limit=limit,
        sources=sources,
        tbs=tbs,
        location=location,
        # v0.1.1: 添加 scrape_options 以获取完整的 markdown 内容而非仅摘要
        scrape_options={
            "formats": ["markdown"],
            "onlyMainContent": True,
        },
    )

    results: list[SearchResult] = []
    data = response.get("data", response)

    # 处理 Firecrawl v2 SearchData 对象
    if hasattr(data, "web") or hasattr(data, "news") or hasattr(data, "images"):
        # SearchData 对象有 .web, .news, .images 属性
        for source_type in ["web", "news", "images"]:
            source_results = getattr(data, source_type, None) or []
            for item in source_results:
                url = getattr(item, "url", "") or ""
                results.append(
                    SearchResult(
                        url=url,
                        title=getattr(item, "title", "") or "",
                        description=getattr(item, "description", "") or getattr(item, "snippet", "") or "",
                        content=getattr(item, "markdown", "") or getattr(item, "content", "") or "",
                        source=source_type,
                        keyword=query,
                        score=0.0,
                        source_domain=_extract_domain(url),
                        published_date=_extract_published_date(item),
                    )
                )
    elif isinstance(data, dict):
        for source_type in ["web", "news", "images"]:
            source_results = data.get(source_type, [])
            for item in source_results:
                url = item.get("url", "")
                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        description=item.get("description", item.get("snippet", "")),
                        content=item.get("markdown", item.get("content", "")),
                        source=source_type,
                        keyword=query,
                        score=0.0,
                        source_domain=_extract_domain(url),
                        published_date=_extract_published_date(item),
                    )
                )
    elif isinstance(data, list):
        for item in data:
            url = item.get("url", "")
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    content=item.get("markdown", item.get("content", "")),
                    source="web",
                    keyword=query,
                    score=0.0,
                    source_domain=_extract_domain(url),
                    published_date=_extract_published_date(item),
                )
            )

    return results
