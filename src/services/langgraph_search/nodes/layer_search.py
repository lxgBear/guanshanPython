"""分层搜索节点

执行 5 层分层搜索策略：
- Layer 0: 官方来源
- Layer 1: 主流媒体
- Layer 2: 周边地区
- Layer 3: 国际权威
- Layer 4: 智库分析
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..state import (
    SearchState,
    SearchResult,
    LayerSearchResult,
    SearchLayer,
    LAYER_NAMES,
)
from ..config import LangGraphSearchConfig
from ..utils.url_utils import extract_domain
from ..languages import get_media_domains, get_language_name

logger = logging.getLogger(__name__)


class LayerSearchNode:
    """分层搜索节点

    根据层级配置执行搜索，支持:
    - 动态域名限制
    - 并行搜索执行
    - 结果质量评分
    """

    def __init__(
        self,
        layer: int,
        config: Optional[LangGraphSearchConfig] = None,
        firecrawl_client: Optional[Any] = None,
    ):
        """初始化分层搜索节点

        Args:
            layer: 搜索层级 (0-4)
            config: LangGraph 搜索配置
            firecrawl_client: Firecrawl 客户端（可选）
        """
        self.layer = layer
        self.config = config or LangGraphSearchConfig()
        self.firecrawl_client = firecrawl_client

        # 获取层级信息
        self.layer_enum = SearchLayer(layer)
        self.layer_name = LAYER_NAMES.get(self.layer_enum, f"Layer {layer}")

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行分层搜索

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        time_range = state.get("time_range", "qdr:m")
        discovered_sources = state.get("discovered_sources", {})

        # v4.5.0: 优先从 layer_search_config 获取该层级配置
        layer_config = self._get_layer_config(state)

        # v4.5.0: 获取 keyword_combinations (4层组合法)
        analysis = state.get("analysis", {})
        keyword_combinations = analysis.get("keyword_combinations", [])

        # 从层级配置中获取语言和关键词（如有）
        if layer_config and layer_config.get("enabled", True):
            layer_language = layer_config.get("language", "")
            layer_keywords = layer_config.get("keywords", [])
            target_languages = [layer_language] if layer_language else state.get("target_languages", ["zh", "en"])
            keywords = layer_keywords if layer_keywords else state.get("keywords", [])
            keywords_en = layer_keywords if layer_language == "en" else state.get("keywords_en", [])
            logger.info(
                f"[user:{user_id}] Layer {self.layer} using layer_search_config: "
                f"language={layer_language}, keywords={layer_keywords[:3] if layer_keywords else []}"
            )
        else:
            # 降级: 使用旧的全局配置
            target_languages = state.get("target_languages", ["zh", "en"])
            keywords = state.get("keywords", [])
            keywords_en = analysis.get("keywords_en", []) or state.get("keywords_en", [])

        start_time = time.time()

        try:
            logger.info(
                f"[user:{user_id}] Starting layer {self.layer} ({self.layer_name}) search, "
                f"target_languages={target_languages}"
            )

            # 获取该层级的搜索域名
            domains = self._get_layer_domains(state, target_languages)

            if not domains and self.layer in [0, 1]:
                # Layer 0 和 1 需要域名限制
                logger.warning(
                    f"[user:{user_id}] No domains for layer {self.layer}, skipping"
                )
                return self._create_empty_result(start_time)

            # v4.5.0: 优先使用 4 层组合法的 keyword_combinations
            # 如果 Claude 生成了 keyword_combinations，直接使用；否则降级到旧方法
            if keyword_combinations:
                queries = self._build_optimized_queries(
                    keyword_combinations=keyword_combinations,
                    domains=domains,
                    layer=self.layer,
                )
                logger.info(
                    f"[user:{user_id}] Using v4.5.0 optimized queries from keyword_combinations, "
                    f"count={len(keyword_combinations)}"
                )
            else:
                # 降级: 使用旧的多语言查询方法
                queries = self._build_multilingual_queries(
                    keywords=keywords,
                    keywords_en=keywords_en,
                    domains=domains,
                    target_languages=target_languages,
                )

            # 执行搜索
            results = self._execute_searches(queries, domains, time_range, user_id, target_languages)

            # 计算执行时间
            execution_time_ms = int((time.time() - start_time) * 1000)

            # 创建层级结果
            layer_result = LayerSearchResult(
                layer=self.layer,
                layer_name=self.layer_name,
                queries_executed=queries,
                results=results,
                execution_time_ms=execution_time_ms,
            )

            logger.info(
                f"[user:{user_id}] Layer {self.layer} complete: "
                f"{len(results)} results in {execution_time_ms}ms"
            )

            return {
                "layer_results": {self.layer: layer_result.to_dict()},
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Layer {self.layer} search failed: {e}")
            execution_time_ms = int((time.time() - start_time) * 1000)

            layer_result = LayerSearchResult(
                layer=self.layer,
                layer_name=self.layer_name,
                queries_executed=[],
                results=[],
                execution_time_ms=execution_time_ms,
                error=str(e),
            )

            return {
                "layer_results": {self.layer: layer_result.to_dict()},
            }

    def _get_layer_config(self, state: SearchState) -> Optional[Dict[str, Any]]:
        """获取该层级的搜索配置 (v4.4.0)

        从 layer_search_config 中获取当前层级的语言和关键词配置。

        Args:
            state: 当前搜索状态

        Returns:
            该层级的配置字典，包含 language, keywords, enabled 等字段
            如果没有配置则返回 None
        """
        layer_search_config = state.get("layer_search_config", {})

        if not layer_search_config:
            return None

        # 层级映射: 将 layer 数字映射到配置键
        layer_key_map = {
            0: "layer_0_1",   # 官方来源与主流媒体共享配置
            1: "layer_0_1",   # 官方来源与主流媒体共享配置
            2: "layer_2",     # 周边地区
            3: "layer_3",     # 国际权威
            4: "layer_4",     # 智库分析
        }

        config_key = layer_key_map.get(self.layer)
        if not config_key:
            return None

        layer_config = layer_search_config.get(config_key, {})

        if layer_config:
            logger.debug(
                f"Layer {self.layer} config from layer_search_config[{config_key}]: "
                f"language={layer_config.get('language')}, "
                f"keywords_count={len(layer_config.get('keywords', []))}"
            )

        return layer_config if layer_config else None

    def _get_layer_domains(
        self,
        state: SearchState,
        target_languages: Optional[List[str]] = None,
    ) -> List[str]:
        """获取该层级的搜索域名

        v4.3.1: 支持根据目标语言动态获取媒体域名

        Args:
            state: 当前搜索状态
            target_languages: 目标语言列表

        Returns:
            域名列表
        """
        discovered_sources = state.get("discovered_sources", {})
        domains = []

        if self.layer == 0:
            # Layer 0: 官方来源 (政府 + 机构)
            for party_name, source_data in discovered_sources.items():
                domains.extend(source_data.get("official_gov", []))
                domains.extend(source_data.get("official_agency", []))

        elif self.layer == 1:
            # Layer 1: 主流媒体
            # v4.3.1: 根据目标语言获取对应的主流媒体
            for party_name, source_data in discovered_sources.items():
                domains.extend(source_data.get("local_mainstream", []))

            # 如果有目标语言，添加对应语言的媒体域名
            if target_languages:
                for lang in target_languages:
                    lang_domains = get_media_domains(lang)
                    if lang_domains:
                        domains.extend(lang_domains[:5])  # 每种语言最多5个域名

        elif self.layer == 2:
            # Layer 2: 周边地区
            # v4.3.1: 根据目标语言获取对应的媒体
            if target_languages:
                for lang in target_languages:
                    lang_domains = get_media_domains(lang)
                    if lang_domains:
                        domains.extend(lang_domains[:3])

        elif self.layer == 3:
            # Layer 3: 国际权威媒体
            domains = self.config.international_media.copy()
            # v4.3.1: 补充目标语言的国际媒体
            if target_languages and "en" not in target_languages:
                # 非英语搜索时，添加目标语言媒体
                for lang in target_languages[:3]:
                    lang_domains = get_media_domains(lang)
                    if lang_domains:
                        domains.extend(lang_domains[:3])

        elif self.layer == 4:
            # Layer 4: 智库分析
            domains = self.config.think_tanks.copy()

        # 限制域名数量
        if len(domains) > self.config.max_domains_per_layer:
            domains = domains[: self.config.max_domains_per_layer]

        return list(set(domains))  # 去重

    def _build_queries(
        self,
        keywords: List[str],
        domains: List[str],
    ) -> List[str]:
        """构建搜索查询 (保留兼容性)

        v4.6.0: 过滤用户意图词

        Args:
            keywords: 关键词列表
            domains: 域名列表

        Returns:
            查询列表
        """
        if not keywords:
            return []

        # v4.6.0: 过滤意图词
        intent_words = [
            "西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体", "海外媒体",
            "西方国家", "美英", "欧美", "西方世界", "西方国家报道", "欧美新闻",
            "亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体", "亚洲国家", "邻国媒体",
            "亚洲视角", "东亚报道", "当地媒体", "国内媒体", "中国媒体", "中文媒体",
            "本地媒体", "欧洲媒体", "欧盟媒体", "欧洲新闻", "欧洲报道", "中东媒体",
            "阿拉伯媒体", "中东新闻", "拉美媒体", "拉丁美洲媒体", "西班牙语媒体",
            "葡萄牙语媒体", "报道", "反应", "整理", "检索", "搜索", "查找",
        ]

        # 过滤关键词
        filtered_keywords = []
        for kw in keywords:
            if kw not in intent_words:
                # 同时检查关键词是否包含意图词
                is_intent = any(intent in kw for intent in intent_words)
                if not is_intent:
                    filtered_keywords.append(kw)

        if not filtered_keywords:
            return []

        # 合并过滤后的关键词
        base_query = " ".join(filtered_keywords[:5])  # 最多使用 5 个关键词

        queries = []

        if domains:
            # 为每个域名创建查询
            for domain in domains[:5]:  # 最多 5 个域名
                queries.append(f"site:{domain} {base_query}")
        else:
            # 无域名限制的通用查询
            queries.append(base_query)

        return queries

    def _build_multilingual_queries(
        self,
        keywords: List[str],
        keywords_en: List[str],
        domains: List[str],
        target_languages: List[str],
    ) -> List[str]:
        """构建多语言搜索查询 (v4.3.1)

        v4.6.0: 在构建查询时过滤掉用户意图词

        根据目标语言生成多种语言的搜索查询，确保能获取到不同语言的媒体内容。

        Args:
            keywords: 中文关键词列表
            keywords_en: 英文关键词列表
            domains: 域名列表
            target_languages: 目标语言列表

        Returns:
            多语言查询列表
        """
        # v4.6.0: 意图词过滤 - 过滤掉不应作为搜索词的意图词
        intent_words_zh = [
            "西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体", "海外媒体",
            "西方国家", "美英", "欧美", "西方世界", "西方国家报道", "欧美新闻",
            "亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体", "亚洲国家", "邻国媒体",
            "亚洲视角", "东亚报道", "当地媒体", "国内媒体", "中国媒体", "中文媒体",
            "本地媒体", "欧洲媒体", "欧盟媒体", "欧洲新闻", "欧洲报道", "中东媒体",
            "阿拉伯媒体", "中东新闻", "拉美媒体", "拉丁美洲媒体", "西班牙语媒体",
            "葡萄牙语媒体", "报道", "反应", "整理", "检索", "搜索", "查找",
        ]

        intent_words_en = [
            "western media", "western news", "international media", "overseas media",
            "western countries", "us european", "western world", "asian media", "asia news",
            "east asian media", "asian perspective", "domestic media", "chinese media",
            "local media", "european media", "eu media", "europe news", "middle east media",
            "arab media", "middle east news", "latin american media", "hispanic media",
            "report", "coverage", "reaction", "response", "collect", "search", "find",
        ]

        # 过滤中文关键词
        filtered_keywords = []
        for kw in keywords:
            if kw not in intent_words_zh:
                # 同时检查关键词是否包含意图词
                is_intent = any(intent in kw for intent in intent_words_zh)
                if not is_intent:
                    filtered_keywords.append(kw)

        # 过滤英文关键词
        filtered_keywords_en = []
        for kw in keywords_en:
            if kw.lower() not in intent_words_en:
                # 同时检查关键词是否包含意图词
                kw_lower = kw.lower()
                is_intent = any(intent.lower() in kw_lower for intent in intent_words_en)
                if not is_intent:
                    filtered_keywords_en.append(kw)

        queries = []

        if not filtered_keywords and not filtered_keywords_en:
            return []

        # 构建中文查询（使用过滤后的关键词）
        zh_query = " ".join(filtered_keywords[:5]) if filtered_keywords else ""

        # 构建英文查询（使用过滤后的关键词）
        en_query = " ".join(filtered_keywords_en[:5]) if filtered_keywords_en else ""

        # 如果没有英文关键词但目标语言包含英语，使用中文关键词
        if not en_query and "en" in target_languages:
            en_query = zh_query

        # 判断是否需要多语言搜索
        is_multilingual = len(target_languages) > 1 or "zh" not in target_languages

        if is_multilingual:
            logger.info(
                f"Building multilingual queries for languages: {target_languages}, "
                f"zh_keywords={filtered_keywords[:3]}, en_keywords={filtered_keywords_en[:3]}"
            )

        # 根据目标语言构建查询
        if domains:
            # 有域名限制时
            for domain in domains[:10]:  # 多语言时增加域名数量
                # 优先使用英文查询（对国际媒体更有效）
                if en_query and any(lang in ["en", "fr", "de", "es", "it", "pt"] for lang in target_languages):
                    queries.append(f"site:{domain} {en_query}")
                # 也添加中文查询（对中文媒体有效）
                if zh_query and "zh" in target_languages:
                    queries.append(f"site:{domain} {zh_query}")
                # 如果只有中文关键词但目标是其他语言，仍使用中文查询
                if not en_query and zh_query:
                    queries.append(f"site:{domain} {zh_query}")
        else:
            # 无域名限制时
            if en_query:
                queries.append(en_query)
            if zh_query and zh_query != en_query:
                queries.append(zh_query)

        # 去重并限制查询数量
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        # 限制查询总数（避免过多API调用）
        max_queries = 15 if is_multilingual else 10
        return unique_queries[:max_queries]

    def _build_optimized_queries(
        self,
        keyword_combinations: List[Dict[str, Any]],
        domains: List[str],
        layer: int,
    ) -> List[str]:
        """构建优化的搜索查询 (v4.5.0: 4层组合法)

        根据最佳实践文档优化查询构建策略：
        1. 每个关键词组合先执行无域名查询（发现更多来源）
        2. 再执行精简的 site: 查询（精确匹配）

        Args:
            keyword_combinations: Claude 生成的 4 层关键词组合
            domains: 域名列表
            layer: 当前搜索层级

        Returns:
            优化的查询列表
        """
        queries = []

        if not keyword_combinations:
            return queries

        logger.info(
            f"[BUILD_OPTIMIZED_QUERIES] layer={layer}, "
            f"combinations={len(keyword_combinations)}, "
            f"domains={len(domains)}"
        )

        for combo in keyword_combinations:
            query_text = combo.get("query", "")
            if not query_text:
                continue

            # 1. 无域名限制的通用查询（最重要！）
            # 这是 v4.5.0 的核心改进 - 先执行无限制查询发现更多来源
            queries.append(query_text)
            logger.debug(f"  [通用查询] {query_text[:80]}...")

            # 2. 有域名限制的精确查询（精简关键词）
            # 只取前 2 个核心词 + site: 限制
            words = query_text.split()
            if len(words) >= 2:
                core_query = " ".join(words[:2])  # 只用前2个核心词

                # 根据层级决定使用哪些域名
                # Layer 3 (国际权威) 使用所有可用域名
                # 其他层级限制域名数量
                max_domains = 10 if layer == 3 else 5
                for domain in domains[:max_domains]:
                    queries.append(f"site:{domain} {core_query}")

        # 去重并限制总数
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        # v4.5.0: 根据层级调整最大查询数
        # Layer 3 (国际权威) 可以有更多查询
        max_queries = 20 if layer == 3 else 15

        logger.info(
            f"[BUILD_OPTIMIZED_QUERIES] generated {len(unique_queries)} queries "
            f"(max={max_queries})"
        )

        return unique_queries[:max_queries]

    def _execute_searches(
        self,
        queries: List[str],
        domains: List[str],
        time_range: str,
        user_id: str,
        target_languages: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """执行搜索

        v4.3.1: 支持目标语言参数

        Args:
            queries: 查询列表
            domains: 域名列表
            time_range: 时间范围
            user_id: 用户ID
            target_languages: 目标语言列表

        Returns:
            搜索结果列表
        """
        all_results = []
        target_languages = target_languages or ["zh", "en"]

        for query in queries:
            try:
                # 调用 Firecrawl 搜索 API
                raw_results = self._call_firecrawl_search(
                    query=query,
                    time_range=time_range,
                    num_results=self.config.results_per_query,
                    target_languages=target_languages,
                )

                # 转换为 SearchResult
                for i, raw in enumerate(raw_results):
                    result = self._convert_to_search_result(raw, i, target_languages)
                    all_results.append(result)

            except Exception as e:
                logger.warning(
                    f"[user:{user_id}] Search query failed: {query[:50]}... - {e}"
                )
                continue

        return all_results

    def _call_firecrawl_search(
        self,
        query: str,
        time_range: str,
        num_results: int,
        target_languages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """调用 Firecrawl 搜索 API

        v4.3.1: 支持目标语言参数

        Args:
            query: 搜索查询
            time_range: 时间范围
            num_results: 结果数量
            target_languages: 目标语言列表

        Returns:
            原始搜索结果
        """
        if self.firecrawl_client is None:
            # 如果没有客户端，返回空结果
            logger.error(
                f"[FIRECRAWL_CLIENT_MISSING] layer={self.layer}, "
                f"query='{query[:50]}...', "
                f"原因: Firecrawl客户端未配置，请检查FIRECRAWL_API_KEY环境变量"
            )
            return []

        try:
            # 构建搜索参数 (Firecrawl SDK v2 使用关键字参数)
            # v4.5.0: 根据最佳实践优化参数
            search_params = {
                "query": query,
                "limit": min(num_results, 10),  # v4.5.0: 限制为10以提高质量
                "sources": ["news", "web"],  # v4.5.0: 同时搜索新闻和网页
            }

            # 添加时间范围参数
            if time_range:
                search_params["tbs"] = time_range

            # v4.3.2: 移除 lang 参数 - Firecrawl SDK 不支持
            # 多语言搜索通过以下方式实现:
            # 1. _build_multilingual_queries() 生成中英文查询
            # 2. _get_layer_domains() 根据目标语言选择媒体域名
            if target_languages:
                logger.info(f"Target languages: {target_languages} (query-based multilingual)")

            # 添加内容抓取选项 (Firecrawl SDK 使用 snake_case)
            # v4.5.4: 同时请求 markdown 和 html 格式
            search_params["scrape_options"] = {
                "formats": ["markdown", "html"],
                "only_main_content": True,
            }

            lang_info = f", target_langs={target_languages[:2] if target_languages else ['auto']}"
            logger.info(
                f"[FIRECRAWL_REQUEST] layer={self.layer}, "
                f"query='{query[:80]}...', "
                f"limit={num_results}, sources=news{lang_info}"
            )
            logger.debug(f"[FIRECRAWL_PARAMS] {search_params}")

            # 调用 Firecrawl Search API (使用关键字参数)
            response = self.firecrawl_client.search(**search_params)

            # 解析 SDK v4 响应 (SearchData 对象)
            results = []

            # v4.3.4: 优先检查 response.news (当 sources=['news'] 时结果在这里)
            # 注意: 使用 scrape_options 时可能返回混合类型:
            #   - Document 类型: URL/title 在 metadata 中
            #   - SearchResultNews 类型: URL/title 直接在属性上
            if hasattr(response, 'news') and response.news:
                logger.info(f"Processing {len(response.news)} news results from Firecrawl")
                for item in response.news:
                    # 检查是否是 Document 类型 (有 metadata 属性且 metadata 非空)
                    if hasattr(item, 'metadata') and item.metadata:
                        # Document 类型: URL 和标题在 metadata 中
                        metadata = item.metadata
                        result_dict = {
                            "url": getattr(metadata, 'url', '') or getattr(metadata, 'source_url', ''),
                            "title": getattr(metadata, 'title', ''),
                            "description": getattr(metadata, 'description', ''),
                            "markdown": getattr(item, 'markdown', ''),
                            "html": getattr(item, 'html', ''),  # v4.5.4: 添加 html 字段
                            "publishedDate": getattr(metadata, 'published_time', None),
                        }
                    else:
                        # SearchResultNews 类型: URL 和标题直接在 item 上
                        result_dict = {
                            "url": getattr(item, 'url', ''),
                            "title": getattr(item, 'title', ''),
                            "description": getattr(item, 'snippet', '') or getattr(item, 'description', ''),
                            "markdown": getattr(item, 'markdown', ''),
                            "html": getattr(item, 'html', ''),  # v4.5.4: 添加 html 字段
                            "publishedDate": getattr(item, 'date', None) or getattr(item, 'published_date', None),
                        }
                    # 只添加有效的结果（至少有 URL 或 title）
                    if result_dict.get('url') or result_dict.get('title'):
                        results.append(result_dict)
            elif hasattr(response, 'web') and response.web:
                # SDK v4: response.web 是网页搜索结果列表
                # 注意: 使用 scrape_options 时返回 Document 类型，URL 在 metadata 中
                logger.info(f"Processing {len(response.web)} web results from Firecrawl")
                for item in response.web:
                    # 检查是否是 Document 类型 (有 metadata 属性)
                    if hasattr(item, 'metadata') and item.metadata:
                        # Document 类型: URL 和标题在 metadata 中
                        metadata = item.metadata
                        result_dict = {
                            "url": getattr(metadata, 'url', '') or getattr(metadata, 'source_url', ''),
                            "title": getattr(metadata, 'title', ''),
                            "description": getattr(metadata, 'description', ''),
                            "markdown": getattr(item, 'markdown', ''),
                            "html": getattr(item, 'html', ''),  # v4.5.4: 添加 html 字段
                            "publishedDate": getattr(metadata, 'published_time', None),
                        }
                    else:
                        # SearchResultWeb 类型: URL 和标题直接在 item 上
                        result_dict = {
                            "url": getattr(item, 'url', ''),
                            "title": getattr(item, 'title', ''),
                            "description": getattr(item, 'description', ''),
                            "markdown": getattr(item, 'markdown', ''),
                            "html": getattr(item, 'html', ''),  # v4.5.4: 添加 html 字段
                            "publishedDate": getattr(item, 'published_date', None),
                        }
                    results.append(result_dict)
            elif hasattr(response, 'data') and response.data:
                # 兼容 SDK v2 格式: response.data
                for item in response.data:
                    result_dict = {
                        "url": getattr(item, 'url', ''),
                        "title": getattr(item, 'title', ''),
                        "description": getattr(item, 'description', ''),
                        "markdown": getattr(item, 'markdown', ''),
                        "html": getattr(item, 'html', ''),  # v4.5.4: 添加 html 字段
                        "publishedDate": getattr(item, 'publishedDate', None),
                    }
                    results.append(result_dict)
            elif isinstance(response, dict) and "data" in response:
                # 兼容 REST API 字典格式
                results = response["data"]
            elif isinstance(response, list):
                results = response

            logger.info(
                f"[FIRECRAWL_RESPONSE] layer={self.layer}, "
                f"results_count={len(results)}, "
                f"query='{query[:50]}...'"
            )
            return results

        except Exception as e:
            logger.error(
                f"[FIRECRAWL_ERROR] layer={self.layer}, "
                f"query='{query[:50]}...', "
                f"error={str(e)}"
            )
            return []

    def _convert_to_search_result(
        self,
        raw: Dict[str, Any],
        position: int,
        target_languages: Optional[List[str]] = None,
    ) -> SearchResult:
        """将原始结果转换为 SearchResult

        v4.3.1: 支持目标语言参数

        Args:
            raw: 原始搜索结果
            position: 结果位置
            target_languages: 目标语言列表

        Returns:
            SearchResult 对象
        """
        url = raw.get("url", "")
        domain = extract_domain(url)

        # 计算基础分数
        base_relevance = 1.0 - (position * 0.1)  # 位置越靠前分数越高
        credibility = self.config.get_layer_credibility(self.layer)

        # 计算最终分数
        layer_weight = self.config.get_layer_weight(self.layer)
        final_score = (base_relevance * 0.5 + credibility * 0.5) * layer_weight

        # v4.3.1: 检测结果语言（如果未提供）
        result_language = raw.get("language", "")
        if not result_language and target_languages:
            # 使用目标语言中的主要语言作为默认值
            result_language = target_languages[0] if target_languages else "en"

        # v4.5.5: 检查 firecrawl 返回的内容是否为空
        # 如果内容为空或仅包含空白字符，则不保存（设为 None）
        markdown_raw = raw.get("markdown", raw.get("content", ""))
        html_raw = raw.get("html", "")
        markdown_content = markdown_raw.strip() if markdown_raw and markdown_raw.strip() else None
        html_content = html_raw.strip() if html_raw and html_raw.strip() else None

        return SearchResult(
            url=url,
            title=raw.get("title", ""),
            snippet=raw.get("description", raw.get("snippet", "")),
            source_domain=domain,
            layer=self.layer,
            layer_name=self.layer_name,
            source_tier=self.config.get_layer_tier(self.layer),
            relevance_score=base_relevance,
            credibility_score=credibility,
            final_score=final_score,
            markdown_content=markdown_content,  # v4.5.5: 空内容检查
            html_content=html_content,  # v4.5.5: 空内容检查
            language=result_language or "en",
            published_date=raw.get("publishedDate"),
            fetched_at=datetime.utcnow(),
        )

    def _create_empty_result(self, start_time: float) -> Dict[str, Any]:
        """创建空结果

        Args:
            start_time: 开始时间

        Returns:
            状态更新字典
        """
        execution_time_ms = int((time.time() - start_time) * 1000)

        layer_result = LayerSearchResult(
            layer=self.layer,
            layer_name=self.layer_name,
            queries_executed=[],
            results=[],
            execution_time_ms=execution_time_ms,
        )

        return {
            "layer_results": {self.layer: layer_result.to_dict()},
        }


def create_layer_search_nodes(
    config: Optional[LangGraphSearchConfig] = None,
    firecrawl_client: Optional[Any] = None,
) -> Dict[int, LayerSearchNode]:
    """创建所有层级的搜索节点

    Args:
        config: LangGraph 搜索配置
        firecrawl_client: Firecrawl 客户端

    Returns:
        层级 → 节点的映射
    """
    config = config or LangGraphSearchConfig()
    nodes = {}

    for layer in range(5):
        layer_enabled = getattr(config, f"enable_layer_{layer}", True)
        if layer_enabled:
            nodes[layer] = LayerSearchNode(
                layer=layer,
                config=config,
                firecrawl_client=firecrawl_client,
            )

    return nodes
