"""
NL Search 核心服务
用于编排整个自然语言搜索流程

版本: v3.6.0 (Unified Multilang Analysis)
日期: 2026-01-09

v3.6.0 更新:
- 统一多语言搜索分析函数 (analyze_and_generate_multilang_search)
- 单次 Claude API 调用完成：查询类型分析 + 语言检测 + 优化搜索词生成
- 非翻译式搜索词优化（针对各语言信息生态系统）
- 新增查询类型分类 (news_coverage/research_data/policy_document/opinion_analysis)
- 减少 API 延迟和成本

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
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from src.services.nl_search.config import nl_search_config
from src.services.nl_search.llm_processor import LLMProcessor
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter
# v3.8.0: 使用基础设施层适配器 (合并后)
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.infrastructure.database.mongo_nl_search_repository import MongoNLSearchLogRepository
from src.infrastructure.database.user_selection_repository import user_selection_repository
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.services.nl_search.search_result_adapter import nl_search_result_adapter
from src.infrastructure.persistence.repositories.mongo.result_repository import MongoResultRepository
from src.services.nl_search.url_normalizer import normalize_url

# v3.0.0: Claude 客户端集成
from src.infrastructure.llm.claude_client import create_claude_client, ClaudeClient

# v3.7.0: 统一查询分析器（复用 LangGraph QueryAnalyzerNode 的优秀 Prompt）
from src.services.query_analyzer import get_unified_analyzer, UnifiedQueryAnalyzer

# v3.5.0: 用于 URL 解析
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)


# ============================================================================
# v3.8.0: 兼容性辅助类
# ============================================================================

class _SimpleSearchResult:
    """简化的搜索结果类 (兼容原有接口)"""
    def __init__(self, title: str, url: str, snippet: str = "",
                 position: int = 0, score: float = 0.0,
                 source: str = "firecrawl", markdown: str = "",
                 published_date: str = ""):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.position = position
        self.score = score
        self.source = source
        self.markdown = markdown
        self.published_date = published_date

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "position": self.position,
            "score": self.score,
            "source": self.source,
            "markdown": self.markdown,
            "published_date": self.published_date
        }

# ============================================================================
# v3.5.0: 垃圾内容过滤系统
# ============================================================================

# 域名黑名单 - 已知的垃圾站点/SEO站点/内容农场
SPAM_DOMAINS = {
    # SEO垃圾站点
    "tongli.net",
    "99csw.com",
    "biquge.com",
    "biquge.info",
    "biquge.cc",
    "69shu.com",
    "23us.so",
    "booktxt.net",
    # 内容农场/低质量聚合站
    "eastday.com",  # 东方头条 - 大量聚合内容
    "sohu.com",     # 可选 - 部分搜狐内容质量较低
    # 成人/赌博/诈骗相关
    "pornhub.com",
    "xvideos.com",
    "bet365.com",
    # 已知404/失效站点
    # (可根据实际情况添加)
}

# URL 路径黑名单模式 - 匹配垃圾 URL 路径
# 注意：避免匹配新闻日期格式如 /20260106/（YYYYMMDD）
SPAM_URL_PATTERNS = [
    # 随机字母数字混合路径（必须包含字母），如 /3x6j9f/756631778.html
    r"/(?=[a-z0-9]*[a-z])[a-z0-9]{5,8}/\d+\.html$",
    # 明确的垃圾路径关键词
    r"/casino/",
    r"/betting/",
    r"/adult/",
    r"/porn/",
    r"/slot[s]?/",
    r"/gambl[ei]/",
]

# 垃圾标题关键词 - 检测标题中的垃圾内容
SPAM_TITLE_KEYWORDS = [
    # 色情相关
    "噜噜", "狠狠", "撸", "啪啪", "福利", "成人", "色情", "裸", "做爱",
    "高潮", "性爱", "操逼", "鸡巴", "屌", "骚", "淫", "荡",
    # 赌博相关
    "赌场", "博彩", "彩票", "六合彩", "时时彩", "真人娱乐",
    # 赌博/娱乐平台常见关键词
    "棋牌", "娱乐城", "官网登录", "注册入口", "真人", "电子游戏",
    # 广告/营销垃圾
    "加微信", "加QQ", "兼职", "日赚", "月入", "免费领",
    # 视频/素材网站垃圾标题
    "高清素材", "视频素材", "图片素材", "PPT模板",
    # v3.7.1: 技术页面/无意义页面
    "网站地图", "sitemap", "站点地图", "网站导航",
    # v3.7.1: 低质量聚合站特征
    "首页登录", "官网首页", "平台登录", "入口", "官网下载",
]

# 404/空内容检测关键词
NOT_FOUND_INDICATORS = [
    "404 not found",
    "page not found",
    "页面不存在",
    "页面未找到",
    "内容已删除",
    "文章不存在",
    "nginx/",
    "apache/",
    "error 404",
]


def extract_domain(url: str) -> str:
    """从 URL 提取主域名"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # 去除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_spam_domain(url: str) -> bool:
    """检查 URL 是否属于垃圾域名"""
    domain = extract_domain(url)
    if not domain:
        return False

    # 直接匹配
    if domain in SPAM_DOMAINS:
        return True

    # 子域名匹配 (如 news.tongli.net)
    for spam_domain in SPAM_DOMAINS:
        if domain.endswith("." + spam_domain) or domain == spam_domain:
            return True

    return False


def is_spam_url_pattern(url: str) -> bool:
    """检查 URL 路径是否匹配垃圾模式"""
    for pattern in SPAM_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def is_spam_title(title: str) -> bool:
    """检查标题是否包含垃圾关键词"""
    if not title:
        return False
    title_lower = title.lower()
    for keyword in SPAM_TITLE_KEYWORDS:
        if keyword.lower() in title_lower:
            return True
    return False


def is_404_content(content: str) -> bool:
    """检查内容是否为 404 页面"""
    if not content:
        return False
    content_lower = content.lower().strip()

    # 检查内容是否过短 (< 200 字符通常是错误页面)
    if len(content_lower) < 200:
        for indicator in NOT_FOUND_INDICATORS:
            if indicator in content_lower:
                return True

    return False


def filter_spam_results(
    results: List[Dict[str, Any]],
    check_domain: bool = True,
    check_url_pattern: bool = True,
    check_title: bool = True,
) -> tuple[List[Dict[str, Any]], int]:
    """
    过滤垃圾搜索结果

    Args:
        results: 搜索结果列表
        check_domain: 是否检查域名黑名单
        check_url_pattern: 是否检查 URL 模式
        check_title: 是否检查标题关键词

    Returns:
        tuple: (过滤后的结果列表, 被过滤的数量)
    """
    filtered_results = []
    spam_count = 0

    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")

        is_spam = False
        spam_reason = None

        # 域名黑名单检查
        if check_domain and is_spam_domain(url):
            is_spam = True
            spam_reason = f"spam_domain: {extract_domain(url)}"

        # URL 模式检查
        elif check_url_pattern and is_spam_url_pattern(url):
            is_spam = True
            spam_reason = f"spam_url_pattern: {url}"

        # 标题关键词检查
        elif check_title and is_spam_title(title):
            is_spam = True
            spam_reason = f"spam_title: {title[:50]}"

        if is_spam:
            spam_count += 1
            logger.info(f"🚫 过滤垃圾结果: {spam_reason}")
        else:
            filtered_results.append(result)

    return filtered_results, spam_count


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

        # 初始化搜索适配器 (v4.19.5: 默认生产模式)
        if self.search_engine == "firecrawl":
            self.search_adapter = FirecrawlSearchAdapter(
                test_mode=False  # 默认生产模式，不再依赖 nl_search_config.enabled
            )
            logger.info("✅ 使用 Firecrawl Search 引擎 (4-5x 更快, 支持 location)")
        else:
            self.search_adapter = GPT5SearchAdapter(
                test_mode=False  # 默认生产模式
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

        # v3.7.0: 统一查询分析器（复用 LangGraph QueryAnalyzerNode 的优秀 Prompt）
        self.unified_analyzer: Optional[UnifiedQueryAnalyzer] = None
        self.use_unified_analyzer = nl_search_config.unified_analyzer_enabled
        if self.use_unified_analyzer:
            try:
                self.unified_analyzer = get_unified_analyzer()
                logger.info("✅ UnifiedQueryAnalyzer 初始化成功（增强 Prompt）")
            except Exception as e:
                logger.warning(f"⚠️ UnifiedQueryAnalyzer 初始化失败: {e}")
                self.use_unified_analyzer = False

        # v3.0.0: 初始化 Claude 客户端（当 UnifiedQueryAnalyzer 未启用时使用）
        self.claude_client: Optional[ClaudeClient] = None
        self.use_claude = nl_search_config.claude_enabled and not self.use_unified_analyzer
        if self.use_claude:
            try:
                self.claude_client = create_claude_client()
                logger.info("✅ Claude 客户端初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ Claude 客户端初始化失败，降级使用 LLMProcessor: {e}")
                self.use_claude = False

        logger.info(
            f"NLSearchService 初始化完成 "
            f"(搜索引擎={self.search_engine}, "
            f"分析器={'UnifiedAnalyzer' if self.use_unified_analyzer else ('Claude' if self.use_claude else 'LLMProcessor')})"
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

        if search_mode not in ["single", "multi", "multilang"]:
            raise ValueError(f"无效的搜索模式: {search_mode}，必须是 'single', 'multi' 或 'multilang'")

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

            # 3. LLM解析查询 (v3.7.0: 优先使用 UnifiedQueryAnalyzer)
            if self.use_unified_analyzer and self.unified_analyzer:
                logger.info("🤖 使用 UnifiedQueryAnalyzer 解析查询（增强 Prompt）...")
                enhanced_result = await self.unified_analyzer.analyze(query_text)
                # 转换为兼容格式
                analysis = {
                    "intent": enhanced_result.search_strategy.get("primary_focus", "general"),
                    "keywords": enhanced_result.keywords,
                    "entities": [p.name for p in enhanced_result.parties],
                    "time_range": enhanced_result.suggested_time_range,
                    "category": enhanced_result.event_type,
                    "confidence": 0.8,
                    # v3.7.0 额外信息
                    "_enhanced": {
                        "summary": enhanced_result.summary,
                        "parties": [{"name": p.name, "type": p.type, "role": p.role} for p in enhanced_result.parties],
                        "time_sensitivity": enhanced_result.time_sensitivity,
                        "search_queries": enhanced_result.search_queries,
                        "query_variations": enhanced_result.query_variations,
                    }
                }
                logger.info(f"UnifiedQueryAnalyzer 解析完成: intent={analysis.get('intent')}, "
                           f"keywords={analysis.get('keywords')}, parties={len(analysis.get('entities', []))}")
            elif self.use_claude and self.claude_client:
                logger.info("🤖 使用 ClaudeClient 解析查询...")
                analysis = await self.claude_client.parse_query(query_text)
                logger.info(f"ClaudeClient 解析完成: intent={analysis.get('intent')}, "
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

            # 5. 根据search_mode选择执行模式 (v3.7.1: 支持 multilang)
            if search_mode == "multilang":
                # 多语言搜索模式（v3.7推荐，默认模式）
                return await self._create_search_multilang(
                    log_id=log_id,
                    query_text=query_text,
                    analysis=analysis
                )
            elif search_mode == "multi":
                # 多问题分解搜索模式
                return await self._create_search_multi(
                    log_id=log_id,
                    query_text=query_text,
                    analysis=analysis
                )
            else:
                # 单次搜索模式
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
        单次搜索模式（v3.3.0: Claude 查询优化 + 分数过滤 + 多语言搜索）

        流程：
        - 如果启用多语言 + Firecrawl + Claude: 多语言搜索
        - 否则: Claude解析 → 查询优化 → GPT搜索（10条） → 分数过滤 → 只爬取高分结果

        v3.4.0 更新:
        - 多语言搜索支持（Claude 智能语言检测 + 多语言并行搜索）
        """
        # v3.4.0: 检查是否启用多语言搜索
        multilang_enabled = (
            nl_search_config.multilang_enabled and
            self.search_engine == "firecrawl" and
            self.use_claude and
            self.claude_client is not None
        )

        if multilang_enabled:
            logger.info("🌐 启用多语言搜索模式")
            return await self._create_search_multilang(
                log_id=log_id,
                query_text=query_text,
                analysis=analysis
            )

        # 原有逻辑: 单语言搜索
        # v3.3.0: 使用 Claude 解析结果优化搜索查询
        optimized_query = self._optimize_search_query(query_text, analysis)

        if optimized_query != query_text:
            logger.info(f"🔍 查询优化: '{query_text}' → '{optimized_query}'")
        else:
            logger.info(f"直接搜索: {query_text}")

        # ���行搜索（获取10条结果）
        logger.info("开始执行单次搜索...")
        # v3.8.0: 使用基础设施层适配器的 search_simple() 方法
        if isinstance(self.search_adapter, FirecrawlSearchAdapter):
            results_dict = await self.search_adapter.search_simple(
                query=optimized_query,
                max_results=nl_search_config.max_search_results
            )
        else:
            # GPT5SearchAdapter 兼容路径
            search_results = await self.gpt5_adapter.search(
                query=optimized_query,
                max_results=nl_search_config.max_search_results
            )
            results_dict = [r.to_dict() for r in search_results]

        logger.info(f"搜索完成: 获得{len(results_dict)}个结果")

        # 分数过滤：只保留高质量结果

        # v3.5.0: 垃圾内容过滤（分数过滤前执行）
        results_dict, spam_count = filter_spam_results(results_dict)
        if spam_count > 0:
            logger.info(f"🚫 垃圾过滤: 移除 {spam_count} 个垃圾结果，剩余 {len(results_dict)} 个")

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

    async def _create_search_multilang(
        self,
        log_id: str,
        query_text: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        多语言搜索模式（v3.7.0 统一优化版 + UnifiedQueryAnalyzer）

        流程：
        1. UnifiedQueryAnalyzer/Claude 统一分析：查询类型 + 语言检测 + 优化搜索词生成（单次API调用）
        2. 并行执行多语言搜索
        3. 聚合去重结果
        4. 抓取内容并返回

        v3.7.0 更新:
        - 使用 UnifiedQueryAnalyzer.decompose_query_with_multilang() 统一函数
        - 保存增强分解结果（parties, event_type, time_sensitivity, search_queries, query_variations）
        - 单次 Claude API 调用（减少延迟和成本）
        """
        try:
            # Step 1: 使用 UnifiedQueryAnalyzer 或 ClaudeClient 进行多语言搜索分析
            unified_analysis = {}  # v3.7.0: 增强分解结果
            query_type_reasoning = ""
            language_reasoning = ""

            if self.use_unified_analyzer and self.unified_analyzer:
                logger.info("🌐 使用 UnifiedQueryAnalyzer 统一分析多语言搜索策略...")
                multilang_analysis = await self.unified_analyzer.decompose_query_with_multilang(
                    query=query_text,
                    context=analysis,
                    languages=["zh", "en", "ja", "ko"]
                )
                # 提取分析结果
                languages = multilang_analysis["languages"]
                multilang_queries = multilang_analysis["multilang_queries"]
                query_type = multilang_analysis.get("event_type", "news_coverage")

                # v3.7.0: 保存 UnifiedQueryAnalyzer 的增强分解结果
                unified_analysis = {
                    "summary": multilang_analysis.get("summary", ""),
                    "event_type": multilang_analysis.get("event_type", ""),
                    "time_sensitivity": multilang_analysis.get("time_sensitivity", ""),
                    "suggested_time_range": multilang_analysis.get("suggested_time_range", ""),
                    "parties": multilang_analysis.get("parties", []),
                    "keywords": multilang_analysis.get("keywords", []),
                    "keywords_en": multilang_analysis.get("keywords_en", []),
                    "search_queries": multilang_analysis.get("search_queries", {}),
                    "query_variations": multilang_analysis.get("query_variations", {}),
                    "search_strategy": multilang_analysis.get("search_strategy", {}),
                }
                query_type_reasoning = multilang_analysis.get("summary", "")
                language_reasoning = f"UnifiedQueryAnalyzer 分析: {len(languages)} 种语言"

                logger.info(
                    f"✅ UnifiedQueryAnalyzer 分析完成: 类型={query_type}, 语言={languages}, "
                    f"当事方={len(unified_analysis['parties'])}, "
                    f"关键词={len(unified_analysis['keywords'])}"
                )
            elif self.use_claude and self.claude_client:
                logger.info("🌐 使用 ClaudeClient 统一分析多语言搜索策略...")
                multilang_analysis = await self.claude_client.analyze_and_generate_multilang_search(
                    query=query_text,
                    context=analysis,
                    min_languages=2,
                    max_languages=5
                )
                # 提取分析结果
                languages = multilang_analysis["languages"]
                multilang_queries = multilang_analysis["multilang_queries"]
                query_type = multilang_analysis.get("query_type", "news_coverage")
                query_type_reasoning = multilang_analysis.get("query_type_reasoning", "")
                language_reasoning = multilang_analysis.get("language_reasoning", "")

                logger.info(
                    f"✅ ClaudeClient 分析完成: 类型={query_type}, 语言={languages}, "
                    f"策略={multilang_analysis.get('search_strategy', '')[:50]}..."
                )
            else:
                raise ValueError("多语言搜索需要启用 UnifiedQueryAnalyzer")

            # Step 3: 并行执行多语言搜索
            # 使用 FirecrawlSearchAdapter.multi_language_search()
            multilang_result = await self.search_adapter.multi_language_search(
                query=query_text,
                multilang_queries=multilang_queries,
                max_results_per_lang=nl_search_config.multilang_results_per_lang,
                tbs=nl_search_config.default_time_filter if nl_search_config.enable_time_filter else None,
                auto_time_filter=nl_search_config.enable_time_filter
            )

            # Step 4: 处理结果
            all_results = multilang_result.get("all_results", [])
            results_by_lang = multilang_result.get("results_by_lang", {})
            stats = multilang_result.get("stats", {})

            logger.info(
                f"多语言搜索完成: 总计 {stats.get('total_results', 0)} 个结果, "
                f"去重后 {stats.get('unique_results', 0)} 个唯一结果"
            )

            # 转换为统一的 SearchResult 格式
            # v3.8.0: 兼容基础设施层返回的领域实体和字典格式
            search_results = []
            for r in all_results:
                # 如果是领域实体，使用适配器的转换方法
                if hasattr(r, 'url') and hasattr(r, 'title') and not hasattr(r, 'to_dict'):
                    # 领域实体，直接构建字典
                    r_dict = self.search_adapter._convert_domain_result_to_dict(r)
                    search_results.append(_SimpleSearchResult(
                        title=r_dict["title"],
                        url=r_dict["url"],
                        snippet=r_dict["snippet"],
                        position=r_dict["position"],
                        score=r_dict["score"],
                        source=r_dict["source"],
                        markdown=r_dict["markdown"],
                        published_date=r_dict["published_date"]
                    ))
                else:
                    # 字典格式，构建 SearchResult
                    search_results.append(_SimpleSearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("snippet", ""),
                        position=r.get("position", 0),
                        score=r.get("score", 0.0),
                        source=r.get("source", "firecrawl"),
                        markdown=r.get("markdown", ""),
                        published_date=r.get("published_date", "")
                    ))

            # 分数过滤：只保留高质量结果
            results_dict = [r.to_dict() for r in search_results]

            # v3.5.0: 垃圾内容过滤（分数过滤前执行）
            results_dict, spam_count = filter_spam_results(results_dict)
            if spam_count > 0:
                logger.info(f"🚫 垃圾过滤: 移除 {spam_count} 个垃圾结果，剩余 {len(results_dict)} 个")

            high_score_results = [
                r for r in results_dict
                if r.get("score", 0.0) >= nl_search_config.score_threshold
            ]
            logger.info(
                f"分数过滤: {len(results_dict)}个结果 → {len(high_score_results)}个高分结果 "
                f"(阈值: {nl_search_config.score_threshold})"
            )

            # Step 5: 并发抓取内容
            enriched_results = await self._scrape_search_results_concurrent(
                search_results=high_score_results,
                max_concurrent=nl_search_config.scrape_max_concurrent,
                log_id=log_id
            )
            logger.info(f"内容抓取完成: {len(enriched_results)}个结果")

            # v3.7.2: 质量门控检查 - 只有足够数量高质量结果才保存
            if nl_search_config.enable_quality_gate:
                min_quality_results = nl_search_config.min_results_for_save or 3
                if len(enriched_results) < min_quality_results:
                    logger.warning(
                        f"⚠️ 质量门控未通过: 结果数量 {len(enriched_results)} < {min_quality_results}，"
                        f"建议重新搜索或调整查询词"
                    )
                    # 不阻止保存，但记录警告
                    # TODO: 在 LangGraph 版本中添加自动重试逻辑

            # Step 6: 保存搜索结果（只保存通过质量门控的结果）
            try:
                await self.repository.update_search_results(
                    log_id=log_id,
                    search_results=enriched_results,
                    results_count=len(enriched_results),
                    total_results=len(results_dict),
                    high_score_results=len(high_score_results),
                    score_threshold=nl_search_config.score_threshold
                )
                logger.info(f"多语言搜索结果已保存: log_id={log_id}")
            except Exception as e:
                logger.warning(f"保存搜索结果失败: {e}")

            # 双写到独立 search_results 集合
            url_to_id = await self._write_to_search_results_collection(log_id, enriched_results)

            # 将 mongo_id 添加回结果，只保留有效结果
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
                    else:
                        filtered_count += 1

            if filtered_count > 0:
                logger.info(
                    f"✅ 结果过滤: {len(enriched_results)} → {len(valid_results)} 个有效结果 "
                    f"(过滤: {filtered_count})"
                )

            # 保存多语言搜索结果到本地 JSON 文件（用于调试）
            try:
                save_dir = Path("data/search_results")
                save_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                query_slug = query_text[:30].replace(" ", "_").replace("/", "_")
                filename = f"{timestamp}_{query_slug}_multilang.json"
                filepath = save_dir / filename

                save_data = {
                    "timestamp": datetime.now().isoformat(),
                    "log_id": log_id,
                    "search_mode": "multilang",
                    "query": query_text,
                    "query_type": query_type,
                    "query_type_reasoning": query_type_reasoning,
                    "languages": languages,
                    "language_reasoning": language_reasoning,
                    "multilang_queries": multilang_queries,
                    "search_strategy": multilang_analysis.get("search_strategy", ""),
                    # v3.7.0: UnifiedQueryAnalyzer 增强分解结果
                    "unified_analysis": unified_analysis,
                    "results_by_lang": results_by_lang,
                    "stats": stats,
                    "total_results": len(results_dict),
                    "high_score_results": len(high_score_results),
                    "valid_results_count": len(valid_results),
                    "results": valid_results,
                }

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

                logger.info(f"💾 多语言搜索结果已保存: {filepath}")

            except Exception as save_error:
                logger.warning(f"⚠️ 保存多语言搜索结果失败: {save_error}")

            # 构建返回结果
            return {
                "log_id": log_id,
                "query_text": query_text,
                "search_mode": "multilang",
                "analysis": analysis,
                "multilang_info": {
                    "query_type": query_type,
                    "query_type_reasoning": query_type_reasoning,
                    "languages": languages,
                    "language_reasoning": language_reasoning,
                    "multilang_queries": multilang_queries,
                    "search_strategy": multilang_analysis.get("search_strategy", ""),
                    # v3.7.0: 包含增强分解结果
                    "unified_analysis": unified_analysis,
                    "results_by_lang": results_by_lang,
                    "stats": stats
                },
                "total_results": len(results_dict),
                "high_score_results": len(high_score_results),
                "score_threshold": nl_search_config.score_threshold,
                "results": valid_results,
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"多语言搜索失败: {e}", exc_info=True)
            # 失败时降级到普通单语言搜索
            logger.info("降级到单语言搜索模式...")
            # 这里需要递归调用，但为了避免死循环，我们临时禁用多语言
            original_enabled = nl_search_config.multilang_enabled
            nl_search_config.multilang_enabled = False
            try:
                result = await self._create_search_single(log_id, query_text, analysis)
                result["search_mode"] = "single_fallback"
                return result
            finally:
                nl_search_config.multilang_enabled = original_enabled

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
                # v3.8.0: 使用基础设施层适配器的 search_simple() 方法
                if isinstance(self.search_adapter, FirecrawlSearchAdapter):
                    result_dicts = await self.search_adapter.search_simple(
                        query=sub_query,
                        max_results=nl_search_config.max_results_per_query
                    )
                    # 添加来源子问题标记
                    for result_dict in result_dicts:
                        result_dict["sub_query"] = sub_query
                        result_dict["sub_query_index"] = idx
                        all_search_results.append(result_dict)
                else:
                    # GPT5SearchAdapter 兼容路径
                    results = await self.gpt5_adapter.search(
                        query=sub_query,
                        max_results=nl_search_config.max_results_per_query
                    )
                    # 标记来源子问题
                    for result in results:
                        result_dict = result.to_dict()
                        result_dict["sub_query"] = sub_query
                        result_dict["sub_query_index"] = idx
                        all_search_results.append(result_dict)

                logger.info(f"[{idx}/{len(sub_queries)}] 获得 {len(result_dicts) if isinstance(self.search_adapter, FirecrawlSearchAdapter) else len(results)} 个结果")

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

        # v3.5.0: Post-scrape 内容质量过滤
        # v3.7.1: 增强版 - 同时过滤 404 页面和垃圾内容（包括缓存结果）
        valid_results = []
        filtered_404_count = 0
        filtered_spam_count = 0

        for result in enriched_results:
            # 检查 markdown_content 或 html_content 是否为 404 页面
            markdown_content = result.get("markdown_content", "")
            html_content = result.get("html_content", "")

            # 优先检查 markdown，因为更简洁
            content_to_check = markdown_content or html_content or ""

            # 1. 404/空内容检查
            if is_404_content(content_to_check):
                filtered_404_count += 1
                url = result.get("url", "N/A")
                logger.info(f"🚫 过滤 404 页面: {url}")
                continue

            # 2. v3.7.1: 重新检查垃圾标题（捕获缓存中的垃圾结果）
            title = result.get("title", "")
            if is_spam_title(title):
                filtered_spam_count += 1
                url = result.get("url", "N/A")
                logger.info(f"🚫 过滤缓存垃圾结果: {title[:50]}... | {url}")
                continue

            # 3. v3.7.1: 检查内容质量 - 过滤过短或无意义内容
            # 抓取后的内容应该有实质内容
            if len(content_to_check) < 200:
                # 内容过短，可能是错误页面或无意义页面
                # 但对于 from_cache=True 的结果，可能是之前抓取的内容被截断
                # 所以只在没有缓存标记时才过滤
                if not result.get("from_cache"):
                    filtered_spam_count += 1
                    logger.info(f"🚫 过滤过短内容: {result.get('url', 'N/A')} (长度: {len(content_to_check)})")
                    continue

            valid_results.append(result)

        if filtered_404_count > 0 or filtered_spam_count > 0:
            logger.info(
                f"✅ 抓取后内容质量过滤: {len(enriched_results)} → {len(valid_results)} 个有效结果 "
                f"(过滤 404: {filtered_404_count}, 垃圾: {filtered_spam_count})"
            )

        return valid_results

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
