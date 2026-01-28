"""审批流程领域实体 v2.8.0"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class ReviewFlowStatus(str, Enum):
    """审批流程状态"""
    PENDING = "pending"       # 待审批
    APPROVED = "approved"     # 已通过
    REJECTED = "rejected"     # 已拒绝


class ReviewAction(str, Enum):
    """审批操作类型"""
    PASS_AND_CONTINUE = "pass_and_continue"  # 通过并继续（指定下一审核员）
    PASS_AND_END = "pass_and_end"            # 通过并结束
    REJECT = "reject"                         # 拒绝


class ReviewTargetType(str, Enum):
    """被审批对象类型"""
    REVIEW_ENTRY = "review_entry"    # 审核条目
    INFO_ENTRY = "info_entry"        # 信息条目
    ARCHIVE = "archive"              # 档案


class ReviewStep(BaseModel):
    """审批步骤"""
    step: int = Field(..., ge=1, description="步骤序号")
    reviewer_id: str = Field(..., description="审核员ID")
    reviewer_name: str = Field(..., description="审核员姓名")
    status: ReviewFlowStatus = Field(default=ReviewFlowStatus.PENDING, description="本步骤状态")
    action: Optional[ReviewAction] = Field(None, description="审核操作")
    comment: Optional[str] = Field(None, max_length=1000, description="审核意见")
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="指派时间")
    reviewed_at: Optional[datetime] = Field(None, description="审核时间")


class ReviewFlowBase(BaseModel):
    """审批流程基础模型"""
    target_id: str = Field(..., description="被审批对象ID")
    target_type: ReviewTargetType = Field(..., description="对象类型")
    title: Optional[str] = Field(None, max_length=200, description="审批标题")


class ReviewFlowCreate(ReviewFlowBase):
    """创建审批流程请求"""
    reviewer_id: str = Field(..., description="首个审核员ID")


class ReviewFlowInDB(ReviewFlowBase):
    """数据库中的审批流程模型"""
    id: str = Field(..., description="流程ID")

    # 审批链（动态形成）
    review_chain: List[ReviewStep] = Field(default_factory=list, description="审批链")
    current_step: int = Field(default=1, ge=1, description="当前步骤")
    status: ReviewFlowStatus = Field(default=ReviewFlowStatus.PENDING, description="整体状态")

    # 提交人信息
    submitter_id: str = Field(..., description="提交人ID")
    submitter_name: str = Field(..., description="提交人姓名")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        from_attributes = True


class ReviewFlow(ReviewFlowInDB):
    """审批流程响应模型"""
    pass


class ReviewFlowDetail(ReviewFlow):
    """审批流程详情（包含目标对象信息）"""
    target_title: Optional[str] = Field(None, description="目标对象标题")
    target_summary: Optional[str] = Field(None, description="目标对象摘要")


class ReviewFlowApproveRequest(BaseModel):
    """审批通过请求"""
    action: ReviewAction = Field(..., description="审批操作")
    comment: Optional[str] = Field(None, max_length=1000, description="审核意见")
    next_reviewer_id: Optional[str] = Field(None, description="下一审核员ID（action=pass_and_continue时必填）")


class ReviewFlowRejectRequest(BaseModel):
    """审批拒绝请求"""
    comment: Optional[str] = Field(None, max_length=1000, description="拒绝原因")


class ReviewFlowListParams(BaseModel):
    """审批流程列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    target_type: Optional[ReviewTargetType] = Field(None, description="对象类型筛选")
    status: Optional[ReviewFlowStatus] = Field(None, description="状态筛选")


class ReviewFlowListResponse(BaseModel):
    """审批流程列表响应"""
    items: List[ReviewFlowDetail] = Field(default_factory=list, description="流程列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=20, description="每页数量")
    total_pages: int = Field(default=0, description="总页数")


class ReviewerInfo(BaseModel):
    """审核员信息"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    display_name: Optional[str] = Field(None, description="显示名称")
    department: Optional[str] = Field(None, description="部门")


class ReviewerListResponse(BaseModel):
    """可选审核员列表响应"""
    items: List[ReviewerInfo] = Field(default_factory=list, description="审核员列表")
    total: int = Field(default=0, description="总数")
