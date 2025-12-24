"""
Claude API 客户端

用于 NL Search 的查询分析、增强和结果重排序
支持代理 API 配置

版本: v2.1.0 (OSINT 增强 + 时间验证)
日期: 2025-12-24

v2.1.0 更新:
- 添加时间验证置信度 (HIGH/MEDIUM/LOW/NONE)
- 增强 rerank_results 支持 time_verification
- 时间格式智能识别 (ISO/中文/美式/相对时间)

v2.0.0 更新:
- 引入 Source Tier 来源分层分类
- 实现 5级可信度评分系统
- 增强 rerank_results 支持 source_tier + credibility
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx

logger = logging.getLogger(__name__)


# ============================================
# Source Tier 来源层级定义 (借鉴 OSINT 最佳实践)
# ============================================
SOURCE_TIER_RULES = {
    "official": {
        # 注意: .org 移除，因为太宽泛；只保留政府/教育/军事域名
        "domains": [".gov", ".gov.cn", ".edu", ".edu.cn", ".mil",
                   "gov.cn", "mfa.gov", "state.gov", "whitehouse.gov"],
        "keywords": ["government", "ministry", "official", "白宫", "外交部", "国务院"],
        "tier_score": 1.0,
        "label": "官方",
        "description": "政府官网、教育机构"
    },
    "authoritative": {
        "domains": ["reuters.com", "ap.org", "afp.com", "bbc.com", "bbc.co.uk",
                   "npr.org", "pbs.org", "xinhuanet.com", "chinadaily.com.cn"],
        "keywords": ["reuters", "associated press", "agence france", "bbc", "新华社"],
        "tier_score": 0.9,
        "label": "权威",
        "description": "国际通讯社、权威媒体"
    },
    "mainstream": {
        "domains": ["nytimes.com", "washingtonpost.com", "wsj.com", "economist.com",
                   "theguardian.com", "cnn.com", "bloomberg.com", "ft.com",
                   "scmp.com", "japantimes.co.jp", "straitstimes.com",
                   "163.com", "sina.com.cn", "sohu.com", "qq.com", "ifeng.com"],
        "keywords": ["times", "post", "journal", "news", "herald", "tribune"],
        "tier_score": 0.8,
        "label": "主流",
        "description": "主流媒体、大型新闻网站"
    },
    "specialized": {
        "domains": ["csis.org", "brookings.edu", "rand.org", "cfr.org",
                   "foreignaffairs.com", "diplomat.com", "nature.com", "science.org",
                   "arxiv.org", "ieee.org", "acm.org"],
        "keywords": ["research", "institute", "think tank", "journal", "study", "analysis"],
        "tier_score": 0.75,
        "label": "专业",
        "description": "智库、研究机构、学术来源"
    },
    "general": {
        "domains": ["medium.com", "substack.com", "wordpress.com", "blogspot.com"],
        "keywords": ["blog", "opinion", "comment"],
        "tier_score": 0.6,
        "label": "一般",
        "description": "一般新闻网站、博客"
    },
    "social": {
        "domains": ["twitter.com", "x.com", "facebook.com", "weibo.com",
                   "reddit.com", "quora.com", "zhihu.com"],
        "keywords": ["social", "forum", "community"],
        "tier_score": 0.4,
        "label": "社交",
        "description": "社交媒体、论坛"
    }
}

# ============================================
# 5级可信度评分系统 (借鉴 OSINT Validator)
# ============================================
CREDIBILITY_LEVELS = {
    "confirmed": {
        "symbol": "✅",
        "range": (0.9, 1.0),
        "label": "确认",
        "description": "多源证实，高度可信"
    },
    "reliable": {
        "symbol": "🟢",
        "range": (0.7, 0.9),
        "label": "可信",
        "description": "权威来源，基本可信"
    },
    "unverified": {
        "symbol": "🟡",
        "range": (0.5, 0.7),
        "label": "待核实",
        "description": "单一来源，需谨慎"
    },
    "questionable": {
        "symbol": "🟠",
        "range": (0.3, 0.5),
        "label": "存疑",
        "description": "来源不明，有矛盾"
    },
    "unreliable": {
        "symbol": "🔴",
        "range": (0.0, 0.3),
        "label": "不可靠",
        "description": "无法验证，可能错误"
    }
}

# ============================================
# 时间验证置信度 (借鉴 OSINT Validator)
# ============================================
TIME_CONFIDENCE_LEVELS = {
    "high": {
        "symbol": "🕐",
        "label": "高置信度",
        "description": "有明确发布日期，格式标准",
        "score_bonus": 0.1
    },
    "medium": {
        "symbol": "🕑",
        "label": "中置信度",
        "description": "有日期但格式不标准或为相对时间",
        "score_bonus": 0.05
    },
    "low": {
        "symbol": "🕒",
        "label": "低置信度",
        "description": "日期不明确或无法解析",
        "score_bonus": 0.0
    },
    "none": {
        "symbol": "❓",
        "label": "无日期",
        "description": "未找到发布日期",
        "score_bonus": 0.0
    }
}


# ============================================
# 辅助函数
# ============================================

def classify_source_tier(url: str) -> Dict[str, Any]:
    """
    根据 URL 判断来源层级

    Args:
        url: 网页 URL

    Returns:
        Dict: 包含 tier, tier_score, tier_label, tier_description
    """
    if not url:
        return {
            "tier": "general",
            "tier_score": 0.5,
            "tier_label": "未知",
            "tier_description": "无法识别来源"
        }

    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc

        # 按优先级检查各层级
        for tier_name, tier_info in SOURCE_TIER_RULES.items():
            # 检查域名匹配
            for pattern in tier_info["domains"]:
                if pattern.startswith("."):
                    # 顶级域名匹配 (如 .gov, .edu)
                    if domain.endswith(pattern):
                        return {
                            "tier": tier_name,
                            "tier_score": tier_info["tier_score"],
                            "tier_label": tier_info["label"],
                            "tier_description": tier_info["description"]
                        }
                else:
                    # 完整域名匹配
                    if pattern in domain:
                        return {
                            "tier": tier_name,
                            "tier_score": tier_info["tier_score"],
                            "tier_label": tier_info["label"],
                            "tier_description": tier_info["description"]
                        }

        # 默认返回一般
        return {
            "tier": "general",
            "tier_score": 0.6,
            "tier_label": "一般",
            "tier_description": "一般新闻网站"
        }

    except Exception as e:
        logger.warning(f"classify_source_tier 解析失败: {e}")
        return {
            "tier": "general",
            "tier_score": 0.5,
            "tier_label": "未知",
            "tier_description": "解析失败"
        }


def calculate_credibility(
    rerank_score: float,
    tier_score: float,
    has_date: bool = False,
    multiple_sources: bool = False
) -> Dict[str, Any]:
    """
    计算综合可信度评分

    Args:
        rerank_score: Claude 重排序评分 (0-1)
        tier_score: 来源层级评分 (0-1)
        has_date: 是否有明确日期
        multiple_sources: 是否有多个来源验证

    Returns:
        Dict: 包含 score, level, symbol, label, description
    """
    # 加权计算: rerank 40% + tier 40% + 其他因素 20%
    base_score = rerank_score * 0.4 + tier_score * 0.4

    # 时间明确加分
    if has_date:
        base_score += 0.1

    # 多源验证加分
    if multiple_sources:
        base_score += 0.1

    # 限制范围
    final_score = min(max(base_score, 0.0), 1.0)

    # 确定可信度等级
    for level_name, level_info in CREDIBILITY_LEVELS.items():
        range_min, range_max = level_info["range"]
        if range_min <= final_score <= range_max:
            return {
                "score": round(final_score, 2),
                "level": level_name,
                "symbol": level_info["symbol"],
                "label": level_info["label"],
                "description": level_info["description"]
            }

    # 默认返回待核实
    return {
        "score": round(final_score, 2),
        "level": "unverified",
        "symbol": "🟡",
        "label": "待核实",
        "description": "需要进一步验证"
    }


def verify_publish_date(date_str: Optional[str]) -> Dict[str, Any]:
    """
    验证发布日期的置信度

    Args:
        date_str: 日期字符串 (可以是各种格式)

    Returns:
        Dict: 包含 confidence, parsed_date, symbol, label, description
    """
    from datetime import datetime
    import re

    if not date_str:
        return {
            "confidence": "none",
            "parsed_date": None,
            "symbol": TIME_CONFIDENCE_LEVELS["none"]["symbol"],
            "label": TIME_CONFIDENCE_LEVELS["none"]["label"],
            "description": TIME_CONFIDENCE_LEVELS["none"]["description"],
            "score_bonus": 0.0
        }

    date_str = str(date_str).strip()

    # 标准日期格式模式 (HIGH confidence)
    standard_patterns = [
        # ISO 格式: 2025-12-24, 2025-12-24T10:30:00
        (r'^\d{4}-\d{2}-\d{2}', "%Y-%m-%d"),
        # 美式: December 24, 2025 或 Dec 24, 2025
        (r'^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}', None),
        # 中文: 2025年12月24日
        (r'^\d{4}年\d{1,2}月\d{1,2}日', None),
    ]

    # 相对时间模式 (MEDIUM confidence)
    relative_patterns = [
        r'\d+\s*(小时|hours?|hrs?)\s*(前|ago)',
        r'\d+\s*(天|days?)\s*(前|ago)',
        r'\d+\s*(周|weeks?)\s*(前|ago)',
        r'(昨天|yesterday|today|今天)',
        r'(刚刚|just now|moments? ago)',
    ]

    # 检查标准格式 (HIGH)
    for pattern, _ in standard_patterns:
        if re.search(pattern, date_str, re.IGNORECASE):
            return {
                "confidence": "high",
                "parsed_date": date_str,
                "symbol": TIME_CONFIDENCE_LEVELS["high"]["symbol"],
                "label": TIME_CONFIDENCE_LEVELS["high"]["label"],
                "description": TIME_CONFIDENCE_LEVELS["high"]["description"],
                "score_bonus": TIME_CONFIDENCE_LEVELS["high"]["score_bonus"]
            }

    # 检查相对时间 (MEDIUM)
    for pattern in relative_patterns:
        if re.search(pattern, date_str, re.IGNORECASE):
            return {
                "confidence": "medium",
                "parsed_date": date_str,
                "symbol": TIME_CONFIDENCE_LEVELS["medium"]["symbol"],
                "label": TIME_CONFIDENCE_LEVELS["medium"]["label"],
                "description": TIME_CONFIDENCE_LEVELS["medium"]["description"],
                "score_bonus": TIME_CONFIDENCE_LEVELS["medium"]["score_bonus"]
            }

    # 有内容但格式不明确 (LOW)
    if len(date_str) > 0:
        return {
            "confidence": "low",
            "parsed_date": date_str,
            "symbol": TIME_CONFIDENCE_LEVELS["low"]["symbol"],
            "label": TIME_CONFIDENCE_LEVELS["low"]["label"],
            "description": TIME_CONFIDENCE_LEVELS["low"]["description"],
            "score_bonus": TIME_CONFIDENCE_LEVELS["low"]["score_bonus"]
        }

    return {
        "confidence": "none",
        "parsed_date": None,
        "symbol": TIME_CONFIDENCE_LEVELS["none"]["symbol"],
        "label": TIME_CONFIDENCE_LEVELS["none"]["label"],
        "description": TIME_CONFIDENCE_LEVELS["none"]["description"],
        "score_bonus": 0.0
    }


@dataclass
class ClaudeConfig:
    """Claude API 配置"""
    base_url: str = "http://23.106.129.19:2828/api"
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    timeout: int = 60
    max_tokens: int = 1500


class ClaudeClient:
    """
    Claude API 客户端

    功能:
    1. parse_query - 解析查询意图和关键词
    2. enhance_query - 增强搜索查询
    3. rerank_results - 重排序搜索结果
    4. generate_multilang_queries - 生成多语言查询
    5. summarize_results - 汇总多语言搜索结果

    使用示例:
        client = ClaudeClient(config)
        analysis = await client.parse_query("日本2025防卫白书")
        enhanced = await client.enhance_query("日本2025防卫白书", analysis)
    """

    def __init__(self, config: Optional[ClaudeConfig] = None):
        """初始化客户端"""
        self.config = config or ClaudeConfig()
        self.base_url = self.config.base_url.rstrip('/')

        if not self.config.api_key:
            logger.warning("Claude API Key 未配置")

        logger.info(f"Claude 客户端初始化: base_url={self.base_url}, model={self.config.model}")

    async def _call(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """调用 Claude API"""
        if not self.config.api_key:
            raise ValueError("Claude API Key 未配置")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01"
        }

        body = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=body
            )
            response.raise_for_status()
            data = response.json()

            if "content" in data and len(data["content"]) > 0:
                return data["content"][0].get("text", "")
            return ""

    def _parse_json_response(self, text: str) -> Any:
        """解析 JSON 响应"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    async def parse_query(self, query: str) -> Dict[str, Any]:
        """
        解析查询意图和关键词

        Args:
            query: 用户查询文本

        Returns:
            Dict: 包含 intent, keywords, entities, time_range, category, confidence
        """
        prompt = f"""分析以下用户查询，提取关键信息。

用户查询: {query}

请以 JSON 格式返回:
{{
    "intent": "查询意图描述",
    "keywords": ["关键词1", "关键词2", ...],
    "entities": ["实体1", "实体2", ...],
    "time_range": "时间范围 (如: 最近一周, 2024年, null)",
    "category": "分类 (如: 新闻, 技术, 商业, 政治, 军事, 其他)",
    "confidence": 0.0-1.0
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self._call(prompt, max_tokens=500)
            return self._parse_json_response(response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            return {
                "intent": "general",
                "keywords": query.split(),
                "entities": [],
                "time_range": None,
                "category": "other",
                "confidence": 0.5
            }
        except Exception as e:
            logger.error(f"parse_query 失败: {e}")
            raise

    async def enhance_query(self, query: str, analysis: Dict[str, Any]) -> str:
        """
        增强搜索查询

        Args:
            query: 原始查询
            analysis: parse_query 返回的分析结果

        Returns:
            str: 增强后的搜索查询
        """
        prompt = f"""基于以下用户查询和分析结果，生成一个更精准的搜索查询。

原始查询: {query}
分析结果:
- 意图: {analysis.get('intent')}
- 关键词: {analysis.get('keywords')}
- 实体: {analysis.get('entities')}
- 时间范围: {analysis.get('time_range')}

要求:
1. 保留核心关键词
2. 添加相关限定词提高精准度
3. 使用搜索引擎友好的格式
4. 如果有时间范围，添加时间关键词
5. 输出一行简洁的搜索查询（不超过100字符）

只返回搜索查询文本，不要解释。"""

        try:
            response = await self._call(prompt, max_tokens=200)
            enhanced = response.strip().strip('"').strip("'")

            # 长度限制
            if len(enhanced) > 100:
                enhanced = enhanced[:100]

            return enhanced
        except Exception as e:
            logger.error(f"enhance_query 失败: {e}")
            return query  # 降级返回原始查询

    async def rerank_results(
        self,
        query: str,
        analysis: Dict[str, Any],
        results: List[Dict[str, Any]],
        max_results: int = 15
    ) -> List[Dict[str, Any]]:
        """
        重排序搜索结果 (v2.0.0 OSINT 增强版)

        Args:
            query: 用户查询
            analysis: 查询分析结果
            results: 搜索结果列表
            max_results: 最多处理的结果数

        Returns:
            List[Dict]: 重排序后的结果列表，包含:
                - rerank_score: Claude 相关性评分 (0-1)
                - rerank_reason: 评分理由
                - source_tier: 来源层级信息 (tier, tier_score, tier_label)
                - credibility: 可信度信息 (score, level, symbol, label)
        """
        if not results:
            return results

        # 准备结果摘要
        results_summary = []
        for i, r in enumerate(results[:max_results]):
            results_summary.append({
                "index": i,
                "title": r.get("title", "")[:100],
                "url": r.get("url", "")[:100],
                "snippet": r.get("description", r.get("snippet", ""))[:200]
            })

        prompt = f"""基于用户查询意图，对以下搜索结果进行相关性评分。

用户查询: {query}
查询意图: {analysis.get('intent')}
关键词: {analysis.get('keywords')}

搜索结果:
{json.dumps(results_summary, ensure_ascii=False, indent=2)}

请为每个结果评分 (0.0-1.0)，输出 JSON 数组:
[
  {{"index": 0, "score": 0.95, "reason": "高度相关"}},
  {{"index": 1, "score": 0.80, "reason": "部分相关"}},
  ...
]

只返回 JSON 数组，不要其他内容。按 score 从高到低排序。"""

        try:
            response = await self._call(prompt, max_tokens=1500)
            scores = self._parse_json_response(response)

            # 按分数排序
            scores.sort(key=lambda x: x.get("score", 0), reverse=True)

            # 重排序结果并添加 OSINT 增强信息
            reranked = []
            for s in scores:
                idx = s.get("index", 0)
                if 0 <= idx < len(results):
                    result = results[idx].copy()
                    rerank_score = s.get("score", 0)
                    result["rerank_score"] = rerank_score
                    result["rerank_reason"] = s.get("reason", "")

                    # v2.0.0: 添加 Source Tier 来源层级
                    url = result.get("url", "")
                    source_tier_info = classify_source_tier(url)
                    result["source_tier"] = source_tier_info

                    # v2.1.0: 添加时间验证
                    date_str = result.get("published_date") or result.get("date") or result.get("publish_date")
                    time_verification = verify_publish_date(date_str)
                    result["time_verification"] = time_verification
                    has_valid_date = time_verification["confidence"] in ("high", "medium")

                    # v2.0.0: 添加 5级可信度评分 (使用时间验证结果)
                    credibility_info = calculate_credibility(
                        rerank_score=rerank_score,
                        tier_score=source_tier_info["tier_score"],
                        has_date=has_valid_date,
                        multiple_sources=False  # 单结果暂不支持多源验证
                    )
                    result["credibility"] = credibility_info

                    reranked.append(result)

            logger.info(f"Rerank 完成: {len(reranked)} 结果，已添加 source_tier + credibility + time_verification")
            return reranked

        except json.JSONDecodeError:
            logger.warning("Rerank JSON 解析失败，返回带基础增强的原始结果")
            # 降级：仍然添加 source_tier 和 credibility
            return self._add_basic_enhancements(results[:max_results])
        except Exception as e:
            logger.error(f"rerank_results 失败: {e}")
            return self._add_basic_enhancements(results[:max_results])

    def _add_basic_enhancements(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        降级时添加基础增强信息

        当 Claude API 调用失败时，仍然为结果添加 source_tier, time_verification 和 credibility
        """
        enhanced = []
        for i, result in enumerate(results):
            r = result.copy()
            url = r.get("url", "")

            # 添加 Source Tier
            source_tier_info = classify_source_tier(url)
            r["source_tier"] = source_tier_info

            # v2.1.0: 添加时间验证
            date_str = r.get("published_date") or r.get("date") or r.get("publish_date")
            time_verification = verify_publish_date(date_str)
            r["time_verification"] = time_verification
            has_valid_date = time_verification["confidence"] in ("high", "medium")

            # 使用默认评分计算可信度
            credibility_info = calculate_credibility(
                rerank_score=0.5,  # 默认中等相关性
                tier_score=source_tier_info["tier_score"],
                has_date=has_valid_date,
                multiple_sources=False
            )
            r["credibility"] = credibility_info

            # 设置默认 rerank 信息
            r["rerank_score"] = 0.5
            r["rerank_reason"] = "API 降级，使用默认评分"

            enhanced.append(r)

        return enhanced

    async def generate_multilang_queries(
        self,
        query: str,
        languages: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        生成多语言查询

        Args:
            query: 原始查询
            languages: 目标语言列表，默认 ["zh", "en", "ja", "ko"]

        Returns:
            Dict[str, str]: 语言代码 -> 搜索查询 的映射
        """
        if languages is None:
            languages = ["zh", "en", "ja", "ko"]

        lang_names = {
            "zh": "中文",
            "en": "英语",
            "ja": "日语",
            "ko": "韩语",
            "ru": "俄语",
            "fr": "法语",
            "de": "德语"
        }

        lang_desc = ", ".join([f'"{lang}": "{lang_names.get(lang, lang)}搜索查询"' for lang in languages])

        prompt = f"""将以下查询翻译成多种语言，用于搜索引擎搜索。

原始查询: {query}

请生成以下语言的搜索查询，每个查询应该：
1. 保留核心搜索意图
2. 使用该语言的常用搜索词
3. 适合搜索引擎使用

以 JSON 格式返回:
{{
    {lang_desc}
}}

只返回 JSON，不要其他内容。根据查询主题，只生成相关语言的查询（如果某语言不相关可以省略）。"""

        try:
            response = await self._call(prompt, max_tokens=500)
            return self._parse_json_response(response)
        except json.JSONDecodeError:
            logger.warning("多语言查询 JSON 解析失败")
            return {"zh": query, "en": query}
        except Exception as e:
            logger.error(f"generate_multilang_queries 失败: {e}")
            return {"zh": query}

    async def summarize_multilang_results(
        self,
        query: str,
        results: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        汇总多语言搜索结果

        Args:
            query: 原始查询
            results: 按语言分组的搜索结果

        Returns:
            str: Markdown 格式的汇总分析
        """
        # 准备结果摘要
        summary_parts = []
        lang_names = {"zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语"}

        for lang, items in results.items():
            lang_name = lang_names.get(lang, lang)
            summary_parts.append(f"\n### {lang_name}来源 ({len(items)}条)")
            for item in items[:5]:
                title = item.get("title", "")[:80]
                snippet = item.get("description", item.get("snippet", ""))[:150]
                summary_parts.append(f"- {title}")
                if snippet:
                    summary_parts.append(f"  摘要: {snippet}")

        results_text = "\n".join(summary_parts)

        prompt = f"""基于多语言搜索结果，生成一份综合分析摘要。

原始查询: {query}

多语言搜索结果:
{results_text}

请生成:
1. 核心发现摘要 (3-5个要点)
2. 各语言来源的独特信息
3. 信息交叉验证情况
4. 推荐优先阅读的来源

用中文回答，结构清晰。"""

        try:
            return await self._call(prompt, max_tokens=2000)
        except Exception as e:
            logger.error(f"summarize_multilang_results 失败: {e}")
            return f"汇总失败: {e}"


# 工厂函数
def create_claude_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> ClaudeClient:
    """
    创建 Claude 客户端

    优先级: 参数 > 环境变量 > 默认值
    """
    import os

    config = ClaudeConfig(
        base_url=base_url or os.getenv("ANTHROPIC_BASE_URL", "http://23.106.129.19:2828/api"),
        api_key=api_key or os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        model=model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )

    return ClaudeClient(config)
