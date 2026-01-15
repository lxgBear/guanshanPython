"""意图解析节点 (v4.7.0)

OSINT 架构中的意图解析节点，专门负责从用户查询中提取意图要素。
与关键词生成节点分离，确保 source_type_constraint 不作为搜索关键词。
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from anthropic import Anthropic

from ..state import SearchState, ParsedIntent
from ..config import LangGraphSearchConfig
from ..languages import (
    get_media_domains,
    get_languages_by_region,
    get_default_languages_for_query,
)

logger = logging.getLogger(__name__)


# 意图解析 Prompt - 专注于意图识别，不涉及关键词生成
INTENT_PARSE_PROMPT = """你是 OSINT 意图解析专家。请从用户查询中提取意图要素。

## 核心原则

### 1. 职责分离
- **本节点只负责提取意图**：识别用户想要什么、想搜索哪些媒体
- **不生成搜索关键词**：关键词生成由专门的 KeywordGeneratorNode 完成

### 2. 意图 vs 内容
- **意图词**：决定"搜索策略"，但**绝不能**作为搜索关键词
  - 媒体类型：西方媒体、西方主流媒体、欧美媒体、国际媒体、当地媒体
  - 意图动词：报道、反应、整理、检索��搜索、收集
  - 英文对应：western media, international media, report, coverage, reaction, response

- **内容词**：事件核心，用于生成搜索关键词
  - 地点：四川、阿坝、红旗
  - 事件：大桥、垮塌、地震、冲突
  - 时间：2025年、11月11日
  - 实体：Sichuan, Aba, Hongqi, Bridge

## 输出格式

返回以下 JSON 格式的分析结果：

{{
    "investigation_target": "事件核心描述，用于关键词生成",
    "source_type_constraint": "用户想搜索的媒体类型（仅用于域名过滤）",
    "time_range": "时间范围（如有）",
    "investigation_type": "调查类型",
    "user_intent_raw": "原始意图描述"
}}

## 示例分析

### 示例 1
输入: "请检索整理西方主流媒体对2025年11月11日四川阿坝红旗大桥垮塌的报道和反应"

分析:
- investigation_target: "2025年11月11日四川阿坝红旗大桥垮塌事件"
- source_type_constraint: "西方主流媒体"
  ⚠️ 注意：这个字段仅决定搜索哪些媒体（路透、BBC、AP等），不作为搜索关键词
- time_range: "2025-11-11 至今"
- investigation_type: "event"

### 示例 2
输入: "搜索当地媒体关于台海地震的最新报道"

分析:
- investigation_target: "台海地震事件"
- source_type_constraint: "当地媒体"
- time_range: "最近"
- investigation_type: "event"

## 禁止事项

❌ 不在 investigation_target 中包含媒体类型词
❌ 不返回任何搜索关键词（keywords 字段）
❌ 不混淆意图和内容

请只返回 JSON，不要添加任何其他文字。"""


def map_source_type_to_domains(source_type: Optional[str]) -> List[str]:
    """将媒体类型映射到域名列表

    Args:
        source_type: 媒体类型约束

    Returns:
        对应的搜索域名列表
    """
    if not source_type:
        return []

    source_type_lower = source_type.lower()

    # 西方主流媒体
    if any(kw in source_type_lower for kw in [
        "西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体", "海外媒体",
        "western media", "western news", "international media", "overseas media"
    ]):
        return get_media_domains("en")

    # 亚洲媒体
    if any(kw in source_type_lower for kw in [
        "亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体",
        "asian media", "asia news", "east asian media"
    ]):
        return get_media_domains("ja") + get_media_domains("ko")

    # 当地媒体/国内媒体
    if any(kw in source_type_lower for kw in [
        "当地媒体", "国内媒体", "中国媒体", "中文媒体",
        "domestic media", "chinese media", "local media"
    ]):
        return get_media_domains("zh")

    # 欧洲媒体
    if any(kw in source_type_lower for kw in [
        "欧洲媒体", "欧盟媒体", "欧洲新闻",
        "european media", "eu media", "europe news"
    ]):
        return get_media_domains("fr") + get_media_domains("de")

    return []


def map_source_type_to_languages(source_type: Optional[str]) -> List[str]:
    """将媒体类型映射到目标语言列表

    Args:
        source_type: 媒体类型约束

    Returns:
        对应的语言代码列表
    """
    if not source_type:
        return []

    source_type_lower = source_type.lower()

    # 西方主流媒体 → 欧洲语言 + 英语
    if any(kw in source_type_lower for kw in [
        "西方媒体", "西方主流媒体", "欧美媒体", "western media"
    ]):
        return ["en", "fr", "de", "es", "it"]

    # 亚洲媒体 → 亚洲语言
    if any(kw in source_type_lower for kw in [
        "亚洲媒体", "asian media"
    ]):
        return ["ja", "ko", "zh", "vi", "th"]

    # 当地媒体/国内媒体 → 中文
    if any(kw in source_type_lower for kw in [
        "当地媒体", "国内媒体", "中国媒体", "domestic media", "chinese media"
    ]):
        return ["zh"]

    # 欧洲媒体 → 欧洲语言
    if any(kw in source_type_lower for kw in [
        "欧洲媒体", "european media"
    ]):
        return ["fr", "de", "es", "it", "nl"]

    return []


def extract_time_range(query: str, intent_text: Optional[str] = None) -> str:
    """从查询中提取时间范围

    Args:
        query: 原始查询
        intent_text: 意图解析结果（可选）

    Returns:
        时间范围字符串 (qdr:d, qdr:w, qdr:m, qdr:y, custom:YYYY-MM-DD)
    """
    # 检查明确的日期格式
    date_patterns = [
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        r'(\d{1,2})月(\d{1,2})日',
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
    ]

    for pattern in date_patterns:
        if re.search(pattern, query):
            # 找到具体日期，返回 qdr:d（日）或 qdr:w（周）
            return "qdr:w" if "周" in query or "week" in query.lower() else "qdr:d"

    # 检查时间关键词
    time_keywords = {
        "今日": "qdr:d",
        "今天": "qdr:d",
        "最近": "qdr:w",
        "latest": "qdr:w",
        "本周": "qdr:w",
        "本月": "qdr:m",
        "今年": "qdr:y",
        "yesterday": "qdr:d",
        "yesterday": "qdr:d",
    }

    for kw, time_range in time_keywords.items():
        if kw in query.lower():
            return time_range

    # 默认返回一个月范围
    return "qdr:m"


class IntentParserNode:
    """意图解析节点 (v4.7.0)

    OSINT 架构的第一阶段：解析用户查询的意图要素。
    职责：
    1. 提取 investigation_target（事件核心）
    2. 提取 source_type_constraint（媒体类型约束）
    3. 提取 time_range（时间范围）
    4. 确定 investigation_type（调查类型）

    关键设计：source_type_constraint 只决定搜索哪些媒体，不作为搜索关键词。
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Anthropic] = None,
    ):
        """初始化意图解析节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()
        self.client = anthropic_client or Anthropic()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行意图解析

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        query = state.get("query", "")
        user_id = state.get("user_id", "")

        if not query:
            logger.warning(f"[user:{user_id}] Empty query received in IntentParser")
            return {
                "parsed_intent": None,
                "source_type_constraint": None,
                "search_domains": [],
                "target_languages": state.get("target_languages", []),
                "error_message": "查询为空",
            }

        try:
            logger.info(f"[user:{user_id}] IntentParser analyzing query: {query[:50]}...")

            # 调用 Claude 解析意图
            intent_dict = self._parse_intent_with_claude(query)

            # 映射 source_type_constraint 到域名和语言
            source_type_constraint = intent_dict.get("source_type_constraint")
            search_domains = map_source_type_to_domains(source_type_constraint)
            target_languages = map_source_type_to_languages(source_type_constraint)

            # 如果没有检测到特定媒体类型，使用默认语言
            if not target_languages:
                target_languages = state.get("target_languages", get_default_languages_for_query(query))

            # 提取时间范围
            time_range = extract_time_range(query, intent_dict.get("time_range"))

            # 构建 ParsedIntent
            parsed_intent = ParsedIntent(
                investigation_target=intent_dict.get("investigation_target", ""),
                source_type_constraint=source_type_constraint,
                time_range=time_range,
                investigation_type=intent_dict.get("investigation_type", "event"),
                user_intent_raw=intent_dict.get("user_intent_raw"),
            )

            logger.info(
                f"[user:{user_id}] IntentParser complete: "
                f"target='{intent_dict.get('investigation_target', '')[:30]}...', "
                f"source_constraint={source_type_constraint}, "
                f"domains={len(search_domains)}, langs={target_languages}"
            )

            return {
                "parsed_intent": parsed_intent.to_dict(),
                "source_type_constraint": source_type_constraint,
                "search_domains": search_domains,
                "target_languages": target_languages,
                "time_range": time_range,
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] IntentParser failed: {e}")

            # 降级逻辑：使用规则提取
            fallback_result = self._fallback_parse_intent(query, state)
            return {
                "parsed_intent": fallback_result["parsed_intent"],
                "source_type_constraint": fallback_result["source_type_constraint"],
                "search_domains": fallback_result["search_domains"],
                "target_languages": fallback_result["target_languages"],
                "time_range": "qdr:m",
                "error_message": f"意图解析失败: {str(e)}",
            }

    def _parse_intent_with_claude(self, query: str) -> Dict[str, Any]:
        """使用 Claude 解析意图

        Args:
            query: 搜索查询

        Returns:
            意图解析结果字典
        """
        # 构建完整的 prompt，包含用户查询
        prompt = f"{INTENT_PARSE_PROMPT}\n\n用户查询: {query}\n\n请分析上述查询并返回 JSON 结果。"

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
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        # 解析 JSON
        try:
            intent = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                intent = json.loads(json_match.group())
            else:
                raise ValueError("Unable to extract JSON from response")

        return intent

    def _fallback_parse_intent(self, query: str, state: SearchState) -> Dict[str, Any]:
        """降级意图解析（当 LLM 失败时使用规则）

        Args:
            query: 搜索查询
            state: 当前搜索状态

        Returns:
            降级的意图解析结果
        """
        # 清理查询中的意图动词和媒体类型词
        cleaned_query = query
        for particle in ["对", "的", "关于", "有关", "检索", "搜索", "查找", "整理", "报道", "反应"]:
            cleaned_query = cleaned_query.replace(particle, " ")

        # 提取 investigation_target
        investigation_target = cleaned_query.strip()

        # 检测媒体类型约束
        source_type_constraint = None
        query_lower = query.lower()

        western_keywords = ["西方媒体", "西方主流媒体", "欧美媒体", "western media"]
        domestic_keywords = ["当地媒体", "国内媒体", "中国媒体", "domestic media", "chinese media"]
        asian_keywords = ["亚洲媒体", "asian media"]
        european_keywords = ["欧洲媒体", "european media"]

        if any(kw in query_lower for kw in western_keywords):
            source_type_constraint = "西方主流媒体"
        elif any(kw in query_lower for kw in domestic_keywords):
            source_type_constraint = "当地媒体"
        elif any(kw in query_lower for kw in asian_keywords):
            source_type_constraint = "亚洲媒体"
        elif any(kw in query_lower for kw in european_keywords):
            source_type_constraint = "欧洲媒体"

        # 映射到域名和语言
        search_domains = map_source_type_to_domains(source_type_constraint)
        target_languages = map_source_type_to_languages(source_type_constraint)

        if not target_languages:
            target_languages = state.get("target_languages", ["en", "zh"])

        # 提取时间范围
        time_range = extract_time_range(query)

        # 构建降级意图
        fallback_intent = ParsedIntent(
            investigation_target=investigation_target,
            source_type_constraint=source_type_constraint,
            time_range=time_range,
            investigation_type="event",
            user_intent_raw=query,
        )

        return {
            "parsed_intent": fallback_intent.to_dict(),
            "source_type_constraint": source_type_constraint,
            "search_domains": search_domains,
            "target_languages": target_languages,
        }
