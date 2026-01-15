"""
Claude Search Agent v2.1 - 增强版

基于 OSINT Search Agent 规范优化:
- country 参数支持 (ISO 国家代码)
- 查询运算符 (-wikipedia, "精确匹配")
- source_tier 来源分类 (official/local_mainstream/intl_mainstream/think_tank)
- 增强输出格式 (可信度评分、时间验证)

版本: v2.1.0
日期: 2025-12-25
"""
import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.services.nl_search.config import nl_search_config
from src.infrastructure.llm.claude_client import create_claude_client
from src.infrastructure.database.claude_search_session_repository import claude_search_session_repository


logger = logging.getLogger(__name__)


# =============================================================================
# 来源层级定义
# =============================================================================

class SourceTier(Enum):
    """来源层级枚举"""
    OFFICIAL = "official"              # 官方来源 (政府、外交部、官方通讯社)
    LOCAL_MAINSTREAM = "local_mainstream"  # 当地主流媒体
    INTL_MAINSTREAM = "intl_mainstream"    # 国际主流媒体
    THINK_TANK = "think_tank"          # 智库/专业分析
    OTHER = "other"                    # 其他来源


SOURCE_TIER_LABELS = {
    SourceTier.OFFICIAL: "官方来源",
    SourceTier.LOCAL_MAINSTREAM: "当地主流",
    SourceTier.INTL_MAINSTREAM: "国际主流",
    SourceTier.THINK_TANK: "智库分析",
    SourceTier.OTHER: "其他",
}

SOURCE_TIER_CREDIBILITY = {
    SourceTier.OFFICIAL: 0.95,
    SourceTier.LOCAL_MAINSTREAM: 0.85,
    SourceTier.INTL_MAINSTREAM: 0.85,
    SourceTier.THINK_TANK: 0.75,
    SourceTier.OTHER: 0.50,
}


# =============================================================================
# 来源分类器
# =============================================================================

class SourceClassifier:
    """基于 URL 模式自动分类信息源层级"""

    OFFICIAL_PATTERNS = [
        # 政府域名
        r"\.gov\.", r"\.go\.", r"\.gouv\.", r"\.gob\.",
        # 外交部
        r"mofa\.", r"mfa\.", r"foreign\.",
        # 国防部
        r"mod\.", r"defense\.", r"defence\.",
        # 总统/总理
        r"president\.", r"kantei\.", r"bluehouse\.",
        # 官方通讯社
        r"nhk\.", r"kyodonews\.", r"yonhap\.", r"cna\.com\.tw",
        r"xinhua", r"chinanews",
    ]

    LOCAL_MAINSTREAM_PATTERNS = [
        # 日本
        r"asahi\.", r"yomiuri\.", r"mainichi\.", r"nikkei\.", r"japantimes",
        # 韩国
        r"chosun\.", r"donga\.", r"hani\.", r"koreaherald", r"koreatimes",
        # 台湾
        r"udn\.com", r"ltn\.com", r"chinatimes", r"taipeitimes",
        # 东南亚
        r"straitstimes", r"channelnewsasia", r"bangkokpost", r"nationthailand",
        r"vnexpress", r"inquirer\.net", r"rappler",
        # 通用模式
        r"times\.", r"post\.", r"daily\.", r"news\.",
    ]

    INTL_MAINSTREAM_PATTERNS = [
        r"reuters\.", r"apnews\.", r"afp\.", r"bbc\.", r"cnn\.",
        r"aljazeera", r"theguardian", r"nytimes", r"washingtonpost",
        r"scmp\.com", r"bloomberg\.", r"ft\.com",
    ]

    THINK_TANK_PATTERNS = [
        r"csis\.", r"brookings\.", r"carnegie", r"rand\.",
        r"iseas\.", r"aspi\.", r"crisisgroup",
        r"cfr\.org", r"chathamhouse", r"iiss\.",
        r"thediplomat",
    ]

    # 百科类 - 仅供参考，不作为主要来源
    ENCYCLOPEDIA_PATTERNS = [
        # 百科类
        r"wikipedia\.", r"baike\.baidu", r"baike\.so\.com", r"baike\.sogou",
        r"britannica\.com", r"encyclopedia\.", r"wiki\.",
        # 问答/论坛类
        r"zhihu\.", r"quora\.", r"stackoverflow\.", r"segmentfault\.",
        r"reddit\.", r"tieba\.baidu",
        # 博客平台
        r"blog\.", r"medium\.com", r"csdn\.", r"jianshu\.",
    ]
    # 注意: Twitter/Facebook/YouTube 保留，可能有官方账号发布的重要信息

    EXCLUDED_PATTERNS = ENCYCLOPEDIA_PATTERNS  # 别名保持兼容

    @classmethod
    def classify(cls, url: str, source_name: str = "") -> Tuple[SourceTier, float]:
        """
        分类 URL 的来源层级

        Returns:
            (SourceTier, credibility_score)
        """
        url_lower = url.lower()

        # 检查排除模式
        for pattern in cls.EXCLUDED_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.OTHER, 0.3

        # 检查官方来源
        for pattern in cls.OFFICIAL_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.OFFICIAL, SOURCE_TIER_CREDIBILITY[SourceTier.OFFICIAL]

        # 检查智库
        for pattern in cls.THINK_TANK_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.THINK_TANK, SOURCE_TIER_CREDIBILITY[SourceTier.THINK_TANK]

        # 检查国际主流
        for pattern in cls.INTL_MAINSTREAM_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.INTL_MAINSTREAM, SOURCE_TIER_CREDIBILITY[SourceTier.INTL_MAINSTREAM]

        # 检查当地主流
        for pattern in cls.LOCAL_MAINSTREAM_PATTERNS:
            if re.search(pattern, url_lower):
                return SourceTier.LOCAL_MAINSTREAM, SOURCE_TIER_CREDIBILITY[SourceTier.LOCAL_MAINSTREAM]

        return SourceTier.OTHER, SOURCE_TIER_CREDIBILITY[SourceTier.OTHER]


# =============================================================================
# 语言 → Country 映射
# =============================================================================

LANG_TO_COUNTRY = {
    "zh": "CN",
    "en": "US",
    "ja": "JP",
    "ko": "KR",
    "ru": "RU",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "ar": "SA",
    "vi": "VN",
    "th": "TH",
    "pt": "BR",
    "id": "ID",
    "ms": "MY",
    "tl": "PH",
}

LANG_TO_LOCATION = {
    "zh": "China",
    "en": "United States",
    "ja": "Japan",
    "ko": "South Korea",
    "ru": "Russia",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "ar": "Saudi Arabia",
    "vi": "Vietnam",
    "th": "Thailand",
    "pt": "Brazil",
    "id": "Indonesia",
    "ms": "Malaysia",
    "tl": "Philippines",
}


# tbs → 时间范围提示
TBS_RANGE_HINTS = {
    "qdr:h": "过去1小时内",
    "qdr:d": "过去24小时内",
    "qdr:w": "过去一周内",
    "qdr:m": "过去一个月内",
    "qdr:y": "过去一年内",
}


# =============================================================================
# Claude Prompt - v2.1 增强版
# =============================================================================

SEARCH_CONFIG_PROMPT_V21 = """Generate search configs for: {query}

Output ONLY valid JSON array, no explanation:
[
  {{"query": "...", "lang": "zh", "limit": 50, "tbs": "qdr:m", "location": "China", "country": "CN"}},
  {{"query": "...", "lang": "en", "limit": 50, "tbs": "qdr:m", "location": "United States", "country": "US"}}
]

TIME FILTER (tbs) - IMPORTANT:
Detect time expressions in the query and set appropriate tbs for ALL configs:
- "today/今天/今日/24小时" → "qdr:d" (past day)
- "this week/最近一周/本周/近几天/七天" → "qdr:w" (past week)
- "this month/最近一个月/本月/近期/最近/30天" → "qdr:m" (past month)
- "this year/最近一年/今年/近年/年内" → "qdr:y" (past year)
- No time mentioned → "qdr:w" (default to past week)

Rules:
- EXCLUDE encyclopedias: -wikipedia -百度百科 -知乎 -quora -medium -blog
- Use "exact phrase" for key terms
- Add news keywords: 新闻/ニュース/뉴스/news
- Select 3-6 relevant languages based on topic region
- lang→country: zh→CN, en→US, ja→JP, ko→KR, ru→RU, de→DE, fr→FR
- All configs MUST use the SAME tbs value based on detected time expression

Return ONLY JSON array."""


# =============================================================================
# 时间过滤器检测 (备用方案)
# =============================================================================

TIME_PATTERNS = {
    # 过去一天
    "qdr:d": [
        r"today|今天|今日|24小时|当天|本日",
        r"오늘|きょう|今日中|当日",
    ],
    # 过去一周
    "qdr:w": [
        r"this\s*week|最近一周|本周|近几天|七天|7天|一周内",
        r"过去一周|上周|이번\s*주|今週|近日",
    ],
    # 过去一个月
    "qdr:m": [
        r"this\s*month|最近一个月|本月|近期|最近|30天|三十天|一个月",
        r"过去一个月|上月|이번\s*달|今月|近一个月|近月",
    ],
    # 过去一年
    "qdr:y": [
        r"this\s*year|最近一年|今年|年内|近年|一年内|12个月",
        r"过去一年|去年|올해|今年中|近一年",
    ],
}


def detect_time_filter(query: str) -> str:
    """
    从自然语言查询中检测时间过滤器

    Args:
        query: 用户查询字符串

    Returns:
        tbs 时间过滤值 (qdr:d, qdr:w, qdr:m, qdr:y)
        默认返回 qdr:w (一周)
    """
    query_lower = query.lower()

    # 按优先级检测: 天 → 周 → 月 → 年
    for tbs, patterns in TIME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                logger.info(f"检测到时间表达式 → {tbs}: {pattern}")
                return tbs

    # 默认返回一周
    return "qdr:w"


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class EnhancedSearchResult:
    """增强的搜索结果"""
    source_id: str
    title: str
    url: str
    snippet: str

    # 来源分类
    source_tier: str
    source_tier_label: str
    credibility_score: float

    # 语言和地区
    language: str
    country: str
    search_query: str

    # 时间元数据
    published_date: Optional[str] = None  # Firecrawl 返回的真实发布时间
    time_verified: bool = False  # True=真实发布时间, False=无发布时间
    crawled_at: Optional[str] = None  # 采集时间 (ISO 格式)
    time_range_hint: Optional[str] = None  # 根据 tbs 推断的时间范围提示

    # 评分
    relevance_score: float = 0.0
    position: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Claude Search Agent v2.1
# =============================================================================

class ClaudeSearchAgentV21:
    """
    Claude Search Agent v2.1 - 增强版

    新增功能:
    - country 参数 (ISO 国家代码)
    - 查询运算符 (排除百科、精确匹配)
    - source_tier 来源分类
    - 可信度评分
    - 增强输出格式
    """

    def __init__(self, test_mode: bool = False):
        """初始化"""
        self.test_mode = test_mode
        self.classifier = SourceClassifier()

        # Claude 客户端
        self.claude_client = None
        if nl_search_config.claude_enabled:
            try:
                self.claude_client = create_claude_client()
                logger.info("Claude 客户端已初始化")
            except Exception as e:
                logger.warning(f"Claude 初始化失败: {e}")

        # Firecrawl 适配器
        self.adapter = FirecrawlSearchAdapter(test_mode=test_mode)

        logger.info(f"ClaudeSearchAgentV21 initialized: claude={'ready' if self.claude_client else 'unavailable'}")

    def _extract_json_array(self, text: str) -> Optional[List[Dict]]:
        """从文本中提取 JSON 数组，使用多种策略"""
        # 策略 1: 直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 code block
        if "```json" in text:
            try:
                json_str = text.split("```json")[1].split("```")[0]
                return json.loads(json_str.strip())
            except (IndexError, json.JSONDecodeError):
                pass

        if "```" in text:
            try:
                json_str = text.split("```")[1].split("```")[0]
                return json.loads(json_str.strip())
            except (IndexError, json.JSONDecodeError):
                pass

        # 策略 3: 正则匹配 JSON 数组
        try:
            match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass

        # 策略 4: 修复常见问题 (尾部逗号, 单引号)
        try:
            # 移除尾部逗号
            fixed = re.sub(r',(\s*[\]\}])', r'\1', text)
            # 单引号转双引号 (小心处理)
            fixed = re.sub(r"'([^']*)':", r'"\1":', fixed)
            match = re.search(r'\[\s*\{.*?\}\s*\]', fixed, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass

        return None

    async def _generate_configs(self, query: str) -> List[Dict[str, Any]]:
        """使用 Claude 生成增强搜索配置"""
        # 预先检测时间过滤器作为备用
        detected_tbs = detect_time_filter(query)
        logger.info(f"时间过滤器检测结果: {detected_tbs} (原始查询: {query[:50]}...)")

        if not self.claude_client:
            logger.warning("Claude 不可用，使用默认配置")
            return self._default_configs(query, tbs=detected_tbs)

        try:
            prompt = SEARCH_CONFIG_PROMPT_V21.format(query=query)
            response_text = await self.claude_client._call(prompt, max_tokens=2000)

            # 使用增强的 JSON 提取
            configs = self._extract_json_array(response_text)

            if not configs:
                logger.warning(f"无法解析 Claude 响应，使用默认配置")
                logger.debug(f"原始响应: {response_text[:200]}...")
                return self._default_configs(query, tbs=detected_tbs)

            # 验证和补全配置
            validated = []
            for cfg in configs:
                if not isinstance(cfg, dict) or "query" not in cfg:
                    continue

                lang = cfg.get("lang", "en")
                cfg_query = cfg["query"]

                # 强制添加排除词（如果缺失）
                cfg_query = self._ensure_exclusions(cfg_query, lang)

                # 获取 Claude 生成的 tbs，如果是默认值则使用检测到的值
                claude_tbs = cfg.get("tbs", "qdr:w")
                # 如果 Claude 返回默认值但我们检测到了具体时间，使用检测结果
                final_tbs = detected_tbs if (claude_tbs == "qdr:w" and detected_tbs != "qdr:w") else claude_tbs

                validated.append({
                    "query": cfg_query,
                    "lang": lang,
                    "limit": cfg.get("limit", 50),
                    "tbs": final_tbs,
                    "location": cfg.get("location") or LANG_TO_LOCATION.get(lang),
                    "country": cfg.get("country") or LANG_TO_COUNTRY.get(lang, "US"),
                    "timeout": 90000,
                })

            if not validated:
                return self._default_configs(query, tbs=detected_tbs)

            # 记录最终使用的 tbs 值
            tbs_values = set(v["tbs"] for v in validated)
            logger.info(f"Claude 生成 {len(validated)} 个搜索配置 (v2.1), tbs: {tbs_values}")
            return validated

        except Exception as e:
            logger.error(f"配置生成失败: {e}")
            return self._default_configs(query, tbs=detected_tbs)

    def _ensure_exclusions(self, query: str, lang: str) -> str:
        """确保查询包含排除词

        Args:
            query: 原始查询字符串
            lang: 语言代码

        Returns:
            添加排除词后的查询字符串
        """
        # 通用排除词（所有语言）
        common_exclusions = ["-wikipedia", "-blog", "-medium"]

        # 语言特定排除词
        lang_exclusions = {
            "zh": ["-百度百科", "-知乎"],
            "en": ["-quora", "-reddit"],
            "ja": ["-ウィキペディア"],
            "ko": ["-나무위키", "-위키백과"],
        }

        # 获取需要添加的排除词
        exclusions_to_add = []

        # 检查通用排除词
        for exc in common_exclusions:
            if exc not in query.lower():
                exclusions_to_add.append(exc)

        # 检查语言特定排除词
        for exc in lang_exclusions.get(lang, []):
            if exc not in query:
                exclusions_to_add.append(exc)

        # 添加缺失的排除词
        if exclusions_to_add:
            query = f"{query} {' '.join(exclusions_to_add)}"

        return query

    def _default_configs(self, query: str, tbs: str = "qdr:w") -> List[Dict[str, Any]]:
        """默认配置 - 排除百科类来源

        Args:
            query: 搜索查询字符串
            tbs: 时间过滤器 (qdr:d=天, qdr:w=周, qdr:m=月, qdr:y=年)

        Returns:
            默认搜索配置列表
        """
        logger.info(f"使用默认配置，tbs={tbs}")
        return [
            {
                "query": f'"{query}" 新闻 -wikipedia -百度百科 -知乎 -blog -medium',
                "lang": "zh",
                "limit": 50,
                "tbs": tbs,
                "location": "China",
                "country": "CN",
                "timeout": 90000,
            },
            {
                "query": f'"{query}" news -wikipedia -quora -medium -blog -reddit',
                "lang": "en",
                "limit": 50,
                "tbs": tbs,
                "location": "United States",
                "country": "US",
                "timeout": 90000,
            },
        ]

    async def _execute_search(self, config: Dict[str, Any], index: int) -> Dict[str, Any]:
        """执行单个搜索"""
        try:
            results = await self.adapter.search(
                query=config["query"],
                max_results=config.get("limit", 20),
                location=config.get("location"),
                country=config.get("country"),      # v2.1: ISO 国家代码
                tbs=config.get("tbs", "qdr:d"),
                timeout=config.get("timeout"),      # v2.1: 超时设置
                auto_detect_location=False,
                auto_time_filter=False
            )

            # 增强结果
            # 获取采集时间和时间范围提示
            crawled_at = datetime.now().isoformat()
            tbs = config.get("tbs", "qdr:w")
            time_range_hint = TBS_RANGE_HINTS.get(tbs, "未知时间范围")

            enhanced_results = []
            for i, r in enumerate(results):
                # 分类来源
                tier, credibility = self.classifier.classify(r.url, r.title)

                # 处理发布时间
                raw_published_date = r.published_date if hasattr(r, 'published_date') else None
                has_published_date = bool(raw_published_date)

                enhanced = EnhancedSearchResult(
                    source_id=f"{config['lang'].upper()}-{index:02d}-{i+1:03d}",
                    title=r.title,
                    url=r.url,
                    snippet=r.snippet,
                    source_tier=tier.value,
                    source_tier_label=SOURCE_TIER_LABELS[tier],
                    credibility_score=credibility,
                    language=config.get("lang", "en"),
                    country=config.get("country", "US"),
                    search_query=config["query"][:50],
                    published_date=raw_published_date,
                    time_verified=has_published_date,
                    crawled_at=crawled_at,
                    time_range_hint=time_range_hint if not has_published_date else None,
                    relevance_score=r.score,
                    position=i + 1,
                )
                enhanced_results.append(enhanced.to_dict())

            return {
                "config": config,
                "results": enhanced_results,
                "success": True
            }

        except Exception as e:
            logger.error(f"搜索失败 [{config['query'][:30]}...]: {e}")
            return {
                "config": config,
                "results": [],
                "success": False,
                "error": str(e)
            }

    async def _execute_all(self, configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并行执行所有搜索"""
        tasks = [self._execute_search(cfg, i) for i, cfg in enumerate(configs)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _aggregate_results(self, search_results: List[Dict[str, Any]]) -> Tuple[List[Dict], Dict]:
        """聚合结果并统计来源层级"""
        seen_urls = set()
        all_results = []
        tier_stats = {tier.value: 0 for tier in SourceTier}
        lang_stats = {}

        for sr in search_results:
            if isinstance(sr, Exception):
                continue
            if not sr.get("success"):
                continue

            lang = sr["config"].get("lang", "unknown")
            lang_stats[lang] = lang_stats.get(lang, 0)

            for result in sr.get("results", []):
                url = result.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(result)

                    # 统计
                    tier = result.get("source_tier", "other")
                    tier_stats[tier] = tier_stats.get(tier, 0) + 1
                    lang_stats[lang] = lang_stats.get(lang, 0) + 1

        # 按可信度和相关性排序
        all_results.sort(key=lambda r: (
            -r.get("credibility_score", 0),
            -r.get("relevance_score", 0)
        ))

        return all_results, {"by_tier": tier_stats, "by_lang": lang_stats}

    async def search(
        self,
        query: str,
        save_to_db: bool = True,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行智能搜索 v2.1

        Args:
            query: 搜索查询
            save_to_db: 是否保存到数据库 (默认True)
            user_id: 用户ID，用于数据隔离 (可选)

        Returns:
            Dict: 搜索结果，包含 query, version, configs, results, stats, timestamp
                  如果 save_to_db=True，还包含 session_id
        """
        start_time = time.time()

        print("\n" + "=" * 80)
        print("🤖 Claude Search Agent v2.1 (增强版)")
        print("=" * 80)
        print(f"📝 查询: {query}")
        print("-" * 80)

        # Step 1: Claude 生成配置
        print("\n🧠 Step 1: Claude 生成搜索配置...")
        configs = await self._generate_configs(query)
        print(f"   ✅ 生成 {len(configs)} 个配置:")
        for i, cfg in enumerate(configs, 1):
            q = cfg['query'][:45] + "..." if len(cfg['query']) > 45 else cfg['query']
            print(f"      [{i}] [{cfg.get('lang', '?')}] {q}")
            print(f"          country={cfg.get('country')}, location={cfg.get('location')}")

        # Step 2: 并行执行搜索
        print(f"\n🔍 Step 2: 并行执行 {len(configs)} 个搜索...")
        search_results = await self._execute_all(configs)

        success_count = 0
        total_raw = 0
        for sr in search_results:
            if isinstance(sr, Exception):
                continue
            if sr.get("success"):
                success_count += 1
                total_raw += len(sr.get("results", []))
                lang = sr["config"].get("lang", "?")
                print(f"   ✅ [{lang}] {len(sr['results'])} 条结果")
            else:
                lang = sr["config"].get("lang", "?")
                print(f"   ❌ [{lang}] 失败: {sr.get('error', 'unknown')[:30]}")

        # Step 3: 聚合和分类
        print(f"\n📦 Step 3: 聚合去重 + 来源分类...")
        all_results, stats = self._aggregate_results(search_results)
        print(f"   ✅ 去重后: {len(all_results)} 条结果")

        # 来源层级统计
        print(f"\n📊 来源层级分布:")
        for tier, count in stats["by_tier"].items():
            if count > 0:
                label = SOURCE_TIER_LABELS.get(SourceTier(tier), tier)
                print(f"   {label}: {count} 条")

        total_time = time.time() - start_time

        # 构建返回结果
        result = {
            "query": query,
            "version": "v2.1.0",
            "configs": configs,
            "results": all_results,
            "stats": {
                "total_results": len(all_results),
                "configs_count": len(configs),
                "success_count": success_count,
                "raw_results_count": total_raw,
                "by_source_tier": stats["by_tier"],
                "by_language": stats["by_lang"],
                "execution_time": round(total_time, 2)
            },
            "timestamp": datetime.now().isoformat()
        }

        # Step 4: 保存到数据库
        session_id = None
        if save_to_db:
            try:
                print(f"\n💾 Step 4: 保存到数据库...")
                session_id = await claude_search_session_repository.create_session(
                    query=query,
                    version=result["version"],
                    configs=configs,
                    results=all_results,
                    stats=result["stats"],
                    user_id=user_id,
                    timestamp=result["timestamp"]
                )
                result["session_id"] = session_id
                print(f"   ✅ 已保存: session_id={session_id}")
            except Exception as e:
                logger.warning(f"保存到数据库失败: {e}")
                print(f"   ⚠️ 保存失败: {e}")

        # 打印摘要
        print("\n" + "-" * 80)
        print(f"📊 搜索结果摘要:")
        print(f"   搜索配置: {len(configs)} 个")
        print(f"   成功执行: {success_count} 个")
        print(f"   原始结果: {total_raw} 条")
        print(f"   去重结果: {len(all_results)} 条")
        print(f"   总耗时: {total_time:.2f}s")
        if session_id:
            print(f"   会话ID: {session_id}")
        print("-" * 80)

        # 显示前 10 条结果
        print(f"\n📰 前 10 条结果 (按可信度排序):")
        for i, r in enumerate(all_results[:10], 1):
            tier_label = r.get("source_tier_label", "?")[:4]
            cred = r.get("credibility_score", 0)
            lang = r.get("language", "?")[:2]
            title = r.get("title", "N/A")[:50]
            print(f"[{i:2d}] [{tier_label}] [{cred:.2f}] [{lang}] {title}")

        print("\n" + "=" * 80)

        return result

    async def close(self):
        """关闭资源"""
        if self.adapter:
            await self.adapter.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# =============================================================================
# 便捷函数
# =============================================================================

async def smart_search_v21(query: str, test_mode: bool = False) -> Dict[str, Any]:
    """便捷函数: v2.1 智能搜索"""
    async with ClaudeSearchAgentV21(test_mode=test_mode) as agent:
        return await agent.search(query)
