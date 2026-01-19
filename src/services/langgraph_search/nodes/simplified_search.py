"""简化搜索节点 (v4.15.0)

执行 Firecrawl 搜索，读取 firecrawl_search_config 字段。

支持的架构流程：
- v4.15.0 两步架构:
  START → keyword_generator → firecrawl_config → simplified_search → output → END

功能：
1. 读取 firecrawl_search_config 配置列表 (query, limit, tier)
2. 执行 Firecrawl 搜索（每个配置一次调用）
3. URL 去重和结果聚合

v4.15.0 更新：
- 添加 sources: ["web", "news"] 参数
- 同时搜索 web 和 news 源，提高新闻报道覆盖率

v4.14.0 更新：
- 移除 location 参数
- 简化配置结构
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from firecrawl import FirecrawlApp

from ..state import SearchState, SearchResult
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


class SimplifiedSearchNode:
    """简化搜索节点 (v4.15.0)

    执行 Firecrawl 搜索，读取 state.firecrawl_search_config 配置列表。

    输入字段：
    - firecrawl_search_config: List[Dict] - 搜索配置列表
      每个配置包含: query, limit, tier, tbs (可选), scrapeOptions (可选)

    输出字段：
    - search_results: List[Dict] - 搜索结果
    - aggregated_results: List[Dict] - 聚合结果（OutputNode 需要）
    - statistics: Dict - 统计信息

    v4.15.0: 默认使用 sources=["web", "news"] 同时搜索网页和新闻
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        firecrawl_client: Optional[FirecrawlApp] = None,
    ):
        """初始化简化搜索节点

        Args:
            config: LangGraph 搜索配置
            firecrawl_client: Firecrawl 客户端
        """
        self.config = config or LangGraphSearchConfig()

        if firecrawl_client:
            self.firecrawl_client = firecrawl_client
        else:
            # 尝试创建 Firecrawl 客户端
            api_key = self.config.firecrawl_api_key
            if api_key:
                self.firecrawl_client = FirecrawlApp(api_key=api_key)
                logger.info("[SimplifiedSearch] Firecrawl client initialized")
            else:
                self.firecrawl_client = None
                logger.warning("[SimplifiedSearch] Firecrawl API key not configured")

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行简化搜索

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        query = state.get("query", "")

        # 获取 LLM 生成的 Firecrawl 配置
        firecrawl_configs = state.get("firecrawl_search_config", [])

        if not firecrawl_configs:
            logger.warning(f"[user:{user_id}] No firecrawl_search_config found, using fallback")
            firecrawl_configs = [{"query": query, "lang": "en", "limit": 20}]

        logger.info(
            f"[user:{user_id}] SimplifiedSearch starting: "
            f"{len(firecrawl_configs)} configs"
        )

        # 执行搜索
        all_results = []
        search_stats = {
            "total_configs": len(firecrawl_configs),
            "successful_searches": 0,
            "failed_searches": 0,
            "total_raw_results": 0,
        }

        for i, config in enumerate(firecrawl_configs):
            try:
                search_query = config.get("query", query)

                logger.info(
                    f"[user:{user_id}] Executing search {i+1}/{len(firecrawl_configs)}: "
                    f"query='{search_query[:50]}...'"
                )

                results = self._execute_firecrawl_search(config, user_id)
                all_results.extend(results)

                search_stats["successful_searches"] += 1
                search_stats["total_raw_results"] += len(results)

                logger.info(
                    f"[user:{user_id}] Search {i+1} completed: {len(results)} results"
                )

            except Exception as e:
                logger.error(
                    f"[user:{user_id}] Search {i+1} failed: {e}"
                )
                search_stats["failed_searches"] += 1

        # URL 去重
        unique_results = self._deduplicate(all_results, user_id)

        search_stats["unique_results"] = len(unique_results)
        search_stats["duplicates_removed"] = len(all_results) - len(unique_results)

        logger.info(
            f"[user:{user_id}] SimplifiedSearch complete: "
            f"raw={search_stats['total_raw_results']} → unique={len(unique_results)}"
        )

        return {
            # v4.10.0: 同时设置多个字段以兼容不同节点
            "search_results": unique_results,
            "aggregated_results": unique_results,  # OutputNode 期望这个字段
            # 统计信息
            "statistics": {
                **state.get("statistics", {}),
                "simplified_search": search_stats,
            },
            "status": "running",
        }

    def _execute_firecrawl_search(
        self,
        config: Dict[str, Any],
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """执行单次 Firecrawl 搜索

        Args:
            config: Firecrawl 搜索配置
            user_id: 用户ID

        Returns:
            搜索结果列表
        """
        if self.firecrawl_client is None:
            raise RuntimeError(
                "Firecrawl 客户端未配置，请检查 FIRECRAWL_API_KEY 环境变量"
            )

        # 构建搜索参数
        # v4.17.0: 使用配置化的 limit，替代硬编码的 20
        limit = min(config.get("limit", self.config.search_results_per_query), self.config.search_results_per_query)
        search_params = {
            "query": config.get("query", ""),
            "limit": limit,
        }

        # v4.15.0: 添加 sources 参数，同时搜索 web 和 news 源
        # 这样可以更好地找到新闻报道（如 BBC、CNN 等）
        search_params["sources"] = ["web", "news"]

        # 添加时间范围
        tbs = config.get("tbs")
        if tbs:
            search_params["tbs"] = tbs

        # 添加内容抓取选项
        scrape_options = config.get("scrapeOptions", {})
        if scrape_options:
            # Firecrawl SDK 使用 snake_case
            search_params["scrape_options"] = {
                "formats": scrape_options.get("formats", ["markdown", "html"]),
                "only_main_content": scrape_options.get("onlyMainContent", True),
            }
        else:
            # 默认抓取选项
            search_params["scrape_options"] = {
                "formats": ["markdown", "html"],
                "only_main_content": True,
            }

        logger.debug(f"[user:{user_id}] Firecrawl params: {search_params}")

        # 调用 Firecrawl API
        response = self.firecrawl_client.search(**search_params)

        # v4.10.0: 调试日志 - 显示响应结构
        logger.debug(f"[user:{user_id}] Firecrawl response type: {type(response)}")
        logger.debug(f"[user:{user_id}] Firecrawl response attrs: {dir(response)}")
        if hasattr(response, 'data'):
            logger.debug(f"[user:{user_id}] Firecrawl response.data: {len(response.data) if response.data else 0} items")

        # 解析响应
        results = []

        # v4.10.0: 新增 - 处理 data 字段（Firecrawl v1 响应格式）
        if hasattr(response, 'data') and response.data:
            logger.info(f"[user:{user_id}] Processing {len(response.data)} results from Firecrawl data")
            for item in response.data:
                result = self._parse_firecrawl_item(item)
                if result:
                    results.append(result)

        # 处理 news 结果
        if hasattr(response, 'news') and response.news:
            logger.debug(f"[user:{user_id}] Processing {len(response.news)} news results")
            for item in response.news:
                result = self._parse_firecrawl_item(item)
                if result:
                    results.append(result)

        # 处理 web 结果
        if hasattr(response, 'web') and response.web:
            logger.debug(f"[user:{user_id}] Processing {len(response.web)} web results")
            for item in response.web:
                result = self._parse_firecrawl_item(item)
                if result:
                    results.append(result)

        return results

    def _parse_firecrawl_item(
        self,
        item: Any,
    ) -> Optional[Dict[str, Any]]:
        """解析 Firecrawl 响应项

        支持两种类型：
        - Document 类型: URL/title 在 metadata 中
        - SearchResult 类型: URL/title 直接在属性上

        Args:
            item: Firecrawl 响应项

        Returns:
            解析后的结果字典，或 None
        """
        result = {}

        # 检查是否是 Document 类型（有 metadata 属性）
        if hasattr(item, 'metadata') and item.metadata:
            metadata = item.metadata
            result = {
                "url": getattr(metadata, 'url', '') or getattr(metadata, 'source_url', ''),
                "title": getattr(metadata, 'title', ''),
                "description": getattr(metadata, 'description', ''),
                "markdown_content": getattr(item, 'markdown', ''),
                "html_content": getattr(item, 'html', ''),
                "published_date": getattr(metadata, 'published_time', None),
                "source": self._extract_domain(
                    getattr(metadata, 'url', '') or getattr(metadata, 'source_url', '')
                ),
            }
        else:
            # SearchResult 类型
            result = {
                "url": getattr(item, 'url', ''),
                "title": getattr(item, 'title', ''),
                "description": getattr(item, 'snippet', '') or getattr(item, 'description', ''),
                "markdown_content": getattr(item, 'markdown', ''),
                "html_content": getattr(item, 'html', ''),
                "published_date": getattr(item, 'date', None) or getattr(item, 'published_date', None),
                "source": self._extract_domain(getattr(item, 'url', '')),
            }

        # 只返回有效结果（至少有 URL 或 title）
        if result.get("url") or result.get("title"):
            # 添加统一层标识（简化架构只有一层）
            result["layer"] = 0
            result["layer_name"] = "统一搜索"
            return result

        return None

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名

        Args:
            url: 完整 URL

        Returns:
            域名字符串
        """
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or ""
        except Exception:
            return ""

    def _deduplicate(
        self,
        results: List[Dict[str, Any]],
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """URL 去重

        Args:
            results: 原始结果列表
            user_id: 用户ID

        Returns:
            去重后的结果列表
        """
        seen_urls = set()
        unique_results = []

        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        duplicates = len(results) - len(unique_results)
        if duplicates > 0:
            logger.debug(
                f"[user:{user_id}] Deduplicated: {len(results)} → {len(unique_results)} "
                f"(removed {duplicates})"
            )

        return unique_results


def create_simplified_search_node(
    config: Optional[LangGraphSearchConfig] = None,
    firecrawl_client: Optional[FirecrawlApp] = None,
) -> SimplifiedSearchNode:
    """创建简化搜索节点的工厂函数

    Args:
        config: LangGraph 搜索配置
        firecrawl_client: Firecrawl 客户端

    Returns:
        SimplifiedSearchNode 实例
    """
    return SimplifiedSearchNode(
        config=config,
        firecrawl_client=firecrawl_client,
    )
