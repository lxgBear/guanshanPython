"""智能搜索服务层

v2.0.0 核心业务逻辑：
- 阶段1：创建任务并调用LLM分解查询
- 阶段2：用户确认后并发执行子搜索
- 阶段3：聚合结果并计算综合评分

架构说明：
┌─────────────────────────────────────────┐
│   智能搜索系统 (应用层) - v2.0.0         │
│   - SmartSearchService                  │
│   - ResultAggregator                    │
│   - LLM查询分解                          │
│   - 并发协调                             │
│   - 结果聚合                             │
└────────────┬────────────────────────────┘
             │ 依赖关系 (USES)
             ↓
┌─────────────────────────────────────────┐
│   即时搜索系统 (基础设施层) - v1.3.0     │
│   - InstantSearchService                │
│   - 单次搜索执行                         │
│   - 结果存储                             │
│   - 去重逻辑                             │
└────────────┬────────────────────────────┘
             │ 依赖
             ↓
┌─────────────────────────────────────────┐
│   Firecrawl API (外部服务)               │
└─────────────────────────────────────────┘

关键依赖：
- 第306行：智能搜索使用 InstantSearchService.create_and_execute_search()
- 第409行：智能搜索通过 instant_search_service.get_task_by_id() 获取子搜索结果
- ResultAggregator 使用 InstantSearchResultRepository 读取数据

注意：即时搜索系统是智能搜索的核心基础设施，不可删除！
"""

import time
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

from src.core.domain.entities.smart_search_task import SmartSearchTask, SmartSearchStatus, SubSearchResult
from src.core.domain.entities.instant_search_task import InstantSearchTask
from src.core.domain.entities.aggregated_search_result import AggregatedSearchResult, SourceInfo
from src.infrastructure.llm.openai_service import LLMService, LLMException
from src.services.instant_search_service import InstantSearchService
from src.infrastructure.database.smart_search_repositories import (
    SmartSearchTaskRepository,
    QueryDecompositionCacheRepository
)
from src.infrastructure.database.aggregated_search_result_repositories import (
    AggregatedSearchResultRepository
)
from src.services.result_aggregator import ResultAggregator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SmartSearchService:
    """
    智能搜索服务

    协调LLM分解、用户确认、并发搜索、结果聚合的完整流程
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.instant_search_service = InstantSearchService()
        self.task_repo = SmartSearchTaskRepository()
        self.cache_repo = QueryDecompositionCacheRepository()
        self.aggregator = ResultAggregator()
        self.aggregated_result_repo = AggregatedSearchResultRepository()  # v1.5.2: 职责分离

        # 并发控制
        self.max_concurrent_searches = int(
            __import__('os').getenv("SMART_SEARCH_MAX_CONCURRENT_SEARCHES", "5")
        )

        logger.info(f"SmartSearchService初始化: max_concurrent={self.max_concurrent_searches}")

    async def create_and_decompose(
        self,
        name: str,
        query: str,
        search_config: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> SmartSearchTask:
        """
        阶段1：创建智能搜索任务并分解查询

        流程：
        1. 创建SmartSearchTask
        2. 检查缓存
        3. 调用LLM分解查询（或使用缓存）
        4. 保存分解结果
        5. 返回待确认的任务

        Args:
            name: 任务名称
            query: 原始查询
            search_config: 搜索配置
            created_by: 创建者

        Returns:
            SmartSearchTask（status=awaiting_confirmation）
        """
        start_time = time.time()

        try:
            logger.info(f"开始创建智能搜索任务: {name}")

            # 1. 创建任务
            task = SmartSearchTask(
                name=name,
                original_query=query,
                search_config=search_config or {},
                created_by=created_by
            )

            # 保存初始任务
            task = await self.task_repo.create(task)
            logger.info(f"创建智能搜索任务成功: {task.name} (ID: {task.id})")

            # 2. 构建搜索上下文
            context = {
                "target_domains": search_config.get("include_domains", ["无限制"])[0] if search_config and search_config.get("include_domains") else "无限制",
                "language": search_config.get("language", "中文或英文") if search_config else "中文或英文",
                "time_range": search_config.get("time_range", "不限") if search_config else "不限"
            }

            # 3. 检查缓存
            cached_decomposition = await self.cache_repo.get_cached_decomposition(query, context)

            if cached_decomposition:
                # 使用缓存结果
                logger.info(f"使用缓存的分解结果: query_hash={query[:50]}...")
                decomposition = cached_decomposition
            else:
                # 调用LLM分解
                logger.info(f"调用LLM分解查询: {query}")
                decomposition = await self.llm_service.decompose_query(query, context)

                # 保存到缓存
                await self.cache_repo.save_decomposition(query, context, decomposition)

            # 4. 更新任务的分解信息
            task.decomposed_queries = decomposition.decomposed_queries
            task.llm_model = decomposition.model
            task.llm_reasoning = decomposition.overall_strategy
            task.decomposition_tokens_used = decomposition.tokens_used
            task.mark_as_awaiting_confirmation()

            # 保存更新
            task = await self.task_repo.update(task)

            elapsed_time = int((time.time() - start_time) * 1000)
            logger.info(
                f"查询分解完成: {len(task.decomposed_queries)}个子查询, "
                f"耗时={elapsed_time}ms, tokens={task.decomposition_tokens_used}"
            )

            return task

        except LLMException as e:
            # LLM调用失败
            error_msg = f"LLM查询分解失败: {str(e)}"
            logger.error(error_msg)

            if 'task' in locals():
                task.mark_as_failed(error_msg)
                await self.task_repo.update(task)

            raise

        except Exception as e:
            error_msg = f"创建智能搜索任务失败: {str(e)}"
            logger.error(error_msg)

            if 'task' in locals():
                task.mark_as_failed(error_msg)
                await self.task_repo.update(task)

            raise

    async def confirm_and_execute(
        self,
        task_id: str,
        confirmed_queries: List[str],
        progress_callback: Optional[Callable] = None
    ) -> SmartSearchTask:
        """
        阶段2：确认子查询并执行搜索

        流程：
        1. 验证任务状态
        2. 更新确认的查询
        3. 并发执行子搜索
        4. 聚合结果
        5. 返回完成的任务

        Args:
            task_id: 智能搜索任务ID
            confirmed_queries: 用户确认的子查询列表
            progress_callback: 进度回调函数

        Returns:
            SmartSearchTask（status=completed/partial_success/failed）
        """
        start_time = time.time()

        try:
            # 1. 获取任务
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            # 2. 验证状态
            if task.status != SmartSearchStatus.AWAITING_CONFIRMATION:
                raise ValueError(f"任务状态不允许确认: {task.status.value}")

            logger.info(f"开始执行智能搜索: {task.name}, {len(confirmed_queries)}个子查询")

            # 3. 更新确认信息
            task.user_confirmed_queries = confirmed_queries
            task.confirmed_at = datetime.utcnow()

            # 计算用户修改
            original_queries = [q.query for q in task.decomposed_queries]
            added = [q for q in confirmed_queries if q not in original_queries]
            removed = [q for q in original_queries if q not in confirmed_queries]

            task.user_modifications = {
                "added": added,
                "removed": removed,
                "edited": []  # 暂不支持编辑
            }

            # 标记为搜索中
            task.mark_as_searching()
            await self.task_repo.update(task)

            # 4. 并发执行子搜索
            sub_tasks = await self._execute_concurrent_searches(
                queries=confirmed_queries,
                search_config=task.search_config,
                progress_callback=progress_callback
            )

            # 5. 更新子搜索结果
            task.sub_search_task_ids = [t.id for t in sub_tasks]

            for sub_task in sub_tasks:
                sub_result = SubSearchResult(
                    query=sub_task.query or sub_task.crawl_url or "",
                    task_id=sub_task.id,
                    status="completed" if sub_task.status.value == "completed" else "failed",
                    result_count=sub_task.total_results,
                    credits_used=sub_task.credits_used,
                    execution_time_ms=sub_task.execution_time_ms,
                    error=sub_task.error_message,
                    retryable=sub_task.status.value == "failed"
                )
                task.add_sub_search_result(sub_task.id, sub_result)

            # 6. 聚合结果
            logger.info(f"开始聚合 {len(sub_tasks)} 个子搜索的结果")
            aggregation_result = await self.aggregator.aggregate(sub_tasks)

            # 6.5. 保存聚合结果到 smart_search_results 集合（v1.5.2 职责分离）
            await self._save_aggregated_results(task.id, aggregation_result)

            # 7. 更新任务状态
            stats = aggregation_result["stats"]
            task.aggregated_stats = stats

            # 计算执行时间
            task.execution_time_ms = int((time.time() - start_time) * 1000)

            # 判断最终状态
            if stats["failed_searches"] == 0:
                # 全部成功
                task.mark_as_completed(stats)
            elif stats["successful_searches"] > 0:
                # 部分成功
                task.mark_as_partial_success(stats)
            else:
                # 全部失败
                task.mark_as_failed("所有子搜索均失败")

            # 保存最终状态
            await self.task_repo.update(task)

            logger.info(
                f"智能搜索完成: {task.name}, "
                f"状态={task.status.value}, "
                f"总结果={stats['total_results_deduplicated']}, "
                f"耗时={task.execution_time_ms}ms"
            )

            return task

        except Exception as e:
            error_msg = f"执行智能搜索失败: {str(e)}"
            logger.error(error_msg)

            if 'task' in locals():
                task.mark_as_failed(error_msg)
                await self.task_repo.update(task)

            raise

    async def _execute_concurrent_searches(
        self,
        queries: List[str],
        search_config: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> List[InstantSearchTask]:
        """
        并发执行多个子搜索（控制并发数）

        Args:
            queries: 查询列表
            search_config: 搜索配置
            progress_callback: 进度回调

        Returns:
            InstantSearchTask列表
        """
        logger.info(f"开始并发执行 {len(queries)} 个子搜索, max_concurrent={self.max_concurrent_searches}")

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent_searches)

        async def search_with_semaphore(query: str, index: int):
            """带并发控制的搜索"""
            async with semaphore:
                try:
                    logger.info(f"[{index+1}/{len(queries)}] 开始搜索: {query}")

                    # 执行即时搜索（v2.1.0 指定搜索类型为"smart"）
                    task = await self.instant_search_service.create_and_execute_search(
                        name=f"子搜索: {query}",
                        query=query,
                        search_config=search_config,
                        created_by="smart_search_system",
                        search_type="smart"  # v2.1.0 统一架构：智能搜索结果存入instant_search_results
                    )

                    logger.info(
                        f"[{index+1}/{len(queries)}] 搜索完成: {query}, "
                        f"结果={task.total_results}, 积分={task.credits_used}"
                    )

                    # 调用进度回调
                    if progress_callback:
                        await progress_callback({
                            "type": "sub_search_completed",
                            "index": index,
                            "total": len(queries),
                            "query": query,
                            "task_id": task.id,
                            "result_count": task.total_results
                        })

                    return task

                except Exception as e:
                    logger.error(f"[{index+1}/{len(queries)}] 搜索失败: {query}, 错误: {str(e)}")

                    # 调用进度回调（失败）
                    if progress_callback:
                        await progress_callback({
                            "type": "sub_search_failed",
                            "index": index,
                            "total": len(queries),
                            "query": query,
                            "error": str(e)
                        })

                    # 返回失败的任务（不抛出异常，允许部分成功）
                    from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus
                    failed_task = InstantSearchTask(
                        name=f"子搜索: {query}",
                        query=query,
                        status=InstantSearchStatus.FAILED,
                        error_message=str(e)
                    )
                    return failed_task

        # 创建所有搜索任务
        search_tasks = [
            search_with_semaphore(query, i)
            for i, query in enumerate(queries)
        ]

        # 并发执行（等待所有完成）
        results = await asyncio.gather(*search_tasks)

        # 统计成功/失败
        successful = sum(1 for t in results if t.status.value == "completed")
        failed = len(results) - successful

        logger.info(
            f"并发搜索完成: 总数={len(results)}, "
            f"成功={successful}, 失败={failed}"
        )

        return results

    async def get_aggregated_results(
        self,
        task_id: str,
        view_mode: str = "combined",  # combined | by_query
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取聚合搜索结果

        v1.5.2: 职责分离 - 从 smart_search_results 集合读取聚合结果

        Args:
            task_id: 智能搜索任务ID
            view_mode: 视图模式（combined=综合去重, by_query=按查询分组）
            page: 页码
            page_size: 每页数量

        Returns:
            聚合结果字典
        """
        try:
            # 1. 获取任务
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            # 2. 检查任务状态
            if task.status not in [
                SmartSearchStatus.COMPLETED,
                SmartSearchStatus.PARTIAL_SUCCESS
            ]:
                raise ValueError(f"任务尚未完成: {task.status.value}")

            # 4. 根据视图模式返回结果
            if view_mode == "combined":
                # v1.5.2: 从 smart_search_results 集合读取聚合结果
                results, total = await self.aggregated_result_repo.get_results_by_task(
                    smart_task_id=task_id,
                    skip=(page - 1) * page_size,
                    limit=page_size,
                    sort_by="composite_score"
                )

                # 转换为 API 响应格式
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "result": {
                            "id": result.id,
                            "title": result.title,
                            "url": result.url,
                            "content": result.content,
                            "snippet": result.snippet,
                            "result_type": result.result_type,
                            "language": result.language,
                            "published_date": result.published_date.isoformat() if result.published_date else None,
                            "status": result.status.value
                        },
                        "composite_score": result.composite_score,
                        "sources": [
                            {
                                "query": s.query,
                                "task_id": s.task_id,
                                "position": s.position,
                                "relevance_score": s.relevance_score
                            }
                            for s in result.sources
                        ],
                        "multi_source_bonus": result.multi_source_bonus,
                        "source_count": result.source_count
                    })

                # 返回分页结果
                return {
                    "statistics": task.aggregated_stats or {},  # 从任务读取统计信息
                    "results": formatted_results,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total": total,
                        "total_pages": (total + page_size - 1) // page_size
                    }
                }

            elif view_mode == "by_query":
                # 按查询分组视图 - 仍从 instant_search_results 读取（保持原有行为）
                sub_tasks = []
                for sub_task_id in task.sub_search_task_ids:
                    sub_task = await self.instant_search_service.get_task_by_id(sub_task_id)
                    if sub_task:
                        sub_tasks.append(sub_task)

                return await self.aggregator.get_by_query_view(
                    sub_search_tasks=sub_tasks,
                    page=page,
                    page_size=page_size
                )
            else:
                raise ValueError(f"不支持的视图模式: {view_mode}")

        except Exception as e:
            logger.error(f"获取聚合结果失败: {str(e)}")
            raise

    async def get_task_by_id(self, task_id: str) -> Optional[SmartSearchTask]:
        """获取任务"""
        return await self.task_repo.get_by_id(task_id)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> tuple:
        """获取任务列表"""
        return await self.task_repo.list_tasks(
            page=page,
            page_size=page_size,
            status=status
        )

    async def _save_aggregated_results(
        self,
        smart_task_id: str,
        aggregation_result: Dict[str, Any]
    ) -> int:
        """保存聚合结果到 smart_search_results 集合

        v1.5.2: 职责分离实现
        - instant_search_results: 存储原始子搜索结果
        - smart_search_results: 存储去重聚合后的结果

        Args:
            smart_task_id: 智能搜索任务ID
            aggregation_result: ResultAggregator.aggregate() 返回的聚合结果

        Returns:
            保存的结果数量
        """
        scored_results = aggregation_result.get("results", [])

        if not scored_results:
            logger.warning(f"聚合结果为空: task_id={smart_task_id}")
            return 0

        # 转换为 AggregatedSearchResult 实体列表
        aggregated_entities = []

        for item in scored_results:
            # item 结构：
            # {
            #   "result": InstantSearchResult,
            #   "composite_score": float,
            #   "sources": [{"query", "task_id", "position", "relevance_score"}, ...],
            #   "multi_source": bool,
            #   "source_count": int
            # }

            result_data = item["result"]  # InstantSearchResult 实体

            # 构建 SourceInfo 列表
            sources = [
                SourceInfo(
                    query=s["query"],
                    task_id=s["task_id"],
                    position=s["position"],
                    relevance_score=s["relevance_score"]
                )
                for s in item["sources"]
            ]

            # 计算分项评分
            relevance_scores = [s.relevance_score for s in sources]
            positions = [s.position for s in sources]

            avg_relevance_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
            avg_position = sum(positions) / len(positions) if positions else 1
            position_score = 1.0 / (1.0 + avg_position)
            multi_source_score = item["source_count"] / aggregation_result["stats"]["total_searches"]

            # 创建 AggregatedSearchResult 实体
            aggregated_entity = AggregatedSearchResult(
                smart_task_id=smart_task_id,

                # 基础搜索结果字段（从 InstantSearchResult 复制）
                title=result_data.title,
                url=result_data.url,
                content=result_data.content,
                snippet=result_data.snippet,

                # 聚合评分
                composite_score=item["composite_score"],
                avg_relevance_score=avg_relevance_score,
                avg_quality_score=0.0,  # InstantSearchResult 暂无 quality_score
                position_score=position_score,
                multi_source_score=multi_source_score,

                # 多源信息
                sources=sources,
                source_count=item["source_count"],
                multi_source_bonus=item["multi_source"],

                # 元数据（从 InstantSearchResult 复制）
                result_type=result_data.result_type,
                language=result_data.language,
                published_date=result_data.published_date,

                # 状态（继承原始结果状态）
                status=result_data.status
            )

            aggregated_entities.append(aggregated_entity)

        # 批量保存到 smart_search_results 集合
        saved_count = await self.aggregated_result_repo.save_results(aggregated_entities)

        logger.info(
            f"保存聚合结果: task_id={smart_task_id}, "
            f"数量={saved_count}/{len(scored_results)}"
        )

        return saved_count
