"""
域名过滤器

根据URL的域名过滤外部链接,支持严格模式和宽松模式。

实现原理:
1. 提取URL域名
2. 与基础域名比较
3. 根据模式决定是否保留

模式说明:
- strict: 只保留完全匹配基础域名的URL
- loose: 保留相同根域名的URL(包括子域名)
"""

from typing import Optional, List
from urllib.parse import urlparse

from ..base import URLFilter, FilterContext


class DomainFilter(URLFilter):
    """域名过滤器

    Example:
        ```python
        # 严格模式(只保留 example.com)
        filter = DomainFilter("https://example.com", mode='strict')

        # 宽松模式(保留 *.example.com)
        filter = DomainFilter("https://example.com", mode='loose')
        ```
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        mode: str = 'loose',
        enabled: bool = True
    ):
        """初始化域名过滤器

        Args:
            base_url: 基础URL(从context中获取或指定)
            mode: 过滤模式 ('strict', 'loose')
            enabled: 是否启用过滤器
        """
        self._base_url = base_url
        self._mode = mode
        self._enabled = enabled
        self._base_domain = self._extract_domain(base_url) if base_url else None
        self._base_root_domain = self._extract_root_domain(self._base_domain) if self._base_domain else None

    def _extract_domain(self, url: str) -> Optional[str]:
        """提取域名

        Args:
            url: URL字符串

        Returns:
            Optional[str]: 域名(如 www.example.com)
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return None

    def _extract_root_domain(self, domain: Optional[str]) -> Optional[str]:
        """提取根域名

        Args:
            domain: 域名(如 www.example.com)

        Returns:
            Optional[str]: 根域名(如 example.com)
        """
        if not domain:
            return None

        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return domain

    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行域名过滤

        Args:
            urls: 待过滤的URL列表
            context: 过滤上下文

        Returns:
            List[str]: 过滤后的URL列表
        """
        if not self._enabled or not urls:
            return urls

        # 从context获取base_url(如果未在init中指定)
        if not self._base_domain and context:
            self._base_domain = self._extract_domain(context.base_url)
            self._base_root_domain = self._extract_root_domain(self._base_domain)

        if not self._base_domain:
            # 无法确定基础域名,保留所有URL
            return urls

        filtered_urls = []

        for url in urls:
            if not self._should_filter(url):
                filtered_urls.append(url)

        return filtered_urls

    def _should_filter(self, url: str) -> bool:
        """判断URL是否应该被过滤

        Args:
            url: URL字符串

        Returns:
            bool: True表示应该过滤,False表示保留
        """
        url_domain = self._extract_domain(url)

        if not url_domain:
            # 无法提取域名,保守策略:保留
            return False

        if self._mode == 'strict':
            # 严格模式:只保留完全匹配的域名
            return url_domain != self._base_domain

        elif self._mode == 'loose':
            # 宽松模式:保留相同根域名
            url_root_domain = self._extract_root_domain(url_domain)
            return url_root_domain != self._base_root_domain

        return False

    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return "domain_filter"

    @property
    def enabled(self) -> bool:
        """过滤器是否启用"""
        return self._enabled

    def get_description(self) -> str:
        """获取过滤器描述"""
        return (
            f"域名过滤器 "
            f"(mode={self._mode}, "
            f"base_domain={self._base_domain})"
        )
