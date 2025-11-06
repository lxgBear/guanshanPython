"""
单页面爬取执行器

使用 Firecrawl Scrape API 爬取单个页面的内容
"""

from datetime import datetime
from typing import Optional, Dict, Any

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter

from ..base import TaskExecutor, ConfigValidationError, ExecutionError
from ..config import ScrapeConfig, ConfigFactory
from ..credits_calculator import FirecrawlCreditsCalculator


class ScrapeExecutor(TaskExecutor):
    """单页面爬取任务执行器

    适用于定期爬取特定页面内容的场景
    """

    def __init__(self):
        super().__init__()
        self.scrape_adapter = FirecrawlAdapter()

    def _extract_metadata_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """从爬取结果的metadata中提取结构化字段

        与FirecrawlSearchAdapter保持一致的字段提取逻辑

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

        # 7. 解析发布日期（从metadata或顶层）
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
            self.logger.error("单页面爬取任务必须提供 crawl_url 参数")
            return False

        if not task.crawl_url.startswith(('http://', 'https://')):
            self.logger.error(f"crawl_url 格式无效: {task.crawl_url}")
            return False

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行单页面爬取任务

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
        config = ConfigFactory.create_scrape_config(task.search_config)

        try:
            # 3. 执行爬取
            self.logger.info(f"🌐 爬取页面: {task.crawl_url}")

            scrape_options = {
                "only_main_content": config.only_main_content,
                "wait_for": config.wait_for,
                "include_tags": config.include_tags,
                "exclude_tags": config.exclude_tags,
                "timeout": config.timeout
            }

            crawl_result = await self.scrape_adapter.scrape(
                task.crawl_url,
                **scrape_options
            )

            # 4. 提取元数据字段（与SearchExecutor保持一致）
            metadata_fields = self._extract_metadata_fields(crawl_result.metadata or {})

            # 5. 转换为 SearchResult（增强版：包含完整元数据字段）
            search_result = SearchResult(
                task_id=str(task.id),
                title=crawl_result.metadata.get("title", task.crawl_url),
                url=crawl_result.url,
                snippet=(crawl_result.content[:200] if crawl_result.content else ""),
                source="scrape",
                # 新增字段：从metadata提取
                published_date=metadata_fields.get('published_date'),
                author=metadata_fields.get('author'),
                language=metadata_fields.get('language'),
                article_tag=metadata_fields.get('article_tag'),
                article_published_time=metadata_fields.get('article_published_time'),
                source_url=metadata_fields.get('source_url'),
                http_status_code=metadata_fields.get('http_status_code'),
                search_position=1,  # URL爬取固定为位置1
                # 内容字段
                markdown_content=(
                    crawl_result.markdown if crawl_result.markdown
                    else crawl_result.content
                ),
                html_content=crawl_result.html,
                metadata={},  # v2.1.0: 不再传递metadata，所有字段已提取为独立字段
                relevance_score=1.0,  # 直接爬取的页面相关性为100%
                status=ResultStatus.PENDING
            )
            self.logger.info(f"✅ 已提取元数据字段: author={metadata_fields.get('author')}, language={metadata_fields.get('language')}")

            # 6. 创建结果批次
            batch = self._create_result_batch(
                task,
                query=f"页面爬取: {task.crawl_url}"
            )
            batch.add_result(search_result)
            batch.total_count = 1

            # 计算实际积分消耗
            batch.credits_used = FirecrawlCreditsCalculator.calculate_actual_credits(
                operation="scrape",
                urls_scraped=1
            )
            self.logger.info(f"💰 积分消耗: {batch.credits_used}")

            # 7. 计算执行时间
            end_time = datetime.utcnow()
            batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            self._log_execution_end(task, 1, batch.execution_time_ms)

            return batch

        except Exception as e:
            self.logger.error(f"执行爬取任务失败: {e}")
            raise ExecutionError(f"爬取任务执行失败: {str(e)}")
