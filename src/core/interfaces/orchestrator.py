"""协调器接口定义

定义层协调器的接口，负责管理和协调多个层的执行。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from enum import Enum

from .layer import ILayer, LayerContext, LayerResult


class ExecutionMode(str, Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"      # 并行执行
    HYBRID = "hybrid"          # 混合模式


@dataclass
class OrchestratorConfig:
    """协调器配置

    Attributes:
        parallel_execution: 是否启用并行执行
        max_concurrent_layers: 最大并发层数
        global_timeout: 全局超时时间（秒）
        retry_failed_layers: 是否重试失败的层
        skip_on_error: 是否在错误时跳过后续层
    """
    parallel_execution: bool = True
    max_concurrent_layers: int = 5
    global_timeout: int = 600
    retry_failed_layers: bool = True
    skip_on_error: bool = False


@dataclass
class LayerExecutionInfo:
    """层执行信息"""
    layer_name: str
    layer_type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    result: Optional[LayerResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class OrchestratorResult:
    """协调器执行结果

    Attributes:
        task_id: 任务ID
        status: 整体状态
        execution_mode: 执行模式
        layer_results: 各层执行结果
        total_time_ms: 总执行时间
        errors: 错误列表
    """
    task_id: str
    status: str  # "completed" | "partial" | "failed"
    execution_mode: ExecutionMode
    layer_results: Dict[str, LayerExecutionInfo] = field(default_factory=dict)
    total_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def is_success(self) -> bool:
        """是否全部成功"""
        return self.status == "completed"

    @property
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def get_layer_result(self, layer_name: str) -> Optional[LayerExecutionInfo]:
        """获取指定层的结果"""
        return self.layer_results.get(layer_name)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "execution_mode": self.execution_mode.value,
            "layer_results": {
                name: info.to_dict()
                for name, info in self.layer_results.items()
            },
            "total_time_ms": self.total_time_ms,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class LayerRegistration:
    """层注册信息"""
    layer: ILayer
    priority: int = 0  # 优先级，越小越先执行
    dependencies: List[str] = field(default_factory=list)  # 依赖的层名称
    required: bool = True  # 是否必须成功


class IOrchestrator(ABC):
    """协调器接口

    协调器负责:
    1. 管理层的注册和生命周期
    2. 协调层的执行顺序和并行策略
    3. 处理层间依赖和数据传递
    4. 错误处理和重试逻辑
    """

    @abstractmethod
    def register_layer(
        self,
        layer: ILayer,
        priority: int = 0,
        dependencies: Optional[List[str]] = None,
        required: bool = True,
    ) -> None:
        """注册层

        Args:
            layer: 层实例
            priority: 优先级（越小越先执行）
            dependencies: 依赖的层名称列表
            required: 是否必须成功
        """
        pass

    @abstractmethod
    def unregister_layer(self, layer_name: str) -> None:
        """注销层

        Args:
            layer_name: 层名称
        """
        pass

    @abstractmethod
    async def execute(
        self,
        context: LayerContext,
        mode: ExecutionMode = ExecutionMode.PARALLEL,
    ) -> OrchestratorResult:
        """执行所有已注册的层

        Args:
            context: 层执行上下文
            mode: 执行模式

        Returns:
            OrchestratorResult: 执行结果
        """
        pass

    @abstractmethod
    async def execute_layer(
        self,
        layer_name: str,
        context: LayerContext,
    ) -> LayerResult:
        """执行单个层

        Args:
            layer_name: 层名称
            context: 层执行上下文

        Returns:
            LayerResult: 层执行结果
        """
        pass

    @abstractmethod
    def get_layer(self, layer_name: str) -> Optional[ILayer]:
        """获取层实例

        Args:
            layer_name: 层名称

        Returns:
            层实例，如果不存在返回 None
        """
        pass

    @abstractmethod
    def get_all_layers(self) -> List[ILayer]:
        """获取所有已注册的层"""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, bool]:
        """健康检查所有层

        Returns:
            Dict[层名称, 是否健康]
        """
        pass
