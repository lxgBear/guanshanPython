"""
搜索任务字段验证逻辑

提供 crawl_url 和 include_domains 的互斥验证
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator, model_validator
from fastapi import HTTPException


class SearchTaskFieldValidator:
    """搜索任务字段验证器"""

    @staticmethod
    def validate_crawl_url_and_include_domains(
        crawl_url: Optional[str],
        search_config: Dict[str, Any]
    ) -> None:
        """
        验证 crawl_url 和 include_domains 的互斥关系

        规则:
        1. crawl_url 和 include_domains 可以同时存在（不报错）
        2. 但会记录警告日志，提示用户 include_domains 会被忽略
        3. 建议用户只设置其中一个

        Args:
            crawl_url: 爬取URL
            search_config: 搜索配置

        Raises:
            HTTPException: 如果配置不合理
        """
        include_domains = search_config.get('include_domains', [])

        # 情况1: crawl_url 和 include_domains 都存在
        if crawl_url and include_domains:
            # 记录警告但不报错（向后兼容）
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"⚠️ crawl_url 和 include_domains 同时设置，"
                f"include_domains 将被忽略。"
                f"建议：使用 crawl_url 时，无需设置 include_domains。"
            )

    @staticmethod
    def validate_mode_fields(
        crawl_url: Optional[str],
        query: str,
        search_config: Dict[str, Any]
    ) -> None:
        """
        验证模式字段的完整性

        Args:
            crawl_url: 爬取URL
            query: 搜索关键词
            search_config: 搜索配置

        Raises:
            HTTPException: 如果配置不完整
        """
        # Crawl 模式：crawl_url 必填
        if crawl_url:
            # Crawl 模式下，其他字段可选
            return

        # Search 模式：query 必填
        if not query or not query.strip():
            raise HTTPException(
                status_code=400,
                detail="Search 模式下，query 字段不能为空"
            )

        # Search 模式建议（不强制）：配置 include_domains
        include_domains = search_config.get('include_domains', [])
        if not include_domains:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                "💡 建议：Search 模式下配置 include_domains 可以提高搜索精准度。"
            )

    @staticmethod
    def suggest_optimal_config(
        crawl_url: Optional[str],
        search_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        建议最优配置（清理冗余字段）

        Args:
            crawl_url: 爬取URL
            search_config: 搜索配置

        Returns:
            优化后的 search_config
        """
        if crawl_url:
            # Crawl 模式：移除 include_domains（可选优化）
            optimized_config = search_config.copy()
            if 'include_domains' in optimized_config:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    "🔧 优化建议：Crawl 模式下，已自动忽略 include_domains 配置。"
                )
            return optimized_config
        else:
            # Search 模式：保留所有配置
            return search_config


def validate_task_creation(
    crawl_url: Optional[str],
    query: str,
    search_config: Dict[str, Any]
) -> None:
    """
    任务创建验证（主入口函数）

    Args:
        crawl_url: 爬取URL
        query: 搜索关键词
        search_config: 搜索配置

    Raises:
        HTTPException: 如果验证失败
    """
    validator = SearchTaskFieldValidator()

    # 1. 验证互斥关系（警告但不报错）
    validator.validate_crawl_url_and_include_domains(crawl_url, search_config)

    # 2. 验证模式字段完整性
    validator.validate_mode_fields(crawl_url, query, search_config)


def get_task_mode_description(
    crawl_url: Optional[str],
    search_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    获取任务模式描述（用于前端展示）

    Args:
        crawl_url: 爬取URL
        search_config: 搜索配置

    Returns:
        模式描述字典
    """
    include_domains = search_config.get('include_domains', [])

    if crawl_url:
        return {
            "mode": "crawl",
            "mode_display": "URL爬取模式",
            "description": f"直接爬取: {crawl_url}",
            "api_used": "Firecrawl Scrape API",
            "active_fields": ["crawl_url"],
            "ignored_fields": ["query", "include_domains"],
            "warning": "include_domains 在此模式下不生效" if include_domains else None
        }
    else:
        return {
            "mode": "search",
            "mode_display": "关键词搜索模式",
            "description": "基于关键词搜索多个来源",
            "api_used": "Firecrawl Search API",
            "active_fields": ["query", "include_domains"],
            "ignored_fields": ["crawl_url"],
            "warning": None
        }
