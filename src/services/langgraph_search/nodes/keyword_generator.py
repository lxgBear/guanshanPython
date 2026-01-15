"""关键词生成节点 (v4.7.0)

OSINT 架构中的关键词生成节点，专门负责基于 investigation_target 生成搜索关键词。
输入是纯事件内容（不含媒体类型约束），确保关键词不包含意图词。
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from anthropic import Anthropic

from ..state import SearchState, KeywordGroup, SearchLayer, LAYER_NAMES
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


# 关键词生成 Prompt - 专注于生成搜索关键词，不涉及意图解析
KEYWORD_GEN_PROMPT = """你是 OSINT 关键词生成专家。请基于事件核心内容生成分层搜索关键词。

## 核心原则

### 1. 纯事件内容
- 只使用 investigation_target（事件核心）生成关键词
- investigation_target 中**不包含**任何媒体类型词或意图动词
- source_type_constraint 仅决定搜索哪些媒体，**绝不作为搜索关键词**

### 2. 严格禁止词
以下词语**严禁**出现在 keywords 中：
- 媒体类型词：西方媒体、欧美媒体、国际媒体、当地媒体、中文媒体
- 意图动词：报道、反应、整理、检索、搜索、查找、收集
- 英文对应：western media, international media, report, reaction, coverage, response

### 3. 分层策略
每层根据其目标媒体使用不同的关键词策略：

**Layer 0: 官方来源** (政府网站、官方机构)
- 语言：中文优先
- 关键词：地点 + 事件类型 + 官方术语
- 示例：["四川阿坝红旗大桥垮塌官方通报", "阿坝州政府红旗大桥"]

**Layer 1: 主流媒体** (国内主流媒体)
- 语言：中文
- 关键词：地点 + 事件 + 时间
- 示例：["四川阿坝红旗大桥垮塌2025年", "红旗大桥事故"]

**Layer 2: 周边地区媒体** (日韩等周边)
- 语言：日文或英文
- 关键词：英文地名 + 事件英文 + 年份
- 示例：["Sichuan Aba Hongqi Bridge collapse 2025", "China Sichuan bridge"]

**Layer 3: 国际主流媒体** (路透、BBC、AP等)
- 语言：英文
- 关键词：英文地名 + 事件英文 + 时间范围
- 示例：["Sichuan China bridge collapse November 2025", "Hongqi Bridge Aba collapse"]

**Layer 4: 智库分析机构** (Crisis Group等)
- 语言：英文
- 关键词：专业术语 + 分析性词汇
- 示例：["China infrastructure bridge safety Sichuan", "Chinese bridge collapse analysis"]

## 输出格式

返回以下 JSON 格式：

{{
    "keyword_groups": [
        {
            "layer": 0,
            "language": "zh",
            "search_type": "news",
            "description": "官方来源",
            "keywords": ["关键词1", "关键词2"]
        },
        {
            "layer": 1,
            "language": "zh",
            "search_type": "news",
            "description": "主流媒体",
            "keywords": ["关键词1", "关键词2"]
        },
        {
            "layer": 2,
            "language": "en",
            "search_type": "news",
            "description": "周边地区媒体",
            "keywords": ["keyword1", "keyword2"]
        },
        {
            "layer": 3,
            "language": "en",
            "search_type": "news",
            "description": "国际主流媒体",
            "keywords": ["keyword1", "keyword2"]
        },
        {
            "layer": 4,
            "language": "en",
            "search_type": "web",
            "description": "智库分析机构",
            "keywords": ["keyword1", "keyword2"]
        }
    ]
}}

## 禁止事项检查清单

- ❌ keywords 中包含 "Western Media" 或 "西方媒体"
- ❌ keywords 中包含 "report" 或 "报道"
- ❌ keywords 中包含 "reaction" 或 "反应"
- ❌ keywords 中包含任何媒体类型词
- ✅ keywords 纯粹包含事件内容（地点、事件、时间、实体名）
- ✅ 每层 2-4 个关键词
- ✅ 英文关键词是实际新闻会使用的表述

## 输入参数

investigation_target: "{investigation_target}"
source_type_constraint: "{source_type_constraint}" (仅参考，不作为关键词）

请只返回 JSON，不要添加任何其他文字。"""


# 简单的地名/实体名翻译映射（用于降级）
TRANSLATIONS = {
    "四川": "Sichuan",
    "阿坝": "Aba",
    "红旗": "Hongqi",
    "大桥": "Bridge",
    "垮塌": "collapse",
    "倒塌": "collapse",
    "地震": "earthquake",
    "冲突": "conflict",
    "中国": "China",
}


def clean_investigation_target(target: str, source_type_constraint: Optional[str] = None) -> str:
    """清理 investigation_target，移除可能的媒体类型词

    Args:
        target: 原始调查目标
        source_type_constraint: 媒体类型约束（用于识别需要过滤的词）

    Returns:
        清理后的调查目标
    """
    # 移除已知的媒体类型词和意图动词
    words_to_remove = [
        "西方媒体", "西方主流媒体", "欧美媒体", "国际媒体", "海外媒体",
        "当地媒体", "国内媒体", "中国媒体", "中文媒体",
        "亚洲媒体", "欧洲媒体", "中东媒体",
        "报道", "反应", "整理", "检索", "搜索", "查找", "收集",
        "western media", "international media", "report", "reaction",
        "coverage", "response", "collect", "search", "find",
    ]

    cleaned = target
    for word in words_to_remove:
        cleaned = cleaned.replace(word, " ")

    # 清理多余空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def generate_fallback_keyword_groups(
    investigation_target: str,
    target_languages: List[str],
    time_range: str
) -> List[KeywordGroup]:
    """降级关键词生成（当 LLM 失败时使用规则）

    Args:
        investigation_target: 事件核心
        target_languages: 目标语言列表
        time_range: 时间范围

    Returns:
        关键词组列表
    """
    # 清理 investigation_target
    target = clean_investigation_target(investigation_target)

    # 提取中英文关键词
    zh_keywords = []
    en_keywords = []

    # 中文分词（简单：提取 2-4 字词）
    zh_pattern = re.compile(r'[\u4e00-\u9fff]{2,4}')
    for match in zh_pattern.findall(target):
        zh_keywords.append(match)

    # 英文分词
    en_pattern = re.compile(r'[a-zA-Z]{2,}')
    for match in en_pattern.findall(target):
        en_keywords.append(match)

    # 添加翻译的英文字
    for zh_kw in zh_keywords[:3]:
        if zh_kw in TRANSLATIONS:
            translated = TRANSLATIONS[zh_kw]
            if translated not in en_keywords:
                en_keywords.append(translated)

    # 如果没有中文关键词，使用默认
    if not zh_keywords:
        zh_keywords = [target[:20]] if len(target) > 20 else [target]

    # 如果没有英文关键词，使用翻译
    if not en_keywords:
        en_keywords = []
        for zh_kw in zh_keywords[:3]:
            if zh_kw in TRANSLATIONS:
                en_keywords.append(TRANSLATIONS[zh_kw])
        if not en_keywords:
            en_keywords = ["event", "report"]

    # 去重
    zh_keywords = list(dict.fromkeys(zh_keywords))
    en_keywords = list(dict.fromkeys(en_keywords))

    # 构建分层关键词组
    keyword_groups = []

    # Layer 0: 官方来源 (中文)
    if "zh" in target_languages:
        keyword_groups.append(KeywordGroup(
            keywords=zh_keywords[:3] + ["官方通报"],
            layer=SearchLayer.OFFICIAL.value,
            language="zh",
            search_type="news",
            description="官方来源",
        ))

    # Layer 1: 主流媒体 (中文)
    if "zh" in target_languages:
        keyword_groups.append(KeywordGroup(
            keywords=zh_keywords[:4],
            layer=SearchLayer.MAINSTREAM.value,
            language="zh",
            search_type="news",
            description="主流媒体",
        ))

    # Layer 2: 周边地区媒体 (日文/英文)
    if any(lang in target_languages for lang in ["ja", "ko"]):
        keyword_groups.append(KeywordGroup(
            keywords=en_keywords[:3],
            layer=SearchLayer.REGIONAL.value,
            language="en",
            search_type="news",
            description="周边地区媒体",
        ))

    # Layer 3: 国际主流媒体 (英文)
    if "en" in target_languages:
        keyword_groups.append(KeywordGroup(
            keywords=en_keywords[:4],
            layer=SearchLayer.INTERNATIONAL.value,
            language="en",
            search_type="news",
            description="国际主流媒体",
        ))

    # Layer 4: 智库分析机构 (英文)
    if "en" in target_languages:
        keyword_groups.append(KeywordGroup(
            keywords=en_keywords[:3] + ["analysis", "infrastructure"],
            layer=SearchLayer.THINK_TANK.value,
            language="en",
            search_type="web",
            description="智库分析机构",
        ))

    return keyword_groups


class KeywordGeneratorNode:
    """关键词生成节点 (v4.7.0)

    OSINT 架构的第二阶段：基于 investigation_target 生成分层搜索关键词。
    职责：
    1. 使用 LLM 生成 5 层关键词组
    2. 确保关键词不包含任何媒体类型词或意图动词
    3. 提供降级逻辑（当 LLM 失败时）

    输入是 investigation_target（纯事件内容），不包含 source_type_constraint。
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Anthropic] = None,
    ):
        """初始化关键词生成节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()
        self.client = anthropic_client or Anthropic()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行关键词生成

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")

        # 检查是否已有 parsed_intent
        parsed_intent = state.get("parsed_intent")
        if not parsed_intent:
            logger.warning(f"[user:{user_id}] KeywordGenerator: no parsed_intent found, skipping")
            return {
                "keyword_groups": [],
                "error_message": "缺少意图解析结果",
            }

        investigation_target = parsed_intent.get("investigation_target", "")
        source_type_constraint = parsed_intent.get("source_type_constraint")
        time_range = state.get("time_range", "qdr:m")
        target_languages = state.get("target_languages", ["en", "zh"])

        if not investigation_target:
            logger.warning(f"[user:{user_id}] KeywordGenerator: empty investigation_target")
            return {
                "keyword_groups": [],
                "error_message": "调查目标为空",
            }

        try:
            logger.info(
                f"[user:{user_id}] KeywordGenerator generating for target: "
                f"{investigation_target[:40]}... (source_constraint: {source_type_constraint})"
            )

            # 调用 LLM 生成关键词
            keyword_groups_dict = self._generate_with_claude(
                investigation_target,
                source_type_constraint
            )

            # 转换为 KeywordGroup 对象列表
            keyword_groups = [
                KeywordGroup.from_dict(g) for g in keyword_groups_dict
            ]

            logger.info(
                f"[user:{user_id}] KeywordGenerator generated {len(keyword_groups)} groups: "
                f"{[f'{LAYER_NAMES.get(g.layer, g.layer)}: {len(g.keywords)}kws' for g in keyword_groups]}"
            )

            return {
                "keyword_groups": [g.to_dict() for g in keyword_groups],
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] KeywordGenerator failed: {e}")

            # 使用降级逻辑生成关键词
            fallback_groups = generate_fallback_keyword_groups(
                investigation_target,
                target_languages,
                time_range
            )

            logger.warning(
                f"[user:{user_id}] Using fallback keyword generation: "
                f"{len(fallback_groups)} groups"
            )

            return {
                "keyword_groups": [g.to_dict() for g in fallback_groups],
                "error_message": f"关键词生成失败，使用降级策略: {str(e)}",
            }

    def _generate_with_claude(
        self,
        investigation_target: str,
        source_type_constraint: Optional[str]
    ) -> List[Dict[str, Any]]:
        """使用 Claude 生成关键词

        Args:
            investigation_target: 调查目标（纯事件内容）
            source_type_constraint: 媒体类型约束（仅参考，不作为关键词）

        Returns:
            关键词组字典列表
        """
        # 清理 investigation_target，移除可能的意图词
        cleaned_target = clean_investigation_target(
            investigation_target,
            source_type_constraint
        )

        prompt = KEYWORD_GEN_PROMPT.format(
            investigation_target=cleaned_target,
            source_type_constraint=source_type_constraint or "无"
        )

        response = self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.claude_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        # 提取响应文本
        response_text = response.content[0].text.strip()

        # 清理 JSON 响应
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        # 解析 JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("Unable to extract JSON from response")

        return result.get("keyword_groups", [])
