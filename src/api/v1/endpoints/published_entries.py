"""发布条目 API 端点

提供已发布内容的列表、详情查询和联动统计接口。
"""

from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.dependencies.auth import get_current_user
from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.auth import User
from src.infrastructure.persistence.repositories.mongo.published_entry_repository import (
    PublishedEntryRepository,
)
from src.core.domain.entities.published_entry import PublishedEntry
from src.api.v1.endpoints.review_entries import (
    RawDataRefResponse,
    get_user_display_name,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/published-entries", tags=["📢 发布条目"])


# ==================== 响应模型 ====================

class PublishedEntryResponse(BaseModel):
    """发布条目完整响应（详情接口）"""
    id: str
    title: str
    description: str
    summary: str
    combined_content: str
    tags: List[str]
    primary_category: str
    secondary_category: str
    tertiary_category: str
    entry_type: str
    raw_data_refs: List[RawDataRefResponse]
    raw_data_count: int
    # 审核溯源
    author_id: str
    author_name: str = ""
    reviewer_id: str
    reviewer_name: str = ""
    review_comment: str
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    # 发布信息
    status: str
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PublishedEntryListItem(BaseModel):
    """发布条目列表项（不含大字段）"""
    id: str
    title: str
    description: str
    summary: str
    tags: List[str]
    primary_category: str
    secondary_category: str
    tertiary_category: str
    entry_type: str
    raw_data_count: int
    # 审核溯源
    author_id: str
    author_name: str = ""
    reviewer_id: str
    reviewer_name: str = ""
    review_comment: str
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    # 发布信息
    status: str
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PublishedEntryListResponse(BaseModel):
    """发布条目列表响应"""
    items: List[PublishedEntryListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PublishedEntryStatsResponse(BaseModel):
    """发布条目联动统计响应"""
    entry_type_stats: Dict[str, int]
    category_stats: Dict[str, int]
    secondary_category_stats: Dict[str, int]
    tertiary_category_stats: Dict[str, int]
    total: int


# ==================== 辅助函数 ====================

async def published_entry_to_response(entry: PublishedEntry) -> PublishedEntryResponse:
    """将 PublishedEntry 转换为完整响应模型（详情接口用）"""
    author_name = await get_user_display_name(entry.author_id)
    reviewer_name = await get_user_display_name(entry.reviewer_id)

    return PublishedEntryResponse(
        id=entry.id,
        title=entry.title,
        description=entry.description,
        summary=entry.summary,
        combined_content=entry.combined_content,
        tags=entry.tags,
        primary_category=entry.primary_category,
        secondary_category=entry.secondary_category,
        tertiary_category=entry.tertiary_category,
        entry_type=entry.entry_type,
        raw_data_refs=[
            RawDataRefResponse(
                ref_id=ref.ref_id,
                data_id=ref.data_id,
                data_type=ref.data_type,
                source_collection=ref.source_collection,
                title=ref.title or "",
                url=ref.url or "",
                origin_site=ref.origin_site or "",
                published_date=ref.published_date.isoformat() if ref.published_date else None,
                markdown_content=ref.markdown_content or "",
                snippet=ref.snippet or "",
                translated_title=ref.translated_title or "",
                translated_content=ref.translated_content or "",
                translated_at=ref.translated_at.isoformat() if ref.translated_at else None,
                task_name=ref.task_name or "",
            )
            for ref in entry.raw_data_refs
        ],
        raw_data_count=entry.raw_data_count,
        author_id=entry.author_id,
        author_name=author_name,
        reviewer_id=entry.reviewer_id,
        reviewer_name=reviewer_name,
        review_comment=entry.review_comment,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        status=entry.status.value,
        published_at=entry.published_at.isoformat() if entry.published_at else None,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
    )


async def published_entry_to_list_item(entry: PublishedEntry) -> PublishedEntryListItem:
    """将 PublishedEntry 转换为列表项（不含 combined_content 和 raw_data_refs）"""
    author_name = await get_user_display_name(entry.author_id)
    reviewer_name = await get_user_display_name(entry.reviewer_id)

    return PublishedEntryListItem(
        id=entry.id,
        title=entry.title,
        description=entry.description,
        summary=entry.summary,
        tags=entry.tags,
        primary_category=entry.primary_category,
        secondary_category=entry.secondary_category,
        tertiary_category=entry.tertiary_category,
        entry_type=entry.entry_type,
        raw_data_count=entry.raw_data_count,
        author_id=entry.author_id,
        author_name=author_name,
        reviewer_id=entry.reviewer_id,
        reviewer_name=reviewer_name,
        review_comment=entry.review_comment,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        status=entry.status.value,
        published_at=entry.published_at.isoformat() if entry.published_at else None,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
    )


def _parse_comma_list(value: Optional[str]) -> Optional[List[str]]:
    """解析逗号分隔的字符串为列表"""
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


# ==================== API 端点 ====================

@router.get(
    "/stats",
    response_model=PublishedEntryStatsResponse,
    summary="获取发布条目联动统计",
    description="根据当前筛选条件返回各维度的计数统计。每个维度的统计排除该维度自身的筛选。",
)
async def get_published_entry_stats(
    entry_type: Optional[str] = Query(None, description="成果类型筛选（逗号分隔）: single,entry"),
    primary_category: Optional[str] = Query(None, description="情报分类: security/competitive/maritime"),
    secondary_category: Optional[str] = Query(None, description="细分类型筛选（逗号分隔）"),
    tertiary_category: Optional[str] = Query(None, description="地域筛选（逗号分隔）"),
    start_date: Optional[str] = Query(None, description="开始日期 (ISO format)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO format)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取发布条目联动统计"""
    repo = PublishedEntryRepository(db)

    stats = await repo.get_stats(
        primary_category=primary_category,
        secondary_categories=_parse_comma_list(secondary_category),
        tertiary_categories=_parse_comma_list(tertiary_category),
        entry_types=_parse_comma_list(entry_type),
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
    )

    return PublishedEntryStatsResponse(**stats)


@router.get(
    "/",
    response_model=PublishedEntryListResponse,
    summary="获取发布条目列表",
    description="获取已发布内容列表，支持分页、多维度筛选、搜索、排序",
)
async def list_published_entries(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    entry_type: Optional[str] = Query(None, description="成果类型筛选（逗号分隔）: single,entry"),
    primary_category: Optional[str] = Query(None, description="情报分类: security/competitive/maritime"),
    secondary_category: Optional[str] = Query(None, description="细分类型筛选（逗号分隔）"),
    tertiary_category: Optional[str] = Query(None, description="地域筛选（逗号分隔）"),
    start_date: Optional[str] = Query(None, description="开始日期 (ISO format)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO format)"),
    keyword: Optional[str] = Query(None, description="关键词搜索（标题、描述、摘要）"),
    sort_by: str = Query("published_at", description="排序字段: published_at/created_at/reviewed_at/title"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取发布条目列表"""
    repo = PublishedEntryRepository(db)
    sort_order_int = 1 if sort_order == "asc" else -1

    entries, total = await repo.list_entries(
        page=page,
        page_size=page_size,
        primary_category=primary_category,
        secondary_categories=_parse_comma_list(secondary_category),
        tertiary_categories=_parse_comma_list(tertiary_category),
        entry_types=_parse_comma_list(entry_type),
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order_int,
        exclude_fields=["combined_content", "raw_data_refs"],
    )

    total_pages = (total + page_size - 1) // page_size
    items = [await published_entry_to_list_item(e) for e in entries]

    return PublishedEntryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{entry_id}",
    response_model=PublishedEntryResponse,
    summary="获取发布条目详情",
    description="根据ID获取发布条目详情（含完整内容和原始数据引用）",
)
async def get_published_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取发布条目详情"""
    repo = PublishedEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="发布条目不存在")

    return await published_entry_to_response(entry)
