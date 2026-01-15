# 搜索系统升级需求文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.1.0 |
| 创建日期 | 2025-01-08 |
| 参考项目 | Tool_for_osint (OSINT Agent 系统) |
| 当前版�� | v2.11.0 |
| 目标版本 | v3.0.0 |

---

## 1. 项目背景

### 1.1 问题陈述

当前系统使用 Firecrawl API 进行搜索，但存在以下问题：

1. **搜索策略单一**：所有查询使用相同的搜索模式，无差异化策略
2. **源发现静态化**：依赖预定义的域名分类表，无法动态适应新事件
3. **site: 搜索未充分利用**：未针对官方来源使用 site: 搜索语法
4. **缺少分层排序**：所有搜索结果混合排序，无法体现来源层级

### 1.2 参考项目分析

**Tool_for_osint** 项目的核心优势：

- **动态源发现**：根据事件当事方动态识别官方来源
- **分层搜索策略**：5层搜索架构（官方→主流→周边→国际→智库）
- **site: 搜索**：针对官方来源使用 site: 语法精确搜索
- **交叉验证机制**：本地语言+英语双重验证

---

## 2. 需求分析

### 2.1 功能需求

#### FR-1: 动态源发现

**需求描述**：根据查询内容自动识别当事方及其官方信息来源。

| 优先级 | P0 (必须) |
|--------|----------|
| 识别内容 | 国家/地区、政府机构、官方媒体、通讯社 |
| 发现方式 | Claude LLM 分析 + Firecrawl 验证 |
| 输出格式 | 结构化域名列表 |

**验收标准**：
- [ ] 能够识别至少 10 个主要国家/地区的官方来源
- [ ] 发现的官方域名准确率 ≥ 85%
- [ ] 支持中英文混合查询
- [ ] 源发现耗时 ≤ 10 秒

#### FR-2: 分层搜索策略

**需求描述**：按照来源层级实施差异化搜索策略。

| 优先级 | P0 (必须) |
|--------|----------|
| 分层方式 | 5 层架构 (参考 OSINT) |
| 每层策略 | 不同的搜索参数和结果数量要求 |

**分层定义**：

```
Layer 0: 当事方官方来源 [必须搜索，site: 搜索]
├── 官方政府网站 (site:gov, site:gov.cn, etc.)
├── 官方通讯社 (site:reuters.com, etc.)
└── 官方发言人平台

Layer 1: 当事方主流媒体 [必须搜索，site: 搜索]
├── 当地主流报纸
├── 当地主流电视媒体
└── 当地主流网络媒体

Layer 2: 周边地区/相关国家 [重点搜索，语言优先]
├── 地理位置周边国家
├── 政治/经济相关国家
└── 使用当地语言搜索

Layer 3: 国际权威媒体 [标准搜索，英语为主]
├── 路透社、美联社、法新社
├── CNN、BBC、NYT
└── 其他国际主流媒体

Layer 4: 智库与专业分析 [补充搜索，专业来源]
├── 国际智库 (CSIS, RAND, etc.)
├── 学术研究机构
└── 专业分析平台

Layer 5: 百科类 [仅理解补充，不作引用]
├── Wikipedia
└── 其他百科网站
```

**验收标准**：
- [ ] Layer 0-1 结果优先展示
- [ ] 每层结果有明确的 tier 标记
- [ ] 支持 site: 搜索语法
- [ ] Layer 5 结果单独分组，不参与主要排名

#### FR-3: Site: 搜索优化

**需求描述**：针对官方来源使用 site: 语法进行精确搜索。

| 优先级 | P0 (必须) |
|--------|----------|
| 语法支持 | site:domain.com keyword |
| 批量支持 | 同一查询支持多个 domain |
| 语言适配 | 根据域名自动选择搜索语言 |

**site: 搜索示例**：

```python
# Layer 0: 官方来源 site: 搜索
queries = [
    "site:whitehouse.gov 某某事件",     # 美国官方
    "site:reuters.com 某某事件",        # 国际通讯社
    "site:kyodo.co.jp 某某事件",        # 日本通讯社
]

# Layer 1: 主流媒体 site: 搜索
queries = [
    "site:nytimes.com 某某事件",        # 美国主流
    "site:asahi.com 某某事件",          # 日本主流
]
```

**验收标准**：
- [ ] site: 搜索语法正确实现
- [ ] 多个 domain 的搜索结果正确聚合
- [ ] site: 搜索结果与非 site: 结果区分标记

#### FR-4: 精确时间过滤

**需求描述**：支持精确的时间过滤功能。

| 优先级 | P1 (重要) |
|--------|----------|
| 时间粒度 | hour / day / week / month / year |
| 实现方式 | Firecrawl time_range 参数 |
| 兼容性 | 与 site: 搜索兼容 |

**时间参数映射**：

| 用户输入 | Firecrawl 参数 | 说明 |
|----------|----------------|------|
| 过去 1 小时 | time_range="1h" | 最近 1 小时 |
| 过去 24 小时 | time_range="1d" | 最近 1 天 |
| 过去 7 天 | time_range="1w" | 最近 1 周 |
| 过去 30 天 | time_range="1m" | 最近 1 月 |
| 过去 365 天 | time_range="1y" | 最近 1 年 |

**验收标准**：
- [ ] 支持至少 5 种时间粒度
- [ ] 时间过滤与 site: 搜索兼容
- [ ] 时间过滤不影响其他搜索条件

#### FR-5: 多语言交叉验证

**需求描述**：使用本地语言和英语进行交叉验证，提升信息准确性。

| 优先级 | P1 (重要) |
|--------|----------|
| 验证方式 | 同一事件的多语言报道对比 |
| 一致性检测 | Claude LLM 分析内容相似度 |

**验收标准**：
- [ ] 支持至少 5 种语言（中、英、日、韩、阿拉伯）
- [ ] 交叉验证结果标注一致性得分
- [ ] 一致性低的结果自动降权

---

## 3. 技术方案

### 3.1 架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           搜索服务层                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐   ┌───────────────┐   ┌─────────────────────────┐    │
│  │ SmartSearch  │   │ SourceDiscovery│   │  LayeredSearchStrategy │    │
│  │   Service    │→  │    Service     │→  │       (5 Layers)       │    │
│  └──────┬───────┘   └───────┬───────┘   └──────────┬──────────────┘    │
│         │                   │                       │                   │
│         └───────────────────┴───────────────────────┘                   │
│                             ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Enhanced Search Strategy                    │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │  Layer 0-1: Site Search (官方来源 + 主流媒体)           │  │   │
│  │  │    site:whitehouse.gov, site:reuters.com, etc.          │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │  Layer 2-3: Local Language + International (周边+国际)   │  │   │
│  │  │    本地语言搜索 + 英语搜索                               │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │  Layer 4: Think Tanks (智库专业分析)                     │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                             ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Firecrawl API                                 │   │
│  │  • Site: 搜索支持                                               │   │
│  │  • 多语言搜索                                                   │   │
│  │  • 时间过滤                                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                             ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   ResultAggregator                              │   │
│  │  • 去重 (URL + content_hash)                                   │   │
│  │  • 聚合 (来源合并)                                              │   │
│  │  • 评分 (综合可信度)                                            │   │
│  │  • 排序 (分层优先 + 时间相关)                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据模型

#### 3.2.1 发现的源信息

```python
@dataclass
class DiscoveredSource:
    """动态发现的源信息"""
    party_name: str          # 当事方名称 (如: "美国", "日本", "中国")
    party_type: str          # country | organization | person
    party_code: str          # ISO 国家代码 (如: "US", "JP", "CN")

    # 官方来源 (Layer 0)
    official_gov: List[str]  # 官方政府网站域名
    # ["whitehouse.gov", "state.gov", "mofa.go.jp"]

    official_agency: List[str]  # 官方通讯社域名
    # ["reuters.com", "apnews.com", "kyodo.co.jp"]

    # 主流媒体 (Layer 1)
    local_mainstream: List[str]  # 当地主流媒体域名
    # ["nytimes.com", "washingtonpost.com", "asahi.com"]

    # 搜索语言
    primary_language: str    # 主要语言代码

    # 元数据
    discovery_time: datetime
    confidence: float        # 置信度 0-1
```

#### 3.2.2 分层搜索配置

```python
@dataclass
class LayerSearchConfig:
    """分层搜索配置"""
    layer: int               # 层级 0-5
    name: str                # 层级名称
    priority: str            # must | focus | standard | supplement
    search_type: str         # site | general | specialized
    max_results: int         # 最大结果数
    target_domains: List[str] # 目标域名列表
    languages: List[str]     # 目标语言列表
```

#### 3.2.3 分层搜索结果

```python
@dataclass
class LayeredSearchResult:
    """分层搜索结果"""
    layer: int               # 层级 0-5
    layer_name: str          # 层级名称
    source_type: str         # 来源类型
    query: str               # 使用的查询

    # 结果
    results: List[SearchResult]
    total_count: int
    fetched_count: int

    # 元数据
    execution_time_ms: int
    sources_used: List[str]  # 使用的域名列表
```

### 3.3 接口设计

#### 3.3.1 源发现接口

```python
class SourceDiscoveryService:
    """动态源发现服务"""

    async def discover_official_sources(
        self,
        query: str,
        parties: Optional[List[str]] = None
    ) -> Dict[str, DiscoveredSource]:
        """发现当事方官方来源

        Args:
            query: 原始查询 (如: "美日韩联合军演 2025")
            parties: 预先识别的当事方列表，None 则自动识别

        Returns:
            当事方名称 -> 发现的源信息
            {
                "美国": DiscoveredSource(party_name="美国", ...),
                "日本": DiscoveredSource(party_name="日本", ...)
            }
        """
        pass

    async def _identify_parties(
        self,
        query: str
    ) -> List[str]:
        """从查询中识别当事方"""
        # 使用 Claude 分析查询，提取国家/地区/组织
        pass

    async def _discover_party_sources(
        self,
        party: str
    ) -> DiscoveredSource:
        """发现单个当事方的官方来源"""
        # 1. 构建发现查询
        # 2. 使用 Firecrawl 搜索
        # 3. 使用 Claude 提取域名
        pass
```

#### 3.3.2 分层搜索接口

```python
class LayeredSearchStrategy:
    """分层搜索策略"""

    async def execute_layered_search(
        self,
        query: str,
        parties: List[str],
        discovered_sources: Dict[str, DiscoveredSource],
        options: SearchOptions
    ) -> Dict[int, LayeredSearchResult]:
        """执行分层搜索

        Args:
            query: 原始查询
            parties: 当事方列表
            discovered_sources: 发现的源信息
            options: 搜索选项 (时间范围、语言等)

        Returns:
            层级编号 -> 该层搜索结果
        """
        pass

    def _build_layer_queries(
        self,
        query: str,
        discovered_sources: Dict[str, DiscoveredSource]
    ) -> Dict[int, List[str]]:
        """构建各层搜索查询

        Returns:
            {
                0: ["site:whitehouse.gov 某某事件", "site:reuters.com 某某事件"],
                1: ["site:nytimes.com 某某事件"],
                2: ["(JP) 某某事件", "(KR) 某某事件"],
                3: ["某某事件 international"],
                4: ["某某事件 analysis think tank"]
            }
        """
        pass
```

---

## 4. 实施计划

### 4.1 阶段划分

| 阶段 | 名称 | 优先级 | 预计工期 | 依赖 |
|------|------|--------|----------|------|
| 阶段 1 | 动态源发现服务 | P0 | 2-3 天 | 无 |
| 阶段 2 | 分层搜索策略 | P0 | 2-3 天 | 阶段 1 |
| 阶段 3 | Site: 搜索优化 | P0 | 1-2 天 | 阶段 2 |
| 阶段 4 | 多语言交叉验证 | P1 | 1-2 天 | 阶段 3 |

### 4.2 阶段 1: 动态源发现服务

**目标**：实现基于 Claude + Firecrawl 的源发现服务

**新增文件**：
```
src/services/
└── source_discovery_service.py
```

**修改文件**：
```
src/infrastructure/llm/claude_client.py  # 添加源发现相关方法
src/services/smart_search_service.py     # 集成源发现服务
```

**关键代码**：
```python
# source_discovery_service.py
class SourceDiscoveryService:
    def __init__(self):
        self.claude_client = create_claude_client()
        self.firecrawl = FirecrawlAdapter()

    async def discover_official_sources(
        self,
        query: str,
        parties: Optional[List[str]] = None
    ) -> Dict[str, DiscoveredSource]:
        # 1. 识别当事方 (如果未提供)
        if not parties:
            parties = await self._identify_parties(query)

        # 2. 为每个当事方发现官方来源
        results = {}
        for party in parties:
            party_sources = await self._discover_party_sources(party, query)
            results[party] = party_sources

        return results

    async def _identify_parties(self, query: str) -> List[str]:
        """使用 Claude 识别查询中的当事方"""
        prompt = f"""
        分析以下查询，提取涉及的当事方（国家/地区/组织）：

        查询：{query}

        请返回涉及的当事方列表，格式：["当事方1", "当事方2", ...]
        只返回主要当事方（最多5个）。
        """
        response = await self.claude_client.chat(prompt)
        return self._parse_parties(response)

    async def _discover_party_sources(self, party: str, context: str) -> DiscoveredSource:
        """发现单个当事方的官方来源"""

        # 1. 构建发现查询
        discovery_queries = [
            f"{party} official government website domain",
            f"{party} official news agency domain",
            f"{party} main news media websites"
        ]

        # 2. 使用 Firecrawl 搜索
        search_results = []
        for q in discovery_queries:
            results = await self.firecrawl.search(q, limit=10)
            search_results.extend(results)

        # 3. 使用 Claude 提取和分类域名
        extracted = await self.claude_client.extract_and_classify_domains(
            party=party,
            search_results=search_results
        )

        return DiscoveredSource(
            party_name=party,
            party_type="country",
            party_code=extracted.get("country_code", ""),
            official_gov=extracted.get("official_gov", []),
            official_agency=extracted.get("official_agency", []),
            local_mainstream=extracted.get("local_mainstream", []),
            primary_language=extracted.get("primary_language", "en"),
            discovery_time=datetime.utcnow(),
            confidence=extracted.get("confidence", 0.8)
        )
```

**Claude Client 新增方法**：
```python
# claude_client.py 新增
async def extract_and_classify_domains(
    self,
    party: str,
    search_results: List[Dict]
) -> Dict[str, Any]:
    """提取并分类域名

    Args:
        party: 当事方名称
        search_results: Firecrawl 搜索结果

    Returns:
        {
            "country_code": "US",
            "official_gov": ["whitehouse.gov", "state.gov"],
            "official_agency": ["reuters.com"],
            "local_mainstream": ["nytimes.com"],
            "primary_language": "en",
            "confidence": 0.9
        }
    """
    # 构建搜索结果摘要
    results_text = "\n".join([
        f"- {r.get('title', '')}: {r.get('url', '')}"
        for r in search_results[:20]
    ])

    prompt = f"""
    分析以下关于 {party} 的搜索结果，提取并分类官方域名：

    {results_text}

    请以 JSON 格式返回：
    {{
        "country_code": "ISO代码",
        "official_gov": ["政府网站域名列表"],
        "official_agency": ["官方通讯社域名列表"],
        "local_mainstream": ["当地主流媒体域名列表"],
        "primary_language": "主要语言代码",
        "confidence": 0.9
    }}
    """

    response = await self._message_create(prompt)
    return self._parse_json_response(response)
```

### 4.3 阶段 2: 分层搜索策略

**目标**：实现 5 层搜索架构

**新增文件**：
```
src/services/
└── layered_search_strategy.py
```

**修改文件**：
```
src/services/smart_search_service.py
src/core/domain/entities/search_config.py
```

**关键代码**：
```python
# layered_search_strategy.py
class LayeredSearchStrategy:
    LAYERS = {
        0: {
            "name": "当事方官方来源",
            "priority": "must",
            "search_type": "site",
            "max_results": 20
        },
        1: {
            "name": "当事方主流媒体",
            "priority": "must",
            "search_type": "site",
            "max_results": 20
        },
        2: {
            "name": "周边地区",
            "priority": "focus",
            "search_type": "lang",
            "max_results": 15
        },
        3: {
            "name": "国际权威媒体",
            "priority": "standard",
            "search_type": "general",
            "max_results": 30
        },
        4: {
            "name": "智库分析",
            "priority": "supplement",
            "search_type": "specialized",
            "max_results": 10
        }
    }

    async def execute_layered_search(
        self,
        query: str,
        parties: List[str],
        discovered_sources: Dict[str, DiscoveredSource],
        options: SearchOptions
    ) -> Dict[int, LayeredSearchResult]:
        results = {}

        # Layer 0: 当事方官方来源 (site: 搜索)
        layer0_queries = self._build_layer_0_queries(query, discovered_sources)
        results[0] = await self._execute_layer_search(0, layer0_queries, options)

        # Layer 1: 当事方主流媒体 (site: 搜索)
        layer1_queries = self._build_layer_1_queries(query, discovered_sources)
        results[1] = await self._execute_layer_search(1, layer1_queries, options)

        # Layer 2: 周边地区 (语言搜索)
        layer2_queries = self._build_layer_2_queries(query, parties)
        results[2] = await self._execute_layer_search(2, layer2_queries, options)

        # Layer 3: 国际权威媒体 (一般搜索)
        layer3_queries = self._build_layer_3_queries(query)
        results[3] = await self._execute_layer_search(3, layer3_queries, options)

        # Layer 4: 智库分析 (专业搜索)
        layer4_queries = self._build_layer_4_queries(query)
        results[4] = await self._execute_layer_search(4, layer4_queries, options)

        return results

    def _build_layer_0_queries(
        self,
        query: str,
        discovered_sources: Dict[str, DiscoveredSource]
    ) -> List[str]:
        """构建 Layer 0 查询 (官方来源 site: 搜索)"""
        queries = []
        for source in discovered_sources.values():
            # 官方政府网站
            for domain in source.official_gov:
                queries.append(f"site:{domain} {query}")
            # 官方通讯社
            for domain in source.official_agency:
                queries.append(f"site:{domain} {query}")
        return queries

    def _build_layer_1_queries(
        self,
        query: str,
        discovered_sources: Dict[str, DiscoveredSource]
    ) -> List[str]:
        """构建 Layer 1 查询 (主流媒体 site: 搜索)"""
        queries = []
        for source in discovered_sources.values():
            for domain in source.local_mainstream:
                queries.append(f"site:{domain} {query}")
        return queries

    def _build_layer_2_queries(
        self,
        query: str,
        parties: List[str]
    ) -> List[str]:
        """构建 Layer 2 查询 (周边地区语言搜索)"""
        # 根据当事方确定周边地区和语言
        queries = []
        for party in parties:
            lang_map = {
                "美国": "en",
                "日本": "ja",
                "韩国": "ko",
                "中国": "zh"
            }
            lang = lang_map.get(party, "en")
            queries.append(f"({lang}) {query}")
        return queries

    def _build_layer_3_queries(self, query: str) -> List[str]:
        """构建 Layer 3 查询 (国际权威媒体)"""
        # 预定义的国际权威媒体
        intl_domains = [
            "reuters.com", "apnews.com", "afp.com",
            "cnn.com", "bbc.com", "nytimes.com"
        ]
        return [f"site:{domain} {query}" for domain in intl_domains]

    def _build_layer_4_queries(self, query: str) -> List[str]:
        """构建 Layer 4 查询 (智库分析)"""
        think_tank_domains = [
            "csis.org", "rand.org", "brookings.edu",
            "heritage.org", "aei.org"
        ]
        return [f"site:{domain} {query}" for domain in think_tank_domains]

    async def _execute_layer_search(
        self,
        layer: int,
        queries: List[str],
        options: SearchOptions
    ) -> LayeredSearchResult:
        """执行单层搜索"""
        start_time = time.time()

        # 并发执行该层的所有查询
        all_results = []
        for query in queries:
            results = await self.firecrawl.search(
                query=query,
                limit=options.get("limit", 20) // len(queries),
                time_range=options.get("time_range", "1w")
            )
            all_results.extend(results)

        return LayeredSearchResult(
            layer=layer,
            layer_name=self.LAYERS[layer]["name"],
            source_type=self.LAYERS[layer]["search_type"],
            query=", ".join(queries[:3]),  # 取前3个作为示例
            results=all_results,
            total_count=len(all_results),
            fetched_count=len([r for r in all_results if r.get("content")]),
            execution_time_ms=int((time.time() - start_time) * 1000),
            sources_used=queries
        )
```

### 4.4 阶段 3: Site: 搜索优化

**目标**：优化 Firecrawl 的 site: 搜索实现

**修改文件**：
```
src/infrastructure/crawlers/firecrawl_adapter.py
src/infrastructure/search/firecrawl_search_adapter.py
```

**关键改进**：
```python
# firecrawl_search_adapter.py
class FirecrawlSearchAdapter:
    async def search(
        self,
        query: str,
        limit: int = 100,
        time_range: str = "1w",
        search_type: str = "news"
    ) -> List[SearchResult]:
        """执行搜索，支持 site: 语法"""

        # 检测 site: 语法
        is_site_search = "site:" in query

        if is_site_search:
            # Site: 搜索使用特殊处理
            return await self._site_search(query, limit, time_range)
        else:
            # 常规搜索
            return await self._regular_search(query, limit, time_range)

    async def _site_search(
        self,
        query: str,
        limit: int,
        time_range: str
    ) -> List[SearchResult]:
        """Site: 搜索专用处理"""
        # 提取域名
        domain = self._extract_domain_from_site_query(query)
        actual_query = self._remove_site_prefix(query)

        # 设置搜索选项
        search_options = {
            "query": actual_query,
            "limit": limit,
            "time_range": time_range,
            # 如果可能，添加域名过滤
        }

        # 执行搜索
        response = await self.client.search(search_options)

        # 后处理：只返回指定域名的结果
        results = self._filter_by_domain(response, domain)
        return results

    def _extract_domain_from_site_query(self, query: str) -> str:
        """从 site: 查询中提取域名"""
        import re
        match = re.search(r'site:([^\s]+)', query)
        return match.group(1) if match else ""

    def _remove_site_prefix(self, query: str) -> str:
        """移除 site: 前缀"""
        import re
        return re.sub(r'site:[^\s]+\s*', '', query)
```

### 4.5 阶段 4: 多语言交叉验证

**目标**：实现多语言交叉验证机制

**新增文件**：
```
src/services/
└── cross_validation_service.py
```

**关键代码**：
```python
# cross_validation_service.py
class CrossValidationService:
    def __init__(self):
        self.claude_client = create_claude_client()

    async def validate_cross_language(
        self,
        results: Dict[str, List[SearchResult]],
        original_query: str
    ) -> Dict[str, float]:
        """交叉验证多语言搜索结果

        Args:
            results: 各语言搜索结果 {"zh": [...], "en": [...], "ja": [...]}
            original_query: 原始查询

        Returns:
            各结果的一致性得分 {url: consistency_score}
        """
        # 提取各语言的关键信息
        summaries = {}
        for lang, lang_results in results.items():
            summaries[lang] = await self._summarize_results(lang_results, lang)

        # 使用 Claude 比较一致性
        consistency = await self.claude_client.compare_summaries(
            original_query=original_query,
            summaries=summaries
        )

        return consistency

    async def _summarize_results(
        self,
        results: List[SearchResult],
        lang: str
    ) -> List[Dict]:
        """总结单语言搜索结果"""
        return [
            {
                "url": r.url,
                "title": r.title,
                "summary": r.snippet[:200]  # 使用摘要
            }
            for r in results[:10]
        ]
```

---

## 5. 验收标准

### 5.1 功能验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| FV-1 | 动态源发现 | 官方源发现准确率 ≥ 85% |
| FV-2 | 分层搜索 | 5 层结果正确分类 |
| FV-3 | Site: 搜索 | Site: 搜索结果正确 |
| FV-4 | 结果去重 | 去重率 ≥ 30%，无重复 URL |
| FV-5 | 时间过滤 | 时间过滤与预期一致 |

### 5.2 性能验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| PV-1 | 源发现耗时 | ≤ 10 秒 |
| PV-2 | 分层搜索耗时 | ≤ 45 秒 |
| PV-3 | 单次搜索总耗时 | ≤ 60 秒 |

### 5.3 质量验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| QV-1 | 代码覆盖率 | 新增代码覆盖率 ≥ 80% |
| QV-2 | 单元测试 | 所有单元测试通过 |
| QV-3 | 集成测试 | 核心流程集成测试通过 |

---

## 6. 风险与对策

| 风险 | 影响 | 概率 | 对策 |
|------|------|------|------|
| 源发现准确率不足 | 中 | 中 | 增加人工审核机制 |
| Site: 搜索限制 | 中 | 中 | 准备常规搜索备选方案 |
| 分层搜索耗时过长 | 低 | 低 | 设置超时和并行优化 |
| Claude API 限流 | 高 | 中 | 实现缓存机制 |

---

## 7. 附录

### 7.1 参考资料

1. Tool_for_osint 项目: `~/Downloads/Tool_for_osint/`
2. OSINT Agent 系统文档: `README_OSINT_Agent系统.md`
3. Search Agent 文档: `_agents/search_agent.md`

### 7.2 版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0.0 | 2025-01-08 | Claude | 初始版本 |
| v1.1.0 | 2025-01-08 | Claude | 移除 WebSearch/Playwright/Chrome DevTools，聚焦 Firecrawl |
