"""即时搜索结果实体模型

v1.3.0 架构重大变更：
- ✅ 移除 search_execution_id 字段（改用映射表）
- ✅ 新增 content_hash 字段（全局去重键）
- ✅ 新增发现统计字段（first_found_at, last_found_at, found_count, unique_searches）
- ✅ 新增 url_normalized 字段（URL规范化）
- ✅ 全局唯一结果，多次搜索共享同一结果记录

v1.4.0 数据源管理支持：
- ✅ 新增 status 字段（支持数据源状态管理）
- ✅ 状态枚举：pending, archived, processing, completed, deleted

设计优势：
- 92.5% 存储空间节省（避免重复存储相同内容）
- 完整的发现历史追踪
- 支持跨搜索结果可见性
- 数据源状态同步管理
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urlunparse
from enum import Enum

# 导入雪花算法ID生成器
from src.infrastructure.id_generator import generate_string_id


class InstantSearchResultStatus(Enum):
    """即时搜索结果状态枚举（v1.5.2 简化版）"""
    PENDING = "pending"         # 待处理：初始状态
    ARCHIVED = "archived"       # 留存：用户标记重要
    DELETED = "deleted"         # 删除：软删除


@dataclass
class InstantSearchResult:
    """
    即时搜索结果实体

    v1.3.0 核心改进：
    - 结果ID全局唯一，不再与特定搜索绑定
    - content_hash 作为去重键（MD5(title + url + content)）
    - 记录发现历史统计信息

    与映射表关系：
    - 一个结果可以被多次搜索发现（1:N 映射关系）
    - 通过 instant_search_result_mappings 表建立关联
    """
    # 主键（雪花算法ID，全局唯一）
    id: str = field(default_factory=generate_string_id)

    # 归属任务（首次发现该结果的任务）
    task_id: str = ""

    # 核心内容字段
    title: str = ""
    url: str = ""
    snippet: Optional[str] = None  # 搜索结果摘要

    # v1.3.0 去重和规范化字段
    content_hash: str = ""  # MD5(title + url + markdown_content)，全局去重键
    url_normalized: str = ""  # 规范化URL（去除查询参数、锚点等）

    # Firecrawl 特定字段
    markdown_content: Optional[str] = None  # Markdown 格式内容
    html_content: Optional[str] = None  # HTML 格式内容

    # 元数据
    source: str = "web"  # 来源：web, news, academic 等
    published_date: Optional[datetime] = None  # 发布日期
    author: Optional[str] = None  # 作者
    language: Optional[str] = None  # 语言
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据

    # 质量指标
    relevance_score: float = 0.0  # 相关性分数
    quality_score: float = 0.0  # 质量分数

    # v1.4.0 数据源管理字段
    status: InstantSearchResultStatus = InstantSearchResultStatus.PENDING  # 数据状态

    # v1.3.0 发现统计字段（核心新增）
    first_found_at: datetime = field(default_factory=datetime.utcnow)  # 首次发现时间
    last_found_at: datetime = field(default_factory=datetime.utcnow)  # 最后发现时间
    found_count: int = 1  # 被找到次数（初始为1）
    unique_searches: int = 1  # 不同搜索数（初始为1）

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """初始化后自动计算content_hash和url_normalized"""
        if not self.content_hash:
            self.content_hash = self._compute_content_hash()

        if not self.url_normalized:
            self.url_normalized = self._normalize_url(self.url)

    def _compute_content_hash(self) -> str:
        """
        计算内容哈希值

        哈希算法：MD5(title + url + markdown_content)
        用于去重判断，相同内容生成相同哈希
        """
        content_str = f"{self.title}||{self.url}||{self.markdown_content or ''}"
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        URL 规范化

        规则：
        1. 统一协议为 https
        2. 移除查询参数（?后面的部分）
        3. 移除锚点（#后面的部分）
        4. 移除末尾斜杠
        5. 统一域名为小写

        示例：
        - http://example.com/page?id=123#section
        - → https://example.com/page
        """
        if not url:
            return ""

        try:
            parsed = urlparse(url)

            # 规范化协议和域名
            normalized_scheme = "https"
            normalized_netloc = parsed.netloc.lower()
            normalized_path = parsed.path.rstrip('/')

            # 重构URL（移除查询参数和锚点）
            normalized_url = urlunparse((
                normalized_scheme,
                normalized_netloc,
                normalized_path,
                '',  # params
                '',  # query
                ''   # fragment
            ))

            return normalized_url

        except Exception:
            # 如果解析失败，返回原始URL
            return url

    def record_new_discovery(self, search_execution_id: str) -> None:
        """
        记录新的发现事件

        当其他搜索再次发现该结果时调用
        更新发现统计信息

        Args:
            search_execution_id: 搜索执行ID（用于映射表）
        """
        self.last_found_at = datetime.utcnow()
        self.found_count += 1
        self.unique_searches += 1
        self.updated_at = datetime.utcnow()

    def mark_as_archived(self) -> None:
        """标记为已留存"""
        self.status = InstantSearchResultStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """标记为已删除（软删除）"""
        self.status = InstantSearchResultStatus.DELETED
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content_hash": self.content_hash,
            "url_normalized": self.url_normalized,
            "markdown_content": self.markdown_content,
            "html_content": self.html_content,
            "source": self.source,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "author": self.author,
            "language": self.language,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score,
            "quality_score": self.quality_score,
            "first_found_at": self.first_found_at.isoformat() if self.first_found_at else None,
            "last_found_at": self.last_found_at.isoformat() if self.last_found_at else None,
            "found_count": self.found_count,
            "unique_searches": self.unique_searches,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary(self) -> Dict[str, Any]:
        """返回摘要信息（轻量级响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet or (self.markdown_content[:200] if self.markdown_content else ""),
            "source": self.source,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "found_count": self.found_count,
            "unique_searches": self.unique_searches
        }


def create_instant_search_result_from_firecrawl(
    task_id: str,
    firecrawl_data: Dict[str, Any],
    search_position: int = 0
) -> InstantSearchResult:
    """
    从 Firecrawl API 响应数据创建即时搜索结果实体

    Args:
        task_id: 任务ID
        firecrawl_data: Firecrawl API 返回的结果数据
        search_position: 搜索结果排名

    Returns:
        InstantSearchResult 实例
    """
    # 提取核心字段
    title = firecrawl_data.get("title", "")
    url = firecrawl_data.get("url", "")
    markdown_content = firecrawl_data.get("markdown", "")
    html_content = firecrawl_data.get("html", "")

    # 提取元数据
    metadata = firecrawl_data.get("metadata", {})

    # 创建实体
    result = InstantSearchResult(
        task_id=task_id,
        title=title,
        url=url,
        snippet=markdown_content[:200] if markdown_content else title,
        markdown_content=markdown_content,
        html_content=html_content,
        source=metadata.get("sourceURL", "web"),
        published_date=metadata.get("publishedDate"),
        author=metadata.get("author"),
        language=metadata.get("language"),
        metadata=metadata,
        relevance_score=metadata.get("relevanceScore", 0.0),
        quality_score=metadata.get("qualityScore", 0.0)
    )

    return result
