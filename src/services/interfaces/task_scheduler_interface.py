"""定时搜索任务调度器接口定义

定义调度器服务的标准接口，支持不同的调度器实现：
- APScheduler实现（用于生产环境）
- 内存调度器实现（用于测试）
- 其他调度器实现的扩展
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from src.core.domain.entities.search_task import SearchTask


class ITaskScheduler(ABC):
    """定时搜索任务调度器接口"""
    
    @abstractmethod
    async def start(self) -> None:
        """启动调度器服务
        
        Raises:
            SchedulerStartError: 调度器启动失败时抛出
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止调度器服务
        
        Raises:
            SchedulerStopError: 调度器停止失败时抛出
        """
        pass
    
    @abstractmethod
    async def add_task(self, task: SearchTask) -> None:
        """添加新任务到调度器
        
        Args:
            task: 要添加的搜索任务
            
        Raises:
            TaskScheduleError: 任务调度失败时抛出
        """
        pass
    
    @abstractmethod
    async def remove_task(self, task_id: str) -> None:
        """从调度器移除任务
        
        Args:
            task_id: 要移除的任务ID
            
        Raises:
            TaskRemoveError: 任务移除失败时抛出
        """
        pass
    
    @abstractmethod
    async def update_task(self, task: SearchTask) -> None:
        """更新调度器中的任务
        
        Args:
            task: 要更新的搜索任务
            
        Raises:
            TaskUpdateError: 任务更新失败时抛出
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态
        
        Returns:
            包含调度器状态信息的字典：
            - status: 调度器状态（running/stopped）
            - active_jobs: 活跃任务数量
            - next_run_time: 下次执行时间
            - jobs: 任务列表详情
        """
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """检查调度器是否在运行
        
        Returns:
            True if running, False otherwise
        """
        pass
    
    @abstractmethod
    async def pause_task(self, task_id: str) -> None:
        """暂停指定任务
        
        Args:
            task_id: 要暂停的任务ID
            
        Raises:
            TaskNotFoundError: 任务不存在时抛出
        """
        pass
    
    @abstractmethod
    async def resume_task(self, task_id: str) -> None:
        """恢复指定任务
        
        Args:
            task_id: 要恢复的任务ID
            
        Raises:
            TaskNotFoundError: 任务不存在时抛出
        """
        pass
    
    @abstractmethod
    async def execute_task_now(self, task_id: str) -> Dict[str, Any]:
        """立即执行指定任务（手动触发）
        
        Args:
            task_id: 要执行的任务ID
            
        Returns:
            执行结果信息
            
        Raises:
            TaskNotFoundError: 任务不存在时抛出
            TaskExecutionError: 任务执行失败时抛出
        """
        pass
    
    @abstractmethod
    def get_task_next_run(self, task_id: str) -> Optional[datetime]:
        """获取指定任务的下次执行时间
        
        Args:
            task_id: 任务ID
            
        Returns:
            下次执行时间，如果任务不存在或未调度则返回None
        """
        pass
    
    @abstractmethod
    def get_running_tasks(self) -> Dict[str, Any]:
        """获取当前正在运行的任务列表
        
        Returns:
            正在运行的任务信息字典
        """
        pass


class SchedulerError(Exception):
    """调度器基础异常类"""
    pass


class SchedulerStartError(SchedulerError):
    """调度器启动异常"""
    pass


class SchedulerStopError(SchedulerError):
    """调度器停止异常"""
    pass


class TaskScheduleError(SchedulerError):
    """任务调度异常"""
    pass


class TaskRemoveError(SchedulerError):
    """任务移除异常"""
    pass


class TaskUpdateError(SchedulerError):
    """任务更新异常"""
    pass


class TaskNotFoundError(SchedulerError):
    """任务未找到异常"""
    pass


class TaskExecutionError(SchedulerError):
    """任务执行异常"""
    pass