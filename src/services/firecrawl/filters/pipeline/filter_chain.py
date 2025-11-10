"""
过滤器链

实现责任链模式,将多个过滤器串联执行,并提供统计功能。

设计模式: Chain of Responsibility Pattern
"""

from typing import List, Optional, Dict
import logging

from ..base import URLFilter, FilterContext


logger = logging.getLogger(__name__)


class FilterChain:
    """过滤器链 - 责任链模式

    按顺序执行多个过滤器,并收集每个过滤器的统计信息。

    Example:
        ```python
        chain = FilterChain()
        chain.add_filter(URLNormalizer())
        chain.add_filter(PathKeywordFilter())
        chain.add_filter(FileTypeFilter())

        filtered_urls = chain.execute(urls, context)
        stats = chain.get_statistics()
        ```
    """

    def __init__(self, name: str = "default_chain"):
        """初始化过滤器链

        Args:
            name: 过滤器链名称
        """
        self._name = name
        self._filters: List[URLFilter] = []
        self._statistics: Dict[str, Dict[str, int]] = {}

    def add_filter(self, url_filter: URLFilter) -> 'FilterChain':
        """添加过滤器到链中

        Args:
            url_filter: URL过滤器实例

        Returns:
            FilterChain: 返回自身,支持链式调用
        """
        self._filters.append(url_filter)
        return self

    def execute(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行过滤器链

        Args:
            urls: 待过滤的URL列表
            context: 过滤上下文

        Returns:
            List[str]: 过滤后的URL列表
        """
        if not urls:
            return urls

        current_urls = urls
        self._statistics = {}

        logger.info(
            f"🔍 开始执行过滤器链 '{self._name}': "
            f"初始URL数={len(urls)}, 过滤器数={len(self._filters)}"
        )

        for url_filter in self._filters:
            if not url_filter.enabled:
                logger.debug(f"⏭️  跳过已禁用的过滤器: {url_filter.get_filter_name()}")
                continue

            before_count = len(current_urls)

            try:
                # 执行过滤
                current_urls = url_filter.filter(current_urls, context)
                after_count = len(current_urls)
                filtered_count = before_count - after_count

                # 记录统计信息
                filter_name = url_filter.get_filter_name()
                self._statistics[filter_name] = {
                    "before": before_count,
                    "after": after_count,
                    "filtered": filtered_count,
                    "filter_rate": filtered_count / before_count if before_count > 0 else 0
                }

                logger.info(
                    f"  ✓ {filter_name}: "
                    f"{before_count} → {after_count} "
                    f"(过滤 {filtered_count}, {filtered_count/before_count*100:.1f}%)"
                )

            except Exception as e:
                logger.error(
                    f"  ✗ 过滤器 {url_filter.get_filter_name()} 执行失败: {e}",
                    exc_info=True
                )
                # 失败时继续使用当前URL列表

        logger.info(
            f"✅ 过滤器链执行完成: "
            f"{len(urls)} → {len(current_urls)} "
            f"(总过滤率 {(len(urls)-len(current_urls))/len(urls)*100:.1f}%)"
        )

        return current_urls

    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """获取过滤统计信息

        Returns:
            Dict: 统计信息字典
                {
                    "filter_name": {
                        "before": 100,
                        "after": 80,
                        "filtered": 20,
                        "filter_rate": 0.2
                    }
                }
        """
        return self._statistics.copy()

    def get_filter_count(self) -> int:
        """获取过滤器数量

        Returns:
            int: 过滤器数量
        """
        return len(self._filters)

    def get_enabled_filter_count(self) -> int:
        """获取启用的过滤器数量

        Returns:
            int: 启用的过滤器数量
        """
        return sum(1 for f in self._filters if f.enabled)

    def clear(self) -> None:
        """清空过滤器链"""
        self._filters.clear()
        self._statistics.clear()

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"FilterChain(name='{self._name}', "
            f"filters={self.get_filter_count()}, "
            f"enabled={self.get_enabled_filter_count()})"
        )
