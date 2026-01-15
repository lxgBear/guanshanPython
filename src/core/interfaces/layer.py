"""层基础接口定义

所有层（搜索层、AI层等）必须实现的基础接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class LayerStatus(str, Enum):
    """层执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class LayerConfig:
    """层配置基类"""
    enabled: bool = True
    timeout: int = 300  # 秒
    retry_count: int = 3
    retry_delay: float = 1.0  # 秒


@dataclass
class LayerContext:
    """层执行上下文 - 在层之间传递

    Attributes:
        task_id: 任务ID，用于关联搜索结果和AI处理
        user_id: 用户ID
        query: 用户查询
        options: 执行选项
        shared_data: 层间共享数据
        metadata: 元数据
    """
    task_id: str
    user_id: str
    query: str
    options: Dict[str, Any] = field(default_factory=dict)
    shared_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_option(self, key: str, default: Any = None) -> Any:
        """获取选项值"""
        return self.options.get(key, default)

    def set_shared(self, key: str, value: Any) -> None:
        """设置共享数据"""
        self.shared_data[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        """获取共享数据"""
        return self.shared_data.get(key, default)


@dataclass
class LayerResult:
    """层执行结果基类

    Attributes:
        status: 执行状态
        data: 结果数据
        error: 错误信息
        metrics: 执行指标
        started_at: 开始时间
        completed_at: 完成时间
    """
    status: LayerStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        """是否执行成功"""
        return self.status == LayerStatus.COMPLETED

    @property
    def duration_ms(self) -> Optional[int]:
        """执行时长（毫秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
            "metrics": self.metrics,
            "duration_ms": self.duration_ms,
        }


class ILayer(ABC):
    """层接口 - 所有层必须实现

    层是系统的核心组件，负责执行特定的业务逻辑。
    每个层应该职责单一，通过协调器进行组合。
    """

    @property
    @abstractmethod
    def layer_name(self) -> str:
        """层名称，用于标识和日志"""
        pass

    @property
    @abstractmethod
    def layer_type(self) -> str:
        """层类型: search | ai | cache | audit 等"""
        pass

    @abstractmethod
    async def execute(self, context: LayerContext) -> LayerResult:
        """执行层逻辑

        Args:
            context: 层执行上下文，包含任务信息和共享数据

        Returns:
            LayerResult: 执行结果
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查

        Returns:
            bool: True 表示健康，False 表示不健康
        """
        pass

    def get_config(self) -> LayerConfig:
        """获取层配置

        子类可以重写此方法返回自定义配置
        """
        return LayerConfig()

    async def initialize(self) -> None:
        """初始化层

        可选实现，用于层启动时的初始化工作
        """
        pass

    async def shutdown(self) -> None:
        """关闭层

        可选实现，用于层关闭时的清理工作
        """
        pass
