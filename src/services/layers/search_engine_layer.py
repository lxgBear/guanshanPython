"""搜索引擎层实现

封装搜索服务，提供职责单一的搜索层。

v4.19.0 - 集成 gs-ai-crawl 搜索引擎

职责:
- 执行搜索查询（gs-ai-crawl 或 NL Search）
- 将结果保存到 langgraph_search_results 集合
- 发送搜索完成事件

不负责:
- 调用 AI 服务
- 处理对话历史
- 推送到前端
"""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

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
from src.core.domain.entities.langgraph_search_result import LangGraphSearchResult

logger = logging.getLogger(__name__)


class SearchEngineLayerConfig(LayerConfig):
    """搜索引擎层配置"""
    search_engine: str = "gsac"  # "gsac" | "nl_search" - 默认使用 gsac
    fallback_engine: str = "nl_search"
    enable_fallback: bool = True  # 启用回退到 nl_search
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
        gsac_engine: Optional[Any] = None,
        nl_search_service: Optional[Any] = None,
        result_repository: Optional[Any] = None,
    ):
        """初始化搜索引擎层

        Args:
            config: 层配置
            gsac_engine: gs-ai-crawl 搜索引擎实例
            nl_search_service: NL Search 服务实例
            result_repository: 结果仓储实例
        """
        self._config = config or SearchEngineLayerConfig()
        self._gsac_engine = gsac_engine
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
        # 延迟导入，避免循环依赖
        # 初始化 gsac 引擎
        if self._gsac_engine is None:
            try:
                from src.services.langgraph_search.gsac_engine import GSAICrawlEngine
                self._gsac_engine = GSAICrawlEngine()
            except ImportError:
                logger.warning("GSAICrawlEngine not available")

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
            # 检查配置的引擎是否可用
            if self._config.search_engine == "gsac":
                return self._gsac_engine is not None
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
            # 执行搜索 - 根据配置选择引擎
            if self._config.search_engine == "gsac":
                result = await self._execute_gsac_search(context)
            else:
                result = await self._execute_nl_search(context)

            # 如果主搜索失败且启用回退
            if not result.is_success and self._config.enable_fallback:
                logger.warning(
                    f"[SearchEngineLayer] Primary search failed, trying fallback: {self._config.fallback_engine}"
                )
                # 回退到备用引擎
                if self._config.fallback_engine == "nl_search":
                    result = await self._execute_nl_search(context)
                elif self._config.fallback_engine == "gsac":
                    result = await self._execute_gsac_search(context)

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

    async def _execute_gsac_search(
        self,
        context: LayerContext,
    ) -> SearchLayerResult:
        """执行 gs-ai-crawl 搜索

        Args:
            context: 层执行上下文

        Returns:
            SearchLayerResult: 搜索结果
        """
        if self._gsac_engine is None:
            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error="gs-ai-crawl engine not available",
            )

        try:
            # 从 context.options 获取搜索配置
            options = context.options or {}
            
            result = await self._gsac_engine.search(
                query=context.query,
                user_id=context.user_id,
                **options
            )

            if result.get("success"):
                items = [
                    SearchResultItem.from_dict(r)
                    for r in result.get("results", [])
                ]

                stats = SearchStatistics(
                    total_results=result.get("statistics", {}).get("total_results", len(items)),
                    search_engine="gsac",
                )

                # 保存到数据库（如果配置启用）
                if self._config.save_to_db and self._result_repository:
                    try:
                        # 将 Dict 转换为 LangGraphSearchResult 实体
                        langgraph_results = self._convert_to_langgraph_results(
                            raw_results=result.get("results", []),
                            task_id=context.task_id,
                            user_id=context.user_id,
                            conversation_id=context.options.get("conversation_id") if context.options else None,
                        )
                        if langgraph_results:
                            save_stats = await self._result_repository.save_results(
                                results=langgraph_results,
                                enable_dedup=True,
                            )
                            logger.info(
                                f"[SearchEngineLayer] Saved results: "
                                f"saved={save_stats.get('saved', 0)}, "
                                f"duplicates={save_stats.get('duplicates', 0)}"
                            )
                    except Exception as e:
                        logger.warning(f"[SearchEngineLayer] Failed to save results: {e}")

                return SearchLayerResult(
                    status=LayerStatus.COMPLETED,
                    results=items,
                    statistics=stats,
                    data=result,
                )
            else:
                return SearchLayerResult(
                    status=LayerStatus.FAILED,
                    error=result.get("error", "Unknown error from gsac"),
                )
        except Exception as e:
            logger.error(f"[SearchEngineLayer] gsac search failed: {e}", exc_info=True)
            return SearchLayerResult(
                status=LayerStatus.FAILED,
                error=str(e),
            )

    def _convert_to_langgraph_results(
        self,
        raw_results: List[Dict[str, Any]],
        task_id: str,
        user_id: str,
        conversation_id: Optional[str] = None,
    ) -> List[LangGraphSearchResult]:
        """将 gsac 原始结果转换为 LangGraphSearchResult 实体

        Args:
            raw_results: gsac 返回的原始结果列表
            task_id: 任务 ID
            user_id: 用户 ID
            conversation_id: 对话会话 ID（可选）

        Returns:
            LangGraphSearchResult 实体列表
        """
        from src.infrastructure.id_generator import generate_string_id

        results = []
        skipped_count = 0
        for idx, raw in enumerate(raw_results):
            try:
                # 从 metadata 中提取额外信息
                metadata = raw.get("metadata", {})

                # v4.9.2: 获取 markdown 内容
                markdown_content = raw.get("markdown") or raw.get("content")

                # v4.9.2: 过滤 - markdown 为空则跳过，不保存到数据库
                if not markdown_content or not markdown_content.strip():
                    logger.debug(f"[SearchEngineLayer] Skipping result without markdown: {raw.get('url')}")
                    skipped_count += 1
                    continue

                result = LangGraphSearchResult(
                    id=generate_string_id(),
                    task_id=str(task_id),
                    user_id=str(user_id),
                    created_by=str(user_id),
                    conversation_id=conversation_id,
                    # 基础字段
                    title=raw.get("title", ""),
                    url=raw.get("url", ""),
                    snippet=raw.get("snippet", ""),
                    source=raw.get("source_domain", "web"),
                    published_date=self._parse_published_date(raw.get("published_date")),
                    markdown_content=markdown_content,
                    # v4.9.2: 移除 html_content 字段
                    search_position=idx + 1,
                    # LangGraph 特定字段 (v4.8.1: 移除评分字段)
                    layer=raw.get("layer", 0),
                    layer_name=self._get_layer_name(raw.get("layer", 0)),
                    source_tier=raw.get("source_tier", 3),
                    category=raw.get("category"),
                    # 元数据 (保存评分到 metadata 供参考)
                    metadata={
                        "keyword": metadata.get("keyword"),
                        "source": metadata.get("source"),
                        "engine": "gsac",
                        "credibility_score": raw.get("credibility_score", 0.5),
                        "final_score": raw.get("score", 0.0),
                    },
                    data_source_type="gsac",
                    created_at=datetime.utcnow(),
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"[SearchEngineLayer] Failed to convert result: {e}")
                continue

        logger.info(
            f"[SearchEngineLayer] Converted {len(results)} results to LangGraphSearchResult, "
            f"skipped {skipped_count} without markdown"
        )
        return results

    def _get_layer_name(self, layer: int) -> str:
        """获取层级名称"""
        layer_names = {
            0: "官方来源",
            1: "主流媒体",
            2: "区域媒体",
            3: "国际媒体",
            4: "智库机构",
        }
        return layer_names.get(layer, "未知层级")

    def _parse_published_date(self, date_value: Union[str, datetime, None]) -> Optional[datetime]:
        """解析发布日期

        支持多种日期格式：
        - datetime 对象
        - ISO 8601 格式: "2025-01-19T12:00:00Z"
        - 英文月份格式: "Nov 11, 2025", "January 15, 2026"
        - 纯数字格式: "2025-01-19", "2025/01/19"

        Args:
            date_value: 日期值（字符串或 datetime）

        Returns:
            datetime 对象或 None
        """
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if not isinstance(date_value, str):
            return None

        date_str = date_value.strip()
        if not date_str:
            return None

        # 常见日期格式列表
        date_formats = [
            # ISO 8601 formats
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            # English month formats
            "%b %d, %Y",      # "Nov 11, 2025"
            "%B %d, %Y",      # "November 11, 2025"
            "%d %b %Y",       # "11 Nov 2025"
            "%d %B %Y",       # "11 November 2025"
            "%b %d %Y",       # "Nov 11 2025"
            "%B %d %Y",       # "November 11 2025"
            # Other common formats
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%m-%d-%Y",
            "%d-%m-%Y",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # 如果所有格式都失败，记录警告
        logger.warning(f"[SearchEngineLayer] Unable to parse date: {date_str}")
        return None

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
