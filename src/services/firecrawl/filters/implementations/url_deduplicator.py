"""
URL 去重过滤器

移除重复的URL和规范化后重复的URL(如带/不带尾部斜杠)。

实现原理:
1. 规范化URL(移除fragment,统一尾部斜杠,移除跟踪参数)
2. 使用集合去重
3. 保留第一次出现的URL

优化策略:
- 使用集合(Set)记录已见URL O(1)
- 可配置跟踪参数移除
- 保持原始顺序
"""

from typing import List, Optional, Set
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from ..base import URLFilter, FilterContext


class URLDeduplicator(URLFilter):
    """URL 去重过滤器

    Example:
        ```python
        # 基础去重
        filter = URLDeduplicator()
        filtered = filter.filter(urls)

        # 移除跟踪参数
        filter = URLDeduplicator(remove_tracking_params=True)
        ```
    """

    # 常见跟踪参数
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'ref', 'source', 'fbclid', 'gclid', 'msclkid',
        '_ga', '_gid', '_hsenc', '_hsmi',
        'mc_cid', 'mc_eid'
    }

    def __init__(
        self,
        remove_tracking_params: bool = True,
        remove_fragment: bool = True,
        unify_trailing_slash: bool = True,
        enabled: bool = True
    ):
        """初始化URL去重过滤器

        Args:
            remove_tracking_params: 是否移除跟踪参数
            remove_fragment: 是否移除fragment(#后面的部分)
            unify_trailing_slash: 是否统一尾部斜杠
            enabled: 是否启用过滤器
        """
        self._remove_tracking_params = remove_tracking_params
        self._remove_fragment = remove_fragment
        self._unify_trailing_slash = unify_trailing_slash
        self._enabled = enabled

    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行URL去重

        Args:
            urls: 待去重的URL列表
            context: 过滤上下文

        Returns:
            List[str]: 去重后的URL列表
        """
        if not self._enabled or not urls:
            return urls

        seen_urls: Set[str] = set()
        unique_urls: List[str] = []

        for url in urls:
            # 规范化URL用于去重判断
            normalized = self._normalize_url(url)

            if normalized not in seen_urls:
                seen_urls.add(normalized)
                # 保留原始URL(不是规范化后的)
                unique_urls.append(url)

        return unique_urls

    def _normalize_url(self, url: str) -> str:
        """规范化URL用于去重

        Args:
            url: 原始URL

        Returns:
            str: 规范化后的URL
        """
        try:
            parsed = urlparse(url)

            # 移除fragment
            if self._remove_fragment:
                parsed = parsed._replace(fragment='')

            # 统一尾部斜杠
            if self._unify_trailing_slash:
                path = parsed.path
                if path and not path.endswith('/') and '.' not in path.split('/')[-1]:
                    parsed = parsed._replace(path=path + '/')

            # 移除跟踪参数
            if self._remove_tracking_params and parsed.query:
                params = parse_qs(parsed.query)
                # 移除跟踪参数
                clean_params = {
                    k: v for k, v in params.items()
                    if k.lower() not in self.TRACKING_PARAMS
                }
                # 重新构建查询字符串
                new_query = urlencode(clean_params, doseq=True)
                parsed = parsed._replace(query=new_query)

            return urlunparse(parsed).lower()

        except Exception:
            # 规范化失败,返回原URL的小写形式
            return url.lower()

    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return "url_deduplicator"

    @property
    def enabled(self) -> bool:
        """过滤器是否启用"""
        return self._enabled

    def get_description(self) -> str:
        """获取过滤器描述"""
        return (
            f"URL去重过滤器 "
            f"(remove_tracking={self._remove_tracking_params}, "
            f"remove_fragment={self._remove_fragment}, "
            f"trailing_slash={self._unify_trailing_slash})"
        )
