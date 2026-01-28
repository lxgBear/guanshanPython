"""审核条目 API 端点

v1.0.0 初始版本：
- 创建审核条目（草稿保存）
- 获取条目列表
- 获取条目详情
- 更新条目
- 删除条目
- 提交审核
- 通过/退回审核（管理员）
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_user
from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.auth import User
from src.core.domain.entities.review_entry import (
    ReviewEntry,
    ReviewStatus,
    EntryType,
)
from src.core.domain.entities.info_entry import RawDataRef
from src.infrastructure.persistence.repositories.mongo.review_entry_repository import (
    ReviewEntryRepository,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/review-entries", tags=["📋 审核条目"])


# ==================== 请求模型 ====================

class RawDataRefInput(BaseModel):
    """原始数据引用输入"""
    data_id: str = Field(..., description="原始数据ID")
    data_type: str = Field(..., description="数据类型: scheduled/smart-search/chat-search/upload/manual")


class CreateReviewEntryRequest(BaseModel):
    """创建审核条目请求"""
    title: str = Field(..., description="条目标题", min_length=1, max_length=200)
    description: Optional[str] = Field("", description="条目描述")
    summary: Optional[str] = Field("", description="摘要")
    combined_content: Optional[str] = Field("", description="编辑内容（TipTap JSON）")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    primary_category: Optional[str] = Field("", description="大类")
    secondary_category: Optional[str] = Field("", description="类别")
    tertiary_category: Optional[str] = Field("", description="地域")
    entry_type: str = Field("single", description="条目类型: single/batch")
    raw_data_refs: List[RawDataRefInput] = Field(..., description="原始数据引用列表", min_length=1)
    source_entry_id: Optional[str] = Field("", description="关联的 info_entry ID（可选）")
    reviewer_id: Optional[str] = Field(None, description="指定审核员ID（提交时使用）")


class UpdateReviewEntryRequest(BaseModel):
    """更新审核条目请求"""
    title: Optional[str] = Field(None, description="条目标题", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="条目描述")
    summary: Optional[str] = Field(None, description="摘要")
    combined_content: Optional[str] = Field(None, description="编辑内容")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    primary_category: Optional[str] = Field(None, description="大类")
    secondary_category: Optional[str] = Field(None, description="类别")
    tertiary_category: Optional[str] = Field(None, description="地域")


class ReviewActionRequest(BaseModel):
    """审核操作请求"""
    comment: Optional[str] = Field("", description="审核意见")


# ==================== 响应模型 ====================

class RawDataRefResponse(BaseModel):
    """原始数据引用响应"""
    ref_id: str
    data_id: str
    data_type: str
    source_collection: str
    title: str = ""
    url: str = ""
    origin_site: str = ""
    published_date: Optional[str] = None
    markdown_content: str = ""
    html_content: str = ""
    snippet: str = ""
    translated_title: str = ""
    translated_content: str = ""
    translated_at: Optional[str] = None
    task_name: str = ""


class ReviewEntryResponse(BaseModel):
    """审核条目响应"""
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
    status: str
    raw_data_refs: List[RawDataRefResponse]
    raw_data_count: int
    source_entry_id: str
    user_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_id: str
    review_comment: str


class ReviewEntryListResponse(BaseModel):
    """审核条目列表响应"""
    items: List[ReviewEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MyEntryResponse(BaseModel):
    """我的条目响应（简化版，用于 dashboard 列表）"""
    id: str
    title: str
    status: str
    entry_type: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_id: str = ""
    review_comment: str = ""


class MyEntryListResponse(BaseModel):
    """我的条目列表响应"""
    items: List[MyEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateReviewEntryResponse(BaseModel):
    """创建审核条目响应"""
    success: bool
    message: str
    entry: Optional[ReviewEntryResponse] = None


# ==================== 辅助函数 ====================

def entry_to_response(entry: ReviewEntry) -> ReviewEntryResponse:
    """将 ReviewEntry 转换为响应模型"""
    return ReviewEntryResponse(
        id=entry.id,
        title=entry.title,
        description=entry.description,
        summary=entry.summary,
        combined_content=entry.combined_content,
        tags=entry.tags,
        primary_category=entry.primary_category,
        secondary_category=entry.secondary_category,
        tertiary_category=entry.tertiary_category,
        entry_type=entry.entry_type.value,
        status=entry.status.value,
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
                html_content=ref.html_content or "",
                snippet=ref.snippet or "",
                translated_title=ref.translated_title or "",
                translated_content=ref.translated_content or "",
                translated_at=ref.translated_at.isoformat() if ref.translated_at else None,
                task_name=ref.task_name or "",
            )
            for ref in entry.raw_data_refs
        ],
        raw_data_count=entry.raw_data_count,
        source_entry_id=entry.source_entry_id,
        user_id=entry.user_id,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        reviewer_id=entry.reviewer_id,
        review_comment=entry.review_comment,
    )


# ==================== API 端点 ====================

@router.post(
    "/",
    response_model=CreateReviewEntryResponse,
    summary="创建审核条目（保存草稿）",
    description="创建审核条目并保存为草稿状态",
)
async def create_review_entry(
    request: CreateReviewEntryRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """创建审核条目（保存草稿）"""
    try:
        repo = ReviewEntryRepository(db)

        # 从数据源获取原始数据
        data_refs_input = [
            {
                "data_id": ref.data_id,
                "data_type": ref.data_type,
            }
            for ref in request.raw_data_refs
        ]

        raw_data_refs = await repo.fetch_raw_data_from_sources(data_refs_input)

        # 校验必须全部获取成功
        if len(raw_data_refs) != len(request.raw_data_refs):
            fetched_ids = {ref.data_id for ref in raw_data_refs}
            requested_ids = {ref.data_id for ref in request.raw_data_refs}
            failed_ids = requested_ids - fetched_ids
            logger.warning(
                f"部分原始数据获取失败: 期望 {len(request.raw_data_refs)}, "
                f"实际 {len(raw_data_refs)}, 失败ID: {failed_ids}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"以下数据获取失败: {', '.join(failed_ids)}"
            )

        # 确定条目类型
        entry_type = EntryType(request.entry_type)

        # 创建条目实体
        entry = ReviewEntry(
            title=request.title,
            description=request.description or "",
            summary=request.summary or "",
            combined_content=request.combined_content or "",
            tags=request.tags or [],
            primary_category=request.primary_category or "",
            secondary_category=request.secondary_category or "",
            tertiary_category=request.tertiary_category or "",
            entry_type=entry_type,
            status=ReviewStatus.DRAFT,
            raw_data_refs=raw_data_refs,
            source_entry_id=request.source_entry_id or "",
            user_id=current_user.id,
            reviewer_id=request.reviewer_id or "",  # 指定审核员
        )

        # 保存到数据库
        created_entry = await repo.create(entry)

        logger.info(
            f"创建审核条目成功: id={created_entry.id}, title={request.title}, "
            f"entry_type={entry_type.value}, raw_data_count={len(raw_data_refs)}, user={current_user.id}"
        )

        return CreateReviewEntryResponse(
            success=True,
            message=f"草稿保存成功，包含 {len(raw_data_refs)} 条原始数据",
            entry=entry_to_response(created_entry),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建审核条目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建条目失败: {str(e)}")


@router.get(
    "/my",
    response_model=MyEntryListResponse,
    summary="获取我的条目列表",
    description="获取当前用户的所有条目（草稿+审核流程），支持分页、筛选、搜索、排序",
)
async def get_my_entries(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: draft/pending_review/approved/rejected"),
    keyword: Optional[str] = Query(None, description="关键词搜索（标题、描述）"),
    sort_by: str = Query("updated_at", description="排序字段: updated_at/created_at/submitted_at/title"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """
    获取当前用户的所有条目列表
    
    用于 dashboard 展示：
    - 草稿列表
    - 提交审核后的流程状态列表
    """
    repo = ReviewEntryRepository(db)
    
    # 转换排序方向
    sort_order_int = 1 if sort_order == "asc" else -1
    
    entries, total = await repo.list_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order_int,
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    items = [
        MyEntryResponse(
            id=entry.id,
            title=entry.title,
            status=entry.status.value,
            entry_type=entry.entry_type.value,
            created_at=entry.created_at.isoformat() if entry.created_at else None,
            updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
            submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
            reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
            reviewer_id=entry.reviewer_id or "",
            review_comment=entry.review_comment or "",
        )
        for entry in entries
    ]
    
    return MyEntryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/",
    response_model=ReviewEntryListResponse,
    summary="获取审核条目列表",
    description="获取当前用户的审核条目列表，支持分页和筛选",
)
async def list_review_entries(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: draft/pending_review/approved/rejected"),
    entry_type: Optional[str] = Query(None, description="类型筛选: single/batch"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取审核条目列表"""
    repo = ReviewEntryRepository(db)
    entries, total = await repo.list_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        entry_type=entry_type,
        keyword=keyword,
    )

    total_pages = (total + page_size - 1) // page_size

    return ReviewEntryListResponse(
        items=[entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/pending",
    response_model=ReviewEntryListResponse,
    summary="获取待审核列表（管理员）",
    description="获取所有待审核的条目列表",
)
async def list_pending_reviews(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    entry_type: Optional[str] = Query(None, description="类型筛选: single/batch"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取待审核列表（管理员）"""
    # TODO: 添加管理员权限校验
    repo = ReviewEntryRepository(db)
    entries, total = await repo.list_pending_reviews(
        page=page,
        page_size=page_size,
        entry_type=entry_type,
        keyword=keyword,
    )

    total_pages = (total + page_size - 1) // page_size

    return ReviewEntryListResponse(
        items=[entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{entry_id}",
    response_model=ReviewEntryResponse,
    summary="获取审核条目详情",
    description="根据ID获取审核条目详情",
)
async def get_review_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取审核条目详情"""
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    # 只允许条目所有者或管理员查看
    # TODO: 添加管理员权限校验
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此条目")

    return entry_to_response(entry)


@router.put(
    "/{entry_id}",
    response_model=ReviewEntryResponse,
    summary="更新审核条目",
    description="更新审核条目信息（仅草稿和退回状态可编辑）",
)
async def update_review_entry(
    entry_id: str,
    request: UpdateReviewEntryRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """更新审核条目"""
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此条目")

    # 只有草稿和退回状态可以编辑
    if entry.status not in [ReviewStatus.DRAFT, ReviewStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许编辑"
        )

    # 更新字段
    if request.title is not None:
        entry.title = request.title
    if request.description is not None:
        entry.description = request.description
    if request.summary is not None:
        entry.summary = request.summary
    if request.combined_content is not None:
        entry.combined_content = request.combined_content
    if request.tags is not None:
        entry.tags = request.tags
    if request.primary_category is not None:
        entry.primary_category = request.primary_category
    if request.secondary_category is not None:
        entry.secondary_category = request.secondary_category
    if request.tertiary_category is not None:
        entry.tertiary_category = request.tertiary_category

    updated_entry = await repo.update(entry)
    return entry_to_response(updated_entry)


@router.delete(
    "/{entry_id}",
    summary="删除审核条目",
    description="删除指定审核条目（仅草稿和退回状态可删除）",
)
async def delete_review_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """删除审核条目"""
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此条目")

    # 只有草稿和退回状态可以删除
    if entry.status not in [ReviewStatus.DRAFT, ReviewStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许删除"
        )

    success = await repo.delete(entry_id)
    if success:
        return {"success": True, "message": "删除成功"}
    else:
        raise HTTPException(status_code=500, detail="删除失败")


@router.post(
    "/{entry_id}/submit",
    response_model=ReviewEntryResponse,
    summary="提交审核",
    description="将条目提交审核",
)
async def submit_for_review(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """提交审核"""
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此条目")

    # 只有草稿和退回状态可以提交审核
    if entry.status not in [ReviewStatus.DRAFT, ReviewStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许提交审核"
        )

    updated_entry = await repo.submit_for_review(entry_id)
    if not updated_entry:
        raise HTTPException(status_code=500, detail="提交审核失败")

    logger.info(f"条目提交审核: id={entry_id}, user={current_user.id}")
    return entry_to_response(updated_entry)


@router.post(
    "/{entry_id}/approve",
    response_model=ReviewEntryResponse,
    summary="通过审核",
    description="通过审核（管理员）",
)
async def approve_entry(
    entry_id: str,
    request: ReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """通过审核（管理员）"""
    # TODO: 添加管理员权限校验
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.status != ReviewStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许审核操作"
        )

    updated_entry = await repo.approve(
        entry_id=entry_id,
        reviewer_id=current_user.id,
        comment=request.comment or "",
    )
    if not updated_entry:
        raise HTTPException(status_code=500, detail="审核操作失败")

    logger.info(f"条目审核通过: id={entry_id}, reviewer={current_user.id}")
    return entry_to_response(updated_entry)


@router.post(
    "/{entry_id}/reject",
    response_model=ReviewEntryResponse,
    summary="退回审核",
    description="退回审核（管理员）",
)
async def reject_entry(
    entry_id: str,
    request: ReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """退回审核（管理员）"""
    # TODO: 添加管理员权限校验
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.status != ReviewStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许审核操作"
        )

    updated_entry = await repo.reject(
        entry_id=entry_id,
        reviewer_id=current_user.id,
        comment=request.comment or "",
    )
    if not updated_entry:
        raise HTTPException(status_code=500, detail="审核操作失败")

    logger.info(f"条目审核退回: id={entry_id}, reviewer={current_user.id}")
    return entry_to_response(updated_entry)
