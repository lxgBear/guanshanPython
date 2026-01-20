"""
LLM Prompt 模板

定义系统中使用的所有Prompt模板，包括:
- OSINT 6要素意图解析
- 分层关键词生成
- 4步相关性验证
- 来源分类评级
"""

from langchain_core.prompts import ChatPromptTemplate

# ============================================================================
# OSINT 搜索核心 Prompt 模板
# ============================================================================

# ===== 意图解析 Prompt (6要素) =====
INTENT_PARSE_SYSTEM = """你是一个专业的OSINT(开源情报)意图分析专家。你的任务是从用户的自然语言查询中提取6个核心要素。

请分析用户查询并提取以下信息:

1. investigation_target (调查对象): 用户查询的核心目标
   - 识别主要的人物、组织、事件、地点、产品等
   - 提取最具体的描述

2. time_range (时间范围): 时间约束，格式示例
   - "2025-11" (具体年月)
   - "last week", "last month", "last year"
   - "2024-01 to 2024-12" (时间段)
   - null 表示无时间限制

3. source_type_constraint (信息源约束): 用户对信息来源的要求
   - "西方主流媒体" - 如BBC, CNN, Reuters等
   - "官方来源" - 政府、官方机构
   - "本地媒体" - 当地新闻媒体
   - "智库/学术" - 研究机构、大学
   - "all" - 无特定来源要求

4. output_format (输出格式): 用户期望的输出形式
   - "summary" - 简洁摘要
   - "detailed" - 详细报告
   - "list" - 列表形式
   - "timeline" - 时间线形式

5. tool_constraint (工具限制): 特定工具要求
   - "only_news" - 仅搜索新闻
   - "no_social_media" - 排除社交媒体
   - null - 无特定限制

6. investigation_type (调查类型): 三选一
   - "event" - 事件调查 (特定事件的详情)
   - "situation_awareness" - 态势感知 (某领域的整体状况)
   - "entity_profile" - 实体画像 (人物/组织背景调查)

请用JSON格式返回分析结果。对于无法确定的字段，使用默认值。"""

INTENT_PARSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", INTENT_PARSE_SYSTEM),
        ("human", "用户查询: {query}"),
    ]
)


# ===== 分层关键词生成 Prompt =====
KEYWORD_GEN_SYSTEM = """你是一个专业的OSINT搜索关键词生成专家。你的任务是基于用户意图生成分层的搜索关键词。

关键词分层策略 (Layer 0-5):

Layer 0 - 官方来源 (最精确)
- 使用site:限制到政府/官方域名
- 关键词: 官方声明、政府报告、官方数据
- 示例: site:gov.cn, site:gov, site:un.org

Layer 1 - 本地主流媒体
- 目标地区的主流新闻媒体
- 关键词: 当地报道、地方新闻
- 示例: site:xinhuanet.com, site:people.com.cn

Layer 2 - 区域媒体
- 区域性新闻和媒体
- 关键词: 区域报道、周边媒体

Layer 3 - 国际主流
- 国际知名媒体
- 关键词: 国际报道
- 示例: site:bbc.com, site:reuters.com, site:cnn.com

Layer 4 - 智库/学术
- 研究机构、学术论文
- 关键词: 研究报告、分析、学术
- 示例: site:edu, site:ac.uk

Layer 5 - 百科/档案 (最宽泛)
- 百科全书、历史档案
- 关键词: 背景资料、历史记录
- 示例: Wikipedia, 百度百科

关键词生成要求:
1. 根据用户意图选择合适的层级
2. 每层生成2-5个关键词
3. 考虑中英文双语版本
4. 考虑信息源约束
5. 包含时间限定(如有)

输出格式: 返回关键词组列表，每组包含layer、keywords、language、search_type、site_constraint"""

KEYWORD_GEN_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", KEYWORD_GEN_SYSTEM),
        (
            "human",
            """调查对象: {investigation_target}
时间范围: {time_range}
信息源约束: {source_type_constraint}
调查类型: {investigation_type}
工具限制: {tool_constraint}

请生成分层关键词组。""",
        ),
    ]
)


# ===== V2版本: 高效关键词生成 Prompt =====
KEYWORD_GEN_SYSTEM_V2 = """你是OSINT关键词策略专家。基于解析的意图生成高效搜索关键词。

## 核心规则 (必须严格遵守)

1. **实体名称必须出现在每个关键词中**
   - 如果目标是"红旗大桥垮塌"，每个关键词都必须包含"Hongqi"或"红旗"
   - 绝对禁止生成不含目标实体的泛化关键词

2. **禁止使用 site: OR 链**
   - ❌ 错误: `site:bbc.com OR site:cnn.com Hongqi bridge`
   - ✅ 正确: 每个 site: 约束单独一个关键词组

3. **每个site约束单独一个关键词组**
   - 如需多个媒体，生成多个KeywordGroup，每个只有一个site_constraint

4. **时间要素显式包含**
   - 将时间范围转化为关键词的一部分
   - 例如: "2025-11" → 关键词中包含 "November 2025" 或 "2025年11月"

## 高效查询模板 (按有效率排序)

| 层级 | 模板 | 有效率 | 说明 |
|------|------|-------|------|
| tier1 | `[实体英文名] collapse [地点] China [年月]` | 100% | 最精确 |
| tier2 | `[实体中文名] 垮塌 英文报道 [年月]` | 70% | 中文+英文报道需求 |
| tier3 | `site:[单个媒体域名] [实体英文名] collapse [年月]` | 60% | 限定媒体 |

## 输出格式

生成3-5个KeywordGroup，每组包含:
- keywords: 2-3个具体关键词 (必须包含实体名称)
- layer: 0-5 (0=官方, 5=最宽泛)
- language: zh/en/mixed
- search_type: web/news
- site_constraint: 单个域名或null (禁止OR链)

## 示例

输入:
- investigation_target: "四川阿坝红旗大桥垮塌"
- time_range: "2025-11"
- source_type_constraint: "西方主流媒体"

输出 (JSON数组格式):
- 第1组: keywords=["Hongqi Bridge collapse Sichuan November 2025", "红旗大桥 Sichuan bridge collapse 2025"], layer=1, language="mixed", search_type="news", site_constraint=null
- 第2组: keywords=["红旗大桥 垮塌 英文报道 2025年11月"], layer=5, language="zh", search_type="web", site_constraint=null
- 第3组: keywords=["Hongqi Bridge collapse China November 2025"], layer=2, language="en", search_type="news", site_constraint="bbc.com"
- 第4组: keywords=["Hongqi Bridge collapse China November 2025"], layer=2, language="en", search_type="news", site_constraint="reuters.com"
- 第5组: keywords=["Hongqi Bridge collapse China November 2025"], layer=2, language="en", search_type="news", site_constraint="cnn.com"

## 西方主流媒体域名参考

- 通讯社: reuters.com, apnews.com
- 英国: bbc.com, theguardian.com, telegraph.co.uk
- 美国: cnn.com, nytimes.com, washingtonpost.com, wsj.com
- 法国: france24.com, lemonde.fr
- 德国: dw.com

请根据信息源约束选择合适的媒体。"""

KEYWORD_GEN_PROMPT_V2 = ChatPromptTemplate.from_messages(
    [
        ("system", KEYWORD_GEN_SYSTEM_V2),
        (
            "human",
            """## 意图信息

- 调查对象: {investigation_target}
- 时间范围: {time_range}
- 信息源约束: {source_type_constraint}
- 调查类型: {investigation_type}
- 工具限制: {tool_constraint}

请生成高效搜索关键词组。严格遵守核心规则，确保每个关键词都包含实体名称。""",
        ),
    ]
)


# ===== 4步相关性验证 Prompt =====
RELEVANCE_VALIDATE_SYSTEM = """你是一个专业的OSINT内容相关性验证专家。使用4步判断法验证搜索结果的相关性。

4步判断流程:

Step 1: 回顾原始意图
- 确认调查对象
- 明确时间范围要求
- 了解信息源要求

Step 2: 核心要素匹配检查
检查以下要素是否匹配:
- 地点匹配: 内容涉及的地理位置是否相关
- 事件匹配: 内容描述的事件是否相关
- 时间匹配: 内容的时间是否在要求范围内
- 来源匹配: 内容来源是否符合要求

Step 3: 偏离判定
根据匹配程度做出判定:
- keep: 核心要素全部匹配，直接相关
- downgrade: 部分匹配，可作为背景信息
- discard: 完全不相关或时间/来源不符

Step 4: 输出结果
- 给出判定结果
- 说明判定理由
- 列出匹配的要素

输出要求:
对每条内容返回:
- url: 内容URL
- title: 内容标题
- relevance: keep/downgrade/discard
- reason: 判定理由
- matched_elements: 匹配的要素列表
- confidence: 判定置信度 (0.0-1.0)"""

RELEVANCE_VALIDATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", RELEVANCE_VALIDATE_SYSTEM),
        (
            "human",
            """原始意图:
调查对象: {investigation_target}
时间范围: {time_range}
信息源约束: {source_type_constraint}
调查类型: {investigation_type}

待验证内容列表:
{contents}

请对每条内容进行相关性验证。""",
        ),
    ]
)


# ===== 来源分类 Prompt =====
CLASSIFY_SOURCE_SYSTEM = """你是一个专业的OSINT来源分类和可信度评估专家。你的任务是对搜索结果进行来源分类和可信度评估。

来源分类体系:

1. official (官方)
- 政府机构、官方媒体、国际组织
- 高可信度 (0.85-1.0)
- 示例: .gov, .un.org, 官方发言人

2. local_mainstream (本地主流媒体)
- 当地知名媒体、主流报社
- 中高可信度 (0.7-0.85)
- 示例: 人民日报、新华网、当地主要报纸

3. intl_mainstream (国际主流媒体)
- 国际知名媒体机构
- 中高可信度 (0.7-0.85)
- 示例: BBC, CNN, Reuters, AP

4. think_tank (智库/学术)
- 研究机构、大学、智库报告
- 中高可信度 (0.7-0.9)
- 示例: .edu, 布鲁金斯学会, 兰德公司

5. other (其他)
- 博客、社交媒体、未知来源
- 低可信度 (0.3-0.6)

时间置信度评估:

- HIGH: 内容有明确的发布日期，且在时间范围内
- MEDIUM: 可从上下文推断时间，大致符合
- LOW: 时间不确定，但可能相关
- REJECTED: 明确超出时间范围

输出要求:
对每条内容返回:
- url, title: 基本信息
- category: 来源分类
- credibility_score: 可信度评分 (0.0-1.0)
- time_confidence: 时间置信度
- content_summary: 100字以内的内容摘要
- relevance_status: keep/downgrade (继承自验证阶段)
- source_domain: 来源域名
- published_date: 发布日期 (如可提取)"""

CLASSIFY_SOURCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", CLASSIFY_SOURCE_SYSTEM),
        (
            "human",
            """时间范围要求: {time_range}
信息源约束: {source_type_constraint}

待分类内容列表:
{contents}

请对每条内容进行来源分类和可信度评估。""",
        ),
    ]
)


# ===== 扩展搜索关键词生成 Prompt =====
EXPAND_KEYWORDS_SYSTEM = """你是一个OSINT搜索扩展专家。当初始搜索结果不足时，你需要生成更宽泛的关键词来扩大搜索范围。

扩展策略:

1. 放宽地域限制
- 从具体地点扩展到更大区域
- 添加相关地区的关键词

2. 放宽时间限制
- 如果时间过于具体，考虑扩展时间范围
- 添加"近期"、"最新"等时间词

3. 使用同义词和相关词
- 替换专业术语为通用词
- 添加事件的其他描述方式

4. 降低来源限制
- 从官方来源扩展到主流媒体
- 从主流媒体扩展到一般来源

5. 使用Layer 5关键词
- 背景资料、历史信息
- 百科性质的搜索"""

EXPAND_KEYWORDS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", EXPAND_KEYWORDS_SYSTEM),
        (
            "human",
            """调查对象: {investigation_target}
当前迭代次数: {iteration_count}
已使用的关键词: {used_keywords}

请生成扩展搜索关键词。""",
        ),
    ]
)


# ============================================================================
# 兼容旧API的 Prompt 模板
# ============================================================================

# ===== 意图解析 Prompt (旧版) =====
PARSE_INTENT_SYSTEM = """你是一个专业的搜索意图分析专家。你的任务是从用户的自然语言查询中提取关键信息。

请分析用户查询并提取以下信息:
1. entities: 识别查询中的核心实体(人物、组织、事件、产品等)
2. time_range: 如果查询涉及时间范围，提取时间约束
   - h: 最近一小时
   - d: 最近一天
   - w: 最近一周
   - m: 最近一个月
   - y: 最近一年
   - null: 无时间限制
3. search_sources: 推荐的搜索来源
   - web: 网页搜索(默认)
   - news: 新闻搜索(适用于时事、事件)
   - images: 图片搜索(适用于视觉相关)
4. language: 目标语言(zh/en)
5. intent_type: 意图类型
   - search: 简单信息搜索
   - research: 深度研究调查
   - monitor: 持续监控

请用JSON格式返回分析结果。"""

PARSE_INTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", PARSE_INTENT_SYSTEM),
        ("human", "用户查询: {query}"),
    ]
)


# ===== 关键词生成 Prompt (旧版) =====
GENERATE_KEYWORDS_SYSTEM = """你是一个专业的搜索关键词生成专家。你的任务是基于用户意图生成有效的搜索关键词。

关键词生成策略:
1. 核心关键词: 直接使用用户查询中的核心实体
2. 同义词扩展: 添加同义词或相关术语
3. 语言变体: 如果适用，生成中英文版本
4. 长尾关键词: 添加限定词使搜索更精确
5. 时间限定: 如有时间约束，添加时间相关词汇

要求:
- 生成3-10个关键词
- 按相关性排序(最相关的在前)
- 确保关键词多样性
- 避免重复或过于相似的关键词"""

GENERATE_KEYWORDS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", GENERATE_KEYWORDS_SYSTEM),
        (
            "human",
            """原始查询: {query}

解析后的意图:
{intent}

请生成搜索关键词列表。""",
        ),
    ]
)


# ===== 结果摘要 Prompt =====
SUMMARIZE_RESULTS_SYSTEM = """你是一个专业的信息摘要专家。你的任务是基于搜索结果生成简洁、准确的摘要。

摘要要求:
1. 抓住核心信息和关键事实
2. 保持客观中立，不添加个人观点
3. 如有多个来源，综合不同观点
4. 标注信息来源(如有)
5. 控制在200-500字

输出格式:
1. 核心摘要(1-2段)
2. 关键发现(要点列表)
3. 来源概述"""

SUMMARIZE_RESULTS_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SUMMARIZE_RESULTS_SYSTEM),
        (
            "human",
            """原始查询: {query}

搜索结果内容:
{contents}

请生成摘要。""",
        ),
    ]
)


# ===== 内容清洗 Prompt =====
CLEAN_CONTENT_SYSTEM = """你是一个内容清洗专家。你的任务是从原始网页内容中提取核心信息。

清洗规则:
1. 移除广告、导航、页脚等非核心内容
2. 保留正文、标题、关键数据
3. 保持原有结构和格式
4. 移除冗余的空白和格式符号
5. 如有代码或数据，保持原格式"""

CLEAN_CONTENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", CLEAN_CONTENT_SYSTEM),
        (
            "human",
            """原始内容:
{content}

请清洗并提取核心信息。""",
        ),
    ]
)


# ============================================================================
# 导出所有 Prompt 模板
# ============================================================================

__all__ = [
    # OSINT核心模板
    "INTENT_PARSE_PROMPT",
    "KEYWORD_GEN_PROMPT",
    "KEYWORD_GEN_PROMPT_V2",  # V2高效关键词生成
    "RELEVANCE_VALIDATE_PROMPT",
    "CLASSIFY_SOURCE_PROMPT",
    "EXPAND_KEYWORDS_PROMPT",
    # 兼容旧API
    "PARSE_INTENT_PROMPT",
    "GENERATE_KEYWORDS_PROMPT",
    "SUMMARIZE_RESULTS_PROMPT",
    "CLEAN_CONTENT_PROMPT",
]
