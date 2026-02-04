"""
成果草稿 API

提供成果草稿的 CRUD 和审核流程 API
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_user
from src.services.achievement.achievement_draft_service import achievement_draft_service
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/achievement-drafts", tags=["📝 成果草稿"])


# ==================== 请求/响应模型 ====================

class CreateDraftRequest(BaseModel):
    """创建草稿请求"""
    source_entry_ids: List[str] = Field(..., description="关联的 published_entries IDs")
    title: str = Field(..., description="标题")
    description: str = Field("", description="描述")
    summary: str = Field("", description="摘要")
    combined_content: str = Field("", description="整编内容")
    tags: List[str] = Field(default_factory=list, description="标签")
    primary_category: str = Field("", description="大类")
    secondary_category: str = Field("", description="类别")
    tertiary_category: str = Field("", description="地域")


class UpdateDraftRequest(BaseModel):
    """更新草稿请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    combined_content: Optional[str] = None
    tags: Optional[List[str]] = None
    primary_category: Optional[str] = None
    secondary_category: Optional[str] = None
    tertiary_category: Optional[str] = None
    source_entry_ids: Optional[List[str]] = None


class SubmitReviewRequest(BaseModel):
    """提交审核请求"""
    reviewer_id: str = Field(..., description="审核员ID")
    reviewer_name: str = Field(..., description="审核员姓名")


class ReviewActionRequest(BaseModel):
    """审核操作请求"""
    action: str = Field(..., description="操作类型: approve|forward|return_to_author|return_to_previous|void")
    comment: str = Field("", description="审核意见")
    to_user_id: str = Field("", description="下一级审核员ID（转交时必填）")
    to_user_name: str = Field("", description="下一级审核员姓名（转交时必填）")


class DraftResponse(BaseModel):
    """草稿响应"""
    id: str
    title: str
    description: str
    summary: str
    combined_content: str
    tags: List[str]
    primary_category: str
    secondary_category: str
    tertiary_category: str
    source_entry_ids: List[str]
    raw_data_count: int
    author_id: str
    author_name: str
    status: str
    current_reviewer_id: str
    current_reviewer_name: str
    current_review_level: int
    created_at: Optional[str]
    updated_at: Optional[str]
    submitted_at: Optional[str]
    completed_at: Optional[str]


class DraftListResponse(BaseModel):
    """草稿列表响应"""
    items: List[DraftResponse]
    total: int
    page: int
    page_size: int


class ReviewLogResponse(BaseModel):
    """审核日志响应"""
    id: str
    achievement_id: str
    action: str
    review_level: int
    operator_id: str
    operator_name: str
    from_user_id: str
    to_user_id: str
    to_user_name: str
    comment: str
    created_at: Optional[str]


class ReviewStatsResponse(BaseModel):
    """审核统计响应"""
    operator_id: str
    operator_name: str
    total: int
    approved: int
    forwarded: int
    returned: int
    voided: int


# ==================== 辅助函数 ====================

def draft_to_response(draft) -> DraftResponse:
    """将 draft 对象转换为响应模型"""
    d = draft.to_dict()
    return DraftResponse(**d)


# ==================== API 端点 ====================

@router.post(
    "",
    response_model=DraftResponse,
    summary="创建草稿",
    description="从已选的 published_entries 创建成果草稿",
)
async def create_draft(
    request: CreateDraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建草稿"""
    try:
        draft = await achievement_draft_service.create(
            source_entry_ids=request.source_entry_ids,
            title=request.title,
            author_id=str(current_user["id"]),
            author_name=current_user.get("display_name") or current_user.get("username", ""),
            description=request.description,
            summary=request.summary,
            combined_content=request.combined_content,
            tags=request.tags,
            primary_category=request.primary_category,
            secondary_category=request.secondary_category,
            tertiary_category=request.tertiary_category,
        )
        return draft_to_response(draft)
    except Exception as e:
        logger.error(f"创建草稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "",
    response_model=DraftListResponse,
    summary="列出草稿",
    description="根据角色列出草稿",
)
async def list_drafts(
    status: Optional[str] = Query(None, description="状态筛选"),
    primary_category: Optional[str] = Query(None, description="大类筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """列出草稿"""
    try:
        # 返回用户自己的草稿
        result = await achievement_draft_service.list_by_author(
            author_id=str(current_user["id"]),
            status=status,
            page=page,
            page_size=page_size,
        )

        return DraftListResponse(
            items=[draft_to_response(d) for d in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except Exception as e:
        logger.error(f"列出草稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pending-review",
    response_model=DraftListResponse,
    summary="列出待审核草稿",
    description="列出当前用户需要审核的草稿",
)
async def list_pending_review(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """列出待审核草稿"""
    try:
        result = await achievement_draft_service.list_by_reviewer(
            reviewer_id=str(current_user["id"]),
            page=page,
            page_size=page_size,
        )

        return DraftListResponse(
            items=[draft_to_response(d) for d in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except Exception as e:
        logger.error(f"列出待审核草稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats/review",
    response_model=List[ReviewStatsResponse],
    summary="获取审核统计",
    description="获取审核员的审核统计",
)
async def get_review_stats(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """获取审核统计"""
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None

        stats = await achievement_draft_service.get_review_stats(start, end)
        return [ReviewStatsResponse(**s) for s in stats]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {e}")
    except Exception as e:
        logger.error(f"获取审核统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{draft_id}",
    response_model=DraftResponse,
    summary="获取草稿详情",
)
async def get_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取草稿详情"""
    draft = await achievement_draft_service.get_by_id(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft_to_response(draft)


@router.put(
    "/{draft_id}",
    response_model=DraftResponse,
    summary="更新草稿",
    description="更新草稿（仅 DRAFT/RETURNED 状态可用）",
)
async def update_draft(
    draft_id: str,
    request: UpdateDraftRequest,
    current_user: dict = Depends(get_current_user),
):
    """更新草稿"""
    try:
        updates = request.model_dump(exclude_none=True)
        draft = await achievement_draft_service.update(
            draft_id=draft_id,
            user_id=str(current_user["id"]),
            **updates,
        )
        return draft_to_response(draft)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新草稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{draft_id}",
    summary="删除草稿",
    description="删除草稿（仅 DRAFT 状态可删除）",
)
async def delete_draft(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除草稿"""
    try:
        success = await achievement_draft_service.delete(draft_id, str(current_user["id"]))
        return {"success": success, "message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除草稿失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{draft_id}/submit",
    response_model=DraftResponse,
    summary="提交审核",
    description="提交草稿进行审核，需指定审核员",
)
async def submit_for_review(
    draft_id: str,
    request: SubmitReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交审核"""
    try:
        draft = await achievement_draft_service.submit_for_review(
            draft_id=draft_id,
            user_id=str(current_user["id"]),
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
        )
        return draft_to_response(draft)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"提交审核失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{draft_id}/review",
    response_model=DraftResponse,
    summary="执行审核操作",
    description="执行审核操作：通过、转交、退回提交人、退回上一级、作废",
)
async def review_draft(
    draft_id: str,
    request: ReviewActionRequest,
    current_user: dict = Depends(get_current_user),
):
    """执行审核操作"""
    try:
        draft = await achievement_draft_service.review(
            draft_id=draft_id,
            reviewer_id=str(current_user["id"]),
            reviewer_name=current_user.get("display_name") or current_user.get("username", ""),
            action=request.action,
            comment=request.comment,
            to_user_id=request.to_user_id,
            to_user_name=request.to_user_name,
        )
        return draft_to_response(draft)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"审核操作失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{draft_id}/logs",
    response_model=List[ReviewLogResponse],
    summary="获取审核日志",
    description="获取草稿的审核历史",
)
async def get_review_logs(
    draft_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取审核日志"""
    logs = await achievement_draft_service.get_review_logs(draft_id)
    return [ReviewLogResponse(**log.to_dict()) for log in logs]
