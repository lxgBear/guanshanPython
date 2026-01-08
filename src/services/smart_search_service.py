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
from src.infrastructure.llm.claude_client import ClaudeClient, ClaudeConfig, create_claude_client
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

        # v2.2.0: 方案 A - Claude 集成支持
        self.use_claude = __import__('os').getenv("SMART_SEARCH_USE_CLAUDE", "true").lower() == "true"
        self.enable_multilang = __import__('os').getenv("SMART_SEARCH_ENABLE_MULTILANG", "true").lower() == "true"
        self.default_languages = __import__('os').getenv("SMART_SEARCH_DEFAULT_LANGUAGES", "zh,en,ja,ko").split(",")

        if self.use_claude:
            self.claude_client = create_claude_client()
            logger.info(f"SmartSearchService: 使用 Claude 进行查询分解")
        else:
            self.claude_client = None
            logger.info(f"SmartSearchService: 使用 OpenAI 进行查询分解")

        # 并发控制
        self.max_concurrent_searches = int(
            __import__('os').getenv("SMART_SEARCH_MAX_CONCURRENT_SEARCHES", "5")
        )

        logger.info(
            f"SmartSearchService初始化: max_concurrent={self.max_concurrent_searches}, "
            f"multilang={self.enable_multilang}, languages={self.default_languages}"
        )

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
                # v2.2.0: 根据配置选择 LLM 服务
                if self.use_claude:
                    logger.info(f"调用 Claude 分解查询: {query}")
                    claude_decomposition = await self.claude_client.decompose_query(query, context)
                    # 转换为统一的 QueryDecomposition 格式
                    decomposition = claude_decomposition
                else:
                    # 调用 OpenAI LLM 分解
                    logger.info(f"调用 OpenAI LLM 分解查询: {query}")
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

    async def create_and_decompose_with_multilang(
        self,
        name: str,
        query: str,
        search_config: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
        languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        v2.2.0 方案 A: 创建智能搜索任务并分解查询（含多语言支持）

        这是方案 A 的核心入口方法，一站式完成：
        1. Claude 分解查询
        2. 为每个子查询生成多语言配置
        3. 返回完整的搜索配置

        Args:
            name: 任务名称
            query: 原始查询
            search_config: 搜索配置
            created_by: 创建者
            languages: 目标语言列表，默认使用配置

        Returns:
            Dict: 包含分解结果和多语言配置
            {
                "decomposed_queries": [...],  # 带 multilang_configs 的子查询
                "overall_strategy": "...",
                "languages": ["zh", "en", "ja", "ko"],
                "model": "claude-sonnet-4-20250514"
            }
        """
        if not self.use_claude:
            raise ValueError("多语言分解需要启用 Claude (设置 SMART_SEARCH_USE_CLAUDE=true)")

        if languages is None:
            languages = self.default_languages

        start_time = time.time()

        try:
            logger.info(f"开始创建多语言智能搜索任务: {name}, languages={languages}")

            # 构建搜索上下文
            context = {
                "target_domains": search_config.get("include_domains", ["无限制"])[0] if search_config and search_config.get("include_domains") else "无限制",
                "language": search_config.get("language", "中文或英文") if search_config else "中文或英文",
                "time_range": search_config.get("time_range", "不限") if search_config else "不限"
            }

            # 调用 Claude 分解查询并生成多语言配置
            result = await self.claude_client.decompose_query_with_multilang(
                query=query,
                context=context,
                languages=languages
            )

            elapsed_time = int((time.time() - start_time) * 1000)
            total_searches = len(result["decomposed_queries"]) * len(languages)

            logger.info(
                f"多语言查询分解完成: {len(result['decomposed_queries'])} 个子查询 × {len(languages)} 种语言 = {total_searches} 个搜索, "
                f"耗时={elapsed_time}ms"
            )

            return result

        except Exception as e:
            error_msg = f"多语言查询分解失败: {str(e)}"
            logger.error(error_msg)
            raise

    async def confirm_and_execute_multilang(
        self,
        task_id: str,
        confirmed_queries: List[Dict[str, Any]],  # 带多语言配置的确认查询
        progress_callback: Optional[Callable] = None
    ) -> SmartSearchTask:
        """
        v2.2.0 方案 A: 确认多语言子查询并执行搜索

        这是方案 A 的核心执行方法：
        1. 验证任务状态
        2. 执行多语言并发搜索
        3. 聚合结果
        4. 返回完成的任务

        Args:
            task_id: 智能搜索任务ID
            confirmed_queries: 用户确认的多语言子查询列表
                [{
                    "query": "子查询",
                    "multilang_configs": {"zh": "...", "en": "...", ...},
                    "languages": ["zh", "en", "ja", "ko"],
                    "reasoning": "...",
                    "focus": "..."
                }, ...]
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

            logger.info(
                f"开始执行多语言智能搜索: {task.name}, "
                f"{len(confirmed_queries)} 个子查询 × 多语言"
            )

            # 3. 标记为搜索中
            task.mark_as_searching()
            await self.task_repo.update(task)

            # 4. 执行多语言并发搜索
            sub_tasks = await self._execute_multilang_searches(
                decomposed_queries=confirmed_queries,
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
            logger.info(f"开始聚合 {len(sub_tasks)} 个多语言子搜索的结果")
            aggregation_result = await self.aggregator.aggregate(sub_tasks)

            # 6.5. 保存聚合结果
            await self._save_aggregated_results(task.id, aggregation_result)

            # 7. 更新任务状态
            stats = aggregation_result["stats"]
            task.aggregated_stats = stats

            # 计算执行时间
            task.execution_time_ms = int((time.time() - start_time) * 1000)

            # 判断最终状态
            if stats["failed_searches"] == 0:
                task.mark_as_completed(stats)
            elif stats["successful_searches"] > 0:
                task.mark_as_partial_success(stats)
            else:
                task.mark_as_failed("所有多语言子搜索均失败")

            # 保存最终状态
            await self.task_repo.update(task)

            logger.info(
                f"多语言智能搜索完成: {task.name}, "
                f"状态={task.status.value}, "
                f"总结果={stats['total_results_deduplicated']}, "
                f"耗时={task.execution_time_ms}ms"
            )

            return task

        except Exception as e:
            error_msg = f"执行多语言智能搜索失败: {str(e)}"
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

    async def _execute_multilang_searches(
        self,
        decomposed_queries: List[Dict[str, Any]],
        search_config: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> List[InstantSearchTask]:
        """
        v2.2.0: 执行多语言搜索（方案 A 核心功能）

        对每个子查询的多语言配置并发执行搜索

        Args:
            decomposed_queries: 带多语言配置的子查询列表
                [{
                    "query": "子查询",
                    "reasoning": "理由",
                    "focus": "关注点",
                    "multilang_configs": {"zh": "...", "en": "...", ...},
                    "languages": ["zh", "en", "ja", "ko"]
                }, ...]
            search_config: 搜索配置
            progress_callback: 进度回调

        Returns:
            InstantSearchTask列表
        """
        # 展平所有语言搜索任务
        all_searches = []
        for sub_query in decomposed_queries:
            multilang_configs = sub_query.get("multilang_configs", {})
            languages = sub_query.get("languages", self.default_languages)

            for lang in languages:
                if lang in multilang_configs:
                    all_searches.append({
                        "query": multilang_configs[lang],
                        "original_query": sub_query["query"],
                        "language": lang,
                        "reasoning": sub_query["reasoning"],
                        "focus": sub_query["focus"]
                    })

        total_searches = len(all_searches)
        logger.info(f"开始执行多语言搜索: {total_searches} 个搜索 (子查询×语言)")

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent_searches)

        async def search_with_semaphore(search_item: Dict[str, Any], index: int):
            """带并发控制的搜索"""
            async with semaphore:
                try:
                    query = search_item["query"]
                    language = search_item["language"]
                    original_query = search_item["original_query"]

                    logger.info(
                        f"[{index+1}/{total_searches}] [{language.upper()}] 搜索: {query} "
                        f"(原查询: {original_query})"
                    )

                    # 创建带语言标签的搜索配置
                    lang_config = search_config.copy() if search_config else {}
                    lang_config["language"] = language

                    # 执行即时搜索
                    task = await self.instant_search_service.create_and_execute_search(
                        name=f"[{language.upper()}] {query[:50]}",
                        query=query,
                        search_config=lang_config,
                        created_by="smart_search_multilang",
                        search_type="smart"
                    )

                    logger.info(
                        f"[{index+1}/{total_searches}] [{language.upper()}] 搜索完成: {query}, "
                        f"结果={task.total_results}"
                    )

                    # 调用进度回调
                    if progress_callback:
                        await progress_callback({
                            "type": "multilang_search_completed",
                            "index": index,
                            "total": total_searches,
                            "query": query,
                            "language": language,
                            "original_query": original_query,
                            "task_id": task.id,
                            "result_count": task.total_results
                        })

                    return task

                except Exception as e:
                    logger.error(
                        f"[{index+1}/{total_searches}] 搜索失败: {search_item['query']}, "
                        f"语言={search_item['language']}, 错误: {str(e)}"
                    )

                    # 调用进度回调（失败）
                    if progress_callback:
                        await progress_callback({
                            "type": "multilang_search_failed",
                            "index": index,
                            "total": total_searches,
                            "query": search_item["query"],
                            "language": search_item["language"],
                            "error": str(e)
                        })

                    # 返回失败的任务
                    from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus
                    failed_task = InstantSearchTask(
                        name=f"[{search_item['language'].upper()}] {search_item['query'][:50]}",
                        query=search_item["query"],
                        status=InstantSearchStatus.FAILED,
                        error_message=str(e)
                    )
                    return failed_task

        # 创建所有搜索任务
        search_tasks = [
            search_with_semaphore(search_item, i)
            for i, search_item in enumerate(all_searches)
        ]

        # 并发执行
        results = await asyncio.gather(*search_tasks)

        # 统计成功/失败
        successful = sum(1 for t in results if t.status.value == "completed")
        failed = len(results) - successful

        # 按语言统计
        lang_stats = {}
        for search_item in all_searches:
            lang = search_item["language"]
            lang_stats[lang] = lang_stats.get(lang, 0) + 1

        logger.info(
            f"多语言搜索完成: 总数={len(results)}, 成功={successful}, 失败={failed}, "
            f"语言分布={lang_stats}"
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
                            # v2.1.2: AggregatedSearchResult 仍保留 content 字段用于API响应
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
                # v2.1.2: 使用 markdown_content（InstantSearchResult 已移除 content 字段）
                content=result_data.markdown_content or result_data.html_content or "",
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
                # v2.1.2: result_type 映射自 source（InstantSearchResult 使用 source 字段）
                result_type=result_data.source or "web",
                language=result_data.language,
                published_date=result_data.published_date,

                # 状态（继承原始结果状态）
                status=result_data.status
            )

            aggregated_entities.append(aggregated_entity)

        # v2.2.1: URL 去重 - 检查并过滤重复的 URL
        unique_entities = []
        duplicate_count = 0
        seen_urls = set()

        for entity in aggregated_entities:
            # 使用 URL 规范化检查（与 nl_search_service 保持一致）
            url = entity.url
            if url in seen_urls:
                duplicate_count += 1
                logger.debug(f"跳过重复URL (已在本批次中): {url}")
                continue

            seen_urls.add(url)

            # 检查数据库中是否已存在该 URL 的结果
            existing = await self.aggregated_result_repo.get_by_url(smart_task_id, url)
            if existing is not None:
                duplicate_count += 1
                logger.debug(f"跳过重复URL (已在数据库中): {url}")
                continue

            unique_entities.append(entity)

        logger.info(
            f"URL去重统计: 原始={len(aggregated_entities)}, "
            f"唯一={len(unique_entities)}, "
            f"重复={duplicate_count}"
        )

        # 批量保存到 smart_search_results 集合（只保存唯一的结果）
        if unique_entities:
            saved_count = await self.aggregated_result_repo.save_results(unique_entities)
        else:
            saved_count = 0

        logger.info(
            f"保存聚合结果: task_id={smart_task_id}, "
            f"新增={saved_count}/{len(scored_results)}, "
            f"跳过重复={duplicate_count}"
        )

        return saved_count
