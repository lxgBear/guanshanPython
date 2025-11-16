"""
NL Search Prompt 模板
用于 LLM 处理自然语言查询
"""

# 查询解析 Prompt
QUERY_PARSE_PROMPT = """你是一个专业的查询分析助手，擅长分析用户的自然语言查询意图。

请分析以下用户查询，提取以下信息：

用户查询：{query_text}

请以 JSON 格式返回分析结果，包含以下字段：
1. intent: 查询意图类型（如：technology_news, product_review, tutorial, research, general_info, entertainment, sports, finance 等）
2. keywords: 提取的关键词列表（3-8个最重要的关键词）
3. entities: 识别的实体列表，每个实体包含 type 和 value（如：{{{{"type": "technology", "value": "AI"}}}}）
4. time_range: 时间范围信息（如果查询包含时间相关词汇）
   - type: 时间类型（recent, specific, range, none）
   - from: 开始时间（YYYY-MM-DD格式，如果适用）
   - to: 结束时间（YYYY-MM-DD格式，如果适用）
5. category: 内容分类（tech, business, entertainment, sports, health, science, finance, education, other）
6. confidence: 分析置信度（0.0-1.0，建议值：0.7-0.95表示高置信度）

**重要提示**：
- 仅返回纯 JSON 对象，不要添加任何解释文字
- 关键词必须是中文或英文，避免混合
- 时间范围推断要合理（如"最近"指过去3-6个月）
- 实体类型包括：technology, person, organization, location, product, event 等

**示例**：

输入："最近有哪些AI技术突破"
输出：
```json
{{{{
  "intent": "technology_news",
  "keywords": ["AI", "技术突破", "人工智能", "最新进展"],
  "entities": [
    {{{{"type": "technology", "value": "AI"}}}},
    {{{{"type": "technology", "value": "人工智能"}}}}
  ],
  "time_range": {{{{
    "type": "recent",
    "from": "2024-06-01",
    "to": "2024-12-31"
  }}}},
  "category": "tech",
  "confidence": 0.95
}}}}
```

现在请分析用户的查询。
"""

# 查询精炼 Prompt
QUERY_REFINE_PROMPT = """你是一个专业的搜索优化助手，擅长将自然语言查询转换为精准的搜索关键词。

用户的原始查询：{query_text}

查询意图分析：{llm_analysis}

请根据以上信息，生成一个优化的搜索查询，遵循以下规则：

**优化规则**：
1. 保留最核心的关键词（3-6个词）
2. 去除冗余的语气词和无效词（如："有哪些"、"请问"、"能不能"等）
3. 添加时间限定词（如果原查询包含时间信息）
4. 使用空格分隔关键词，不要使用特殊符号
5. 保持原查询的语言（中文或英文）
6. 长度控制在 15-50 个字符
7. 针对不同意图优化：
   - technology_news: 添加"最新"、年份等
   - product_review: 添加"评测"、"体验"等
   - tutorial: 添加"教程"、"指南"等
   - research: 添加"研究"、"论文"等

**返回格式**：
仅返回优化后的搜索查询字符串，不要添加任何解释或额外内容。

**示例**：

输入查询："最近有哪些AI技术突破"
意图分析：{{{{"intent": "technology_news", "keywords": ["AI", "技术突破"]}}}}
输出："AI 技术突破 2024 最新"

输入查询："Python 数据分析怎么做"
意图分析：{{{{"intent": "tutorial", "keywords": ["Python", "数据分析"]}}}}
输出："Python 数据分析 教程"

现在请优化用户的查询。
"""

# 错误恢复 Prompt（当 LLM 返回格式错误时使用）
QUERY_PARSE_FALLBACK_PROMPT = """之前的分析返回了无效的 JSON 格式。请重新分析用户查询，并严格按照以下 JSON 格式返回：

用户查询：{query_text}

返回格式（必须是有效的 JSON）：
{{{{
  "intent": "查询意图类型",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "entities": [],
  "time_range": {{{{
    "type": "none",
    "from": null,
    "to": null
  }}}},
  "category": "other",
  "confidence": 0.7
}}}}

请确保返回的是**纯 JSON 对象**，不要包含任何 Markdown 代码块标记或解释文字。
"""


def get_query_parse_prompt(query_text: str) -> str:
    """
    获取查询解析 Prompt

    Args:
        query_text: 用户原始查询

    Returns:
        完整的 Prompt 字符串
    """
    return QUERY_PARSE_PROMPT.format(query_text=query_text)


def get_query_refine_prompt(query_text: str, llm_analysis: dict) -> str:
    """
    获取查询精炼 Prompt

    Args:
        query_text: 用户原始查询
        llm_analysis: LLM 解析结果

    Returns:
        完整的 Prompt 字符串
    """
    import json
    analysis_str = json.dumps(llm_analysis, ensure_ascii=False, indent=2)
    return QUERY_REFINE_PROMPT.format(
        query_text=query_text,
        llm_analysis=analysis_str
    )


def get_query_parse_fallback_prompt(query_text: str) -> str:
    """
    获取查询解析失败后的后备 Prompt

    Args:
        query_text: 用户原始查询

    Returns:
        完整的 Prompt 字符串
    """
    return QUERY_PARSE_FALLBACK_PROMPT.format(query_text=query_text)
