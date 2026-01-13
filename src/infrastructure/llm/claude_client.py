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
from dataclasses import dataclass, field
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
            "fr": "法语",
            "de": "德语",
            "ru": "俄语",
            "es": "西班牙语",
            "ar": "阿拉伯语",
            "pt": "葡萄牙语",
            "it": "意大利语",
            "vi": "越南语",
            "th": "泰语",
            "id": "印尼语"
        }

        # 构建语言列表说明
        lang_list = ", ".join([f'"{lang}" ({lang_names.get(lang, lang)})' for lang in languages])

        # 构建示例
        example_json = {
            lang: f"{query} 的{lang_names.get(lang, lang)}搜索词" for lang in languages[:2]  # 只展示前2个作为示例
        }
        example_str = json.dumps(example_json, ensure_ascii=False)

        prompt = f"""将以下查询翻译成多种语言，用于搜索引擎搜索。

原始查询: {query}

请为以下语言生成搜索查询：{lang_list}

要求：
1. 保留核心搜索意图
2. 使用该语言的常用搜索词
3. 适合搜索引擎使用（简洁、有效）
4. 必须为所有指定的语言生成查询，不要省略

返回格式（严格遵循）：
{example_str}

注意：
- 必须返回 JSON 格式
- 必须包含所有请求的语言: {languages}
- 只返回 JSON，不要其他内容
- 不要使用 markdown 代码块"""

        try:
            response = await self._call(prompt, max_tokens=500)
            parsed = self._parse_json_response(response)

            # 验证返回结果包含所有请求的语言
            if not isinstance(parsed, dict):
                raise ValueError("返回结果不是字典")

            # 检查缺失的语言，使用原文补充
            missing_langs = [lang for lang in languages if lang not in parsed]
            if missing_langs:
                logger.warning(f"LLM 未生成以下语言的查询: {missing_langs}，使用原文补充")
                for lang in missing_langs:
                    parsed[lang] = query

            return parsed

        except json.JSONDecodeError as e:
            logger.warning(f"多语言查询 JSON 解析失败: {e}")
            # Fallback: 返回所有请求的语言，使用原文
            return {lang: query for lang in languages}
        except Exception as e:
            logger.error(f"generate_multilang_queries 失败: {e}")
            # Fallback: 返回所有请求的语言，使用原文
            return {lang: query for lang in languages}

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

    async def decompose_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> "QueryDecomposition":
        """
        使用 Claude 分解复杂查询为多个子查询

        Args:
            query: 用户原始查询
            context: 搜索上下文（目标网站、语言、时间范围等）

        Returns:
            QueryDecomposition: 分解结果
        """
        if context is None:
            context = {}

        target_domains = context.get("target_domains", "无限制")
        language = context.get("language", "中文或英文")
        time_range = context.get("time_range", "不限")

        prompt = f"""你是一个专业的搜索查询优化专家。你的任务是将用户的复杂查询分解为多个有针对性的子查询，以便通过搜索引擎获得更全面的结果。

分解原则：
1. 覆盖性：子查询应覆盖原始查询的所有关键方面
2. 独立性：每个子查询应该是独立的、可以单独搜索的
3. 针对性：每个子查询应该针对一个具体的信息需求
4. 简洁性：避免过度分解，通常2-5个子查询为宜
5. 可搜索性：子查询应该是搜索引擎友好的

原始查询："{query}"

搜索上下文：
- 目标网站：{target_domains}
- 语言偏好：{language}
- 时间范围：{time_range}

请以 JSON 格式返回（不要使用 markdown 代码块）：
{{
  "decomposed_queries": [
    {{
      "query": "子查询文本",
      "reasoning": "为什么需要这个子查询的解释",
      "focus": "关注的信息维度"
    }}
  ],
  "overall_strategy": "整体分解策略说明"
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self._call(prompt, max_tokens=1500)
            parsed = self._parse_json_response(response)

            # 验证返回结果
            if "decomposed_queries" not in parsed:
                raise ValueError("返回结果缺少 decomposed_queries 字段")

            if not isinstance(parsed["decomposed_queries"], list):
                raise ValueError("decomposed_queries 必须是列表")

            if len(parsed["decomposed_queries"]) == 0:
                raise ValueError("分解结果为空，至少需要1个子查询")

            # 限制最多10个子查询
            if len(parsed["decomposed_queries"]) > 10:
                logger.warning(f"子查询数量过多({len(parsed['decomposed_queries'])}个)，截取前10个")
                parsed["decomposed_queries"] = parsed["decomposed_queries"][:10]

            # 构建 DecomposedQuery 对象列表
            decomposed_queries = []
            for q in parsed["decomposed_queries"]:
                if not all(k in q for k in ["query", "reasoning", "focus"]):
                    logger.warning(f"子查询缺少必要字段，跳过: {q}")
                    continue

                decomposed_queries.append(DecomposedQuery(
                    query=q["query"],
                    reasoning=q["reasoning"],
                    focus=q["focus"]
                ))

            # 导入 QueryDecomposition
            from src.infrastructure.llm.claude_client import QueryDecomposition

            return QueryDecomposition(
                decomposed_queries=decomposed_queries,
                overall_strategy=parsed.get("overall_strategy", ""),
                tokens_used=0,  # Claude API 不返回 token 使用量
                model=self.config.model
            )

        except Exception as e:
            logger.error(f"Claude 查询分解失败: {e}")
            # 返回默认分解结果
            return self._get_fallback_decomposition(query)

    def _get_fallback_decomposition(self, query: str) -> "QueryDecomposition":
        """获取降级分解结果"""
        from src.infrastructure.llm.claude_client import QueryDecomposition, DecomposedQuery

        decomposed_queries = [
            DecomposedQuery(
                query=f"{query} 最新消息",
                reasoning="获取最新的事实性报道和新闻",
                focus="最新动态"
            ),
            DecomposedQuery(
                query=f"{query} 深度分析",
                reasoning="获取专业分析和深度解读",
                focus="专业分析"
            )
        ]

        return QueryDecomposition(
            decomposed_queries=decomposed_queries,
            overall_strategy="降级策略：通用分解模式",
            tokens_used=0,
            model=f"{self.config.model}-fallback"
        )

    async def detect_relevant_languages(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        min_languages: int = 2,
        max_languages: int = 5
    ) -> Dict[str, Any]:
        """
        使用 Claude 智能检测查询相关的语言

        根据查询内容分析，确定哪些语言最适合搜索该主题。
        例如：查询"法国经济"应优先选择法语和英语，查询"日本防卫白皮书"应优先选择日语和英语。

        Args:
            query: 用户查询
            context: 搜索上下文
            min_languages: 最少语言数量（默认2，确保至少有英语+原语言）
            max_languages: 最多语言数量（默认5，避免过度分散）

        Returns:
            Dict: {
                "languages": ["zh", "en", "fr", ...],  # 检测到的语言列表
                "reasoning": "选择理由说明",
                "confidence_scores": {"zh": 0.95, "en": 0.90, ...},  # 各语言相关性评分
                "primary_language": "zh",  # 主要语言
                "model": "claude-sonnet-4-20250514"
            }
        """
        # 支持的语言列表及其描述
        supported_languages = {
            "zh": {"name": "中文", "regions": ["中国", "台湾", "香港", "澳门", "新加坡"], "keywords": ["中国", "中文", "华人", "华语"]},
            "en": {"name": "英语", "regions": ["美国", "英国", "加拿大", "澳大利亚", "全球通用"], "keywords": ["英语", "英文", "international", "global"]},
            "ja": {"name": "日语", "regions": ["日本"], "keywords": ["日本", "日语", "japanese", "东京"]},
            "ko": {"name": "韩语", "regions": ["韩国", "朝鲜"], "keywords": ["韩国", "朝鲜", "韩语", "korean", "首尔"]},
            "fr": {"name": "法语", "regions": ["法国", "比利时", "瑞士", "加拿大魁北克"], "keywords": ["法国", "法语", "french", "巴黎", "欧盟"]},
            "de": {"name": "德语", "regions": ["德国", "奥地利", "瑞士"], "keywords": ["德国", "德语", "german", "柏林"]},
            "ru": {"name": "俄语", "regions": ["俄罗斯", "前苏联国家"], "keywords": ["俄罗斯", "俄语", "russian", "莫斯科"]},
            "es": {"name": "西班牙语", "regions": ["西班牙", "拉丁美洲"], "keywords": ["西班牙", "西班牙语", "spanish", "墨西哥", "拉美"]},
            "ar": {"name": "阿拉伯语", "regions": ["中东", "北非"], "keywords": ["阿拉伯", "中东", "arabic", "沙特", "阿联酋"]},
            "pt": {"name": "葡萄牙语", "regions": ["巴西", "葡萄牙"], "keywords": ["巴西", "葡萄牙", "portuguese", "圣保罗"]},
            "it": {"name": "意大利语", "regions": ["意大利"], "keywords": ["意大利", "italian", "罗马"]},
            "vi": {"name": "越南语", "regions": ["越南"], "keywords": ["越南", "vietnamese", "河内"]},
            "th": {"name": "泰语", "regions": ["泰国"], "keywords": ["泰国", "thai", "曼谷"]},
            "id": {"name": "印尼语", "regions": ["印度尼西亚"], "keywords": ["印尼", "indonesian", "雅加达"]}
        }

        # 构建语言描述
        lang_descriptions = []
        for code, info in supported_languages.items():
            regions_str = "、".join(info["regions"][:3])  # 只显示前3个地区
            lang_descriptions.append(f'  - "{code}": {info["name"]} ({regions_str}等)')

        lang_list_str = "\n".join(lang_descriptions)

        prompt = f"""你是一个专业的搜索语言分析专家。请分析以下查询，确定最适合进行搜索的语言。

用户查询: {query}

支持的代码及对应语言/地区:
{lang_list_str}

分析要求:
1. 地域相关性：查询涉及的国家/地区对应的语言优先
2. 内容相关性：查询主题的语言偏好（如经济新闻多用英语/法语）
3. 资源丰富度：选择该语言网络资源丰富的语言
4. 语言覆盖：确保至少包含英语（通用）和查询相关的本地语言

规则:
- 最少选择 {min_languages} 种语言
- 最多选择 {max_languages} 种语言
- 英语( en )通常应该包含（全球通用）
- 如果查询明确涉及某个国家/地区，必须包含该地区的语言

请以 JSON 格式返回（不要使用 markdown 代码块）:
{{
  "languages": ["en", "zh", "fr"],
  "reasoning": "查询涉及法国经济，法语可获得本地视角，英语可获得国际分析",
  "confidence_scores": {{"en": 0.9, "fr": 0.95, "zh": 0.7}},
  "primary_language": "fr"
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self._call(prompt, max_tokens=500)
            result = self._parse_json_response(response)

            # 验证和清理返回结果
            if not isinstance(result, dict):
                raise ValueError("返回结果不是字典")

            # 确保 languages 存在且是列表
            if "languages" not in result or not isinstance(result["languages"], list):
                raise ValueError("缺少 languages 字段或格式错误")

            detected_languages = result["languages"]

            # 验证语言代码是否有效
            valid_languages = [lang for lang in detected_languages if lang in supported_languages]
            if len(valid_languages) < min_languages:
                logger.warning(f"检测到的有效语言不足{min_languages}种，使用默认补充")
                # 确保至少有英语和中文
                if "en" not in valid_languages:
                    valid_languages.append("en")
                if "zh" not in valid_languages:
                    valid_languages.append("zh")

            # 限制最大数量
            valid_languages = valid_languages[:max_languages]

            # 确保有 primary_language
            if "primary_language" not in result or result["primary_language"] not in valid_languages:
                result["primary_language"] = valid_languages[0]

            return {
                "languages": valid_languages,
                "reasoning": result.get("reasoning", "基于查询内容自动检测"),
                "confidence_scores": result.get("confidence_scores", {lang: 0.8 for lang in valid_languages}),
                "primary_language": result["primary_language"],
                "model": self.config.model
            }

        except Exception as e:
            logger.warning(f"语言检测失败: {e}，使用默认语言配置")

            # Fallback: 基于查询的简单关键词匹配
            fallback_languages = ["en"]  # 英语总是默认

            # 简单关键词匹配
            query_lower = query.lower()
            for code, info in supported_languages.items():
                if code == "en":
                    continue
                if any(keyword.lower() in query_lower for keyword in info["keywords"]):
                    fallback_languages.append(code)
                    if len(fallback_languages) >= max_languages:
                        break

            # 确保至少有 min_languages 种语言
            if len(fallback_languages) < min_languages:
                fallback_languages.append("zh")  # 中文作为补充

            return {
                "languages": fallback_languages[:max_languages],
                "reasoning": "基于关键词匹配的降级策略",
                "confidence_scores": {lang: 0.7 for lang in fallback_languages},
                "primary_language": fallback_languages[0],
                "model": f"{self.config.model}-fallback"
            }

    async def analyze_and_generate_multilang_search(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        min_languages: int = 2,
        max_languages: int = 5
    ) -> Dict[str, Any]:
        """
        v3.6.0: 统一的多语言搜索分析与查询生成函数

        将原来的 detect_relevant_languages() 和 generate_multilang_queries() 合并为单一智能函数。
        使用单次 Claude API 调用完成：
        1. 查询类型分析（新闻报道/研究数据/政策文档/舆情分析）
        2. 相关语言检测（基于主题而非翻译）
        3. 多语言搜索词优化生成（非字面翻译，而是针对各语言的最佳搜索策略）

        核心改进：
        - 将多语言搜索从"翻译问题"转变为"情报检索问题"
        - 每种语言的搜索词针对该语言的信息生态系统优化
        - 例如：查询"西方媒体对中国事件的报道"
          - 英语：搜索英文媒体名称 + 事件关键词
          - 中文：搜索"外媒报道" + 事件关键词
          而不是简单翻译

        Args:
            query: 用户原始查询
            context: 搜索上下文（包含 intent, keywords, entities 等）
            min_languages: 最少语言数量（默认2）
            max_languages: 最多语言数量（默认5）

        Returns:
            Dict: {
                "query_type": "news_coverage|research_data|policy_document|opinion_analysis",
                "query_type_reasoning": "查询类型判断理由",
                "languages": ["en", "zh", ...],
                "language_reasoning": "语言选择理由",
                "confidence_scores": {"en": 0.95, "zh": 0.85, ...},
                "primary_language": "en",
                "multilang_queries": {
                    "en": "optimized English search query",
                    "zh": "优化后的中文搜索词"
                },
                "search_strategy": "整体搜索策略说明",
                "model": "claude-sonnet-4-20250514"
            }
        """
        # 支持的语言列表
        supported_languages = {
            "zh": {"name": "中文", "regions": ["中国", "台湾", "香港", "澳门", "新加坡"]},
            "en": {"name": "英语", "regions": ["美国", "英国", "加拿大", "澳大利亚", "全球通用"]},
            "ja": {"name": "日语", "regions": ["日本"]},
            "ko": {"name": "韩语", "regions": ["韩国", "朝鲜"]},
            "fr": {"name": "法语", "regions": ["法国", "比利时", "瑞士", "加拿大魁北克"]},
            "de": {"name": "德语", "regions": ["德国", "奥地利", "瑞士"]},
            "ru": {"name": "俄语", "regions": ["俄罗斯", "前苏联国家"]},
            "es": {"name": "西班牙语", "regions": ["西班牙", "拉丁美洲"]},
            "ar": {"name": "阿拉伯语", "regions": ["中东", "北非"]},
            "pt": {"name": "葡萄牙语", "regions": ["巴西", "葡萄牙"]},
            "it": {"name": "意大利语", "regions": ["意大利"]},
            "vi": {"name": "越南语", "regions": ["越南"]},
            "th": {"name": "泰语", "regions": ["泰国"]},
            "id": {"name": "印尼语", "regions": ["印度尼西亚"]}
        }

        # 构建语言描述
        lang_descriptions = []
        for code, info in supported_languages.items():
            regions_str = "、".join(info["regions"][:3])
            lang_descriptions.append(f'  "{code}": {info["name"]} ({regions_str})')
        lang_list_str = "\n".join(lang_descriptions)

        # 提取上下文信息
        context_info = ""
        if context:
            keywords = context.get("keywords", [])
            entities = context.get("entities", [])
            intent = context.get("intent", "")
            if keywords:
                context_info += f"\n已识别关键词: {', '.join(keywords[:5])}"
            if entities:
                context_info += f"\n已识别实体: {', '.join(entities[:5])}"
            if intent:
                context_info += f"\n用户意图: {intent}"

        prompt = f"""你是一名专业的开源情报(OSINT)分析师和多语言搜索策略专家。

请分析以下查询，并制定最优的多语言搜索策略。
注意：这不是简单的翻译任务，而是针对不同语言信息生态系统的搜索优化任务。

用户查询: {query}
{context_info if context_info else ""}

支持的语言:
{lang_list_str}

请完成以下分析任务：

1. **查询类型识别**
   判断查询属于以下哪种类型：
   - news_coverage: 新闻报道类（寻找媒体报道、新闻事件）
   - research_data: 研究数据类（寻找学术论文、研究报告、统计数据）
   - policy_document: 政策文档类（寻找政府文件、政策声明、官方立场）
   - opinion_analysis: 舆情分析类（寻找公众反应、社交媒体讨论、评论分析）

2. **语言选择**
   基于查询主题选择最相关的 {min_languages}-{max_languages} 种语言。
   考虑因素：
   - 事件发生地的语言
   - 主要信息来源的语言
   - 国际报道的通用语言（英语）
   - 特定领域的语言偏好

3. **多语言搜索词生成**
   为每种选定语言生成优化的搜索词。

   关键原则（非常重要）：
   - 不是简单翻译，而是针对该语言信息生态系统的最佳搜索策略
   - 例如查询"西方媒体对X事件的报道":
     * 英语搜索词应该是: "X event" + 具体媒体名或关键词
     * 中文搜索词应该是: "外媒报道 X事件" 或 "西方媒体 X"
   - 每种语言的搜索词应能最大化在该语言网络中找到相关信息的概率
   - 搜索词应简洁有效，适合搜索引擎使用（10-50个字符为宜）

请以 JSON 格式返回（不要使用 markdown 代码块）:
{{
  "query_type": "news_coverage",
  "query_type_reasoning": "用户查询涉及媒体报道和新闻事件",
  "languages": ["en", "zh", "ja"],
  "language_reasoning": "事件涉及国际关注，需要英语获取西方媒体视角，中文获取中国视角，日语获取日本视角",
  "confidence_scores": {{"en": 0.95, "zh": 0.90, "ja": 0.75}},
  "primary_language": "en",
  "multilang_queries": {{
    "en": "optimized English search query",
    "zh": "优化后的中文搜索词",
    "ja": "最適化された日本語検索語"
  }},
  "search_strategy": "本次搜索策略：先通过英语获取国际主流媒体报道，再通过中文获取国内视角和分析..."
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self._call(prompt, max_tokens=1000)
            result = self._parse_json_response(response)

            # 验证和清理返回结果
            if not isinstance(result, dict):
                raise ValueError("返回结果不是字典")

            # 验证必需字段
            required_fields = ["query_type", "languages", "multilang_queries"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"缺少必需字段: {field}")

            # 验证语言代码有效性
            detected_languages = result.get("languages", [])
            valid_languages = [lang for lang in detected_languages if lang in supported_languages]

            if len(valid_languages) < min_languages:
                logger.warning(f"检测到的有效语言不足{min_languages}种，使用默认补充")
                if "en" not in valid_languages:
                    valid_languages.append("en")
                if "zh" not in valid_languages and len(valid_languages) < min_languages:
                    valid_languages.append("zh")

            valid_languages = valid_languages[:max_languages]

            # 确保 multilang_queries 包含所有有效语言
            multilang_queries = result.get("multilang_queries", {})
            for lang in valid_languages:
                if lang not in multilang_queries:
                    # 对于缺失的语言，使用原始查询
                    multilang_queries[lang] = query
                    logger.warning(f"语言 {lang} 缺少搜索词，使用原始查询补充")

            # 移除无效语言的查询
            multilang_queries = {k: v for k, v in multilang_queries.items() if k in valid_languages}

            # 验证查询类型
            valid_query_types = ["news_coverage", "research_data", "policy_document", "opinion_analysis"]
            query_type = result.get("query_type", "news_coverage")
            if query_type not in valid_query_types:
                query_type = "news_coverage"

            # 确保 primary_language 有效
            primary_language = result.get("primary_language", valid_languages[0])
            if primary_language not in valid_languages:
                primary_language = valid_languages[0]

            logger.info(
                f"多语言搜索分析完成: query_type={query_type}, "
                f"languages={valid_languages}, primary={primary_language}"
            )

            return {
                "query_type": query_type,
                "query_type_reasoning": result.get("query_type_reasoning", "基于查询内容自动判断"),
                "languages": valid_languages,
                "language_reasoning": result.get("language_reasoning", "基于查询内容自动检测"),
                "confidence_scores": result.get("confidence_scores", {lang: 0.8 for lang in valid_languages}),
                "primary_language": primary_language,
                "multilang_queries": multilang_queries,
                "search_strategy": result.get("search_strategy", "使用多语言并行搜索策略"),
                "model": self.config.model
            }

        except Exception as e:
            logger.warning(f"统一多语言分析失败: {e}，使用降级策略")

            # Fallback: 基于简单规则的降级策略
            fallback_languages = ["en", "zh"]  # 默认英语和中文

            # 简单关键词匹配扩展语言
            query_lower = query.lower()
            for code, info in supported_languages.items():
                if code in fallback_languages:
                    continue
                # 检查地区名是否在查询中
                if any(region.lower() in query_lower for region in info["regions"]):
                    fallback_languages.append(code)
                    if len(fallback_languages) >= max_languages:
                        break

            fallback_languages = fallback_languages[:max_languages]

            # 生成简单的搜索词（直接使用原始查询）
            fallback_queries = {lang: query for lang in fallback_languages}

            return {
                "query_type": "news_coverage",
                "query_type_reasoning": "降级策略：默认为新闻报道类型",
                "languages": fallback_languages,
                "language_reasoning": "降级策略：基于关键词匹配",
                "confidence_scores": {lang: 0.6 for lang in fallback_languages},
                "primary_language": fallback_languages[0],
                "multilang_queries": fallback_queries,
                "search_strategy": "降级策略：使用原始查询在多语言中搜索",
                "model": f"{self.config.model}-fallback"
            }

    async def decompose_query_with_multilang(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        languages: Optional[List[str]] = None,
        auto_detect_languages: bool = False,
        min_languages: int = 2,
        max_languages: int = 5
    ) -> Dict[str, Any]:
        """
        使用 Claude 分解查询并生成多语言配置

        这是方案 A 的核心方法：一站式完成查询分解和多语言配置生成

        Args:
            query: 用户原始查询
            context: 搜索上下文
            languages: 目标语言列表，默认 ["zh", "en", "ja", "ko"]
                    当 auto_detect_languages=True 时，此参数作为备选
            auto_detect_languages: 是否启用智能语言检测（默认False）
                                  启用后 Claude 会根据查询内容智能选择相关语言
            min_languages: 自动检测时的最少语言数量（默认2）
            max_languages: 自动检测时的最多语言数量（默认5）

        Returns:
            Dict: 包含分解结果和多语言配置
            {
                "decomposed_queries": [...],  # 带 multilang_configs 的子查询
                "overall_strategy": "...",
                "languages": ["zh", "en", "ja", "ko"],
                "language_detection": {  # 当 auto_detect_languages=True 时包含
                    "reasoning": "选择理由说明",
                    "confidence_scores": {...},
                    "primary_language": "zh"
                },
                "model": "claude-sonnet-4-20250514"
            }
        """
        # Step 0: 确定使用的语言
        language_detection = None

        # 优先级：明确指定的语言 > 自动检测 > 默认语言
        if languages is not None:
            # 明确指定了语言，直接使用（跳过自动检测）
            pass
        elif auto_detect_languages:
            # 启用自动检测
            detection_result = await self.detect_relevant_languages(
                query=query,
                context=context,
                min_languages=min_languages,
                max_languages=max_languages
            )
            languages = detection_result["languages"]
            language_detection = {
                "reasoning": detection_result["reasoning"],
                "confidence_scores": detection_result["confidence_scores"],
                "primary_language": detection_result["primary_language"]
            }
            logger.info(f"自动检测语言: {languages}, 理由: {detection_result['reasoning']}")
        else:
            # 使用默认语言
            languages = ["zh", "en", "ja", "ko"]

        # Step 1: 调用 Claude 分解查询
        decomposition = await self.decompose_query(query, context)

        # Step 2: 为每个子查询生成多语言配置
        enriched_queries = []
        for sub_query in decomposition.decomposed_queries:
            # 调用 generate_multilang_queries
            multilang_queries = await self.generate_multilang_queries(
                query=sub_query.query,
                languages=languages
            )

            enriched_queries.append({
                "query": sub_query.query,
                "reasoning": sub_query.reasoning,
                "focus": sub_query.focus,
                "multilang_configs": multilang_queries,
                "languages": languages
            })

        result = {
            "decomposed_queries": enriched_queries,
            "overall_strategy": decomposition.overall_strategy,
            "languages": languages,
            "model": decomposition.model
        }

        # 如果启用了自动检测，添加检测信息
        if language_detection:
            result["language_detection"] = language_detection

        return result


# ==================== 实体类定义 ====================

@dataclass
class DecomposedQuery:
    """分解的子查询"""
    query: str  # 子查询文本
    reasoning: str  # 为什么需要这个子查询的解释
    focus: str  # 关注的信息维度


@dataclass
class QueryDecomposition:
    """
    查询分解结果实体

    由 LLM Service 生成，包含分解的子查询列表和整体策略说明
    """
    # 分解的子查询列表
    decomposed_queries: List[DecomposedQuery] = field(default_factory=list)

    # 整体分解策略说明
    overall_strategy: str = ""

    # LLM元数据
    tokens_used: int = 0  # 消耗的token数
    model: str = "gpt-4"  # 使用的模型

    def to_dict(self):
        """转换为字典"""
        return {
            "decomposed_queries": [
                {
                    "query": q.query,
                    "reasoning": q.reasoning,
                    "focus": q.focus
                }
                for q in self.decomposed_queries
            ],
            "overall_strategy": self.overall_strategy,
            "tokens_used": self.tokens_used,
            "model": self.model
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueryDecomposition":
        """从字典创建实例"""
        return cls(
            decomposed_queries=[
                DecomposedQuery(
                    query=q["query"],
                    reasoning=q["reasoning"],
                    focus=q["focus"]
                )
                for q in data.get("decomposed_queries", [])
            ],
            overall_strategy=data.get("overall_strategy", ""),
            tokens_used=data.get("tokens_used", 0),
            model=data.get("model", "gpt-4")
        )


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
