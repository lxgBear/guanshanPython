"""内存仓储实现（用于开发和测试）"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from src.core.domain.entities.search_task import SearchTask, TaskStatus
from src.core.domain.entities.search_result import SearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InMemorySearchTaskRepository:
    """内存搜索任务仓储"""
    
    def __init__(self):
        self._storage: Dict[str, SearchTask] = {}
        logger.info("初始化内存任务存储")
    
    async def create(self, task: SearchTask) -> SearchTask:
        """创建任务"""
        self._storage[str(task.id)] = task
        logger.info(f"创建任务成功: {task.name} (ID: {task.id})")
        return task
    
    async def get_by_id(self, task_id: str) -> Optional[SearchTask]:
        """根据ID获取任务"""
        return self._storage.get(task_id)
    
    async def update(self, task: SearchTask) -> SearchTask:
        """更新任务"""
        if str(task.id) not in self._storage:
            raise ValueError(f"任务不存在: {task.id}")
        
        self._storage[str(task.id)] = task
        logger.info(f"更新任务成功: {task.name} (ID: {task.id})")
        return task
    
    async def delete(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._storage:
            task = self._storage.pop(task_id)
            logger.info(f"删除任务成功: {task.name} (ID: {task_id})")
            return True
        return False
    
    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
        query: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> tuple[List[SearchTask], int]:
        """获取任务列表"""
        # 过滤任务
        filtered_tasks = list(self._storage.values())
        
        if status:
            filtered_tasks = [t for t in filtered_tasks if t.status.value == status]
        
        if is_active is not None:
            filtered_tasks = [t for t in filtered_tasks if t.is_active == is_active]
        
        if created_by:
            filtered_tasks = [t for t in filtered_tasks if t.created_by == created_by]
        
        if query:
            query_lower = query.lower()
            filtered_tasks = [
                t for t in filtered_tasks
                if (query_lower in t.name.lower() or 
                    query_lower in t.query.lower() or
                    (t.description and query_lower in t.description.lower()))
            ]
        
        # 排序（按创建时间倒序）
        filtered_tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # 分页
        total = len(filtered_tasks)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        
        page_tasks = filtered_tasks[start:end]
        
        return page_tasks, total
    
    async def get_active_tasks(self) -> List[SearchTask]:
        """获取所有活跃任务（用于调度）"""
        return [
            task for task in self._storage.values()
            if task.is_active and task.status == TaskStatus.ACTIVE
        ]
    
    async def get_tasks_to_execute(self, current_time: datetime) -> List[SearchTask]:
        """获取需要执行的任务"""
        return [
            task for task in self._storage.values()
            if (task.is_active and 
                task.status == TaskStatus.ACTIVE and
                (task.next_run_time is None or task.next_run_time <= current_time))
        ]


class InMemorySearchResultRepository:
    """内存搜索结果仓储"""
    
    def __init__(self):
        self._storage: Dict[str, SearchResult] = {}
        logger.info("初始化内存结果存储")
    
    async def save_results(self, results: List[SearchResult]) -> None:
        """批量保存搜索结果"""
        if not results:
            return
        
        for result in results:
            self._storage[str(result.id)] = result
        
        logger.info(f"保存搜索结果成功: {len(results)}条")
    
    async def get_results_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20,
        execution_time: Optional[datetime] = None
    ) -> tuple[List[SearchResult], int]:
        """获取任务的搜索结果"""
        # 过滤结果
        filtered_results = [
            result for result in self._storage.values()
            if str(result.task_id) == task_id
        ]
        
        if execution_time:
            filtered_results = [
                result for result in filtered_results
                if result.execution_time == execution_time
            ]
        
        # 排序（按创建时间倒序）
        filtered_results.sort(key=lambda r: r.created_at, reverse=True)
        
        # 分页
        total = len(filtered_results)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        
        page_results = filtered_results[start:end]
        
        return page_results, total
    
    async def get_latest_results(
        self,
        task_id: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """获取任务的最新结果"""
        # 过滤并排序
        task_results = [
            result for result in self._storage.values()
            if str(result.task_id) == task_id
        ]
        
        task_results.sort(key=lambda r: r.created_at, reverse=True)
        
        return task_results[:limit]
    
    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果"""
        deleted_count = 0
        to_delete = []
        
        for result_id, result in self._storage.items():
            if str(result.task_id) == task_id:
                to_delete.append(result_id)
        
        for result_id in to_delete:
            self._storage.pop(result_id)
            deleted_count += 1
        
        logger.info(f"删除任务结果: {task_id}, 删除数量: {deleted_count}")
        return deleted_count