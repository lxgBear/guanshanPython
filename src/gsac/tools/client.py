"""
Firecrawl 客户端封装

提供统一的Firecrawl API访问接口，支持重试和错误处理
"""

from functools import lru_cache
from typing import Any

from firecrawl import Firecrawl
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import get_settings


class FirecrawlClient:
    """Firecrawl客户端封装"""

    def __init__(self, api_key: str | None = None):
        """
        初始化Firecrawl客户端

        Args:
            api_key: API密钥，默认从配置读取
        """
        settings = get_settings()
        self._api_key = api_key or settings.firecrawl_api_key
        if not self._api_key:
            raise ValueError("Firecrawl API key is required")
        self._client = Firecrawl(api_key=self._api_key)

    @property
    def client(self) -> Firecrawl:
        """获取底层Firecrawl客户端"""
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def search(
        self,
        query: str,
        limit: int = 10,
        sources: list[str] | None = None,
        tbs: str | None = None,
        location: str | None = None,
        categories: list[str] | None = None,
        scrape_options: dict | None = None,
    ) -> dict[str, Any]:
        """
        执行搜索

        Args:
            query: 搜索查询
            limit: 结果数量限制
            sources: 搜索来源 ["web", "news", "images"]
            tbs: 时间过滤 "qdr:h", "qdr:d", "qdr:w", "qdr:m", "qdr:y"
            location: 地理位置
            categories: 类别过滤 ["github", "research", "pdf"]
            scrape_options: 抓取选项

        Returns:
            搜索结果字典
        """
        kwargs: dict[str, Any] = {"query": query, "limit": limit}

        if sources:
            kwargs["sources"] = sources
        if tbs:
            kwargs["tbs"] = tbs
        if location:
            kwargs["location"] = location
        if categories:
            kwargs["categories"] = categories
        if scrape_options:
            kwargs["scrape_options"] = scrape_options

        result = self._client.search(**kwargs)
        return result if isinstance(result, dict) else {"data": result}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def scrape(
        self,
        url: str,
        formats: list[str] | None = None,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        抓取单个URL

        Args:
            url: 目标URL
            formats: 输出格式 ["markdown", "html"]
            timeout: 超时时间(毫秒)

        Returns:
            抓取结果字典
        """
        kwargs: dict[str, Any] = {"url": url}

        if formats:
            kwargs["formats"] = formats
        kwargs["timeout"] = timeout

        result = self._client.scrape(**kwargs)
        return result if isinstance(result, dict) else {"data": result}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def crawl(
        self,
        url: str,
        limit: int = 100,
        scrape_options: dict | None = None,
    ) -> dict[str, Any]:
        """
        爬取网站

        Args:
            url: 起始URL
            limit: 页面数量限制
            scrape_options: 抓取选项

        Returns:
            爬取结果字典
        """
        kwargs: dict[str, Any] = {"url": url, "limit": limit}

        if scrape_options:
            kwargs["scrape_options"] = scrape_options

        result = self._client.crawl(**kwargs)
        return result if isinstance(result, dict) else {"data": result}


@lru_cache
def get_firecrawl_client(api_key: str | None = None) -> FirecrawlClient:
    """获取Firecrawl客户端单例"""
    return FirecrawlClient(api_key=api_key)
