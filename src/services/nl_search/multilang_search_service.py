"""
多语言搜索服务

基于 Claude + Firecrawl Search 实现多语言 OSINT 搜索
支持中文、英语、日语、韩语四种语言的并行搜索和智能汇总

版本: v1.0.0
日期: 2025-12-23
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from src.infrastructure.llm.claude_client import ClaudeClient, create_claude_client
from src.services.nl_search.config import (
    nl_search_config,
    DEFAULT_LANGUAGES,
    get_supported_language_codes
)

logger = logging.getLogger(__name__)


@dataclass
class MultilangSearchConfig:
    """多语言搜索配置"""
    # 支持的语言列表 (使用集中配置的默认语言)
    languages: List[str] = field(default_factory=lambda: DEFAULT_LANGUAGES.copy())
    # 每种语言的搜索结果数
    results_per_language: int = 5
    # 是否启用内容抓取
    enable_scrape: bool = True
    # 搜索超时（秒）
    search_timeout: int = 90
    # Claude 汇总最大 token
    summary_max_tokens: int = 2000


class FirecrawlSearchClient:
    """Firecrawl Search 客户端"""

    def __init__(self, api_key: str, base_url: str = "https://api.firecrawl.dev/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

    async def search(
        self,
        query: str,
        lang: str = "en",
        limit: int = 5,
        scrape: bool = True
    ) -> List[Dict[str, Any]]:
        """
        执行搜索

        Args:
            query: 搜索查询
            lang: 语言代码
            limit: 结果数量限制
            scrape: 是否抓取页面内容

        Returns:
            搜索结果列表
        """
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        body = {
            "query": query,
            "limit": limit,
            "lang": lang
        }

        if scrape:
            body["scrapeOptions"] = {
                "formats": ["markdown"],
                "onlyMainContent": True
            }

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=body
                )

                if response.status_code != 200:
                    logger.warning(f"搜索请求失败: {response.status_code} - {response.text[:200]}")
                    return []

                data = response.json().get("data", [])

                # 处理不同的响应格式
                if isinstance(data, dict):
                    return data.get("web", [])
                return data if isinstance(data, list) else []

        except Exception as e:
            logger.error(f"Firecrawl 搜索失败 ({lang}): {e}")
            return []

    async def search_multilang(
        self,
        queries: Dict[str, str],
        limit: int = 5,
        scrape: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        并行多语言搜索

        Args:
            queries: 语言代码 -> 查询文本 的映射
            limit: 每种语言的结果数限制
            scrape: 是否抓取页面内容

        Returns:
            语言代码 -> 搜索结果列表 的映射
        """
        tasks = []
        langs = []

        for lang, query in queries.items():
            tasks.append(self.search(query, lang, limit, scrape))
            langs.append(lang)

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for lang, result in zip(langs, results_list):
            if isinstance(result, Exception):
                logger.error(f"搜索失败 ({lang}): {result}")
                results[lang] = []
            else:
                results[lang] = result

        return results


class MultilangSearchService:
    """
    多语言搜索服务

    功能:
    1. 使用 Claude 生成多语言搜索查询
    2. 使用 Firecrawl 并行搜索多种语言
    3. 使用 Claude 汇总分析多语言结果

    使用示例:
        service = MultilangSearchService()
        result = await service.search("从日本2025防卫白书看东亚安全趋势")
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        firecrawl_api_key: Optional[str] = None,
        config: Optional[MultilangSearchConfig] = None
    ):
        """
        初始化服务

        Args:
            claude_client: Claude 客户端实例（可选，默认自动创建）
            firecrawl_api_key: Firecrawl API Key（可选，从环境变量读取）
            config: 多语言搜索配置
        """
        import os

        # 初始化 Claude 客户端
        self.claude = claude_client or create_claude_client()

        # 初始化 Firecrawl 客户端
        api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY", "")
        if not api_key:
            logger.warning("Firecrawl API Key 未配置")
        self.firecrawl = FirecrawlSearchClient(api_key)

        # 配置
        self.config = config or MultilangSearchConfig()

        logger.info(
            f"MultilangSearchService 初始化完成 "
            f"(languages={self.config.languages}, "
            f"results_per_lang={self.config.results_per_language})"
        )

    async def search(
        self,
        query: str,
        languages: Optional[List[str]] = None,
        include_summary: bool = True
    ) -> Dict[str, Any]:
        """
        执行多语言搜索

        Args:
            query: 用户查询文本
            languages: 目标语言列表（默认使用配置）
            include_summary: 是否生成 Claude 汇总

        Returns:
            包含搜索结果和汇总的字典:
            {
                "query": str,
                "timestamp": str,
                "multilang_queries": Dict[str, str],
                "results": Dict[str, List[Dict]],
                "result_counts": Dict[str, int],
                "summary": str (可选),
                "execution_time_ms": int
            }
        """
        start_time = datetime.now()

        if not query or not query.strip():
            raise ValueError("查询文本不能为空")

        query = query.strip()
        target_languages = languages or self.config.languages

        logger.info(f"开始多语言搜索: {query[:50]}... (languages={target_languages})")

        result = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "steps": []
        }

        try:
            # Step 1: Claude 生成多语言查询
            step_start = datetime.now()
            multilang_queries = await self.claude.generate_multilang_queries(
                query,
                languages=target_languages
            )
            step_time = (datetime.now() - step_start).total_seconds()

            result["multilang_queries"] = multilang_queries
            result["steps"].append({
                "step": "generate_queries",
                "time_s": step_time,
                "queries": multilang_queries
            })

            logger.info(f"多语言查询生成完成 ({step_time:.1f}s): {list(multilang_queries.keys())}")

            # Step 2: Firecrawl 并行搜索
            step_start = datetime.now()
            search_results = await self.firecrawl.search_multilang(
                queries=multilang_queries,
                limit=self.config.results_per_language,
                scrape=self.config.enable_scrape
            )
            step_time = (datetime.now() - step_start).total_seconds()

            result["results"] = search_results
            result["result_counts"] = {
                lang: len(items) for lang, items in search_results.items()
            }
            result["steps"].append({
                "step": "multilang_search",
                "time_s": step_time,
                "result_counts": result["result_counts"]
            })

            total_results = sum(result["result_counts"].values())
            logger.info(f"多语言搜索完成 ({step_time:.1f}s): 共 {total_results} 条结果")

            # Step 3: Claude 汇总分析（可选）
            if include_summary and total_results > 0:
                step_start = datetime.now()
                summary = await self.claude.summarize_multilang_results(
                    query,
                    search_results
                )
                step_time = (datetime.now() - step_start).total_seconds()

                result["summary"] = summary
                result["steps"].append({
                    "step": "summarize",
                    "time_s": step_time
                })

                logger.info(f"汇总分析完成 ({step_time:.1f}s)")

            # 计算总耗时
            total_time = (datetime.now() - start_time).total_seconds()
            result["execution_time_ms"] = int(total_time * 1000)

            logger.info(
                f"多语言搜索完成: "
                f"query='{query[:30]}...', "
                f"languages={len(multilang_queries)}, "
                f"results={total_results}, "
                f"time={total_time:.1f}s"
            )

            return result

        except Exception as e:
            logger.error(f"多语言搜索失败: {e}", exc_info=True)
            raise

    async def search_simple(
        self,
        query: str,
        languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        简化搜索（不生成汇总）

        Args:
            query: 用户查询文本
            languages: 目标语言列表

        Returns:
            搜索结果字典（不含汇总）
        """
        return await self.search(
            query=query,
            languages=languages,
            include_summary=False
        )

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        分析查询意图

        Args:
            query: 用户查询文本

        Returns:
            查询分析结果
        """
        return await self.claude.parse_query(query)

    async def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态

        Returns:
            服务状态信息
        """
        import os

        return {
            "service": "MultilangSearchService",
            "version": "1.0.0",
            "claude_configured": bool(self.claude.config.api_key),
            "firecrawl_configured": bool(self.firecrawl.api_key),
            "supported_languages": self.config.languages,
            "results_per_language": self.config.results_per_language,
            "scrape_enabled": self.config.enable_scrape
        }


# 工厂函数
def create_multilang_search_service(
    claude_base_url: Optional[str] = None,
    claude_api_key: Optional[str] = None,
    claude_model: Optional[str] = None,
    firecrawl_api_key: Optional[str] = None,
    languages: Optional[List[str]] = None,
    results_per_language: int = 5
) -> MultilangSearchService:
    """
    创建多语言搜索服务

    Args:
        claude_base_url: Claude API Base URL
        claude_api_key: Claude API Key
        claude_model: Claude 模型名称
        firecrawl_api_key: Firecrawl API Key
        languages: 支持的语言列表
        results_per_language: 每种语言的结果数

    Returns:
        MultilangSearchService 实例
    """
    # 创建 Claude 客户端
    claude = create_claude_client(
        base_url=claude_base_url,
        api_key=claude_api_key,
        model=claude_model
    )

    # 创建配置
    config = MultilangSearchConfig(
        languages=languages or ["zh", "en", "ja", "ko"],
        results_per_language=results_per_language
    )

    return MultilangSearchService(
        claude_client=claude,
        firecrawl_api_key=firecrawl_api_key,
        config=config
    )


# 全局服务实例（延迟初始化）
_multilang_search_service: Optional[MultilangSearchService] = None


def get_multilang_search_service() -> MultilangSearchService:
    """获取多语言搜索服务单例"""
    global _multilang_search_service

    if _multilang_search_service is None:
        _multilang_search_service = create_multilang_search_service()

    return _multilang_search_service
