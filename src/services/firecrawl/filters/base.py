"""
URL 过滤器核心接口

定义 URL 过滤系统的抽象基类和上下文对象,遵循 SOLID 原则中的:
- 单一职责原则 (SRP): 每个过滤器只负责一种过滤逻辑
- 开闭原则 (OCP): 对扩展开放,对修改封闭
- 接口隔离原则 (ISP): 最小化接口依赖
- 依赖倒置原则 (DIP): 依赖抽象而非具体实现
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class FilterContext:
    """过滤上下文 - 传递过滤所需的上下文信息

    Attributes:
        base_url: 基础URL(用于域名过滤和相对路径判断)
        task_id: 任务ID(用于日志和追踪)
        config: 配置信息(可选的扩展配置)
        metadata: 元数据字典(用于存储过滤过程中的临时信息)
    """
    base_url: str
    task_id: str
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class URLFilter(ABC):
    """URL 过滤器抽象基类

    所有具体过滤器必须继承此类并实现抽象方法。
    遵循策略模式,每个过滤器是一个独立的策略。

    设计原则:
    1. 单一职责: 每个过滤器只负责一种过滤逻辑
    2. 可组合性: 通过 FilterChain 组合多个过滤器
    3. 可配置性: 支持启用/禁用控制
    4. 可测试性: 接口清晰,易于单元测试

    Example:
        ```python
        class MyFilter(URLFilter):
            def filter(self, urls: List[str], context: Optional[FilterContext] = None) -> List[str]:
                return [url for url in urls if self._is_valid(url)]

            def get_filter_name(self) -> str:
                return "my_filter"
        ```
    """

    @abstractmethod
    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行过滤逻辑

        Args:
            urls: 待过滤的URL列表
            context: 过滤上下文(可选)

        Returns:
            List[str]: 过滤后的URL列表
        """
        pass

    @abstractmethod
    def get_filter_name(self) -> str:
        """获取过滤器名称

        用于日志记录、统计分析和调试。
        应返回一个唯一的、描述性的名称。

        Returns:
            str: 过滤器名称
        """
        pass

    @property
    def enabled(self) -> bool:
        """过滤器是否启用

        子类可以重写此属性以支持动态启用/禁用。

        Returns:
            bool: True表示启用,False表示禁用
        """
        return True

    def get_description(self) -> str:
        """获取过滤器描述

        子类可以重写此方法以提供更详细的描述信息。

        Returns:
            str: 过滤器描述
        """
        return f"过滤器: {self.get_filter_name()}"


class URLNormalizer(URLFilter):
    """URL 规范化过滤器

    负责将URL标准化为一致的格式,包括:
    1. 移除 URL fragment (#后面的部分)
    2. 统一尾部斜杠
    3. URL解码
    4. 协议统一(可选)

    这是过滤管道中的第一个过滤器,确保后续过滤器处理统一格式的URL。
    """

    def __init__(
        self,
        remove_fragment: bool = True,
        unify_trailing_slash: bool = True,
        url_decode: bool = True,
        enabled: bool = True
    ):
        """初始化 URL 规范化过滤器

        Args:
            remove_fragment: 是否移除 fragment
            unify_trailing_slash: 是否统一尾部斜杠
            url_decode: 是否进行 URL 解码
            enabled: 是否启用过滤器
        """
        self._remove_fragment = remove_fragment
        self._unify_trailing_slash = unify_trailing_slash
        self._url_decode = url_decode
        self._enabled = enabled

    def filter(
        self,
        urls: List[str],
        context: Optional[FilterContext] = None
    ) -> List[str]:
        """执行 URL 规范化

        Args:
            urls: 待规范化的URL列表
            context: 过滤上下文

        Returns:
            List[str]: 规范化后的URL列表
        """
        if not self._enabled:
            return urls

        from urllib.parse import urlparse, urlunparse, unquote

        normalized_urls = []

        for url in urls:
            try:
                parsed = urlparse(url)

                # 1. 移除 fragment
                if self._remove_fragment:
                    parsed = parsed._replace(fragment='')

                # 2. 统一尾部斜杠(路径以 / 结尾)
                if self._unify_trailing_slash:
                    path = parsed.path
                    if path and not path.endswith('/') and '.' not in path.split('/')[-1]:
                        # 如果路径不以 / 结尾,且最后一段不包含文件扩展名,则添加 /
                        parsed = parsed._replace(path=path + '/')

                # 3. URL 解码
                normalized_url = urlunparse(parsed)
                if self._url_decode:
                    normalized_url = unquote(normalized_url)

                normalized_urls.append(normalized_url)

            except Exception:
                # 解析失败,保留原URL
                normalized_urls.append(url)

        return normalized_urls

    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return "url_normalizer"

    @property
    def enabled(self) -> bool:
        """过滤器是否启用"""
        return self._enabled

    def get_description(self) -> str:
        """获取过滤器描述"""
        return (
            f"URL规范化过滤器 "
            f"(fragment={self._remove_fragment}, "
            f"trailing_slash={self._unify_trailing_slash}, "
            f"decode={self._url_decode})"
        )
