"""AI处理层接口定义

定义AI处理层的专用接口和数据模型。
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from enum import Enum

from .layer import ILayer, LayerContext, LayerResult, LayerStatus


class SSEEventType(str, Enum):
    """SSE 事件类型"""
    CHUNK = "chunk"           # 文本块
    SOURCE = "source"         # 来源引用
    STREAM_START = "stream_start"  # 流开始
    STREAM_END = "stream_end"      # 流结束
    ERROR = "error"           # 错误
    HEARTBEAT = "heartbeat"   # 心跳


@dataclass
class SSEEvent:
    """SSE 事件

    Attributes:
        event_type: 事件类型
        data: 事件数据
        timestamp: 时间戳
        event_id: 事件ID（可选）
    """
    event_type: SSEEventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: Optional[str] = None

    def to_sse_string(self) -> str:
        """转换为 SSE 格式字符串"""
        import json
        event_data = {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.event_id:
            event_data["id"] = self.event_id
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSEEvent":
        """从字典创建"""
        event_type_str = data.get("type") or data.get("event_type", "chunk")
        try:
            event_type = SSEEventType(event_type_str)
        except ValueError:
            event_type = SSEEventType.CHUNK

        return cls(
            event_type=event_type,
            data=data.get("data", {}),
            event_id=data.get("id") or data.get("event_id"),
        )

    @classmethod
    def chunk(cls, content: str) -> "SSEEvent":
        """创建文本块事件"""
        return cls(
            event_type=SSEEventType.CHUNK,
            data={"content": content},
        )

    @classmethod
    def source(cls, sources: List[Dict]) -> "SSEEvent":
        """创建来源事件"""
        return cls(
            event_type=SSEEventType.SOURCE,
            data={"sources": sources},
        )

    @classmethod
    def stream_start(cls) -> "SSEEvent":
        """创建流开始事件"""
        return cls(
            event_type=SSEEventType.STREAM_START,
            data={"status": "started"},
        )

    @classmethod
    def stream_end(cls, status: str = "success") -> "SSEEvent":
        """创建流结束事件"""
        return cls(
            event_type=SSEEventType.STREAM_END,
            data={"status": status},
        )

    @classmethod
    def error(cls, message: str, code: str = "unknown") -> "SSEEvent":
        """创建错误事件"""
        return cls(
            event_type=SSEEventType.ERROR,
            data={"message": message, "code": code},
        )


@dataclass
class AILayerResult(LayerResult):
    """AI处理层结果

    继承自 LayerResult，添加AI处理特有的字段。
    """
    answer: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    conversation_id: Optional[str] = None
    token_usage: Dict[str, int] = field(default_factory=dict)
    task_id: str = ""  # 关联的任务ID

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        base = super().to_dict()
        base.update({
            "answer": self.answer,
            "sources": self.sources,
            "conversation_id": self.conversation_id,
            "token_usage": self.token_usage,
            "task_id": self.task_id,
        })
        return base


class IAILayer(ILayer):
    """AI处理层接口

    AI处理层负责:
    1. 从 langgraph_search_results 读取搜索结果
    2. 获取对话历史
    3. 调用远程 AI 服务
    4. 解析并转发 SSE 流
    5. 保存聊天记录

    AI处理层不负责:
    - 执行搜索
    - 管理搜索工作流
    """

    @property
    def layer_type(self) -> str:
        return "ai"

    @abstractmethod
    async def execute(self, context: LayerContext) -> AILayerResult:
        """执行 AI 处理（非流式）

        Args:
            context: 层执行上下文

        Returns:
            AILayerResult: AI处理结果
        """
        pass

    @abstractmethod
    async def stream(
        self,
        context: LayerContext,
    ) -> AsyncGenerator[SSEEvent, None]:
        """流式执行 AI 处理

        Args:
            context: 层执行上下文

        Yields:
            SSEEvent: SSE 事件流
        """
        pass

    @abstractmethod
    async def wait_for_search_results(
        self,
        task_id: str,
        timeout: float = 300.0,
    ) -> Optional[List[Dict[str, Any]]]:
        """等待搜索结果完成

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）

        Returns:
            搜索结果列表，如果超时或失败返回 None
        """
        pass
