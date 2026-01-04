"""
NL Search 核心服务
用于编排整个自然语言搜索流程

版本: v3.3.0 (Claude Query Optimization)
日期: 2025-12-25

v3.3.0 更新:
- 新增 Claude 查询优化功能 (使用解析的关键词/实体优化搜索查询)
- 可配置优化策略 (keywords / entities / both)
- 解决 "东亚政外" 等缩写词搜索不精确问题

v3.2.0 更新:
- 新增 Firecrawl Search 适配器 (4-5x 更快)
- 支持 location 参数实现国家媒体优先搜索
- 可配置切换 Firecrawl / Sonar 搜索引擎

v3.1.0 更新:
- 集成 Source Tier 来源分层分类 (6级: 官方/权威/主流/专业/一般/社交)
- 集成 5级可信度评分系统 (确认/可信/待核实/存疑/不可靠)
- 每个搜索结果自动附带 source_tier 和 credibility 信息

v3.0.0 更新:
- 集成 ClaudeClient 替代 LLMProcessor
- 添加 Claude rerank 智能重排序功能
- 支持 Claude parse_query 查询解析
"""
import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.services.nl_search.config import nl_search_config
from src.services.nl_search.llm_processor import LLMProcessor
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter
from src.services.nl_search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.infrastructure.database.mongo_nl_search_repository import MongoNLSearchLogRepository
from src.infrastructure.database.user_selection_repository import user_selection_repository
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.services.nl_search.search_result_adapter import nl_search_result_adapter
from src.infrastructure.persistence.repositories.mongo.result_repository import MongoResultRepository
from src.services.nl_search.url_normalizer import normalize_url

# v3.0.0: Claude 客户端集成
from src.infrastructure.llm.claude_client import create_claude_client, ClaudeClient

logger = logging.getLogger(__name__)


class NLSearchService:
    """
    自然语言搜索核心服务

    职责:
    1. 编排整个搜索流程
    2. 调用LLM解析用户查询
    3. 调用搜索适配器执行搜索
    4. 保存搜索记录到数据库
    5. 返回完整的搜索结果

    使用示例:
        service = NLSearchService()
        result = await service.create_search(
            query_text="最近有哪些AI技术突破",
            user_id="user_123"
        )
    """

    def __init__(self):
        """初始化服务"""
        # 初始化各个组件
        self.llm_processor = LLMProcessor()

        # v3.2.0: 搜索引擎选择 (firecrawl / sonar)
        # 从环境变量读取，默认使用 firecrawl
        self.search_engine = os.getenv("NL_SEARCH_ENGINE", "firecrawl").lower()

        # 初始化搜索适配器
        if self.search_engine == "firecrawl":
            self.search_adapter = FirecrawlSearchAdapter(
                test_mode=not nl_search_config.enabled
            )
            logger.info("✅ 使用 Firecrawl Search 引擎 (4-5x 更快, 支持 location)")
        else:
            self.search_adapter = GPT5SearchAdapter(
                test_mode=not nl_search_config.enabled
            )
            logger.info("✅ 使用 Sonar/GPT-5 Search 引擎")

        # 保留 gpt5_adapter 引用 (兼容性)
        self.gpt5_adapter = self.search_adapter

        self.repository = MongoNLSearchLogRepository()
        self.selection_repository = user_selection_repository

        # 初始化 Firecrawl 适配器 (用于抓取内容)
        self.firecrawl_adapter = FirecrawlAdapter()

        # 初始化 SearchResult 仓储（用于双写到独立集合）
        self.result_repository = MongoResultRepository()

        # v3.0.0: 初始化 Claude 客户端
        self.claude_client: Optional[ClaudeClient] = None
        self.use_claude = nl_search_config.claude_enabled
        if self.use_claude:
            try:
                self.claude_client = create_claude_client()
                logger.info("✅ Claude 客户端初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ Claude 客户端初始化失败，降级使用 LLMProcessor: {e}")
                self.use_claude = False

        logger.info(
            f"NLSearchService 初始化完成 "
            f"(搜索引擎={self.search_engine}, Claude={'启用' if self.use_claude else '禁用'})"
        )

    async def create_search(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        search_mode: str = "single"
    ) -> Dict[str, Any]:
        """
        创建自然语言搜索

        流程:
        1. 验证输入
        2. 创建搜索记录
        3. LLM解析查询
        4. 更新分析结果
        5. 根据search_mode选择执行模式:
           - single: 精炼查询 → 单次搜索
           - multi: 分解查询 → 循环搜索4个子问题
        6. 返回结果

        Args:
            query_text: 用户输入的自然语言查询
            user_id: 用户ID（可选）
            search_mode: 搜索模式 ("single" | "multi")
                - single: 单次搜索（默认，快速高效）
                - multi: 多问题分解搜索（深度研究，循环搜索4个子问题）

        Returns:
            包含搜索结果的字典:
            {
                "log_id": str,
                "query_text": str,
                "search_mode": str,
                "analysis": dict,
                "refined_query": str (single模式),
                "sub_queries": list (multi模式),
                "results": list,
                "created_at": str
            }

        Raises:
            ValueError: 输入验证失败
            Exception: 搜索过程中的其他错误
        """
        # 1. 验证输入
        if not query_text or not query_text.strip():
            raise ValueError("查询文本不能为空")

        if search_mode not in ["single", "multi"]:
            raise ValueError(f"无效的搜索模式: {search_mode}，必须是 'single' 或 'multi'")

        query_text = query_text.strip()
        logger.info(f"开始处理自然语言搜索: {query_text[:50]}... (模式: {search_mode})")

        # 2. 创建搜索记录（允许失败，不影响搜索功能）
        log_id = None
        try:
            log_id = await self.repository.create(
                query_text=query_text,
                llm_analysis=None
            )
            logger.info(f"创建搜索记录: log_id={log_id}")
        except Exception as e:
            logger.warning(f"创建搜索记录失败（MongoDB可能离线），继续执行搜索: {e}")
            # ✅ v1.5.0: 使用雪花算法生成临时ID（保持ID系统一致性）
            from src.infrastructure.id_generator import generate_string_id
            log_id = generate_string_id()
            logger.info(f"使用临时log_id（雪花算法）: {log_id}")

        try:

            # 3. LLM解析查询 (v3.0.0: 支持 Claude)
            if self.use_claude and self.claude_client:
                logger.info("🤖 使用 Claude 解析查询...")
                analysis = await self.claude_client.parse_query(query_text)
                logger.info(f"Claude 解析完成: intent={analysis.get('intent')}, "
                           f"keywords={analysis.get('keywords')}")
            else:
                logger.info("调用 LLMProcessor (GPT) 解析查询...")
                analysis = await self.llm_processor.parse_query(query_text)
                logger.info(f"LLM解析完成: intent={analysis.get('intent')}, "
                           f"keywords={analysis.get('keywords')}")

            # 4. 更新分析结果（允许失败）
            try:
                await self.repository.update_llm_analysis(
                    log_id=log_id,
                    llm_analysis=analysis
                )
                logger.info("分析结果已保存")
            except Exception as e:
                logger.warning(f"保存分析结果失败（MongoDB可能离线），继续执行: {e}")

            # 5. 根据search_mode选择执行模式
            if search_mode == "multi":
                # 多问题分解搜索模式
                return await self._create_search_multi(
                    log_id=log_id,
                    query_text=query_text,
                    analysis=analysis
                )
            else:
                # 单次搜索模式（默认）
                return await self._create_search_single(
                    log_id=log_id,
                    query_text=query_text,
                    analysis=analysis
                )

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            raise

    def _optimize_search_query(
        self,
        original_query: str,
        analysis: Dict[str, Any]
    ) -> str:
        """
        v3.3.0: 使用 Claude 解析结果优化搜索查询

        根据 Claude 解析出的关键词、实体等信息，构建更精确的搜索查询。

        策略:
        - keywords: 使用解析出的关键词（默认）
        - entities: 使用解析出的实体
        - both: 关键词 + 实体组合

        Args:
            original_query: 用户原始查询
            analysis: Claude 解析结果 (包含 intent, keywords, entities 等)

        Returns:
            优化后的搜索查询字符串
        """
        # 检查是否启用查询优化
        if not nl_search_config.enable_query_optimization:
            logger.debug("查询优化已禁用，使用原始查询")
            return original_query

        # 检查 analysis 是否有效
        if not analysis:
            logger.debug("无 Claude 解析结果，使用原始查询")
            return original_query

        strategy = nl_search_config.query_optimization_strategy
        keywords = analysis.get("keywords", [])
        entities = analysis.get("entities", [])
        intent = analysis.get("intent", "")

        # 过滤空值
        keywords = [k for k in keywords if k and isinstance(k, str)]
        entities = [e for e in entities if e and isinstance(e, str)]

        # 根据策略构建优化查询
        optimized_parts = []

        if strategy in ["keywords", "both"] and keywords:
            optimized_parts.extend(keywords)
            logger.debug(f"添加关键词: {keywords}")

        if strategy in ["entities", "both"] and entities:
            # 避免与关键词重复
            unique_entities = [e for e in entities if e not in optimized_parts]
            optimized_parts.extend(unique_entities)
            logger.debug(f"添加实体: {unique_entities}")

        # 如果没有提取到任何信息，返回原始查询
        if not optimized_parts:
            logger.debug("未提取到关键词/实体，使用原始查询")
            return original_query

        # 构建优化后的查询
        # 策略：关键词用空格连接，形成更精确的搜索词
        optimized_query = " ".join(optimized_parts)

        # 添加意图相关的时效性词汇（如果意图是新闻/动态类）
        news_intents = ["新闻", "动态", "最新", "近期", "news", "recent", "latest"]
        if intent and any(word in intent.lower() for word in news_intents):
            if "最新" not in optimized_query and "latest" not in optimized_query.lower():
                optimized_query += " 最新动态"
                logger.debug("检测到新闻类意图，添加时效性词汇")

        logger.info(
            f"查询优化: strategy={strategy}, "
            f"keywords={len(keywords)}, entities={len(entities)}, "
            f"intent='{intent[:20]}...'" if intent else "intent=None"
        )

        return optimized_query

    async def _create_search_single(
        self,
        log_id: str,
        query_text: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        单次搜索模式（v3.3.0: Claude 查询优化 + 分数过滤）

        流程：Claude解析 → 查询优化 → GPT搜索（10条） → 分数过滤 → 只爬取高分结果

        v3.3.0 更新:
        - 使用 Claude 解析的关键词/实体优化搜索查询
        - 可配置优化策略 (keywords / entities / both)
        """
        # v3.3.0: 使用 Claude 解析结果优化搜索查询
        optimized_query = self._optimize_search_query(query_text, analysis)

        if optimized_query != query_text:
            logger.info(f"🔍 查询优化: '{query_text}' → '{optimized_query}'")
        else:
            logger.info(f"直接搜索: {query_text}")

        # 执行搜索（获取10条结果）
        logger.info("开始执行单次搜索...")
        search_results = await self.gpt5_adapter.search(
            query=optimized_query,  # 使用优化后的查询
            max_results=nl_search_config.max_search_results  # 使用10条配置
        )
        logger.info(f"搜索完成: 获得{len(search_results)}个结果")

        # 分数过滤：只保留高质量结果
        results_dict = [r.to_dict() for r in search_results]
        high_score_results = [
            r for r in results_dict
            if r.get("score", 0.0) >= nl_search_config.score_threshold
        ]
        logger.info(
            f"分数过滤: {len(results_dict)}个结果 → {len(high_score_results)}个高分结果 "
            f"(阈值: {nl_search_config.score_threshold})"
        )

        # v3.1.0: Claude Rerank 智能重排序 + OSINT 增强 (Source Tier + Credibility)
        if self.use_claude and self.claude_client and high_score_results:
            try:
                logger.info("🔄 使用 Claude 进行智能重排序 (v3.1.0 OSINT 增强)...")
                reranked_results = await self.claude_client.rerank_results(
                    query=query_text,
                    analysis=analysis,
                    results=high_score_results,
                    max_results=15
                )
                if reranked_results:
                    high_score_results = reranked_results
                    # 统计增强信息
                    tiers = {}
                    for r in reranked_results:
                        tier = r.get("source_tier", {}).get("tier", "unknown")
                        tiers[tier] = tiers.get(tier, 0) + 1
                    logger.info(
                        f"✅ Claude 重排序完成: {len(reranked_results)} 个结果 "
                        f"(来源分布: {tiers})"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Claude 重排序失败，使用原始排序: {e}")

        # 并发抓取内容（只爬取高分结果，节省Firecrawl成本）
        enriched_results = await self._scrape_search_results_concurrent(
            search_results=high_score_results,
            max_concurrent=nl_search_config.scrape_max_concurrent,
            log_id=log_id  # 传递log_id用于URL去重
        )
        logger.info(f"内容抓取完成: {len(enriched_results)}个结果")

        # 保存搜索结果（包含优化指标，允许失败）
        try:
            await self.repository.update_search_results(
                log_id=log_id,
                search_results=enriched_results,
                results_count=len(enriched_results),
                total_results=len(results_dict),
                high_score_results=len(high_score_results),
                score_threshold=nl_search_config.score_threshold
            )
            logger.info(f"搜索结果已保存: log_id={log_id} (优化指标: {len(results_dict)}→{len(high_score_results)})")
        except Exception as e:
            logger.warning(f"保存搜索结果失败（MongoDB可能离线），继续执行: {e}")

        # 双写到独立 search_results 集合（供 AI 服务使用）
        url_to_id = await self._write_to_search_results_collection(log_id, enriched_results)

        # ✅ v2.2: 将 mongo_id 添加回结果，只保留有效结果
        valid_results = []
        filtered_count = 0

        for result in enriched_results:
            url = result.get("url")
            if url:
                normalized_url = normalize_url(url)
                mongo_id = url_to_id.get(normalized_url)

                if mongo_id:
                    result["mongo_id"] = mongo_id
                    valid_results.append(result)
                    logger.debug(f"添加 mongo_id: {url} → {mongo_id}")
                else:
                    filtered_count += 1
                    logger.debug(f"过滤无效结果（无mongo_id）: {url}")

        if filtered_count > 0:
            logger.info(
                f"✅ 结果过滤: {len(enriched_results)} 个原始结果 → {len(valid_results)} 个有效结果 "
                f"(过滤: {filtered_count})"
            )

        # 构建返回结果
        return {
            "log_id": log_id,
            "query_text": query_text,
            "search_mode": "single",
            "analysis": analysis,
            "total_results": len(results_dict),
            "high_score_results": len(high_score_results),
            "score_threshold": nl_search_config.score_threshold,
            "results": valid_results,  # ← 只返回有 mongo_id 的有效结果
            "created_at": datetime.now().isoformat()
        }

    async def _create_search_multi(
        self,
        log_id: str,
        query_text: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        多问题分解搜索模式（新功能）

        流程：
        1. LLM分解为4个子问题
        2. 循环搜索每个子问题
        3. 聚合和去重结果
        4. 并发抓取内容
        5. 保存结果
        """
        # 步骤1: 分解为4个子问题
        logger.info("开始分解查询为多个子问题...")
        sub_queries = await self.llm_processor.decompose_query(query_text, analysis)
        logger.info(f"查询分解完成: 获得 {len(sub_queries)} 个子问题")
        for idx, sq in enumerate(sub_queries, 1):
            logger.info(f"  子问题{idx}: {sq}")

        # 步骤2: 循环搜索每个子问题
        logger.info(f"开始循环搜索 {len(sub_queries)} 个子问题...")
        all_search_results = []

        for idx, sub_query in enumerate(sub_queries, 1):
            logger.info(f"[{idx}/{len(sub_queries)}] 搜索子问题: {sub_query}")
            try:
                results = await self.gpt5_adapter.search(
                    query=sub_query,
                    max_results=nl_search_config.max_results_per_query
                )
                logger.info(f"[{idx}/{len(sub_queries)}] 获得 {len(results)} 个结果")

                # 标记来源子问题
                for result in results:
                    result_dict = result.to_dict()
                    result_dict["sub_query"] = sub_query
                    result_dict["sub_query_index"] = idx
                    all_search_results.append(result_dict)

            except Exception as e:
                logger.error(f"[{idx}/{len(sub_queries)}] 搜索失败: {e}", exc_info=True)
                continue

        logger.info(f"循环搜索完成: 总共获得 {len(all_search_results)} 个原始结果")

        # 步骤3: 聚合和去重结果
        logger.info("开始聚合和去重结果...")
        aggregated_results = self._aggregate_and_deduplicate_results(all_search_results)
        logger.info(f"聚合去重完成: 保留 {len(aggregated_results)} 个唯一结果")

        # 步骤4: 并发抓取内容
        enriched_results = await self._scrape_search_results_concurrent(
            search_results=aggregated_results,
            max_concurrent=nl_search_config.multi_search_max_concurrent,  # 使用配置的并发数
            log_id=log_id  # 传递log_id用于URL去重
        )
        logger.info(f"内容抓取完成: {len(enriched_results)} 个结果")

        # 步骤5: 保存结果（允许失败）
        try:
            await self.repository.update_search_results(
                log_id=log_id,
                search_results=enriched_results,
                results_count=len(enriched_results)
            )
            logger.info(f"多问题搜索结果已保存: log_id={log_id}")
        except Exception as e:
            logger.warning(f"保存搜索结果失败（MongoDB可能离线），继续执行: {e}")

        # 双写到独立 search_results 集合（供 AI 服务使用）
        url_to_id = await self._write_to_search_results_collection(log_id, enriched_results)

        # ✅ v2.2: 将 mongo_id 添加回结果，只保留有效结果
        valid_results = []
        filtered_count = 0

        for result in enriched_results:
            url = result.get("url")
            if url:
                normalized_url = normalize_url(url)
                mongo_id = url_to_id.get(normalized_url)

                if mongo_id:
                    result["mongo_id"] = mongo_id
                    valid_results.append(result)
                    logger.debug(f"添加 mongo_id: {url} → {mongo_id}")
                else:
                    filtered_count += 1
                    logger.debug(f"过滤无效结果（无mongo_id）: {url}")

        if filtered_count > 0:
            logger.info(
                f"✅ 结果过滤: {len(enriched_results)} 个原始结果 → {len(valid_results)} 个有效结果 "
                f"(过滤: {filtered_count})"
            )

        # 构建返回结果
        return {
            "log_id": log_id,
            "query_text": query_text,
            "search_mode": "multi",
            "analysis": analysis,
            "sub_queries": sub_queries,
            "results": valid_results,  # ← 只返回有 mongo_id 的有效结果
            "total_raw_results": len(all_search_results),
            "total_unique_results": len(aggregated_results),
            "created_at": datetime.now().isoformat()
        }

    def _aggregate_and_deduplicate_results(
        self,
        all_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        聚合和去重搜索结果

        策略:
        1. 基于URL去重
        2. 对于重复URL，保留最高分数的结果
        3. 记录URL出现在哪些子问题中（用于评分加权）
        4. 重新评分：基础分数 + 出现频率加成（可配置）
        5. 排序：按最终分数降序
        6. 限制数量：最多N个结果（由配置决定，默认20）

        Args:
            all_results: 所有原始搜索结果列表

        Returns:
            去重后的结果列表（数量由配置决定）
        """
        if not all_results:
            return []

        # 1. URL去重和统计
        url_data = {}

        for result in all_results:
            url = result.get("url", "")
            if not url:
                continue

            # ✅ URL规范化：统一格式提高去重准确性
            normalized_url = normalize_url(url)

            if normalized_url not in url_data:
                # 首次遇到该URL
                url_data[normalized_url] = {
                    "result": result.copy(),
                    "appearances": 1,
                    "sub_queries": [result.get("sub_query", "")],
                    "max_score": result.get("score", 0.0)
                }
            else:
                # URL重复，更新统计
                url_data[normalized_url]["appearances"] += 1
                url_data[normalized_url]["sub_queries"].append(result.get("sub_query", ""))

                # 保留更高的分数
                current_score = result.get("score", 0.0)
                if current_score > url_data[normalized_url]["max_score"]:
                    url_data[normalized_url]["max_score"] = current_score
                    # 更新为分数更高的结果
                    url_data[normalized_url]["result"] = result.copy()

        # ✅ 去重统计日志
        original_count = len(all_results)
        unique_count = len(url_data)
        duplicate_count = original_count - unique_count
        dedup_rate = (duplicate_count / original_count * 100) if original_count > 0 else 0

        logger.info(
            f"✅ URL去重统计: "
            f"原始结果={original_count}, "
            f"唯一URL={unique_count}, "
            f"去重数={duplicate_count}, "
            f"去重率={dedup_rate:.1f}%"
        )

        # 2. 重新评分和排序
        scored_results = []

        for url, data in url_data.items():
            result = data["result"]

            # 基础分数
            base_score = data["max_score"]

            # 频率加成（出现在多个子问题中 → 更相关）
            # 使用配置的频率加分参数
            frequency_bonus = min(
                (data["appearances"] - 1) * nl_search_config.multi_search_frequency_bonus,
                nl_search_config.multi_search_frequency_bonus_max
            )

            # 最终分数
            final_score = min(base_score + frequency_bonus, 1.0)

            # 更新结果
            result["score"] = final_score
            result["appearances_in_sub_queries"] = data["appearances"]
            result["related_sub_queries"] = data["sub_queries"]

            scored_results.append(result)

        # 3. 排序：按分数降序，再按position升序
        scored_results.sort(key=lambda r: (-r.get("score", 0.0), r.get("position", 999)))

        # 4. 限制数量（使用配置的聚合结果限制）
        final_results = scored_results[:nl_search_config.multi_search_aggregation_limit]

        logger.info(f"聚合完成: 保留前 {len(final_results)} 个结果")

        return final_results

    async def _scrape_search_results_concurrent(
        self,
        search_results: List[Dict[str, Any]],
        max_concurrent: int = 3,
        log_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        并发抓取搜索结果内容（v2.1: 支持URL去重）

        Args:
            search_results: 搜索结果列表（字典格式）
            max_concurrent: 最大并发数（默认3）
            log_id: 搜索日志ID（用于URL去重检查，可选）

        Returns:
            List[Dict]: 包含抓取内容的结果列表
        """
        if not nl_search_config.enable_auto_scrape:
            logger.info("自动抓取已禁用，跳过内容抓取")
            return search_results

        # ✅ URL去重检查：查询数据库中已存在的URL
        existing_urls = set()
        existing_url_data = {}

        if log_id:
            try:
                # 提取所有URL并规范化
                all_urls = [normalize_url(r.get("url")) for r in search_results if r.get("url")]

                if all_urls:
                    # 检查哪些URL已存在（使用log_id作为task_id）
                    existing_urls = await self.result_repository.check_existing_urls(
                        task_id=log_id,
                        urls=all_urls
                    )

                    if existing_urls:
                        cache_hit_rate = (len(existing_urls) / len(all_urls) * 100) if all_urls else 0
                        logger.info(
                            f"✅ URL缓存命中统计: "
                            f"总URL={len(all_urls)}, "
                            f"缓存命中={len(existing_urls)}, "
                            f"命中率={cache_hit_rate:.1f}%"
                        )

                        # 从数据库加载已存在URL的内容
                        for url in existing_urls:
                            try:
                                existing_result = await self.result_repository.find_by_url(url)
                                if existing_result:
                                    existing_url_data[url] = {
                                        "markdown_content": existing_result.markdown_content,
                                        "html_content": existing_result.html_content,
                                        "metadata": existing_result.metadata or {},
                                        "scrape_success": True,
                                        "from_cache": True
                                    }
                                    logger.debug(f"从数据库加载内容: {url}")
                            except Exception as e:
                                logger.warning(f"加载已存在URL内容失败: {url}, {e}")

            except Exception as e:
                logger.warning(f"URL去重检查失败，将继续正常抓取: {e}")

        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_single(result: Dict[str, Any]) -> Dict[str, Any]:
            """抓取单个结果"""
            url = result.get("url", "")
            if not url:
                logger.warning(f"结果缺少 URL，跳过抓取: {result}")
                return result

            # ✅ URL规范化
            normalized_url = normalize_url(url)

            # ✅ 如果URL已存在，直接使用缓存内容
            if normalized_url in existing_urls and normalized_url in existing_url_data:
                cached_data = existing_url_data[normalized_url]
                result.update(cached_data)
                logger.info(f"✅ 使用缓存内容: {normalized_url}")
                return result

            async with semaphore:
                try:
                    logger.info(f"开始抓取: {url}")

                    # 调用 Firecrawl scrape
                    crawl_result = await self.firecrawl_adapter.scrape(
                        url=url,
                        only_main_content=True,
                        wait_for=500,
                        timeout=nl_search_config.scrape_timeout
                    )

                    # 将抓取内容添加到结果中
                    result["markdown_content"] = crawl_result.markdown[:5000] if crawl_result.markdown else None
                    # 使用 raw_html 提供完整HTML供AI分析
                    result["html_content"] = crawl_result.raw_html[:20000] if crawl_result.raw_html else None
                    # 转换 metadata 为 dict (Pydantic model -> dict)
                    result["metadata"] = crawl_result.metadata.dict() if crawl_result.metadata else {}
                    result["scrape_success"] = True

                    logger.info(f"抓取成功: {url} (markdown: {len(crawl_result.markdown or '')} chars)")

                except Exception as e:
                    logger.error(f"抓取失败: {url}, 错误: {e}", exc_info=True)
                    result["scrape_success"] = False
                    result["scrape_error"] = str(e)

                return result

        # 并发抓取所有结果
        urls_to_scrape = len([r for r in search_results if r.get("url") not in existing_urls])
        urls_cached = len(existing_urls)
        logger.info(
            f"开始并发抓取: {urls_to_scrape} 个新URL (并发数: {max_concurrent}), "
            f"{urls_cached} 个URL使用缓存"
        )

        enriched_results = await asyncio.gather(
            *[scrape_single(result.copy()) for result in search_results],
            return_exceptions=False
        )

        # ✅ 抓取统计日志
        success_count = sum(1 for r in enriched_results if r.get("scrape_success", False))
        cached_count = sum(1 for r in enriched_results if r.get("from_cache", False))
        new_scrape_count = success_count - cached_count
        failed_count = len(search_results) - success_count
        cache_benefit_rate = (cached_count / len(search_results) * 100) if search_results else 0

        logger.info(
            f"✅ 抓取完成统计: "
            f"总数={len(search_results)}, "
            f"成功={success_count}, "
            f"新抓取={new_scrape_count}, "
            f"缓存={cached_count}({cache_benefit_rate:.1f}%), "
            f"失败={failed_count}"
        )

        return list(enriched_results)

    async def _write_to_search_results_collection(
        self,
        log_id: str,
        nl_search_results: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        双写到独立 search_results 集合供 AI 服务使用（v2.2: 返回URL→ID映射）

        将 NL Search 的结果转换为 SearchResult 实体，
        并写入 search_results 集合，供 AI 服务统一读取。

        Args:
            log_id: NL Search 日志ID（将作为 task_id）
            nl_search_results: NL Search 的搜索结果列表（字典格式）

        Returns:
            Dict[str, str]: URL（规范化后）→ MongoDB _id 的映射字典

        Note:
            此方法不抛出异常，以避免影响主搜索流程。
            双写失败只记录错误日志，不影响用户体验。
        """
        try:
            logger.info(f"开始双写到 search_results 集合: log_id={log_id}, 结果数={len(nl_search_results)}")

            # ✅ 过滤空内容：移除 html_content 为空的结果
            filtered_results = []
            empty_content_count = 0

            for result in nl_search_results:
                html_content = result.get("html_content")

                # 检查 html_content 是否为空
                if not html_content or (isinstance(html_content, str) and not html_content.strip()):
                    empty_content_count += 1
                    logger.debug(f"跳过空内容结果: {result.get('url', 'N/A')}")
                    continue

                filtered_results.append(result)

            if empty_content_count > 0:
                logger.info(
                    f"✅ 过滤空内容: {len(nl_search_results)} 个结果 → {len(filtered_results)} 个有效结果 "
                    f"(过滤: {empty_content_count})"
                )

            if not filtered_results:
                logger.warning(f"过滤后无有效结果，跳过双写: log_id={log_id}")
                return {}

            # 转换为 SearchResult 实体
            search_results = nl_search_result_adapter.convert_to_search_results(
                log_id=log_id,
                nl_search_results=filtered_results
            )

            if not search_results:
                logger.warning(f"转换后无有效结果，跳过双写: log_id={log_id}")
                return {}

            # 批量写入 search_results 集合
            result_ids = await self.result_repository.bulk_create(search_results)
            logger.info(
                f"双写成功: {len(result_ids)} 条结果已写入 search_results 集合 "
                f"(log_id={log_id})"
            )

            # ✅ v2.2: 创建 URL → mongo_id 映射
            url_to_id = {}
            for idx, search_result in enumerate(search_results):
                if idx < len(result_ids):
                    url_to_id[search_result.url] = result_ids[idx]
                    logger.debug(f"映射: {search_result.url} → {result_ids[idx]}")

            logger.info(f"创建URL映射: {len(url_to_id)} 个URL → mongo_id")

            # ✅ v2.2: 调试日志 - 打印映射的键
            if url_to_id:
                sample_urls = list(url_to_id.keys())[:3]
                logger.info(f"映射示例: {sample_urls}")

            return url_to_id

        except Exception as e:
            logger.error(
                f"双写 search_results 集合失败: {e} (log_id={log_id})",
                exc_info=True
            )
            # 不抛出异常，避免影响主流程
            return {}

    async def get_search_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """
        获取搜索记录

        Args:
            log_id: 搜索记录ID（雪花算法ID字符串）

        Returns:
            搜索记录字典，如果不存在返回None
        """
        logger.info(f"获取搜索记录: log_id={log_id}")

        try:
            log = await self.repository.get_by_id(log_id)

            if not log:
                logger.warning(f"搜索记录不存在: log_id={log_id}")
                return None

            return {
                "log_id": log["_id"],
                "query_text": log["query_text"],
                "analysis": log.get("llm_analysis"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }

        except Exception as e:
            logger.error(f"获取搜索记录失败: {e}", exc_info=True)
            raise

    async def list_search_logs(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出搜索历史

        Args:
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            搜索记录列表
        """
        logger.info(f"查询搜索历史: limit={limit}, offset={offset}")

        try:
            logs = await self.repository.get_recent(limit=limit, offset=offset)

            results = [
                {
                    "log_id": log["_id"],
                    "query_text": log["query_text"],
                    "analysis": log.get("llm_analysis"),
                    "created_at": log["created_at"].isoformat() if log.get("created_at") else None
                }
                for log in logs
            ]

            logger.info(f"返回{len(results)}条搜索记录")
            return results

        except Exception as e:
            logger.error(f"查询搜索历史失败: {e}", exc_info=True)
            raise

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        根据关键词搜索历史记录

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            匹配的搜索记录列表
        """
        logger.info(f"根据关键词搜索: keyword={keyword}")

        try:
            logs = await self.repository.search_by_keyword(
                keyword=keyword,
                limit=limit
            )

            results = [
                {
                    "log_id": log["_id"],
                    "query_text": log["query_text"],
                    "analysis": log.get("llm_analysis"),
                    "created_at": log["created_at"].isoformat() if log.get("created_at") else None
                }
                for log in logs
            ]

            logger.info(f"找到{len(results)}条匹配记录")
            return results

        except Exception as e:
            logger.error(f"关键词搜索失败: {e}", exc_info=True)
            raise

    async def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态

        Returns:
            服务状态信息
        """
        return {
            "enabled": nl_search_config.enabled,
            "llm_configured": bool(self.llm_processor.client),
            "search_configured": bool(self.gpt5_adapter.api_key or self.gpt5_adapter.test_mode),
            "test_mode": self.gpt5_adapter.test_mode,
            "version": "1.0.0-beta"
        }

    async def get_search_results(
        self,
        log_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        获取搜索结果

        Args:
            log_id: 搜索记录ID（雪花算法ID字符串）
            limit: 返回数量限制（可选）
            offset: 分页偏移量（默认 0）

        Returns:
            Optional[Dict]: 搜索结果数据，不存在时返回 None

        Example:
            >>> result = await service.get_search_results("248728141926559744")
            >>> print(f"共 {result['total_count']} 条结果")
            >>> for item in result['results']:
            ...     print(item['title'])
        """
        logger.info(f"获取搜索结果: log_id={log_id}")

        try:
            # 1. 获取搜索记录（包含基本信息）
            log = await self.repository.get_by_id(log_id)
            if not log:
                logger.warning(f"搜索记录不存在: log_id={log_id}")
                return None

            # 2. 获取搜索结果
            search_results = await self.repository.get_search_results(log_id)
            if search_results is None:
                logger.warning(f"搜索结果不存在: log_id={log_id}")
                return None

            # 3. 分页处理
            total_count = len(search_results)
            if limit is not None:
                search_results = search_results[offset:offset + limit]

            # 4. 构建响应
            return {
                "log_id": log_id,
                "query_text": log["query_text"],
                "total_count": total_count,
                "results": search_results,
                "llm_analysis": log.get("llm_analysis"),
                "status": log.get("status", "completed"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }

        except Exception as e:
            logger.error(f"获取搜索结果失败: {e}", exc_info=True)
            raise

    async def record_user_selection(
        self,
        log_id: str,
        result_url: str,
        action_type: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        记录用户选择事件

        Args:
            log_id: 搜索记录ID
            result_url: 选中的结果URL
            action_type: 操作类型（click, bookmark, archive）
            user_id: 用户ID（可选）
            user_agent: 用户代理字符串（可选）
            ip_address: 客户端IP地址（可选）

        Returns:
            str: 事件ID

        Raises:
            ValueError: 搜索记录不存在

        Example:
            >>> event_id = await service.record_user_selection(
            ...     log_id="248728141926559744",
            ...     result_url="https://example.com/gpt5",
            ...     action_type="click"
            ... )
        """
        logger.info(
            f"记录用户选择: log_id={log_id}, "
            f"url={result_url}, action={action_type}"
        )

        try:
            # 1. 验证搜索记录存在
            log = await self.repository.get_by_id(log_id)
            if not log:
                raise ValueError(f"搜索记录不存在: log_id={log_id}")

            # 2. 创建选择事件
            event_id = await self.selection_repository.create(
                log_id=log_id,
                result_url=result_url,
                action_type=action_type,
                user_id=user_id,
                user_agent=user_agent,
                ip_address=ip_address
            )

            logger.info(f"用户选择已记录: event_id={event_id}")
            return event_id

        except Exception as e:
            logger.error(f"记录用户选择失败: {e}", exc_info=True)
            raise

    async def get_selection_statistics(
        self,
        log_id: str
    ) -> Dict[str, Any]:
        """
        获取用户选择统计

        Args:
            log_id: 搜索记录ID

        Returns:
            Dict: 统计数据

        Example:
            >>> stats = await service.get_selection_statistics("248728141926559744")
            >>> print(f"总点击数: {stats['total_clicks']}")
        """
        logger.info(f"获取选择统计: log_id={log_id}")

        try:
            # 获取所有选择事件
            events = await self.selection_repository.get_by_log_id(log_id)

            # 统计数据
            total_count = len(events)
            click_count = sum(1 for e in events if e["action_type"] == "click")
            bookmark_count = sum(1 for e in events if e["action_type"] == "bookmark")
            archive_count = sum(1 for e in events if e["action_type"] == "archive")

            # 统计 URL 点击次数
            url_clicks = {}
            for event in events:
                url = event["result_url"]
                url_clicks[url] = url_clicks.get(url, 0) + 1

            return {
                "log_id": log_id,
                "total_count": total_count,
                "click_count": click_count,
                "bookmark_count": bookmark_count,
                "archive_count": archive_count,
                "top_urls": sorted(
                    url_clicks.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]  # 前5个最热门URL
            }

        except Exception as e:
            logger.error(f"获取选择统计失败: {e}", exc_info=True)
            raise


# 创建全局服务实例（单例模式）
nl_search_service = NLSearchService()
