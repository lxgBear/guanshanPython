"""
统一聚合结果 API 端点 (v4.24.0)

提供统一的搜索结果聚合接口，解决 N+1 查询问题。

功能：
- 聚合多个数据源（定时任务、智能搜索、Chat搜索、文档上传）
- 服务端筛选（关键词、时间范围、采集方式）
- 服务端排序和分页
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.repositories.mongo.unified_result_repository import UnifiedResultRepository
from src.api.dependencies.auth import get_current_active_user
from src.core.domain.entities.auth.user import User
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/unified-results", tags=["📊 统一聚合结果"])


# ==========================================
# Pydantic 模型定义
# ==========================================

class UnifiedResultItem(BaseModel):
    """统一结果项"""
    id: str = Field(..., description="结果ID")
    title: str = Field(..., description="标题")
    url: str = Field("", description="URL链接")
    snippet: Optional[str] = Field(None, description="内容摘要（原始格式，可能是TipTap JSON）")
    snippet_text: Optional[str] = Field(None, description="内容摘要（纯文本，用于列表显示）")
    source_type: str = Field(..., description="采集方式 (scheduled/smart-search/chat-search/upload)")
    source_type_name: str = Field(..., description="采集方式显示名称")
    origin_site: str = Field(..., description="数据来源网站")
    task_id: str = Field(..., description="任务ID")
    task_name: Optional[str] = Field(None, description="所属任务名称")
    published_date: Optional[str] = Field(None, description="发布时间")
    created_at: Optional[str] = Field(None, description="采集时间")
    original_content: Optional[str] = Field(None, description="原文内容（原始格式，可能是TipTap JSON，用于编辑）")
    original_content_text: Optional[str] = Field(None, description="原文内容（纯文本，用于显示）")
    translated_content: Optional[str] = Field(None, description="译文内容")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "274127111587946497",
                "title": "示例文章标题",
                "url": "https://example.com/article",
                "snippet": '{"type":"doc","content":[...]}',
                "snippet_text": "文章摘要内容...",
                "source_type": "scheduled",
                "source_type_name": "定时任务",
                "origin_site": "example.com",
                "task_id": "274112567240638464",
                "task_name": "每日新闻监控",
                "published_date": "2026-01-26T10:00:00Z",
                "created_at": "2026-01-26T18:43:16Z",
                "original_content": '{"type":"doc","content":[...]}',
                "original_content_text": "文章原文内容..."
            }
        }


class SourceTypeStatistics(BaseModel):
    """按采集方式统计"""
    scheduled: int = Field(0, description="定时任务数量")
    smart_search: int = Field(0, alias="smart-search", description="智能搜索数量")
    chat_search: int = Field(0, alias="chat-search", description="Chat搜索数量")
    upload: int = Field(0, description="文档上传数量")

    class Config:
        populate_by_name = True


class UnifiedResultsResponse(BaseModel):
    """统一结果响应"""
    items: List[UnifiedResultItem] = Field(..., description="结果列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")
    statistics: Optional[Dict[str, Any]] = Field(None, description="统计信息")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "statistics": {
                    "by_source_type": {
                        "scheduled": 50,
                        "smart-search": 30,
                        "chat-search": 15,
                        "upload": 5
                    }
                }
            }
        }


# ==========================================
# 依赖注入
# ==========================================

async def get_unified_repository() -> UnifiedResultRepository:
    """获取统一结果仓储实例"""
    db = await get_mongodb_database()
    return UnifiedResultRepository(db)


# ==========================================
# API 端点
# ==========================================

@router.get(
    "/",
    response_model=UnifiedResultsResponse,
    summary="获取统一聚合结果",
    description="""
    从多个数据源聚合查询结果，支持服务端筛选、排序、分页。

    **数据源：**
    - `scheduled`: 定时任务结果
    - `smart-search`: 智能搜索结果（包含 Chat 搜索）
    - `chat-search`: Chat 搜索结果
    - `upload`: 文档上传

    **筛选条件：**
    - `keyword`: 关键词搜索（标题、摘要）
    - `source_type`: 采集方式筛选
    - `time_range`: 时间范围（today/week/month/custom）
    - `task_id`: 任务ID精确筛选

    **排序：**
    - `sort_by`: 排序字段（created_at/published_date）
    - `sort_order`: 排序方向（asc/desc）
    """
)
async def get_unified_results(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索（标题、摘要）"),
    source_type: str = Query(
        "all",
        description="采集方式筛选 (all/scheduled/smart-search/chat-search/upload)"
    ),
    time_range: str = Query(
        "all",
        description="时间范围 (all/today/week/month/custom)"
    ),
    date_start: Optional[str] = Query(
        None,
        description="自定义开始日期 (YYYY-MM-DD)，需配合 time_range=custom"
    ),
    date_end: Optional[str] = Query(
        None,
        description="自定义结束日期 (YYYY-MM-DD)，需配合 time_range=custom"
    ),
    task_id: Optional[str] = Query(None, description="任务ID精确筛选"),
    sort_by: str = Query(
        "created_at",
        description="排序字段 (created_at/published_date)"
    ),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    time_field: str = Query(
        "created_at",
        description="时间筛选字段 (created_at=采集时间/published_date=发布时间)"
    ),
    current_user: User = Depends(get_current_active_user),
    repository: UnifiedResultRepository = Depends(get_unified_repository)
):
    """
    获取统一聚合结果

    **核心优化：**
    - 解决 N+1 查询问题，一次 API 调用获取所有数据
    - 服务端筛选、排序、分页，提升大数据量场景性能
    - 统一响应格式，简化前端逻辑
    """
    try:
        logger.info(
            f"[UnifiedResults] 查询: user={current_user.id}, "
            f"source_type={source_type}, keyword={keyword}, "
            f"time_range={time_range}, page={page}"
        )

        # 解析日期参数
        parsed_date_start = None
        parsed_date_end = None

        if time_range == "custom":
            if date_start:
                try:
                    parsed_date_start = datetime.strptime(date_start, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无效的开始日期格式: {date_start}，请使用 YYYY-MM-DD"
                    )
            if date_end:
                try:
                    parsed_date_end = datetime.strptime(date_end, "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无效的结束日期格式: {date_end}，请使用 YYYY-MM-DD"
                    )

        # 验证 source_type
        valid_source_types = ["all", "scheduled", "smart-search", "chat-search", "upload"]
        if source_type not in valid_source_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 source_type: {source_type}，可选值: {valid_source_types}"
            )

        # 验证 time_range
        valid_time_ranges = ["all", "today", "week", "month", "custom"]
        if time_range not in valid_time_ranges:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 time_range: {time_range}，可选值: {valid_time_ranges}"
            )

        # 验证 sort_by
        valid_sort_fields = ["created_at", "published_date"]
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 sort_by: {sort_by}，可选值: {valid_sort_fields}"
            )

        # 验证 sort_order
        if sort_order not in ["asc", "desc"]:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 sort_order: {sort_order}，可选值: asc, desc"
            )

        # 验证 time_field
        valid_time_fields = ["created_at", "published_date"]
        if time_field not in valid_time_fields:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 time_field: {time_field}，可选值: {valid_time_fields}"
            )

        # 查询数据
        items, total, statistics = await repository.query_unified_results(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            source_type=source_type,
            time_range=time_range,
            date_start=parsed_date_start,
            date_end=parsed_date_end,
            task_id=task_id,
            sort_by=sort_by,
            sort_order=sort_order,
            time_field=time_field
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        logger.info(
            f"[UnifiedResults] 查询完成: total={total}, "
            f"returned={len(items)}, total_pages={total_pages}"
        )

        return UnifiedResultsResponse(
            items=[UnifiedResultItem(**item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            statistics={
                "by_source_type": statistics
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UnifiedResults] 查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
