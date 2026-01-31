"""
搜索任务前端API端点

专为前端设计的清洁API接口，遵循RESTful设计原则。
隐藏系统内部接口，只暴露前端必需的功能。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.core.domain.entities.search_task import SearchTask, TaskStatus, ScheduleInterval
from src.infrastructure.database.repositories import SearchTaskRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.services.task_scheduler import get_scheduler
from src.utils.logger import get_logger
from src.api.v1.endpoints.search_tasks_validation import (
    validate_task_creation,
    get_task_mode_description
)
from src.api.dependencies.auth import require_permissions

logger = get_logger(__name__)
router = APIRouter(prefix="/search-tasks", tags=["🔍 搜索任务管理"])

# 任务仓储实例
task_repository = None


async def get_task_repository():
    """获取任务仓储实例"""
    global task_repository
    if task_repository is None:
        try:
            await get_mongodb_database()
            task_repository = SearchTaskRepository()
            logger.info("使用MongoDB仓储")
        except Exception as e:
            logger.warning(f"MongoDB不可用，使用内存仓储: {e}")
            task_repository = InMemorySearchTaskRepository()
    return task_repository


# ==========================================
# Pydantic 数据模型
# ==========================================

class SearchTaskCreate(BaseModel):
    """创建搜索任务请求

    v4.30.0: 前端字段为主，简化API接口

    字段说明：
    - name: 任务名称
    - url: 监控URL（内部映射到 crawl_url）
    - type: 监控类型 "website" | "social"（内部映射到 task_type: map_detail | search_keyword）
    - frequency: 执行频率 "1h"|"2h"|"12h"|"1d"|"custom"（内部映射到 schedule_interval）
    - custom_frequency_hours: 自定义频率小时数（当 frequency="custom" 时使用）
    - fetch_limit: 每次采集数量 "20"|"30"|"40"|"50"|"unlimited"（内部映射到 search_config.limit）
    - duration: 任务有效期天数 "7"|"14"|"30"|"60"|"90"|"unlimited"（内部映射到 crawl_config.duration_days）
    - is_active: 是否启用任务
    """
    # 基础字段
    name: str = Field(..., description="任务名称", min_length=1, max_length=100)

    # 前端简化字段（内部自动映射到后端模型）
    url: str = Field(..., description="监控URL", max_length=500)
    type: Literal["website", "social"] = Field(
        "website",
        description="监控类型：website（网站监控）、social（社交媒体）"
    )
    frequency: Literal["1h", "2h", "12h", "1d", "custom"] = Field(
        "2h",
        description="执行频率：1h、2h、12h、1d、custom"
    )
    custom_frequency_hours: Optional[str] = Field(
        None,
        description="自定义频率小时数（1-168，当frequency=custom时使用）",
        min_length=1,
        max_length=3
    )
    fetch_limit: Literal["20", "30", "40", "50", "unlimited"] = Field(
        "30",
        description="每次采集数量"
    )
    duration: Literal["7", "14", "30", "60", "90", "unlimited"] = Field(
        "30",
        description="任务有效期天数"
    )
    is_active: bool = Field(True, description="是否启用任务")
    execute_immediately: bool = Field(True, description="创建后是否立即执行一次")


class SearchTaskUpdate(BaseModel):
    """更新搜索任务请求

    v4.30.0: 前端字段为主，简化API接口
    """
    # 基础字段
    name: Optional[str] = Field(None, min_length=1, max_length=100)

    # 前端简化字段（内部自动映射到后端模型）
    url: Optional[str] = Field(None, description="监控URL", max_length=500)
    type: Optional[Literal["website", "social"]] = Field(
        None,
        description="监控类型：website（网站监控）、social（社交媒体）"
    )
    frequency: Optional[Literal["1h", "2h", "12h", "1d", "custom"]] = Field(
        None,
        description="执行频率：1h、2h、12h、1d、custom"
    )
    custom_frequency_hours: Optional[str] = Field(
        None,
        description="自定义频率小时数（1-168，当frequency=custom时使用）",
        min_length=1,
        max_length=3
    )
    fetch_limit: Optional[Literal["20", "30", "40", "50", "unlimited"]] = Field(
        None,
        description="每次采集数量"
    )
    duration: Optional[Literal["7", "14", "30", "60", "90", "unlimited"]] = Field(
        None,
        description="任务有效期天数"
    )
    is_active: Optional[bool] = Field(None, description="是否启用任务")


class SearchTaskStatusUpdate(BaseModel):
    """任务状态更新请求"""
    is_active: bool = Field(..., description="是否启用任务")


class SearchTaskResponse(BaseModel):
    """搜索任务响应

    v4.30.0: 前端字段为主，简化API响应
    """
    # 前端简化字段
    id: str = Field(..., description="任务ID")
    name: str = Field(..., description="任务名称")
    url: str = Field(..., description="监控URL")
    type: str = Field(..., description="监控类型：website、social")
    frequency: str = Field(..., description="执行频率：1h、2h、12h、1d、custom")
    fetch_limit: str = Field(..., description="每次采集数量：20、30、40、50、unlimited")
    duration: str = Field(..., description="任务有效期天数：7、14、30、60、90、unlimited")
    is_active: bool = Field(..., description="是否启用")
    status: str = Field(..., description="任务状态")

    # 任务展示字段
    task_type: str = Field(..., description="任务类型（用于展示）")
    task_mode: str = Field(..., description="任务模式描述（用于前端显示）")

    # 统计字段
    execution_count: int = Field(..., description="总执行次数")
    total_results: int = Field(..., description="总结果数")
    last_executed_at: Optional[datetime] = Field(None, description="最后执行时间")
    created_at: datetime = Field(..., description="创建时间")


class SearchTaskListResponse(BaseModel):
    """任务列表响应"""
    items: List[SearchTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")


class ScheduleIntervalOption(BaseModel):
    """调度间隔选项"""
    value: str = Field(..., description="间隔值")
    label: str = Field(..., description="显示标签")
    description: str = Field(..., description="详细说明")
    interval_minutes: int = Field(..., description="间隔分钟数")


# ==========================================
# 辅助函数
# ==========================================

def _map_task_type_to_monitor_type(task_type: str) -> Optional[str]:
    """将后端 task_type 映射到前端 monitor type"""
    type_mapping = {
        "crawl_website": "website",
        "scrape_url": "website",
        "map_scrape_website": "website",
        "map_detail": "website",       # v4.30.0: Map+Detail 详情页爬取
        "search_keyword": "social",    # 暂时映射
        "search_multilang": "social",
    }
    return type_mapping.get(task_type)


def _map_schedule_interval_to_frequency(schedule_interval: str) -> Optional[str]:
    """将后端 schedule_interval 映射到前端 frequency"""
    frequency_mapping = {
        "HOURLY_1": "1h",
        "HOURLY_6": "2h",
        "HOURLY_12": "12h",
        "DAILY": "1d",
        "DAYS_3": "3d",
        "WEEKLY": "7d",
    }
    return frequency_mapping.get(schedule_interval, "2h")


def _map_limit_to_fetch_limit(search_config: Dict[str, Any]) -> Optional[str]:
    """将后端 search_config.limit 映射到前端 fetch_limit"""
    limit = search_config.get("limit")
    if limit is None:
        return "30"  # 默认值
    if limit == 0 or limit is False:
        return "unlimited"
    return str(limit)


def _map_duration_days_to_duration(crawl_config: Dict[str, Any]) -> Optional[str]:
    """将后端 crawl_config.duration_days 映射到前端 duration"""
    duration_days = crawl_config.get("duration_days")
    if duration_days is None:
        return "30"  # 默认值
    return "unlimited" if duration_days == "unlimited" else str(duration_days)


def task_to_response(task: SearchTask) -> SearchTaskResponse:
    """将任务实体转换为响应模型

    v4.30.0: 前端字段为主，简化响应
    """
    task_type_enum = task.get_task_type()

    # 获取任务模式描述
    task_mode_map = {
        "search_keyword": "关键词搜索 + 详情页爬取",
        "crawl_website": "网站递归爬取",
        "scrape_url": "单页面爬取",
        "map_scrape_website": "Map + Scrape 组合模式",
        "search_multilang": "多语言并行搜索（Claude翻译）",
        "map_detail": "Map + Detail 智能过滤模式"
    }
    task_mode = task_mode_map.get(task_type_enum.value, task_type_enum.value)

    return SearchTaskResponse(
        # 前端简化字段
        id=task.get_id_string(),
        name=task.name,
        url=task.crawl_url or "",
        type=_map_task_type_to_monitor_type(task_type_enum.value) or "website",
        frequency=_map_schedule_interval_to_frequency(task.schedule_interval) or "2h",
        fetch_limit=_map_limit_to_fetch_limit(task.search_config) or "30",
        duration=_map_duration_days_to_duration(task.crawl_config) or "30",
        is_active=task.is_active,
        status=task.status.value,
        # 任务展示字段
        task_type=task_type_enum.value,
        task_mode=task_mode,
        # 统计字段
        execution_count=task.execution_count,
        total_results=task.total_results,
        last_executed_at=task.last_executed_at,
        created_at=task.created_at
    )


# ==========================================
# API端点
# ==========================================

@router.get(
    "/schedule-intervals", 
    response_model=List[ScheduleIntervalOption],
    summary="获取调度间隔选项",
    description="获取所有可用的任务调度间隔选项，前后端通过此接口约定调度配置。"
)
async def get_schedule_intervals():
    """获取所有可用的调度间隔选项"""
    return [interval.to_dict() for interval in ScheduleInterval]


@router.post(
    "",
    response_model=SearchTaskResponse,
    status_code=201,
    summary="创建搜索任务",
    description="创建新的定时搜索任务。任务创建后将按照指定的调度间隔自动执行搜索。"
)
async def create_search_task(task_data: SearchTaskCreate):
    """创建新的搜索任务

    v4.30.0: 前端字段为主，简化API
    """
    try:
        # ==========================================
        # v4.30.0: 前端字段映射到后端模型
        # ==========================================
        # type -> task_type 映射
        type_mapping = {
            "website": "map_detail",
            "social": "search_keyword"
        }
        task_type = type_mapping.get(task_data.type, "map_detail")

        # frequency -> schedule_interval 映射（使用 ScheduleInterval 枚举值）
        frequency_mapping = {
            "1h": "HOURLY_1",
            "2h": "HOURLY_6",
            "12h": "HOURLY_12",
            "1d": "DAILY",
        }
        if task_data.frequency == "custom" and task_data.custom_frequency_hours:
            hours = int(task_data.custom_frequency_hours)
            schedule_interval_map = {
                1: "HOURLY_1", 2: "HOURLY_6", 3: "HOURLY_6", 4: "HOURLY_6", 5: "HOURLY_6",
                6: "HOURLY_6", 12: "HOURLY_12", 24: "DAILY", 168: "WEEKLY"
            }
            schedule_interval = schedule_interval_map.get(hours, "HOURLY_6")
        else:
            schedule_interval = frequency_mapping.get(task_data.frequency, "HOURLY_6")

        # fetch_limit -> search_config.limit 映射
        search_config = {"limit": None if task_data.fetch_limit == "unlimited" else int(task_data.fetch_limit)}

        # duration -> crawl_config.duration_days 映射
        crawl_config = {"duration_days": None if task_data.duration == "unlimited" else int(task_data.duration)}

        # 创建任务
        task = SearchTask.create_with_secure_id(
            name=task_data.name,
            crawl_url=task_data.url,
            task_type=task_type,
            search_config=search_config,
            crawl_config=crawl_config,
            schedule_interval=schedule_interval,
            is_active=task_data.is_active,
            created_by="current_user",
            status=TaskStatus.ACTIVE if task_data.is_active else TaskStatus.DISABLED
        )

        # 自动提取 target_website
        task.sync_target_website()

        # 保存到仓储
        repo = await get_task_repository()
        await repo.create(task)

        logger.info(f"创建搜索任务: {task.name} (ID: {task.get_id_string()}, type: {task_type})")

        # 添加到调度器
        if task.is_active:
            try:
                scheduler = await get_scheduler()
                if scheduler.is_running():
                    await scheduler.add_task(task)
                    logger.info(f"✅ 任务已添加到调度器: {task.name}")
            except Exception as e:
                logger.warning(f"⚠️ 添加任务到调度器失败（不影响任务创建）: {e}")

        # 首次立即执行
        if task.is_active and task_data.execute_immediately:
            try:
                scheduler = await get_scheduler()
                if scheduler.is_running():
                    import asyncio
                    asyncio.create_task(scheduler.execute_task_now(str(task.id)))
                    logger.info(f"✅ 已触发首次立即执行: {task.name} (ID: {task.get_id_string()})")
            except Exception as e:
                logger.warning(f"⚠️ 触发首次执行失败（不影响任务创建）: {e}")

        return task_to_response(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(500, f"创建任务失败: {str(e)}")


@router.get(
    "",
    response_model=SearchTaskListResponse,
    summary="获取搜索任务列表",
    description="获取搜索任务列表，支持分页、状态过滤和模糊查询功能。"
)
async def list_search_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    is_active: Optional[bool] = Query(None, description="启用状态过滤"),
    query: Optional[str] = Query(None, description="关键词模糊查询")
):
    """获取搜索任务列表"""
    repo = await get_task_repository()
    tasks, total = await repo.list_tasks(
        page=page,
        page_size=page_size,
        status=status,
        is_active=is_active,
        query=query
    )
    
    # 计算总页数
    total_pages = (total + page_size - 1) // page_size
    
    return SearchTaskListResponse(
        items=[task_to_response(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/{task_id}/status",
    response_model=SearchTaskResponse,
    summary="获取任务状态",
    description="查询任务的运行状态、执行统计和资源使用情况。返回完整的任务信息，专为前端状态监控设计。"
)
async def get_task_status(task_id: str):
    """获取任务状态信息（返回完整任务响应）"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    return task_to_response(task)


@router.get(
    "/{task_id}",
    response_model=SearchTaskResponse,
    summary="获取搜索任务详情",
    description="根据任务ID获取单个搜索任务的详细信息。"
)
async def get_search_task(task_id: str):
    """获取单个搜索任务详情"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    return task_to_response(task)


@router.put(
    "/{task_id}",
    response_model=SearchTaskResponse,
    summary="更新搜索任务",
    description="更新搜索任务的基本信息，如名称、描述、查询关键词、配置和调度间隔等。"
)
async def update_search_task(task_id: str, task_data: SearchTaskUpdate):
    """更新搜索任务

    v4.30.0: 前端字段为主，简化API
    """
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    # ==========================================
    # v4.30.0: 前端字段映射到后端模型
    # ==========================================
    if task_data.name is not None:
        task.name = task_data.name

    if task_data.url is not None:
        task.crawl_url = task_data.url

    # type -> task_type 映射
    if task_data.type is not None:
        type_mapping = {
            "website": "map_detail",
            "social": "search_keyword"
        }
        task.task_type = type_mapping.get(task_data.type, task.task_type)

    # frequency -> schedule_interval 映射
    if task_data.frequency is not None:
        frequency_mapping = {
            "1h": "HOURLY_1",
            "2h": "HOURLY_6",
            "12h": "HOURLY_12",
            "1d": "DAILY",
        }
        if task_data.frequency == "custom" and task_data.custom_frequency_hours:
            hours = int(task_data.custom_frequency_hours)
            schedule_interval_map = {
                1: "HOURLY_1", 2: "HOURLY_6", 3: "HOURLY_6", 4: "HOURLY_6", 5: "HOURLY_6",
                6: "HOURLY_6", 12: "HOURLY_12", 24: "DAILY", 168: "WEEKLY"
            }
            task.schedule_interval = schedule_interval_map.get(hours, "HOURLY_6")
        else:
            task.schedule_interval = frequency_mapping.get(
                task_data.frequency,
                task.schedule_interval
            )

    # fetch_limit -> search_config.limit 映射
    if task_data.fetch_limit is not None:
        limit = None if task_data.fetch_limit == "unlimited" else int(task_data.fetch_limit)
        if task.search_config is None:
            task.search_config = {}
        task.search_config["limit"] = limit

    # duration -> crawl_config.duration_days 映射
    if task_data.duration is not None:
        duration_days = None if task_data.duration == "unlimited" else int(task_data.duration)
        if task.crawl_config is None:
            task.crawl_config = {}
        task.crawl_config["duration_days"] = duration_days

    if task_data.is_active is not None:
        task.is_active = task_data.is_active
        task.status = TaskStatus.ACTIVE if task_data.is_active else TaskStatus.DISABLED

    task.updated_at = datetime.utcnow()

    # 更新到仓储
    await repo.update(task)

    logger.info(f"更新搜索任务: {task.name} (ID: {task_id})")

    # 同步到调度器
    try:
        scheduler = await get_scheduler()
        if scheduler.is_running():
            await scheduler.update_task(task)
            logger.info(f"✅ 调度器已更新: {task.name}")
    except Exception as e:
        logger.warning(f"⚠️ 更新调度器失败（不影响任务更新）: {e}")

    return task_to_response(task)


@router.patch(
    "/{task_id}/status",
    response_model=SearchTaskResponse,
    summary="修改任务状态",
    description="启用或禁用搜索任务。禁用的任务不会自动执行搜索。"
)
async def update_task_status(task_id: str, status_data: SearchTaskStatusUpdate):
    """修改任务启用/禁用状态"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    task.is_active = status_data.is_active
    task.status = TaskStatus.ACTIVE if status_data.is_active else TaskStatus.DISABLED
    task.updated_at = datetime.utcnow()

    # 更新到仓储
    await repo.update(task)

    # 同步到调度器
    try:
        scheduler = await get_scheduler()
        if scheduler.is_running():
            await scheduler.update_task(task)
            logger.info(f"已同步任务到调度器: {task.name}")
    except Exception as e:
        logger.warning(f"同步任务到调度器失败: {e}")
        # 不影响主流程，继续返回

    logger.info(f"修改任务状态: {task.name} -> {'启用' if task.is_active else '禁用'}")

    return task_to_response(task)


@router.delete(
    "/{task_id}",
    status_code=200,
    summary="删除搜索任务",
    description="永久删除搜索任务及其相关的搜索结果。此操作不可撤销。",
    dependencies=[Depends(require_permissions("info:delete"))]
)
async def delete_search_task(task_id: str):
    """删除搜索任务"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")
    
    success = await repo.delete(task_id)
    if not success:
        raise HTTPException(500, "删除任务失败")
    
    logger.info(f"删除搜索任务: {task.name} (ID: {task_id})")
    
    return {
        "success": True,
        "message": "任务删除成功", 
        "task_id": task_id,
        "task_name": task.name
    }