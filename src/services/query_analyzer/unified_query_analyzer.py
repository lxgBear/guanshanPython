"""统一查询分析服务

复用 LangGraph QueryAnalyzerNode 的优秀 Prompt 设计，
为 SmartSearchService 和 NLSearchService 提供统一的查询分析能力。

特性:
- 识别当事方（国家、组织、人物）
- 分析事件类型（政治、军事、经济、外交等）
- 生成多角度搜索查询（事实性、分析性、地区视角）
- 检测时间敏感度
- 生成多语言查询变体 (zh/en/ja/ko)

版本: v1.1.0 (v3.7.3 多语言增强)
日期: 2025-01-12

v1.1.0 更新:
- 支持 4 种语言查询生成 (zh/en/ja/ko)
- 智能降级策略：亚洲语言缺失时使用英文查询
- 针对"西方媒体报道"类查询优化英文查询生成
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal

import httpx

from src.core.domain.entities.query_decomposition import (
    QueryDecomposition,
    DecomposedQuery
)

logger = logging.getLogger(__name__)


# ============================================================================
# 配置
# ============================================================================

@dataclass
class UnifiedAnalyzerConfig:
    """统一分析器配置"""
    # Claude API 配置 - 从环境变量读取，与项目其他 LLM 配置保持一致
    base_url: str = field(default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    api_key: str = field(default_factory=lambda: os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN", ""))
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout: int = 60

    # 分析配置
    enable_parties: bool = True  # 是否识别当事方
    enable_event_type: bool = True  # 是否分析事件类型
    enable_multilang: bool = True  # 是否生成多语言查询
    default_languages: List[str] = field(default_factory=lambda: ["zh", "en"])

    # 查询分解配置
    min_queries: int = 2
    max_queries: int = 5
    enable_factual_queries: bool = True  # 事实性查询
    enable_analytical_queries: bool = True  # 分析性查询
    enable_regional_queries: bool = True  # 地区视角查询


# ============================================================================
# 增强的查询分解结果（扩展原有实体）
# ============================================================================

@dataclass
class Party:
    """当事方信息"""
    name: str
    type: Literal["country", "organization", "person"]
    role: str
    code: str = ""  # ISO 国家代码或组织简称


@dataclass
class EnhancedQueryDecomposition(QueryDecomposition):
    """增强的查询分解结果

    扩展自 QueryDecomposition，添加更多分析维度
    """
    # 新增字段
    summary: str = ""  # 事件简要描述
    parties: List[Party] = field(default_factory=list)  # 当事方列表
    keywords: List[str] = field(default_factory=list)  # 关键词
    keywords_en: List[str] = field(default_factory=list)  # 英文关键词
    time_sensitivity: Literal["high", "medium", "low"] = "medium"  # 时间敏感度
    suggested_time_range: str = "qdr:m"  # 建议时间范围
    event_type: Literal["政治", "军事", "经济", "外交", "科技", "社会", "其他"] = "其他"

    # 多角度搜索查询
    search_queries: Dict[str, List[str]] = field(default_factory=dict)  # factual/analytical/regional

    # 查询变体（多语言）
    query_variations: Dict[str, List[str]] = field(default_factory=dict)  # zh/en/ja/ko

    # 搜索策略
    search_strategy: Dict[str, Any] = field(default_factory=dict)

    def to_compatible_result(self) -> QueryDecomposition:
        """转换为兼容原有接口的 QueryDecomposition"""
        # 合并所有类型的查询到一个列表
        all_queries = []

        # 从 search_queries 获取
        if self.search_queries:
            for query_type, queries in self.search_queries.items():
                for q in queries:
                    # 分离查询文本和说明（格式: "查询文本: 说明"）
                    if ": " in q:
                        query_text, explanation = q.split(": ", 1)
                    else:
                        query_text, explanation = q, f"{query_type}查询"

                    all_queries.append(DecomposedQuery(
                        query=query_text.strip(),
                        reasoning=explanation.strip(),
                        focus=query_type
                    ))

        # 如果没有 search_queries，使用 query_variations
        if not all_queries and self.query_variations:
            for lang, queries in self.query_variations.items():
                for q in queries[:2]:  # 每种语言最多取2个
                    all_queries.append(DecomposedQuery(
                        query=q,
                        reasoning=f"{lang}语言搜索",
                        focus="multilang"
                    ))

        # 如果仍然为空，使用原始 decomposed_queries
        if not all_queries:
            all_queries = self.decomposed_queries

        # 限制数量
        all_queries = all_queries[:5]

        return QueryDecomposition(
            decomposed_queries=all_queries,
            overall_strategy=self.overall_strategy or self.summary,
            tokens_used=self.tokens_used,
            model=self.model
        )


# ============================================================================
# 统一查询分析器
# ============================================================================

class UnifiedQueryAnalyzer:
    """统一查询分析器

    复用 LangGraph QueryAnalyzerNode 的优秀 Prompt 设计，
    为 SmartSearchService 和 NLSearchService 提供统一的查询分析能力。
    """

    # Claude 查询分析提示词（复用 LangGraph QueryAnalyzerNode）
    # v3.7.3: 支持 4 种语言 (zh/en/ja/ko) 用于国际新闻覆盖
    QUERY_ANALYSIS_PROMPT = """你是一个专业的新闻事件分析专家。请分析以下搜索查询，提取关键信息并生成多角度搜索策略。

查询: {query}

请以 JSON 格式返回分析结果:

{{
    "summary": "事件简要描述（一句话）",
    "parties": [
        {{"name": "当事方名称", "type": "country|organization|person", "role": "���事方角色", "code": "ISO国家代码或组织简称"}}
    ],
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "keywords_en": ["keyword1", "keyword2", "keyword3"],
    "time_sensitivity": "high|medium|low",
    "suggested_time_range": "qdr:d|qdr:w|qdr:m|qdr:y",
    "event_type": "政治|军事|经济|外交|科技|社会|其他",

    "search_queries": {{
        "factual": ["事实性查询1: 精确搜索事件本身", "事实性查询2"],
        "analytical": ["分析性查询1: 搜索评论和深度分析", "分析性查询2"],
        "regional": ["地区视角查询1: 不同地区/国家的报道视角", "地区视角查询2"]
    }},

    "query_variations": {{
        "zh": ["中文搜索变体1", "中文搜索变体2", "中文搜索变体3"],
        "en": ["English search query 1", "English search query 2", "English search query 3"],
        "ja": ["日本語検索クエリ1", "日本語検索クエリ2", "日本語検索クエリ3"],
        "ko": ["한국어 검색 쿼리1", "한국어 검색 쿼리2", "한국어 검색 쿼리3"]
    }},

    "search_strategy": {{
        "primary_focus": "主要搜索焦点",
        "secondary_topics": ["次要话题1", "次要话题2"],
        "recommended_sources": ["官方来源", "主流媒体", "专业智库"],
        "geographic_perspectives": ["相关地区1", "相关地区2"]
    }}
}}

注意事项:
1. 最多识别 5 个主要当事方
2. 关键词应包含中英文版本
3. 时间敏感度：突发事件为 high，近期事件为 medium，历史事件为 low
4. suggested_time_range 对应搜索的时间范围参数
5. search_queries 应覆盖不同角度：事实性（what happened）、分析性（why/how）、地区视角（regional perspectives）
6. query_variations 应为每种语言生成 2-3 个优化的搜索查询：
   - zh: 使用中文关键词，适合中文媒体搜索
   - en: 使用英文关键词，适合国际/西方媒体搜索
   - ja: 使用日文关键词，适合日本媒体搜索（音译专有名词）
   - ko: 使用韩文关键词，适合韩国媒体搜索（音译专有名词）
7. 对于外国事件，英文查询应包含事件、地点、时间的完整描述
8. 搜索变体应使用不同的关键词组合和表述方式，以提高召回率

请只返回 JSON，不要添加任何其他文字。"""

    def __init__(self, config: Optional[UnifiedAnalyzerConfig] = None):
        """初始化分析器

        Args:
            config: 分析器配置
        """
        self.config = config or UnifiedAnalyzerConfig()
        self.base_url = self.config.base_url.rstrip('/')

        if not self.config.api_key:
            logger.warning("Claude API Key 未配置")

        logger.info(
            f"UnifiedQueryAnalyzer 初始化: model={self.config.model}, "
            f"base_url={self.base_url}"
        )

    async def _call_claude(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """调用 Claude API

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数

        Returns:
            响应文本
        """
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

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """解析 JSON 响应

        Args:
            text: 响应文本

        Returns:
            解析后的字典
        """
        text = text.strip()

        # 清理 markdown 代码块
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            raise

    def _create_fallback_result(
        self,
        query: str,
        error_message: str = ""
    ) -> EnhancedQueryDecomposition:
        """创建降级结果

        Args:
            query: 原始查询
            error_message: 错误信息

        Returns:
            降级分解结果
        """
        logger.warning(f"使用降级分解策略: {error_message}")

        # 生成简单的分解结果
        decomposed_queries = [
            DecomposedQuery(
                query=f"{query} 最新",
                reasoning="获取最新报道",
                focus="最新动态"
            ),
            DecomposedQuery(
                query=f"{query} 分析",
                reasoning="获取深度分析",
                focus="专业分析"
            )
        ]

        # v4.20.1: 修复中文文本分词 - 使用简单的中文关键词提取
        # 对于中文查询，尝试提取常见的实体词
        keywords = self._extract_chinese_keywords(query)

        return EnhancedQueryDecomposition(
            decomposed_queries=decomposed_queries,
            overall_strategy="降级策略：通用分解模式",
            summary=f"关于'{query}'的搜索",
            keywords=keywords,
            keywords_en=[],
            time_sensitivity="medium",
            suggested_time_range="qdr:m",
            event_type="其他",
            search_queries={
                "factual": [f"{query} 最新消息"],
                "analytical": [f"{query} 深度分析"],
                "regional": []
            },
            query_variations={
                "zh": [f"{query} 最新", f"{query} 新闻"],
                "en": [f"{query} latest", f"{query} news"]
            },
            tokens_used=0,
            model=f"{self.config.model}-fallback"
        )

    def _extract_chinese_keywords(self, query: str) -> List[str]:
        """从中文查询中提取关键词

        使用简单的规则提取关键词，不依赖外部分词库。

        Args:
            query: 查询文本

        Returns:
            关键词列表
        """
        import re

        # 如果有空格，先按空格分割
        if ' ' in query:
            words = [w.strip() for w in query.split() if w.strip()]
            if len(words) > 1:
                return words[:5]

        # 提取常见的中文实体模式
        keywords = []

        # 1. 提取地名模式 (省市县区、大桥、广场等)
        location_pattern = r'[\u4e00-\u9fa5]{2,4}(?:省|市|县|区|镇|乡|村|大桥|广场|路|街|机场|港口|车站)'
        locations = re.findall(location_pattern, query)
        keywords.extend(locations)

        # 2. 提取事件关键词 (垮塌、爆炸、地震、事故等)
        event_patterns = [
            r'(?:垮塌|倒塌|坍塌|崩塌)',
            r'(?:爆炸|火灾|事故|灾害|灾难)',
            r'(?:地震|洪水|台风|泥石流)',
            r'(?:冲突|战争|袭击|恐袭)',
            r'(?:报道|反应|评论|分析)',
        ]
        for pattern in event_patterns:
            matches = re.findall(pattern, query)
            keywords.extend(matches)

        # 3. 提取组织/媒体名称
        org_pattern = r'[\u4e00-\u9fa5]{2,6}(?:媒体|新闻|报|台|社|网)'
        orgs = re.findall(org_pattern, query)
        keywords.extend(orgs)

        # 4. 提取形容词+名词组合
        adj_noun_pattern = r'(?:西方|主流|国际|国内|官方|民间)[\u4e00-\u9fa5]{2,4}'
        adj_nouns = re.findall(adj_noun_pattern, query)
        keywords.extend(adj_nouns)

        # 去重并限制数量
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen and len(kw) >= 2:
                seen.add(kw)
                unique_keywords.append(kw)

        # 如果没有提取到关键词，返回原始查询（截取前30字符）
        if not unique_keywords:
            return [query[:30]] if len(query) > 30 else [query]

        return unique_keywords[:5]

    async def analyze(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EnhancedQueryDecomposition:
        """分析查询

        Args:
            query: 用户查询
            context: 搜索上下文（可选）

        Returns:
            增强的查询分解结果
        """
        if context is None:
            context = {}

        start_time = __import__('time').time()

        try:
            logger.info(f"开始分析查询: {query[:50]}...")

            # 调用 Claude 进行分析
            prompt = self.QUERY_ANALYSIS_PROMPT.format(query=query)
            response_text = await self._call_claude(prompt)
            analysis = self._parse_json_response(response_text)

            # 记录耗时
            elapsed = int((__import__('time').time() - start_time) * 1000)
            logger.info(f"查询分析完成: 耗时={elapsed}ms")

            # 构建 DecomposedQuery 列表（从 search_queries 提取）
            decomposed_queries = self._extract_decomposed_queries(analysis)

            # 构建增强结果
            result = EnhancedQueryDecomposition(
                decomposed_queries=decomposed_queries,
                overall_strategy=analysis.get("search_strategy", {}).get("primary_focus", ""),
                summary=analysis.get("summary", ""),
                keywords=analysis.get("keywords", []),
                keywords_en=analysis.get("keywords_en", []),
                time_sensitivity=analysis.get("time_sensitivity", "medium"),
                suggested_time_range=analysis.get("suggested_time_range", "qdr:m"),
                event_type=analysis.get("event_type", "其他"),
                search_queries=analysis.get("search_queries", {}),
                query_variations=analysis.get("query_variations", {}),
                search_strategy=analysis.get("search_strategy", {}),
                tokens_used=0,
                model=self.config.model
            )

            # 提取当事方
            if self.config.enable_parties:
                for p in analysis.get("parties", []):
                    if p.get("name"):
                        result.parties.append(Party(
                            name=p["name"],
                            type=p.get("type", "organization"),
                            role=p.get("role", ""),
                            code=p.get("code", "")
                        ))

            logger.info(
                f"分析结果: {len(decomposed_queries)}个子查询, "
                f"{len(result.parties)}个当事方, "
                f"类型={result.event_type}"
            )

            return result

        except Exception as e:
            logger.error(f"查询分析失败: {e}", exc_info=True)
            return self._create_fallback_result(query, str(e))

    def _extract_decomposed_queries(self, analysis: Dict[str, Any]) -> List[DecomposedQuery]:
        """从分析结果中提取 DecomposedQuery 列表

        Args:
            analysis: Claude 分析结果

        Returns:
            DecomposedQuery 列表
        """
        queries = []

        search_queries = analysis.get("search_queries", {})

        # 事实性查询
        if self.config.enable_factual_queries and "factual" in search_queries:
            for q in search_queries["factual"][:2]:  # 最多2个
                if ": " in q:
                    query_text, explanation = q.split(": ", 1)
                else:
                    query_text, explanation = q, "事实性查询"
                queries.append(DecomposedQuery(
                    query=query_text.strip(),
                    reasoning=explanation.strip(),
                    focus="factual"
                ))

        # 分析性查询
        if self.config.enable_analytical_queries and "analytical" in search_queries:
            for q in search_queries["analytical"][:2]:
                if ": " in q:
                    query_text, explanation = q.split(": ", 1)
                else:
                    query_text, explanation = q, "分析性查询"
                queries.append(DecomposedQuery(
                    query=query_text.strip(),
                    reasoning=explanation.strip(),
                    focus="analytical"
                ))

        # 地区视角查询
        if self.config.enable_regional_queries and "regional" in search_queries:
            for q in search_queries["regional"][:2]:
                if ": " in q:
                    query_text, explanation = q.split(": ", 1)
                else:
                    query_text, explanation = q, "地区视角查询"
                queries.append(DecomposedQuery(
                    query=query_text.strip(),
                    reasoning=explanation.strip(),
                    focus="regional"
                ))

        # 如果没有提取到任何查询，使用 query_variations
        if not queries and "query_variations" in analysis:
            variations = analysis["query_variations"]
            for lang in ["zh", "en"]:
                if lang in variations and variations[lang]:
                    for q in variations[lang][:1]:
                        queries.append(DecomposedQuery(
                            query=q,
                            reasoning=f"{lang}语言搜索",
                            focus="multilang"
                        ))

        # 确保至少有一个查询
        if not queries:
            queries.append(DecomposedQuery(
                query=analysis.get("summary", "搜索"),
                reasoning="通用搜索",
                focus="general"
            ))

        return queries[:5]  # 最多5个

    async def decompose_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryDecomposition:
        """兼容原有接口的查询分解方法

        Args:
            query: 用户查询
            context: 搜索上下文

        Returns:
            QueryDecomposition（兼容原有格式）
        """
        enhanced_result = await self.analyze(query, context)
        return enhanced_result.to_compatible_result()

    async def decompose_query_with_multilang(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        languages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """带多语言支持的查询分解

        用于 SmartSearchService 的多语言搜索。

        Args:
            query: 用户查询
            context: 搜索上下文
            languages: 目标语言列表

        Returns:
            Dict: 包含分解结果和多语言配置
        """
        if languages is None:
            languages = self.config.default_languages

        enhanced_result = await self.analyze(query, context)

        # v3.7.3: 智能降级策略 - 亚洲语言使用英文查询，而不是中文查询
        multilang_queries = {}
        asian_langs = {"ja", "ko", "zh"}  # 亚洲语言集合
        query_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in query)  # 检测是否中文

        for lang in languages:
            if lang in enhanced_result.query_variations and enhanced_result.query_variations[lang]:
                # 使用生成的语言查询
                multilang_queries[lang] = enhanced_result.query_variations[lang]
            elif lang in asian_langs and "en" in enhanced_result.query_variations:
                # v3.7.3: 亚洲语言缺失时，使用英文查询（比中文更适合国际搜索）
                multilang_queries[lang] = enhanced_result.query_variations["en"]
                logger.info(f"多语言降级: {lang} 使用英文查询（原查询为中文）")
            else:
                # 最后降级：使用原查询
                multilang_queries[lang] = [query]

        # 构建带 multilang_configs 的子查询列表
        decomposed_with_multilang = []
        for dq in enhanced_result.decomposed_queries:
            decomposed_with_multilang.append({
                "query": dq.query,
                "reasoning": dq.reasoning,
                "focus": dq.focus,
                "multilang_configs": multilang_queries,
                "languages": languages
            })

        return {
            "decomposed_queries": decomposed_with_multilang,
            "overall_strategy": enhanced_result.overall_strategy,
            "languages": languages,
            "model": enhanced_result.model,
            # 多语言查询配置
            "multilang_queries": multilang_queries,
            # 完整增强信息（用于保存到JSON）
            "summary": enhanced_result.summary,
            "event_type": enhanced_result.event_type,
            "time_sensitivity": enhanced_result.time_sensitivity,
            "suggested_time_range": enhanced_result.suggested_time_range,
            "parties": [
                {"name": p.name, "type": p.type, "role": p.role, "code": p.code}
                for p in enhanced_result.parties
            ],
            "keywords": enhanced_result.keywords,
            "keywords_en": enhanced_result.keywords_en,
            "search_queries": enhanced_result.search_queries,
            "query_variations": enhanced_result.query_variations,
            "search_strategy": enhanced_result.search_strategy,
        }


# ============================================================================
# 单例实例
# ============================================================================

_analyzer_instance: Optional[UnifiedQueryAnalyzer] = None


def get_unified_analyzer() -> UnifiedQueryAnalyzer:
    """获取统一分析器单例

    Returns:
        UnifiedQueryAnalyzer 实例
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = UnifiedQueryAnalyzer()
    return _analyzer_instance


def reset_unified_analyzer():
    """重置统一分析器（主要用于测试）"""
    global _analyzer_instance
    _analyzer_instance = None
