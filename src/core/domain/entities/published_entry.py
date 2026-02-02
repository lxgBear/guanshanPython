"""发布条目实体模型

审核通过后从 review_entries 移入此表，独立管理已发布内容。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.info_entry import RawDataRef


class PublishedStatus(Enum):
    """发布状态枚举"""
    PUBLISHED = "published"   # 已发布
    ARCHIVED = "archived"     # 已归档


@dataclass
class PublishedEntry:
    """发布条目实体

    审核通过后创建，存储已发布的内容及审核溯源信息
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 内容字段（从草稿复制）
    title: str = ""
    description: str = ""
    summary: str = ""
    combined_content: str = ""        # 编辑内容（TipTap JSON 格式）

    # 分类与标签
    tags: List[str] = field(default_factory=list)
    primary_category: str = ""        # 大类
    secondary_category: str = ""      # 类别
    tertiary_category: str = ""       # 地域

    # 条目类型
    entry_type: str = "single"        # single / batch

    # 原始数据引用
    raw_data_refs: List[RawDataRef] = field(default_factory=list)
    raw_data_count: int = 0

    # 审核溯源字段
    author_id: str = ""               # 原始创建者
    reviewer_id: str = ""             # 审核员
    review_comment: str = ""          # 审核意见
    submitted_at: Optional[datetime] = None   # 提交审核时间
    reviewed_at: Optional[datetime] = None    # 审核通过时间

    # 发布状态
    status: PublishedStatus = PublishedStatus.PUBLISHED
    published_at: Optional[datetime] = None   # 发布时间

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """初始化后处理"""
        self.raw_data_count = len(self.raw_data_refs)
        if self.published_at is None:
            self.published_at = datetime.utcnow()

    def archive(self) -> None:
        """归档"""
        self.status = PublishedStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "summary": self.summary,
            "combined_content": self.combined_content,
            "tags": self.tags,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "tertiary_category": self.tertiary_category,
            "entry_type": self.entry_type,
            "raw_data_refs": [ref.to_dict() for ref in self.raw_data_refs],
            "raw_data_count": self.raw_data_count,
            "author_id": self.author_id,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "status": self.status.value,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def published_entry_to_mongo_doc(entry: PublishedEntry) -> Dict[str, Any]:
    """将 PublishedEntry 转换为 MongoDB 文档"""
    return {
        "_id": entry.id,
        "title": entry.title,
        "description": entry.description,
        "summary": entry.summary,
        "combined_content": entry.combined_content,
        "tags": entry.tags,
        "primary_category": entry.primary_category,
        "secondary_category": entry.secondary_category,
        "tertiary_category": entry.tertiary_category,
        "entry_type": entry.entry_type,
        "raw_data_refs": [ref.to_dict() for ref in entry.raw_data_refs],
        "raw_data_count": entry.raw_data_count,
        "author_id": entry.author_id,
        "reviewer_id": entry.reviewer_id,
        "review_comment": entry.review_comment,
        "submitted_at": entry.submitted_at,
        "reviewed_at": entry.reviewed_at,
        "status": entry.status.value,
        "published_at": entry.published_at,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def mongo_doc_to_published_entry(doc: Dict[str, Any]) -> PublishedEntry:
    """将 MongoDB 文档转换为 PublishedEntry"""
    raw_data_refs = [
        RawDataRef.from_dict(ref) for ref in doc.get("raw_data_refs", [])
    ]

    return PublishedEntry(
        id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        summary=doc.get("summary", ""),
        combined_content=doc.get("combined_content", ""),
        tags=doc.get("tags", []),
        primary_category=doc.get("primary_category", ""),
        secondary_category=doc.get("secondary_category", ""),
        tertiary_category=doc.get("tertiary_category", ""),
        entry_type=doc.get("entry_type", "single"),
        raw_data_refs=raw_data_refs,
        raw_data_count=doc.get("raw_data_count", len(raw_data_refs)),
        author_id=doc.get("author_id", ""),
        reviewer_id=doc.get("reviewer_id", ""),
        review_comment=doc.get("review_comment", ""),
        submitted_at=doc.get("submitted_at"),
        reviewed_at=doc.get("reviewed_at"),
        status=PublishedStatus(doc.get("status", "published")),
        published_at=doc.get("published_at"),
        created_at=doc.get("created_at") or datetime.utcnow(),
        updated_at=doc.get("updated_at") or datetime.utcnow(),
    )
