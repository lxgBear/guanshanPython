"""事件类型定义

定义系统中使用的各种事件类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class BaseEvent:
    """事件基类

    所有事件都应该继承此类。
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """事件类型名称"""
        return self.__class__.__name__

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TaskCreatedEvent(BaseEvent):
    """任务创建事件"""
    task_id: str = ""
    user_id: str = ""
    query: str = ""
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "query": self.query,
            "options": self.options,
        })
        return base


@dataclass
class SearchStartedEvent(BaseEvent):
    """搜索开始事件"""
    task_id: str = ""
    user_id: str = ""
    search_engine: str = ""  # "langgraph" | "nl_search"
    query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "search_engine": self.search_engine,
            "query": self.query,
        })
        return base


@dataclass
class SearchCompletedEvent(BaseEvent):
    """搜索完成事件

    AI处理层监听此事件以获取搜索结果。
    """
    task_id: str = ""
    user_id: str = ""
    result_count: int = 0
    duration_ms: int = 0
    search_engine: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "result_count": self.result_count,
            "duration_ms": self.duration_ms,
            "search_engine": self.search_engine,
        })
        return base


@dataclass
class SearchFailedEvent(BaseEvent):
    """搜索失败事件"""
    task_id: str = ""
    user_id: str = ""
    error: str = ""
    error_code: str = ""
    search_engine: str = ""

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "error": self.error,
            "error_code": self.error_code,
            "search_engine": self.search_engine,
        })
        return base


@dataclass
class AIProcessingStartedEvent(BaseEvent):
    """AI 处理开始事件"""
    task_id: str = ""
    user_id: str = ""
    has_search_results: bool = False
    search_result_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "has_search_results": self.has_search_results,
            "search_result_count": self.search_result_count,
        })
        return base


@dataclass
class AIProcessingCompletedEvent(BaseEvent):
    """AI 处理完成事件"""
    task_id: str = ""
    user_id: str = ""
    duration_ms: int = 0
    answer_length: int = 0
    source_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "task_id": self.task_id,
            "user_id": self.user_id,
            "duration_ms": self.duration_ms,
            "answer_length": self.answer_length,
            "source_count": self.source_count,
        })
        return base


@dataclass
class LayerExecutionEvent(BaseEvent):
    """层执行事件

    用于监控和审计层的执行情况。
    """
    layer_name: str = ""
    layer_type: str = ""
    status: str = ""  # "started" | "completed" | "failed"
    duration_ms: int = 0
    task_id: str = ""
    user_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "details": self.details,
        })
        return base
