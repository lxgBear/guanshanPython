"""信息条目 API 端点

v1.0.0 初始版本：
- 创建条目（从多个数据源选择数据合并）
- 获取条目列表
- 获取条目详情
- 更新条目
- 删除条目
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies.auth import get_current_user
from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.auth import User
from src.core.domain.entities.info_entry import (
    InfoEntry,
    RawDataRef,
    EntryStatus,
)
from src.infrastructure.persistence.repositories.mongo.info_entry_repository import (
    InfoEntryRepository,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/info-entries", tags=["📝 信息条目"])


# ==================== 请求模型 ====================

class RawDataRefInput(BaseModel):
    """原始数据引用输入（简化版）

    v1.1.0: 移除快照字段，只传 data_type + data_id，后台自动查询完整数据
    """
    data_id: str = Field(..., description="原始数据ID")
    data_type: str = Field(..., description="数据类型: scheduled/smart-search/chat-search/upload/manual")


class CreateEntryRequest(BaseModel):
    """创建条目请求"""
    title: str = Field(..., description="条目标题", min_length=1, max_length=200)
    description: Optional[str] = Field("", description="条目描述")
    summary: Optional[str] = Field("", description="摘要")
    combined_content: Optional[str] = Field("", description="合并后的内容（TipTap JSON）")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    primary_category: Optional[str] = Field("", description="大类")
    secondary_category: Optional[str] = Field("", description="类别")
    tertiary_category: Optional[str] = Field("", description="地域")
    raw_data_refs: List[RawDataRefInput] = Field(..., description="原始数据引用列表", min_length=1)


class UpdateEntryRequest(BaseModel):
    """更新条目请求"""
    title: Optional[str] = Field(None, description="条目标题", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="条目描述")
    summary: Optional[str] = Field(None, description="摘要")
    combined_content: Optional[str] = Field(None, description="合并后的内容")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    primary_category: Optional[str] = Field(None, description="大类")
    secondary_category: Optional[str] = Field(None, description="类别")
    tertiary_category: Optional[str] = Field(None, description="地域")
    status: Optional[str] = Field(None, description="状态: draft/published/archived")


class CreateFromSingleRequest(BaseModel):
    """从单条信息创建条目请求

    用于将 compile 页面编辑的单条信息保存到 info_entries
    """
    # 原始数据信息
    source_data_id: str = Field(..., description="原数据 ID")
    source_data_type: str = Field(..., description="数据类型: scheduled/smart-search/chat-search/upload/manual")
    source_collection: str = Field(..., description="来源集合名")

    # 内容字段
    title: str = Field(..., description="标题", min_length=1, max_length=200)
    markdown_content: str = Field("", description="原文内容")
    translated_content: str = Field("", description="译文内容")
    translated_title: str = Field("", description="翻译后标题")
    snippet: str = Field("", description="摘要")
    url: str = Field("", description="原文 URL")
    origin_site: str = Field("", description="来源网站")
    published_date: Optional[datetime] = Field(None, description="发布日期")

    # 分类
    primary_category: str = Field("", description="大类")
    secondary_category: str = Field("", description="类别")
    tertiary_category: str = Field("", description="地域")
    tags: List[str] = Field(default_factory=list, description="标签列表")

    # 状态
    status: str = Field("draft", description="状态: draft/published")


# ==================== 响应模型 ====================

class RawDataRefResponse(BaseModel):
    """原始数据引用响应

    v1.1.0: 字段加默认值，兼容数据库中的 None 值；新增 task_name 字段
    """
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
    task_name: str = ""  # 新增：任务名称（仅 scheduled/manual 类型有值）


class EntryResponse(BaseModel):
    """条目响应"""
    id: str
    title: str
    translated_title: str = ""  # 翻译后的标题
    description: str
    summary: str
    combined_content: str
    tags: List[str]
    primary_category: str
    secondary_category: str
    tertiary_category: str
    status: str
    raw_data_refs: List[RawDataRefResponse]
    raw_data_count: int
    user_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EntryListResponse(BaseModel):
    """条目列表响应"""
    items: List[EntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateEntryResponse(BaseModel):
    """创建条目响应"""
    success: bool
    message: str
    entry: Optional[EntryResponse] = None


# ==================== 辅助函数 ====================

def entry_to_response(entry: InfoEntry) -> EntryResponse:
    """将 InfoEntry 转换为响应模型"""
    # 获取翻译标题（从第一个原始数据引用中获取）
    translated_title = ""
    if entry.raw_data_refs and len(entry.raw_data_refs) > 0:
        translated_title = entry.raw_data_refs[0].translated_title or ""
    
    return EntryResponse(
        id=entry.id,
        title=entry.title,
        translated_title=translated_title,
        description=entry.description,
        summary=entry.summary,
        combined_content=entry.combined_content,
        tags=entry.tags,
        primary_category=entry.primary_category,
        secondary_category=entry.secondary_category,
        tertiary_category=entry.tertiary_category,
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
                task_name=ref.task_name or "",  # 新增
            )
            for ref in entry.raw_data_refs
        ],
        raw_data_count=entry.raw_data_count,
        user_id=entry.user_id,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
    )


# ==================== API 端点 ====================

@router.post(
    "/",
    response_model=CreateEntryResponse,
    summary="创建信息条目",
    description="从多个数据源选择数据，合并创建一个信息条目",
)
async def create_entry(
    request: CreateEntryRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """创建信息条目

    v1.1.0: 简化请求，只传 data_type + data_id，后台自动查询完整数据
    - 移除快照兜底逻辑
    - 数据获取失败直接返回 400 错误
    """
    try:
        repo = InfoEntryRepository(db)

        # 从数据源获取原始数据
        data_refs_input = [
            {
                "data_id": ref.data_id,
                "data_type": ref.data_type,
            }
            for ref in request.raw_data_refs
        ]

        raw_data_refs = await repo.fetch_raw_data_from_sources(data_refs_input)

        # v1.1.0: 校验必须全部获取成功，不再使用快照兜底
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

        # 生成合并内容（如果前端没有传）
        combined_content = request.combined_content
        if not combined_content:
            combined_content = "\n\n---\n\n".join([
                f"【{i+1}】{ref.title}\n来源：{ref.origin_site}\n{ref.markdown_content or ref.snippet}"
                for i, ref in enumerate(raw_data_refs)
            ])

        # 创建条目实体
        entry = InfoEntry(
            title=request.title,
            description=request.description or f"包含 {len(raw_data_refs)} 条原始数据的条目",
            summary=request.summary or "",
            combined_content=combined_content,
            tags=request.tags or [],
            primary_category=request.primary_category or "",
            secondary_category=request.secondary_category or "",
            tertiary_category=request.tertiary_category or "",
            status=EntryStatus.DRAFT,
            raw_data_refs=raw_data_refs,
            user_id=current_user.id,
        )

        # 保存到数据库
        created_entry = await repo.create(entry)

        logger.info(
            f"创建条目成功: id={created_entry.id}, title={request.title}, "
            f"raw_data_count={len(raw_data_refs)}, user={current_user.id}"
        )

        return CreateEntryResponse(
            success=True,
            message=f"成功创建条目，包含 {len(raw_data_refs)} 条原始数据",
            entry=entry_to_response(created_entry),
        )

    except Exception as e:
        logger.error(f"创建条目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建条目失败: {str(e)}")


@router.get(
    "/",
    response_model=EntryListResponse,
    summary="获取条目列表",
    description="获取当前用户的条目列表，支持分页和筛选",
)
async def list_entries(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: draft/published/archived"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取条目列表"""
    repo = InfoEntryRepository(db)
    entries, total = await repo.list_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword,
    )

    total_pages = (total + page_size - 1) // page_size

    return EntryListResponse(
        items=[entry_to_response(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{entry_id}",
    response_model=EntryResponse,
    summary="获取条目详情",
    description="根据ID获取条目详情",
)
async def get_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """获取条目详情"""
    repo = InfoEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此条目")

    return entry_to_response(entry)


@router.put(
    "/{entry_id}",
    response_model=EntryResponse,
    summary="更新条目",
    description="更新条目信息",
)
async def update_entry(
    entry_id: str,
    request: UpdateEntryRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """更新条目"""
    repo = InfoEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
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
    if request.status is not None:
        entry.status = EntryStatus(request.status)

    updated_entry = await repo.update(entry)
    return entry_to_response(updated_entry)


@router.delete(
    "/{entry_id}",
    summary="删除条目",
    description="删除指定条目",
)
async def delete_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """删除条目"""
    repo = InfoEntryRepository(db)
    entry = await repo.get_by_id(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")

    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此条目")

    success = await repo.delete(entry_id)
    if success:
        return {"success": True, "message": "删除成功"}
    else:
        raise HTTPException(status_code=500, detail="删除失败")


@router.post(
    "/from-single",
    response_model=CreateEntryResponse,
    summary="从单条信息创建条目",
    description="将 compile 页面编辑的单条信息保存到 info_entries，raw_data_count = 1",
)
async def create_from_single(
    request: CreateFromSingleRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_mongodb_database),
):
    """从单条信息创建条目

    - 创建包含 1 条原始数据引用的条目
    - combined_content 存储译文内容
    - raw_data_count 固定为 1
    """
    try:
        repo = InfoEntryRepository(db)

        # 创建原始数据引用（1条）
        raw_data_ref = RawDataRef(
            data_id=request.source_data_id,
            data_type=request.source_data_type,
            source_collection=request.source_collection,
            title=request.title,
            url=request.url,
            origin_site=request.origin_site,
            published_date=request.published_date,
            markdown_content=request.markdown_content,
            snippet=request.snippet,
            translated_title=request.translated_title,
            translated_content=request.translated_content,
        )

        # 创建条目实体
        entry = InfoEntry(
            title=request.title,
            description="",  # 单条信息不需要描述
            summary="",
            combined_content=request.translated_content,  # 译文作为合并内容
            tags=request.tags,
            primary_category=request.primary_category,
            secondary_category=request.secondary_category,
            tertiary_category=request.tertiary_category,
            status=EntryStatus(request.status),
            raw_data_refs=[raw_data_ref],
            user_id=current_user.id,
        )

        # 保存到数据库
        created_entry = await repo.create(entry)

        logger.info(
            f"从单条信息创建条目成功: id={created_entry.id}, title={request.title}, "
            f"source_data_id={request.source_data_id}, user={current_user.id}"
        )

        return CreateEntryResponse(
            success=True,
            message="单条信息保存成功",
            entry=entry_to_response(created_entry),
        )

    except Exception as e:
        logger.error(f"从单条信息创建条目失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
