"""成果草稿实体模型

支持动态链式多级审核流程：
- 提交人创建草稿 → 提交审核（选择审核员）
- 审核员可：通过、转交、退回提交人、退回上一级、作废
- 退回后重新提交，直接回到退回的审核员
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from src.infrastructure.id_generator import generate_string_id


class AchievementStatus(Enum):
    """成果草稿状态"""
    DRAFT = "draft"                    # 草稿（可编辑）
    PENDING_REVIEW = "pending_review"  # 待审核（提交人不可编辑）
    RETURNED = "returned"              # 已退回（提交人可编辑）
    APPROVED = "approved"              # 已通过（流程结束）
    VOIDED = "voided"                  # 已作废（流程终止，不可编辑）


@dataclass
class AchievementDraft:
    """成果草稿实体

    用于存储整编成果草稿，支持多级审核流程
    """
    # === 主键 ===
    id: str = field(default_factory=generate_string_id)

    # === 内容字段 ===
    title: str = ""
    description: str = ""
    summary: str = ""
    combined_content: str = ""        # 整编内容（HTML/JSON）

    # === 分类与标签 ===
    tags: List[str] = field(default_factory=list)
    primary_category: str = ""        # 大类
    secondary_category: str = ""      # 类别
    tertiary_category: str = ""       # 地域

    # === 来源引用 ===
    source_entry_ids: List[str] = field(default_factory=list)  # 关联的 published_entries IDs
    raw_data_count: int = 0           # 原始数据数量

    # === 提交人信息 ===
    author_id: str = ""               # 创建/提交人ID
    author_name: str = ""             # 创建/提交人姓名

    # === 状态管理 ===
    status: AchievementStatus = AchievementStatus.DRAFT

    # === 当前审核信息 ===
    current_reviewer_id: str = ""     # 当前审核员ID
    current_reviewer_name: str = ""   # 当前审核员姓名
    current_review_level: int = 0     # 当前审核层级（0=未提交, 1, 2, 3...）

    # === 退回时记录的审核员（用于重新提交时直接回到该审核员）===
    returned_by_reviewer_id: str = ""
    returned_by_reviewer_name: str = ""
    returned_at_level: int = 0

    # === 时间戳 ===
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None   # 提交审核时间
    completed_at: Optional[datetime] = None   # 流程完成时间（通过/作废）

    def __post_init__(self):
        """初始化后处理"""
        self.raw_data_count = len(self.source_entry_ids)

    def update_raw_data_count(self) -> None:
        """更新原始数据数量

        当 source_entry_ids 被修改后调用此方法同步 raw_data_count
        """
        self.raw_data_count = len(self.source_entry_ids)

    def can_edit(self, user_id: str) -> bool:
        """检查用户是否可以编辑"""
        if not user_id or not self.author_id:
            return False
        if self.author_id != user_id:
            return False
        return self.status in [AchievementStatus.DRAFT, AchievementStatus.RETURNED]

    def can_submit(self, user_id: str) -> bool:
        """检查用户是否可以提交审核"""
        if not user_id or not self.author_id:
            return False
        if self.author_id != user_id:
            return False
        return self.status in [AchievementStatus.DRAFT, AchievementStatus.RETURNED]

    def can_review(self, user_id: str) -> bool:
        """检查用户是否可以审核"""
        if not user_id or not self.current_reviewer_id:
            return False
        if self.status != AchievementStatus.PENDING_REVIEW:
            return False
        return self.current_reviewer_id == user_id

    def submit_for_review(self, reviewer_id: str, reviewer_name: str) -> None:
        """提交审核

        Args:
            reviewer_id: 审核员ID
            reviewer_name: 审核员姓名

        Raises:
            ValueError: 当前状态不允许提交，或缺少审核员信息
        """
        if self.status not in [AchievementStatus.DRAFT, AchievementStatus.RETURNED]:
            raise ValueError(f"Cannot submit: current status is {self.status.value}")

        if self.status == AchievementStatus.RETURNED:
            # 退回后重新提交，回到退回的审核员
            self.current_reviewer_id = self.returned_by_reviewer_id
            self.current_reviewer_name = self.returned_by_reviewer_name
            self.current_review_level = self.returned_at_level
        else:
            # 首次提交，需要验证审核员信息
            if not reviewer_id or not reviewer_name:
                raise ValueError("Cannot submit: missing reviewer information")
            self.current_reviewer_id = reviewer_id
            self.current_reviewer_name = reviewer_name
            self.current_review_level = 1

        self.status = AchievementStatus.PENDING_REVIEW
        self.submitted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        # 清除退回记录
        self.returned_by_reviewer_id = ""
        self.returned_by_reviewer_name = ""
        self.returned_at_level = 0

    def approve(self) -> None:
        """通过审核

        Raises:
            ValueError: 当前状态不允许通过审核
        """
        if self.status != AchievementStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot approve: current status is {self.status.value}")
        self.status = AchievementStatus.APPROVED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def forward(self, next_reviewer_id: str, next_reviewer_name: str) -> None:
        """转交下一级

        Args:
            next_reviewer_id: 下一级审核员ID
            next_reviewer_name: 下一级审核员姓名

        Raises:
            ValueError: 当前状态不允许转交，或缺少下一级审核员信息
        """
        if self.status != AchievementStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot forward: current status is {self.status.value}")
        if not next_reviewer_id or not next_reviewer_name:
            raise ValueError("Cannot forward: missing next reviewer information")
        self.current_reviewer_id = next_reviewer_id
        self.current_reviewer_name = next_reviewer_name
        self.current_review_level += 1
        self.updated_at = datetime.utcnow()

    def return_to_author(self) -> None:
        """退回提交人

        Raises:
            ValueError: 当前状态不允许退回
        """
        if self.status != AchievementStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot return to author: current status is {self.status.value}")

        self.returned_by_reviewer_id = self.current_reviewer_id
        self.returned_by_reviewer_name = self.current_reviewer_name
        self.returned_at_level = self.current_review_level

        self.status = AchievementStatus.RETURNED
        self.current_reviewer_id = ""
        self.current_reviewer_name = ""
        self.updated_at = datetime.utcnow()

    def return_to_previous(self, prev_reviewer_id: str, prev_reviewer_name: str, prev_level: int) -> None:
        """退回上一级审核员

        Args:
            prev_reviewer_id: 上一级审核员ID
            prev_reviewer_name: 上一级审核员姓名
            prev_level: 上一级审核层级

        Raises:
            ValueError: 当前状态不允许退回，或缺少上一级审核员信息
        """
        if self.status != AchievementStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot return to previous: current status is {self.status.value}")
        if not prev_reviewer_id or not prev_reviewer_name:
            raise ValueError("Cannot return to previous: missing previous reviewer information")
        if prev_level < 1:
            raise ValueError("Cannot return to previous: invalid previous level")
        self.current_reviewer_id = prev_reviewer_id
        self.current_reviewer_name = prev_reviewer_name
        self.current_review_level = prev_level
        self.updated_at = datetime.utcnow()

    def void(self) -> None:
        """作废

        Raises:
            ValueError: 当前状态不允许作废
        """
        if self.status in [AchievementStatus.APPROVED, AchievementStatus.VOIDED]:
            raise ValueError(f"Cannot void: current status is {self.status.value}")
        self.status = AchievementStatus.VOIDED
        self.completed_at = datetime.utcnow()
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
            "source_entry_ids": self.source_entry_ids,
            "raw_data_count": self.raw_data_count,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "status": self.status.value,
            "current_reviewer_id": self.current_reviewer_id,
            "current_reviewer_name": self.current_reviewer_name,
            "current_review_level": self.current_review_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def achievement_draft_to_mongo_doc(draft: AchievementDraft) -> Dict[str, Any]:
    """将 AchievementDraft 转换为 MongoDB 文档"""
    return {
        "_id": draft.id,
        "title": draft.title,
        "description": draft.description,
        "summary": draft.summary,
        "combined_content": draft.combined_content,
        "tags": draft.tags,
        "primary_category": draft.primary_category,
        "secondary_category": draft.secondary_category,
        "tertiary_category": draft.tertiary_category,
        "source_entry_ids": draft.source_entry_ids,
        "raw_data_count": draft.raw_data_count,
        "author_id": draft.author_id,
        "author_name": draft.author_name,
        "status": draft.status.value,
        "current_reviewer_id": draft.current_reviewer_id,
        "current_reviewer_name": draft.current_reviewer_name,
        "current_review_level": draft.current_review_level,
        "returned_by_reviewer_id": draft.returned_by_reviewer_id,
        "returned_by_reviewer_name": draft.returned_by_reviewer_name,
        "returned_at_level": draft.returned_at_level,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "submitted_at": draft.submitted_at,
        "completed_at": draft.completed_at,
    }


def mongo_doc_to_achievement_draft(doc: Dict[str, Any]) -> AchievementDraft:
    """将 MongoDB 文档转换为 AchievementDraft

    对于无效的 status 值，默认使用 DRAFT 状态
    """
    # 安全解析状态值
    try:
        status = AchievementStatus(doc.get("status", "draft"))
    except ValueError:
        status = AchievementStatus.DRAFT

    return AchievementDraft(
        id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        summary=doc.get("summary", ""),
        combined_content=doc.get("combined_content", ""),
        tags=doc.get("tags", []),
        primary_category=doc.get("primary_category", ""),
        secondary_category=doc.get("secondary_category", ""),
        tertiary_category=doc.get("tertiary_category", ""),
        source_entry_ids=doc.get("source_entry_ids", []),
        raw_data_count=doc.get("raw_data_count", 0),
        author_id=doc.get("author_id", ""),
        author_name=doc.get("author_name", ""),
        status=status,
        current_reviewer_id=doc.get("current_reviewer_id", ""),
        current_reviewer_name=doc.get("current_reviewer_name", ""),
        current_review_level=doc.get("current_review_level", 0),
        returned_by_reviewer_id=doc.get("returned_by_reviewer_id", ""),
        returned_by_reviewer_name=doc.get("returned_by_reviewer_name", ""),
        returned_at_level=doc.get("returned_at_level", 0),
        created_at=doc.get("created_at") or datetime.utcnow(),
        updated_at=doc.get("updated_at") or datetime.utcnow(),
        submitted_at=doc.get("submitted_at"),
        completed_at=doc.get("completed_at"),
    )
