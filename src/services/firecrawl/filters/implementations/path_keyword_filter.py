"""
路径关键词过滤器

根据URL路径中的关键词过滤掉无用链接,如登录页面、管理后台、API端点等。

实现原理:
1. 提取URL路径部分
2. 检查路径是否包含黑名单关键词
3. 过滤包含黑名单关键词的URL

优化策略:
- 使用集合(Set)进行快速查找 O(1)
- 预编译正则表达式(如果使用)
- 批量处理以提高效率
"""

from typing import List, Optional, Set
from urllib.parse import urlparse

from ..base import URLFilter, FilterContext
from ..blacklists import path_keywords


class PathKeywordFilter(URLFilter):
    """路径关键词过滤器

    Example:
        ```python
        # 使用默认黑名单
        filter = PathKeywordFilter()
        filtered = filter.filter(urls)

        # 使用保守模式(只过滤高优先级)
        filter = PathKeywordFilter(mode='conservative')

        # 自定义黑名单
        filter = PathKeywordFilter(
            blacklist=['login', 'admin', 'api']
        )
        ```
    """

    def __init__(
        self,
        blacklist: Optional[List[str]] = None,
        mode: str = 'default',
        case_sensitive: bool = False,
        enabled: bool = True
    ):
        """初始化路径关键词过滤器

        Args:
            blacklist: 自定义黑名单列表,如果为None则使用预设模式
            mode: 预设模式 ('default', 'conservative', 'aggressive')
            case_sensitive: 是否区分大小写
            enabled: 是否启用过滤器
        """
        self._case_sensitive = case_sensitive
        self._enabled = enabled
        self._mode = mode

        # 初始化黑名单
        if blacklist is not None:
            # 使用自定义黑名单
            self._blacklist = self._normalize_blacklist(blacklist)
        else:
            # 使用预设模式
            self._blacklist = self._get_preset_blacklist(mode)

    def _normalize_blacklist(self, blacklist: List[str]) -> Set[str]:
        """规范化黑名单(转小写,去重)

        Args:
            blacklist: 原始黑名单列表

        Returns:
            Set[str]: 规范化后的黑名单集合
        """
        if self._case_sensitive:
            return set(blacklist)
        return set(keyword.lower() for keyword in blacklist)

    def _get_preset_blacklist(self, mode: str) -> Set[str]:
        """获取预设黑名单

        Args:
            mode: 预设模式

        Returns:
            Set[str]: 预设黑名单集合
        """
        mode_map = {
            'default': path_keywords.DEFAULT_BLACKLIST,
            'conservative': path_keywords.CONSERVATIVE_BLACKLIST,
            'aggressive': path_keywords.AGGRESSIVE_BLACKLIST
        }

        blacklist = mode_map.get(mode, path_keywords.DEFAULT_BLACKLIST)
        return self._normalize_blacklist(blacklist)

    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行路径关键词过滤

        Args:
            urls: 待过滤的URL列表
            context: 过滤上下文

        Returns:
            List[str]: 过滤后的URL列表
        """
        if not self._enabled or not urls:
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
        try:
            parsed = urlparse(url)
            path = parsed.path

            # 处理大小写
            if not self._case_sensitive:
                path = path.lower()

            # 检查路径是否包含黑名单关键词
            for keyword in self._blacklist:
                if keyword in path:
                    return True

            # 检查查询参数(对于分页等参数)
            if parsed.query and not self._case_sensitive:
                query = parsed.query.lower()
            else:
                query = parsed.query

            for keyword in self._blacklist:
                if '=' in keyword and keyword in query:
                    return True

            return False

        except Exception:
            # 解析失败,保守策略:保留URL
            return False

    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return "path_keyword_filter"

    @property
    def enabled(self) -> bool:
        """过滤器是否启用"""
        return self._enabled

    def get_description(self) -> str:
        """获取过滤器描述"""
        return (
            f"路径关键词过滤器 "
            f"(mode={self._mode}, "
            f"keywords={len(self._blacklist)}, "
            f"case_sensitive={self._case_sensitive})"
        )

    def get_blacklist_size(self) -> int:
        """获取黑名单大小

        Returns:
            int: 黑名单关键词数量
        """
        return len(self._blacklist)

    def add_keyword(self, keyword: str) -> None:
        """动态添加关键词到黑名单

        Args:
            keyword: 要添加的关键词
        """
        if not self._case_sensitive:
            keyword = keyword.lower()
        self._blacklist.add(keyword)

    def remove_keyword(self, keyword: str) -> bool:
        """从黑名单中移除关键词

        Args:
            keyword: 要移除的关键词

        Returns:
            bool: True表示成功移除,False表示关键词不存在
        """
        if not self._case_sensitive:
            keyword = keyword.lower()

        if keyword in self._blacklist:
            self._blacklist.remove(keyword)
            return True
        return False

    def get_blacklist(self) -> Set[str]:
        """获取当前黑名单

        Returns:
            Set[str]: 当前黑名单集合(复制)
        """
        return self._blacklist.copy()
