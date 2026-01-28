"""审批流程API端点 v2.8.0"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.auth import get_current_active_user, require_permissions
from src.core.domain.entities.auth.user import User
from src.core.domain.entities.review_flow import (
    ReviewFlow,
    ReviewFlowCreate,
    ReviewFlowDetail,
    ReviewFlowListResponse,
    ReviewFlowApproveRequest,
    ReviewFlowRejectRequest,
    ReviewFlowStatus,
    ReviewTargetType,
    ReviewAction,
)
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.repositories.mongo.review_flow_repository import ReviewFlowRepository
from src.infrastructure.persistence.auth.mongodb.user_repository import MongoUserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review-flow", tags=["审批流程"])


async def get_review_flow_repository() -> ReviewFlowRepository:
    """获取审批流程仓储"""
    db = await get_mongodb_database()
    return ReviewFlowRepository(db)


async def get_user_repository() -> MongoUserRepository:
    """获取用户仓储"""
    db = await get_mongodb_database()
    return MongoUserRepository(db)


@router.post("/submit", response_model=ReviewFlow, summary="提交审批")
async def submit_review(
    request: ReviewFlowCreate,
    current_user: User = Depends(get_current_active_user),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
    user_repo: MongoUserRepository = Depends(get_user_repository),
):
    """
    提交内容进行审批

    - target_id: 被审批对象ID
    - target_type: 对象类型 (review_entry, info_entry, archive)
    - reviewer_id: 首个审核员ID
    """
    # 验证审核员存在且有审批权限
    reviewer = await user_repo.get_by_id(request.reviewer_id)
    if not reviewer:
        raise HTTPException(status_code=404, detail="审核员不存在")

    if "review:approve" not in reviewer.permissions:
        raise HTTPException(status_code=400, detail="该用户没有审批权限")

    # 检查是否已有进行中的审批流程
    existing = await repo.get_by_target(request.target_id, request.target_type)
    if existing and existing.status == ReviewFlowStatus.PENDING:
        raise HTTPException(status_code=400, detail="该对象已有进行中的审批流程")

    # 创建审批流程
    flow = await repo.create(
        target_id=request.target_id,
        target_type=request.target_type,
        submitter_id=current_user.id,
        submitter_name=current_user.display_name or current_user.username,
        reviewer_id=request.reviewer_id,
        reviewer_name=reviewer.display_name or reviewer.username,
        title=request.title,
    )

    logger.info(f"提交审批: flow_id={flow.id}, submitter={current_user.username}")
    return flow


@router.post("/{flow_id}/approve", response_model=ReviewFlow, summary="审批通过")
async def approve_review(
    flow_id: str,
    request: ReviewFlowApproveRequest,
    current_user: User = Depends(require_permissions("review:approve")),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
    user_repo: MongoUserRepository = Depends(get_user_repository),
):
    """
    审批通过

    - action: 操作类型
      - pass_and_continue: 通过并继续（需指定下一审核员）
      - pass_and_end: 通过并结束流程
    - comment: 审核意见（可选）
    - next_reviewer_id: 下一审核员ID（action=pass_and_continue时必填）
    """
    flow = await repo.get_by_id(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="审批流程不存在")

    if flow.status != ReviewFlowStatus.PENDING:
        raise HTTPException(status_code=400, detail="该审批流程已结束")

    # 验证当前用户是否是当前步骤的审核员
    current_step = None
    for step in flow.review_chain:
        if step.reviewer_id == current_user.id and step.status == ReviewFlowStatus.PENDING:
            current_step = step
            break

    if not current_step:
        raise HTTPException(status_code=403, detail="您不是当前步骤的审核员")

    # 如果选择继续，需要验证下一审核员
    next_reviewer_name = None
    if request.action == ReviewAction.PASS_AND_CONTINUE:
        if not request.next_reviewer_id:
            raise HTTPException(status_code=400, detail="请指定下一审核员")

        next_reviewer = await user_repo.get_by_id(request.next_reviewer_id)
        if not next_reviewer:
            raise HTTPException(status_code=404, detail="下一审核员不存在")

        if "review:approve" not in next_reviewer.permissions:
            raise HTTPException(status_code=400, detail="该用户没有审批权限")

        next_reviewer_name = next_reviewer.display_name or next_reviewer.username

    # 执行审批
    updated_flow = await repo.approve(
        flow_id=flow_id,
        reviewer_id=current_user.id,
        action=request.action,
        comment=request.comment,
        next_reviewer_id=request.next_reviewer_id,
        next_reviewer_name=next_reviewer_name,
    )

    if not updated_flow:
        raise HTTPException(status_code=500, detail="审批操作失败")

    logger.info(f"审批通过: flow_id={flow_id}, action={request.action}, reviewer={current_user.username}")
    return updated_flow


@router.post("/{flow_id}/reject", response_model=ReviewFlow, summary="审批拒绝")
async def reject_review(
    flow_id: str,
    request: ReviewFlowRejectRequest,
    current_user: User = Depends(require_permissions("review:approve")),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
):
    """
    审批拒绝

    - comment: 拒绝原因（可选）
    """
    flow = await repo.get_by_id(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="审批流程不存在")

    if flow.status != ReviewFlowStatus.PENDING:
        raise HTTPException(status_code=400, detail="该审批流程已结束")

    # 验证当前用户是否是当前步骤的审核员
    is_reviewer = False
    for step in flow.review_chain:
        if step.reviewer_id == current_user.id and step.status == ReviewFlowStatus.PENDING:
            is_reviewer = True
            break

    if not is_reviewer:
        raise HTTPException(status_code=403, detail="您不是当前步骤的审核员")

    # 执行拒绝
    updated_flow = await repo.reject(
        flow_id=flow_id,
        reviewer_id=current_user.id,
        comment=request.comment,
    )

    if not updated_flow:
        raise HTTPException(status_code=500, detail="拒绝操作失败")

    logger.info(f"审批拒绝: flow_id={flow_id}, reviewer={current_user.username}")
    return updated_flow


@router.get("/pending", response_model=ReviewFlowListResponse, summary="我的待审批列表")
async def get_pending_reviews(
    target_type: Optional[ReviewTargetType] = Query(None, description="对象类型筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_permissions("review:approve")),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
):
    """获取当前用户的待审批列表"""
    items, total = await repo.get_pending_by_reviewer(
        reviewer_id=current_user.id,
        target_type=target_type,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return ReviewFlowListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/history", response_model=ReviewFlowListResponse, summary="我的审批历史")
async def get_review_history(
    target_type: Optional[ReviewTargetType] = Query(None, description="对象类型筛选"),
    status: Optional[ReviewFlowStatus] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_permissions("review:approve")),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
):
    """获取当前用户的审批历史"""
    items, total = await repo.get_history_by_reviewer(
        reviewer_id=current_user.id,
        target_type=target_type,
        status=status,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return ReviewFlowListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/my-submissions", response_model=ReviewFlowListResponse, summary="我提交的审批")
async def get_my_submissions(
    target_type: Optional[ReviewTargetType] = Query(None, description="对象类型筛选"),
    status: Optional[ReviewFlowStatus] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_active_user),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
):
    """获取当前用户提交的审批流程列表"""
    items, total = await repo.get_by_submitter(
        submitter_id=current_user.id,
        target_type=target_type,
        status=status,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return ReviewFlowListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{flow_id}", response_model=ReviewFlowDetail, summary="获取审批详情")
async def get_review_detail(
    flow_id: str,
    current_user: User = Depends(get_current_active_user),
    repo: ReviewFlowRepository = Depends(get_review_flow_repository),
):
    """获取审批流程详情"""
    flow = await repo.get_by_id(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="审批流程不存在")

    # 检查权限：提交人或审核链中的人可以查看
    is_submitter = flow.submitter_id == current_user.id
    is_reviewer = any(step.reviewer_id == current_user.id for step in flow.review_chain)

    if not is_submitter and not is_reviewer:
        # 检查是否有管理权限
        if "workflow:read" not in current_user.permissions and "admin" not in current_user.roles:
            raise HTTPException(status_code=403, detail="无权查看此审批流程")

    return ReviewFlowDetail(**flow.model_dump())
