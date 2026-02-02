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
from src.infrastructure.persistence.repositories.mongo.published_entry_repository import (
    PublishedEntryRepository,
)
from src.core.domain.entities.published_entry import PublishedEntry, PublishedStatus
from src.infrastructure.persistence.auth.mongodb.user_repository import MongoUserRepository
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


class SubmitForReviewRequest(BaseModel):
    """提交审核请求"""
    reviewer_id: str = Field(..., description="审核员ID")


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
    author_name: str = ""  # 作者用户名（display_name 或 username）
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_id: str
    reviewer_name: str = ""  # 审核员用户名（display_name 或 username）
    review_comment: str


class ReviewEntryListResponse(BaseModel):
    """审核条目列表响应"""
    items: List[ReviewEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MyEntryResponse(BaseModel):
    """我的条目响应（扩展版，用于 dashboard 列表）"""
    id: str
    title: str
    translated_title: str = ""  # 翻译后的标题
    status: str
    entry_type: str
    # 扩展字段 - 用于草稿箱列表展示和筛选
    summary: str = ""
    primary_category: str = ""
    secondary_category: str = ""
    tertiary_category: str = ""
    tags: List[str] = []
    raw_data_count: int = 0
    # 审核相关
    reviewer_name: str = ""  # 审核员用户名
    # 时间字段
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

# 用户名缓存（避免重复查询）
_user_name_cache: dict = {}


async def get_user_display_name(user_id: str) -> str:
    """获取用户显示名称（优先 display_name，其次 username）"""
    if not user_id:
        return ""

    # 检查缓存
    if user_id in _user_name_cache:
        return _user_name_cache[user_id]

    try:
        user_repo = MongoUserRepository()
        user = await user_repo.get_by_id(user_id)
        if user:
            name = user.get("display_name") or user.get("username") or ""
            _user_name_cache[user_id] = name
            return name
    except Exception as e:
        logger.warning(f"获取用户名失败: user_id={user_id}, error={e}")

    return ""


async def entry_to_response(entry: ReviewEntry) -> ReviewEntryResponse:
    """将 ReviewEntry 转换为响应模型"""
    # 获取用户名
    author_name = await get_user_display_name(entry.user_id)
    reviewer_name = await get_user_display_name(entry.reviewer_id)

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
        author_name=author_name,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        reviewer_id=entry.reviewer_id,
        reviewer_name=reviewer_name,
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
            entry=await entry_to_response(created_entry),
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
    
    # v4.32.0: 构建扩展响应，包含分类、标签等字段用于前端列表展示
    items = []
    for entry in entries:
        # 获取审核员用户名
        reviewer_name = ""
        if entry.reviewer_id:
            reviewer_name = await get_user_display_name(entry.reviewer_id)

        # 获取翻译标题（从第一个原始数据引用中获取）
        translated_title = ""
        if entry.raw_data_refs and len(entry.raw_data_refs) > 0:
            translated_title = entry.raw_data_refs[0].translated_title or ""

        items.append(MyEntryResponse(
            id=entry.id,
            title=entry.title,
            translated_title=translated_title,
            status=entry.status.value,
            entry_type=entry.entry_type.value,
            # 新增字段
            summary=entry.summary or "",
            primary_category=entry.primary_category or "",
            secondary_category=entry.secondary_category or "",
            tertiary_category=entry.tertiary_category or "",
            tags=entry.tags or [],
            raw_data_count=entry.raw_data_count,
            reviewer_name=reviewer_name,
            # 时间字段
            created_at=entry.created_at.isoformat() if entry.created_at else None,
            updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
            submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
            reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
            reviewer_id=entry.reviewer_id or "",
            review_comment=entry.review_comment or "",
        ))
    
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

    # 异步转换所有条目
    items = [await entry_to_response(e) for e in entries]

    return ReviewEntryListResponse(
        items=items,
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

    # 异步转换所有条目
    items = [await entry_to_response(e) for e in entries]

    return ReviewEntryListResponse(
        items=items,
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

    # 权限检查：允许条目所有者、指定审核员、具有审核权限的用户或管理员查看
    is_owner = entry.user_id == current_user.id
    is_assigned_reviewer = entry.reviewer_id and entry.reviewer_id == current_user.id
    is_admin = "admin" in current_user.roles if current_user.roles else False
    # 有审核权限的用户可以查看待审核状态的条目
    has_review_permission = "review:approve" in (current_user.permissions or [])
    can_view_pending = has_review_permission and entry.status == ReviewStatus.PENDING_REVIEW

    if not (is_owner or is_assigned_reviewer or is_admin or can_view_pending):
        raise HTTPException(status_code=403, detail="无权访问此条目")

    return await entry_to_response(entry)


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

    # 权限和状态检查
    is_owner = entry.user_id == current_user.id
    is_assigned_reviewer = entry.reviewer_id and entry.reviewer_id == current_user.id
    is_admin = "admin" in current_user.roles if current_user.roles else False
    has_review_permission = "review:approve" in (current_user.permissions or [])
    can_edit_pending = has_review_permission and entry.status == ReviewStatus.PENDING_REVIEW

    # 所有者只能编辑草稿和退回状态
    if is_owner and not is_admin and entry.status not in [ReviewStatus.DRAFT, ReviewStatus.REJECTED]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许编辑"
        )

    # 审核员只能编辑待审核状态
    if (is_assigned_reviewer or can_edit_pending) and not is_owner and not is_admin:
        if entry.status != ReviewStatus.PENDING_REVIEW:
            raise HTTPException(
                status_code=400,
                detail=f"当前状态（{entry.status.value}）不允许审核员编辑"
            )

    # 既不是所有者也不是审核员也不是管理员
    if not (is_owner or is_assigned_reviewer or is_admin or can_edit_pending):
        raise HTTPException(status_code=403, detail="无权修改此条目")

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
    return await entry_to_response(updated_entry)


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
    description="将条目提交审核，需指定审核员",
)
async def submit_for_review(
    entry_id: str,
    request: SubmitForReviewRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """提交审核

    Args:
        entry_id: 条目ID
        request: 提交审核请求，包含审核员ID
    """
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

    # 验证审核员ID不能为空
    if not request.reviewer_id:
        raise HTTPException(status_code=400, detail="必须指定审核员")

    updated_entry = await repo.submit_for_review(
        entry_id=entry_id,
        reviewer_id=request.reviewer_id
    )
    if not updated_entry:
        raise HTTPException(status_code=500, detail="提交审核失败")

    logger.info(
        f"条目提交审核: id={entry_id}, user={current_user.id}, "
        f"reviewer={request.reviewer_id}"
    )
    return await entry_to_response(updated_entry)


@router.post(
    "/{entry_id}/approve",
    summary="通过审核",
    description="通过审核，将内容发布到 published_entries 并删除草稿",
)
async def approve_entry(
    entry_id: str,
    request: ReviewActionRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """通过审核（具有审核权限的用户）

    流程：
    1. 权限校验和状态校验
    2. 读取 review_entries 完整数据
    3. 创建 PublishedEntry 写入 published_entries
    4. 物理删除 review_entries 中的记录
    5. 返回 PublishedEntryResponse
    """
    review_repo = ReviewEntryRepository(db)
    entry = await review_repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    # 权限检查：允许指定审核员、具有审核权限的用户或管理员操作
    is_assigned_reviewer = entry.reviewer_id and entry.reviewer_id == current_user.id
    is_admin = "admin" in current_user.roles if current_user.roles else False
    has_review_permission = "review:approve" in (current_user.permissions or [])
    if not (is_assigned_reviewer or is_admin or has_review_permission):
        raise HTTPException(status_code=403, detail="无权审核此条目")

    if entry.status != ReviewStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态（{entry.status.value}）不允许审核操作"
        )

    now = datetime.utcnow()

    # 创建 PublishedEntry（从草稿复制内容 + 审核溯源）
    published_entry = PublishedEntry(
        title=entry.title,
        description=entry.description,
        summary=entry.summary,
        combined_content=entry.combined_content,
        tags=entry.tags,
        primary_category=entry.primary_category,
        secondary_category=entry.secondary_category,
        tertiary_category=entry.tertiary_category,
        entry_type=entry.entry_type.value,
        raw_data_refs=entry.raw_data_refs,
        author_id=entry.user_id,
        reviewer_id=current_user.id,
        review_comment=request.comment or "",
        submitted_at=entry.submitted_at,
        reviewed_at=now,
        status=PublishedStatus.PUBLISHED,
        published_at=now,
    )

    # 先插入 published_entries（安全机制：插入失败不删除草稿）
    pub_repo = PublishedEntryRepository(db)
    try:
        await pub_repo.create(published_entry)
    except Exception as e:
        logger.error(f"创建发布条目失败: {e}")
        raise HTTPException(status_code=500, detail="发布失败，草稿未删除")

    # 插入成功后，删除 review_entries 中的草稿
    try:
        await review_repo.delete(entry_id)
    except Exception as e:
        logger.warning(f"删除草稿失败（发布已成功）: id={entry_id}, error={e}")

    logger.info(
        f"条目审核通过并发布: review_id={entry_id}, "
        f"published_id={published_entry.id}, reviewer={current_user.id}"
    )

    # 返回发布条目信息
    from src.api.v1.endpoints.published_entries import published_entry_to_response
    return await published_entry_to_response(published_entry)


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
    """退回审核（具有审核权限的用户）"""
    repo = ReviewEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    # 权限检查：允许指定审核员、具有审核权限的用户或管理员操作
    is_assigned_reviewer = entry.reviewer_id and entry.reviewer_id == current_user.id
    is_admin = "admin" in current_user.roles if current_user.roles else False
    has_review_permission = "review:approve" in (current_user.permissions or [])
    if not (is_assigned_reviewer or is_admin or has_review_permission):
        raise HTTPException(status_code=403, detail="无权审核此条目")

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
    return await entry_to_response(updated_entry)
