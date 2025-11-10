"""
管道构建器

提供便捷的API来构建预配置的过滤管道。

设计模式: Builder Pattern
"""

from typing import Optional

from .filter_chain import FilterChain
from ..base import URLNormalizer
from ..implementations import (
    PathKeywordFilter,
    FileTypeFilter,
    DomainFilter,
    URLDeduplicator
)


class PipelineBuilder:
    """管道构建器 - 建造者模式

    Example:
        ```python
        # 构建默认管道
        pipeline = PipelineBuilder.build_default_pipeline("https://example.com")

        # 构建自定义管道
        pipeline = (PipelineBuilder("custom_pipeline")
                   .add_normalizer()
                   .add_path_filter(mode='conservative')
                   .add_file_type_filter(mode='aggressive')
                   .build())
        ```
    """

    def __init__(self, name: str = "custom_pipeline"):
        """初始化管道构建器

        Args:
            name: 管道名称
        """
        self._chain = FilterChain(name=name)

    def add_normalizer(
        self,
        remove_fragment: bool = True,
        unify_trailing_slash: bool = True,
        url_decode: bool = True
    ) -> 'PipelineBuilder':
        """添加 URL 规范化过滤器

        Args:
            remove_fragment: 是否移除 fragment
            unify_trailing_slash: 是否统一尾部斜杠
            url_decode: 是否进行 URL 解码

        Returns:
            PipelineBuilder: 返回自身,支持链式调用
        """
        self._chain.add_filter(URLNormalizer(
            remove_fragment=remove_fragment,
            unify_trailing_slash=unify_trailing_slash,
            url_decode=url_decode
        ))
        return self

    def add_path_filter(
        self,
        mode: str = 'default',
        blacklist: Optional[list] = None
    ) -> 'PipelineBuilder':
        """添加路径关键词过滤器

        Args:
            mode: 预设模式 ('default', 'conservative', 'aggressive')
            blacklist: 自定义黑名单(优先于mode)

        Returns:
            PipelineBuilder: 返回自身,支持链式调用
        """
        self._chain.add_filter(PathKeywordFilter(
            blacklist=blacklist,
            mode=mode
        ))
        return self

    def add_file_type_filter(
        self,
        mode: str = 'default',
        blacklist: Optional[list] = None,
        categories: Optional[list] = None
    ) -> 'PipelineBuilder':
        """添加文件类型过滤器

        Args:
            mode: 预设模式 ('default', 'conservative', 'aggressive', 'non_html')
            blacklist: 自定义黑名单(优先于mode)
            categories: 要过滤的类别列表

        Returns:
            PipelineBuilder: 返回自身,支持链式调用
        """
        self._chain.add_filter(FileTypeFilter(
            blacklist=blacklist,
            mode=mode,
            categories=categories
        ))
        return self

    def add_domain_filter(
        self,
        base_url: Optional[str] = None,
        mode: str = 'loose'
    ) -> 'PipelineBuilder':
        """添加域名过滤器

        Args:
            base_url: 基础URL(从context中获取或指定)
            mode: 过滤模式 ('strict', 'loose')

        Returns:
            PipelineBuilder: 返回自身,支持链式调用
        """
        self._chain.add_filter(DomainFilter(
            base_url=base_url,
            mode=mode
        ))
        return self

    def add_deduplicator(
        self,
        remove_tracking_params: bool = True
    ) -> 'PipelineBuilder':
        """添加 URL 去重过滤器

        Args:
            remove_tracking_params: 是否移除跟踪参数

        Returns:
            PipelineBuilder: 返回自身,支持链式调用
        """
        self._chain.add_filter(URLDeduplicator(
            remove_tracking_params=remove_tracking_params
        ))
        return self

    def build(self) -> FilterChain:
        """构建过滤器链

        Returns:
            FilterChain: 构建完成的过滤器链
        """
        return self._chain

    @classmethod
    def build_default_pipeline(cls, base_url: str) -> FilterChain:
        """构建默认过滤管道

        默认管道包含:
        1. URL 规范化
        2. 路径关键词过滤(默认模式)
        3. 文件类型过滤(默认模式)
        4. 域名过滤(宽松模式)
        5. URL 去重

        Args:
            base_url: 基础URL

        Returns:
            FilterChain: 默认过滤器链
        """
        return (cls("default_pipeline")
                .add_normalizer()
                .add_path_filter(mode='default')
                .add_file_type_filter(mode='default')
                .add_domain_filter(base_url=base_url, mode='loose')
                .add_deduplicator()
                .build())

    @classmethod
    def build_conservative_pipeline(cls, base_url: str) -> FilterChain:
        """构建保守过滤管道

        只过滤高优先级的无用链接。

        Args:
            base_url: 基础URL

        Returns:
            FilterChain: 保守过滤器链
        """
        return (cls("conservative_pipeline")
                .add_normalizer()
                .add_path_filter(mode='conservative')
                .add_file_type_filter(mode='conservative')
                .add_domain_filter(base_url=base_url, mode='loose')
                .add_deduplicator()
                .build())

    @classmethod
    def build_aggressive_pipeline(cls, base_url: str) -> FilterChain:
        """构建激进过滤管道

        过滤所有可能的无用链接。

        Args:
            base_url: 基础URL

        Returns:
            FilterChain: 激进过滤器链
        """
        return (cls("aggressive_pipeline")
                .add_normalizer()
                .add_path_filter(mode='aggressive')
                .add_file_type_filter(mode='aggressive')
                .add_domain_filter(base_url=base_url, mode='strict')
                .add_deduplicator()
                .build())
