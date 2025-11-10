"""
Firecrawl 任务配置类

提供类型安全的配置管理
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CrawlConfig:
    """网站爬取配置（Crawl API）"""

    # 爬取限制
    limit: int = 100  # 最大页面数
    max_depth: int = 3  # 最大爬取深度

    # 路径过滤
    include_paths: List[str] = field(default_factory=list)  # 包含的路径模式
    exclude_paths: List[str] = field(default_factory=lambda: ['/$'])  # 排除的路径模式（默认排除首页）
    allow_backward_links: bool = False  # 是否允许向后链接

    # Scrape 选项（用于每个爬取的页面）
    only_main_content: bool = False  # v2.1.1: 获取完整HTML
    wait_for: int = 1000  # 等待页面加载时间（毫秒）
    exclude_tags: List[str] = field(default_factory=lambda: [])  # v2.1.1: 不排除任何标签

    # 超时设置
    timeout: int = 300  # 整体爬取超时（秒）
    poll_interval: int = 10  # 状态轮询间隔（秒）

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CrawlConfig':
        """从字典创建配置"""
        return CrawlConfig(
            limit=data.get('limit', 100),
            max_depth=data.get('max_depth', 3),
            include_paths=data.get('include_paths', []),
            exclude_paths=data.get('exclude_paths', ['/$']),  # 默认排除首页
            allow_backward_links=data.get('allow_backward_links', False),
            only_main_content=data.get('only_main_content', False),  # v2.1.1: 默认 False 获取完整HTML
            wait_for=data.get('wait_for', 1000),
            exclude_tags=data.get('exclude_tags', []),  # v2.1.1: 默认空列表
            timeout=data.get('timeout', 300),
            poll_interval=data.get('poll_interval', 10)
        )


@dataclass
class SearchConfig:
    """关键词搜索配置（Search API）"""

    # 搜索参数
    limit: int = 10  # 搜索结果数量
    language: str = "zh"  # 搜索语言

    # 详情页爬取控制
    enable_detail_scrape: bool = True  # 是否启用详情页爬取
    max_concurrent_scrapes: int = 2  # 最大并发爬取数（降低避免被限流）
    scrape_delay: float = 2.0  # 爬取间隔（秒，增加避免被限流）

    # Scrape 选项（用于详情页爬取）
    only_main_content: bool = False  # v2.1.1: 获取完整HTML
    wait_for: int = 3000  # 等待页面加载时间（毫秒，增加确保JS渲染完成）
    exclude_tags: List[str] = field(default_factory=lambda: [])  # v2.1.1: 不排除任何标签
    timeout: int = 120  # 单个页面爬取超时（秒，增加处理慢速页面）

    # 域名过滤
    include_domains: Optional[List[str]] = None  # 白名单：只爬取这些域名
    exclude_domains: List[str] = field(default_factory=lambda: [
        "wikipedia.org",
        "youtube.com",
        "youtu.be"
    ])  # 黑名单：排除这些域名（默认排除维基百科和YouTube）

    # URL过滤选项
    filter_homepage: bool = True  # 是否过滤首页URL

    # 其他选项
    strict_language_filter: bool = True

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SearchConfig':
        """从字典创建配置"""
        # 默认的排除域名列表
        default_exclude_domains = ["wikipedia.org", "youtube.com", "youtu.be"]

        return SearchConfig(
            limit=data.get('limit', 10),
            language=data.get('language', 'zh'),
            enable_detail_scrape=data.get('enable_detail_scrape', True),
            max_concurrent_scrapes=data.get('max_concurrent_scrapes', 2),
            scrape_delay=data.get('scrape_delay', 2.0),
            only_main_content=data.get('only_main_content', False),  # v2.1.1: 默认 False 获取完整HTML
            wait_for=data.get('wait_for', 3000),
            exclude_tags=data.get('exclude_tags', []),  # v2.1.1: 默认空列表
            timeout=data.get('timeout', 120),
            include_domains=data.get('include_domains'),
            exclude_domains=data.get('exclude_domains', default_exclude_domains),
            filter_homepage=data.get('filter_homepage', True),
            strict_language_filter=data.get('strict_language_filter', True)
        )


@dataclass
class ScrapeConfig:
    """单页面爬取配置（Scrape API）"""

    # 内容提取
    only_main_content: bool = False  # v2.1.1: 获取完整HTML
    wait_for: int = 1000

    # 标签过滤
    include_tags: Optional[List[str]] = None
    exclude_tags: List[str] = field(default_factory=lambda: [])  # v2.1.1: 不排除任何标签

    # 超时设置
    timeout: int = 90

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ScrapeConfig':
        """从字典创建配置"""
        return ScrapeConfig(
            only_main_content=data.get('only_main_content', False),  # v2.1.1: 默认 False 获取完整HTML
            wait_for=data.get('wait_for', 1000),
            include_tags=data.get('include_tags'),
            exclude_tags=data.get('exclude_tags', []),  # v2.1.1: 默认空列表
            timeout=data.get('timeout', 90)
        )


class ConfigFactory:
    """配置工厂

    根据任务类型和配置字典创建对应的配置对象
    """

    @staticmethod
    def create_crawl_config(task_config: Dict[str, Any]) -> CrawlConfig:
        """创建爬取配置

        Args:
            task_config: 任务的 crawl_config 字典

        Returns:
            CrawlConfig: 爬取配置对象
        """
        return CrawlConfig.from_dict(task_config)

    @staticmethod
    def create_search_config(task_config: Dict[str, Any]) -> SearchConfig:
        """创建搜索配置

        Args:
            task_config: 任务的 search_config 字典

        Returns:
            SearchConfig: 搜索配置对象
        """
        return SearchConfig.from_dict(task_config)

    @staticmethod
    def create_scrape_config(task_config: Dict[str, Any]) -> ScrapeConfig:
        """创建单页面爬取配置

        Args:
            task_config: 任务的 search_config 字典

        Returns:
            ScrapeConfig: 爬取配置对象
        """
        return ScrapeConfig.from_dict(task_config)

    @staticmethod
    def create_map_scrape_config(task_config: Dict[str, Any]) -> 'MapScrapeConfig':
        """创建 Map + Scrape 配置

        Args:
            task_config: 任务的配置字典（支持 crawl_config 或 search_config）

        Returns:
            MapScrapeConfig: Map + Scrape 配置对象
        """
        from .map_scrape_config import MapScrapeConfig
        return MapScrapeConfig.from_dict(task_config)
