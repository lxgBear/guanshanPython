"""调度器管理API端点

提供调度器状态监控和管理功能的RESTful API接口。
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from src.services.task_scheduler import get_scheduler
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/scheduler", tags=["📊 调度器管理"])


# ==========================================
# Pydantic 数据模型
# ==========================================

class SchedulerStatusResponse(BaseModel):
    """调度器状态响应"""
    status: str = Field(..., description="调度器状态 (running/stopped)")
    active_jobs: int = Field(..., description="活跃任务数量")
    next_run_time: Optional[str] = Field(None, description="下次执行时间")
    jobs: list = Field(default_factory=list, description="任务列表详情")


class RunningTasksResponse(BaseModel):
    """正在运行任务响应"""
    running_tasks: list = Field(..., description="正在运行的任务列表")
    count: int = Field(..., description="正在运行的任务数量")


class TaskNextRunResponse(BaseModel):
    """任务下次执行时间响应"""
    task_id: str = Field(..., description="任务ID")
    next_run_time: Optional[str] = Field(None, description="下次执行时间")


class TaskExecutionResponse(BaseModel):
    """任务执行响应"""
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    executed_at: str = Field(..., description="执行时间")
    status: str = Field(..., description="执行状态")
    last_execution_success: bool = Field(..., description="最后一次执行是否成功")
    execution_count: int = Field(..., description="总执行次数")


# ==========================================
# API端点
# ==========================================

@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="获取调度器状态",
    description="获取调度器的当前运行状态，包括活跃任务数量和下次执行时间等信息。"
)
async def get_scheduler_status():
    """获取调度器状态"""
    try:
        scheduler = await get_scheduler()
        status = scheduler.get_status()
        
        return SchedulerStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        raise HTTPException(500, f"获取调度器状态失败: {str(e)}")


@router.get(
    "/running-tasks",
    response_model=RunningTasksResponse,
    summary="获取正在运行的任务",
    description="获取当前正在运行的所有搜索任务的详细信息。"
)
async def get_running_tasks():
    """获取正在运行的任务"""
    try:
        scheduler = await get_scheduler()
        running_tasks = scheduler.get_running_tasks()
        
        return RunningTasksResponse(**running_tasks)
        
    except Exception as e:
        logger.error(f"获取运行任务失败: {e}")
        raise HTTPException(500, f"获取运行任务失败: {str(e)}")


@router.get(
    "/tasks/{task_id}/next-run",
    response_model=TaskNextRunResponse,
    summary="获取任务下次执行时间",
    description="获取指定任务的下次计划执行时间。"
)
async def get_task_next_run(task_id: str = Path(..., description="任务ID")):
    """获取任务下次执行时间"""
    try:
        scheduler = await get_scheduler()
        next_run = scheduler.get_task_next_run(task_id)
        
        return TaskNextRunResponse(
            task_id=task_id,
            next_run_time=next_run.isoformat() if next_run else None
        )
        
    except Exception as e:
        logger.error(f"获取任务下次执行时间失败 {task_id}: {e}")
        raise HTTPException(500, f"获取任务下次执行时间失败: {str(e)}")


@router.post(
    "/tasks/{task_id}/execute",
    response_model=TaskExecutionResponse,
    summary="立即执行任务",
    description="手动触发指定任务立即执行，不等待计划的执行时间。适用于调试和紧急执行场景。"
)
async def execute_task_now(task_id: str = Path(..., description="任务ID")):
    """立即执行指定任务"""
    try:
        logger.info(f"🚀 收到手动执行任务请求: {task_id}")

        scheduler = await get_scheduler()

        if not scheduler.is_running():
            raise HTTPException(503, "调度器未运行，无法执行任务")

        result = await scheduler.execute_task_now(task_id)

        logger.info(f"✅ 任务手动执行完成: {task_id}")

        return TaskExecutionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手动执行任务失败 {task_id}: {e}")

        # 根据错误类型返回合适的HTTP状态码
        if "not found" in str(e).lower() or "不存在" in str(e):
            raise HTTPException(404, f"任务不存在: {task_id}")
        elif "失败" in str(e) or "error" in str(e).lower():
            raise HTTPException(500, f"任务执行失败: {str(e)}")
        else:
            raise HTTPException(500, f"未知错误: {str(e)}")


@router.get(
    "/health",
    summary="调度器健康检查",
    description="检查调度器服务的健康状态。"
)
async def scheduler_health_check():
    """调度器健康检查"""
    try:
        scheduler = await get_scheduler()
        is_running = scheduler.is_running()

        if is_running:
            status = scheduler.get_status()
            return {
                "status": "healthy",
                "scheduler_running": True,
                "active_jobs": status.get("active_jobs", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "stopped",
                "scheduler_running": False,
                "active_jobs": 0,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"调度器健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }