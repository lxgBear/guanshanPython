"""
Map + Detail 核心服务

实现 Map + Detail 详情页爬取的核心业务逻辑
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.infrastructure.database.repositories import SearchResultRepository
from src.utils.logger import get_logger

from .url_filter import UrlFilter, FilterStats
from .langgraph_filter import LangGraphUrlFilter

logger = get_logger(__name__)


@dataclass
class MapDetailConfig:
    """Map + Detail 配置"""
    enable_ai_processing: bool = True      # 是否启用 AI 处理
    map_limit: int = 500                    # Map API 最大链接数
    scrape_concurrency: int = 10            # Scrape 并发数
    max_retries: int = 5                    # 失败重试次数
    llm_batch_size: int = 50                # LLM 每批处理 URL 数
    enable_dedup: bool = True               # 是否启用 URL 去重

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "enable_ai_processing": self.enable_ai_processing,
            "map_limit": self.map_limit,
            "scrape_concurrency": self.scrape_concurrency,
            "max_retries": self.max_retries,
            "llm_batch_size": self.llm_batch_size,
            "enable_dedup": self.enable_dedup,
        }


@dataclass
class MapDetailStats:
    """Map + Detail 统计信息"""
    total_urls_found: int = 0              # Map 发现的总链接数
    urls_after_dedup: int = 0              # 去重后链接数
    urls_after_filter: int = 0             # 规则过滤后链接数
    urls_after_llm: int = 0                # LLM 判断后的详情页数
    urls_scraped: int = 0                  # 成功爬取数
    urls_failed: int = 0                   # 爬取失败数
    execution_time_ms: int = 0             # 执行时间

    # 详细统计
    navigation_filtered: int = 0           # 规则过滤的导航页数
    external_filtered: int = 0             # 过滤的外部链接数
    llm_navigation_pages: int = 0          # LLM 判断为导航页的数量

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_urls_found": self.total_urls_found,
            "urls_after_dedup": self.urls_after_dedup,
            "urls_after_filter": self.urls_after_filter,
            "urls_after_llm": self.urls_after_llm,
            "urls_scraped": self.urls_scraped,
            "urls_failed": self.urls_failed,
            "execution_time_ms": self.execution_time_ms,
            "navigation_filtered": self.navigation_filtered,
            "external_filtered": self.external_filtered,
            "llm_navigation_pages": self.llm_navigation_pages,
        }


@dataclass
class MapDetailResult:
    """Map + Detail 执行结果"""
    task_id: str
    success: bool
    stats: MapDetailStats
    error_message: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)


class MapDetailService:
    """Map + Detail 详情页爬取服务

    核心流程：
    1. Map API 获取所有链接
    2. URL 去重
    3. 规则过滤（黑名单）
    4. LLM 判断剩余 URL
    5. Scrape 批量爬取详情页
    6. 存储到 search_results
    """

    def __init__(self, config: Optional[MapDetailConfig] = None):
        """初始化服务

        Args:
            config: Map + Detail 配置
        """
        self.config = config or MapDetailConfig()
        self.firecrawl = FirecrawlAdapter()
        self.result_repo = SearchResultRepository()
        self.logger = logger

    async def execute(
        self,
        task: SearchTask,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> MapDetailResult:
        """执行 Map + Detail 任务

        Args:
            task: 搜索任务
            progress_callback: 进度回调函数 (message, current, total)

        Returns:
            MapDetailResult: 执行结果
        """
        start_time = datetime.utcnow()
        stats = MapDetailStats()
        results: List[SearchResult] = []

        source_url = task.crawl_url or ""
        if not source_url:
            return MapDetailResult(
                task_id=str(task.id),
                success=False,
                stats=stats,
                error_message="crawl_url 未设置"
            )

        try:
            self.logger.info(f"[MapDetail] 开始执行任务: {task.id}, URL: {source_url}")

            # Step 1: Map API 获取所有链接
            self._update_progress(progress_callback, "使用 Map API 发现链接", 1, 6)
            self.logger.info(f"[MapDetail] ========== Step 1: Map API 开始 ==========")
            self.logger.info(f"[MapDetail] 目标 URL: {source_url}")
            self.logger.info(f"[MapDetail] Map 限制: {self.config.map_limit}")
            discovered_urls = await self._execute_map(source_url, stats)
            stats.total_urls_found = len(discovered_urls)
            self.logger.info(f"[MapDetail] ✓ Map API 完成: 发现 {len(discovered_urls)} 个 URL")
            # 记录所有发现的 URL
            for idx, url in enumerate(discovered_urls[:20], 1):  # 只记录前20个
                self.logger.debug(f"[MapDetail]   [{idx}] {url}")
            if len(discovered_urls) > 20:
                self.logger.debug(f"[MapDetail]   ... 共 {len(discovered_urls)} 个 URL")

            if not discovered_urls:
                return MapDetailResult(
                    task_id=str(task.id),
                    success=True,
                    stats=stats,
                    results=[]
                )

            # Step 2: URL 去重
            self._update_progress(progress_callback, "检查 URL 去重", 2, 6)
            self.logger.info(f"[MapDetail] ========== Step 2: URL 去重 ==========")
            self.logger.info(f"[MapDetail] 去重前数量: {len(discovered_urls)}")
            if self.config.enable_dedup:
                discovered_urls = await self._deduplicate_urls(discovered_urls, task.id)
            stats.urls_after_dedup = len(discovered_urls)
            self.logger.info(f"[MapDetail] ✓ 去重后剩余: {len(discovered_urls)} 个 URL")

            if not discovered_urls:
                return MapDetailResult(
                    task_id=str(task.id),
                    success=True,
                    stats=stats,
                    results=[]
                )

            # Step 3: 规则过滤
            self._update_progress(progress_callback, "规则过滤导航页", 3, 6)
            self.logger.info(f"[MapDetail] ========== Step 3: 规则过滤 ==========")
            self.logger.info(f"[MapDetail] 过滤前数量: {len(discovered_urls)}")
            self.logger.info(f"[MapDetail] 基础 URL: {source_url}")
            url_filter = UrlFilter(base_url=source_url)
            filtered_urls, filter_stats = url_filter.filter(discovered_urls)
            stats.urls_after_filter = len(filtered_urls)
            stats.navigation_filtered = filter_stats.navigation_filtered
            stats.external_filtered = filter_stats.external_filtered
            self.logger.info(
                f"[MapDetail] ✓ 规则过滤完成: {len(discovered_urls)} → {len(filtered_urls)} "
                f"(导航页过滤: {filter_stats.navigation_filtered}, "
                f"外部链接: {filter_stats.external_filtered}, "
                f"无效URL: {filter_stats.invalid_filtered})"
            )
            # 记录保留的 URL
            self.logger.info(f"[MapDetail] 规则过滤后保留的 URL:")
            for idx, url in enumerate(filtered_urls, 1):
                self.logger.info(f"[MapDetail]   ✓ [{idx}] {url}")

            if not filtered_urls:
                return MapDetailResult(
                    task_id=str(task.id),
                    success=True,
                    stats=stats,
                    results=[]
                )

            # Step 4: LLM 判断
            self._update_progress(progress_callback, "LLM 判断详情页", 4, 6)
            self.logger.info(f"[MapDetail] ========== Step 4: LLM 判断 ==========")
            self.logger.info(f"[MapDetail] AI 处理启用: {self.config.enable_ai_processing}")
            self.logger.info(f"[MapDetail] 待判断 URL 数量: {len(filtered_urls)}")
            if self.config.enable_ai_processing:
                self.logger.info(f"[MapDetail] LLM 批次大小: {self.config.llm_batch_size}")
                llm_filter = LangGraphUrlFilter(batch_size=self.config.llm_batch_size)
                detail_urls, navigation_urls, llm_stats = await llm_filter.filter(filtered_urls)
                stats.urls_after_llm = len(detail_urls)
                stats.llm_navigation_pages = len(navigation_urls)
                self.logger.info(
                    f"[MapDetail] ✓ LLM 判断完成: 详情页 {len(detail_urls)}, "
                    f"导航页 {len(navigation_urls)}"
                )
                # 记录 LLM 判断结果
                self.logger.info(f"[MapDetail] LLM 判断为详情页的 URL:")
                for idx, url in enumerate(detail_urls, 1):
                    self.logger.info(f"[MapDetail]   ✓ 详情页 [{idx}] {url}")
                self.logger.info(f"[MapDetail] LLM 判断为导航页的 URL:")
                for idx, url in enumerate(navigation_urls, 1):
                    self.logger.info(f"[MapDetail]   ✗ 导航页 [{idx}] {url}")
            else:
                # 跳过 LLM 判断，全部视为详情页
                self.logger.info(f"[MapDetail] 跳过 LLM 判断，全部视为详情页")
                detail_urls = filtered_urls
                stats.urls_after_llm = len(detail_urls)
                stats.llm_navigation_pages = 0

            if not detail_urls:
                return MapDetailResult(
                    task_id=str(task.id),
                    success=True,
                    stats=stats,
                    results=[]
                )

            # Step 5: 批量 Scrape 爬取
            self._update_progress(progress_callback, "批量爬取详情页", 5, 6)
            scrape_results = await self._batch_scrape(detail_urls)
            stats.urls_scraped = len(scrape_results)
            stats.urls_failed = len(detail_urls) - len(scrape_results)
            self.logger.info(
                f"[MapDetail] Scrape 完成: 成功 {len(scrape_results)}, "
                f"失败 {stats.urls_failed}"
            )

            # Step 6: 存储结果
            self._update_progress(progress_callback, "存储结果", 6, 6)
            results = self._convert_to_search_results(scrape_results, task)
            await self._save_results(results)

            # 计算执行时间
            end_time = datetime.utcnow()
            stats.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            self.logger.info(
                f"[MapDetail] 任务完成: 发现 {stats.total_urls_found}, "
                f"爬取 {stats.urls_scraped}, 耗时 {stats.execution_time_ms}ms"
            )

            return MapDetailResult(
                task_id=str(task.id),
                success=True,
                stats=stats,
                results=results
            )

        except Exception as e:
            self.logger.error(f"[MapDetail] 执行失败: {e}", exc_info=True)
            return MapDetailResult(
                task_id=str(task.id),
                success=False,
                stats=stats,
                error_message=str(e)
            )

    async def _execute_map(self, url: str, stats: MapDetailStats) -> List[str]:
        """执行 Map API

        Args:
            url: 起始 URL
            stats: 统计信息

        Returns:
            发现的 URL 列表
        """
        try:
            links = await self.firecrawl.map(
                url=url,
                limit=self.config.map_limit
            )
            return [link['url'] for link in links if link.get('url')]

        except Exception as e:
            self.logger.error(f"[MapDetail] Map API 失败: {e}")
            raise

    async def _deduplicate_urls(self, urls: List[str], task_id: str) -> List[str]:
        """去重 URL

        Args:
            urls: URL 列表
            task_id: 任务 ID

        Returns:
            去重后的 URL 列表
        """
        try:
            existing_urls = await self.result_repo.check_existing_urls(
                task_id=str(task_id),
                urls=urls
            )

            if existing_urls:
                new_urls = [url for url in urls if url not in existing_urls]
                self.logger.info(
                    f"[MapDetail] URL 去重: 发现 {len(urls)} 个, "
                    f"已存在 {len(existing_urls)} 个, 待爬取 {len(new_urls)} 个"
                )
                return new_urls

            return urls

        except Exception as e:
            self.logger.warning(f"[MapDetail] 去重检查失败: {e}")
            # 失败时返回原始列表
            return urls

    async def _batch_scrape(self, urls: List[str]) -> List[Any]:
        """批量 Scrape 爬取

        Args:
            urls: URL 列表

        Returns:
            CrawlResult 列表
        """
        semaphore = asyncio.Semaphore(self.config.scrape_concurrency)
        results = []

        async def scrape_with_retry(url: str, retry_count: int = 0) -> Optional[Any]:
            """带重试的 Scrape"""
            async with semaphore:
                try:
                    result = await self.firecrawl.scrape(url)
                    return result

                except Exception as e:
                    if retry_count < self.config.max_retries:
                        self.logger.warning(
                            f"[MapDetail] Scrape 失败，重试 {retry_count + 1}/{self.config.max_retries}: {url}"
                        )
                        await asyncio.sleep(1 * (retry_count + 1))  # 指数退避
                        return await scrape_with_retry(url, retry_count + 1)
                    else:
                        self.logger.error(f"[MapDetail] Scrape 失败: {url}, {e}")
                        return None

        # 并发执行
        tasks = [scrape_with_retry(url) for url in urls]
        scrape_results = await asyncio.gather(*tasks)

        # 过滤成功的结果
        for result in scrape_results:
            if result is not None:
                results.append(result)

        return results

    def _convert_to_search_results(
        self,
        scrape_results: List[Any],
        task: SearchTask
    ) -> List[SearchResult]:
        """将 CrawlResult 转换为 SearchResult

        Args:
            scrape_results: CrawlResult 列表
            task: 搜索任务

        Returns:
            SearchResult 列表
        """
        results = []

        for idx, result in enumerate(scrape_results, start=1):
            # 处理 metadata
            metadata_dict = {}
            if result.metadata:
                if isinstance(result.metadata, dict):
                    metadata_dict = result.metadata
                else:
                    metadata_dict = {
                        k: v for k, v in vars(result.metadata).items()
                        if not k.startswith('_')
                    }

            # 获取标题和 URL
            title = metadata_dict.get("title", "")
            result_url = (
                metadata_dict.get("url") or
                metadata_dict.get("source_url") or
                result.url or
                ""
            )

            search_result = SearchResult(
                task_id=str(task.id),
                task_name=task.name,
                title=title if title else result_url,
                url=result_url,
                snippet=(
                    result.content[:200] if result.content else ""
                ),
                source="map_detail",
                # 元数据字段
                published_date=self._parse_published_date(metadata_dict),
                author=metadata_dict.get('author'),
                language=metadata_dict.get('language'),
                article_tag=self._extract_article_tag(metadata_dict),
                article_published_time=metadata_dict.get('article:published_time'),
                source_url=metadata_dict.get('sourceURL'),
                http_status_code=metadata_dict.get('statusCode'),
                search_position=idx,
                # 内容字段
                markdown_content=(
                    result.markdown if result.markdown
                    else result.content
                ),
                metadata={},
                status=ResultStatus.PENDING
            )
            results.append(search_result)

        return results

    def _parse_published_date(self, metadata: Dict[str, Any]) -> Optional[datetime]:
        """解析发布日期

        Args:
            metadata: 元数据字典

        Returns:
            解析后的日期，如果失败则返回 None
        """
        published_date_str = metadata.get('publishedDate') or metadata.get('published_date')
        if published_date_str:
            try:
                return datetime.fromisoformat(published_date_str)
            except:
                pass
        return None

    def _extract_article_tag(self, metadata: Dict[str, Any]) -> Optional[str]:
        """提取文章标签

        Args:
            metadata: 元数据字典

        Returns:
            标签字符串
        """
        article_tag_raw = metadata.get('article:tag')
        if isinstance(article_tag_raw, list):
            return ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        return article_tag_raw

    async def _save_results(self, results: List[SearchResult]) -> None:
        """保存结果到数据库

        Args:
            results: SearchResult 列表
        """
        if not results:
            return

        try:
            await self.result_repo.bulk_create(results)
            self.logger.info(f"[MapDetail] 保存 {len(results)} 条结果")

        except Exception as e:
            self.logger.error(f"[MapDetail] 保存结果失败: {e}")
            raise

    def _update_progress(
        self,
        callback: Optional[Callable[[str, int, int], None]],
        message: str,
        current: int,
        total: int
    ) -> None:
        """更新进度

        Args:
            callback: 进度回调函数
            message: 进度消息
            current: 当前进度
            total: 总进度
        """
        if callback:
            try:
                callback(message, current, total)
            except Exception as e:
                self.logger.warning(f"[MapDetail] 进度回调失败: {e}")


# 便捷函数
async def execute_map_detail_task(
    task: SearchTask,
    config: Optional[MapDetailConfig] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> MapDetailResult:
    """执行 Map + Detail 任务的便捷函数

    Args:
        task: 搜索任务
        config: Map + Detail 配置
        progress_callback: 进度回调函数

    Returns:
        MapDetailResult: 执行结果
    """
    service = MapDetailService(config)
    return await service.execute(task, progress_callback)
