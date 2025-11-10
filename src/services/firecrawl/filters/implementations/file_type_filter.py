"""
文件类型过滤器

根据URL的文件扩展名过滤掉非网页内容,如PDF、图片、视频、压缩包等。

实现原理:
1. 提取URL路径的文件扩展名
2. 检查扩展名是否在黑名单中
3. 过滤包含黑名单扩展名的URL

优化策略:
- 使用集合(Set)进行快速查找 O(1)
- 预处理扩展名(统一小写,添加点号)
- 支持无扩展名URL判断(通常是网页)
"""

from typing import List, Optional, Set
from urllib.parse import urlparse
import os

from ..base import URLFilter, FilterContext
from ..blacklists import file_extensions


class FileTypeFilter(URLFilter):
    """文件类型过滤器

    Example:
        ```python
        # 使用默认黑名单(过滤所有非HTML文件)
        filter = FileTypeFilter()
        filtered = filter.filter(urls)

        # 使用保守模式(只过滤文档、压缩包、可执行文件)
        filter = FileTypeFilter(mode='conservative')

        # 自定义黑名单
        filter = FileTypeFilter(
            blacklist=['.pdf', '.zip', '.mp4']
        )

        # 只过滤特定类别
        filter = FileTypeFilter(
            categories=['document', 'archive']
        )
        ```
    """

    def __init__(
        self,
        blacklist: Optional[List[str]] = None,
        mode: str = 'default',
        categories: Optional[List[str]] = None,
        allow_no_extension: bool = True,
        enabled: bool = True
    ):
        """初始化文件类型过滤器

        Args:
            blacklist: 自定义扩展名黑名单,如果为None则使用预设模式
            mode: 预设模式 ('default', 'conservative', 'aggressive', 'non_html')
            categories: 要过滤的类别列表 (如 ['document', 'media'])
            allow_no_extension: 是否允许无扩展名的URL(通常是网页)
            enabled: 是否启用过滤器
        """
        self._allow_no_extension = allow_no_extension
        self._enabled = enabled
        self._mode = mode
        self._categories = categories

        # 初始化黑名单
        if blacklist is not None:
            # 使用自定义黑名单
            self._blacklist = self._normalize_blacklist(blacklist)
        elif categories is not None:
            # 使用指定类别
            self._blacklist = self._get_category_blacklist(categories)
        else:
            # 使用预设模式
            self._blacklist = self._get_preset_blacklist(mode)

    def _normalize_blacklist(self, blacklist: List[str]) -> Set[str]:
        """规范化黑名单(确保以.开头,转小写,去重)

        Args:
            blacklist: 原始黑名单列表

        Returns:
            Set[str]: 规范化后的黑名单集合
        """
        normalized = set()
        for ext in blacklist:
            ext = ext.lower()
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized.add(ext)
        return normalized

    def _get_preset_blacklist(self, mode: str) -> Set[str]:
        """获取预设黑名单

        Args:
            mode: 预设模式

        Returns:
            Set[str]: 预设黑名单集合
        """
        mode_map = {
            'default': file_extensions.DEFAULT_BLACKLIST,
            'conservative': file_extensions.CONSERVATIVE_BLACKLIST,
            'aggressive': file_extensions.AGGRESSIVE_BLACKLIST,
            'non_html': file_extensions.NON_HTML_BLACKLIST
        }

        blacklist = mode_map.get(mode, file_extensions.DEFAULT_BLACKLIST)
        return self._normalize_blacklist(blacklist)

    def _get_category_blacklist(self, categories: List[str]) -> Set[str]:
        """根据类别获取黑名单

        Args:
            categories: 类别列表

        Returns:
            Set[str]: 黑名单集合
        """
        extensions = []
        for category in categories:
            try:
                category_exts = file_extensions.get_extensions_by_category(category)
                extensions.extend(category_exts)
            except ValueError:
                # 忽略无效类别
                pass

        return self._normalize_blacklist(extensions)

    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行文件类型过滤

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
            path = parsed.path.lower()

            # 提取文件扩展名
            _, ext = os.path.splitext(path)

            if not ext:
                # 无扩展名
                if self._allow_no_extension:
                    # 无扩展名的URL通常是网页,保留
                    return False
                else:
                    # 不允许无扩展名,过滤
                    return True

            # 检查扩展名是否在黑名单中
            return ext in self._blacklist

        except Exception:
            # 解析失败,保守策略:保留URL
            return False

    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return "file_type_filter"

    @property
    def enabled(self) -> bool:
        """过滤器是否启用"""
        return self._enabled

    def get_description(self) -> str:
        """获取过滤器描述"""
        return (
            f"文件类型过滤器 "
            f"(mode={self._mode}, "
            f"extensions={len(self._blacklist)}, "
            f"allow_no_ext={self._allow_no_extension})"
        )

    def get_blacklist_size(self) -> int:
        """获取黑名单大小

        Returns:
            int: 黑名单扩展名数量
        """
        return len(self._blacklist)

    def add_extension(self, extension: str) -> None:
        """动态添加扩展名到黑名单

        Args:
            extension: 要添加的扩展名(可以带或不带点号)
        """
        extension = extension.lower()
        if not extension.startswith('.'):
            extension = '.' + extension
        self._blacklist.add(extension)

    def remove_extension(self, extension: str) -> bool:
        """从黑名单中移除扩展名

        Args:
            extension: 要移除的扩展名

        Returns:
            bool: True表示成功移除,False表示扩展名不存在
        """
        extension = extension.lower()
        if not extension.startswith('.'):
            extension = '.' + extension

        if extension in self._blacklist:
            self._blacklist.remove(extension)
            return True
        return False

    def get_blacklist(self) -> Set[str]:
        """获取当前黑名单

        Returns:
            Set[str]: 当前黑名单集合(复制)
        """
        return self._blacklist.copy()

    def is_web_page(self, url: str) -> bool:
        """判断URL是否是网页

        Args:
            url: URL字符串

        Returns:
            bool: True表示是网页,False表示是文件
        """
        return file_extensions.is_web_page(url)
