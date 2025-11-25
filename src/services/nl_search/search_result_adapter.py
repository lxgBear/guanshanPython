"""
NL Search 到 SearchResult 实体的适配器

用于将 NL Search 的搜索结果转换为标准的 SearchResult 实体，
以便存储到 search_results 集合，供 AI 服务统一读取。

设计说明:
- task_id 映射为 log_id（语义适配）
- source 固定为 "nl_search"（标识数据来源）
- 保留所有 Firecrawl scrape 数据
- 自动生成 content_hash 用于去重
- URL 自动规范化提高去重准确性

版本: v1.0.1
日期: 2025-11-21
"""
import logging
from typing import List, Dict, Any
from datetime import datetime

from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.services.nl_search.url_normalizer import normalize_url

logger = logging.getLogger(__name__)


class NLSearchResultAdapter:
    """NL Search 结果适配器

    将 NL Search 的字典格式结果转换为标准的 SearchResult 实体。
    """

    @staticmethod
    def convert_to_search_results(
        log_id: str,
        nl_search_results: List[Dict[str, Any]]
    ) -> List[SearchResult]:
        """
        将 NL Search 结果列表转换为 SearchResult 实体列表

        Args:
            log_id: NL Search 的日志ID（将作为 task_id 使用）
            nl_search_results: NL Search 的搜索结果列表（字典格式）

        Returns:
            List[SearchResult]: 转换后的 SearchResult 实体列表

        Example:
            >>> nl_results = [
            ...     {
            ...         "title": "FastAPI Best Practices",
            ...         "url": "https://...",
            ...         "markdown_content": "...",
            ...         "html_content": "...",
            ...         "metadata": {...},
            ...         "score": 0.95,
            ...         "scrape_success": True
            ...     }
            ... ]
            >>> search_results = NLSearchResultAdapter.convert_to_search_results(
            ...     log_id="249162656928047104",
            ...     nl_search_results=nl_results
            ... )
        """
        if not nl_search_results:
            logger.warning(f"NL Search结果为空，无法转换 (log_id: {log_id})")
            return []

        search_results = []

        for idx, nl_result in enumerate(nl_search_results, 1):
            try:
                search_result = NLSearchResultAdapter._convert_single_result(
                    log_id=log_id,
                    nl_result=nl_result,
                    position=idx
                )
                search_results.append(search_result)

            except Exception as e:
                logger.error(
                    f"转换单个结果失败 (position: {idx}, url: {nl_result.get('url')}): {e}",
                    exc_info=True
                )
                continue

        logger.info(
            f"NL Search结果转换完成: {len(search_results)}/{len(nl_search_results)} "
            f"(log_id: {log_id})"
        )

        return search_results

    @staticmethod
    def _convert_single_result(
        log_id: str,
        nl_result: Dict[str, Any],
        position: int
    ) -> SearchResult:
        """
        转换单个 NL Search 结果为 SearchResult 实体

        Args:
            log_id: NL Search 日志ID
            nl_result: 单个 NL Search 结果（字典）
            position: 搜索结果位置（排名）

        Returns:
            SearchResult: 转换后的实体
        """
        # 提取基本信息
        title = nl_result.get("title", "")
        url = nl_result.get("url", "")

        # ✅ URL规范化：统一格式提高去重准确性
        normalized_url = normalize_url(url) if url else ""

        snippet = nl_result.get("snippet") or nl_result.get("description")

        # 提取 Firecrawl scrape 数据
        markdown_content = nl_result.get("markdown_content")
        html_content = nl_result.get("html_content")
        metadata = nl_result.get("metadata", {})

        # 从 metadata 中提取有用字段
        author = metadata.get("author")
        language = metadata.get("language")
        article_tag = metadata.get("article_tag")
        article_published_time = metadata.get("article_published_time")
        source_url = metadata.get("source_url")
        http_status_code = metadata.get("status_code")

        # 提取发布日期
        published_date = None
        if article_published_time:
            try:
                published_date = datetime.fromisoformat(article_published_time)
            except (ValueError, TypeError):
                pass

        # 构建 SearchResult 实体
        search_result = SearchResult(
            # 使用雪花ID（自动生成）
            # id 由 SearchResult 自动生成

            # task_id 映射为 log_id（语义适配）
            task_id=log_id,

            # 基本信息
            title=title,
            url=normalized_url,  # ✅ 使用规范化后的URL
            snippet=snippet,

            # 来源标识
            source="nl_search",  # 固定为 nl_search 标识数据来源

            # 发布信息
            published_date=published_date,
            author=author,
            language=language,

            # Firecrawl 数据
            markdown_content=markdown_content,
            html_content=html_content,
            article_tag=article_tag,
            article_published_time=article_published_time,
            source_url=source_url,
            http_status_code=http_status_code,
            search_position=position,

            # 保留原始 metadata（精简版）
            metadata=NLSearchResultAdapter._filter_metadata(metadata),

            # 评分数据
            relevance_score=float(nl_result.get("score", 0.0)),
            quality_score=float(nl_result.get("score", 0.0)),  # 使用相同分数

            # 状态
            status=ResultStatus.PENDING,  # 新结果默认为待处理
            created_at=datetime.utcnow(),

            # 非测试数据
            is_test_data=False
        )

        # 生成 content_hash 用于去重
        search_result.ensure_content_hash()

        return search_result

    @staticmethod
    def _filter_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        过滤 metadata，保留有用字段，移除冗余信息

        Args:
            metadata: 原始 metadata

        Returns:
            Dict: 精简后的 metadata
        """
        if not metadata:
            return {}

        # 保留的有用字段
        useful_fields = [
            "title", "description", "language", "keywords",
            "og_title", "og_description", "og_image",
            "author", "article_tag", "article_published_time",
            "source_url", "status_code"
        ]

        # 过滤并返回
        filtered = {
            key: value
            for key, value in metadata.items()
            if key in useful_fields and value is not None
        }

        return filtered


# 全局实例
nl_search_result_adapter = NLSearchResultAdapter()
