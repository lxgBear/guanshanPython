"""
Map + Scrape 组合执行器

使用 Firecrawl Map API 快速发现URL，再通过 Scrape API 批量获取内容
支持时间范围过滤，实现精确、高效、低成本的内容爬取
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter, MapAPIError
from src.core.domain.interfaces.crawler_interface import CrawlResult
from src.core.domain.entities.firecrawl_raw_response import create_firecrawl_raw_response
from src.infrastructure.database.firecrawl_raw_repositories import get_firecrawl_raw_repository
from src.infrastructure.database.repositories import SearchResultRepository

from ..base import TaskExecutor, ConfigValidationError, ExecutionError
from ..config import MapScrapeConfig, ConfigFactory
from ..credits_calculator import FirecrawlCreditsCalculator
from ..filters import PipelineBuilder, FilterContext


class MapScrapeExecutor(TaskExecutor):
    """Map + Scrape 组合任务执行器

    执行流程：
    1. Map API 发现所有URL（固定1 credit）
    2. 批量 Scrape API 获取页面内容（N credits）
    3. 时间过滤（根据publishedDate）
    4. 保存结果

    优势：
    - 精确控制：只爬取需要的页面
    - 成本优化：相比Crawl API节省80-90%积分
    - 时间过滤：支持按发布日期过滤内容
    """

    def __init__(self):
        super().__init__()
        self.adapter = FirecrawlAdapter()
        self.result_repo = SearchResultRepository()

    def _extract_metadata_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """从爬取结果的metadata中提取结构化字段

        与其他Executor保持一致的字段提取逻辑

        Args:
            metadata: CrawlResult.metadata字典

        Returns:
            包含提取字段的字典
        """
        extracted = {}

        # 1. 提取作者
        extracted['author'] = metadata.get('author')

        # 2. 提取语言
        extracted['language'] = metadata.get('language')

        # 3. 提取文章标签（处理列表格式）
        article_tag_raw = metadata.get('article:tag')
        if isinstance(article_tag_raw, list):
            extracted['article_tag'] = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        else:
            extracted['article_tag'] = article_tag_raw

        # 4. 提取文章发布时间
        extracted['article_published_time'] = metadata.get('article:published_time')

        # 5. 提取源URL（重定向场景）
        extracted['source_url'] = metadata.get('sourceURL')

        # 6. 提取HTTP状态码
        extracted['http_status_code'] = metadata.get('statusCode')

        # 7. 解析发布日期
        published_date = None
        published_date_str = metadata.get('publishedDate') or metadata.get('published_date')
        if published_date_str:
            try:
                published_date = datetime.fromisoformat(published_date_str)
            except:
                self.logger.debug(f"无法解析发布日期: {published_date_str}")
        extracted['published_date'] = published_date

        return extracted

    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置

        Args:
            task: 搜索任务

        Returns:
            bool: 配置是否有效
        """
        if not task.crawl_url:
            self.logger.error("Map + Scrape 任务必须提供 crawl_url 参数")
            return False

        if not task.crawl_url.startswith(('http://', 'https://')):
            self.logger.error(f"crawl_url 格式无效: {task.crawl_url}")
            return False

        # 验证配置对象
        config = ConfigFactory.create_map_scrape_config(task.crawl_config)
        if not config.is_valid():
            self.logger.error("MapScrapeConfig 配置无效")
            return False

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行 Map + Scrape 任务

        Args:
            task: 搜索任务

        Returns:
            SearchResultBatch: 爬取结果批次

        Raises:
            ConfigValidationError: 配置验证失败
            ExecutionError: 执行过程错误
        """
        start_time = datetime.utcnow()
        self._log_execution_start(task)

        # 1. 验证配置
        if not self.validate_config(task):
            raise ConfigValidationError(f"任务配置无效: {task.id}")

        # 2. 解析配置
        config = ConfigFactory.create_map_scrape_config(task.crawl_config)
        self.logger.info(f"📋 配置: {config}")

        try:
            # 3. 执行 Map API 发现 URL
            self.logger.info(f"🗺️  Step 1: 使用 Map API 发现 URL")
            discovered_urls = await self._execute_map(task.crawl_url, config)

            if not discovered_urls:
                self.logger.warning(f"⚠️  Map API 未发现任何URL")
                return self._create_empty_batch(task)

            self.logger.info(f"✅ 发现 {len(discovered_urls)} 个URL")

            # 3.3. URL 过滤 (v2.1.2)
            discovered_urls = await self._filter_urls(discovered_urls, task, config)

            if not discovered_urls:
                self.logger.warning(f"⚠️  过滤后无剩余URL")
                return self._create_empty_batch(task)

            # 3.4. 限制 Scrape URL 数量 (v2.1.3)
            if config.max_scrape_urls and len(discovered_urls) > config.max_scrape_urls:
                self.logger.info(
                    f"📊 限制 URL 数量: {len(discovered_urls)} → {config.max_scrape_urls}"
                )
                discovered_urls = discovered_urls[:config.max_scrape_urls]

            # 3.5. URL去重检查（v2.1.1）
            if config.enable_dedup:
                self.logger.info(f"🔍 检查已爬取URL去重")
                existing_urls = await self.result_repo.check_existing_urls(
                    task_id=str(task.id),
                    urls=discovered_urls
                )

                if existing_urls:
                    # 过滤掉已存在的URL
                    new_urls = [url for url in discovered_urls if url not in existing_urls]
                    self.logger.info(
                        f"✅ URL去重: 发现{len(discovered_urls)}个, "
                        f"已存在{len(existing_urls)}个, "
                        f"待爬取{len(new_urls)}个"
                    )
                    discovered_urls = new_urls

                    if not discovered_urls:
                        self.logger.warning(f"⚠️  所有URL均已爬取，跳过执行")
                        return self._create_empty_batch(task)

            # 4. 批量 Scrape 获取内容
            self.logger.info(f"📥 Step 2: 批量 Scrape 获取页面内容")
            scrape_results = await self._batch_scrape(discovered_urls, config)

            if not scrape_results:
                self.logger.warning(f"⚠️  Scrape 未获取到任何内容")
                return self._create_empty_batch(task)

            self.logger.info(f"✅ 成功爬取 {len(scrape_results)} 个页面")

            # 5. 时间过滤
            if config.has_time_filter():
                self.logger.info(f"🕒 Step 3: 应用时间过滤")
                scrape_results = self._filter_by_date(scrape_results, config)
                self.logger.info(f"✅ 过滤后剩余 {len(scrape_results)} 个页面")

            if not scrape_results:
                self.logger.warning(f"⚠️  时间过滤后无结果")
                return self._create_empty_batch(task)

            # 6. 保存原始响应数据
            await self._save_raw_responses(scrape_results, task)

            # 7. 转换为 SearchResult
            search_results = self._convert_to_search_results(scrape_results, task)

            # 8. 创建结果批次
            batch = self._create_result_batch(
                task,
                query=f"Map+Scrape: {task.crawl_url}"
            )

            for result in search_results:
                batch.add_result(result)

            batch.total_count = len(search_results)

            # 9. 计算实际积分消耗
            batch.credits_used = FirecrawlCreditsCalculator.calculate_map_scrape_credits(
                urls_discovered=len(discovered_urls),
                pages_scraped=len(scrape_results)
            )
            self.logger.info(
                f"💰 积分消耗: {batch.credits_used} "
                f"(Map: 1 + Scrape: {len(scrape_results)})"
            )

            # 10. 计算执行时间
            end_time = datetime.utcnow()
            batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            self._log_execution_end(
                task,
                len(search_results),
                batch.execution_time_ms
            )

            return batch

        except MapAPIError as e:
            self.logger.error(f"Map API 调用失败: {e}")
            raise ExecutionError(f"Map API 失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"执行 Map + Scrape 失败: {e}")
            raise ExecutionError(f"Map + Scrape 执行失败: {str(e)}")

    async def _execute_map(
        self,
        url: str,
        config: MapScrapeConfig
    ) -> List[str]:
        """执行 Map API 发现 URL

        Args:
            url: 网站起始URL
            config: Map + Scrape 配置

        Returns:
            List[str]: 发现的URL列表
        """
        try:
            # 调用 Map API
            links = await self.adapter.map(
                url=url,
                search=config.search,
                limit=config.map_limit
            )

            # 提取URL列表
            urls = [link['url'] for link in links if link.get('url')]

            return urls

        except Exception as e:
            self.logger.error(f"Map API 执行失败: {e}")
            raise

    async def _batch_scrape(
        self,
        urls: List[str],
        config: MapScrapeConfig
    ) -> List[CrawlResult]:
        """批量 Scrape 获取页面内容

        使用 asyncio.Semaphore 控制并发数量，避免触发限流

        Args:
            urls: URL列表
            config: Map + Scrape 配置

        Returns:
            List[CrawlResult]: 爬取结果列表
        """
        semaphore = asyncio.Semaphore(config.max_concurrent_scrapes)
        results = []
        failed_count = 0

        async def scrape_with_semaphore(url: str) -> Optional[CrawlResult]:
            """带信号量控制的 Scrape"""
            async with semaphore:
                try:
                    # 延迟控制
                    if config.scrape_delay > 0:
                        await asyncio.sleep(config.scrape_delay)

                    # 调用 Scrape API
                    result = await self.adapter.scrape(
                        url,
                        only_main_content=config.only_main_content,
                        wait_for=config.wait_for,
                        exclude_tags=config.exclude_tags,
                        timeout=config.timeout
                    )
                    return result

                except Exception as e:
                    self.logger.warning(f"Scrape 失败 {url}: {e}")
                    return None

        # 并发执行所有 Scrape 请求
        self.logger.info(
            f"🔄 并发爬取 {len(urls)} 个URL "
            f"(并发数: {config.max_concurrent_scrapes}, "
            f"延迟: {config.scrape_delay}s)"
        )

        tasks = [scrape_with_semaphore(url) for url in urls]
        scrape_results = await asyncio.gather(*tasks)

        # 过滤失败的结果
        for result in scrape_results:
            if result is not None:
                results.append(result)
            else:
                failed_count += 1

        # 检查成功率
        success_rate = len(results) / len(urls) if urls else 0
        self.logger.info(
            f"📊 Scrape 完成: 成功 {len(results)}, 失败 {failed_count}, "
            f"成功率 {success_rate:.1%}"
        )

        if config.allow_partial_failure:
            if success_rate < config.min_success_rate:
                self.logger.warning(
                    f"⚠️  成功率 {success_rate:.1%} 低于最低要求 "
                    f"{config.min_success_rate:.1%}"
                )
        else:
            if failed_count > 0:
                raise ExecutionError(
                    f"Scrape 失败 {failed_count} 个URL，不允许部分失败"
                )

        return results

    def _filter_by_date(
        self,
        results: List[CrawlResult],
        config: MapScrapeConfig
    ) -> List[CrawlResult]:
        """根据发布日期过滤结果

        Args:
            results: 爬取结果列表
            config: Map + Scrape 配置

        Returns:
            List[CrawlResult]: 过滤后的结果列表
        """
        if not config.has_time_filter():
            return results

        filtered = []

        for result in results:
            # 获取发布日期
            metadata = result.metadata if isinstance(result.metadata, dict) else {}
            published_date_str = (
                metadata.get('publishedDate') or
                metadata.get('published_date')
            )

            if not published_date_str:
                # 没有发布日期的页面，根据配置决定是否保留
                # 这里选择保留（保守策略）
                self.logger.debug(f"⚠️  无发布日期: {result.url}")
                filtered.append(result)
                continue

            try:
                published_date = datetime.fromisoformat(published_date_str)

                # 检查是否在时间范围内
                if config.start_date and published_date < config.start_date:
                    self.logger.debug(
                        f"❌ 早于起始日期: {result.url} "
                        f"({published_date.date()})"
                    )
                    continue

                if config.end_date and published_date > config.end_date:
                    self.logger.debug(
                        f"❌ 晚于结束日期: {result.url} "
                        f"({published_date.date()})"
                    )
                    continue

                # 通过时间过滤
                filtered.append(result)

            except Exception as e:
                self.logger.warning(
                    f"⚠️  解析发布日期失败: {result.url}, {published_date_str}"
                )
                # 解析失败的页面保留
                filtered.append(result)

        return filtered

    async def _save_raw_responses(
        self,
        scrape_results: List[CrawlResult],
        task: SearchTask
    ) -> None:
        """保存 Firecrawl 原始响应数据

        Args:
            scrape_results: Scrape 结果列表
            task: 搜索任务
        """
        if not scrape_results:
            return

        try:
            raw_repo = await get_firecrawl_raw_repository()
            raw_responses = []

            for result in scrape_results:
                # 构建原始响应数据
                raw_data = {
                    "url": result.url,
                    "content": result.content or "",
                    "markdown": result.markdown,
                    "html": result.html,
                    "metadata": result.metadata if isinstance(result.metadata, dict) else {},
                    "screenshot": result.screenshot
                }

                # 创建原始响应实体
                raw_response = create_firecrawl_raw_response(
                    task_id=str(task.id),
                    result_url=result.url,
                    raw_data=raw_data,
                    api_endpoint="map_scrape",
                    response_time_ms=0
                )
                raw_responses.append(raw_response)

            # 批量保存
            if raw_responses:
                await raw_repo.batch_create(raw_responses)
                self.logger.info(
                    f"✅ 已保存 {len(raw_responses)} 条原始响应数据到 "
                    f"firecrawl_raw_responses"
                )

        except Exception as e:
            # 原始数据保存失败不影响主流程
            self.logger.warning(f"⚠️  保存原始响应数据失败: {e}")

    def _convert_to_search_results(
        self,
        scrape_results: List[CrawlResult],
        task: SearchTask
    ) -> List[SearchResult]:
        """将 CrawlResult 转换为 SearchResult

        Args:
            scrape_results: Scrape 结果列表
            task: 搜索任务

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        search_results = []

        for idx, result in enumerate(scrape_results, start=1):
            # 处理 metadata
            metadata_dict = {}
            if result.metadata:
                if isinstance(result.metadata, dict):
                    metadata_dict = result.metadata
                else:
                    # 将对象属性转换为字典
                    metadata_dict = {
                        k: v for k, v in vars(result.metadata).items()
                        if not k.startswith('_')
                    }

            # 提取元数据字段
            metadata_fields = self._extract_metadata_fields(metadata_dict)

            # 获取标题和URL
            title = metadata_dict.get("title", "")
            result_url = (
                metadata_dict.get("url") or
                metadata_dict.get("source_url") or
                result.url or
                ""
            )

            search_result = SearchResult(
                task_id=str(task.id),
                title=title if title else result_url,
                url=result_url,
                snippet=(
                    result.content[:200] if result.content else ""
                ),
                source="map_scrape",
                # 元数据字段
                published_date=metadata_fields.get('published_date'),
                author=metadata_fields.get('author'),
                language=metadata_fields.get('language'),
                article_tag=metadata_fields.get('article_tag'),
                article_published_time=metadata_fields.get('article_published_time'),
                source_url=metadata_fields.get('source_url'),
                http_status_code=metadata_fields.get('http_status_code'),
                search_position=idx,
                # 内容字段
                markdown_content=(
                    result.markdown if result.markdown
                    else result.content
                ),
                html_content=result.html,
                metadata={},  # 不再传递metadata，所有字段已提取
                relevance_score=1.0,
                status=ResultStatus.PENDING
            )
            search_results.append(search_result)

        return search_results

    async def _filter_urls(
        self,
        urls: List[str],
        task: SearchTask,
        config: MapScrapeConfig
    ) -> List[str]:
        """过滤无用URL (v2.1.2)

        使用模块化过滤管道过滤掉无用链接,如登录页面、PDF文件、外部链接等。

        Args:
            urls: 待过滤的URL列表
            task: 搜索任务
            config: Map + Scrape 配置

        Returns:
            List[str]: 过滤后的URL列表
        """
        if not urls:
            return urls

        self.logger.info(f"🔍 开始URL过滤: {len(urls)} 个原始链接")

        try:
            # 构建默认过滤管道
            # TODO: 未来可以从 config 中读取过滤模式配置
            pipeline = PipelineBuilder.build_default_pipeline(task.crawl_url)

            # 创建过滤上下文
            context = FilterContext(
                base_url=task.crawl_url,
                task_id=str(task.id),
                config=config.to_dict()
            )

            # 执行过滤
            filtered_urls = pipeline.execute(urls, context)

            # 输出统计
            stats = pipeline.get_statistics()
            self._log_filter_statistics(stats, len(urls), len(filtered_urls))

            return filtered_urls

        except Exception as e:
            self.logger.error(f"URL过滤失败: {e}", exc_info=True)
            # 过滤失败时返回原始URL列表,不影响主流程
            return urls

    def _log_filter_statistics(
        self,
        stats: dict,
        original_count: int,
        filtered_count: int
    ) -> None:
        """输出过滤统计信息

        Args:
            stats: 过滤器统计信息
            original_count: 原始URL数量
            filtered_count: 过滤后URL数量
        """
        total_filtered = original_count - filtered_count
        filter_rate = total_filtered / original_count if original_count > 0 else 0

        self.logger.info(
            f"✅ URL过滤完成: {original_count} → {filtered_count} "
            f"(过滤 {total_filtered}, {filter_rate*100:.1f}%)"
        )

        # 详细统计
        if stats:
            self.logger.info(f"📊 详细统计:")
            for filter_name, filter_stats in stats.items():
                self.logger.info(
                    f"  - {filter_name}: "
                    f"过滤 {filter_stats['filtered']} "
                    f"({filter_stats['filter_rate']*100:.1f}%)"
                )

    def _create_empty_batch(self, task: SearchTask) -> SearchResultBatch:
        """创建空结果批次

        Args:
            task: 搜索任务

        Returns:
            SearchResultBatch: 空结果批次
        """
        batch = self._create_result_batch(
            task,
            query=f"Map+Scrape: {task.crawl_url}"
        )
        batch.total_count = 0
        batch.credits_used = 1  # Map API 固定消耗1积分
        batch.execution_time_ms = 0
        return batch
