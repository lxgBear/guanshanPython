"""
用户档案实体

存储用户创建的档案元数据。

设计说明:
- 档案是用户基于AI筛选结果创建的知识管理单元
- 支持标签、描述等元数据
- 关联搜索记录，提供内容溯源

v2.7.0: 新增审核流程支持
- 档案创建后默认为待审核状态
- 审核员可通过/驳回档案
- 被驳回的档案可修改后重新提交
- 支持审核历史追踪
"""
from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class ArchiveStatus(str, Enum):
    """档案审核状态枚举

    v2.7.0: 新增审核状态支持

    状态流转:
    - pending -> approved (审核通过)
    - pending -> rejected (审核驳回)
    - rejected -> pending (重新提交)
    """
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已审核（通过）
    REJECTED = "rejected"    # 已驳回


class ArchiveReviewAction(str, Enum):
    """档案审核操作枚举

    用于记录审核历史中的操作类型
    """
    SUBMIT = "submit"        # 提交（创建）
    APPROVE = "approve"      # 通过
    REJECT = "reject"        # 驳回
    RESUBMIT = "resubmit"    # 重新提交


class ArchiveReviewHistory(BaseModel):
    """档案审核历史记录

    v2.7.0: 新增审核历史追踪

    用于记录档案的所有审核操作，提供完整的审计追踪。

    Attributes:
        review_id: 审核记录ID
        archive_id: 档案ID
        action: 操作类型
        operator_id: 操作人ID
        operator_name: 操作人姓名
        status_before: 操作前状态
        status_after: 操作后状态
        feedback: 反馈意见（驳回时必填）
        created_at: 操作时间
    """
    review_id: Optional[str] = Field(None, description="审核记录ID")
    archive_id: str = Field(..., description="档案ID")
    action: ArchiveReviewAction = Field(..., description="操作类型")
    operator_id: int = Field(..., description="操作人ID")
    operator_name: str = Field(..., description="操作人姓名")
    status_before: Optional[ArchiveStatus] = Field(None, description="操作前状态")
    status_after: ArchiveStatus = Field(..., description="操作后状态")
    feedback: Optional[str] = Field(None, description="反馈意见（驳回时的改进建议）", max_length=2000)
    created_at: Optional[datetime] = Field(None, description="操作时间")

    class Config:
        from_attributes = True


class NLUserArchive(BaseModel):
    """用户档案实体

    用户基于AI筛选的新闻结果创建的档案，用于知识管理和内容归档。

    Attributes:
        id: 档案唯一ID (数据库自动生成)
        user_id: 用户ID
        archive_name: 档案名称（用户命名）
        description: 档案描述（可选）
        tags: 档案标签列表（可选）
        search_log_id: 关联的搜索记录ID（可选，用于溯源）
        items_count: 档案中的条目数量
        created_at: 创建时间
        updated_at: 最后更新时间

    v2.7.0 新增审核相关字段:
        status: 审核状态（pending/approved/rejected）
        reviewer_id: 审核人ID
        reviewer_name: 审核人姓名
        reviewed_at: 审核时间
        rejection_feedback: 驳回原因
        submission_count: 提交次数

    Example:
        >>> archive = NLUserArchive(
        ...     user_id=1001,
        ...     archive_name="2024年AI技术突破汇总",
        ...     description="整理2024年重要的AI技术突破新闻",
        ...     tags=["AI", "技术", "2024"],
        ...     search_log_id=123456
        ... )
    """

    id: Optional[int] = Field(
        None,
        description="档案唯一ID (数据库自动生成)"
    )

    user_id: int = Field(
        ...,
        description="用户ID",
        gt=0
    )

    archive_name: str = Field(
        ...,
        description="档案名称",
        max_length=255,
        min_length=1
    )

    description: Optional[str] = Field(
        None,
        description="档案描述（可选）",
        max_length=2000
    )

    tags: Optional[List[str]] = Field(
        None,
        description="档案标签列表（可选）"
    )

    search_log_id: Optional[int] = Field(
        None,
        description="关联的搜索记录ID（用于溯源）"
    )

    items_count: int = Field(
        0,
        description="档案中的条目数量",
        ge=0
    )

    # v2.7.0: 审核流程相关字段
    status: ArchiveStatus = Field(
        ArchiveStatus.PENDING,
        description="审核状态：pending（待审核）、approved（已审核）、rejected（已驳回）"
    )

    reviewer_id: Optional[int] = Field(
        None,
        description="审核人ID"
    )

    reviewer_name: Optional[str] = Field(
        None,
        description="审核人姓名",
        max_length=100
    )

    reviewed_at: Optional[datetime] = Field(
        None,
        description="审核时间"
    )

    rejection_feedback: Optional[str] = Field(
        None,
        description="驳回原因/改进建议",
        max_length=2000
    )

    submission_count: int = Field(
        1,
        description="提交次数（首次创建为1，每次重新提交+1）",
        ge=1
    )

    created_at: Optional[datetime] = Field(
        None,
        description="创建时间"
    )

    updated_at: Optional[datetime] = Field(
        None,
        description="最后更新时间"
    )

    class Config:
        """Pydantic 配置"""
        from_attributes = True  # SQLAlchemy ORM 支持
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1001,
                "archive_name": "2024年AI技术突破汇总",
                "description": "整理2024年重要的AI技术突破新闻",
                "tags": ["AI", "技术", "2024"],
                "search_log_id": 123456,
                "items_count": 5,
                "status": "pending",
                "reviewer_id": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "rejection_feedback": None,
                "submission_count": 1,
                "created_at": "2024-11-17T10:00:00",
                "updated_at": "2024-11-17T10:30:00"
            }
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<NLUserArchive(id={self.id}, name='{self.archive_name}', status={self.status}, items={self.items_count})>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        status_text = {
            ArchiveStatus.PENDING: "待审核",
            ArchiveStatus.APPROVED: "已审核",
            ArchiveStatus.REJECTED: "已驳回"
        }.get(self.status, self.status)
        return f"档案 #{self.id}: {self.archive_name} [{status_text}] ({self.items_count}条)"

    @property
    def has_tags(self) -> bool:
        """是否有标签"""
        return self.tags is not None and len(self.tags) > 0

    @property
    def has_description(self) -> bool:
        """是否有描述"""
        return self.description is not None and len(self.description) > 0

    @property
    def is_linked_to_search(self) -> bool:
        """是否关联搜索记录"""
        return self.search_log_id is not None

    # v2.7.0: 审核状态相关属性
    @property
    def is_pending(self) -> bool:
        """是否待审核"""
        return self.status == ArchiveStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """是否已审核通过"""
        return self.status == ArchiveStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        """是否已驳回"""
        return self.status == ArchiveStatus.REJECTED

    @property
    def can_be_reviewed(self) -> bool:
        """是否可以被审核（仅待审核状态可审核）"""
        return self.status == ArchiveStatus.PENDING

    @property
    def can_be_resubmitted(self) -> bool:
        """是否可以重新提交（仅已驳回状态可重新提交）"""
        return self.status == ArchiveStatus.REJECTED

    @property
    def status_display(self) -> str:
        """获取状态的中文显示"""
        return {
            ArchiveStatus.PENDING: "待审核",
            ArchiveStatus.APPROVED: "已审核",
            ArchiveStatus.REJECTED: "已驳回"
        }.get(self.status, str(self.status))
