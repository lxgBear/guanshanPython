"""聊天协调器实现

协调搜索引擎层和AI处理层的执行，支持串行和并行两种模式。

核心职责:
- 管理层的注册和生命周期
- 协调搜索层和AI层的执行
- 支持 wait=true (串行) 和 wait=false (并行) 两种模式
- 处理层间数据传递
- 错误处理和状态更新

执行模式:
- SEQUENTIAL (wait=true): 搜索完成后再执行AI处理
- PARALLEL (wait=false): 搜索和AI处理并行执行，AI层轮询搜索结果
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.core.interfaces.layer import ILayer, LayerContext, LayerResult, LayerStatus
from src.core.interfaces.ai_layer import IAILayer, SSEEvent
from src.core.interfaces.orchestrator import (
    IOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
    LayerExecutionInfo,
    LayerRegistration,
    ExecutionMode,
)
from src.core.events.types import TaskCreatedEvent, LayerExecutionEvent
from src.core.events.bus import get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class ChatOrchestratorConfig(OrchestratorConfig):
    """聊天协调器配置

    扩展基础配置，添加聊天特定的配置项。
    """
    search_layer_name: str = "search_engine"
    ai_layer_name: str = "ai_processing"
    default_mode: ExecutionMode = ExecutionMode.PARALLEL
    search_timeout: float = 300.0
    ai_timeout: float = 300.0
    enable_streaming: bool = True


class ChatOrchestrator(IOrchestrator):
    """聊天协调器

    协调搜索引擎层和AI处理层的执行。

    Example:
        # 创建协调器并注册层
        orchestrator = ChatOrchestrator()
        orchestrator.register_layer(SearchEngineLayer(), priority=1)
        orchestrator.register_layer(AIProcessingLayer(), priority=2, dependencies=["search_engine"])

        # 执行（并行模式）
        context = LayerContext(
            task_id="task_123",
            user_id="user_456",
            query="中美贸易谈判最新进展",
        )
        result = await orchestrator.execute(context, mode=ExecutionMode.PARALLEL)

        # 执行（串行模式）
        result = await orchestrator.execute(context, mode=ExecutionMode.SEQUENTIAL)

        # 流式执行
        async for event in orchestrator.stream(context):
            print(event.to_sse_string())
    """

    def __init__(
        self,
        config: Optional[ChatOrchestratorConfig] = None,
    ):
        """初始化协调器

        Args:
            config: 协调器配置
        """
        self._config = config or ChatOrchestratorConfig()
        self._layers: Dict[str, LayerRegistration] = {}
        self._event_bus = get_event_bus()
        self._initialized = False

    @property
    def config(self) -> ChatOrchestratorConfig:
        """获取配置"""
        return self._config

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
        layer_name = layer.layer_name
        self._layers[layer_name] = LayerRegistration(
            layer=layer,
            priority=priority,
            dependencies=dependencies or [],
            required=required,
        )
        logger.info(
            f"[ChatOrchestrator] Layer registered: {layer_name}, "
            f"priority={priority}, dependencies={dependencies}"
        )

    def unregister_layer(self, layer_name: str) -> None:
        """注销层"""
        if layer_name in self._layers:
            del self._layers[layer_name]
            logger.info(f"[ChatOrchestrator] Layer unregistered: {layer_name}")

    def get_layer(self, layer_name: str) -> Optional[ILayer]:
        """获取层实例"""
        registration = self._layers.get(layer_name)
        return registration.layer if registration else None

    def get_all_layers(self) -> List[ILayer]:
        """获取所有已注册的层"""
        return [reg.layer for reg in self._layers.values()]

    async def initialize(self) -> None:
        """初始化所有层"""
        if self._initialized:
            return

        for layer_name, registration in self._layers.items():
            try:
                await registration.layer.initialize()
                logger.info(f"[ChatOrchestrator] Layer initialized: {layer_name}")
            except Exception as e:
                logger.error(f"[ChatOrchestrator] Layer init failed: {layer_name}, {e}")

        self._initialized = True

    async def shutdown(self) -> None:
        """关闭所有层"""
        for layer_name, registration in self._layers.items():
            try:
                await registration.layer.shutdown()
                logger.info(f"[ChatOrchestrator] Layer shutdown: {layer_name}")
            except Exception as e:
                logger.error(f"[ChatOrchestrator] Layer shutdown failed: {layer_name}, {e}")

        self._initialized = False

    async def health_check(self) -> Dict[str, bool]:
        """健康检查所有层"""
        results = {}
        for layer_name, registration in self._layers.items():
            try:
                results[layer_name] = await registration.layer.health_check()
            except Exception:
                results[layer_name] = False
        return results

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
        started_at = datetime.utcnow()
        task_id = context.task_id

        logger.info(
            f"[ChatOrchestrator] Starting execution: "
            f"task_id={task_id}, mode={mode.value}"
        )

        # 确保层已初始化
        if not self._initialized:
            await self.initialize()

        # 发送任务创建事件
        await self._event_bus.publish(
            TaskCreatedEvent(
                task_id=task_id,
                user_id=context.user_id,
                query=context.query,
                options=context.options,
            )
        )

        layer_results: Dict[str, LayerExecutionInfo] = {}
        errors: List[str] = []

        try:
            if mode == ExecutionMode.SEQUENTIAL:
                # 串行执行：按优先级顺序执行
                layer_results, errors = await self._execute_sequential(context)
            elif mode == ExecutionMode.PARALLEL:
                # 并行执行：搜索和AI处理并行
                layer_results, errors = await self._execute_parallel(context)
            else:
                # 混合模式：当前与并行相同
                layer_results, errors = await self._execute_parallel(context)

            # 计算总时间
            completed_at = datetime.utcnow()
            total_time_ms = int((completed_at - started_at).total_seconds() * 1000)

            # 确定整体状态
            status = self._determine_status(layer_results, errors)

            result = OrchestratorResult(
                task_id=task_id,
                status=status,
                execution_mode=mode,
                layer_results=layer_results,
                total_time_ms=total_time_ms,
                errors=errors,
                started_at=started_at,
                completed_at=completed_at,
            )

            logger.info(
                f"[ChatOrchestrator] Execution completed: "
                f"task_id={task_id}, status={status}, "
                f"total_time={total_time_ms}ms"
            )

            return result

        except Exception as e:
            completed_at = datetime.utcnow()
            total_time_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(
                f"[ChatOrchestrator] Execution failed: "
                f"task_id={task_id}, error={e}"
            )

            return OrchestratorResult(
                task_id=task_id,
                status="failed",
                execution_mode=mode,
                layer_results=layer_results,
                total_time_ms=total_time_ms,
                errors=[str(e)],
                started_at=started_at,
                completed_at=completed_at,
            )

    async def execute_layer(
        self,
        layer_name: str,
        context: LayerContext,
    ) -> LayerResult:
        """执行单个层"""
        registration = self._layers.get(layer_name)
        if not registration:
            raise ValueError(f"Layer not found: {layer_name}")

        layer = registration.layer

        # 确保层已初始化
        if not self._initialized:
            await layer.initialize()

        # 发送层执行开始事件
        await self._event_bus.publish(
            LayerExecutionEvent(
                layer_name=layer_name,
                layer_type=layer.layer_type,
                status="started",
                task_id=context.task_id,
                user_id=context.user_id,
            )
        )

        started_at = datetime.utcnow()

        try:
            result = await layer.execute(context)

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # 发送层执行完成事件
            await self._event_bus.publish(
                LayerExecutionEvent(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="completed",
                    duration_ms=duration_ms,
                    task_id=context.task_id,
                    user_id=context.user_id,
                )
            )

            return result

        except Exception as e:
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # 发送层执行失败事件
            await self._event_bus.publish(
                LayerExecutionEvent(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="failed",
                    duration_ms=duration_ms,
                    task_id=context.task_id,
                    user_id=context.user_id,
                    details={"error": str(e)},
                )
            )

            raise

    async def stream(
        self,
        context: LayerContext,
        mode: ExecutionMode = ExecutionMode.PARALLEL,
    ) -> AsyncGenerator[SSEEvent, None]:
        """流式执行

        支持流式返回AI处理结果。

        Args:
            context: 层执行上下文
            mode: 执行模式

        Yields:
            SSEEvent: SSE 事件流
        """
        task_id = context.task_id

        logger.info(
            f"[ChatOrchestrator] Starting streaming execution: "
            f"task_id={task_id}, mode={mode.value}"
        )

        # 确保层已初始化
        if not self._initialized:
            await self.initialize()

        # 获取搜索层和AI层
        search_layer = self.get_layer(self._config.search_layer_name)
        ai_layer = self.get_layer(self._config.ai_layer_name)

        if not search_layer or not ai_layer:
            yield SSEEvent.error("Required layers not registered", "layer_missing")
            yield SSEEvent.stream_end("error")
            return

        if not isinstance(ai_layer, IAILayer):
            yield SSEEvent.error("AI layer does not support streaming", "invalid_layer")
            yield SSEEvent.stream_end("error")
            return

        try:
            if mode == ExecutionMode.SEQUENTIAL:
                # 串行模式：先搜索，再AI处理
                # 1. 执行搜索
                search_result = await search_layer.execute(context)

                if search_result.status != LayerStatus.COMPLETED:
                    yield SSEEvent.error(
                        f"Search failed: {search_result.error}",
                        "search_failed"
                    )
                    yield SSEEvent.stream_end("error")
                    return

                # 2. 将搜索结果传递给AI层
                context.set_shared("search_results", search_result.data.get("results", []))
                context.set_shared("search_completed", True)
                context.set_shared("search_result_count", search_result.result_count)

                # 3. 流式执行AI处理
                async for event in ai_layer.stream(context):
                    yield event

            else:
                # 并行模式：搜索和AI处理并行启动
                # 启动搜索任务
                search_task = asyncio.create_task(
                    search_layer.execute(context)
                )

                # AI层会轮询等待搜索结果
                async for event in ai_layer.stream(context):
                    yield event

                # 确保搜索任务完成
                try:
                    await asyncio.wait_for(search_task, timeout=self._config.search_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[ChatOrchestrator] Search task timeout: {task_id}")

        except Exception as e:
            logger.error(
                f"[ChatOrchestrator] Streaming failed: task_id={task_id}, error={e}"
            )
            yield SSEEvent.error(str(e), "orchestrator_error")
            yield SSEEvent.stream_end("error")

    async def execute_search_only(
        self,
        context: LayerContext,
    ) -> LayerResult:
        """仅执行搜索层

        用于 skip_summary 模式，只需要搜索结果不需要AI处理。

        Args:
            context: 层执行上下文

        Returns:
            LayerResult: 搜索结果
        """
        search_layer = self.get_layer(self._config.search_layer_name)
        if not search_layer:
            raise ValueError("Search layer not registered")

        return await self.execute_layer(self._config.search_layer_name, context)

    async def execute_ai_only(
        self,
        context: LayerContext,
        search_results: List[Dict[str, Any]],
    ) -> LayerResult:
        """仅执行AI处理层

        用于已有搜索结果的场景。

        Args:
            context: 层执行上下文
            search_results: 搜索结果列表

        Returns:
            LayerResult: AI处理结果
        """
        ai_layer = self.get_layer(self._config.ai_layer_name)
        if not ai_layer:
            raise ValueError("AI layer not registered")

        # 将搜索结果注入上下文
        context.set_shared("search_results", search_results)
        context.set_shared("search_completed", True)
        context.set_shared("search_result_count", len(search_results))

        return await self.execute_layer(self._config.ai_layer_name, context)

    async def _execute_sequential(
        self,
        context: LayerContext,
    ) -> tuple[Dict[str, LayerExecutionInfo], List[str]]:
        """串行执行所有层"""
        layer_results: Dict[str, LayerExecutionInfo] = {}
        errors: List[str] = []

        # 按优先级排序
        sorted_layers = sorted(
            self._layers.items(),
            key=lambda x: x[1].priority
        )

        for layer_name, registration in sorted_layers:
            layer = registration.layer
            started_at = datetime.utcnow()

            try:
                result = await layer.execute(context)

                completed_at = datetime.utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                layer_results[layer_name] = LayerExecutionInfo(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="completed" if result.status == LayerStatus.COMPLETED else "failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    error=result.error,
                    result=result,
                )

                # 如果是必需层且失败，记录错误
                if registration.required and result.status != LayerStatus.COMPLETED:
                    errors.append(f"{layer_name}: {result.error}")
                    if self._config.skip_on_error:
                        break

            except Exception as e:
                completed_at = datetime.utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                layer_results[layer_name] = LayerExecutionInfo(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    error=str(e),
                )

                if registration.required:
                    errors.append(f"{layer_name}: {str(e)}")
                    if self._config.skip_on_error:
                        break

        return layer_results, errors

    async def _execute_parallel(
        self,
        context: LayerContext,
    ) -> tuple[Dict[str, LayerExecutionInfo], List[str]]:
        """并行执行搜索和AI处理层"""
        layer_results: Dict[str, LayerExecutionInfo] = {}
        errors: List[str] = []

        search_layer = self.get_layer(self._config.search_layer_name)
        ai_layer = self.get_layer(self._config.ai_layer_name)

        if not search_layer:
            errors.append("Search layer not registered")
            return layer_results, errors

        if not ai_layer:
            errors.append("AI layer not registered")
            return layer_results, errors

        # 并行启动搜索和AI处理
        async def execute_with_info(
            layer: ILayer,
            layer_name: str,
        ) -> LayerExecutionInfo:
            started_at = datetime.utcnow()
            try:
                result = await layer.execute(context)
                completed_at = datetime.utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                return LayerExecutionInfo(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="completed" if result.status == LayerStatus.COMPLETED else "failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    error=result.error,
                    result=result,
                )
            except Exception as e:
                completed_at = datetime.utcnow()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                return LayerExecutionInfo(
                    layer_name=layer_name,
                    layer_type=layer.layer_type,
                    status="failed",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    error=str(e),
                )

        # 创建并行任务
        search_task = asyncio.create_task(
            execute_with_info(search_layer, self._config.search_layer_name)
        )
        ai_task = asyncio.create_task(
            execute_with_info(ai_layer, self._config.ai_layer_name)
        )

        # 等待所有任务完成
        results = await asyncio.gather(search_task, ai_task, return_exceptions=True)

        for result in results:
            if isinstance(result, LayerExecutionInfo):
                layer_results[result.layer_name] = result
                if result.status == "failed" and result.error:
                    errors.append(f"{result.layer_name}: {result.error}")
            elif isinstance(result, Exception):
                errors.append(str(result))

        return layer_results, errors

    def _determine_status(
        self,
        layer_results: Dict[str, LayerExecutionInfo],
        errors: List[str],
    ) -> str:
        """确定整体执行状态"""
        if not errors:
            return "completed"

        # 检查是否所有必需层都成功
        all_required_success = True
        for layer_name, registration in self._layers.items():
            if registration.required:
                info = layer_results.get(layer_name)
                if not info or info.status != "completed":
                    all_required_success = False
                    break

        if all_required_success:
            return "partial"  # 部分成功（非必需层失败）
        else:
            return "failed"
