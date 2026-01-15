# Brief Agent 配置 - 查询分析与关键词分解

## 核心原则

### 区分两类信息

用户查询包含两种不同类型的信息：

| 类型 | 说明 | 示例 | 是否作为搜索关键词 |
|------|------|------|----------------|
| **用户意图** | 用户想要如何搜索 | "检索"、"整理"、"西方主流媒体" | ❌ 否 |
| **事件内容** | 实际要搜索什么 | "四川阿坝"、"红旗大桥"、"垮塌" | ✅ 是 |

### 关键词提取规则

**规则1：媒体类型词必须过滤**
- "西方媒体"、"西方主流媒体"、"欧美媒体"
- "国际媒体"、"海外媒体"
- "当地媒体"、"国内媒体"、"中国媒体"
- "western media"、"international media"

**规则2：意图动词必须过滤**
- "报道"、"反应"、"整理"、"检索"、"搜索"、"查找"
- "collect"、"search"、"find"
- "coverage"、"reaction"、"response"

**规则3：事件内容必须保留**
- 地点：如"四川阿坝"、"红旗"、"大桥"
- 事件：如"垮塌"、"倒塌"
- 时间：如"2025年11月11日"、"11月11日"
- 实体名：如"Hongqi"、"Sichuan"、"Aba"

---

## 四层搜索配置模板

### Layer 0: 官方来源层

目标：搜索事件当事方的官方声明和官方网站

```json
{
  "layer_id": 0,
  "layer_name": "官方来源",
  "layer_type": "official",
  "priority": 1,
  "search_strategy": {
    "language": "zh",  // 优先中文，中文可能包含更多本地信息
    "keywords": ["四川阿坝", "红旗大桥", "垮塌", "事故", "通报", "最新消息"],
    "keywords_en": ["Sichuan", "Aba", "Hongqi", "Bridge", "collapse", "incident", "accident"],
    "domains": [
      "aba.gov.cn",  // 阿坝州政府官网
      "sc.gov.cn",   // 四川省应急厅
      "xinhuanet.com"  // 新华社
    ],
    "query_templates": [
      "site:aba.gov.cn {keywords}",
      "site:sc.gov.cn 红旗大桥 垮塌 2025",
      "site:xinhuanet.com 四川阿坝 红旗大桥 垮塌"
    ]
  }
}
```

### Layer 1: 主流媒体层

目标：搜索中国国内主流媒体的报道

```json
{
  "layer_id": 1,
  "layer_name": "主流媒体",
  "layer_type": "mainstream",
  "priority": 2,
  "search_strategy": {
    "language": "zh",
    "keywords": ["四川阿坝", "红旗大桥", "垮塌", "救援", "伤亡", "原因"],
    "keywords_en": ["Sichuan", "Aba", "Hongqi", "Bridge", "collapse", "rescue", "casualties", "cause"],
    "domains": [
      "news.sina.com.cn",
      "news.163.com",
      "people.com.cn",
      "cctv.com",
      "thepaper.cn"
    ],
    "query_templates": [
      "site:news.sina.com.cn 四川阿坝 红旗大桥 垮塌",
      "site:people.com.cn 红旗大桥 事故"
    ]
  }
}
```

### Layer 2: 西方主流媒体层（用户核心需求）

目标：搜索西方主流媒体的报道和反应

```json
{
  "layer_id": 2,
  "layer_name": "西方主流媒体",
  "layer_type": "western_media",
  "priority": 1,
  "search_strategy": {
    "language": "en",  // 西方媒体主要使用英语
    "keywords": ["四川", "阿坝", "红旗大桥", "垮塌", "Bridge"],
    "keywords_en": ["Sichuan", "Aba", "Hongqi", "Bridge", "collapse", "China bridge accident"],
    "domains": [
      "reuters.com",        // 路透社
      "bbc.com",           // BBC
      "apnews.com",        // 美联社
      "cnn.com",           // CNN
      "nytimes.com",       // 纽约时报
      "theguardian.com",   // 卫报
      "aljazeera.com"      // 半岛台
    ],
    "query_templates": [
      "site:reuters.com China bridge collapse Sichuan 2025",
      "site:bbc.com Hongqi Bridge collapse China",
      "site:apnews.com Sichuan Aba bridge accident"
    ]
  }
}
```

### Layer 3: 国际权威媒体层

目标：搜索国际权威通讯社和专业媒体

```json
{
  "layer_id": 3,
  "layer_name": "国际权威媒体",
  "layer_type": "international_authority",
  "priority": 2,
  "search_strategy": {
    "language": "en",
    "keywords": ["国际", "反应", "中国", "四川"],
    "keywords_en": ["international", "reaction", "response", "China", "Sichuan", "Aba"],
    "domains": [
      "france24.com",
      "dw.com",           // 德国之声
      "rferl.org"        // 自由欧洲电台
      "scmp.com"         // 南华早报
      "straitstimes.com"  // 海峡时报
    ],
    "query_templates": [
      "China bridge collapse international response 2025"
    ]
  }
}
```

### Layer 4: 深度分析与补充层

目标：专业分析报告和背景资料

```json
{
  "layer_id": 4,
  "layer_name": "深度分析",
  "layer_type": "deep_analysis",
  "priority": 3,
  "search_strategy": {
    "language": "en",
    "keywords": ["基础设施", "桥梁", "工程", "安全", "调查"],
    "keywords_en": ["infrastructure", "bridge", "engineering", "safety", "investigation", "China infrastructure"],
    "domains": [
      "crisisgroup.org",
      "brookings.edu",
      "csis.org",
      "asiafoundation.org"
    ],
    "query_templates": [
      "China infrastructure bridge safety investigation"
    ]
  }
}
```

---

## 提示词模板

### 核心提示词

```
你是一个查询分析专家，负责将用户的搜索请求分解为结构化的四层搜索配置。

## 任务

解析用户查询，区分以下两类信息：

1. **用户意图词** - 决定"如何搜索"和"搜索哪些媒体"，但**不作为搜索关键词**
   - 意图动词："检索"、"搜索"、"整理"、"收集"
   - 媒体类型词："西方主流媒体"、"国际媒体"、"当地媒体"、"报道"、"反应"

2. **事件内容词** - 实际要搜索的内容
   - 地点/实体名：如"四川阿坝"、"红旗大桥"
   - 事件类型：如"垮塌"、"倒塌"、"事故"
   - 时间信息：如"2025年11月11日"

## 输出格式

返回包含四层搜索配置的 JSON 对象，每层包含：
- layer_id: 层级 ID (0-4)
- layer_name: 层级名称
- layer_type: 层级类型
- priority: 优先级 (1=最高, 5=最低)
- search_strategy: 搜索策略
  - language: 搜索语言
  - keywords: 中文关键词列表
  - keywords_en: 英文关键词列表
  - domains: 搜索域名列表
  - query_templates: 查询模板列表

## 关键词提取规则

1. **必须过滤的用户意图词**（不作为搜索关键词）：
   - 媒体类型：西方媒体、西方主流媒体、欧美媒体、国际媒体、海外媒体
   - 意图动词：报道、反应、整理、检索、搜索、查找、收集
   - 英文对应：western media, report, reaction, search, find, collect

2. **必须保留的事件内容词**：
   - 地点：四川、阿坝、红旗
   - 事件：大桥、垮塌、倒塌、事故
   - 时间：2025年、11月11日
   - 英文：Sichuan, Aba, Hongqi, Bridge, collapse

3. **处理组合词**：
   - 如果关键词同时包含"报道"和"红旗大桥"，只保留"红旗大桥"
   - 如果关键词是"西方媒体"单独出现，完全过滤
   - 如果是"四川阿坝红旗大桥"这样的组合，保留整体

## 示例分析

用户输入："请检索整理西方主流媒体对2025年11月11日四川阿坝红旗大桥垮塌的报道和反应"

分解结果：
- 用户意图（不作为搜索关键词）：检索、整理、西方主流媒体、报道、反应
- 事件内容（作为搜索关键词）：四川阿坝、红旗大桥、垮塌、2025年11月11日
```

---

## 查询测试用例

### 测试用例 1：典型的用户查询

```
输入: "请检索整理西方主流媒体对2025年11月11日四川阿坝红旗大桥垮塌的报道和反应"

期望输出:
- keywords: ["四川阿坝", "红旗大桥", "垮塌"]
- keywords_en: ["Sichuan", "Aba", "Hongqi", "Bridge", "collapse"]
- intent_filtered: ["检索", "整理", "西方主流媒体", "报道", "反应"]

错误的输出:
- keywords: ["西方媒体", "报道", "四川阿坝", "红旗大桥", "垮塌"]  // 错误！包含意图词
```

### 测试用例 2：只有事件内容

```
输入: "2025年11月11日四川阿坝红旗大桥垮塌事故"

期望输出:
- keywords: ["四川阿坝", "红旗大桥", "垮塌", "事故"]
- keywords_en: ["Sichuan", "Aba", "Hongqi", "Bridge", "collapse", "incident"]
- intent_filtered: []
```

### 测试用例 3：复杂组合

```
输入: "收集整理海外媒体关于台海地震的最新报道和各方反应"

期望输出:
- keywords: ["台海", "地震", "最新"]
- keywords_en: ["Taiwan", "earthquake", "latest"]
- intent_filtered: ["收集", "整理", "海外媒体", "报道", "反应"]
```

---

## 集成说明

此配置文件可用于：

1. **LangGraph QueryAnalyzer**: 作为提示词参考
2. **Brief Agent**: 直接调用 LLM 生成搜索计划
3. **搜索调度**: 根据四层配置分配搜索任务

### 集成到 LangGraph 的方式

在 `src/services/langgraph_search/nodes/query_analyzer.py` 的 `QUERY_ANALYSIS_PROMPT` 中引用此配置：
- 添加用户意图词列表作为全局常量
- 在提示词中明确区分规则
- 要求 LLM 按四层结构输出 `keyword_combinations`
