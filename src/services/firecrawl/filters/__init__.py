"""
URL 过滤模块

提供模块化、可扩展的 URL 过滤功能,用于 Map API 返回的 URL 列表过滤。

主要组件:
- base: 核心接口(URLFilter, FilterContext)
- implementations: 具体过滤器实现
- config: 过滤配置
- pipeline: 过滤管道(FilterChain, PipelineBuilder)
- blacklists: 黑名单定义

Example:
    ```python
    from src.services.firecrawl.filters import PipelineBuilder, FilterContext

    # 构建默认过滤管道
    pipeline = PipelineBuilder.build_default_pipeline("https://example.com")

    # 创建过滤上下文
    context = FilterContext(
        base_url="https://example.com",
        task_id="task_123"
    )

    # 执行过滤
    filtered_urls = pipeline.execute(urls, context)
    ```
"""

from .base import URLFilter, FilterContext, URLNormalizer
from .pipeline import FilterChain, PipelineBuilder
from .implementations import (
    PathKeywordFilter,
    FileTypeFilter,
    DomainFilter,
    URLDeduplicator
)

__all__ = [
    # 核心接口
    'URLFilter',
    'FilterContext',
    'URLNormalizer',
    # 管道
    'FilterChain',
    'PipelineBuilder',
    # 具体实现
    'PathKeywordFilter',
    'FileTypeFilter',
    'DomainFilter',
    'URLDeduplicator',
]
