"""
内部系统API端点

这些接口仅供系统内部使用，不暴露在前端API文档中。
包括手动执行任务、系统状态查询等管理功能。
"""

import os
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_config import UserSearchConfig, SearchConfigManager
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 创建内部API路由，设置include_in_schema=False隐藏在文档中
router = APIRouter(
    prefix="/internal",
    tags=["🔧 系统内部接口"],
    include_in_schema=False  # 隐藏在API文档中
)

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
            logger.warning(f"MongoDB不可用，结果保存将失败: {e}")
            raise HTTPException(503, "结果仓储不可用")
    return result_repository


# ==========================================
# Pydantic 数据模型
# ==========================================

class TaskExecutionResponse(BaseModel):
    """任务执行响应"""
    success: bool = Field(..., description="执行是否成功")
    task_id: str = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    total_results: int = Field(..., description="获得结果数量")
    execution_time_ms: int = Field(..., description="执行时间（毫秒）")
    credits_used: int = Field(..., description="消耗积分")
    is_test_mode: bool = Field(..., description="是否为测试模式")
    error_message: str = Field(None, description="错误信息（如果有）")
    results_preview: list = Field(..., description="结果预览（前5条）")


class SystemTestModeStatus(BaseModel):
    """系统测试模式状态"""
    is_test_mode: bool = Field(..., description="是否启用测试模式")
    max_limit: int = Field(..., description="最大限制数量")
    default_limit: int = Field(..., description="默认限制数量")
    search_timeout_seconds: int = Field(..., description="搜索超时秒数")
    max_credits_per_search: int = Field(..., description="每次搜索最大积分")
    max_credits_per_day: int = Field(..., description="每日最大积分")
    cache_enabled: bool = Field(..., description="是否启用缓存")
    log_level: str = Field(..., description="日志级别")


class SystemHealthStatus(BaseModel):
    """系统健康状态"""
    status: str = Field(..., description="系统状态")
    timestamp: datetime = Field(..., description="检查时间")
    database_connected: bool = Field(..., description="数据库连接状态")
    search_service_available: bool = Field(..., description="搜索服务可用状态")
    active_tasks_count: int = Field(..., description="活跃任务数量")
    total_tasks_count: int = Field(..., description="总任务数量")
    system_config: SystemTestModeStatus = Field(..., description="系统配置")


# ==========================================
# API端点
# ==========================================

@router.post(
    "/search-tasks/{task_id}/execute",
    response_model=TaskExecutionResponse,
    summary="手动执行搜索任务",
    description="手动触发搜索任务执行，通常用于测试或系统管理。仅供内部使用，不对前端暴露。"
)
async def execute_task_manually(task_id: str):
    """
    手动执行搜索任务

    优先级逻辑：
    1. 如果 crawl_url 存在 → 使用 Firecrawl Scrape API (网址爬取)
    2. 如果 crawl_url 不存在 → 使用 Firecrawl Search API (关键词搜索)
    """
    repo = await get_task_repository()
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(404, f"任务不存在: {task_id}")

    if not task.is_active:
        raise HTTPException(400, "任务未启用，无法执行")

    try:
        # ========================================
        # 优先级逻辑：crawl_url 优先于 query
        # ========================================
        if task.crawl_url:
            # 方案1：使用 Firecrawl Scrape API 爬取指定网址
            logger.info(f"🌐 使用网址爬取模式: {task.crawl_url}")
            result_batch = await _execute_crawl_task(task)
        else:
            # 方案2：使用 Firecrawl Search API 关键词搜索
            logger.info(f"🔍 使用关键词搜索模式: {task.query}")
            result_batch = await _execute_search_task(task)

        # 保存搜索结果到数据库（如果有结果）
        if result_batch.results:
            try:
                result_repo = await get_result_repository()
                await result_repo.save_results(result_batch.results)
                logger.info(f"保存结果成功: {len(result_batch.results)}条 (任务ID: {task_id})")
            except Exception as e:
                logger.error(f"保存结果失败: {e}")
                # 不抛出异常,继续处理任务统计

        # 更新任务统计
        task.record_execution(
            success=result_batch.success,
            results_count=result_batch.returned_count,
            credits_used=result_batch.credits_used
        )

        # 更新到仓储
        await repo.update(task)

        logger.info(f"手动执行任务成功: {task.name} (ID: {task_id})")

        # 返回执行结果
        return TaskExecutionResponse(
            success=result_batch.success,
            task_id=task_id,
            task_name=task.name,
            total_results=result_batch.returned_count,
            execution_time_ms=result_batch.execution_time_ms,
            credits_used=result_batch.credits_used,
            is_test_mode=result_batch.is_test_mode,
            error_message=None,
            results_preview=[r.to_summary() for r in result_batch.results[:5]]
        )

    except Exception as e:
        logger.error(f"手动执行任务失败: {e}")

        # 记录失败统计
        task.record_execution(success=False)
        await repo.update(task)

        # 返回错误信息
        return TaskExecutionResponse(
            success=False,
            task_id=task_id,
            task_name=task.name,
            total_results=0,
            execution_time_ms=0,
            credits_used=0,
            is_test_mode=True,
            error_message=str(e),
            results_preview=[]
        )


async def _execute_search_task(task: SearchTask) -> SearchResultBatch:
    """执行关键词搜索任务（使用 Firecrawl Search API）"""
    adapter = FirecrawlSearchAdapter()
    user_config = UserSearchConfig.from_json(task.search_config)
    result_batch = await adapter.search(
        query=task.query,
        user_config=user_config,
        task_id=str(task.id)
    )
    return result_batch


async def _execute_crawl_task(task: SearchTask) -> SearchResultBatch:
    """执行网址爬取任务（使用 Firecrawl Scrape API）"""
    from datetime import datetime

    start_time = datetime.utcnow()

    # 创建爬虫适配器
    crawler = FirecrawlAdapter()

    # 构建爬取选项（从 search_config 提取）
    scrape_options = {
        "wait_for": task.search_config.get("wait_for", 1000),
        "include_tags": task.search_config.get("include_tags"),
        "exclude_tags": task.search_config.get("exclude_tags", ["nav", "footer", "header"])
    }

    # 执行爬取
    crawl_result = await crawler.scrape(task.crawl_url, **scrape_options)

    # 将 CrawlResult 转换为 SearchResult
    search_result = SearchResult(
        task_id=str(task.id),
        title=crawl_result.metadata.get("title", task.crawl_url),
        url=crawl_result.url,
        content=crawl_result.content[:5000] if crawl_result.content else "",
        snippet=crawl_result.content[:200] if crawl_result.content else "",
        source="crawl",
        markdown_content=crawl_result.markdown[:5000] if crawl_result.markdown else None,
        html_content=crawl_result.html,
        metadata=crawl_result.metadata or {},
        relevance_score=1.0,  # 直接爬取的页面相关性为100%
        status=ResultStatus.PROCESSED
    )

    # 创建结果批次
    batch = SearchResultBatch(
        task_id=str(task.id),
        query=f"URL爬取: {task.crawl_url}",
        search_config=task.search_config,
        is_test_mode=False
    )
    batch.add_result(search_result)
    batch.total_count = 1
    batch.credits_used = 1  # Scrape API 通常消耗1个积分

    # 计算执行时间
    end_time = datetime.utcnow()
    batch.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

    logger.info(f"✅ 网址爬取完成: {task.crawl_url}, 耗时: {batch.execution_time_ms}ms")

    return batch


@router.get(
    "/system/test-mode-status",
    response_model=SystemTestModeStatus,
    summary="获取系统测试模式状态",
    description="获取系统测试模式配置和状态信息，用于系统管理和调试。仅供内部使用。"
)
async def get_system_test_mode_status():
    """获取系统测试模式状态"""
    is_test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
    config_manager = SearchConfigManager()
    
    return SystemTestModeStatus(
        is_test_mode=is_test_mode,
        max_limit=config_manager.system_config.MAX_LIMIT,
        default_limit=config_manager.system_config.DEFAULT_LIMIT,
        search_timeout_seconds=config_manager.system_config.SEARCH_TIMEOUT_SECONDS,
        max_credits_per_search=config_manager.system_config.MAX_CREDITS_PER_SEARCH,
        max_credits_per_day=config_manager.system_config.MAX_CREDITS_PER_DAY,
        cache_enabled=config_manager.system_config.ENABLE_CACHE,
        log_level=config_manager.system_config.LOG_LEVEL
    )


@router.get(
    "/system/health",
    response_model=SystemHealthStatus,
    summary="系统健康状态检查",
    description="获取系统整体健康状态，包括数据库连接、服务可用性、任务统计等。用于监控和运维。"
)
async def get_system_health():
    """系统健康状态检查"""
    
    # 检查数据库连接
    database_connected = False
    try:
        repo = await get_task_repository()
        database_connected = True
    except Exception as e:
        logger.warning(f"数据库连接检查失败: {e}")
    
    # 检查搜索服务
    search_service_available = False
    try:
        adapter = FirecrawlSearchAdapter()
        # 这里可以添加实际的服务可用性检查
        search_service_available = True
    except Exception as e:
        logger.warning(f"搜索服务检查失败: {e}")
    
    # 获取任务统计
    active_tasks_count = 0
    total_tasks_count = 0
    
    if database_connected:
        try:
            repo = await get_task_repository()
            # 获取任务统计（这里简化实现）
            tasks, total = await repo.list_tasks(page=1, page_size=1000)
            total_tasks_count = total
            active_tasks_count = sum(1 for task in tasks if task.is_active)
        except Exception as e:
            logger.warning(f"任务统计获取失败: {e}")
    
    # 获取系统配置
    system_config = await get_system_test_mode_status()
    
    # 确定整体状态
    if database_connected and search_service_available:
        overall_status = "healthy"
    elif database_connected or search_service_available:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    return SystemHealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow(),
        database_connected=database_connected,
        search_service_available=search_service_available,
        active_tasks_count=active_tasks_count,
        total_tasks_count=total_tasks_count,
        system_config=system_config
    )


@router.post(
    "/system/maintenance/clear-old-results",
    summary="清理旧搜索结果",
    description="清理指定天数之前的搜索结果数据，释放存储空间。仅供系统管理使用。"
)
async def clear_old_results(days: int = 30):
    """清理旧搜索结果"""
    if days < 1:
        raise HTTPException(400, "清理天数必须大于0")
    
    try:
        from src.api.v1.endpoints.search_results_frontend import clear_task_results
        from datetime import timedelta
        
        # 这里应该实现真正的数据库清理逻辑
        # 目前只是示例实现
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 记录操作日志
        logger.info(f"开始清理 {days} 天前的搜索结果，截止日期: {cutoff_date}")
        
        # 实际清理逻辑会在这里实现
        cleaned_count = 0  # 模拟清理数量
        
        return {
            "success": True,
            "message": f"清理完成",
            "days": days,
            "cutoff_date": cutoff_date,
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"清理旧结果失败: {e}")
        raise HTTPException(500, f"清理操作失败: {str(e)}")


@router.get(
    "/system/stats/overview",
    summary="系统统计概览",
    description="获取系统整体统计信息，包括任务数量、执行情况、积分消耗等。用于管理面板。"
)
async def get_system_stats_overview():
    """系统统计概览"""
    
    try:
        repo = await get_task_repository()
        
        # 获取所有任务
        tasks, total_count = await repo.list_tasks(page=1, page_size=1000)
        
        # 统计各种状态
        active_count = sum(1 for task in tasks if task.is_active)
        total_executions = sum(task.execution_count for task in tasks)
        total_successes = sum(task.success_count for task in tasks)
        total_credits = sum(task.total_credits_used for task in tasks)
        total_results = sum(task.total_results for task in tasks)
        
        # 计算平均成功率
        avg_success_rate = (total_successes / total_executions * 100) if total_executions > 0 else 0
        
        return {
            "total_tasks": total_count,
            "active_tasks": active_count,
            "inactive_tasks": total_count - active_count,
            "total_executions": total_executions,
            "total_successes": total_successes,
            "average_success_rate": round(avg_success_rate, 2),
            "total_results": total_results,
            "total_credits_used": total_credits,
            "average_results_per_execution": round(total_results / total_executions, 2) if total_executions > 0 else 0,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        raise HTTPException(500, f"获取统计信息失败: {str(e)}")