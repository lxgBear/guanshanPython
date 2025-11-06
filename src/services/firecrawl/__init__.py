"""
Firecrawl 服务模块

模块化的 Firecrawl 任务执行系统，支持：
- 网站爬取（Crawl API）
- 关键词搜索 + 详情页爬取（Search API + Scrape API）
- 单页面爬取（Scrape API）

版本: v2.0.0
"""

from .factory import ExecutorFactory
from .executors import (
    TaskExecutor,
    CrawlExecutor,
    SearchExecutor,
    ScrapeExecutor
)

__all__ = [
    'ExecutorFactory',
    'TaskExecutor',
    'CrawlExecutor',
    'SearchExecutor',
    'ScrapeExecutor'
]
