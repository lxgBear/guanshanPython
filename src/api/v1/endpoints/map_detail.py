"""
Map + Detail 详情页爬取 API 端点

提供基于 Map API + LLM 判断的详情页爬取功能

功能：
- POST /map-detail - 创建 Map + Detail 任务
- GET /map-detail/{task_id} - 查询任务状态
- GET /map-detail/{task_id}/results - 查询任务结果
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field, HttpUrl

from src.services.map_detail import MapDetailService, MapDetailConfig, MapDetailStats
from src.core.domain.entities.search_task import SearchTask, TaskType
from src.infrastructure.database.repositories import SearchResultRepository
from src.utils.logger import get_logger
from src.api.dependencies.auth import get_current_active_user

logger = get_logger(__name__)

router = APIRouter(
    prefix="/map-detail",
    tags=["🗺️ Map + Detail 详情页爬取"]
)


# ==================== Request Models ====================

class CreateMapDetailRequest(BaseModel):
    """创建 Map + Detail 任务请求"""
    source_url: HttpUrl = Field(..., description="目标网站URL")
    name: Optional[str] = Field(None, description="任务名称（默认使用域名）")
    enable_ai_processing: bool = Field(True, description="是否启用 AI 处理（LLM 判断）")
    map_limit: int = Field(500, ge=1, le=1000, description="Map API 最大链接数")
    scrape_concurrency: int = Field(10, ge=1, le=50, description="Scrape 并发数")
    max_retries: int = Field(5, ge=0, le=10, description="失败重试次数")
    llm_batch_size: int = Field(50, ge=10, le=100, description="LLM 每批处理 URL 数")
    enable_dedup: bool = Field(True, description="是否启用 URL 去重")

    class Config:
        json_schema_extra = {
            "example": {
                "source_url": "https://example.com/news",
                "name": "Example 新闻爬取",
                "enable_ai_processing": True,
                "map_limit": 500,
                "scrape_concurrency": 10,
                "max_retries": 5,
                "llm_batch_size": 50,
                "enable_dedup": True
            }
        }


# ==================== Response Models ====================

class MapDetailStatsResponse(BaseModel):
    """统计信息响应"""
    total_urls_found: int = Field(..., description="Map 发现的总链接数")
    urls_after_dedup: int = Field(..., description="去重后链接数")
    urls_after_filter: int = Field(..., description="规则过滤后链接数")
    urls_after_llm: int = Field(..., description="LLM 判断后的详情页数")
    urls_scraped: int = Field(..., description="成功爬取数")
    urls_failed: int = Field(..., description="爬取失败数")
    execution_time_ms: int = Field(..., description="执行时间（毫秒）")
    navigation_filtered: int = Field(..., description="规则过滤的导航页数")
    external_filtered: int = Field(..., description="过滤的外部链接数")
    llm_navigation_pages: int = Field(..., description="LLM 判断为导航页的数量")


class MapDetailTaskResponse(BaseModel):
    """Map + Detail 任务响应"""
    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态: pending/running/completed/failed")
    source_url: str = Field(..., description="源 URL")
    stats: Optional[MapDetailStatsResponse] = Field(None, description="统计信息")
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class MapDetailResultItem(BaseModel):
    """Map + Detail 结果项"""
    id: str = Field(..., description="结果 ID")
    url: str = Field(..., description="页面 URL")
    title: str = Field(..., description="页面标题")
    snippet: Optional[str] = Field(None, description="内容摘要")
    published_date: Optional[str] = Field(None, description="发布日期")
    author: Optional[str] = Field(None, description="作者")
    language: Optional[str] = Field(None, description="语言")


class MapDetailResultsResponse(BaseModel):
    """Map + Detail 结果响应"""
    task_id: str = Field(..., description="任务 ID")
    total: int = Field(..., description="总结果数")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    results: List[MapDetailResultItem] = Field(..., description="结果列表")


# ==================== 任务状态管理 ====================

# 全局任务状态存储（生产环境应使用 Redis）
_task_status: Dict[str, Dict[str, Any]] = {}


def _get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    return _task_status.get(task_id)


def _set_task_status(task_id: str, status: Dict[str, Any]) -> None:
    """设置任务状态"""
    _task_status[task_id] = status


def _update_task_status(task_id: str, **kwargs) -> None:
    """更新任务状态"""
    if task_id in _task_status:
        _task_status[task_id].update(kwargs)


# ==================== API Endpoints ====================

@router.post("", response_model=MapDetailTaskResponse, status_code=201)
async def create_map_detail_task(
    request: CreateMapDetailRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user)
):
    """
    创建 Map + Detail 详情页爬取任务

    核心流程：
    1. Map API 获取所有链接
    2. URL 去重（检查已爬取）
    3. 规则过滤（黑名单模式）
    4. LLM 判断剩余 URL 是否为详情页
    5. 批量 Scrape 爬取详情页
    6. 存储到 search_results 表
    """
    from datetime import datetime
    from src.infrastructure.id_generator import generate_string_id

    # 生成任务 ID
    task_id = generate_string_id()
    source_url = str(request.source_url)

    # 创建任务配置
    config = MapDetailConfig(
        enable_ai_processing=request.enable_ai_processing,
        map_limit=request.map_limit,
        scrape_concurrency=request.scrape_concurrency,
        max_retries=request.max_retries,
        llm_batch_size=request.llm_batch_size,
        enable_dedup=request.enable_dedup,
    )

    # 创建 SearchTask
    task = SearchTask(
        id=task_id,
        name=request.name or f"Map Detail: {source_url}",
        task_type=TaskType.MAP_DETAIL.value,
        crawl_url=source_url,
        is_active=False,  # 非定时任务
        created_by=str(current_user.id) if hasattr(current_user, 'id') else "api_user",
        created_at=datetime.utcnow(),
    )

    # 初始化任务状态
    _set_task_status(task_id, {
        "task_id": task_id,
        "status": "pending",
        "source_url": source_url,
        "config": config.to_dict(),
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "stats": None,
    })

    # 添加后台任务
    background_tasks.add_task(_execute_map_detail_task, task, config)

    return MapDetailTaskResponse(
        task_id=task_id,
        status="pending",
        source_url=source_url,
        stats=None,
        created_at=_task_status[task_id]["created_at"],
        started_at=None,
        completed_at=None,
        error_message=None
    )


@router.get("/{task_id}", response_model=MapDetailTaskResponse)
async def get_map_detail_task(
    task_id: str,
    current_user = Depends(get_current_active_user)
):
    """查询 Map + Detail 任务状态"""
    status = _get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    stats = status.get("stats")
    stats_response = MapDetailStatsResponse(**stats) if stats else None

    return MapDetailTaskResponse(
        task_id=status["task_id"],
        status=status["status"],
        source_url=status["source_url"],
        stats=stats_response,
        created_at=status["created_at"],
        started_at=status.get("started_at"),
        completed_at=status.get("completed_at"),
        error_message=status.get("error_message")
    )


@router.get("/{task_id}/results", response_model=MapDetailResultsResponse)
async def get_map_detail_results(
    task_id: str,
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user = Depends(get_current_active_user)
):
    """查询 Map + Detail 任务结果"""
    status = _get_task_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    if status["status"] not in ("completed", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"任务状态不支持查询结果: {status['status']}"
        )

    # 查询结果
    result_repo = SearchResultRepository()
    results, total = await result_repo.get_results_by_task(
        task_id=task_id,
        page=page,
        page_size=limit
    )

    # 转换为响应格式
    result_items = [
        MapDetailResultItem(
            id=str(r.id),
            url=r.url,
            title=r.title,
            snippet=r.snippet,
            published_date=r.published_date.isoformat() if r.published_date else None,
            author=r.author,
            language=r.language
        )
        for r in results
    ]

    return MapDetailResultsResponse(
        task_id=task_id,
        total=total,
        page=page,
        limit=limit,
        results=result_items
    )


# ==================== 后台任务执行 ====================

async def _execute_map_detail_task(task: SearchTask, config: MapDetailConfig):
    """执行 Map + Detail 后台任务"""
    from datetime import datetime

    task_id = str(task.id)

    try:
        # 更新状态为运行中
        _update_task_status(
            task_id,
            status="running",
            started_at=datetime.utcnow().isoformat()
        )

        # 执行服务
        service = MapDetailService(config)

        # 进度回调
        def progress_callback(message: str, current: int, total: int):
            logger.info(f"[MapDetail] [{task_id}] {message} ({current}/{total})")

        result = await service.execute(task, progress_callback)

        if result.success:
            # 更新状态为完成
            _update_task_status(
                task_id,
                status="completed",
                completed_at=datetime.utcnow().isoformat(),
                stats=result.stats.to_dict()
            )
            logger.info(f"[MapDetail] 任务完成: {task_id}")
        else:
            # 更新状态为失败
            _update_task_status(
                task_id,
                status="failed",
                completed_at=datetime.utcnow().isoformat(),
                error_message=result.error_message
            )
            logger.error(f"[MapDetail] 任务失败: {task_id}, {result.error_message}")

    except Exception as e:
        # 更新状态为失败
        _update_task_status(
            task_id,
            status="failed",
            completed_at=datetime.utcnow().isoformat(),
            error_message=str(e)
        )
        logger.error(f"[MapDetail] 任务异常: {task_id}, {e}", exc_info=True)
