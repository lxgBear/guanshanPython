"""
Firecrawl 任务执行器模块

v2.1.0: 添加 MultilangSearchExecutor 多语言搜索执行器
v4.30.0: 添加 MapDetailExecutor Map+Detail 详情页爬取执行器
"""

from ..base import TaskExecutor
from .search_executor import SearchExecutor
from .crawl_executor import CrawlExecutor
from .scrape_executor import ScrapeExecutor
from .map_scrape_executor import MapScrapeExecutor
from .multilang_search_executor import MultilangSearchExecutor
from .map_detail_executor import MapDetailExecutor

__all__ = [
    'TaskExecutor',
    'SearchExecutor',
    'CrawlExecutor',
    'ScrapeExecutor',
    'MapScrapeExecutor',
    'MultilangSearchExecutor',
    'MapDetailExecutor',
]
