"""AI处理层实现

封装远程AI服务调用，提供职责单一的AI处理层。

职责:
- 从 langgraph_search_results 读取搜索结果
- 获取对话历史
- 调用远程 AI 服务
- 解析并转发 SSE 流
- 保存聊天记录

不负责:
- 执行搜索
- 管理搜索工作流
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from src.core.interfaces.layer import LayerConfig, LayerContext, LayerStatus
from src.core.interfaces.ai_layer import (
    IAILayer,
    AILayerResult,
    SSEEvent,
    SSEEventType,
)
from src.core.events.types import (
    AIProcessingStartedEvent,
    AIProcessingCompletedEvent,
)
from src.core.events.bus import get_event_bus

logger = logging.getLogger(__name__)

# 默认配置 (支持环境变量覆盖)
DEFAULT_AI_SERVICE_URL = os.getenv("LAYER_AI_SERVICE_URL", "http://localhost:8035/chat")
DEFAULT_AI_SERVICE_TIMEOUT = 300.0
DEFAULT_SEARCH_POLL_INTERVAL = 1.0
DEFAULT_SEARCH_POLL_MAX_RETRIES = 300


class AIProcessingLayerConfig(LayerConfig):
    """AI处理层配置"""
    ai_service_url: str = DEFAULT_AI_SERVICE_URL
    ai_service_timeout: float = DEFAULT_AI_SERVICE_TIMEOUT
    search_poll_interval: float = DEFAULT_SEARCH_POLL_INTERVAL
    search_poll_max_retries: int = DEFAULT_SEARCH_POLL_MAX_RETRIES
    save_history: bool = True
    enhance_sources: bool = True


class AIProcessingLayer(IAILayer):
    """AI处理层

    封装远程AI服务调用，提供统一的AI处理接口。

    Example:
        layer = AIProcessingLayer()
        context = LayerContext(
            task_id="task_123",
            user_id="user_456",
            query="中美贸易谈判最新进展",
        )

        # 非流式调用
        result = await layer.execute(context)

        # 流式调用
        async for event in layer.stream(context):
            print(event.to_sse_string())
    """

    def __init__(
        self,
        config: Optional[AIProcessingLayerConfig] = None,
        result_repository: Optional[Any] = None,
        history_service: Optional[Any] = None,
    ):
        """初始化AI处理层

        Args:
            config: 层配置
            result_repository: 搜索结果仓储实例
            history_service: 历史记录服务实例
        """
        self._config = config or AIProcessingLayerConfig()
        self._result_repository = result_repository
        self._history_service = history_service
        self._event_bus = get_event_bus()
        self._db = None

    @property
    def layer_name(self) -> str:
        return "ai_processing"

    @property
    def layer_type(self) -> str:
        return "ai"

    def get_config(self) -> LayerConfig:
        return self._config

    async def initialize(self) -> None:
        """初始化层"""
        # 延迟导入，避免循环依赖
        if self._result_repository is None:
            from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
                MongoLangGraphResultRepository
            )
            self._result_repository = MongoLangGraphResultRepository()

        if self._history_service is None:
            try:
                from src.services.nl_search.search_history_service import search_history_service
                self._history_service = search_history_service
            except ImportError:
                logger.warning("SearchHistoryService not available")

        if self._db is None:
            from src.infrastructure.database.connection import get_mongodb_database
            self._db = await get_mongodb_database()

        logger.info(
            f"AIProcessingLayer initialized with service: {self._config.ai_service_url}"
        )

    async def shutdown(self) -> None:
        """关闭层"""
        logger.info("AIProcessingLayer shutdown")

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    self._config.ai_service_url.replace("/chat", "/health")
                )
                return response.status_code == 200
        except Exception:
            return False

    async def execute(self, context: LayerContext) -> AILayerResult:
        """执行AI处理（非流式）

        Args:
            context: 层执行上下文

        Returns:
            AILayerResult: AI处理结果
        """
        started_at = datetime.utcnow()
        task_id = context.task_id
        user_id = context.user_id
        query = context.query

        logger.info(
            f"[AIProcessingLayer] Starting AI processing: "
            f"task_id={task_id}, user_id={user_id}, query={query[:50]}..."
        )

        # 发送AI处理开始事件
        await self._event_bus.publish(
            AIProcessingStartedEvent(
                task_id=task_id,
                user_id=user_id,
                has_search_results=context.get_shared("search_completed", False),
                search_result_count=context.get_shared("search_result_count", 0),
            )
        )

        try:
            # 获取搜索结果
            search_results = await self._get_search_results(context)

            # 获取对话历史
            conversation_history = await self._get_conversation_history(context)

            # 调用远程AI服务
            ai_result = await self._call_ai_service(
                query=query,
                search_results=search_results,
                user_id=user_id,
                task_id=task_id,
                history=conversation_history,
            )

            # 增强来源数据
            enhanced_sources = []
            if self._config.enhance_sources:
                enhanced_sources = await self._enhance_sources(
                    ai_result.get("sources", [])
                )
            else:
                enhanced_sources = ai_result.get("sources", [])

            # 保存历史记录
            history_id = None
            if self._config.save_history and self._history_service:
                history_id = await self._save_history(
                    context=context,
                    answer=ai_result.get("answer", ""),
                    sources=enhanced_sources,
                )

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            # 发送AI处理完成事件
            await self._event_bus.publish(
                AIProcessingCompletedEvent(
                    task_id=task_id,
                    user_id=user_id,
                    duration_ms=duration_ms,
                    answer_length=len(ai_result.get("answer", "")),
                    source_count=len(enhanced_sources),
                )
            )

            # 更新共享数据
            context.set_shared("ai_completed", True)
            context.set_shared("history_id", history_id)

            logger.info(
                f"[AIProcessingLayer] AI processing completed: "
                f"task_id={task_id}, answer_length={len(ai_result.get('answer', ''))}, "
                f"sources={len(enhanced_sources)}, duration={duration_ms}ms"
            )

            return AILayerResult(
                status=LayerStatus.COMPLETED,
                answer=ai_result.get("answer", ""),
                sources=enhanced_sources,
                conversation_id=context.options.get("conversation_id"),
                started_at=started_at,
                completed_at=completed_at,
                task_id=task_id,
                data={
                    "history_id": history_id,
                    "search_result_count": len(search_results),
                },
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(
                f"[AIProcessingLayer] AI processing failed: "
                f"task_id={task_id}, error={e}"
            )

            return AILayerResult(
                status=LayerStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                task_id=task_id,
            )

    async def stream(
        self,
        context: LayerContext,
    ) -> AsyncGenerator[SSEEvent, None]:
        """流式执行AI处理

        Args:
            context: 层执行上下文

        Yields:
            SSEEvent: SSE 事件流
        """
        task_id = context.task_id
        user_id = context.user_id
        query = context.query

        logger.info(
            f"[AIProcessingLayer] Starting streaming AI processing: "
            f"task_id={task_id}, user_id={user_id}"
        )

        # 发送流开始事件
        yield SSEEvent.stream_start()

        try:
            # 获取搜索结果
            search_results = await self._get_search_results(context)

            # 获取对话历史
            conversation_history = await self._get_conversation_history(context)

            # 流式调用远程AI服务
            answer_chunks = []
            ai_sources = []

            async for event in self._stream_ai_service(
                query=query,
                search_results=search_results,
                user_id=user_id,
                task_id=task_id,
                history=conversation_history,
            ):
                # 收集数据用于后续处理
                if event.event_type == SSEEventType.CHUNK:
                    answer_chunks.append(event.data.get("content", ""))
                elif event.event_type == SSEEventType.SOURCE:
                    ai_sources = event.data.get("sources", [])

                # 转发事件
                yield event

            # 增强来源数据
            enhanced_sources = []
            if self._config.enhance_sources and ai_sources:
                enhanced_sources = await self._enhance_sources(ai_sources)
            else:
                enhanced_sources = ai_sources

            # 发送增强后的来源
            if enhanced_sources:
                yield SSEEvent.source(enhanced_sources)

            # 保存历史记录
            if self._config.save_history and self._history_service:
                full_answer = "".join(answer_chunks)
                await self._save_history(
                    context=context,
                    answer=full_answer,
                    sources=enhanced_sources,
                )

            # 发送流结束事件
            yield SSEEvent.stream_end("success")

            logger.info(
                f"[AIProcessingLayer] Streaming completed: "
                f"task_id={task_id}, answer_length={len(''.join(answer_chunks))}, "
                f"sources={len(enhanced_sources)}"
            )

        except Exception as e:
            logger.error(
                f"[AIProcessingLayer] Streaming failed: "
                f"task_id={task_id}, error={e}"
            )
            yield SSEEvent.error(str(e), "ai_processing_error")
            yield SSEEvent.stream_end("error")

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
        if self._result_repository is None:
            await self.initialize()

        start_time = datetime.utcnow()
        poll_interval = self._config.search_poll_interval
        max_retries = self._config.search_poll_max_retries

        for retry in range(max_retries):
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(
                    f"[AIProcessingLayer] Search results timeout: "
                    f"task_id={task_id}, elapsed={elapsed:.1f}s"
                )
                return None

            # 查询搜索结果
            try:
                result = await self._result_repository.find_by_task_id(task_id)
                if result and result.get("status") == "completed":
                    logger.info(
                        f"[AIProcessingLayer] Search results ready: "
                        f"task_id={task_id}, results={len(result.get('results', []))}"
                    )
                    return result.get("results", [])
            except Exception as e:
                logger.warning(
                    f"[AIProcessingLayer] Error polling search results: {e}"
                )

            # 等待下次轮询
            await asyncio.sleep(poll_interval)

        logger.warning(
            f"[AIProcessingLayer] Max retries reached: task_id={task_id}"
        )
        return None

    async def _get_search_results(
        self,
        context: LayerContext,
    ) -> List[Dict[str, Any]]:
        """获取搜索结果

        优先从共享数据获取，否则从数据库查询。
        """
        # 检查是否有直接传入的搜索结果
        search_results = context.options.get("search_results")
        if search_results:
            return search_results

        # 检查共享数据中是否有搜索结果
        if context.get_shared("search_results"):
            return context.get_shared("search_results")

        # 从数据库查询
        if self._result_repository:
            result = await self._result_repository.find_by_task_id(context.task_id)
            if result:
                return result.get("results", [])

        return []

    async def _get_conversation_history(
        self,
        context: LayerContext,
    ) -> List[Dict[str, Any]]:
        """获取对话历史"""
        conversation_id = context.options.get("conversation_id")
        if not conversation_id:
            return []

        # 从共享数据获取
        if context.get_shared("conversation_history"):
            return context.get_shared("conversation_history")

        # 从数据库查询
        if self._history_service:
            try:
                history = await self._history_service.get_conversation_history(
                    conversation_id=conversation_id,
                    limit=10,
                )
                return history or []
            except Exception as e:
                logger.warning(f"Failed to get conversation history: {e}")

        return []

    async def _call_ai_service(
        self,
        query: str,
        search_results: List[Dict],
        user_id: str,
        task_id: str,
        history: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """调用远程AI服务（非流式）"""
        try:
            async with httpx.AsyncClient(
                timeout=self._config.ai_service_timeout
            ) as client:
                request_data = {
                    "question": query,
                    "search_results": search_results,
                    "user_id": user_id,
                    "log_id": task_id,
                }

                if history:
                    request_data["history"] = history

                async with client.stream(
                    "POST",
                    self._config.ai_service_url,
                    json=request_data,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(
                            f"AI service error: {response.status_code}, "
                            f"{error_text.decode()[:200]}"
                        )

                    # 解析 SSE 流
                    answer_chunks = []
                    ai_sources = []

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type")

                            if event_type == "answer_chunk":
                                answer_chunks.append(event_data.get("data", ""))
                            elif event_type == "sources":
                                ai_sources = event_data.get("data", [])
                            elif event_type == "stream_end":
                                logger.debug("AI SSE stream ended")

                        except json.JSONDecodeError:
                            continue

                    return {
                        "answer": "".join(answer_chunks),
                        "sources": ai_sources,
                    }

        except httpx.TimeoutException:
            raise Exception(
                f"AI service timeout ({self._config.ai_service_timeout}s)"
            )
        except httpx.RequestError as e:
            raise Exception(f"AI service request failed: {str(e)}")

    async def _stream_ai_service(
        self,
        query: str,
        search_results: List[Dict],
        user_id: str,
        task_id: str,
        history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """流式调用远程AI服务"""
        try:
            async with httpx.AsyncClient(
                timeout=self._config.ai_service_timeout
            ) as client:
                request_data = {
                    "question": query,
                    "search_results": search_results,
                    "user_id": user_id,
                    "log_id": task_id,
                }

                if history:
                    request_data["history"] = history

                async with client.stream(
                    "POST",
                    self._config.ai_service_url,
                    json=request_data,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield SSEEvent.error(
                            f"AI service error: {response.status_code}",
                            "ai_service_error"
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type")

                            if event_type == "answer_chunk":
                                yield SSEEvent.chunk(event_data.get("data", ""))
                            elif event_type == "sources":
                                yield SSEEvent.source(event_data.get("data", []))
                            elif event_type == "stream_end":
                                pass  # 由调用者处理流结束

                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            yield SSEEvent.error(
                f"AI service timeout ({self._config.ai_service_timeout}s)",
                "timeout"
            )
        except httpx.RequestError as e:
            yield SSEEvent.error(f"AI service request failed: {str(e)}", "request_error")

    async def _enhance_sources(
        self,
        sources: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """增强来源数据（从MongoDB获取完整信息）"""
        if not sources:
            return []

        if self._db is None:
            await self.initialize()

        from bson import ObjectId

        enhanced = []
        seen_ids = set()

        # 去重
        unique_sources = []
        for s in sources:
            mongo_id = s.get("mongo_id")
            if mongo_id and mongo_id not in seen_ids:
                seen_ids.add(mongo_id)
                unique_sources.append(s)

        for source in unique_sources:
            mongo_id = source.get("mongo_id")
            source_type = source.get("source", "")

            if not mongo_id:
                continue

            # 处理默认 category
            category = source.get("category", {})
            if not category or not all(k in category for k in ["大类", "类别", "地域"]):
                category = {"大类": "未分类", "类别": "未分类", "地域": "未知"}

            enhanced_source = {
                "id": source.get("id", ""),
                "mongo_id": mongo_id,
                "title": source.get("title", ""),
                "source": source_type,
                "score": source.get("score", 0.0),
                "category": category,
                "publish_time": source.get("publish_time", "未知时间"),
                "preview": source.get("preview", ""),
            }

            # 根据来源类型查询不同集合
            try:
                if source_type == "用户上传":
                    file_result = await self._db["file_uploads"].find_one(
                        {"_id": ObjectId(mongo_id)},
                        {"title": 1, "content": 1, "storage_url": 1, "_id": 0}
                    )
                    if file_result:
                        enhanced_source["url"] = file_result.get("storage_url")
                        enhanced_source["title_zh"] = file_result.get("title")
                        enhanced_source["content_zh"] = file_result.get("content")
                else:
                    news_result = await self._db["news_results"].find_one(
                        {"_id": mongo_id},
                        {
                            "url": 1,
                            "news_results.title_zh": 1,
                            "news_results.summary_zh": 1,
                            "news_results.content_zh": 1,
                            "_id": 0
                        }
                    )
                    if news_result:
                        enhanced_source["url"] = news_result.get("url")
                        nested = news_result.get("news_results", {})
                        enhanced_source["title_zh"] = nested.get("title_zh")
                        enhanced_source["summary_zh"] = nested.get("summary_zh")
                        enhanced_source["content_zh"] = nested.get("content_zh")

            except Exception as e:
                logger.warning(
                    f"Failed to enhance source: mongo_id={mongo_id}, error={e}"
                )

            enhanced.append(enhanced_source)

        return enhanced

    async def _save_history(
        self,
        context: LayerContext,
        answer: str,
        sources: List[Dict[str, Any]],
    ) -> Optional[str]:
        """保存历史记录"""
        if not self._history_service:
            return None

        try:
            sources_for_history = [
                {
                    "mongo_id": s.get("mongo_id"),
                    "source": s.get("source", ""),
                    "title": s.get("title", ""),
                    "score": s.get("score", 0),
                    "category": s.get("category", {}),
                    "publish_time": s.get("publish_time", ""),
                    "preview": (s.get("preview") or "")[:200],
                }
                for s in sources
            ]

            history_id = await self._history_service.save_from_sync_response(
                user_id=int(context.user_id) if context.user_id.isdigit() else 0,
                question=context.query,
                answer=answer,
                sources=sources_for_history,
                conversation_id=context.options.get("conversation_id"),
                search_mode=context.options.get("search_mode", "single"),
            )

            logger.info(
                f"[AIProcessingLayer] History saved: "
                f"task_id={context.task_id}, history_id={history_id}"
            )
            return history_id

        except Exception as e:
            logger.warning(f"Failed to save history: {e}")
            return None
