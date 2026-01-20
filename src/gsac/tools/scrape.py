"""
Firecrawl 抓取工具

封装页面抓取相关的高级功能
"""

from ..models.schemas import ScrapedContent
from .client import FirecrawlClient, get_firecrawl_client


async def scrape_url(
    url: str,
    formats: list[str] | None = None,
    timeout: int = 30000,
    client: FirecrawlClient | None = None,
) -> ScrapedContent:
    """
    抓取单个URL

    Args:
        url: 目标URL
        formats: 输出格式 ["markdown", "html"]
        timeout: 超时时间(毫秒)
        client: Firecrawl客户端

    Returns:
        抓取的内容
    """
    if client is None:
        client = get_firecrawl_client()

    if formats is None:
        formats = ["markdown"]

    try:
        response = client.scrape(url=url, formats=formats, timeout=timeout)
        data = response.get("data", response)

        return ScrapedContent(
            url=url,
            title=data.get("title", data.get("metadata", {}).get("title", "")),
            markdown=data.get("markdown"),
            html=data.get("html"),
            metadata=data.get("metadata", {}),
        )

    except Exception as e:
        # 返回带错误标记的结果
        return ScrapedContent(
            url=url,
            title="",
            markdown=None,
            html=None,
            metadata={"error": str(e)},
        )


async def scrape_urls(
    urls: list[str],
    formats: list[str] | None = None,
    timeout: int = 30000,
    client: FirecrawlClient | None = None,
) -> list[ScrapedContent]:
    """
    批量抓取多个URL

    Args:
        urls: URL列表
        formats: 输出格式
        timeout: 超时时间(毫秒)
        client: Firecrawl客户端

    Returns:
        抓取结果列表
    """
    results: list[ScrapedContent] = []

    for url in urls:
        content = await scrape_url(
            url=url,
            formats=formats,
            timeout=timeout,
            client=client,
        )
        results.append(content)

    return results


def scrape_url_sync(
    url: str,
    formats: list[str] | None = None,
    timeout: int = 30000,
) -> ScrapedContent:
    """
    同步抓取单个URL

    Args:
        url: 目标URL
        formats: 输出格式
        timeout: 超时时间(毫秒)

    Returns:
        抓取的内容
    """
    client = get_firecrawl_client()

    if formats is None:
        formats = ["markdown"]

    try:
        response = client.scrape(url=url, formats=formats, timeout=timeout)
        data = response.get("data", response)

        return ScrapedContent(
            url=url,
            title=data.get("title", data.get("metadata", {}).get("title", "")),
            markdown=data.get("markdown"),
            html=data.get("html"),
            metadata=data.get("metadata", {}),
        )

    except Exception as e:
        return ScrapedContent(
            url=url,
            title="",
            markdown=None,
            html=None,
            metadata={"error": str(e)},
        )
