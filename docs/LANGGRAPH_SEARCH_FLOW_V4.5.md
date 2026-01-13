# LangGraph 分层搜索流程文档 v4.5

> 版本: v4.5.1
> 日期: 2025-01-13
> 作者: Claude Code

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LangGraph 搜索系统                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │   API 层    │───▶│  Service    │───▶│   LangGraph StateGraph  │  │
│  │  (FastAPI)  │    │   层        │    │   (graph.py)            │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘  │
│                                                  │                   │
│                                                  ▼                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      搜索节点 (nodes/)                         │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│  │  │QueryAnalyzer │─▶│SourceDiscover│─▶│  LayerSearch (x5)   │ │  │
│  │  │   (Claude)   │  │   (Claude)   │  │   (Firecrawl)       │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘ │  │
│  │                                                  │              │  │
│  │                                                  ▼              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│  │  │   Output     │◀─│  Validator   │◀─│   Aggregator        │ │  │
│  │  │              │  │              │  │  + ResultFilter      │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. 完整执行流程

### 2.1 流程图

```
START
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. QueryAnalyzerNode                                            │
│    - 调用 Claude 分析用户查询                                      │
│    - 识别当事方 (parties)                                         │
│    - 生成关键词 (keywords, keywords_en)                           │
│    - 生成 4 层组合法查询 (keyword_combinations)                    │
│    - 判断时间范围和目标语言                                         │
│    输出: analysis, keywords, target_languages, layer_search_config│
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. SourceDiscoveryNode                                          │
│    - 调用 Claude 发现官方来源                                      │
│    - 根据当事方识别政府网站、官方机构、主流媒体                        │
│    输出: discovered_sources                                      │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼ (并行分发到 5 个层级)
┌─────────────────────────────────────────────────────────────────┐
│ 3. LayerSearchNode (x5) - 并行执行                               │
│    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│    │Layer 0  │ │Layer 1  │ │Layer 2  │ │Layer 3  │ │Layer 4  │  │
│    │官方来源 │ │主流媒体 │ │周边地区 │ │国际权威 │ │智库分析 │  │
│    └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│                                                                  │
│    每层执行:                                                     │
│    - 使用 keyword_combinations 构建优化查询                       │
│    - 无域名通用查询 + site: 精确查询                               │
│    - 调用 Firecrawl API (limit=10, sources=[news,web])           │
│    输出: layer_results                                           │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼ (等待所有层级完成)
┌─────────────────────────────────────────────────────────────────┐
│ 4. AggregatorNode                                               │
│    - 合并所有层级结果                                             │
│    - URL 去重 (基于 content_hash)                                │
│    - 按分数排序                                                  │
│    输出: aggregated_results                                      │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. ResultFilter (v4.5.1 新增)                                   │
│    - 黑名单域名过滤 (社交媒体、论坛、视频平台等)                     │
│    - 白名单域名加权 (官方媒体、智库 +10%~30%)                       │
│    - 中文内容优先排序                                             │
│    - 空内容过滤                                                  │
│    输出: filtered aggregated_results                             │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. ValidatorNode                                                │
│    - 多源验证 (相同事实被多来源报道 → +分)                         │
│    - 权威验证 (官方来源确认 → +分)                                │
│    - 内容长度验证                                                │
│    输出: validation_scores, updated aggregated_results           │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. OutputNode                                                   │
│    - 格式化最终结果                                               │
│    - 生成统计信息                                                │
│    输出: final_results, statistics                               │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
 END
```

## 3. 关键配置

### 3.1 超时配置 (config.py)

```python
@dataclass
class LangGraphSearchConfig:
    # API 超时
    firecrawl_timeout: int = 60      # Firecrawl 单次请求超时
    claude_timeout: int = 60         # Claude API 超时

    # 整体搜索超时
    search_timeout: int = 300        # 5分钟 - 整个搜索流程超时

    # 每层搜索
    results_per_query: int = 10      # 每个查询返回结果数
    max_domains_per_layer: int = 10  # 每层最多域名数
```

### 3.2 环境变量

```bash
# Claude API
ANTHROPIC_API_KEY=xxx
ANTHROPIC_AUTH_TOKEN=xxx

# Firecrawl API
FIRECRAWL_API_KEY=xxx

# 超时配置
SEARCH_TIMEOUT=300                   # 搜索超时（秒）

# 功能开关
SMART_SEARCH_USE_UNIFIED_ANALYZER=true
SMART_SEARCH_USE_CLAUDE=true
SMART_SEARCH_ENABLE_MULTILANG=true
```

## 4. 核心组件详解

### 4.1 QueryAnalyzerNode (v4.5.0)

**位置**: `src/services/langgraph_search/nodes/query_analyzer.py`

**主要功能**:
- 使用 Claude 分析用户查询
- 生成 4 层组合法关键词 (keyword_combinations)
- 识别目标语言和时间范围

**Prompt 核心要点** (v4.5.0 4层组合法):
```
keyword_combinations 生成规则:
1. layer_0_1: 中文关键词 (官方来源+主流媒体)
2. layer_2: 周边地区语言关键词 (日/韩)
3. layer_3: 英文关键词 (国际权威)
4. layer_4: 英文学术关键词 (智库)

每层只生成 2-3 个核心关键词，避免过度限制。
```

### 4.2 LayerSearchNode (v4.5.0)

**位置**: `src/services/langgraph_search/nodes/layer_search.py`

**优化策略**:
1. **无域名通用查询** - 先执行不限制域名的查询，发现更多来源
2. **精简关键词** - site: 查询只使用前 2 个核心词
3. **参数优化**:
   - `limit=10` (每次最多 10 条)
   - `sources=["news", "web"]` (同时搜索新闻和网页)

**查询构建示例**:
```python
# 对于 keyword_combination: "四川阿坝 地震 最新"
queries = [
    "四川阿坝 地震 最新",           # 通用查询
    "site:gov.cn 四川 地震",        # 官方来源 (只用2个核心词)
    "site:xinhuanet.com 四川 地震", # 主流媒体
]
```

### 4.3 ResultFilter (v4.5.1 新增)

**位置**: `src/services/langgraph_search/nodes/result_filter.py`

**过滤策略**:

| 过滤类型 | 说明 |
|---------|------|
| 黑名单 | facebook, twitter, youtube, wikipedia 等 |
| 白名单加权 | xinhuanet +30%, reuters +25%, nytimes +20% |
| 中文优先 | 目标语言含 zh 时，中文内容排前 70% |
| 空内容过滤 | markdown_content < 50 字符 |

### 4.4 ValidatorNode (v4.5.1 修复)

**位置**: `src/services/langgraph_search/nodes/validator.py`

**修复内容**:
- 修复 `title` 可能为 None 导致的 NoneType 错误
- 修复 `url` 为空时的处理
- 修复 `source_tier` 为 None 时的默认值

## 5. 问题诊断

### 5.1 常见超时原因

| 阶段 | 可能原因 | 解决方案 |
|-----|---------|---------|
| QueryAnalyzer | Claude API 响应慢 | 检查 API 连接，增加超时 |
| SourceDiscovery | Claude API 响应慢 | 同上 |
| LayerSearch | Firecrawl API 慢/查询过多 | 减少 max_queries，检查 API |
| Aggregator | 结果数量巨大 | 提前过滤，限制每层结果数 |
| Validator | 结果数量巨大 | 限制验证数量 |

### 5.2 日志关键字

```bash
# 查看搜索超时
grep "timeout" logs/app.log

# 查看 Firecrawl 请求
grep "FIRECRAWL" logs/app.log

# 查看 Claude 调用
grep "Claude" logs/app.log

# 查看层级搜索
grep "Layer.*complete" logs/app.log
```

### 5.3 性能优化建议

1. **减少 Claude 调用**
   - QueryAnalyzer 和 SourceDiscovery 可以合并
   - 缓存重复查询

2. **减少 Firecrawl 调用**
   - 降低 `max_queries`
   - 减少每层域名数

3. **提前过滤**
   - 在 LayerSearch 阶段就应用黑名单
   - 限制每层返回结果数

## 6. 目录结构

```
src/services/langgraph_search/
├── __init__.py
├── config.py              # 配置类
├── state.py               # SearchState 定义
├── graph.py               # StateGraph 构建
├── service.py             # LangGraphSearchService
├── languages.py           # 多语言支持
│
├── nodes/
│   ├── __init__.py
│   ├── query_analyzer.py  # 查询分析 (Claude)
│   ├── source_discovery.py # 来源发现 (Claude)
│   ├── layer_search.py    # 分层搜索 (Firecrawl)
│   ├── aggregator.py      # 结果聚合
│   ├── result_filter.py   # 结果过滤 (v4.5.1)
│   ├── validator.py       # 交叉验证
│   ├── quality_gate.py    # 质量门控
│   └── output.py          # 输出格式化
│
├── converters/
│   ├── result_converter.py
│   └── aggregated_converter.py
│
└── utils/
    ├── url_utils.py
    └── thread_id.py
```

## 7. 版本历史

| 版本 | 日期 | 主要更新 |
|-----|------|---------|
| v4.5.1 | 2025-01-13 | 新增 ResultFilter, 修复 Validator NoneType 错误 |
| v4.5.0 | 2025-01-12 | 4层组合法 Prompt, 无域名通用查询, 精简关键词 |
| v4.4.0 | 2025-01-11 | layer_search_config 分层配置 |
| v4.3.x | 2025-01-10 | 多语言支持增强 |
| v3.7.x | 2025-01-08 | 质量门控 QualityGate |

---

## 附录: 搜索状态 (SearchState) 关键字段

```python
class SearchState(TypedDict, total=False):
    # 用户
    user_id: str
    query: str

    # 分析结果
    analysis: Dict                    # Claude 分析结果
    keywords: List[str]               # 中文关键词
    keywords_en: List[str]            # 英文关键词
    target_languages: List[str]       # ["zh", "en", "ja"]
    layer_search_config: Dict         # 每层语言/关键词配置

    # 来源发现
    discovered_sources: Dict          # 官方/媒体域名

    # 搜索结果
    layer_results: Dict[int, Dict]    # 层级 → 结果
    aggregated_results: List[Dict]    # 聚合后结果
    validation_scores: Dict           # URL → 验证分数
    final_results: List[Dict]         # 最终结果

    # 状态
    status: str                       # pending|running|completed|failed
    error_message: Optional[str]
```
