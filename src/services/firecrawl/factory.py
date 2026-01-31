"""
执行器工厂

根据任务类型创建对应的执行器实例

v2.1.0: 添加 MultilangSearchExecutor 支持多语言搜索
v4.30.0: 添加 MapDetailExecutor 支持 Map+Detail 详情页爬取
"""

import logging
from typing import Optional

from src.core.domain.entities.search_task import TaskType
from .base import TaskExecutor
from .executors import (
    CrawlExecutor,
    SearchExecutor,
    ScrapeExecutor,
    MapScrapeExecutor,
    MultilangSearchExecutor,
    MapDetailExecutor
)


logger = logging.getLogger(__name__)


class ExecutorFactory:
    """执行器工厂类

    根据任务类型创建对应的执行器实例
    使用工厂模式解耦任务调度与具体执行逻辑

    v2.1.0: 新增 SEARCH_MULTILANG 类型支持
    """

    # 执行器类型映射表
    _executor_map = {
        TaskType.CRAWL_WEBSITE: CrawlExecutor,
        TaskType.SEARCH_KEYWORD: SearchExecutor,
        TaskType.SCRAPE_URL: ScrapeExecutor,
        TaskType.MAP_SCRAPE_WEBSITE: MapScrapeExecutor,
        TaskType.SEARCH_MULTILANG: MultilangSearchExecutor,
        TaskType.MAP_DETAIL: MapDetailExecutor
    }

    @classmethod
    def create(cls, task_type: TaskType) -> TaskExecutor:
        """根据任务类型创建执行器

        Args:
            task_type: 任务类型枚举

        Returns:
            TaskExecutor: 对应的执行器实例

        Raises:
            ValueError: 不支持的任务类型
        """
        executor_class = cls._executor_map.get(task_type)

        if executor_class is None:
            supported_types = ", ".join([t.value for t in cls._executor_map.keys()])
            raise ValueError(
                f"不支持的任务类型: {task_type}. "
                f"支持的类型: {supported_types}"
            )

        logger.info(f"🏭 创建执行器: {executor_class.__name__} (类型: {task_type.value})")

        return executor_class()

    @classmethod
    def create_from_string(cls, task_type_str: str) -> TaskExecutor:
        """从字符串创建执行器（兼容性方法）

        Args:
            task_type_str: 任务类型字符串

        Returns:
            TaskExecutor: 对应的执行器实例

        Raises:
            ValueError: 无效的任务类型字符串
        """
        try:
            task_type = TaskType(task_type_str)
            return cls.create(task_type)
        except ValueError as e:
            supported_types = ", ".join([t.value for t in TaskType])
            raise ValueError(
                f"无效的任务类型: {task_type_str}. "
                f"支持的类型: {supported_types}"
            ) from e

    @classmethod
    def get_supported_types(cls) -> list[TaskType]:
        """获取所有支持的任务类型

        Returns:
            list[TaskType]: 支持的任务类型列表
        """
        return list(cls._executor_map.keys())

    @classmethod
    def register_executor(
        cls,
        task_type: TaskType,
        executor_class: type[TaskExecutor]
    ) -> None:
        """注册自定义执行器（扩展点）

        允许外部注册新的执行器类型，增强可扩展性

        Args:
            task_type: 任务类型
            executor_class: 执行器类

        Raises:
            TypeError: executor_class 不是 TaskExecutor 的子类
        """
        if not issubclass(executor_class, TaskExecutor):
            raise TypeError(
                f"执行器类必须继承 TaskExecutor, 得到: {executor_class.__name__}"
            )

        cls._executor_map[task_type] = executor_class
        logger.info(
            f"📝 注册自定义执行器: {executor_class.__name__} "
            f"(类型: {task_type.value})"
        )
