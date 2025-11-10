"""
Map + Scrape 模式配置

定义 Map API + Scrape API 组合模式的配置参数
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class MapScrapeConfig:
    """
    Map + Scrape 模式配置

    Map API 用于快速发现URL，Scrape API 用于获取页面内容，
    结合时间过滤实现精确的内容爬取。

    Attributes:
        # Map API 配置
        search: 搜索关键词，过滤URL或标题包含该关键词的页面
        map_limit: Map API 返回URL数量限制，默认5000（API最大值）
        max_scrape_urls: 最大爬取URL数量，默认500，None表示不限制（v2.1.3）

        # 时间过滤配置
        start_date: 起始日期，只保留此日期之后发布的内容
        end_date: 结束日期，只保留此日期之前发布的内容

        # Scrape API 配置
        max_concurrent_scrapes: 最大并发Scrape数量，默认5
        scrape_delay: Scrape请求间隔（秒），默认0.5秒
        only_main_content: 只提取主要内容，默认True
        exclude_tags: 排除的HTML标签列表，默认['nav', 'footer', 'header', 'aside']
        timeout: Scrape超时时间（秒），默认90秒

        # 错误处理配置
        allow_partial_failure: 允许部分失败，默认True
        min_success_rate: 最低成功率，默认0.8（80%）
    """

    # Map API 配置
    search: Optional[str] = None
    map_limit: int = 5000

    # v2.1.3: URL数量限制配置
    max_scrape_urls: Optional[int] = 500  # 最大爬取URL数量，默认500(None表示不限制)

    # 时间过滤配置
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Scrape API 配置
    max_concurrent_scrapes: int = 5
    scrape_delay: float = 0.5
    only_main_content: bool = False  # v2.1.1: 改为False获取完整HTML
    wait_for: int = 500  # v2.1.1 Hotfix: 从3000ms改为500ms，避免 "waitFor must not exceed half of timeout" 错误
    exclude_tags: List[str] = field(
        default_factory=lambda: []  # v2.1.1: 改为空列表，不排除任何标签，获取完整HTML
    )
    timeout: int = 90

    # 错误处理配置
    allow_partial_failure: bool = True
    min_success_rate: float = 0.8

    # v2.1.1: 去重配置
    enable_dedup: bool = True  # 是否启用URL去重，默认启用

    def has_time_filter(self) -> bool:
        """检查是否配置了时间过滤"""
        return self.start_date is not None or self.end_date is not None

    def is_valid(self) -> bool:
        """验证配置是否有效"""
        # 验证 map_limit 范围
        if self.map_limit <= 0 or self.map_limit > 5000:
            return False

        # 验证 max_scrape_urls (v2.1.3)
        if self.max_scrape_urls is not None and self.max_scrape_urls <= 0:
            return False

        # 验证并发数量
        if self.max_concurrent_scrapes <= 0:
            return False

        # 验证延迟时间
        if self.scrape_delay < 0:
            return False

        # 验证超时时间
        if self.timeout <= 0:
            return False

        # 验证成功率
        if not (0 < self.min_success_rate <= 1.0):
            return False

        # 验证时间范围
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                return False

        return True

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'search': self.search,
            'map_limit': self.map_limit,
            'max_scrape_urls': self.max_scrape_urls,  # v2.1.3
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'max_concurrent_scrapes': self.max_concurrent_scrapes,
            'scrape_delay': self.scrape_delay,
            'only_main_content': self.only_main_content,
            'wait_for': self.wait_for,
            'exclude_tags': self.exclude_tags,
            'timeout': self.timeout,
            'allow_partial_failure': self.allow_partial_failure,
            'min_success_rate': self.min_success_rate,
            'enable_dedup': self.enable_dedup
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MapScrapeConfig':
        """从字典创建配置对象"""
        # 处理日期字符串
        start_date = data.get('start_date')
        if start_date and isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)

        end_date = data.get('end_date')
        if end_date and isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        return cls(
            search=data.get('search'),
            map_limit=data.get('map_limit', 5000),
            max_scrape_urls=data.get('max_scrape_urls', 500),  # v2.1.3
            start_date=start_date,
            end_date=end_date,
            max_concurrent_scrapes=data.get('max_concurrent_scrapes', 5),
            scrape_delay=data.get('scrape_delay', 0.5),
            only_main_content=data.get('only_main_content', False),  # v2.1.1: 默认 False 获取完整HTML
            wait_for=data.get('wait_for', 500),  # v2.1.1 Hotfix: 从3000改为500ms
            exclude_tags=data.get('exclude_tags', []),  # v2.1.1: 默认空列表
            timeout=data.get('timeout', 90),
            allow_partial_failure=data.get('allow_partial_failure', True),
            min_success_rate=data.get('min_success_rate', 0.8),
            enable_dedup=data.get('enable_dedup', True)
        )

    def __repr__(self) -> str:
        """字符串表示"""
        time_filter = ""
        if self.has_time_filter():
            parts = []
            if self.start_date:
                parts.append(f"start={self.start_date.date()}")
            if self.end_date:
                parts.append(f"end={self.end_date.date()}")
            time_filter = f", time_filter=({', '.join(parts)})"

        search_filter = f", search='{self.search}'" if self.search else ""

        return (
            f"MapScrapeConfig("
            f"map_limit={self.map_limit}"
            f"{search_filter}"
            f"{time_filter}, "
            f"concurrent={self.max_concurrent_scrapes}, "
            f"success_rate>={self.min_success_rate})"
        )
