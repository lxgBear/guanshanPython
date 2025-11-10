"""
关键词搜索执行器

实现两阶段处理流程：
1. Search API 获取搜索结果（标题、URL、摘要）
2. Scrape API 批量爬取详情页内容（完整正文）
"""

import asyncio
import re
from datetime import datetime
from typing import List, Optional

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch
from src.core.domain.entities.search_config import UserSearchConfig
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter

from ..base import TaskExecutor, ConfigValidationError, ExecutionError
from ..config import SearchConfig, ConfigFactory
from ..credits_calculator import FirecrawlCreditsCalculator


class SearchExecutor(TaskExecutor):
    """关键词搜索任务执行器

    工作流程：
    1. 阶段1：使用 Search API 获取搜索结果
    2. 阶段2：对每个结果使用 Scrape API 爬取详情页
    3. 合并结果返回
    """

    def __init__(self):
        super().__init__()
        self.search_adapter = FirecrawlSearchAdapter()
        self.scrape_adapter = FirecrawlAdapter()

    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置

        Args:
            task: 搜索任务

        Returns:
            bool: 配置是否有效
        """
        if not task.query:
            self.logger.error("关键词搜索任务必须提供 query 参数")
            return False

        if not task.query.strip():
            self.logger.error("query 参数不能为空")
            return False

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行关键词搜索任务

        Args:
            task: 搜索任务

        Returns:
            SearchResultBatch: 包含详情页内容的搜索结果批次

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
        config = ConfigFactory.create_search_config(task.search_config)

        try:
            # 3. 阶段1：执行搜索
            search_batch = await self._execute_search(task, config)

            if not search_batch.results:
                self.logger.warning(f"搜索无结果: {task.query}")
                return search_batch

            # 4. 阶段2：爬取详情页（如果启用）
            scraped_count = 0
            if config.enable_detail_scrape:
                scraped_count = await self._enrich_with_details(
                    search_batch.results,
                    config,
                    task.query
                )
            else:
                self.logger.info("详情页爬取已禁用，跳过阶段2")

            # 5. 计算实际积分消耗
            # 使用 FirecrawlCreditsCalculator 计算实际消耗
            actual_credits = FirecrawlCreditsCalculator.calculate_actual_credits(
                operation="search",
                results_count=len(search_batch.results),
                scraped_count=scraped_count
            )
            search_batch.credits_used = actual_credits

            self.logger.info(
                f"💰 积分消耗: 搜索={search_batch.credits_used - scraped_count}, "
                f"爬取={scraped_count}, 总计={actual_credits}"
            )

            # 6. 计算执行时间
            end_time = datetime.utcnow()
            search_batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            self._log_execution_end(
                task,
                len(search_batch.results),
                search_batch.execution_time_ms
            )

            return search_batch

        except Exception as e:
            self.logger.error(f"执行搜索任务失败: {e}")
            raise ExecutionError(f"搜索任务执行失败: {str(e)}")

    async def _execute_search(
        self,
        task: SearchTask,
        config: SearchConfig
    ) -> SearchResultBatch:
        """阶段1：执行搜索

        Args:
            task: 搜索任务
            config: 搜索配置

        Returns:
            SearchResultBatch: 搜索结果批次
        """
        self.logger.info(f"🔍 阶段1：搜索关键词 '{task.query}'")

        # 构建 UserSearchConfig（使用 overrides 字典）
        user_config = UserSearchConfig(
            template_name="default",
            overrides={
                "limit": config.limit,
                "language": config.language,
                "include_domains": config.include_domains,
                "strict_language_filter": config.strict_language_filter
            }
        )

        # 调用 Search API
        search_batch = await self.search_adapter.search(
            query=task.query,
            user_config=user_config,
            task_id=str(task.id)
        )

        self.logger.info(
            f"✅ 阶段1完成：获得 {len(search_batch.results)} 条搜索结果"
        )

        return search_batch

    def _filter_homepage_urls(
        self,
        results: List[SearchResult],
        config: SearchConfig
    ) -> List[SearchResult]:
        """过滤首页URL和黑名单域名，只保留详情页URL

        Args:
            results: 搜索结果列表
            config: 搜索配置

        Returns:
            过滤后的结果列表
        """
        filtered_results = []
        filter_stats = {
            'homepage': 0,
            'excluded_domain': 0,
            'total': len(results)
        }

        for result in results:
            url = result.url
            url_lower = url.lower()

            # 1. 检查域名黑名单（优先级最高）
            if config.exclude_domains:
                is_excluded_domain = False
                for excluded_domain in config.exclude_domains:
                    if excluded_domain.lower() in url_lower:
                        is_excluded_domain = True
                        filter_stats['excluded_domain'] += 1
                        self.logger.debug(
                            f"🚫 过滤黑名单域名: {result.url} (匹配: {excluded_domain})"
                        )
                        break

                if is_excluded_domain:
                    continue  # 跳过黑名单域名

            # 2. 检查是否过滤首页（如果启用）
            if config.filter_homepage:
                # 首页URL特征
                homepage_patterns = [
                    r'/$',  # 以/结尾
                    r'/index\.(html|php|htm|aspx|jsp)$',
                    r'/home$',
                    r'/default\.(html|aspx)$',
                    r'^https?://[^/]+/?$',  # 只有域名，没有路径
                ]

                # 检查是否匹配首页模式
                is_homepage = False
                for pattern in homepage_patterns:
                    if re.search(pattern, url_lower):
                        is_homepage = True
                        filter_stats['homepage'] += 1
                        self.logger.debug(
                            f"🚫 过滤首页URL: {result.url} (匹配模式: {pattern})"
                        )
                        break

                if is_homepage:
                    # 检查是否有详情页特征（可以覆盖首页判断）
                    detail_page_indicators = [
                        r'/\d{4}/\d{2}/',  # 日期路径 /2025/01/
                        r'/article/\d+',    # 文章ID
                        r'/post/\d+',       # 帖子ID
                        r'/news/\d+',       # 新闻ID
                        r'/p/\d+',          # 页面ID
                        r'[^/]+/[^/]+/[^/]+',  # 至少3层路径
                    ]

                    has_detail_indicator = False
                    for pattern in detail_page_indicators:
                        if re.search(pattern, url_lower):
                            has_detail_indicator = True
                            self.logger.debug(
                                f"✅ 保留（虽匹配首页但有详情页特征）: {result.url}"
                            )
                            break

                    if not has_detail_indicator:
                        continue  # 跳过首页URL

            # 3. 通过所有过滤器，保留该结果
            filtered_results.append(result)

        # 输出过滤统计
        total_filtered = filter_stats['homepage'] + filter_stats['excluded_domain']
        if total_filtered > 0:
            self.logger.info(
                f"🔍 URL过滤统计: 总计 {filter_stats['total']} 个 → "
                f"过滤首页 {filter_stats['homepage']} 个, "
                f"过滤黑名单域名 {filter_stats['excluded_domain']} 个, "
                f"保留 {len(filtered_results)} 个"
            )

        return filtered_results

    def _validate_content_quality(
        self,
        content: str,
        query: str,
        url: str
    ) -> Optional[str]:
        """验证内容质量，检测是否为首页内容

        Args:
            content: 页面内容
            query: 搜索关键词
            url: 页面URL

        Returns:
            Optional[str]: 如果内容无效，返回原因；否则返回 None
        """
        if not content:
            return "内容为空"

        # 1. 内容长度检查
        content_length = len(content)
        if content_length < 500:
            return f"内容过短 ({content_length} 字符)，可能为首页或无效页面"

        if content_length > 50000:
            return f"内容过长 ({content_length} 字符)，可能为首页或列表页"

        # 2. 关键词相关性检查
        content_lower = content.lower()
        query_lower = query.lower()

        # 检查查询词是否出现在内容中
        if query_lower not in content_lower:
            # 检查查询词的各个部分（分词）
            query_words = query_lower.split()
            matched_words = sum(1 for word in query_words if word in content_lower)
            match_ratio = matched_words / len(query_words) if query_words else 0

            if match_ratio < 0.5:
                return f"关键词相关性低 ({match_ratio:.1%})，可能不是目标详情页"

        # 3. 首页特征检测
        # 统计链接密度（首页通常有大量链接）
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'  # Markdown 链接
        links = re.findall(link_pattern, content)
        link_density = len(links) / max(content_length / 1000, 1)  # 每千字符的链接数

        if link_density > 20:
            return f"链接密度过高 ({link_density:.1f} 个/千字)，可能为首页或导航页"

        # 4. 导航关键词检测（首页常见词汇）
        homepage_keywords = [
            '首页', '导航', '菜单', '更多', '查看更多', '最新', '热门', '推荐',
            'home', 'navigation', 'menu', 'more', 'latest', 'popular', 'recommended'
        ]
        homepage_keyword_count = sum(
            1 for keyword in homepage_keywords
            if keyword in content_lower
        )

        if homepage_keyword_count > 5:
            return f"首页特征词过多 ({homepage_keyword_count} 个)，可能为首页"

        # 通过所有检查
        return None

    async def _enrich_with_details(
        self,
        results: List[SearchResult],
        config: SearchConfig,
        query: str
    ) -> int:
        """阶段2：批量爬取详情页内容

        使用并发控制和错误处理，确保部分失败不影响整体

        Args:
            results: 搜索结果列表（会被原地修改）
            config: 搜索配置
            query: 搜索关键词（用于内容质量验证）

        Returns:
            int: 成功爬取的页面数（用于积分计算）
        """
        # URL质量过滤
        filtered_results = self._filter_homepage_urls(results, config)

        if len(filtered_results) == 0:
            self.logger.warning("⚠️ URL过滤后无可用详情页，跳过阶段2")
            return 0

        self.logger.info(
            f"📄 阶段2：爬取 {len(filtered_results)} 个详情页 "
            f"(并发数: {config.max_concurrent_scrapes})"
        )

        # 创建并发控制信号量
        semaphore = asyncio.Semaphore(config.max_concurrent_scrapes)

        # 创建爬取任务 (使用过滤后的结果)
        tasks = [
            self._scrape_single_detail(result, config, semaphore, idx, query)
            for idx, result in enumerate(filtered_results)
        ]

        # 并发执行所有爬取任务
        scrape_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败
        success_count = sum(1 for r in scrape_results if r is True)
        failure_count = len(results) - success_count

        self.logger.info(
            f"✅ 阶段2完成：成功 {success_count}/{len(results)}, "
            f"失败 {failure_count}"
        )

        return success_count

    async def _scrape_single_detail(
        self,
        result: SearchResult,
        config: SearchConfig,
        semaphore: asyncio.Semaphore,
        index: int,
        query: str
    ) -> bool:
        """爬取单个详情页

        Args:
            result: 搜索结果（会被原地修改）
            config: 搜索配置
            semaphore: 并发控制信号量
            index: 结果索引
            query: 搜索关键词（用于内容质量验证）

        Returns:
            bool: 是否成功
        """
        async with semaphore:
            try:
                self.logger.debug(
                    f"🔍 [{index + 1}] 爬取详情页: {result.url[:60]}..."
                )

                # 构建 Scrape 参数
                scrape_options = {
                    "only_main_content": config.only_main_content,
                    "wait_for": config.wait_for,
                    "exclude_tags": config.exclude_tags,
                    "timeout": config.timeout
                }

                # 调用 Scrape API
                crawl_result = await self.scrape_adapter.scrape(
                    result.url,
                    **scrape_options
                )

                # 提取内容
                content = crawl_result.markdown or crawl_result.content

                # 内容质量验证
                validation_error = self._validate_content_quality(
                    content=content,
                    query=query,
                    url=result.url
                )

                if validation_error:
                    self.logger.warning(
                        f"⚠️ [{index + 1}] 内容质量检查失败 {result.url}: {validation_error}"
                    )
                    # 验证失败，不更新内容，保留原始搜索结果
                    return False

                # 更新搜索结果的内容
                result.markdown_content = content
                result.html_content = crawl_result.html
                # v2.1.0: 不再更新metadata，所有字段已在阶段1提取为独立字段

                self.logger.debug(f"✅ [{index + 1}] 爬取成功且内容质量合格")

                # 添加延迟避免请求过快
                if config.scrape_delay > 0:
                    await asyncio.sleep(config.scrape_delay)

                return True

            except Exception as e:
                self.logger.warning(
                    f"❌ [{index + 1}] 爬取详情页失败 {result.url}: {e}"
                )
                # 失败时保留原始搜索结果，不抛出异常
                return False
