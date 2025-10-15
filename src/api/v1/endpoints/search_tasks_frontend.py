"""
搜索任务前端API端点

专为前端设计的清洁API接口，遵循RESTful设计原则。
隐藏系统内部接口，只暴露前端必需的功能。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.core.domain.entities.search_task import SearchTask, TaskStatus, ScheduleInterval
from src.infrastructure.database.repositories import SearchTaskRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.services.task_scheduler import get_scheduler
from src.utils.logger import get_logger

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
    """创建搜索任务请求"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    query: str = Field(..., description="搜索关键词", min_length=1, max_length=200)
    target_website: Optional[str] = Field(None, description="主要目标网站（例如：www.gnlm.com.mm）", max_length=200)
    crawl_url: Optional[str] = Field(None, description="定时爬取的URL（优先于query关键词搜索）", max_length=500)
    search_config: Dict[str, Any] = Field(default_factory=dict, description="搜索配置")
    schedule_interval: str = Field("DAILY", description="调度间隔")
    is_active: bool = Field(True, description="是否启用")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "AI新闻监控",
                "description": "监控人工智能领域最新进展",
                "query": "人工智能 深度学习 最新进展",
                "target_website": "www.36kr.com",
                "search_config": {
                    "limit": 20,
                    "sources": ["web", "news"],
                    "language": "zh",
                    "include_domains": [
                        "www.36kr.com",
                        "tech.sina.com.cn",
                        "www.ithome.com"
                    ],
                    "time_range": "day",
                    "enable_ai_summary": True
                },
                "schedule_interval": "DAILY",
                "is_active": True
            }
        }


class SearchTaskUpdate(BaseModel):
    """更新搜索任务请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    query: Optional[str] = Field(None, min_length=1, max_length=200)
    target_website: Optional[str] = Field(None, max_length=200)
    crawl_url: Optional[str] = Field(None, max_length=500)
    search_config: Optional[Dict[str, Any]] = None
    schedule_interval: Optional[str] = None
    is_active: Optional[bool] = None


class SearchTaskStatusUpdate(BaseModel):
    """任务状态更新请求"""
    is_active: bool = Field(..., description="是否启用任务")


class SearchTaskResponse(BaseModel):
    """搜索任务响应（统一的任务信息模型，包含完整的执行统计和状态信息）"""
    id: str = Field(..., description="任务ID")
    name: str = Field(..., description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    query: str = Field(..., description="搜索关键词")
    target_website: Optional[str] = Field(None, description="主要目标网站")
    crawl_url: Optional[str] = Field(None, description="定时爬取的URL")
    search_config: Dict[str, Any] = Field(..., description="搜索配置")
    schedule_interval: str = Field(..., description="调度间隔值")
    schedule_display: str = Field(..., description="调度间隔显示名称")
    schedule_description: str = Field(..., description="调度间隔说明")
    is_active: bool = Field(..., description="是否启用")
    status: str = Field(..., description="任务状态")
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    last_executed_at: Optional[datetime] = Field(None, description="最后执行时间")
    next_run_time: Optional[datetime] = Field(None, description="下次运行时间")
    execution_count: int = Field(..., description="总执行次数")
    success_count: int = Field(..., description="成功次数")
    failure_count: int = Field(..., description="失败次数")
    success_rate: float = Field(..., description="成功率（%）")
    average_results: float = Field(..., description="平均结果数")
    total_results: int = Field(..., description="总结果数")
    total_credits_used: int = Field(..., description="总消耗积分")


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

def task_to_response(task: SearchTask) -> SearchTaskResponse:
    """将任务实体转换为响应模型"""
    interval = task.get_schedule_interval()
    return SearchTaskResponse(
        id=task.get_id_string(),
        name=task.name,
        description=task.description,
        query=task.query,
        target_website=task.target_website,
        crawl_url=task.crawl_url,
        search_config=task.search_config,
        schedule_interval=task.schedule_interval,
        schedule_display=interval.display_name,
        schedule_description=interval.description,
        is_active=task.is_active,
        status=task.status.value,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
        last_executed_at=task.last_executed_at,
        next_run_time=task.next_run_time,
        execution_count=task.execution_count,
        success_count=task.success_count,
        failure_count=task.failure_count,
        success_rate=task.success_rate,
        average_results=task.average_results,
        total_results=task.total_results,
        total_credits_used=task.total_credits_used
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
    """创建新的搜索任务"""
    try:
        # 验证调度间隔
        try:
            ScheduleInterval.from_value(task_data.schedule_interval)
        except ValueError as e:
            raise HTTPException(400, f"无效的调度间隔: {str(e)}")

        # 使用安全ID创建任务
        task = SearchTask.create_with_secure_id(
            name=task_data.name,
            description=task_data.description,
            query=task_data.query,
            target_website=task_data.target_website,
            crawl_url=task_data.crawl_url,
            search_config=task_data.search_config,
            schedule_interval=task_data.schedule_interval,
            is_active=task_data.is_active,
            created_by="current_user",  # TODO: 从JWT token获取用户信息
            status=TaskStatus.ACTIVE if task_data.is_active else TaskStatus.DISABLED
        )

        # 如果 target_website 为空，自动从 search_config 提取
        task.sync_target_website()

        # 保存到仓储
        repo = await get_task_repository()
        await repo.create(task)

        logger.info(f"创建搜索任务: {task.name} (ID: {task.get_id_string()}, 目标网站: {task.target_website})")

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
    """更新搜索任务"""
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    # 更新字段
    if task_data.name is not None:
        task.name = task_data.name

    if task_data.description is not None:
        task.description = task_data.description

    if task_data.query is not None:
        task.query = task_data.query

    if task_data.crawl_url is not None:
        task.crawl_url = task_data.crawl_url

    # 标记是否显式更新了 target_website
    target_website_explicitly_updated = False

    if task_data.target_website is not None:
        task.target_website = task_data.target_website
        target_website_explicitly_updated = True

    if task_data.search_config is not None:
        task.search_config = task_data.search_config
        # 如果更新了 search_config 但没有显式更新 target_website，则自动同步
        if not target_website_explicitly_updated:
            # 强制更新 target_website 为新的第一个域名
            task.target_website = task.extract_target_website()

    if task_data.schedule_interval is not None:
        try:
            ScheduleInterval.from_value(task_data.schedule_interval)
            task.schedule_interval = task_data.schedule_interval
        except ValueError as e:
            raise HTTPException(400, f"无效的调度间隔: {str(e)}")

    if task_data.is_active is not None:
        task.is_active = task_data.is_active
        task.status = TaskStatus.ACTIVE if task_data.is_active else TaskStatus.DISABLED

    task.updated_at = datetime.utcnow()

    # 更新到仓储
    await repo.update(task)

    logger.info(f"更新搜索任务: {task.name} (ID: {task_id}, 目标网站: {task.target_website})")

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
    description="永久删除搜索任务及其相关的搜索结果。此操作不可撤销。"
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