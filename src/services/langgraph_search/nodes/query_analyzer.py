"""查询分析节点

使用 Claude 分析搜索查询，提取当事方、关键词和时间范围。
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Set, Tuple

from anthropic import Anthropic

from ..state import SearchState
from ..config import LangGraphSearchConfig
from ..languages import (
    get_media_domains,
    get_languages_by_region,
    get_language_name,
    get_asian_languages,
    get_european_languages,
    get_default_languages_for_query,
    COUNTRY_TO_LANGUAGES,
)

logger = logging.getLogger(__name__)


# 搜索意图关键词映射 (v3.7.2: 扩展)
MEDIA_INTENT_KEYWORDS = {
    "western": {
        "zh": ["西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体", "海外媒体",
               "西方国家", "美英", "欧美", "西方世界", "西方国家报道", "欧美新闻"],
        "en": ["western media", "western news", "international media", "overseas media",
               "western countries", "us european", "western world"]
    },
    "asian": {
        "zh": ["亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体", "亚洲国家", "邻国媒体",
               "亚洲视角", "东亚报道"],
        "en": ["asian media", "asia news", "east asian media", "asian perspective"]
    },
    "domestic": {
        "zh": ["国内媒体", "中国媒体", "中文媒体", "本地媒体"],
        "en": ["domestic media", "chinese media", "local media"]
    },
    "european": {
        "zh": ["欧洲媒体", "欧盟媒体", "欧洲新闻", "欧洲报道"],
        "en": ["european media", "eu media", "europe news"]
    },
    "middle_east": {
        "zh": ["中东媒体", "阿拉伯媒体", "中东新闻"],
        "en": ["middle east media", "arab media", "middle east news"]
    },
    "latin_american": {
        "zh": ["拉美媒体", "拉丁美洲媒体", "西班牙语媒体", "葡萄牙语媒体"],
        "en": ["latin american media", "hispanic media"]
    }
}


# 国家/地区关键词映射 (v3.7.2: 扩展到30+国家)
COUNTRY_KEYWORDS_MAP = {
    # 东亚
    "美国": ["美国", "usa", "us", "america", "united states"],
    "英国": ["英国", "uk", "united kingdom", "britain"],
    "日本": ["日本", "japan"],
    "韩国": ["韩国", "south korea"],
    "中国": ["中国", "china"],
    "台湾": ["台湾", "taiwan"],
    "香港": ["香港", "hong kong"],
    # 欧洲
    "法国": ["法国", "france"],
    "德国": ["德国", "germany"],
    "意大利": ["意大利", "italy"],
    "西班牙": ["西班牙", "spain"],
    "葡萄牙": ["葡萄牙", "portugal"],
    "荷兰": ["荷兰", "netherlands", "holland"],
    "俄罗斯": ["俄罗斯", "russia"],
    "乌克兰": ["乌克兰", "ukraine"],
    # 中东
    "沙特": ["沙特", "saudi arabia"],
    "阿联酋": ["阿联酋", "uae", "united arab emirates"],
    "土耳其": ["土耳其", "turkey"],
    "以色列": ["以色列", "israel"],
    # 南亚
    "印度": ["印度", "india"],
    "巴基斯坦": ["巴基斯坦", "pakistan"],
    # 东南亚
    "越南": ["越南", "vietnam"],
    "泰国": ["泰国", "thailand"],
    "印尼": ["印尼", "indonesia"],
    "马来西亚": ["马来西亚", "malaysia"],
    "新加坡": ["新加坡", "singapore"],
    # 拉美
    "巴西": ["巴西", "brazil"],
    "阿根廷": ["阿根廷", "argentina"],
    "墨西哥": ["墨西哥", "mexico"],
}


def detect_search_intent(query: str) -> Dict[str, Any]:
    """检测搜索意图 (v3.7.2: 扩展支持20+种语言)

    Args:
        query: 搜索查询

    Returns:
        意图检测结果
    """
    query_lower = query.lower()
    intent = {
        "target_languages": [],
        "target_regions": [],
        "media_types": [],
        "search_domains": []
    }

    # 1. 检测媒体类型意图
    # 西方媒体
    western_keywords = MEDIA_INTENT_KEYWORDS["western"]["zh"] + MEDIA_INTENT_KEYWORDS["western"]["en"]
    if any(kw in query_lower for kw in western_keywords):
        intent["media_types"].append("western")
        intent["target_languages"].extend(get_european_languages())  # 欧洲语言
        # 添加英语媒体域名
        intent["search_domains"].extend(get_media_domains("en"))

    # 亚洲媒体
    asian_keywords = MEDIA_INTENT_KEYWORDS["asian"]["zh"] + MEDIA_INTENT_KEYWORDS["asian"]["en"]
    if any(kw in query_lower for kw in asian_keywords):
        intent["media_types"].append("asian")
        intent["target_languages"].extend(["ja", "ko", "vi", "th", "id", "ms"])

    # 欧洲媒体 (新增)
    european_keywords = MEDIA_INTENT_KEYWORDS["european"]["zh"] + MEDIA_INTENT_KEYWORDS["european"]["en"]
    if any(kw in query_lower for kw in european_keywords):
        intent["media_types"].append("european")
        intent["target_languages"].extend(["fr", "de", "it", "es", "pt", "nl"])

    # 中东媒体 (新增)
    middle_east_keywords = MEDIA_INTENT_KEYWORDS["middle_east"]["zh"] + MEDIA_INTENT_KEYWORDS["middle_east"]["en"]
    if any(kw in query_lower for kw in middle_east_keywords):
        intent["media_types"].append("middle_east")
        intent["target_languages"].extend(["ar", "tr"])

    # 拉美媒体 (新增)
    latin_american_keywords = MEDIA_INTENT_KEYWORDS["latin_american"]["zh"] + MEDIA_INTENT_KEYWORDS["latin_american"]["en"]
    if any(kw in query_lower for kw in latin_american_keywords):
        intent["media_types"].append("latin_american")
        intent["target_languages"].extend(["es", "pt"])

    # 国内/中文媒体
    domestic_keywords = MEDIA_INTENT_KEYWORDS["domestic"]["zh"] + MEDIA_INTENT_KEYWORDS["domestic"]["en"]
    if any(kw in query_lower for kw in domestic_keywords):
        intent["media_types"].append("domestic")
        intent["target_languages"].append("zh")
        intent["search_domains"].extend(get_media_domains("zh"))

    # 2. 检测特定国家/地区 (使用扩展的 COUNTRY_KEYWORDS_MAP)
    for country, keywords in COUNTRY_KEYWORDS_MAP.items():
        if any(kw in query_lower for kw in keywords):
            intent["target_regions"].append(country)
            # 从 languages 模块获取该国家对应的语言
            country_langs = get_languages_by_region(country)
            if country_langs:
                intent["target_languages"].extend(country_langs)
                # 为每种语言添加媒体域名
                for lang in country_langs:
                    intent["search_domains"].extend(get_media_domains(lang))

    # 3. 去重
    intent["target_languages"] = list(set(intent["target_languages"]))
    intent["search_domains"] = list(set(intent["search_domains"]))
    intent["target_regions"] = list(set(intent["target_regions"]))

    # 4. 如果没有检测到特定意图，使用智能语言检测 (v4.3.0)
    if not intent["target_languages"]:
        intent["target_languages"] = get_default_languages_for_query(query)

    logger.info(f"Intent detected: languages={intent['target_languages']}, "
                f"media_types={intent['media_types']}, regions={intent['target_regions']}")

    return intent


# Claude 查询分析提示词 (v4.5.0: 4层组合法 + 事件核心词提取)
QUERY_ANALYSIS_PROMPT = """你是一个专业的新闻搜索专家。请分析以下搜索查询，生成高质量的搜索关键词组合。

查询: {query}

**核心任务**: 生成能够在新闻搜索引擎中找到相关报道的关键词组合。

**关键规则**:

1. **区分"用户意图"和"搜索关键词"**
   - 用户意图词 (如 "西方媒体"、"当地媒体") → 决定搜索哪些媒体，但**绝不能**作为搜索词
   - 搜索关键词 (如 "bridge collapse"、"earthquake") → 用于实际搜索的词

   ❌ 错误: keywords_en = ["Sichuan Aba", "Western Media", "Nov 2025"]
   ✅ 正确: keywords_en = ["Sichuan bridge collapse", "Hongqi Bridge", "China"]

2. **4层组合法** - 每层代表不同搜索视角，提高召回率

   **组合1 (general_news)**: 省份 + 事件类型 + 完整时间
   - 目标: Reuters, BBC 等通用新闻
   - 示例: "Sichuan bridge collapse November 2025"

   **组合2 (precise_location)**: 国家 + 地区 + 事件类型 + 实体名
   - 目标: 官方声明、专业工程报道
   - 示例: "China Aba bridge collapse Hongqi"

   **组合3 (entity_focused)**: 完整实体名 + 省份 + 年份
   - 目标: Wikipedia, 技术文档
   - 示例: "Hongqi Bridge Sichuan 2025"

   **组合4 (geopolitical)**: 民族地区名 + 事件类型 + 年份
   - 目标: 人权组织、地缘政治分析
   - 示例: "Aba Tibetan bridge collapse 2025"

3. **关键词要求**
   - 每个组合 3-5 个英文词（不能太长）
   - 必须包含: 事件类型词 (collapse/explosion/conflict/earthquake/summit 等)
   - 必须包含: 时间信息 (年份或月份)
   - 必须包含: 地点信息 (省份或国家)
   - **禁止包含**: 用户意图词 (Western Media, 中文媒体, international media 等)

4. **事件类型识别** - 根据事件类型添加相关核心词
   - 桥梁/建筑垮塌 → collapse, collapsed, bridge collapse
   - 地震 → earthquake, magnitude, tremor
   - 政治事件 → summit, agreement, sanctions, talks
   - 军事冲突 → attack, strike, conflict, clash
   - 事故 → accident, crash, incident

请以 JSON 格式返回:

{{
    "summary": "事件简要描述（一句话）",
    "event_type": "事件类型（如: bridge collapse, earthquake, political summit）",
    "event_name_en": "事件的标准英文名称（如: Hongqi Bridge collapse）",
    "event_location": "事件发生地点",
    "event_date": "事件日期（YYYY-MM-DD 或 YYYY-MM）",
    "user_intent": "用户想搜索的媒体类型（如: 西方主流媒体、当地媒体）",

    "keyword_combinations": [
        {{
            "layer": "general_news",
            "query": "省份 事件类型 完整时间",
            "description": "通用新闻搜索"
        }},
        {{
            "layer": "precise_location",
            "query": "国家 地区 事件类型 实体名",
            "description": "精确定位搜索"
        }},
        {{
            "layer": "entity_focused",
            "query": "实体名 省份 年份",
            "description": "实体优先搜索"
        }},
        {{
            "layer": "geopolitical",
            "query": "民族地区名 事件类型 年份",
            "description": "地缘视角搜索"
        }}
    ],

    "keywords": ["中文关键词1", "中文关键词2"],
    "keywords_en": ["English core keyword 1", "English core keyword 2"],

    "time_sensitivity": "high|medium|low",
    "suggested_time_range": "qdr:d|qdr:w|qdr:m|qdr:y",

    "layer_search_config": {{
        "layer_0_1": {{
            "description": "官方来源和当地主流媒体",
            "language": "zh",
            "keywords": ["中文事件核心词"],
            "enabled": true
        }},
        "layer_2": {{
            "description": "周边地区媒体",
            "language": "ja|ko|en",
            "keywords": ["该语言的事件核心词"],
            "enabled": true
        }},
        "layer_3": {{
            "description": "国际权威媒体",
            "language": "en",
            "keywords": ["英文事件核心词，与 keyword_combinations 中的 query 保持一致"],
            "enabled": true
        }},
        "layer_4": {{
            "description": "智库和分析机构",
            "language": "en",
            "keywords": ["英文分析类关键词"],
            "enabled": true
        }}
    }}
}}

**重要**:
- keyword_combinations 中的 query 是完整的搜索语句，将直接发送给搜索引擎
- layer_search_config 中的 keywords 应该与 keyword_combinations 保持一致
- 英文关键词必须是实际新闻会使用的表述，不要生造

请只返回 JSON，不要添加任何其他文字。"""


class QueryAnalyzerNode:
    """查询分析节点

    使用 Claude 分析搜索查询，提取:
    - 当事方（国家、组织、人物）
    - 关键词（中英文）
    - 时间敏感度和建议时间范围
    - 搜索策略建议
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Anthropic] = None,
    ):
        """初始化查询分析节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()
        self.client = anthropic_client or Anthropic()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行查询分析

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        query = state.get("query", "")
        user_id = state.get("user_id", "")

        if not query:
            logger.warning(f"[user:{user_id}] Empty query received")
            return {
                "analysis": {},
                "parties": [],
                "keywords": [],
                "time_range": "qdr:m",
                "status": "failed",
                "error_message": "查询为空",
            }

        try:
            logger.info(f"[user:{user_id}] Analyzing query: {query[:50]}...")

            # v4.4.0: 由 Claude 完成所有分析，包括语言判断和关键词翻译
            analysis = self._analyze_with_claude(query)

            # 提取分层搜索配置 (核心改进)
            layer_search_config = analysis.get("layer_search_config", {})

            # 提取关键信息
            parties = self._extract_party_names(analysis)
            keywords = analysis.get("keywords", [])
            keywords_en = analysis.get("keywords_en", [])
            time_range = analysis.get("suggested_time_range", "qdr:m")

            # 限制当事方数量
            if len(parties) > self.config.max_parties:
                parties = parties[: self.config.max_parties]

            # 从 layer_search_config 提取目标语言列表
            target_languages = self._extract_target_languages(layer_search_config)

            logger.info(
                f"[user:{user_id}] Analysis complete: "
                f"{len(parties)} parties, {len(keywords)} keywords, "
                f"layer_search_config={list(layer_search_config.keys())}, "
                f"target_languages={target_languages}"
            )

            return {
                "analysis": analysis,
                "parties": parties,
                "keywords": keywords,
                "keywords_en": keywords_en,  # v4.4.0: 英文关键词
                "time_range": time_range,
                "target_languages": target_languages,
                "layer_search_config": layer_search_config,  # v4.4.0: 分层搜索配置
                "enabled_layers": self.config.get_enabled_layers(),
                "status": "running",
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Query analysis failed: {e}")
            # v4.5.0: 降级逻辑 - 使用基本关键词提取而非直接使用原始查询
            search_intent = detect_search_intent(query)
            fallback_languages = search_intent.get("target_languages") or get_default_languages_for_query(query)

            # v4.5.0: 简单的关键词提取 - 从查询中提取核心要素
            fallback_keywords = self._extract_fallback_keywords(query)

            # 生成默认的分层搜索配置 (v4.5.0: 使用提取的关键词)
            default_layer_config = {
                "layer_0_1": {
                    "description": "官方来源和当地主流媒体",
                    "language": "zh",
                    "keywords": fallback_keywords["zh"],
                    "enabled": True
                },
                "layer_2": {
                    "description": "周边地区媒体",
                    "language": "zh",
                    "keywords": fallback_keywords["zh"],
                    "enabled": True
                },
                "layer_3": {
                    "description": "国际权威媒体",
                    "language": "en",
                    "keywords": fallback_keywords["en"],  # v4.5.0: 使用提取的英文关键词
                    "enabled": True
                },
                "layer_4": {
                    "description": "智库和分析机构",
                    "language": "en",
                    "keywords": fallback_keywords["en"],
                    "enabled": True
                }
            }

            return {
                "analysis": {"search_intent": search_intent},
                "parties": [],
                "keywords": fallback_keywords["zh"],
                "keywords_en": fallback_keywords["en"],
                "time_range": "qdr:m",
                "target_languages": fallback_languages,
                "layer_search_config": default_layer_config,
                "enabled_layers": self.config.get_enabled_layers(),
                "status": "running",  # 继续执行，使用默认值
                "error_message": f"查询分析失败: {str(e)}",
            }

    def _analyze_with_claude(self, query: str) -> Dict[str, Any]:
        """使用 Claude 分析查询

        Args:
            query: 搜索查询

        Returns:
            分析结果字典
        """
        prompt = QUERY_ANALYSIS_PROMPT.format(query=query)

        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        # 提取响应文本
        response_text = response.content[0].text.strip()

        # 清理 JSON 响应（移除可能的 markdown 代码块）
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # 移除首尾的 ``` 行
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        # 解析 JSON
        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            # 尝试提取 JSON 部分
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError("Unable to extract JSON from response")

        return analysis

    def _extract_party_names(self, analysis: Dict[str, Any]) -> List[str]:
        """从分析结果中提取当事方名称

        Args:
            analysis: Claude 分析结果

        Returns:
            当事方名称列表
        """
        parties = analysis.get("parties", [])
        if not parties:
            return []

        return [
            p.get("name", "") for p in parties
            if p.get("name")
        ]

    def _extract_keywords(self, analysis: Dict[str, Any]) -> List[str]:
        """从分析结果中提取关键词

        Args:
            analysis: Claude 分析结果

        Returns:
            关键词列表（中英文合并）
        """
        keywords = []

        # 中文关键词
        zh_keywords = analysis.get("keywords", [])
        if zh_keywords:
            keywords.extend(zh_keywords)

        # 英文关键词
        en_keywords = analysis.get("keywords_en", [])
        if en_keywords:
            keywords.extend(en_keywords)

        # 去重
        return list(dict.fromkeys(keywords))

    def _extract_target_languages(self, layer_search_config: Dict[str, Any]) -> List[str]:
        """从分层搜索配置中提取目标语言列表 (v4.4.0)

        Args:
            layer_search_config: 分层搜索配置

        Returns:
            去重后的语言代码列表
        """
        languages = set()

        for layer_key, layer_config in layer_search_config.items():
            if isinstance(layer_config, dict):
                lang = layer_config.get("language")
                if lang and layer_config.get("enabled", True):
                    languages.add(lang)

        # 确保���少有默认语言
        if not languages:
            languages = {"zh", "en"}

        return list(languages)

    def _extract_fallback_keywords(self, query: str) -> Dict[str, List[str]]:
        """提取降级关键词 (v4.5.0)

        当 LLM 分析失败时，使用简单的规则提取关键词。
        目标是避免使用用户意图词（如"西方媒体"）作为搜索关键词。

        Args:
            query: 原始查询

        Returns:
            包含 zh 和 en 关键词的字典
        """
        # 移除常见的用户意图词
        intent_words_to_remove = [
            "西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体",
            "海外媒体", "当地媒体", "国内媒体", "中文媒体", "本地媒体",
            "亚洲媒体", "欧洲媒体", "中东媒体", "拉美媒体",
            "western media", "international media", "overseas media",
            "domestic media", "local media", "mainstream media",
        ]

        # 简单的地名/实体名翻译映射
        translations = {
            "四川": "Sichuan",
            "阿坝": "Aba",
            "红旗": "Hongqi",
            "大桥": "Bridge",
            "垮塌": "collapse",
            "倒塌": "collapse",
            "地震": "earthquake",
            "冲突": "conflict",
            "报道": "report",
            "中国": "China",
        }

        # 清理查询
        cleaned_query = query
        for word in intent_words_to_remove:
            cleaned_query = cleaned_query.replace(word, " ")

        # 移除"对"、"的"等虚词
        for particle in ["对", "的", "关于", "有关", "搜索", "查找", "检索", "在", "从"]:
            cleaned_query = cleaned_query.replace(particle, " ")

        # 使用正则分割中文和英文
        import re
        # 匹配中文词组（2个或以上汉字）
        zh_pattern = re.compile(r'[\u4e00-\u9fff]{2,4}')  # 限制为2-4个字的词
        # 匹配英文单词和数字
        en_pattern = re.compile(r'[a-zA-Z0-9]+')

        zh_matches = zh_pattern.findall(cleaned_query)
        en_matches = en_pattern.findall(cleaned_query)

        zh_keywords = []
        en_keywords = []

        # 提取中文关键词（取前3个有意义的词）
        for word in zh_matches:
            if word not in intent_words_to_remove:
                zh_keywords.append(word)

        # 提取英文关键词（取前4个有意义的词）
        for word in en_matches:
            word_lower = word.lower()
            if word_lower not in [w.lower() for w in intent_words_to_remove]:
                en_keywords.append(word)

        # 如果没有英文关键词，尝试翻译中文关键词
        if not en_keywords and zh_keywords:
            for word in zh_keywords[:3]:
                translated = translations.get(word, None)
                if translated:
                    en_keywords.append(translated)

        # 如果没有提取到有效关键词，使用默认
        if not zh_keywords:
            zh_keywords = ["事件", "报道"]
        if not en_keywords:
            en_keywords = ["event", "report"]

        # 去重
        zh_keywords = list(dict.fromkeys(zh_keywords))
        en_keywords = list(dict.fromkeys(en_keywords))

        logger.info(
                f"[FALLBACK_KEYWORDS] zh={zh_keywords[:3]}, en={en_keywords[:3]}"
            )

        return {
            "zh": zh_keywords[:3],  # 最多3个中文关键词
            "en": en_keywords[:4],  # 最多4个英文关键词
        }
