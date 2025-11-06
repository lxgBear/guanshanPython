"""
Firecrawl 模块基础接口和抽象类

定义统一的任务执行接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResultBatch
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TaskExecutor(ABC):
    """任务执行器抽象基类

    所有具体执行器必须继承此类并实现 execute 和 validate_config 方法
    """

    def __init__(self):
        """初始化执行器"""
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行任务并返回结果批次

        Args:
            task: 搜索任务实体

        Returns:
            SearchResultBatch: 执行结果批次

        Raises:
            ExecutorException: 执行过程中的错误
        """
        pass

    @abstractmethod
    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置是否有效

        Args:
            task: 搜索任务实体

        Returns:
            bool: 配置是否有效
        """
        pass

    def _create_result_batch(
        self,
        task: SearchTask,
        query: Optional[str] = None
    ) -> SearchResultBatch:
        """创建结果批次

        Args:
            task: 搜索任务
            query: 查询字符串（可选，默认使用 task.query）

        Returns:
            SearchResultBatch: 空的结果批次
        """
        return SearchResultBatch(
            task_id=str(task.id),
            query=query or task.query,
            search_config=task.search_config,
            is_test_mode=False
        )

    def _log_execution_start(self, task: SearchTask):
        """记录执行开始"""
        self.logger.info(
            f"🚀 开始执行任务: {task.name} "
            f"(ID: {task.id}, 类型: {task.task_type})"
        )

    def _log_execution_end(
        self,
        task: SearchTask,
        result_count: int,
        duration_ms: int
    ):
        """记录执行结束"""
        self.logger.info(
            f"✅ 任务执行完成: {task.name} | "
            f"结果数: {result_count} | "
            f"耗时: {duration_ms}ms"
        )


class ExecutorException(Exception):
    """执行器异常基类"""
    pass


class ConfigValidationError(ExecutorException):
    """配置验证错误"""
    pass


class ExecutionError(ExecutorException):
    """执行错误"""
    pass
