"""LangGraph 智能搜索服务

提供基于 LangGraph 的多层搜索服务，支持:
- 5 层分层搜索策略
- 多用户数据隔离
- 状态持久化和恢复
- Human-in-the-loop 审核
- 搜索结果保存到 search_results 表 (v4.5.2)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator, TYPE_CHECKING

from anthropic import Anthropic

# Optional imports for checkpointing
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    HAS_SQLITE_SAVER = True
except ImportError:
    SqliteSaver = None
    HAS_SQLITE_SAVER = False

try:
    from langgraph.checkpoint.base import BaseCheckpointSaver
except ImportError:
    BaseCheckpointSaver = None

from .state import SearchState, create_initial_state
from .config import LangGraphSearchConfig
from .graph import build_search_graph, build_two_step_search_graph
from .feature_flags import FeatureFlags
from .utils.thread_id import (
    generate_secure_thread_id,
    validate_thread_id_ownership,
)
from .converters import ResultConverter, AggregatedResultConverter

logger = logging.getLogger(__name__)


class LangGraphSearchService:
    """LangGraph 智能搜索服务

    主要功能:
    - execute_search: 执行新搜索
    - resume_search: 恢复中断的搜索
    - get_search_status: 获取搜索状态
    - submit_review: 提交人工审核结果

    多用户隔离:
    - 每个搜索通过 thread_id 包含用户标识
    - 搜索结果关联用户 ID
    - 状态检查点按用户命名空间隔离

    Example:
        >>> service = LangGraphSearchService()
        >>> result = await service.execute_search(
        ...     query="中美贸易谈判最新进展",
        ...     user_id="12345",
        ... )
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        firecrawl_client: Optional[Any] = None,
        anthropic_client: Optional[Anthropic] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        """初始化搜索服务

        Args:
            config: LangGraph 搜索配置
            firecrawl_client: Firecrawl 客户端
            anthropic_client: Anthropic 客户端
            checkpointer: 检查点保存器（用于状态持久化）
        """
        self.config = config or LangGraphSearchConfig.from_env()
        self.firecrawl_client = firecrawl_client
        # v4.9.1: 使用配置的 API key 和 base_url
        if anthropic_client:
            self.anthropic_client = anthropic_client
        elif self.config.claude_api_key:
            # 使用配置的 API key 和 base_url
            api_key = self.config.claude_api_key
            base_url = self.config.claude_base_url
            if base_url and base_url != "https://api.anthropic.com":
                # 自定义 base_url (如中转服务)
                self.anthropic_client = Anthropic(api_key=api_key, base_url=base_url)
                logger.info(f"Anthropic client initialized with custom base_url: {base_url}")
            else:
                # 默认官方 API
                self.anthropic_client = Anthropic(api_key=api_key)
                logger.info("Anthropic client initialized with official API")
        else:
            self.anthropic_client = None
            logger.warning("Anthropic API key not configured, LLM features will be unavailable")

        # 初始化检查点保存器
        if checkpointer:
            self.checkpointer = checkpointer
        elif self.config.enable_checkpointing:
            self.checkpointer = self._create_checkpointer()
        else:
            self.checkpointer = None

        # v4.11.0: 编译两步搜索图（默认）
        self.two_step_graph = build_two_step_search_graph(
            config=self.config,
            firecrawl_client=self.firecrawl_client,
            anthropic_client=self.anthropic_client,
            checkpointer=self.checkpointer,
        )

        # 完整 5 层架构图（备用）
        self.graph = build_search_graph(
            config=self.config,
            firecrawl_client=self.firecrawl_client,
            anthropic_client=self.anthropic_client,
            checkpointer=self.checkpointer,
        )

        logger.info("LangGraphSearchService initialized (v4.11.0 two-step architecture)")

    def _create_checkpointer(self) -> Optional[Any]:
        """创建检查点保存器

        Returns:
            检查点保存器实例
        """
        if self.config.checkpoint_type == "sqlite":
            if not HAS_SQLITE_SAVER or SqliteSaver is None:
                logger.warning("SqliteSaver not available, checkpointing disabled")
                return None
            try:
                return SqliteSaver.from_conn_string(
                    self.config.checkpoint_db_path
                )
            except Exception as e:
                logger.warning(f"Failed to create SQLite checkpointer: {e}")
                return None
        # TODO: 添加 PostgreSQL 支持
        return None

    async def execute_search(
        self,
        query: str,
        user_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID（必需，用于数据隔离）
            options: 搜索选项

        Returns:
            搜索结果字典

        Raises:
            ValueError: 如果 user_id 为空
        """
        if not user_id:
            raise ValueError("user_id is required for search execution")

        # 生成安全的 thread_id
        thread_id = generate_secure_thread_id(user_id, "search")
        log_id = thread_id  # 使用 thread_id 作为 log_id

        logger.info(
            f"[user:{user_id}] Starting search: {query[:50]}... "
            f"[thread:{thread_id}]"
        )

        try:
            # v4.11.0: 检查架构选择（优先级：two_step > full）
            feature_flags = FeatureFlags.from_search_options(options)
            use_two_step = feature_flags.use_two_step_architecture

            if use_two_step:
                logger.info(f"[user:{user_id}] Using TWO-STEP architecture (v4.11.0)")
            else:
                logger.info(f"[user:{user_id}] Using FULL architecture (5-layer search)")

            # 创建初始状态
            initial_state = create_initial_state(
                query=query,
                user_id=user_id,
                log_id=log_id,
                options=options,
            )

            # 配置执行参数
            config = {
                "configurable": {
                    "thread_id": thread_id,
                }
            }

            # v4.11.0: 根据标志选择图执行
            final_state = await self._run_graph(
                initial_state,
                config,
                use_two_step=use_two_step,
            )

            # v4.5.2: 保存结果到 search_results 表
            response = self._build_response(final_state, thread_id)

            # 如果搜索成功且有结果，保存到数据库
            if response.get("success") and response.get("save_to_db"):
                final_results = response.get("results", [])
                if final_results:
                    # v4.6.0: 获取 task_id 和 conversation_id 用于数据库关联
                    task_id_for_save = options.get("task_id") if options else None
                    conversation_id_raw = options.get("conversation_id") if options else None
                    # v4.7.1: 修复 JavaScript 大整数精度丢失问题
                    # 前端发送的 ID 可能被 JS 转换为科学计数法，需要恢复为整数字符串
                    if conversation_id_raw is not None:
                        try:
                            # 尝试转换为整数再转字符串，避免科学计数法
                            conversation_id_for_save = str(int(float(conversation_id_raw)))
                        except (ValueError, TypeError):
                            conversation_id_for_save = str(conversation_id_raw) if conversation_id_raw else None
                    else:
                        conversation_id_for_save = None
                    logger.info(f"[user:{user_id}] Saving {len(final_results)} results to search_results... (task_id={task_id_for_save}, conversation_id={conversation_id_for_save})")
                    await self._save_results_to_search_results(
                        final_results, user_id, task_id_for_save, conversation_id_for_save
                    )

            return response

        except Exception as e:
            logger.error(f"[user:{user_id}] Search failed: {e}")
            return {
                "success": False,
                "thread_id": thread_id,
                "error": str(e),
                "user_id": user_id,
            }

    async def resume_search(
        self,
        thread_id: str,
        user_id: str,
        updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """恢复中断的搜索

        Args:
            thread_id: 搜索线程ID
            user_id: 用户ID
            updates: 状态更新（可选）

        Returns:
            搜索结果字典

        Raises:
            ValueError: 如果 thread_id 不属于该用户
            RuntimeError: 如果检查点不可用
        """
        # 验证 thread_id 所有权
        if not validate_thread_id_ownership(thread_id, user_id):
            raise ValueError(
                f"Thread {thread_id} does not belong to user {user_id}"
            )

        if not self.checkpointer:
            raise RuntimeError("Checkpointing is not enabled")

        logger.info(
            f"[user:{user_id}] Resuming search [thread:{thread_id}]"
        )

        try:
            # 配置执行参数
            config = {
                "configurable": {
                    "thread_id": thread_id,
                }
            }

            # 如果有状态更新（如人工审核结果）
            input_state = updates if updates else None

            # 继续执行
            final_state = await self._run_graph(input_state, config)

            return self._build_response(final_state, thread_id)

        except Exception as e:
            logger.error(f"[user:{user_id}] Resume failed: {e}")
            return {
                "success": False,
                "thread_id": thread_id,
                "error": str(e),
                "user_id": user_id,
            }

    async def stream_search(
        self,
        query: str,
        user_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            options: 搜索选项

        Yields:
            搜索进度更新
        """
        if not user_id:
            raise ValueError("user_id is required for search execution")

        thread_id = generate_secure_thread_id(user_id, "search")
        log_id = thread_id

        logger.info(
            f"[user:{user_id}] Starting stream search: {query[:50]}..."
        )

        try:
            initial_state = create_initial_state(
                query=query,
                user_id=user_id,
                log_id=log_id,
                options=options,
            )

            config = {
                "configurable": {
                    "thread_id": thread_id,
                }
            }

            # 流式执行
            async for event in self.graph.astream(initial_state, config):
                # 解析事件并生成进度更新
                yield self._parse_stream_event(event, thread_id, user_id)

        except Exception as e:
            logger.error(f"[user:{user_id}] Stream search failed: {e}")
            yield {
                "event": "error",
                "thread_id": thread_id,
                "error": str(e),
                "user_id": user_id,
            }

    async def get_search_status(
        self,
        thread_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """获取搜索状态

        Args:
            thread_id: 搜索线程ID
            user_id: 用户ID

        Returns:
            状态信息字典
        """
        if not validate_thread_id_ownership(thread_id, user_id):
            raise ValueError(
                f"Thread {thread_id} does not belong to user {user_id}"
            )

        if not self.checkpointer:
            return {
                "thread_id": thread_id,
                "status": "unknown",
                "message": "Checkpointing is not enabled",
            }

        try:
            # 获取检查点状态
            config = {"configurable": {"thread_id": thread_id}}
            state = await self.graph.aget_state(config)

            if state and state.values:
                return {
                    "thread_id": thread_id,
                    "status": state.values.get("status", "unknown"),
                    "needs_review": state.values.get("needs_review", False),
                    "results_count": len(state.values.get("final_results", [])),
                    "error_message": state.values.get("error_message"),
                }

            return {
                "thread_id": thread_id,
                "status": "not_found",
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Get status failed: {e}")
            return {
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            }

    async def submit_review(
        self,
        thread_id: str,
        user_id: str,
        approved: bool,
        feedback: Optional[str] = None,
        selected_results: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """提交人工审核结果

        Args:
            thread_id: 搜索线程ID
            user_id: 用户ID
            approved: 是否批准结果
            feedback: 审核反馈
            selected_results: 选中的结果URL列表

        Returns:
            更新后的搜索结果
        """
        if not validate_thread_id_ownership(thread_id, user_id):
            raise ValueError(
                f"Thread {thread_id} does not belong to user {user_id}"
            )

        logger.info(
            f"[user:{user_id}] Submitting review for [thread:{thread_id}]"
        )

        updates = {
            "review_completed": True,
            "needs_review": False,
        }

        if not approved:
            updates["status"] = "rejected"
            updates["error_message"] = feedback or "Review rejected"

        if selected_results:
            # 过滤结果，只保留选中的
            updates["filter_urls"] = selected_results

        return await self.resume_search(thread_id, user_id, updates)

    async def _run_graph(
        self,
        input_state: Optional[Dict[str, Any]],
        config: Dict[str, Any],
        use_two_step: bool = False,
    ) -> Dict[str, Any]:
        """运行搜索图

        Args:
            input_state: 输入状态
            config: 执行配置
            use_two_step: 是否使用两步架构 (v4.11.0，默认推荐)

        Returns:
            最终状态

        Raises:
            asyncio.TimeoutError: 如果搜索超时
        """
        # 使用配置的超时时间，默认600秒 (v4.5.3)
        timeout = self.config.search_timeout
        query = input_state.get("query", "unknown")

        # v4.11.0: 选择图（two_step 为推荐架构）
        if use_two_step:
            graph_to_use = self.two_step_graph
            arch_name = "TWO-STEP"
        else:
            graph_to_use = self.graph
            arch_name = "FULL"

        logger.info(f"[LangGraph] 开始搜索 ({arch_name}): query='{query[:50]}...', timeout={timeout}s")

        try:
            # 使用 asyncio.wait_for 包装 ainvoke 以支持超时
            import time
            start_time = time.time()

            result = await asyncio.wait_for(
                graph_to_use.ainvoke(input_state, config),
                timeout=timeout
            )

            elapsed = time.time() - start_time
            logger.info(f"[LangGraph] 搜索完成 ({arch_name}): query='{query[:50]}...', elapsed={elapsed:.1f}s")

            return result
        except asyncio.TimeoutError:
            logger.error(f"[LangGraph] ⏱️ 搜索超时 ({arch_name}): query='{query[:50]}...', timeout={timeout}s")
            raise

    async def _save_results_to_search_results(
        self,
        results: List[Dict[str, Any]],
        user_id: str,
        task_id: Optional[str] = None,  # v4.5.2: 传递 task_id 用于数据库关联
        conversation_id: Optional[str] = None,  # v4.6.0: 传递 conversation_id 用于关联历史会话
    ) -> None:
        """保存搜索结果到 langgraph_search_results 表 (v4.5.2)

        Args:
            results: LangGraph 搜索结果列表
            user_id: 用户ID
            task_id: 任务ID（用于数据库关联）

        Note:
            v4.5.2: 使用专用的 langgraph_search_results 集合，
            与 search_results 表实现数据隔离。
        """
        from src.core.domain.entities.langgraph_search_result import LangGraphSearchResult, ResultStatus
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )

        if not results:
            logger.warning(f"[user:{user_id}] No results to save to langgraph_search_results")
            return

        repo = MongoLangGraphResultRepository()
        langgraph_results = []

        for r in results:
            url = r.get("url", "")
            if not url:
                continue

            # 创建 LangGraphSearchResult 实体
            sr = LangGraphSearchResult(
                task_id=task_id or "",  # v4.5.2: 使用传入的 task_id
                conversation_id=conversation_id,  # v4.6.0: 关联对话会话
                user_id=user_id,
                created_by=user_id,
                title=r.get("title", "") or "",
                url=url,
                snippet=r.get("snippet", ""),
                source=r.get("source_domain", r.get("source", "web")),
                markdown_content=r.get("markdown_content"),
                html_content=r.get("html_content"),
                article_tag=r.get("article_tag"),
                article_published_time=r.get("article_published_time"),
                source_url=r.get("source_url"),
                http_status_code=r.get("http_status_code"),
                search_position=r.get("search_position"),
                relevance_score=r.get("relevance_score", 0.0),
                quality_score=r.get("quality_score", 0.0),
                status=ResultStatus.PENDING,
                # LangGraph 特定字段
                layer=r.get("layer", 0),
                layer_name=r.get("layer_name", ""),
                source_tier=r.get("source_tier", 1),
                credibility_score=r.get("credibility_score", 0.0),
                final_score=r.get("final_score", 0.0),
                category=r.get("category"),
                multi_source_bonus=r.get("multi_source_bonus", 0.0),
                recency_bonus=r.get("recency_bonus", 0.0),
                layer_weight=r.get("layer_weight", 0.0),
                # 存储额外的元数据
                metadata={
                    "publish_date": r.get("publish_date"),
                    "mongo_id": r.get("mongo_id"),
                },
            )
            # 生成 content_hash 用于去重
            sr.ensure_content_hash()
            langgraph_results.append(sr)

        try:
            # 批量保存（自动去重）
            stats = await repo.save_results(langgraph_results, enable_dedup=True)
            logger.info(
                f"[user:{user_id}] Saved to langgraph_search_results: "
                f"saved={stats['saved']}, duplicates={stats['duplicates']}, "
                f"total={stats['total']}"
            )

        except Exception as e:
            logger.error(f"[user:{user_id}] Failed to save results to langgraph_search_results: {e}")
            # 不抛出异常，允许搜索流程继续

    def _build_response(
        self,
        state: Dict[str, Any],
        thread_id: str,
    ) -> Dict[str, Any]:
        """构建响应

        Args:
            state: 最终状态
            thread_id: 线程ID

        Returns:
            响应字典
        """
        user_id = state.get("user_id", "")
        final_results = state.get("final_results", [])

        # v4.5.2: 保存结果到 search_results 表
        # 注意：这是一个异步操作，需要在 execute_search 中处理
        # 这里我们只标记需要保存，实际保存由调用方处理
        # v4.10.1: 修复 - 从 search_options 中读取 save_to_db 选项
        search_options = state.get("search_options", {})
        save_needed = search_options.get("save_to_db", True)

        return {
            "success": state.get("status") == "completed",
            "thread_id": thread_id,
            "user_id": user_id,
            "query": state.get("query"),
            "status": state.get("status"),
            "results": final_results,
            "statistics": state.get("statistics", {}),
            "needs_review": state.get("needs_review", False),
            "error_message": state.get("error_message"),
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "save_to_db": save_needed,  # v4.5.2: 标记是否需要保存到数据库
        }

    def _parse_stream_event(
        self,
        event: Dict[str, Any],
        thread_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """解析流式事件

        Args:
            event: LangGraph 事件
            thread_id: 线程ID
            user_id: 用户ID

        Returns:
            格式化的进度更新
        """
        # 提取节点名称和输出
        for node_name, node_output in event.items():
            if node_name == "__end__":
                return {
                    "event": "complete",
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "data": node_output,
                }

            return {
                "event": "progress",
                "thread_id": thread_id,
                "user_id": user_id,
                "node": node_name,
                "status": node_output.get("status"),
                "data": {
                    k: v for k, v in node_output.items()
                    if k not in ["markdown_content", "html_content"]
                },
            }

        return {
            "event": "unknown",
            "thread_id": thread_id,
            "user_id": user_id,
        }
