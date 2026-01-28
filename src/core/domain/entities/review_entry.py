"""审核条目实体模型

v1.0.0 初始版本：
- 支持单条(single)和多条(batch)两种条目类型
- 支持草稿(draft)、待审核(pending_review)、已通过(approved)、已退回(rejected)四种状态
- 复用 RawDataRef 存储原始数据引用
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.info_entry import RawDataRef


class ReviewStatus(Enum):
    """审核状态枚举"""
    DRAFT = "draft"                     # 草稿
    PENDING_REVIEW = "pending_review"   # 待审核
    APPROVED = "approved"               # 已通过
    REJECTED = "rejected"               # 已退回


class EntryType(Enum):
    """条目类型枚举"""
    SINGLE = "single"   # 单条
    BATCH = "batch"     # 多条


@dataclass
class ReviewEntry:
    """审核条目实体

    用于存储待审核的条目，支持单条和多条两种类型
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 基础信息
    title: str = ""
    description: str = ""
    summary: str = ""
    combined_content: str = ""        # 编辑内容（TipTap JSON 格式）

    # 分类与标签
    tags: List[str] = field(default_factory=list)
    primary_category: str = ""        # 大类
    secondary_category: str = ""      # 类别
    tertiary_category: str = ""       # 地域

    # 条目类型和状态
    entry_type: EntryType = EntryType.SINGLE
    status: ReviewStatus = ReviewStatus.DRAFT

    # 原始数据引用
    raw_data_refs: List[RawDataRef] = field(default_factory=list)
    raw_data_count: int = 0           # 引用的原始数据数量

    # 来源关联（可选，关联 info_entries）
    source_entry_id: str = ""

    # 用户与时间
    user_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # 审核相关
    submitted_at: Optional[datetime] = None   # 提交审核时间
    reviewed_at: Optional[datetime] = None    # 审核时间
    reviewer_id: str = ""                     # 审核人ID
    review_comment: str = ""                  # 审核意见

    def __post_init__(self):
        """初始化后处理"""
        self.raw_data_count = len(self.raw_data_refs)

    def add_raw_data_ref(self, ref: RawDataRef) -> None:
        """添加原始数据引用"""
        self.raw_data_refs.append(ref)
        self.raw_data_count = len(self.raw_data_refs)
        self.updated_at = datetime.utcnow()

    def update_combined_content(self, content: str) -> None:
        """更新编辑内容"""
        self.combined_content = content
        self.updated_at = datetime.utcnow()

    def submit_for_review(self) -> None:
        """提交审核"""
        self.status = ReviewStatus.PENDING_REVIEW
        self.submitted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def approve(self, reviewer_id: str, comment: str = "") -> None:
        """通过审核"""
        self.status = ReviewStatus.APPROVED
        self.reviewer_id = reviewer_id
        self.review_comment = comment
        self.reviewed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def reject(self, reviewer_id: str, comment: str = "") -> None:
        """退回审核"""
        self.status = ReviewStatus.REJECTED
        self.reviewer_id = reviewer_id
        self.review_comment = comment
        self.reviewed_at = datetime.utcnow()
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
            "entry_type": self.entry_type.value,
            "status": self.status.value,
            "raw_data_refs": [ref.to_dict() for ref in self.raw_data_refs],
            "raw_data_count": self.raw_data_count,
            "source_entry_id": self.source_entry_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
        }


def review_entry_to_mongo_doc(entry: ReviewEntry) -> Dict[str, Any]:
    """将 ReviewEntry 转换为 MongoDB 文档"""
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
        "entry_type": entry.entry_type.value,
        "status": entry.status.value,
        "raw_data_refs": [ref.to_dict() for ref in entry.raw_data_refs],
        "raw_data_count": entry.raw_data_count,
        "source_entry_id": entry.source_entry_id,
        "user_id": entry.user_id,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
        "submitted_at": entry.submitted_at,
        "reviewed_at": entry.reviewed_at,
        "reviewer_id": entry.reviewer_id,
        "review_comment": entry.review_comment,
    }


def mongo_doc_to_review_entry(doc: Dict[str, Any]) -> ReviewEntry:
    """将 MongoDB 文档转换为 ReviewEntry"""
    raw_data_refs = [
        RawDataRef.from_dict(ref) for ref in doc.get("raw_data_refs", [])
    ]

    return ReviewEntry(
        id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        summary=doc.get("summary", ""),
        combined_content=doc.get("combined_content", ""),
        tags=doc.get("tags", []),
        primary_category=doc.get("primary_category", ""),
        secondary_category=doc.get("secondary_category", ""),
        tertiary_category=doc.get("tertiary_category", ""),
        entry_type=EntryType(doc.get("entry_type", "single")),
        status=ReviewStatus(doc.get("status", "draft")),
        raw_data_refs=raw_data_refs,
        raw_data_count=doc.get("raw_data_count", len(raw_data_refs)),
        source_entry_id=doc.get("source_entry_id", ""),
        user_id=doc.get("user_id", ""),
        created_at=doc.get("created_at") or datetime.utcnow(),
        updated_at=doc.get("updated_at") or datetime.utcnow(),
        submitted_at=doc.get("submitted_at"),
        reviewed_at=doc.get("reviewed_at"),
        reviewer_id=doc.get("reviewer_id", ""),
        review_comment=doc.get("review_comment", ""),
    )
