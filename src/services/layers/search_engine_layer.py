"""搜索引擎层实现

封装 LangGraph 搜索服务，提供职责单一的搜索层。

职责:
- 执行搜索查询（LangGraph 或 NL Search）
- 将结果保存到 langgraph_search_results 集合
- 发送搜索完成事件

不负责:
- 调用 AI 服务
- 处理对话历史
- 推送到前端
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.interfaces.layer import LayerConfig, LayerContext, LayerStatus
from src.core.interfaces.search_layer import (
    ISearchLayer,
    SearchLayerResult,
    SearchResultItem,
    SearchStatistics,
)
from src.core.events.types import (
    SearchStartedEvent,
    SearchCompletedEvent,
    SearchFailedEvent,
)
from src.core.events.bus import get_event_bus

logger = logging.getLogger(__name__)


class SearchEngineLayerConfig(LayerConfig):
    """搜索引擎层配置"""
    search_engine: str = "langgraph"  # "langgraph" | "nl_search"
    fallback_engine: str = "nl_search"
    enable_fallback: bool = True
    max_results: int = 100
    save_to_db: bool = True


class SearchEngineLayer(ISearchLayer):
    """搜索引擎层

    封装 LangGraph 或 NL Search 搜索服务，提供统一的搜索接口。

    Example:
        layer = SearchEngineLayer()
        context = LayerContext(
            task_id="task_123",
            user_id="user_456",
            query="中美贸易谈判最新进展",
        )
        result = await layer.execute(context)
    """

    def __init__(
        self,
        config: Optional[SearchEngineLayerConfig] = None,
        langgraph_service: Optional[Any] = None,
        nl_search_service: Optional[Any] = None,
        result_repository: Optional[Any] = None,
    ):
        """初始化搜索引擎层

        Args:
            config: 层配置
            langgraph_service: LangGraph 搜索服务实例
            nl_search_service: NL Search 服务实例
            result_repository: 结果仓储实例
        """
        self._config = config or SearchEngineLayerConfig()
        self._langgraph_service = langgraph_service
        self._nl_search_service = nl_search_service
        self._result_repository = result_repository
        self._event_bus = get_event_bus()

    @property
    def layer_name(self) -> str:
        return "search_engine"

    @property
    def layer_type(self) -> str:
        return "search"

    def get_config(self) -> LayerConfig:
        return self._config

    async def initialize(self) -> None:
        """初始化层"""
        from src.config import settings
        from firecrawl import Firecrawl

        # 延迟导入，避免循环依赖
        if self._langgraph_service is None:
            from src.services.langgraph_search.service import LangGraphSearchService

            # 初始化 Firecrawl 客户端并传递给 LangGraphSearchService
            firecrawl_client = None
            if settings.FIRECRAWL_API_KEY:
                try:
                    firecrawl_client = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)
                    logger.info("Firecrawl 客户端初始化成功")
                except Exception as e:
                    logger.warning(f"Firecrawl 客户端初始化失败: {e}")

            self._langgraph_service = LangGraphSearchService(
                firecrawl_client=firecrawl_client
            )

        if self._nl_search_service is None:
            try:
                from src.services.nl_search.nl_search_service import NLSearchService
                self._nl_search_service = NLSearchService()
            except ImportError:
                logger.warning("NLSearchService not available")

        if self._result_repository is None:
            from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
                MongoLangGraphResultRepository
            )
            self._result_repository = MongoLangGraphResultRepository()

        logger.info(f"SearchEngineLayer initialized with engine: {self._config.search_engine}")

    async def shutdown(self) -> None:
        """关闭层"""
        logger.info("SearchEngineLayer shutdown")

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 简单检查服务是否可用
            if self._config.search_engine == "langgraph":
                return self._langgraph_service is not None
            else:
                return self._nl_search_service is not None
        except Exception:
            return False

    async def execute(self, context: LayerContext) -> SearchLayerResult:
        """执行搜索

        Args:
            context: 层执行上下文

        Returns:
            SearchLayerResult: 搜索结果
        """
        started_at = datetime.utcnow()
        task_id = context.task_id
        user_id = context.user_id
        query = context.query

        logger.info(
            f"[SearchEngineLayer] Starting search: "
            f"task_id={task_id}, user_id={user_id}, query={query[:50]}..."
        )

        # 发送搜索开始事件
        await self._event_bus.publish(
            SearchStartedEvent(
                task_id=task_id,
                user_id=user_id,
                query=query,
                search_engine=self._config.search_engine,
            )
        )

        try:
            # 执行搜索
            if self._config.search_engine == "langgraph":
                result = await self._execute_langgraph_search(context)
            else:
                result = await self._execute_nl_search(context)

            # 如果主搜索失败且启用回退
            if not result.is_success and self._config.enable_fallback:
                logger.warning(
                    f"[SearchEngineLayer] Primary search failed, trying fallback"
                )
                if self._config.search_engine == "langgraph":
                    result = await self._execute_nl_search(context)
                else:
                    result = await self._execute_langgraph_search(context)

            # 更新时间
            result.started_at = started_at
            result.completed_at = datetime.utcnow()
            result.task_id = task_id

            # 计算执行时间
            duration_ms = (result.completed_at - started_at).total_seconds() * 1000

            # 发送搜索完成事件
            await self._event_bus.publish(
                SearchCompletedEvent(
                    task_id=task_id,
                    user_id=user_id,
                    result_count=result.result_count,
                    duration_ms=int(duration_ms),
                    search_engine=self._config.search_engine,
                )
            )

            # 更新共享数据，供其他层使用
            context.set_shared("search_completed", True)
            context.set_shared("search_result_count", result.result_count)

            logger.info(
                f"[SearchEngineLayer] Search completed: "
                f"task_id={task_id}, results={result.result_count}, "
                f"duration={duration_ms:.0f}ms"
            )

            return result

        except Exception as e:
            completed_at = datetime.utcnow()
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            logger.error(
                f"[SearchEngineLayer] Search failed: "
                f"task_id={task_id}, error={e}"
            )

            # 发送搜索失败事件
            await self._event_bus.publish(
                SearchFailedEvent(
                    task_id=task_id,
                    user_id=user_id,
                    error=str(e),
                    search_engine=self._config.search_engine,
                )
            )

            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                task_id=task_id,
            )

    async def _execute_langgraph_search(
        self,
        context: LayerContext,
    ) -> SearchLayerResult:
        """执行 LangGraph 搜索"""
        if self._langgraph_service is None:
            await self.initialize()

        options = context.options.copy()
        options["task_id"] = context.task_id

        result = await self._langgraph_service.execute_search(
            query=context.query,
            user_id=context.user_id,
            options=options,
        )

        if result.get("success"):
            # 转换结果格式
            items = [
                SearchResultItem.from_dict(r)
                for r in result.get("results", [])
            ]

            # 从统计信息中提取字段，避免 total_results 重复
            raw_stats = result.get("statistics", {})
            stats = SearchStatistics(
                total_results=len(items),
                search_engine="langgraph",
                unique_domains=raw_stats.get("unique_domains", 0),
                layer_distribution=raw_stats.get("layer_distribution", {}),
                tier_distribution=raw_stats.get("tier_distribution", {}),
                language_distribution=raw_stats.get("language_distribution", {}),
                execution_time_ms=raw_stats.get("execution_time_ms", 0),
            )

            return SearchLayerResult(
                status=LayerStatus.COMPLETED,
                results=items,
                statistics=stats,
                data=result,
            )
        else:
            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error=result.get("error_message") or result.get("error", "Unknown error"),
                data=result,
            )

    async def _execute_nl_search(
        self,
        context: LayerContext,
    ) -> SearchLayerResult:
        """执行 NL Search 搜索"""
        if self._nl_search_service is None:
            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error="NL Search service not available",
            )

        try:
            result = await self._nl_search_service.create_search(
                query_text=context.query,
                user_id=context.user_id,
            )

            if result:
                items = [
                    SearchResultItem.from_dict(r)
                    for r in result.get("results", [])
                ]

                stats = SearchStatistics(
                    total_results=len(items),
                    search_engine="nl_search",
                )

                return SearchLayerResult(
                    status=LayerStatus.COMPLETED,
                    results=items,
                    statistics=stats,
                    data=result,
                )
            else:
                return SearchLayerResult(
                    status=LayerStatus.FAILED,
                    error="No results from NL Search",
                )
        except Exception as e:
            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error=str(e),
            )

    async def get_search_status(self, task_id: str) -> str:
        """获取搜索状态"""
        if self._result_repository is None:
            return "unknown"

        try:
            result = await self._result_repository.find_by_task_id(task_id)
            if result:
                return result.get("status", "unknown")
            return "not_found"
        except Exception:
            return "error"

    async def get_search_results(
        self,
        task_id: str,
    ) -> Optional[SearchLayerResult]:
        """获取搜索结果"""
        if self._result_repository is None:
            return None

        try:
            results = await self._result_repository.find_by_task_id(task_id)
            if results:
                items = [
                    SearchResultItem.from_dict(r)
                    for r in results.get("results", [])
                ]
                return SearchLayerResult(
                    status=LayerStatus.COMPLETED,
                    results=items,
                    task_id=task_id,
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get search results: {e}")
            return None
