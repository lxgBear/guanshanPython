"""核心接口模块

定义系统中所有层和组件的抽象接口。
"""

from .layer import (
    ILayer,
    LayerConfig,
    LayerContext,
    LayerResult,
    LayerStatus,
)
from .search_layer import (
    ISearchLayer,
    SearchLayerResult,
    SearchResultItem,
    SearchStatistics,
)
from .ai_layer import (
    IAILayer,
    AILayerResult,
    SSEEvent,
    SSEEventType,
)
from .orchestrator import (
    IOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
    ExecutionMode,
    LayerExecutionInfo,
)

__all__ = [
    # 基础层接口
    "ILayer",
    "LayerConfig",
    "LayerContext",
    "LayerResult",
    "LayerStatus",
    # 搜索层接口
    "ISearchLayer",
    "SearchLayerResult",
    "SearchResultItem",
    "SearchStatistics",
    # AI层接口
    "IAILayer",
    "AILayerResult",
    "SSEEvent",
    "SSEEventType",
    # 协调器接口
    "IOrchestrator",
    "OrchestratorConfig",
    "OrchestratorResult",
    "ExecutionMode",
    "LayerExecutionInfo",
]
