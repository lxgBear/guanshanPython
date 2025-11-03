"""数据源存档数据实体模型

数据源存档系统的核心实体，用于永久保存原始数据的完整快照。

设计要点：
- 独立集合存储：data_source_archived_data
- 完整内容保存：存储完整content字段（非200字符截断）
- 触发时机：数据源确认（DRAFT → CONFIRMED）时自动存档
- 事务保证：使用MongoDB事务保证原子性
- 数据来源：支持scheduled和instant两种类型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

# 导入雪花算法ID生成器
from src.infrastructure.id_generator import generate_string_id


@dataclass
class ArchivedData:
    """
    存档数据实体

    核心功能：
    - 保存原始数据的完整快照（content完整，非截断）
    - 独立生命周期，不受原始数据表清理影响
    - 支持scheduled和instant两种数据类型
    - 记录存档元信息和追溯信息
    """
    # 主键（雪花算法ID，全局唯一）
    id: str = field(default_factory=generate_string_id)

    # 关联关系
    data_source_id: str = ""          # 所属数据源ID
    original_data_id: str = ""        # 原始数据ID（UUID或雪花ID）
    data_type: str = ""               # scheduled | instant

    # 核心内容字段（完整快照）
    title: str = ""
    url: str = ""
    content: str = ""                 # 【关键】完整内容，非200字符截断
    snippet: Optional[str] = None     # 摘要

    # 发布信息
    published_date: Optional[datetime] = None  # 发布日期

    # Firecrawl 特定字段
    markdown_content: Optional[str] = None  # Markdown 格式内容
    html_content: Optional[str] = None      # HTML 格式内容

    # 类型特定字段（JSON存储）
    type_specific_fields: Dict[str, Any] = field(default_factory=dict)
    # scheduled类型：search_rank, relevance_score, task_id等
    # instant类型：content_hash, url_normalized, found_count等

    # 通用元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 存档元信息
    archived_at: datetime = field(default_factory=datetime.utcnow)
    archived_by: str = ""              # 存档操作者
    archived_reason: str = "confirm"   # confirm | manual

    # 原始数据追溯信息
    original_created_at: Optional[datetime] = None  # 原始数据创建时间
    original_status: str = ""                       # 原始数据状态快照

    # 系统字段
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ==========================================
    # 工厂方法：从SearchResult创建
    # ==========================================

    @classmethod
    def from_search_result(
        cls,
        search_result: Any,  # SearchResult类型
        data_source_id: str,
        archived_by: str,
        archived_reason: str = "confirm"
    ) -> "ArchivedData":
        """
        从SearchResult（定时搜索结果）创建存档数据

        Args:
            search_result: SearchResult实体
            data_source_id: 所属数据源ID
            archived_by: 存档操作者
            archived_reason: 存档原因（confirm | manual）

        Returns:
            ArchivedData实例
        """
        # 提取scheduled类型特定字段
        type_specific = {
            "search_rank": search_result.search_position if hasattr(search_result, 'search_position') else None,
            "relevance_score": search_result.relevance_score,
            "quality_score": search_result.quality_score,
            "task_id": str(search_result.task_id) if isinstance(search_result.task_id, UUID) else search_result.task_id,
            "source": search_result.source,
            "author": search_result.author,
            "language": search_result.language,
        }

        return cls(
            data_source_id=data_source_id,
            original_data_id=str(search_result.id) if isinstance(search_result.id, UUID) else search_result.id,
            data_type="scheduled",
            title=search_result.title,
            url=search_result.url,
            content=search_result.content or "",  # 完整内容
            snippet=search_result.snippet,
            published_date=search_result.published_date,
            markdown_content=getattr(search_result, 'markdown_content', None),
            html_content=getattr(search_result, 'html_content', None),
            type_specific_fields=type_specific,
            metadata=search_result.metadata if hasattr(search_result, 'metadata') else {},
            archived_at=datetime.utcnow(),
            archived_by=archived_by,
            archived_reason=archived_reason,
            original_created_at=search_result.created_at if hasattr(search_result, 'created_at') else None,
            original_status=search_result.status.value if hasattr(search_result, 'status') else ""
        )

    # ==========================================
    # 工厂方法：从InstantSearchResult创建
    # ==========================================

    @classmethod
    def from_instant_search_result(
        cls,
        instant_result: Any,  # InstantSearchResult类型
        data_source_id: str,
        archived_by: str,
        archived_reason: str = "confirm"
    ) -> "ArchivedData":
        """
        从InstantSearchResult（即时搜索结果）创建存档数据

        Args:
            instant_result: InstantSearchResult实体
            data_source_id: 所属数据源ID
            archived_by: 存档操作者
            archived_reason: 存档原因（confirm | manual）

        Returns:
            ArchivedData实例
        """
        # 提取instant类型特定字段
        type_specific = {
            "content_hash": instant_result.content_hash,
            "url_normalized": instant_result.url_normalized,
            "relevance_score": instant_result.relevance_score,
            "quality_score": instant_result.quality_score,
            "task_id": instant_result.task_id,
            "source": instant_result.source,
            "author": instant_result.author,
            "language": instant_result.language,
            "first_found_at": instant_result.first_found_at.isoformat() if instant_result.first_found_at else None,
            "last_found_at": instant_result.last_found_at.isoformat() if instant_result.last_found_at else None,
            "found_count": instant_result.found_count,
            "unique_searches": instant_result.unique_searches,
        }

        return cls(
            data_source_id=data_source_id,
            original_data_id=instant_result.id,
            data_type="instant",
            title=instant_result.title,
            url=instant_result.url,
            content=instant_result.content or "",  # 完整内容
            snippet=instant_result.snippet,
            published_date=instant_result.published_date,
            markdown_content=instant_result.markdown_content,
            html_content=instant_result.html_content,
            type_specific_fields=type_specific,
            metadata=instant_result.metadata,
            archived_at=datetime.utcnow(),
            archived_by=archived_by,
            archived_reason=archived_reason,
            original_created_at=instant_result.created_at,
            original_status=instant_result.status.value if hasattr(instant_result, 'status') else ""
        )

    # ==========================================
    # 序列化方法
    # ==========================================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "data_source_id": self.data_source_id,
            "original_data_id": self.original_data_id,
            "data_type": self.data_type,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "markdown_content": self.markdown_content,
            "html_content": self.html_content,
            "type_specific_fields": self.type_specific_fields,
            "metadata": self.metadata,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "archived_by": self.archived_by,
            "archived_reason": self.archived_reason,
            "original_created_at": self.original_created_at.isoformat() if self.original_created_at else None,
            "original_status": self.original_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary(self) -> Dict[str, Any]:
        """返回摘要信息（轻量级响应）"""
        return {
            "id": self.id,
            "data_source_id": self.data_source_id,
            "data_type": self.data_type,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet or self.content[:200],
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "archived_by": self.archived_by,
        }
