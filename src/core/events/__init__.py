"""事件系统模块

提供事件定义和事件总线，用于层间解耦通信。
"""

from .types import (
    BaseEvent,
    TaskCreatedEvent,
    SearchStartedEvent,
    SearchCompletedEvent,
    SearchFailedEvent,
    AIProcessingStartedEvent,
    AIProcessingCompletedEvent,
    LayerExecutionEvent,
)
from .bus import EventBus

__all__ = [
    # 事件类型
    "BaseEvent",
    "TaskCreatedEvent",
    "SearchStartedEvent",
    "SearchCompletedEvent",
    "SearchFailedEvent",
    "AIProcessingStartedEvent",
    "AIProcessingCompletedEvent",
    "LayerExecutionEvent",
    # 事件总线
    "EventBus",
]
