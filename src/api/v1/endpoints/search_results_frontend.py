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
    """搜索结果响应（v2.0.0: 从 processed_results 读取AI增强数据）"""
    id: str = Field(..., description="处理结果ID")
    raw_result_id: str = Field(..., description="原始结果ID")
    task_id: str = Field(..., description="任务ID")

    # AI增强数据（优先展示）
    title: str = Field(..., description="标题（AI翻译后）")
    content: str = Field(..., description="内容（AI翻译后或摘要）")
    summary: Optional[str] = Field(None, description="AI生成的摘要")
    key_points: List[str] = Field(default_factory=list, description="AI提取的关键点")
    sentiment: Optional[str] = Field(None, description="情感分析")
    categories: List[str] = Field(default_factory=list, description="AI分类标签")

    # 用户操作
    status: str = Field(..., description="处理状态")
    user_rating: Optional[int] = Field(None, description="用户评分(1-5)")
    user_notes: Optional[str] = Field(None, description="用户备注")

    # AI元数据
    ai_model: Optional[str] = Field(None, description="AI模型")
    ai_confidence_score: Optional[float] = Field(None, description="AI置信度")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    processed_at: Optional[datetime] = Field(None, description="AI处理完成时间")


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
    """搜索结果统计（v2.0.0: 基于 processed_results）"""
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
    """将AI处理结果实体转换为响应模型（v2.0.0 新版）"""
    # 获取展示用的标题和内容（优先使用AI翻译版本，回退到空字符串）
    title = result.translated_title or ""
    content = result.summary or result.translated_content or ""

    return SearchResultResponse(
        id=str(result.id),
        raw_result_id=str(result.raw_result_id),
        task_id=str(result.task_id),
        # AI增强数据
        title=title,
        content=content,
        summary=result.summary,
        key_points=result.key_points,
        sentiment=result.sentiment,
        categories=result.categories,
        # 用户操作
        status=result.status.value,
        user_rating=result.user_rating,
        user_notes=result.user_notes,
        # AI元数据
        ai_model=result.ai_model,
        ai_confidence_score=result.ai_confidence_score,
        # 时间戳
        created_at=result.created_at,
        processed_at=result.processed_at
    )


async def validate_task_exists(task_id: str) -> str:
    """验证任务是否存在，返回任务名称"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
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
    """获取指定任务的历史搜索结果 - v2.0.0: 从 processed_results 读取AI增强数据"""

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

    # 从 processed_results 查询（带分页和状态筛选）
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
    """获取任务搜索结果统计 - v2.0.0: 从 processed_results 统计AI处理状态"""

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
    """获取任务结果摘要 - v2.0.0: 从 processed_results 查询AI增强数据"""

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
    """获取单个搜索结果详情 - v2.0.0: 从 processed_results 查询AI增强数据"""

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