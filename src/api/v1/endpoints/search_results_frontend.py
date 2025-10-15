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
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/search-tasks", tags=["📊 搜索结果查询"])

# 仓储实例
task_repository = None
result_repository = None


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
    """获取结果仓储实例"""
    global result_repository
    if result_repository is None:
        try:
            await get_mongodb_database()
            result_repository = SearchResultRepository()
            logger.info("使用MongoDB结果仓储")
        except Exception as e:
            logger.warning(f"MongoDB不可用，结果查询将失败: {e}")
            raise HTTPException(503, "结果仓储不可用")
    return result_repository


# ==========================================
# Pydantic 数据模型
# ==========================================

class SearchResultResponse(BaseModel):
    """搜索结果响应 - 精简版(仅保留前端必需字段)"""
    id: str = Field(..., description="结果ID")
    task_id: str = Field(..., description="任务ID")
    title: str = Field(..., description="标题")
    url: str = Field(..., description="链接地址")
    content: str = Field(..., description="内容")
    snippet: Optional[str] = Field(None, description="内容摘要")
    source: str = Field(..., description="来源")
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容(最大5000字符)")
    html_content: Optional[str] = Field(None, description="HTML格式内容(用于富文本显示和分析)")
    article_tag: Optional[str] = Field(None, description="文章标签")
    article_published_time: Optional[str] = Field(None, description="文章发布时间")
    # 已移除字段:
    # - published_date, author, language (业务字段)
    # - raw_data (冗余大字段)
    # - relevance_score, quality_score (评分字段)
    # - status, created_at, processed_at (状态字段)
    # - is_test_data (测试标记)
    # - metadata (只在内部使用)


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
    """搜索结果统计"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    total_results: int = Field(..., description="结果总数")
    processed_count: int = Field(..., description="已处理数量")
    pending_count: int = Field(..., description="待处理数量")
    failed_count: int = Field(..., description="失败数量")
    average_relevance_score: float = Field(..., ge=0, le=1, description="平均相关性评分")
    average_quality_score: float = Field(..., ge=0, le=1, description="平均质量评分")
    sources_distribution: Dict[str, int] = Field(..., description="来源分布")
    languages_distribution: Dict[str, int] = Field(..., description="语言分布")
    date_range: Dict[str, Optional[datetime]] = Field(..., description="日期范围")
    last_updated: datetime = Field(..., description="最后更新时间")


class SearchResultSummary(BaseModel):
    """搜索结果摘要（用于任务详情页面）"""
    total_results: int = Field(..., description="总结果数")
    recent_results: List[SearchResultResponse] = Field(..., description="最近结果（最多5条）")
    stats: SearchResultStats = Field(..., description="统计信息")


# ==========================================
# 辅助函数
# ==========================================

def result_to_response(result: SearchResult) -> SearchResultResponse:
    """将结果实体转换为响应模型"""
    return SearchResultResponse(
        id=str(result.id),
        task_id=str(result.task_id),
        title=result.title,
        url=result.url,
        content=result.content,
        snippet=result.snippet,
        source=result.source,
        markdown_content=result.markdown_content,
        html_content=result.html_content,
        article_tag=result.article_tag,
        article_published_time=result.article_published_time,
        # 已移除映射: published_date, author, language, raw_data,
        # relevance_score, quality_score, status, created_at, processed_at,
        # is_test_data, metadata
    )


async def validate_task_exists(task_id: str) -> str:
    """验证任务是否存在，返回任务名称"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return task.name


def calculate_result_stats(task_id: str, task_name: str, results: List[SearchResult]) -> SearchResultStats:
    """计算搜索结果统计信息"""
    if not results:
        return SearchResultStats(
            task_id=task_id,
            task_name=task_name,
            total_results=0,
            processed_count=0,
            pending_count=0,
            failed_count=0,
            average_relevance_score=0.0,
            average_quality_score=0.0,
            sources_distribution={},
            languages_distribution={},
            date_range={"min_date": None, "max_date": None},
            last_updated=datetime.utcnow()
        )

    # 状态统计
    status_counts = {status.value: 0 for status in ResultStatus}
    sources_dist = {}
    languages_dist = {}
    total_relevance = 0.0
    total_quality = 0.0
    min_date = None
    max_date = None

    for result in results:
        # 状态统计
        status_counts[result.status.value] += 1

        # 来源统计
        sources_dist[result.source] = sources_dist.get(result.source, 0) + 1

        # 语言统计
        if result.language:
            languages_dist[result.language] = languages_dist.get(result.language, 0) + 1

        # 分数统计
        total_relevance += result.relevance_score
        total_quality += result.quality_score

        # 日期范围
        if result.published_date:
            if not min_date or result.published_date < min_date:
                min_date = result.published_date
            if not max_date or result.published_date > max_date:
                max_date = result.published_date

    total_count = len(results)

    return SearchResultStats(
        task_id=task_id,
        task_name=task_name,
        total_results=total_count,
        processed_count=status_counts.get("processed", 0),
        pending_count=status_counts.get("pending", 0),
        failed_count=status_counts.get("failed", 0),
        average_relevance_score=total_relevance / total_count if total_count > 0 else 0.0,
        average_quality_score=total_quality / total_count if total_count > 0 else 0.0,
        sources_distribution=sources_dist,
        languages_distribution=languages_dist,
        date_range={
            "min_date": min_date,
            "max_date": max_date
        },
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
    source: Optional[str] = Query(None, description="来源过滤"),
    language: Optional[str] = Query(None, description="语言过滤"),
    min_relevance_score: Optional[float] = Query(None, ge=0, le=1, description="最小相关性评分"),
    min_quality_score: Optional[float] = Query(None, ge=0, le=1, description="最小质量评分"),
    sort_by: str = Query("created_at", description="排序字段: created_at, relevance_score, quality_score, published_date"),
    order: str = Query("desc", description="排序方向: asc, desc")
):
    """获取指定任务的历史搜索结果 - 从数据库读取"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取结果仓储
    result_repo = await get_result_repository()

    # 从数据库获取所有结果（用于过滤和排序）
    all_results, total_count = await result_repo.get_results_by_task(
        task_id=task_id,
        page=1,
        page_size=10000  # 获取所有结果
    )

    if not all_results:
        return SearchResultListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            task_id=task_id,
            task_name=task_name
        )

    # 过滤
    filtered_results = all_results

    if source:
        filtered_results = [r for r in filtered_results if r.source == source]

    if language:
        filtered_results = [r for r in filtered_results if r.language == language]

    if min_relevance_score is not None:
        filtered_results = [r for r in filtered_results if r.relevance_score >= min_relevance_score]

    if min_quality_score is not None:
        filtered_results = [r for r in filtered_results if r.quality_score >= min_quality_score]

    # 排序
    sort_fields = {
        "created_at": lambda r: r.created_at,
        "relevance_score": lambda r: r.relevance_score,
        "quality_score": lambda r: r.quality_score,
        "published_date": lambda r: r.published_date or datetime.min
    }

    if sort_by in sort_fields:
        filtered_results.sort(
            key=sort_fields[sort_by],
            reverse=(order == "desc")
        )

    # 分页
    total = len(filtered_results)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = min(start + page_size, total)

    page_results = filtered_results[start:end]

    return SearchResultListResponse(
        items=[result_to_response(r) for r in page_results],
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
    description="获取指定搜索任务的结果统计信息，包括数量分布、评分情况、来源分析等。"
)
async def get_task_result_stats(task_id: str):
    """获取任务搜索结果统计 - 从数据库读取"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取结果仓储
    result_repo = await get_result_repository()

    # 从数据库获取所有结果
    task_results, _ = await result_repo.get_results_by_task(
        task_id=task_id,
        page=1,
        page_size=10000
    )

    return calculate_result_stats(task_id, task_name, task_results)


@router.get(
    "/{task_id}/results/summary",
    response_model=SearchResultSummary,
    summary="获取任务结果摘要",
    description="获取任务搜索结果的摘要信息，包括统计数据和最近结果，适用于任务详情页面展示。"
)
async def get_task_result_summary(task_id: str):
    """获取任务结果摘要 - 从数据库读取"""

    # 验证任务存在
    task_name = await validate_task_exists(task_id)

    # 获取结果仓储
    result_repo = await get_result_repository()

    # 从数据库获取所有结果
    task_results, _ = await result_repo.get_results_by_task(
        task_id=task_id,
        page=1,
        page_size=10000
    )

    # 获取最近的5条结果
    recent_results = sorted(task_results, key=lambda r: r.created_at, reverse=True)[:5]

    # 计算统计信息
    stats = calculate_result_stats(task_id, task_name, task_results)

    return SearchResultSummary(
        total_results=len(task_results),
        recent_results=[result_to_response(r) for r in recent_results],
        stats=stats
    )


@router.get(
    "/{task_id}/results/{result_id}",
    response_model=SearchResultResponse,
    summary="获取单个搜索结果详情",
    description="获取指定搜索结果的详细信息，包括完整内容、元数据等。"
)
async def get_search_result_detail(task_id: str, result_id: str):
    """获取单个搜索结果详情 - 从数据库读取"""

    # 验证任务存在
    await validate_task_exists(task_id)

    # 获取结果仓储
    result_repo = await get_result_repository()

    # 从数据库查找结果
    task_results, _ = await result_repo.get_results_by_task(
        task_id=task_id,
        page=1,
        page_size=10000
    )

    for result in task_results:
        if str(result.id) == result_id:
            return result_to_response(result)

    raise HTTPException(404, f"搜索结果不存在: {result_id}")