"""即时搜索服务层

v1.3.0 核心业务逻辑：
- 支持双模式：关键词搜索（Search API）+ URL爬取（Scrape API）
- 实现content_hash去重机制
- 创建结果映射表实现跨搜索可见性
- 完整的统计信息（新结果、共享结果）
"""

import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus
from src.core.domain.entities.instant_search_result import (
    InstantSearchResult,
    create_instant_search_result_from_firecrawl
)
from src.core.domain.entities.instant_search_result_mapping import (
    InstantSearchResultMapping,
    create_result_mapping
)
from src.infrastructure.database.instant_search_repositories import (
    InstantSearchTaskRepository,
    InstantSearchResultRepository,
    InstantSearchResultMappingRepository
)
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.core.domain.entities.search_config import UserSearchConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InstantSearchService:
    """即时搜索服务"""

    def __init__(self):
        self.task_repo = InstantSearchTaskRepository()
        self.result_repo = InstantSearchResultRepository()
        self.mapping_repo = InstantSearchResultMappingRepository()
        # 使用 FirecrawlSearchAdapter（稳定的HTTP直接调用）代替 FirecrawlAdapter
        self.firecrawl_search = FirecrawlSearchAdapter()
        # 保留 FirecrawlAdapter 用于 scrape 功能
        self.firecrawl = FirecrawlAdapter()

    async def create_and_execute_search(
        self,
        name: str,
        query: Optional[str] = None,
        crawl_url: Optional[str] = None,
        search_config: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
        search_type: str = "instant"  # v2.1.0 统一架构：支持 "instant" | "smart"
    ) -> InstantSearchTask:
        """
        创建并执行即时搜索

        v1.3.0 核心流程：
        1. 创建任务
        2. 执行搜索（keyword search 或 URL crawl）
        3. 对每个结果：
           - 计算content_hash
           - 检查是否已存在（去重）
           - 如果存在：更新统计，标记为共享结果
           - 如果不存在：创建新结果，标记为新结果
           - 创建映射记录
        4. 更新任务统计

        Args:
            name: 任务名称
            query: 搜索关键词（Search模式）
            crawl_url: 爬取URL（Crawl模式，优先于query）
            search_config: 搜索配置
            created_by: 创建者

        Returns:
            执行完成的InstantSearchTask
        """
        start_time = time.time()

        # 1. 创建任务
        task = InstantSearchTask(
            name=name,
            query=query,
            crawl_url=crawl_url,
            search_config=search_config or {},
            created_by=created_by
        )

        # 同步target_website
        task.sync_target_website()

        # 保存任务
        task = await self.task_repo.create(task)
        logger.info(f"创建即时搜索任务: {task.name} (ID: {task.id})")

        # 2. 开始执行
        task.start_execution()
        await self.task_repo.update(task)

        try:
            # 3. 执行搜索
            credits_used = 1  # 默认积分消耗
            if task.get_search_mode() == "crawl":
                results_data = await self._execute_crawl(task.crawl_url)
            elif task.get_search_mode() == "search":
                # 使用新的 _execute_search_with_batch 获取积分消耗
                results_data, credits_used = await self._execute_search_with_batch(task.query, search_config or {})
            else:
                raise ValueError("必须提供query或crawl_url参数")

            # 4. 处理结果（去重 + 映射）
            new_count, shared_count = await self._process_and_save_results(
                task_id=task.id,
                search_execution_id=task.search_execution_id,
                results_data=results_data,
                search_type=search_type  # v2.1.0 传递搜索类型
            )

            # 5. 标记完成
            execution_time = int((time.time() - start_time) * 1000)
            total_count = new_count + shared_count

            task.mark_as_completed(
                total=total_count,
                new=new_count,
                shared=shared_count,
                credits=credits_used,  # 使用真实的积分消耗
                execution_time=execution_time
            )

            await self.task_repo.update(task)

            logger.info(
                f"即时搜索完成: {task.name} - "
                f"总结果={total_count}, 新结果={new_count}, 共享结果={shared_count}"
            )

            return task

        except Exception as e:
            # 标记失败
            task.mark_as_failed(str(e))
            await self.task_repo.update(task)

            logger.error(f"即时搜索失败: {task.name} - {str(e)}")
            raise

    async def _execute_search_with_batch(
        self,
        query: str,
        config: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        执行关键词搜索（Search API）并返回积分消耗

        使用 FirecrawlSearchAdapter（稳定的HTTP直接调用）

        Returns:
            Tuple[List[Dict], int]: (Firecrawl搜索结果列表, 积分消耗)
        """
        logger.info(f"执行Search API: query='{query}'")

        try:
            # 构建用户配置
            user_config = UserSearchConfig.from_json(config)

            # 使用 FirecrawlSearchAdapter 执行搜索
            batch = await self.firecrawl_search.search(
                query=query,
                user_config=user_config,
                task_id=None  # 即时搜索不关联定时任务
            )

            # 检查搜索是否成功
            if not batch.success:
                error_msg = batch.error_message or "搜索失败但未提供错误详情"
                logger.error(f"Search API失败: {error_msg}")
                raise Exception(error_msg)

            # 转换 SearchResult 列表为字典格式
            results_data = []
            for search_result in batch.results:
                results_data.append({
                    'title': search_result.title,
                    'url': search_result.url,
                    'markdown': search_result.markdown_content,
                    'html': search_result.html_content,
                    'content': search_result.content,
                    'metadata': search_result.metadata
                })

            logger.info(f"Search API返回 {len(results_data)} 条结果（积分消耗: {batch.credits_used}）")
            return results_data, batch.credits_used

        except Exception as e:
            logger.error(f"Search API失败: {str(e)}")
            raise

    async def _execute_crawl(self, url: str) -> List[Dict[str, Any]]:
        """
        执行URL爬取（Scrape API）

        Returns:
            List[Dict]: Firecrawl爬取结果（单个结果包装为列表）
        """
        logger.info(f"执行Scrape API: url='{url}'")

        try:
            # 使用Firecrawl的scrape方法
            crawl_result = await self.firecrawl.scrape(url=url)

            # 包装为列表格式
            result_data = [{
                'title': crawl_result.metadata.get('title', ''),
                'url': crawl_result.url,
                'markdown': crawl_result.markdown,
                'html': crawl_result.html,
                'content': crawl_result.content,
                'metadata': crawl_result.metadata
            }]

            logger.info(f"Scrape API成功爬取URL: {url}")
            return result_data

        except Exception as e:
            logger.error(f"Scrape API失败: {str(e)}")
            raise

    async def _process_and_save_results(
        self,
        task_id: str,
        search_execution_id: str,
        results_data: List[Dict[str, Any]],
        search_type: str = "instant"  # v2.1.0 搜索类型
    ) -> Tuple[int, int]:
        """
        处理并保存结果（v1.3.0 核心逻辑 + v2.1.0 search_type支持）

        流程：
        1. 遍历每个结果
        2. 创建InstantSearchResult实体（自动计算content_hash）
        3. 检查content_hash是否已存在
        4. 如果存在：
           - 更新发现统计
           - shared_count + 1
        5. 如果不存在：
           - 创建新结果（指定search_type）
           - new_count + 1
        6. 创建映射记录

        Args:
            task_id: 任务ID
            search_execution_id: 搜索执行ID
            results_data: Firecrawl返回的结果数据
            search_type: 搜索类型 ("instant" | "smart") v2.1.0

        Returns:
            (new_count, shared_count): 新结果数和共享结果数
        """
        new_count = 0
        shared_count = 0
        mappings = []

        for idx, data in enumerate(results_data, start=1):
            # 1. 创建结果实体（自动计算content_hash）
            result = create_instant_search_result_from_firecrawl(
                task_id=task_id,
                firecrawl_data=data,
                search_position=idx
            )

            # 2. 检查去重
            existing_result = await self.result_repo.find_by_content_hash(result.content_hash)

            if existing_result:
                # 去重命中：共享结果
                logger.debug(f"去重命中: {result.title[:50]}...")

                # 更新发现统计
                await self.result_repo.update_discovery_stats(existing_result)

                # 使用已有结果的ID
                result_id = existing_result.id
                is_first_discovery = False
                shared_count += 1

            else:
                # 新结果
                logger.debug(f"新结果: {result.title[:50]}...")

                # 创建新结果（v2.1.0 传递搜索类型）
                await self.result_repo.create(result, search_type=search_type)

                result_id = result.id
                is_first_discovery = True
                new_count += 1

            # 3. 创建映射记录
            mapping = create_result_mapping(
                search_execution_id=search_execution_id,
                result_id=result_id,
                task_id=task_id,
                search_position=idx,
                relevance_score=result.relevance_score,
                is_first_discovery=is_first_discovery
            )
            mappings.append(mapping)

        # 4. 批量保存映射
        if mappings:
            await self.mapping_repo.batch_create(mappings)
            logger.info(f"创建 {len(mappings)} 条结果映射")

        return new_count, shared_count

    async def get_task_results(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取任务的搜索结果（通过映射表JOIN）

        v1.3.0 核心查询：
        - 通过search_execution_id获取映射
        - JOIN instant_search_results表
        - 返回完整结果 + 映射元数据

        Returns:
            (results, total): 结果列表和总数
        """
        # 1. 获取任务
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        # 2. 通过映射表查询结果
        results_with_mapping, total = await self.mapping_repo.get_results_by_search_execution(
            search_execution_id=task.search_execution_id,
            page=page,
            page_size=page_size
        )

        # 3. 格式化返回
        formatted_results = []
        for item in results_with_mapping:
            mapping: InstantSearchResultMapping = item["mapping"]
            result: InstantSearchResult = item["result"]

            formatted_results.append({
                "result": result.to_dict(),
                "mapping_info": {
                    "found_at": mapping.found_at.isoformat(),
                    "search_position": mapping.search_position,
                    "relevance_score": mapping.relevance_score,
                    "is_first_discovery": mapping.is_first_discovery
                }
            })

        return formatted_results, total

    async def get_task_by_id(self, task_id: str) -> Optional[InstantSearchTask]:
        """获取任务"""
        return await self.task_repo.get_by_id(task_id)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[InstantSearchTask], int]:
        """获取任务列表"""
        return await self.task_repo.list_tasks(
            page=page,
            page_size=page_size,
            status=status
        )
