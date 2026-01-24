"""
搜索结果前端API端点

作为搜索任务的子资源，提供任务相关的结果查询功能。
遵循RESTful设计，路径格式：/search-tasks/{task_id}/results
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/search-tasks", tags=["📊 搜索结果查询"])

# 仓储实例
task_repository = None
result_repository = None
processed_result_repository = None  # v2.0.0 新增


async def get_task_repository():
    """获取任务仓储实例"""
    global task_repository
    if task_repository is None:
        try:
            await get_mongodb_database()
            task_repository = SearchTaskRepository()
            logger.info("使用MongoDB任务仓储")
        except Exception as e:
            logger.warning(f"MongoDB不可用，使用内存仓储: {e}")
            task_repository = InMemorySearchTaskRepository()
    return task_repository


async def get_result_repository():
    """获取原始结果仓储实例（v2.0.0: 用于查看原始数据）"""
    global result_repository
    if result_repository is None:
        try:
            await get_mongodb_database()
            result_repository = SearchResultRepository()
            logger.info("使用MongoDB原始结果仓储")
        except Exception as e:
            logger.warning(f"MongoDB不可用，原始结果查询将失败: {e}")
            raise HTTPException(503, "原始结果仓储不可用")
    return result_repository


async def get_processed_result_repository():
    """获取AI处理结果仓储实例（v2.0.0 新增，主查询源）"""
    global processed_result_repository
    if processed_result_repository is None:
        try:
            await get_mongodb_database()
            processed_result_repository = ProcessedResultRepository()
            logger.info("使用MongoDB AI处理结果仓储")
        except Exception as e:
            logger.warning(f"MongoDB不可用，AI处理结果查询将失败: {e}")
            raise HTTPException(503, "AI处理结果仓储不可用")
    return processed_result_repository


# ==========================================
# Pydantic 数据模型
# ==========================================

class SearchResultResponse(BaseModel):
    """搜索结果响应（v2.0.1: 原始数据 + 实际使用的AI字段）"""
    # ==================== 主键和关联 ====================
    id: str = Field(..., description="处理结果ID")
    task_id: str = Field(..., description="任务ID")

    # ==================== 原始字段 ====================
    title: str = Field(..., description="原始标题")
    url: str = Field(..., description="原始URL")
    source_url: Optional[str] = Field(None, description="来源URL")
    content: str = Field(..., description="原始内容")
    snippet: Optional[str] = Field(None, description="内容摘要")
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容")
    html_content: Optional[str] = Field(None, description="HTML格式内容")
    author: Optional[str] = Field(None, description="作者")
    published_date: Optional[datetime] = Field(None, description="发布日期")
    language: Optional[str] = Field(None, description="语言")
    source: str = Field("web", description="来源类型")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    search_position: int = Field(0, description="搜索位置")

    # ==================== AI增强数据（实际使用的字段）====================
    # AI翻译和生成
    content_zh: Optional[str] = Field(None, description="AI翻译的中文内容")
    title_generated: Optional[str] = Field(None, description="AI生成的标题")

    # AI分类和分析
    cls_results: Optional[Dict[str, Any]] = Field(None, description="分类结果（大类、子目录）")

    # AI处理的HTML
    html_ctx_llm: Optional[str] = Field(None, description="LLM处理后的HTML")
    html_ctx_regex: Optional[str] = Field(None, description="Regex处理后的HTML")

    # AI提取的元数据
    article_published_time: Optional[str] = Field(None, description="文章发布时间")
    article_tag: Optional[str] = Field(None, description="文章标签")

    # ==================== AI处理后的新闻结果（v2.0.2）====================
    news_results: Optional[Dict[str, Any]] = Field(None, description="AI处理后的新闻结果（包含翻译标题、分类、媒体URL等）")

    # ==================== 处理状态 ====================
    processing_status: str = Field("pending", description="处理状态（success/failed/pending）")

    # ==================== 用户操作 ====================
    status: str = Field(..., description="处理状态")
    user_rating: Optional[int] = Field(None, description="用户评分(1-5)")
    user_notes: Optional[str] = Field(None, description="用户备注")

    # ==================== 时间戳 ====================
    created_at: datetime = Field(..., description="创建时间")
    processed_at: Optional[datetime] = Field(None, description="AI处理完成时间")
    updated_at: datetime = Field(..., description="更新时间")

    # ==================== 未使用字段（已移除）====================
    # raw_result_id: 内部使用，前端不需要
    # translated_title: 未实现
    # translated_content: 未实现
    # summary: 未实现
    # key_points: 未实现
    # sentiment: 未实现
    # categories: 未实现
    # ai_model: 未实现
    # ai_processing_time_ms: 未实现
    # ai_confidence_score: 未实现


class SearchResultListResponse(BaseModel):
    """搜索结果列表响应"""
    items: List[SearchResultResponse] = Field(..., description="结果列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")


class SearchResultStats(BaseModel):
    """搜索结果统计（v2.0.0: 基于 processed_results_new）"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    total_results: int = Field(..., description="结果总数")

    # v2.0.0 处理状态统计
    pending_count: int = Field(..., description="待AI处理数量")
    processing_count: int = Field(..., description="AI处理中数量")
    completed_count: int = Field(..., description="AI处理完成数量")
    failed_count: int = Field(..., description="AI处理失败数量")
    archived_count: int = Field(..., description="用户留存数量")
    deleted_count: int = Field(..., description="用户删除数量")

    last_updated: datetime = Field(..., description="最后更新时间")


class SearchResultSummary(BaseModel):
    """搜索结果摘要（用于任务详情页面）"""
    total_results: int = Field(..., description="总结果数")
    recent_results: List[SearchResultResponse] = Field(..., description="最近结果（最多5条）")
    stats: SearchResultStats = Field(..., description="统计信息")


# ==========================================
# 辅助函数
# ==========================================

def processed_result_to_response(result: ProcessedResult) -> SearchResultResponse:
    """将AI处理结果实体转换为响应模型（v2.0.1: 仅映射实际使用的字段）

    v2.1.1: 添加 None 值处理，避免 Pydantic 验证错误
    """
    # 处理 language 字段（数据库中可能是数组，需要转换为字符串）
    language_value = result.language
    if isinstance(language_value, list):
        language_value = language_value[0] if language_value else None

    return SearchResultResponse(
        # 主键和关联
        id=str(result.id),
        task_id=str(result.task_id),
        # 原始字段
        title=result.title,
        url=result.url,
        source_url=result.source_url,
        content=result.content or "",  # v2.1.1: 如果为 None，使用空字符串
        snippet=result.snippet,
        markdown_content=result.markdown_content,
        html_content=result.html_content,
        author=result.author,
        published_date=result.published_date,
        language=language_value,
        source=result.source,
        metadata=result.metadata or {},  # v2.1.1: 如果为 None，使用空字典
        # v2.3.1: 移除评分字段
        search_position=result.search_position,
        # AI增强数据（实际使用的字段）
        content_zh=result.content_zh,
        title_generated=result.title_generated,
        cls_results=result.cls_results,
        html_ctx_llm=result.html_ctx_llm,
        html_ctx_regex=result.html_ctx_regex,
        article_published_time=result.article_published_time,
        article_tag=result.article_tag,
        # AI处理后的新闻结果（v2.0.2）
        news_results=result.news_results,
        # 处理状态
        processing_status=result.processing_status,
        # 用户操作
        status=result.status.value,
        user_rating=result.user_rating,
        user_notes=result.user_notes,
        # 时间戳
        created_at=result.created_at,
        processed_at=result.processed_at,
        updated_at=result.updated_at or result.created_at  # v2.1.1: 如果为 None，使用 created_at
    )


async def validate_task_exists(task_id: str) -> str:
    """验证任务是否存在，返回任务名称

    增强功能: 检测用户是否错用了 NL Search 的 ID
    """
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)

    if not task:
        # ✨ 新增：检查是否为 NL Search 数据（用户可能用错了端点）
        from src.infrastructure.database.connection import get_mongodb_database
        db = await get_mongodb_database()
        nl_log = await db['nl_search_logs'].find_one({'_id': task_id})

        if nl_log:
            # 用户使用了错误的端点 - 提供友好提示
            logger.info(f"检测到端点使用错误: ID {task_id} 属于自然语言搜索系统")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "端点使用错误",
                    "message": f"ID {task_id} 属于自然语言搜索系统，不是通用搜索",
                    "correct_endpoint": f"/api/v1/nl-search/{task_id}/results",
                    "current_endpoint": f"/api/v1/search-tasks/{task_id}/results",
                    "hint": "通用搜索使用 /api/v1/search-tasks/ 前缀，自然语言搜索使用 /api/v1/nl-search/ 前缀",
                    "documentation": "查看 API 文档了解两个系统的区别: /api/docs"
                }
            )

        # 确实不存在于任何系统
        raise HTTPException(404, f"任务不存在: {task_id}")

    return task.name


def calculate_result_stats(task_id: str, task_name: str, status_counts: Dict[str, int]) -> SearchResultStats:
    """计算搜索结果统计信息（v2.0.0: 基于 ProcessedStatus）"""
    total = sum(status_counts.values())

    return SearchResultStats(
        task_id=task_id,
        task_name=task_name,
        total_results=total,
        # v2.0.0: ProcessedStatus 统计
        pending_count=status_counts.get("pending", 0),
        processing_count=status_counts.get("processing", 0),
        completed_count=status_counts.get("completed", 0),
        failed_count=status_counts.get("failed", 0),
        archived_count=status_counts.get("archived", 0),
        deleted_count=status_counts.get("deleted", 0),
        last_updated=datetime.utcnow()
    )


# ==========================================
# API端点
# ==========================================

@router.get(
    "/{task_id}/results",
    response_model=SearchResultListResponse,
    summary="获取任务搜索结果列表",
    description="获取指定搜索任务的所有历史搜索结果，支持分页、过滤和排序功能。"
)
async def get_task_results(
    task_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态过滤: pending, processing, completed, failed, archived, deleted"),
    sort_by: str = Query("created_at", description="排序字段: created_at, processed_at"),
    order: str = Query("desc", description="排序方向: asc, desc")
):
    """获取指定任务的历史搜索结果 - v2.0.0: 从 processed_results_new 读取AI增强数据"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 构建状态筛选
    status_filter = None
    if status:
        try:
            status_filter = ProcessedStatus(status)
        except ValueError:
            raise HTTPException(400, f"无效的状态值: {status}")

    # 从 processed_results_new 查询（带分页和状态筛选）
    processed_results, total = await processed_repo.get_by_task(
        task_id=task_id,
        status=status_filter,
        page=page,
        page_size=page_size
    )

    if not processed_results:
        return SearchResultListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            task_id=task_id,
            task_name=task_name
        )

    # 计算总页数
    total_pages = (total + page_size - 1) // page_size

    return SearchResultListResponse(
        items=[processed_result_to_response(r) for r in processed_results],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        task_id=task_id,
        task_name=task_name
    )


@router.get(
    "/{task_id}/results/stats",
    response_model=SearchResultStats,
    summary="获取任务搜索结果统计",
    description="获取指定搜索任务的结果统计信息，包括AI处理状态分布、用户操作统计等。"
)
async def get_task_result_stats(task_id: str):
    """获取任务搜索结果统计 - v2.0.0: 从 processed_results_new 统计AI处理状态"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 获取状态统计
    status_counts = await processed_repo.get_status_statistics(task_id)

    return calculate_result_stats(task_id, task_name, status_counts)


@router.get(
    "/{task_id}/results/summary",
    response_model=SearchResultSummary,
    summary="获取任务结果摘要",
    description="获取任务搜索结果的摘要信息，包括统计数据和最近AI处理完成的结果，适用于任务详情页面展示。"
)
async def get_task_result_summary(task_id: str):
    """获取任务结果摘要 - v2.0.0: 从 processed_results_new 查询AI增强数据"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 获取最近的5条已完成处理的结果
    recent_results, recent_total = await processed_repo.get_by_task(
        task_id=task_id,
        status=ProcessedStatus.COMPLETED,
        page=1,
        page_size=5
    )

    # 获取状态统计
    status_counts = await processed_repo.get_status_statistics(task_id)

    # 计算统计信息
    stats = calculate_result_stats(task_id, task_name, status_counts)

    return SearchResultSummary(
        total_results=stats.total_results,
        recent_results=[processed_result_to_response(r) for r in recent_results],
        stats=stats
    )


@router.get(
    "/{task_id}/results/{result_id}",
    response_model=SearchResultResponse,
    summary="获取单个搜索结果详情",
    description="获取指定搜索结果的详细信息，包括AI翻译内容、摘要、关键点、情感分析等完整元数据。"
)
async def get_search_result_detail(task_id: str, result_id: str):
    """获取单个搜索结果详情 - v2.0.0: 从 processed_results_new 查询AI增强数据"""

    # 验证任务存在
    await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 根据ID查询处理结果
    result = await processed_repo.get_by_id(result_id)

    if not result:
        raise HTTPException(404, f"搜索结果不存在: {result_id}")

    # 验证结果属于指定任务
    if str(result.task_id) != task_id:
        raise HTTPException(404, f"搜索结果不属于任务: {task_id}")

    return processed_result_to_response(result)


# ==========================================
# v2.0.1 用户操作 API
# ==========================================

class UserActionRequest(BaseModel):
    """用户操作请求"""
    pass


class ArchiveRequest(UserActionRequest):
    """留存请求"""
    notes: Optional[str] = Field(None, description="留存备注", max_length=500)


class RatingRequest(UserActionRequest):
    """评分请求"""
    rating: int = Field(..., description="用户评分(1-5)", ge=1, le=5)
    notes: Optional[str] = Field(None, description="评分备注", max_length=500)


class UserActionResponse(BaseModel):
    """用户操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作结果消息")
    result: SearchResultResponse = Field(..., description="更新后的结果")


@router.post(
    "/{task_id}/results/{result_id}/archive",
    response_model=UserActionResponse,
    summary="留存搜索结果",
    description="将搜索结果标记为留存状态，用于保存重要的搜索结果。"
)
async def archive_search_result(
    task_id: str,
    result_id: str,
    request: ArchiveRequest
):
    """留存搜索结果 - v2.0.1 用户操作 API"""

    # 验证任务存在
    await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 验证结果存在
    result = await processed_repo.get_by_id(result_id)
    if not result:
        raise HTTPException(404, f"搜索结果不存在: {result_id}")

    # 验证结果属于指定任务
    if str(result.task_id) != task_id:
        raise HTTPException(404, f"搜索结果不属于任务: {task_id}")

    # 更新为留存状态
    success = await processed_repo.update_user_action(
        result_id=result_id,
        status=ProcessedStatus.ARCHIVED,
        user_notes=request.notes
    )

    if not success:
        raise HTTPException(500, "留存操作失败")

    # 获取更新后的结果
    updated_result = await processed_repo.get_by_id(result_id)

    return UserActionResponse(
        success=True,
        message="搜索结果已成功留存",
        result=processed_result_to_response(updated_result)
    )


@router.post(
    "/{task_id}/results/{result_id}/delete",
    response_model=UserActionResponse,
    summary="删除搜索结果",
    description="将搜索结果标记为删除状态（软删除），不会真正删除数据。"
)
async def delete_search_result(
    task_id: str,
    result_id: str
):
    """删除搜索结果（软删除）- v2.0.1 用户操作 API"""

    # 验证任务存在
    await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 验证结果存在
    result = await processed_repo.get_by_id(result_id)
    if not result:
        raise HTTPException(404, f"搜索结果不存在: {result_id}")

    # 验证结果属于指定任务
    if str(result.task_id) != task_id:
        raise HTTPException(404, f"搜索结果不属于任务: {task_id}")

    # 更新为删除状态
    success = await processed_repo.update_user_action(
        result_id=result_id,
        status=ProcessedStatus.DELETED
    )

    if not success:
        raise HTTPException(500, "删除操作失败")

    # 获取更新后的结果
    updated_result = await processed_repo.get_by_id(result_id)

    return UserActionResponse(
        success=True,
        message="搜索结果已成功删除",
        result=processed_result_to_response(updated_result)
    )


@router.post(
    "/{task_id}/results/{result_id}/rating",
    response_model=UserActionResponse,
    summary="评分搜索结果",
    description="为搜索结果添加用户评分（1-5星）和可选的评分备注。"
)
async def rate_search_result(
    task_id: str,
    result_id: str,
    request: RatingRequest
):
    """评分搜索结果 - v2.0.1 用户操作 API"""

    # 验证任务存在
    await validate_task_exists(task_id)

    # 获取AI处理结果仓储
    processed_repo = await get_processed_result_repository()

    # 验证结果存在
    result = await processed_repo.get_by_id(result_id)
    if not result:
        raise HTTPException(404, f"搜索结果不存在: {result_id}")

    # 验证结果属于指定任务
    if str(result.task_id) != task_id:
        raise HTTPException(404, f"搜索结果不属于任务: {task_id}")

    # 更新评分和备注
    success = await processed_repo.update_user_action(
        result_id=result_id,
        user_rating=request.rating,
        user_notes=request.notes
    )

    if not success:
        raise HTTPException(500, "评分操作失败")

    # 获取更新后的结果
    updated_result = await processed_repo.get_by_id(result_id)

    return UserActionResponse(
        success=True,
        message=f"搜索结果已评分: {request.rating}星",
        result=processed_result_to_response(updated_result)
    )