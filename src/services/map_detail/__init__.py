"""
Map + Detail 详情页爬取服务模块

该模块实现以下功能：
1. 使用 Firecrawl Map API 获取页面所有链接
2. 通过规则过滤 + LLM 判断筛选出详情页
3. 批量爬取详情页内容并存储到 search_results 表
"""

from .service import MapDetailService, MapDetailConfig, MapDetailStats, MapDetailResult
from .url_filter import UrlFilter, NavigationBlacklist, FilterStats
from .langgraph_filter import LangGraphUrlFilter

__all__ = [
    "MapDetailService",
    "MapDetailConfig",
    "MapDetailStats",
    "MapDetailResult",
    "UrlFilter",
    "NavigationBlacklist",
    "FilterStats",
    "LangGraphUrlFilter",
]
