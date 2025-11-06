"""
网站爬取执行器

使用 Firecrawl Crawl API 递归爬取整个网站的所有页面
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.core.domain.interfaces.crawler_interface import CrawlResult
from src.core.domain.entities.firecrawl_raw_response import create_firecrawl_raw_response
from src.infrastructure.database.firecrawl_raw_repositories import get_firecrawl_raw_repository

from ..base import TaskExecutor, ConfigValidationError, ExecutionError
from ..config import CrawlConfig, ConfigFactory
from ..credits_calculator import FirecrawlCreditsCalculator


class CrawlExecutor(TaskExecutor):
    """网站爬取任务执行器

    适用于需要爬取整个网站内容的场景
    使用 Firecrawl Crawl API 的异步爬取功能
    """

    def __init__(self):
        super().__init__()
        self.crawl_adapter = FirecrawlAdapter()

    def _extract_metadata_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """从爬取结果的metadata中提取结构化字段

        与FirecrawlSearchAdapter和ScrapeExecutor保持一致的字段提取逻辑

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
            self.logger.error("网站爬取任务必须提供 crawl_url 参数")
            return False

        if not task.crawl_url.startswith(('http://', 'https://')):
            self.logger.error(f"crawl_url 格式无效: {task.crawl_url}")
            return False

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行网站爬取任务

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
        config = ConfigFactory.create_crawl_config(task.crawl_config)

        try:
            # 3. 执行爬取
            self.logger.info(
                f"🌐 开始爬取网站: {task.crawl_url} "
                f"(限制: {config.limit}页, 深度: {config.max_depth})"
            )

            crawl_results = await self._execute_crawl(task.crawl_url, config)

            # 4. 保存原始响应数据到 firecrawl_raw_responses
            await self._save_raw_responses(crawl_results, task)

            # 5. 转换为 SearchResult 列表
            search_results = self._convert_to_search_results(
                crawl_results,
                task
            )

            # 5. 创建结果批次
            batch = self._create_result_batch(
                task,
                query=f"网站爬取: {task.crawl_url}"
            )

            for result in search_results:
                batch.add_result(result)

            batch.total_count = len(search_results)

            # 计算实际积分消耗
            batch.credits_used = FirecrawlCreditsCalculator.calculate_actual_credits(
                operation="crawl",
                pages_crawled=len(search_results)
            )
            self.logger.info(f"💰 积分消耗: {batch.credits_used} ({len(search_results)} 个页面)")

            # 6. 计算执行时间
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

        except Exception as e:
            self.logger.error(f"执行网站爬取失败: {e}")
            raise ExecutionError(f"网站爬取执行失败: {str(e)}")

    async def _execute_crawl(
        self,
        url: str,
        config: CrawlConfig
    ) -> List[CrawlResult]:
        """执行网站爬取

        Args:
            url: 网站URL
            config: 爬取配置

        Returns:
            List[CrawlResult]: 爬取结果列表
        """
        # 构建爬取选项
        crawl_options = {
            'limit': config.limit,
            'max_depth': config.max_depth,
            'include_paths': config.include_paths,
            'exclude_paths': config.exclude_paths,
            'allow_backward_links': config.allow_backward_links,
            'only_main_content': config.only_main_content,
            'wait_for': config.wait_for,
            'exclude_tags': config.exclude_tags
        }

        self.logger.info(f"📋 爬取参数: {crawl_options}")

        # 调用 Crawl API
        crawl_results = await self.crawl_adapter.crawl(url, **crawl_options)

        self.logger.info(f"✅ 爬取完成: 获得 {len(crawl_results)} 个页面")

        return crawl_results

    async def _save_raw_responses(
        self,
        crawl_results: List[CrawlResult],
        task: SearchTask
    ) -> None:
        """保存 Firecrawl 原始响应数据

        Args:
            crawl_results: 爬取结果列表
            task: 搜索任务
        """
        if not crawl_results:
            return

        try:
            raw_repo = await get_firecrawl_raw_repository()
            raw_responses = []

            for result in crawl_results:
                # 构建原始响应数据（包含所有字段）
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
                    api_endpoint="crawl",
                    response_time_ms=0  # crawl 没有单独的响应时间
                )
                raw_responses.append(raw_response)

            # 批量保存
            if raw_responses:
                await raw_repo.batch_create(raw_responses)
                self.logger.info(f"✅ 已保存 {len(raw_responses)} 条原始响应数据到 firecrawl_raw_responses")

        except Exception as e:
            # 原始数据保存失败不影响主流程
            self.logger.warning(f"⚠️ 保存原始响应数据失败: {e}")

    def _convert_to_search_results(
        self,
        crawl_results: List[CrawlResult],
        task: SearchTask
    ) -> List[SearchResult]:
        """将 CrawlResult 转换为 SearchResult（增强版：包含元数据字段）

        Args:
            crawl_results: 爬取结果列表
            task: 搜索任务

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        search_results = []

        for idx, crawl_result in enumerate(crawl_results, start=1):
            # v2 API: metadata 是对象,需要转换为字典
            metadata_dict = {}
            if crawl_result.metadata:
                if isinstance(crawl_result.metadata, dict):
                    metadata_dict = crawl_result.metadata
                else:
                    # 将对象属性转换为字典
                    metadata_dict = {
                        k: v for k, v in vars(crawl_result.metadata).items()
                        if not k.startswith('_')
                    }

            # 提取元数据字段（与ScrapeExecutor和SearchExecutor保持一致）
            metadata_fields = self._extract_metadata_fields(metadata_dict)

            # 获取标题和URL (v2 API: URL在metadata中)
            title = metadata_dict.get("title", "")
            # v2 API: 优先从 metadata 中获取 URL
            result_url = metadata_dict.get("url") or metadata_dict.get("source_url") or crawl_result.url or ""

            search_result = SearchResult(
                task_id=str(task.id),
                title=title if title else result_url,
                url=result_url,
                snippet=(
                    crawl_result.content[:200] if crawl_result.content else ""
                ),
                source="crawl",
                # 新增字段：从metadata提取
                published_date=metadata_fields.get('published_date'),
                author=metadata_fields.get('author'),
                language=metadata_fields.get('language'),
                article_tag=metadata_fields.get('article_tag'),
                article_published_time=metadata_fields.get('article_published_time'),
                source_url=metadata_fields.get('source_url'),
                http_status_code=metadata_fields.get('http_status_code'),
                search_position=idx,  # 爬取结果的顺序位置
                # 内容字段
                markdown_content=(
                    crawl_result.markdown if crawl_result.markdown
                    else crawl_result.content
                ),
                html_content=crawl_result.html,
                metadata={},  # v2.1.0: 不再传递metadata，所有字段已提取为独立字段
                relevance_score=1.0,
                status=ResultStatus.PENDING
            )
            search_results.append(search_result)

        return search_results
