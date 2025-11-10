"""
Firecrawl 配置模块
"""

from .task_config import (
    CrawlConfig,
    SearchConfig,
    ScrapeConfig,
    ConfigFactory
)
from .map_scrape_config import MapScrapeConfig

__all__ = [
    'CrawlConfig',
    'SearchConfig',
    'ScrapeConfig',
    'MapScrapeConfig',
    'ConfigFactory'
]
