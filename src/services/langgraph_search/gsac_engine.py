"""gs-ai-crawl 搜索引擎封装

将 gs-ai-crawl 库包装为符合 SearchEngineAdapter 接口的引擎。

v4.19.0 - 集成 gs-ai-crawl
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config import settings

logger = logging.getLogger(__name__)


def _setup_gsac_env():
    """设置 gs-ai-crawl 需要的环境变量

    复用现有配置，避免重复配置。
    支持 openai, anthropic, custom_claude (第三方代理) 三种 LLM provider。
    """
    # Firecrawl API Key
    if settings.FIRECRAWL_API_KEY:
        os.environ.setdefault("GS_CRAWL_FIRECRAWL_API_KEY", settings.FIRECRAWL_API_KEY)

    # LLM 配置 - 根据 provider 设置
    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        os.environ.setdefault("GS_CRAWL_LLM_PROVIDER", "openai")
        os.environ.setdefault("GS_CRAWL_LLM_API_KEY", settings.OPENAI_API_KEY)
        os.environ.setdefault("GS_CRAWL_LLM_MODEL", settings.OPENAI_MODEL or "gpt-4o-mini")
    elif settings.LLM_PROVIDER == "claude" and settings.CLAUDE_API_KEY:
        # 检查是否使用自定义 Claude API (第三方代理)
        if settings.ANTHROPIC_BASE_URL:
            # 使用 custom_claude provider (第三方代理如 api.codeable.icu)
            os.environ.setdefault("GS_CRAWL_LLM_PROVIDER", "custom_claude")
            os.environ.setdefault("GS_CRAWL_CUSTOM_CLAUDE_BASE_URL", settings.ANTHROPIC_BASE_URL)
            os.environ.setdefault("GS_CRAWL_CUSTOM_CLAUDE_API_KEY", settings.CLAUDE_API_KEY)
            os.environ.setdefault("GS_CRAWL_CUSTOM_CLAUDE_MODEL", settings.CLAUDE_MODEL or "claude-sonnet-4-20250514")
            logger.info(f"[GSAC_ENV] 使用 custom_claude provider: {settings.ANTHROPIC_BASE_URL}")
        else:
            # 使用原生 Anthropic API
            os.environ.setdefault("GS_CRAWL_LLM_PROVIDER", "anthropic")
            os.environ.setdefault("GS_CRAWL_LLM_API_KEY", settings.CLAUDE_API_KEY)
            os.environ.setdefault("GS_CRAWL_LLM_MODEL", settings.CLAUDE_MODEL or "claude-3-haiku-20240307")

    logger.debug("[GSAC_ENV] 环境变量已设置")


# 初始化时设置环境变量
_setup_gsac_env()


class GSAICrawlEngine:
    """gs-ai-crawl 搜索引擎封装

    提供 SearchEngineAdapter 兼容的搜索接口。
    
    Example:
        engine = GSAICrawlEngine()
        result = await engine.search(
            query="Python web框架对比",
            user_id="test_user",
        )
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化引擎

        Args:
            config: 引擎配置字典，支持以下选项：
                - max_keywords: 最大关键词数量 (默认 5)
                - max_results_per_keyword: 每个关键词最大结果数 (默认 10)
                - enable_deep_scrape: 是否启用深度抓取 (默认 False)
                - max_scrape_urls: 深度抓取最大URL数 (默认 3)
                - similarity_threshold: 去重相似度阈值 (默认 0.8)
                - enable_summary: 是否生成摘要 (默认 True)
        """
        self.config = config or {}
        self._acrawl = None
        self._CrawlConfig = None
        logger.info(f"[GSAC_ENGINE] 初始化: {self.config}")

    def _lazy_import(self):
        """懒加载 gsac 模块"""
        if self._acrawl is None:
            from src.gsac import acrawl
            self._acrawl = acrawl
            logger.debug("[GSAC_ENGINE] gsac 模块已加载")

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        search_mode: str = "single",
        **options
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式 (single/multi)
            options: 其他配置选项
                - max_keywords: 最大关键词数量
                - max_results_per_keyword: 每个关键词的最大结果数
                - enable_deep_scrape: 是否启用深度抓取
                - max_scrape_urls: 深度抓取的最大URL数
                - similarity_threshold: 去重相似度阈值
                - enable_summary: 是否生成摘要

        Returns:
            标准化搜索结果:
            {
                "log_id": str,
                "query_text": str,
                "search_mode": str,
                "results": list,
                "engine_used": "gsac",
                "success": bool,
                "statistics": dict,
                "summary": str | None,
                "errors": list | None,
                "created_at": str,
            }
        """
        started_at = datetime.utcnow()

        logger.info(
            f"[GSAC_ENGINE] 搜索请求: query='{query[:50]}...', "
            f"user_id={user_id}, search_mode={search_mode}"
        )

        try:
            # 懒加载 gsac
            self._lazy_import()

            # 构建 acrawl 参数 (只传递 acrawl 支持的参数)
            acrawl_kwargs = {
                "max_keywords": options.get(
                    "max_keywords",
                    self.config.get("max_keywords", 5)
                ),
                "max_results_per_keyword": options.get(
                    "max_results_per_keyword",
                    self.config.get("max_results_per_keyword", 10)
                ),
                "enable_deep_scrape": options.get(
                    "enable_deep_scrape",
                    self.config.get("enable_deep_scrape", False)
                ),
                "max_scrape_urls": options.get(
                    "max_scrape_urls",
                    self.config.get("max_scrape_urls", 3)
                ),
                "similarity_threshold": options.get(
                    "similarity_threshold",
                    self.config.get("similarity_threshold", 0.8)
                ),
                "enable_summary": options.get(
                    "enable_summary",
                    self.config.get("enable_summary", True)
                ),
                "output_format": options.get(
                    "output_format",
                    self.config.get("output_format", "structured")
                ),
            }

            # 调用 gs-ai-crawl
            result = await self._acrawl(query, **acrawl_kwargs)

            # 标准化输出格式
            completed_at = datetime.utcnow()
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            return {
                "log_id": user_id or f"gsac_{hash(query) & 0xffffffff:08x}",
                "query_text": query,
                "search_mode": search_mode,
                "results": self._convert_results(result.results),
                "engine_used": "gsac",
                "success": True,
                "statistics": {
                    "total_results": result.total_found,
                    "keywords_used": result.keywords_used,
                    "execution_time": result.execution_time,
                    "duration_ms": duration_ms,
                },
                "summary": result.summary,
                "errors": result.errors,
                "created_at": completed_at.isoformat(),
            }

        except ImportError as e:
            logger.error(f"[GSAC_ENGINE] gsac 模块导入失败: {e}")
            return self._error_response(query, search_mode, user_id, f"gsac 模块不可用: {e}")
        except Exception as e:
            logger.error(f"[GSAC_ENGINE] 搜索失败: {e}", exc_info=True)
            return self._error_response(query, search_mode, user_id, str(e))

    def _convert_results(self, results: List[Any]) -> List[Dict[str, Any]]:
        """转换 SearchResult 为标准格式

        修复字段映射：
        - description -> snippet (符合 SearchResultItem.from_dict 期望)
        - keyword/source -> metadata

        Args:
            results: gs-ai-crawl SearchResult 列表

        Returns:
            标准格式的搜索结果列表
        """
        return [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.description,  # 映射 description -> snippet
                "content": r.content,
                "layer": r.layer,
                "score": r.score,
                "source_domain": r.source_domain,
                "published_date": r.published_date,
                "metadata": {
                    "keyword": r.keyword,
                    "source": r.source,
                },
            }
            for r in results
        ]

    def _error_response(
        self,
        query: str,
        search_mode: str,
        user_id: Optional[str],
        error: str,
    ) -> Dict[str, Any]:
        """生成错误响应"""
        return {
            "log_id": user_id or f"gsac_{hash(query) & 0xffffffff:08x}",
            "query_text": query,
            "search_mode": search_mode,
            "results": [],
            "engine_used": "gsac",
            "success": False,
            "error": error,
            "created_at": datetime.utcnow().isoformat(),
        }

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态

        Returns:
            引擎状态信息
        """
        try:
            from src import gsac
            version = gsac.__version__
            return {
                "engine": "gsac",
                "version": version,
                "available": True,
                "config": self.config,
            }
        except ImportError:
            return {
                "engine": "gsac",
                "available": False,
                "error": "gsac package not installed",
            }
