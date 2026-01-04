"""
档案审核管理API (v2.7.0)

提供档案审核工作流的RESTful API端点
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import logging

from src.api.dependencies.auth import require_permissions, get_current_active_user
from src.core.domain.entities.auth import User
from src.services.nl_search.mongo_archive_service import mongo_archive_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review")


# ==================== 数据模型 ====================

class ArchiveItemResponse(BaseModel):
    id: int
    news_result_id: str
    title: str
    content: Optional[str] = None
    edited_title: Optional[str] = None
    edited_summary: Optional[str] = None
    user_notes: Optional[str] = None
    user_rating: Optional[int] = None
    category: Optional[Any] = None
    source: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None


class ArchiveResponse(BaseModel):
    archive_id: str
    user_id: int
    archive_name: str
    description: Optional[str] = None
    tags: List[str] = []
    search_log_id: Optional[str] = None
    search_task_id: Optional[str] = None
    items_count: int = 0
    items: Optional[List[ArchiveItemResponse]] = None
    generated_report: Optional[str] = None
    user_summary: Optional[str] = None
    status: str = "pending"
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_feedback: Optional[str] = None
    submission_count: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ArchiveStatistics(BaseModel):
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class ArchiveListResponse(BaseModel):
    total: int
    items: List[ArchiveResponse]
    page: int
    page_size: int
    statistics: Optional[ArchiveStatistics] = None


class ArchiveStatsResponse(BaseModel):
    pending: int
    approved: int
    rejected: int
    total: int


# ==================== API端点 ====================

@router.get("/pending", response_model=ArchiveListResponse, summary="获取待审核档案列表")
async def get_pending_archives(
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected|submitted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """获取待审核档案列表（支持按状态筛选）"""
    try:
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else current_user.id

        # 映射 submitted 为 pending（前端兼容）
        effective_status = "pending" if status == "submitted" else status

        offset = (page - 1) * page_size

        archives = await mongo_archive_service.list_archives_by_status(
            user_id=effective_user_id,
            status=effective_status,
            limit=page_size,
            offset=offset
        )

        items = [
            ArchiveResponse(
                archive_id=a["archive_id"],
                user_id=a["user_id"],
                archive_name=a["archive_name"],
                description=a.get("description"),
                tags=a.get("tags", []),
                search_log_id=a.get("search_log_id"),
                search_task_id=a.get("search_task_id"),
                items_count=a.get("items_count", 0),
                status=a.get("status", "pending"),
                reviewer_id=a.get("reviewer_id"),
                reviewer_name=a.get("reviewer_name"),
                reviewed_at=a.get("reviewed_at"),
                rejection_feedback=a.get("rejection_feedback"),
                submission_count=a.get("submission_count", 1),
                created_at=a.get("created_at"),
                updated_at=a.get("updated_at")
            )
            for a in archives
        ]

        # 获取统计信息
        stats = await mongo_archive_service.get_archive_stats(user_id=effective_user_id)
        statistics = ArchiveStatistics(
            pending=stats.get("pending", 0),
            approved=stats.get("approved", 0),
            rejected=stats.get("rejected", 0)
        )

        return ArchiveListResponse(
            total=len(items),
            items=items,
            page=page,
            page_size=page_size,
            statistics=statistics
        )

    except Exception as e:
        logger.error(f"查询审核档案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "服务错误", "message": str(e)})


@router.get("/stats", response_model=ArchiveStatsResponse, summary="获取审核统计")
async def get_review_stats(current_user: User = Depends(get_current_active_user)):
    """获取各状态的档案数量统计"""
    try:
        is_admin = "admin" in current_user.roles
        user_id = None if is_admin else current_user.id
        stats = await mongo_archive_service.get_archive_stats(user_id=user_id)
        return ArchiveStatsResponse(**stats)
    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "服务错误", "message": str(e)})
