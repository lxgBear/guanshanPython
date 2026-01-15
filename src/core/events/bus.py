"""事件总线

提供发布/订阅模式的事件通信机制。
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from .types import BaseEvent

logger = logging.getLogger(__name__)

# 事件处理器类型：同步或异步函数
EventHandler = Callable[[BaseEvent], Union[None, Coroutine[Any, Any, None]]]


class EventBus:
    """事件总线

    支持发布/订阅模式的事件通信。

    使用示例:
        bus = EventBus()

        # 订阅事件
        async def on_search_completed(event: SearchCompletedEvent):
            print(f"Search completed: {event.result_count} results")

        bus.subscribe("SearchCompletedEvent", on_search_completed)

        # 发布事件
        await bus.publish(SearchCompletedEvent(task_id="123", result_count=10))
    """

    _instance: Optional["EventBus"] = None

    def __new__(cls) -> "EventBus":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._background_task: Optional[asyncio.Task] = None
        self._initialized = True

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """订阅事件

        Args:
            event_type: 事件类型名称（类名）
            handler: 事件处理器（同步或异步函数）
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed to {event_type}: {handler.__name__}")

    def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """取消订阅

        Args:
            event_type: 事件类型名称
            handler: 事件处理器
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Unsubscribed from {event_type}: {handler.__name__}")
            except ValueError:
                pass

    async def publish(self, event: BaseEvent) -> None:
        """发布事件

        同步调用所有订阅者，然后将事件放入队列供后台处理。

        Args:
            event: 事件实例
        """
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])

        logger.debug(f"Publishing {event_type} to {len(handlers)} handlers")

        # 同步调用所有处理器
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    f"Event handler error for {event_type}: {e}",
                    exc_info=True
                )

        # 放入队列供后台处理（如持久化、日志等）
        if self._running:
            await self._queue.put(event)

    def publish_sync(self, event: BaseEvent) -> None:
        """同步发布事件（仅放入队列）

        适用于不能使用 await 的场景。

        Args:
            event: 事件实例
        """
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(f"Event queue full, dropping event: {event.event_type}")

    async def start(self) -> None:
        """启动事件总线后台处理"""
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(self._process_events())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """停止事件总线"""
        if not self._running:
            return

        self._running = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        logger.info("EventBus stopped")

    async def _process_events(self) -> None:
        """后台事件处理循环"""
        while self._running:
            try:
                # 使用超时避免永久阻塞
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                # 这里可以添加事件持久化、日志等处理
                logger.debug(f"Processed event: {event.event_type}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}", exc_info=True)

    def get_handlers(self, event_type: str) -> List[EventHandler]:
        """获取事件的所有处理器

        Args:
            event_type: 事件类型名称

        Returns:
            处理器列表
        """
        return self._handlers.get(event_type, [])

    def clear_handlers(self, event_type: Optional[str] = None) -> None:
        """清除处理器

        Args:
            event_type: 事件类型，如果为 None 则清除所有
        """
        if event_type:
            self._handlers.pop(event_type, None)
        else:
            self._handlers.clear()


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
