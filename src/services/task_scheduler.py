"""
定时搜索任务调度器服务

基于APScheduler实现的后台任务调度器，负责：
1. 定期检查和执行搜索任务
2. 管理任务调度生命周期
3. 执行结果记录和统计
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore

from src.core.domain.entities.search_task import SearchTask, TaskStatus, ScheduleInterval, TaskType
from src.core.domain.entities.search_config import UserSearchConfig
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.infrastructure.database.memory_repositories import InMemorySearchTaskRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.services.interfaces.task_scheduler_interface import (
    ITaskScheduler, SchedulerStartError, SchedulerStopError,
    TaskScheduleError, TaskRemoveError, TaskUpdateError,
    TaskNotFoundError, TaskExecutionError
)
from src.services.firecrawl import ExecutorFactory
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TaskSchedulerService(ITaskScheduler):
    """定时搜索任务调度服务"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.task_repository: Optional[SearchTaskRepository] = None
        self.result_repository: Optional[SearchResultRepository] = None
        self.processed_result_repository: Optional[ProcessedResultRepository] = None  # v2.0.0 新增
        self.search_adapter: Optional[FirecrawlSearchAdapter] = None
        self._is_running = False

        # 配置调度器
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """配置APScheduler"""
        jobstores = {
            'default': MemoryJobStore()
        }
        
        executors = {
            'default': AsyncIOExecutor()
        }
        
        job_defaults = {
            'coalesce': False,  # 不合并延迟的任务
            'max_instances': 3,  # 最大并发实例数
            'misfire_grace_time': 300  # 任务错过时间的容忍度（秒）
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )
    
    async def _get_task_repository(self):
        """获取任务仓储实例"""
        if self.task_repository is None:
            try:
                await get_mongodb_database()
                self.task_repository = SearchTaskRepository()
                logger.info("调度器使用MongoDB仓储")
            except Exception as e:
                logger.warning(f"MongoDB不可用，调度器使用内存仓储: {e}")
                self.task_repository = InMemorySearchTaskRepository()
        return self.task_repository

    async def _get_result_repository(self):
        """获取结果仓储实例"""
        if self.result_repository is None:
            try:
                await get_mongodb_database()
                self.result_repository = SearchResultRepository()
                logger.info("调度器使用MongoDB结果仓储")
            except Exception as e:
                logger.warning(f"MongoDB不可用，搜索结果将仅保存到内存: {e}")
                self.result_repository = None
        return self.result_repository

    async def _get_processed_result_repository(self):
        """获取AI处理结果仓储实例（v2.0.0 新增）"""
        if self.processed_result_repository is None:
            try:
                await get_mongodb_database()
                self.processed_result_repository = ProcessedResultRepository()
                logger.info("调度器使用MongoDB AI处理结果仓储")
            except Exception as e:
                logger.warning(f"MongoDB不可用，AI处理结果将不可用: {e}")
                self.processed_result_repository = None
        return self.processed_result_repository
    
    async def start(self):
        """启动调度器服务"""
        if self._is_running:
            logger.warning("调度器已在运行中")
            return
        
        try:
            # 初始化依赖
            await self._get_task_repository()
            await self._get_result_repository()
            self.search_adapter = FirecrawlSearchAdapter()

            # 启动调度器
            self.scheduler.start()
            self._is_running = True
            
            # 添加主检查任务（每分钟检查一次）
            self.scheduler.add_job(
                self._check_and_execute_tasks,
                trigger=IntervalTrigger(minutes=1),
                id='main_task_checker',
                name='主任务检查器',
                replace_existing=True
            )
            
            # 加载现有活跃任务
            await self._load_active_tasks()
            
            logger.info("🚀 定时搜索任务调度器启动成功")
            
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            raise
    
    async def stop(self, deactivate_tasks: bool = False):
        """停止调度器服务

        Args:
            deactivate_tasks: 是否同时停用所有活跃任务（设置is_active=False）
        """
        if not self._is_running:
            return

        try:
            # 如果需要停用所有任务，先更新数据库
            if deactivate_tasks:
                try:
                    repo = await self._get_task_repository()
                    # 获取所有活跃任务
                    active_tasks, _ = await repo.list_tasks(
                        page=1,
                        page_size=10000,
                        is_active=True
                    )

                    # 将所有活跃任务设置为非活跃
                    deactivated_count = 0
                    for task in active_tasks:
                        task.is_active = False
                        task.status = TaskStatus.DISABLED
                        task.updated_at = datetime.utcnow()
                        await repo.update(task)
                        deactivated_count += 1

                    if deactivated_count > 0:
                        logger.info(f"⏹️ 已停用 {deactivated_count} 个活跃任务")
                except Exception as e:
                    logger.error(f"停用任务失败: {e}")
                    # 继续执行调度器停止操作

            self.scheduler.shutdown(wait=True)
            self._is_running = False
            logger.info("⏹️ 定时搜索任务调度器已停止")
        except Exception as e:
            logger.error(f"停止调度器失败: {e}")
    
    async def _load_active_tasks(self):
        """加载所有活跃的搜索任务到调度器"""
        try:
            repo = await self._get_task_repository()
            
            # 获取所有活跃任务（使用循环加载避免数量限制）
            all_tasks = []
            page = 1
            page_size = 100
            while True:
                tasks_batch, total = await repo.list_tasks(
                    page=page,
                    page_size=page_size,
                    is_active=True
                )
                all_tasks.extend(tasks_batch)
                if len(all_tasks) >= total:
                    break
                page += 1
            tasks = all_tasks
            
            loaded_count = 0
            for task in tasks:
                try:
                    await self._schedule_task(task)
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"加载任务失败 {task.name} (ID: {task.id}): {e}")
            
            logger.info(f"📋 加载了 {loaded_count} 个活跃搜索任务")
            
        except Exception as e:
            logger.error(f"加载活跃任务失败: {e}")
    
    async def _schedule_task(self, task: SearchTask):
        """将单个任务添加到调度器"""
        try:
            # 获取调度间隔配置
            interval = ScheduleInterval.from_value(task.schedule_interval)
            
            # 创建Cron触发器
            trigger = CronTrigger.from_crontab(interval.cron_expression)
            
            # 添加任务到调度器
            job_id = f"search_task_{task.id}"
            self.scheduler.add_job(
                self._execute_search_task,
                trigger=trigger,
                args=[task.id],
                id=job_id,
                name=f"搜索任务: {task.name}",
                replace_existing=True
            )
            
            # 更新下次执行时间
            next_run = trigger.get_next_fire_time(None, datetime.now())
            if next_run:
                task.next_run_time = next_run
                repo = await self._get_task_repository()
                await repo.update(task)
            
            logger.info(f"✅ 任务已调度: {task.name} - {interval.description}")
            
        except Exception as e:
            logger.error(f"调度任务失败 {task.name}: {e}")
            raise
    
    async def add_task(self, task: SearchTask):
        """添加新任务到调度器"""
        if not self._is_running:
            logger.warning("调度器未运行，无法添加任务")
            return
        
        if task.is_active:
            await self._schedule_task(task)
            logger.info(f"➕ 新增调度任务: {task.name}")
    
    async def remove_task(self, task_id: str):
        """从调度器移除任务"""
        try:
            job_id = f"search_task_{task_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"➖ 移除调度任务: {task_id}")
        except Exception as e:
            logger.error(f"移除任务失败 {task_id}: {e}")
    
    async def update_task(self, task: SearchTask):
        """更新调度器中的任务"""
        await self.remove_task(str(task.id))
        if task.is_active:
            await self.add_task(task)
    
    async def _check_and_execute_tasks(self):
        """主检查函数：检查是否有任务需要执行"""
        try:
            logger.debug("🔍 执行主任务检查...")
            
            # 这里可以添加其他检查逻辑
            # 比如检查失败任务的重试、任务健康状态等
            
            # 获取调度器状态
            jobs = self.scheduler.get_jobs()
            active_jobs = len([job for job in jobs if job.id != 'main_task_checker'])
            
            if active_jobs > 0:
                logger.debug(f"📊 当前活跃任务数: {active_jobs}")
            
        except Exception as e:
            logger.error(f"主任务检查失败: {e}")
    
    async def _execute_search_task(self, task_id: str):
        """执行单个搜索任务（使用新的模块化执行器架构）

        根据任务类型自动选择对应的执行器：
        - SEARCH_KEYWORD: 关键词搜索 + 详情页爬取
        - CRAWL_WEBSITE: 网站递归爬取
        - SCRAPE_URL: 单页面爬取
        """
        start_time = datetime.utcnow()
        logger.info(f"🔍 开始执行搜索任务: {task_id}")

        try:
            # 获取任务详情
            repo = await self._get_task_repository()
            task = await repo.get_by_id(task_id)

            if not task:
                logger.error(f"任务不存在: {task_id}")
                return

            if not task.is_active:
                logger.info(f"任务已禁用，跳过执行: {task.name}")
                return

            # 更新任务状态
            task.last_executed_at = start_time

            # ========================================
            # v2.0.0 新架构：使用执行器工厂创建执行器
            # v2.1.0 多语言支持：自动选择多语言执行器
            # ========================================
            task_type = task.get_task_type()

            # v2.1.0: 如果启用了多语言搜索且是关键词搜索类型，自动切换到多语言执行器
            if task.should_use_multilang() and task_type == TaskType.SEARCH_KEYWORD:
                task_type = TaskType.SEARCH_MULTILANG
                logger.info(
                    f"🌐 检测到多语言配置，自动切换执行器: "
                    f"SEARCH_KEYWORD → SEARCH_MULTILANG (languages={task.languages})"
                )

            logger.info(f"🏭 任务类型: {task_type.value}")

            # 创建对应的执行器
            executor = ExecutorFactory.create(task_type)

            # 执行任务
            result_batch = await executor.execute(task)

            # v2.0.0 职责分离架构：保存到 search_results 和 processed_results_new
            if result_batch.results:
                try:
                    result_repo = await self._get_result_repository()
                    if result_repo:
                        # v4.32.0: 为每个结果设置 user_id（用于数据隔离查询）
                        for result in result_batch.results:
                            result.user_id = task.created_by
                            result.created_by = task.created_by

                        # 1. 保存原始结果到 search_results（纯数据存储）
                        await result_repo.save_results(result_batch.results)
                        logger.info(f"✅ 原始搜索结果已保存: {len(result_batch.results)}条")

                        # 2. 为每个原始结果创建待处理记录到 processed_results_new
                        processed_repo = await self._get_processed_result_repository()
                        if processed_repo:
                            # 提取所有原始结果ID
                            raw_result_ids = [str(r.id) for r in result_batch.results]

                            # 批量创建待处理记录
                            await processed_repo.bulk_create_pending_results(
                                raw_result_ids=raw_result_ids,
                                task_id=str(task_id)
                            )
                            logger.info(f"✅ 已创建{len(raw_result_ids)}条待AI处理记录")
                        else:
                            logger.warning("⚠️ processed_results_new仓储不可用，跳过AI处理记录创建")
                    else:
                        logger.warning("⚠️ MongoDB不可用，搜索结果未保存")
                except Exception as e:
                    logger.error(f"❌ 保存搜索结果失败: {e}")
                    # 失败不影响任务继续执行

            # 更新任务统计
            task.record_execution(
                success=result_batch.success,
                results_count=result_batch.returned_count,
                credits_used=result_batch.credits_used
            )

            # 计算下次执行时间
            interval = ScheduleInterval.from_value(task.schedule_interval)
            trigger = CronTrigger.from_crontab(interval.cron_expression)
            next_run = trigger.get_next_fire_time(None, datetime.now())
            if next_run:
                task.next_run_time = next_run

            # 保存任务更新
            await repo.update(task)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"✅ 搜索任务执行完成: {task.name} | "
                f"任务类型: {task_type.value} | "
                f"结果数: {result_batch.returned_count} | "
                f"耗时: {execution_time:.2f}s | "
                f"下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else 'N/A'}"
            )

        except Exception as e:
            logger.error(f"❌ 搜索任务执行失败 {task_id}: {e}")

            # 记录失败（包含错误信息）
            try:
                repo = await self._get_task_repository()
                task = await repo.get_by_id(task_id)
                if task:
                    # 提取简洁的错误信息
                    error_message = str(e)
                    # 如果错误信息太长，截取前500个字符
                    if len(error_message) > 500:
                        error_message = error_message[:500] + "..."

                    task.record_execution(success=False, error_message=error_message)
                    await repo.update(task)
                    logger.info(f"已记录任务失败信息: {task.name}")
            except Exception as update_error:
                logger.error(f"更新失败统计时出错: {update_error}")

    def is_running(self) -> bool:
        """检查调度器是否在运行"""
        return hasattr(self, '_is_running') and self._is_running
    
    async def pause_task(self, task_id: str) -> None:
        """暂停指定任务"""
        try:
            job_id = f"search_task_{task_id}"
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.pause_job(job_id)
                logger.info(f"⏸️ 暂停任务: {task_id}")
            else:
                raise TaskNotFoundError(f"任务未找到: {task_id}")
        except Exception as e:
            logger.error(f"暂停任务失败 {task_id}: {e}")
            if "not found" in str(e).lower():
                raise TaskNotFoundError(f"任务未找到: {task_id}")
            raise TaskScheduleError(f"暂停任务失败: {str(e)}")
    
    async def resume_task(self, task_id: str) -> None:
        """恢复指定任务"""
        try:
            job_id = f"search_task_{task_id}"
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.resume_job(job_id)
                logger.info(f"▶️ 恢复任务: {task_id}")
            else:
                raise TaskNotFoundError(f"任务未找到: {task_id}")
        except Exception as e:
            logger.error(f"恢复任务失败 {task_id}: {e}")
            if "not found" in str(e).lower():
                raise TaskNotFoundError(f"任务未找到: {task_id}")
            raise TaskScheduleError(f"恢复任务失败: {str(e)}")
    
    async def execute_task_now(self, task_id: str) -> Dict[str, Any]:
        """立即执行指定任务（手动触发）"""
        try:
            # 直接调用执行函数
            await self._execute_search_task(task_id)
            
            # 获取任务执行结果
            repo = await self._get_task_repository()
            task = await repo.get_by_id(task_id)
            
            if not task:
                raise TaskNotFoundError(f"任务不存在: {task_id}")
            
            return {
                "task_id": task_id,
                "task_name": task.name,
                "executed_at": datetime.utcnow().isoformat(),
                "status": "completed",
                "last_execution_success": task.success_count > 0,
                "execution_count": task.execution_count
            }
            
        except TaskNotFoundError:
            raise
        except Exception as e:
            logger.error(f"手动执行任务失败 {task_id}: {e}")
            raise TaskExecutionError(f"任务执行失败: {str(e)}")
    
    def get_task_next_run(self, task_id: str) -> Optional[datetime]:
        """获取指定任务的下次执行时间"""
        if not self.scheduler:
            return None
            
        job_id = f"search_task_{task_id}"
        job = self.scheduler.get_job(job_id)
        
        return job.next_run_time if job else None
    
    def get_running_tasks(self) -> Dict[str, Any]:
        """获取当前正在运行的任务列表"""
        if not self.scheduler:
            return {"running_tasks": [], "count": 0}
        
        running_jobs = self.scheduler.get_jobs()
        task_jobs = [
            job for job in running_jobs 
            if job.id.startswith('search_task_') and job.id != 'main_task_checker'
        ]
        
        return {
            "running_tasks": [
                {
                    "task_id": job.id.replace('search_task_', ''),
                    "task_name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "is_paused": job.next_run_time is None
                }
                for job in task_jobs
            ],
            "count": len(task_jobs)
        }

    def get_status(self) -> dict:
        """获取调度器状态"""
        if not self._is_running:
            return {
                "status": "stopped",
                "active_jobs": 0,
                "next_run_time": None
            }
        
        jobs = self.scheduler.get_jobs()
        active_jobs = [job for job in jobs if job.id != 'main_task_checker']
        
        # 获取最近的下次执行时间
        next_run_times = [job.next_run_time for job in active_jobs if job.next_run_time]
        next_run = min(next_run_times) if next_run_times else None
        
        return {
            "status": "running",
            "active_jobs": len(active_jobs),
            "next_run_time": next_run.isoformat() if next_run else None,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in active_jobs
            ]
        }


# 全局调度器实例和初始化锁
_scheduler_instance: Optional[TaskSchedulerService] = None
_scheduler_lock = asyncio.Lock()


async def get_scheduler() -> TaskSchedulerService:
    """获取调度器实例（线程安全单例模式）"""
    global _scheduler_instance
    # 双重检查锁定模式优化性能
    if _scheduler_instance is None:
        async with _scheduler_lock:
            # 锁内再次检查，防止竞态条件
            if _scheduler_instance is None:
                _scheduler_instance = TaskSchedulerService()
    return _scheduler_instance


@asynccontextmanager
async def scheduler_lifespan():
    """调度器生命周期管理器"""
    scheduler = await get_scheduler()
    try:
        await scheduler.start()
        yield scheduler
    finally:
        await scheduler.stop()


# 用于FastAPI应用的生命周期事件
async def start_scheduler():
    """启动调度器（用于FastAPI startup事件）"""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """停止调度器（用于FastAPI shutdown事件）"""
    global _scheduler_instance
    if _scheduler_instance:
        await _scheduler_instance.stop()
        _scheduler_instance = None