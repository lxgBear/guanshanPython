"""
多语言搜索执行器

基于 Claude + Firecrawl Search 实现多语言 OSINT 搜索
支持中文、英语、日语、韩语四种语言的并行搜索和智能汇总

版本: v2.1.0
日期: 2025-01-06
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult, SearchResultBatch
from src.services.nl_search.multilang_search_service import (
    MultilangSearchService,
    get_multilang_search_service
)
from src.services.nl_search.config import (
    get_supported_language_codes,
    is_language_supported
)

from ..base import TaskExecutor, ConfigValidationError, ExecutionError
from ..credits_calculator import FirecrawlCreditsCalculator


class MultilangSearchExecutor(TaskExecutor):
    """多语言搜索任务执行器

    工作流程：
    1. 使用 Claude 生成多语言搜索查询（翻译）
    2. 使用 Firecrawl Search API 并行搜索多种语言
    3. 使用 Claude 汇总分析多语言结果（可选）
    4. 合并结果返回 SearchResultBatch
    """

    def __init__(self, multilang_service: Optional[MultilangSearchService] = None):
        """初始化执行器

        Args:
            multilang_service: 多语言搜索服务实例（可选，默认使用单例）
        """
        super().__init__()
        self._multilang_service = multilang_service

    @property
    def multilang_service(self) -> MultilangSearchService:
        """延迟初始化多语言搜索服务"""
        if self._multilang_service is None:
            self._multilang_service = get_multilang_search_service()
        return self._multilang_service

    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置

        Args:
            task: 搜索任务

        Returns:
            bool: 配置是否有效
        """
        # 1. 检查查询词
        if not task.query:
            self.logger.error("多语言搜索任务必须提供 query 参数")
            return False

        if not task.query.strip():
            self.logger.error("query 参数不能为空")
            return False

        # 2. 检查多语言配置
        if not task.languages or len(task.languages) == 0:
            self.logger.error("多语言搜索任务必须配置至少一种语言")
            return False

        # 3. 验证语言代码 (使用集中的语言配置)
        supported_languages = get_supported_language_codes()
        unsupported = [lang for lang in task.languages if not is_language_supported(lang)]
        if unsupported:
            self.logger.warning(
                f"不支持的语言代码: {unsupported}。"
                f"支持的语言: {sorted(supported_languages)}"
            )
            # 不阻断执行，只是警告

        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行多语言搜索任务

        Args:
            task: 搜索任务

        Returns:
            SearchResultBatch: 包含多语言搜索结果的批次

        Raises:
            ConfigValidationError: 配置验证失败
            ExecutionError: 执行过程错误
        """
        start_time = datetime.utcnow()
        self._log_execution_start(task)

        # 1. 验证配置
        if not self.validate_config(task):
            raise ConfigValidationError(f"任务配置无效: {task.id}")

        # 2. 创建结果批次
        result_batch = self._create_result_batch(task)

        try:
            # 3. 执行多语言搜索
            self.logger.info(
                f"🌐 开始多语言搜索: query='{task.query[:50]}...' "
                f"languages={task.languages} "
                f"auto_translate={task.auto_translate}"
            )

            # 调用多语言搜索服务
            search_result = await self.multilang_service.search(
                query=task.query,
                languages=task.languages,
                include_summary=True  # 生成 Claude 汇总
            )

            # 4. 转换结果到 SearchResult 格式
            all_results = self._convert_multilang_results(
                search_result=search_result,
                task=task
            )

            # 5. 添加到批次
            for result in all_results:
                result_batch.add_result(result)

            result_batch.total_count = len(all_results)

            # 6. 计算积分消耗
            # 多语言搜索积分 = 每种语言的搜索积分 + Claude 翻译/汇总
            result_counts = search_result.get("result_counts", {})
            total_search_results = sum(result_counts.values())

            # 搜索积分（每种语言1积分 + 每个结果1积分）
            search_credits = len(task.languages) + total_search_results

            # Claude 积分（翻译 + 汇总）
            claude_credits = 2  # 翻译查询词 + 汇总分析

            result_batch.credits_used = search_credits + claude_credits

            self.logger.info(
                f"💰 积分消耗: 搜索={search_credits}, Claude={claude_credits}, "
                f"总计={result_batch.credits_used}"
            )

            # 7. 存储 Claude 汇总到 metadata
            if "summary" in search_result:
                result_batch.search_config["multilang_summary"] = search_result["summary"]
                result_batch.search_config["multilang_queries"] = search_result.get(
                    "multilang_queries", {}
                )

            # 8. 计算执行时间
            end_time = datetime.utcnow()
            result_batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            self._log_execution_end(
                task,
                len(result_batch.results),
                result_batch.execution_time_ms
            )

            return result_batch

        except Exception as e:
            self.logger.error(f"执行多语言搜索任务失败: {e}", exc_info=True)
            result_batch.set_error(str(e))
            raise ExecutionError(f"多语言搜索任务执行失败: {str(e)}")

    def _convert_multilang_results(
        self,
        search_result: Dict[str, Any],
        task: SearchTask
    ) -> List[SearchResult]:
        """转换多语言搜索结果到 SearchResult 格式

        Args:
            search_result: MultilangSearchService 返回的结果
            task: 搜索任务

        Returns:
            List[SearchResult]: 转换后的搜索结果列表
        """
        all_results = []
        results_by_lang = search_result.get("results", {})

        position = 0
        for lang, lang_results in results_by_lang.items():
            for item in lang_results:
                position += 1
                result = self._convert_single_result(
                    item=item,
                    task=task,
                    language=lang,
                    position=position
                )
                all_results.append(result)

        self.logger.info(
            f"✅ 转换完成：共 {len(all_results)} 条结果 "
            f"(按语言: {search_result.get('result_counts', {})})"
        )

        return all_results

    def _convert_single_result(
        self,
        item: Dict[str, Any],
        task: SearchTask,
        language: str,
        position: int
    ) -> SearchResult:
        """转换单个搜索结果

        Args:
            item: Firecrawl 返回的单个结果
            task: 搜索任务
            language: 语言代码
            position: 搜索结果排名

        Returns:
            SearchResult: 转换后的搜索结果
        """
        # 提取基本字段
        result = SearchResult(
            task_id=str(task.id),
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description") or item.get("snippet", ""),
            source="firecrawl_multilang",
            language=language,
            search_position=position,
        )

        # 提取 Markdown 内容（如果有）
        if "markdown" in item:
            result.markdown_content = item["markdown"]
        elif "content" in item:
            result.markdown_content = item["content"]

        # 提取 HTML 内容（如果有）- v4.7.1 修复缺失
        if "html" in item:
            result.html_content = item["html"]

        # 提取元数据
        metadata = item.get("metadata", {})

        # 发布时间
        published_time = (
            metadata.get("article:published_time") or
            metadata.get("og:published_time") or
            item.get("publishedDate")
        )
        if published_time:
            result.article_published_time = published_time
            # 尝试解析为 datetime
            try:
                if isinstance(published_time, str):
                    result.published_date = datetime.fromisoformat(
                        published_time.replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                pass

        # 作者
        result.author = (
            metadata.get("author") or
            metadata.get("article:author") or
            metadata.get("og:site_name")
        )

        # 文章标签
        result.article_tag = metadata.get("article:tag")

        # 源URL（用于处理重定向）
        result.source_url = metadata.get("sourceURL") or item.get("sourceURL")

        # 生成内容哈希用于去重
        result.ensure_content_hash()

        return result
