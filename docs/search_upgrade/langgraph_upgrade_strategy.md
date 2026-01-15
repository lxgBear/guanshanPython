# LangGraph 搜索系统升级策略文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0.0 |
| 创建日期 | 2025-01-08 |
| 基于版本 | guanshanPython v2.11.0 |
| 目标版本 | v4.0.0 (LangGraph 架构) |
| 参考项目 | Tool_for_osint (OSINT Agent 系统) |

---

## 1. 执行摘要

### 1.1 升级目标

将当前基于单服务的搜索系统重构为基于 LangGraph 的多 Agent 协作系统，实现：

- **5层分层搜索**: 官方 → 主流 → 周边 → 国际 → 智库
- **动态源发现**: 根据当事方自动识别官方来源
- **并行执行**: 多层搜索并行执行，提升效率
- **状态持久化**: 支持中断恢复和历史追溯
- **人工审核**: Human-in-the-loop 可选审核点

### 1.2 当前架构 vs 目标架构

```
当前架构 (v2.11.0):
┌─────────────────────────────────────────────┐
│           NLSearchService (单体)             │
│  Query → Claude解析 → Firecrawl搜索 → 返回   │
└─────────────────────────────────────────────┘

目标架构 (v4.0.0):
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph StateGraph                       │
│  ┌───────────┐   ┌────────────┐   ┌─────────────────────┐  │
│  │  Query    │ → │  Source    │ → │  Layered Search     │  │
│  │  Analyzer │   │  Discovery │   │  (Send API 并行)     │  │
│  └───────────┘   └────────────┘   │  ├─ Layer0 (官方)   │  │
│                                   │  ├─ Layer1 (主流)   │  │
│                                   │  ├─ Layer2 (周边)   │  │
│                                   │  ├─ Layer3 (国际)   │  │
│                                   │  └─ Layer4 (智库)   │  │
│                                   └──────────┬──────────┘  │
│                                              ↓              │
│  ┌───────────┐   ┌────────────┐   ┌─────────────────────┐  │
│  │  Output   │ ← │  Validator │ ← │    Aggregator       │  │
│  └───────────┘   └────────────┘   └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 预期收益

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 官方来源覆盖率 | 10% | 45% | +350% |
| 搜索精确度 | 60% | 85% | +42% |
| 结果质量评分 | 6.5/10 | 8.5/10 | +31% |
| 可扩展性 | 低 | 高 | 显著提升 |

---

## 2. LangGraph 技术选型分析

### 2.1 为什么选择 LangGraph

| 特性 | LangGraph | 传统方案 | 优势 |
|------|-----------|----------|------|
| 多 Agent 协作 | 内置支持 | 需自行实现 | 开发效率 +50% |
| 状态管理 | StateGraph | 手动管理 | 代码简洁 |
| 并行执行 | Send API | asyncio | 语义清晰 |
| 条件路由 | Command | if-else | 可维护性高 |
| 持久化 | Checkpointer | 自行实现 | 开箱即用 |
| 可视化 | 内置 | 无 | 调试便利 |

### 2.2 核心概念映射

```python
# LangGraph 核心概念 → 搜索系统映射

StateGraph       → 搜索工作流图
State            → SearchState (查询、来源、结果等)
Node             → 各功能 Agent (分析、搜索、聚合等)
Edge             → 工作流步骤连接
Conditional Edge → 动态路由决策
Send             → 并行分层搜索
Command          → Agent 间通信和状态更新
Checkpointer     → 搜索状态持久化
Interrupt        → 人工审核点
```

### 2.3 版本选择

```toml
# pyproject.toml 依赖
[tool.poetry.dependencies]
langgraph = "^0.2.74"  # 稳定版本，支持所有核心功能
langchain-anthropic = "^0.3.0"  # Claude 集成
langchain-core = "^0.3.0"
```

---

## 3. 架构设计

### 3.1 状态模型设计

```python
# src/services/langgraph_search/state.py

from typing import TypedDict, List, Dict, Optional, Annotated
from dataclasses import dataclass
from datetime import datetime
import operator

# ============ 基础数据结构 ============

@dataclass
class DiscoveredSource:
    """发现的官方来源"""
    party_name: str          # 当事方名称 (如: "美国", "日本")
    party_type: str          # country | organization | person
    party_code: str          # ISO 国家代码 (如: "US", "JP")

    # Layer 0: 官方来源
    official_gov: List[str]      # ["whitehouse.gov", "state.gov"]
    official_agency: List[str]   # ["reuters.com", "apnews.com"]

    # Layer 1: 主流媒体
    local_mainstream: List[str]  # ["nytimes.com", "cnn.com"]

    # 语言
    primary_language: str        # "en", "ja", "zh"

    # 元数据
    discovery_time: datetime
    confidence: float            # 0.0-1.0


@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str
    snippet: str
    source_domain: str

    # 分层信息
    layer: int                   # 0-4
    layer_name: str              # "官方来源", "主流媒体" 等
    source_tier: int             # 1-6 可信度层级

    # 评分
    relevance_score: float       # 相关性分数
    credibility_score: float     # 可信度分数
    final_score: float           # 综合分数

    # 内容
    markdown_content: Optional[str] = None
    html_content: Optional[str] = None

    # 元数据
    language: str = "en"
    published_date: Optional[str] = None
    fetched_at: Optional[datetime] = None


@dataclass
class LayerSearchResult:
    """单层搜索结果"""
    layer: int
    layer_name: str
    queries_executed: List[str]
    results: List[SearchResult]
    execution_time_ms: int
    error: Optional[str] = None


# ============ 主状态定义 ============

class SearchState(TypedDict):
    """LangGraph 搜索状态"""

    # === 输入 ===
    query: str                              # 原始查询
    user_id: Optional[str]                  # 用户ID
    search_options: Dict                    # 搜索选项

    # === 查询分析 ===
    analysis: Dict                          # Claude 分析结果
    parties: List[str]                      # 识别的当事方
    keywords: List[str]                     # 提取的关键词
    time_range: str                         # 时间范围 (qdr:d, qdr:w, qdr:m)

    # === 源发现 ===
    discovered_sources: Dict[str, DiscoveredSource]  # 发现的官方来源

    # === 分层搜索结果 (可累加) ===
    layer_results: Annotated[
        Dict[int, LayerSearchResult],
        operator.or_                        # 字典合并
    ]

    # === 聚合结果 ===
    aggregated_results: List[SearchResult]  # 去重聚合后的结果

    # === 验证结果 ===
    validation_scores: Dict[str, float]     # URL → 验证分数
    cross_validation_done: bool

    # === 最终输出 ===
    final_results: List[SearchResult]       # 最终排序结果
    statistics: Dict                        # 统计信息

    # === 元数据 ===
    log_id: str                             # 搜索记录ID
    status: str                             # pending | running | completed | failed
    error_message: Optional[str]            # 错误信息
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    # === Human-in-the-loop ===
    needs_review: bool                      # 是否需要人工审核
    review_completed: bool                  # 审核是否完成
```

### 3.1.1 数据库字段映射

LangGraph 内部状态需要转换为现有数据库实体格式存储。以下是映射关系：

#### SearchResult (LangGraph) → SearchResult (DB)

```python
# src/services/langgraph_search/converters/result_converter.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import hashlib

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.search_result import SearchResult as DBSearchResult, ResultStatus


@dataclass
class LangGraphSearchResult:
    """LangGraph 内部搜索结果"""
    url: str
    title: str
    snippet: str
    source_domain: str

    # 分层信息
    layer: int                   # 0-4
    layer_name: str              # "官方来源", "主流媒体" 等
    source_tier: int             # 1-6 可信度层级

    # 评分
    relevance_score: float       # 相关性分数
    credibility_score: float     # 可信度分数
    final_score: float           # 综合分数

    # 内容
    markdown_content: Optional[str] = None
    html_content: Optional[str] = None

    # 元数据
    language: str = "en"
    published_date: Optional[str] = None
    fetched_at: Optional[datetime] = None


class ResultConverter:
    """LangGraph 结果转换器

    将 LangGraph 内部结果格式转换为数据库存储格式
    """

    @staticmethod
    def to_db_search_result(
        lg_result: LangGraphSearchResult,
        task_id: str,
    ) -> DBSearchResult:
        """转换为数据库 SearchResult 实体

        字段映射:
        - LangGraph.url → DB.url
        - LangGraph.title → DB.title
        - LangGraph.snippet → DB.snippet
        - LangGraph.markdown_content → DB.markdown_content
        - LangGraph.html_content → DB.html_content
        - LangGraph.relevance_score → DB.relevance_score
        - LangGraph.final_score → DB.quality_score (综合评分作为质量分)
        - LangGraph.language → DB.language
        - LangGraph.layer_name → DB.source (来源标识)
        - LangGraph.source_tier → DB.metadata["source_tier"]
        - LangGraph.layer → DB.metadata["layer"]
        """
        # 生成内容哈希用于去重
        dedup_str = f"{lg_result.url}|{lg_result.title}|{(lg_result.markdown_content or '')[:500]}"
        content_hash = hashlib.sha256(dedup_str.encode('utf-8')).hexdigest()[:16]

        # 解析发布日期
        published_date = None
        if lg_result.published_date:
            try:
                published_date = datetime.fromisoformat(lg_result.published_date)
            except ValueError:
                pass

        return DBSearchResult(
            id=generate_string_id(),
            task_id=task_id,

            # 核心字段
            title=lg_result.title,
            url=lg_result.url,
            snippet=lg_result.snippet,

            # 来源信息
            source=lg_result.layer_name,  # "官方来源", "主流媒体" 等
            language=lg_result.language,
            published_date=published_date,

            # 内容
            markdown_content=lg_result.markdown_content,
            html_content=lg_result.html_content,

            # 评分
            relevance_score=lg_result.relevance_score,
            quality_score=lg_result.final_score,  # 综合评分

            # 去重
            content_hash=content_hash,

            # 扩展元数据 (LangGraph 特有字段)
            metadata={
                "layer": lg_result.layer,
                "layer_name": lg_result.layer_name,
                "source_tier": lg_result.source_tier,
                "source_domain": lg_result.source_domain,
                "credibility_score": lg_result.credibility_score,
                "search_engine": "langgraph_v4",
            },

            # 状态
            status=ResultStatus.PENDING,
            created_at=datetime.utcnow(),
        )
```

#### SearchState (LangGraph) → AggregatedSearchResult (DB)

```python
# src/services/langgraph_search/converters/aggregated_converter.py

from typing import List, Dict, Any
from datetime import datetime

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.aggregated_search_result import (
    AggregatedSearchResult as DBAggregatedResult,
    SourceInfo,
)
from src.core.domain.entities.search_result import ResultStatus


class AggregatedResultConverter:
    """聚合结果转换器

    将 LangGraph 聚合后的结果转换为数据库 AggregatedSearchResult
    """

    @staticmethod
    def to_db_aggregated_result(
        lg_result: 'LangGraphSearchResult',
        smart_task_id: str,
        layer_results: Dict[int, 'LayerSearchResult'],
    ) -> DBAggregatedResult:
        """转换为数据库 AggregatedSearchResult 实体

        字段映射:
        - LangGraph.url → DB.url
        - LangGraph.title → DB.title
        - LangGraph.snippet → DB.snippet
        - LangGraph.markdown_content → DB.content
        - LangGraph.final_score → DB.composite_score
        - LangGraph.relevance_score → DB.avg_relevance_score
        - LangGraph.credibility_score → DB.avg_quality_score
        - LangGraph.layer → DB.sources[].position (来源位置)
        - LangGraph.source_tier → DB.metadata["source_tier"]
        """
        # 构建来源信息
        sources = []
        source_count = 0

        # 从 layer_results 中找到该 URL 出现的所有层
        for layer_id, layer_result in layer_results.items():
            for idx, result in enumerate(layer_result.results):
                if result.url == lg_result.url:
                    sources.append(SourceInfo(
                        query=layer_result.queries_executed[0] if layer_result.queries_executed else "",
                        task_id=str(layer_id),
                        position=idx + 1,
                        relevance_score=result.relevance_score,
                    ))
                    source_count += 1

        # 计算位置评分 (层级越低，评分越高)
        position_score = 1.0 - (lg_result.layer * 0.15)  # Layer 0 = 1.0, Layer 4 = 0.4

        # 多源评分 (出现次数越多，评分越高)
        multi_source_score = min(source_count * 0.25, 1.0)

        return DBAggregatedResult(
            id=generate_string_id(),
            smart_task_id=smart_task_id,

            # 基础字段
            title=lg_result.title,
            url=lg_result.url,
            content=lg_result.markdown_content or "",
            snippet=lg_result.snippet,

            # 聚合评分
            composite_score=lg_result.final_score,
            avg_relevance_score=lg_result.relevance_score,
            avg_quality_score=lg_result.credibility_score,
            position_score=position_score,
            multi_source_score=multi_source_score,

            # 多源信息
            sources=sources,
            source_count=source_count,
            multi_source_bonus=(source_count > 1),

            # 元数据
            result_type="web",
            language=lg_result.language,
            published_date=datetime.fromisoformat(lg_result.published_date) if lg_result.published_date else None,

            # 状态
            status=ResultStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),

            # 扩展元数据
            metadata={
                "layer": lg_result.layer,
                "layer_name": lg_result.layer_name,
                "source_tier": lg_result.source_tier,
                "source_domain": lg_result.source_domain,
                "search_engine": "langgraph_v4",
            },
        )
```

#### NLSearchLog (LangGraph 分析结果存储)

```python
# src/services/langgraph_search/converters/log_converter.py

from typing import Dict, Any
from datetime import datetime

from src.core.domain.entities.nl_search.nl_search_log import NLSearchLog


class SearchLogConverter:
    """搜索日志转换器

    将 LangGraph QueryAnalyzer 的分析结果存储到 NLSearchLog
    """

    @staticmethod
    def create_search_log(
        query: str,
        analysis: Dict[str, Any],
        parties: list,
        keywords: list,
        time_range: str,
    ) -> NLSearchLog:
        """创建搜索日志记录

        字段映射:
        - LangGraph.query → DB.query_text
        - LangGraph.analysis → DB.llm_analysis
        - LangGraph.parties → DB.llm_analysis["parties"]
        - LangGraph.keywords → DB.llm_analysis["keywords"]
        """
        return NLSearchLog(
            query_text=query,
            llm_analysis={
                # Claude 分析结果
                "intent": analysis.get("intent", "unknown"),
                "keywords": keywords,
                "parties": parties,  # 当事方列表

                # 时间范围
                "time_range": {
                    "type": analysis.get("time_indicator", "recent"),
                    "query_param": time_range,  # qdr:d, qdr:w, qdr:m
                },

                # 搜索策略
                "topic_category": analysis.get("topic_category", "other"),
                "search_depth": analysis.get("search_depth", "standard"),

                # 置信度
                "confidence": analysis.get("confidence", 0.5),

                # LangGraph 元数据
                "search_engine": "langgraph_v4",
                "layered_search": True,
            },
            created_at=datetime.utcnow(),
        )
```

#### 数据库字段对照表

| LangGraph 字段 | 数据库实体 | 数据库字段 | 说明 |
|---------------|-----------|-----------|------|
| `SearchState.query` | NLSearchLog | query_text | 原始查询 |
| `SearchState.parties` | NLSearchLog | llm_analysis["parties"] | 当事方列表 |
| `SearchState.keywords` | NLSearchLog | llm_analysis["keywords"] | 关键词 |
| `SearchState.analysis` | NLSearchLog | llm_analysis | Claude 分析结果 |
| `SearchResult.url` | SearchResult | url | 结果URL |
| `SearchResult.title` | SearchResult | title | 标题 |
| `SearchResult.snippet` | SearchResult | snippet | 摘要 |
| `SearchResult.markdown_content` | SearchResult | markdown_content | Markdown内容 |
| `SearchResult.relevance_score` | SearchResult | relevance_score | 相关性分数 |
| `SearchResult.final_score` | SearchResult | quality_score | 综合评分→质量分 |
| `SearchResult.layer` | SearchResult | metadata["layer"] | 搜索层级 |
| `SearchResult.layer_name` | SearchResult | source | 来源标识 |
| `SearchResult.source_tier` | SearchResult | metadata["source_tier"] | 可信度层级 |
| `LayerSearchResult` | AggregatedSearchResult | sources[] | 多源信息 |
| `aggregated_results` | AggregatedSearchResult | - | 聚合后结果 |

### 3.2 Graph 结构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SearchGraph 完整结构                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    START                                                            │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────┐                                               │
│  │  QueryAnalyzer  │  ← Claude 分析查询                             │
│  │  识别当事方      │     提取关键词                                 │
│  │  确定时间范围    │     判断搜索策略                               │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                               │
│  │ SourceDiscovery │  ← Claude + Firecrawl                         │
│  │  动态发现官方源  │     为每个当事方发现官方域名                   │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼ (Conditional: fan_out_layers)                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    PARALLEL EXECUTION                        │   │
│  │   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │   │
│  │   │  Layer0   │ │  Layer1   │ │  Layer2   │ │  Layer3   │  │   │
│  │   │  Search   │ │  Search   │ │  Search   │ │  Search   │  │   │
│  │   │  (官方)   │ │  (主流)   │ │  (周边)   │ │  (国际)   │  │   │
│  │   └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  │   │
│  │         │             │             │             │         │   │
│  │   ┌─────┴─────────────┴─────────────┴─────────────┴─────┐  │   │
│  │   │                     Layer4Search                     │  │   │
│  │   │                       (智库)                         │  │   │
│  │   └───────────────────────────┬─────────────────────────┘  │   │
│  └───────────────────────────────┼─────────────────────────────┘   │
│                                  │                                  │
│                                  ▼ (fan-in)                        │
│  ┌─────────────────┐                                               │
│  │   Aggregator    │  ← URL 去重                                   │
│  │   结果聚合       │     分数计算                                  │
│  │   分层排序       │     来源合并                                  │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼ (Conditional: needs_validation?)                       │
│  ┌─────────────────┐                                               │
│  │   Validator     │  ← 交叉验证 (可选)                            │
│  │   多语言验证     │     可信度评估                                │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼ (Conditional: needs_review?)                           │
│  ┌─────────────────┐                                               │
│  │  HumanReview    │  ← interrupt() 人工审核                       │
│  │   (可选)        │     关键结果确认                               │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                               │
│  │   OutputNode    │  ← 最终结果格式化                              │
│  │   统计生成       │     保存到数据库                              │
│  └────────┬────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│         END                                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 模块结构

```
src/services/langgraph_search/
├── __init__.py
├── state.py                    # 状态定义
├── graph.py                    # Graph 构建
├── nodes/                      # Agent 节点
│   ├── __init__.py
│   ├── query_analyzer.py       # 查询分析
│   ├── source_discovery.py     # 源发现
│   ├── layer_search.py         # 分层搜索
│   ├── aggregator.py           # 结果聚合
│   ├── validator.py            # 验证器
│   ├── human_review.py         # 人工审核
│   └── output.py               # 输出节点
├── tools/                      # 工具函数
│   ├── __init__.py
│   ├── firecrawl_tool.py       # Firecrawl 封装
│   ├── claude_tool.py          # Claude 封装
│   └── url_utils.py            # URL 处理
├── config.py                   # 配置
└── service.py                  # 对外服务接口
```

---

## 4. 核心实现

### 4.1 Graph 构建

```python
# src/services/langgraph_search/graph.py

from typing import Literal, List
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

from .state import SearchState, LayerSearchResult
from .nodes import (
    QueryAnalyzerNode,
    SourceDiscoveryNode,
    LayerSearchNode,
    AggregatorNode,
    ValidatorNode,
    HumanReviewNode,
    OutputNode,
)
from .config import LangGraphSearchConfig


class SearchGraphBuilder:
    """搜索图构建器"""

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config
        self.nodes = self._init_nodes()

    def _init_nodes(self):
        """初始化所有节点"""
        return {
            "query_analyzer": QueryAnalyzerNode(self.config),
            "source_discovery": SourceDiscoveryNode(self.config),
            "layer_search": LayerSearchNode(self.config),
            "aggregator": AggregatorNode(self.config),
            "validator": ValidatorNode(self.config),
            "human_review": HumanReviewNode(self.config),
            "output": OutputNode(self.config),
        }

    def build(self) -> StateGraph:
        """构建搜索图"""
        builder = StateGraph(SearchState)

        # ===== 添加节点 =====
        builder.add_node("query_analyzer", self.nodes["query_analyzer"])
        builder.add_node("source_discovery", self.nodes["source_discovery"])
        builder.add_node("layer_search", self.nodes["layer_search"])
        builder.add_node("aggregator", self.nodes["aggregator"])
        builder.add_node("validator", self.nodes["validator"])
        builder.add_node("human_review", self.nodes["human_review"])
        builder.add_node("output", self.nodes["output"])

        # ===== 添加边 =====

        # 1. START → QueryAnalyzer
        builder.add_edge(START, "query_analyzer")

        # 2. QueryAnalyzer → SourceDiscovery
        builder.add_edge("query_analyzer", "source_discovery")

        # 3. SourceDiscovery → LayerSearch (并行分层搜索)
        builder.add_conditional_edges(
            "source_discovery",
            self._fan_out_layers,
            ["layer_search"]  # 所有 Send 目标都是 layer_search
        )

        # 4. LayerSearch → Aggregator (fan-in)
        builder.add_edge("layer_search", "aggregator")

        # 5. Aggregator → Validator (条件)
        builder.add_conditional_edges(
            "aggregator",
            self._route_after_aggregation,
            {
                "validator": "validator",
                "output": "output"
            }
        )

        # 6. Validator → HumanReview (条件)
        builder.add_conditional_edges(
            "validator",
            self._route_after_validation,
            {
                "human_review": "human_review",
                "output": "output"
            }
        )

        # 7. HumanReview → Output
        builder.add_edge("human_review", "output")

        # 8. Output → END
        builder.add_edge("output", END)

        return builder

    def _fan_out_layers(self, state: SearchState) -> List[Send]:
        """并行分发到各搜索层

        使用 Send API 实现 fan-out 模式：
        - 每个 Layer 作为独立任务
        - 并行执行，提升效率
        - 结果汇聚到 Aggregator
        """
        sends = []
        discovered = state.get("discovered_sources", {})

        # Layer 0: 官方来源 (site: 搜索)
        if discovered:
            sends.append(Send("layer_search", {
                "layer": 0,
                "layer_name": "官方来源",
                "search_type": "site",
                "sources": discovered,
                "query": state["query"],
                "keywords": state.get("keywords", []),
                "time_range": state.get("time_range", "qdr:m"),
            }))

        # Layer 1: 主流媒体 (site: 搜索)
        if discovered:
            sends.append(Send("layer_search", {
                "layer": 1,
                "layer_name": "主流媒体",
                "search_type": "site",
                "sources": discovered,
                "query": state["query"],
                "keywords": state.get("keywords", []),
                "time_range": state.get("time_range", "qdr:m"),
            }))

        # Layer 2: 周边地区 (多语言搜索)
        parties = state.get("parties", [])
        if parties:
            sends.append(Send("layer_search", {
                "layer": 2,
                "layer_name": "周边地区",
                "search_type": "multilang",
                "parties": parties,
                "query": state["query"],
                "keywords": state.get("keywords", []),
                "time_range": state.get("time_range", "qdr:m"),
            }))

        # Layer 3: 国际权威媒体 (通用搜索)
        sends.append(Send("layer_search", {
            "layer": 3,
            "layer_name": "国际权威",
            "search_type": "general",
            "query": state["query"],
            "keywords": state.get("keywords", []),
            "time_range": state.get("time_range", "qdr:m"),
        }))

        # Layer 4: 智库分析 (专业搜索)
        sends.append(Send("layer_search", {
            "layer": 4,
            "layer_name": "智库分析",
            "search_type": "specialized",
            "query": state["query"],
            "keywords": state.get("keywords", []),
            "time_range": state.get("time_range", "qdr:m"),
        }))

        return sends

    def _route_after_aggregation(
        self, state: SearchState
    ) -> Literal["validator", "output"]:
        """聚合后路由决策"""
        # 如果启用验证且结果数量足够
        if (
            self.config.enable_validation and
            len(state.get("aggregated_results", [])) >= self.config.min_results_for_validation
        ):
            return "validator"
        return "output"

    def _route_after_validation(
        self, state: SearchState
    ) -> Literal["human_review", "output"]:
        """验证后路由决策"""
        # 如果启用人工审核且存在低置信结果
        if (
            self.config.enable_human_review and
            state.get("needs_review", False)
        ):
            return "human_review"
        return "output"

    def compile(self, checkpointer=None):
        """编译图并添加检查点"""
        graph = self.build()

        if checkpointer is None and self.config.enable_checkpointing:
            # 默认使用 SQLite
            checkpointer = SqliteSaver.from_conn_string(
                self.config.checkpoint_db_path
            )

        return graph.compile(checkpointer=checkpointer)
```

### 4.2 查询分析节点

```python
# src/services/langgraph_search/nodes/query_analyzer.py

from typing import Dict, Any
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from langgraph.types import Command

from ..state import SearchState
from ..config import LangGraphSearchConfig


class QueryAnalyzerNode:
    """查询分析节点

    职责：
    1. 解析用户查询意图
    2. 识别涉及的当事方 (国家/组织/人物)
    3. 提取关键词
    4. 确定时间范围
    5. 判断搜索策略
    """

    ANALYSIS_PROMPT = """分析以下搜索查询，提取关键信息：

查询：{query}

请以 JSON 格式返回：
{{
    "intent": "查询意图描述",
    "parties": ["涉及的当事方列表，如国家、组织、人物"],
    "keywords": ["搜索关键词列表"],
    "time_indicator": "时间相关词 (如：最近、今年、本周) 或 null",
    "suggested_time_range": "建议时间范围: h (1小时) | d (1天) | w (1周) | m (1月) | y (1年)",
    "topic_category": "主题分类: politics | military | economy | technology | society | other",
    "search_depth": "搜索深度建议: quick | standard | deep",
    "confidence": 0.0-1.0
}}

注意：
- parties 只包含主要当事方（最多5个）
- keywords 提取核心搜索词（3-8个）
- 根据查询内容智能判断时间范围
"""

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config
        self.llm = ChatAnthropic(
            model=config.claude_model,
            temperature=0,
            max_tokens=1024,
        )

    async def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行查询分析"""
        query = state["query"]

        # 调用 Claude 分析
        prompt = self.ANALYSIS_PROMPT.format(query=query)
        response = await self.llm.ainvoke(prompt)

        # 解析响应
        analysis = self._parse_response(response.content)

        # 确定时间范围
        time_range = self._determine_time_range(analysis)

        return {
            "analysis": analysis,
            "parties": analysis.get("parties", []),
            "keywords": analysis.get("keywords", [query]),
            "time_range": time_range,
            "status": "analyzing",
        }

    def _parse_response(self, content: str) -> Dict:
        """解析 Claude 响应"""
        import json
        try:
            # 提取 JSON 部分
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return {
            "intent": "unknown",
            "parties": [],
            "keywords": [],
            "time_indicator": None,
            "suggested_time_range": "m",
            "confidence": 0.5,
        }

    def _determine_time_range(self, analysis: Dict) -> str:
        """确定搜索时间范围"""
        suggested = analysis.get("suggested_time_range", "m")

        # 时间范围映射
        time_map = {
            "h": "qdr:h",   # 过去1小时
            "d": "qdr:d",   # 过去24小时
            "w": "qdr:w",   # 过去1周
            "m": "qdr:m",   # 过去1月
            "y": "qdr:y",   # 过去1年
        }

        return time_map.get(suggested, "qdr:m")
```

### 4.3 源发现节点

```python
# src/services/langgraph_search/nodes/source_discovery.py

from typing import Dict, Any, List
from datetime import datetime
from langchain_anthropic import ChatAnthropic

from ..state import SearchState, DiscoveredSource
from ..config import LangGraphSearchConfig
from ..tools.firecrawl_tool import FirecrawlTool


class SourceDiscoveryNode:
    """源发现节点

    职责：
    1. 为每个当事方动态发现官方来源
    2. 识别政府官网、官方通讯社、主流媒体
    3. 确定各当事方的主要语言
    """

    DISCOVERY_PROMPT = """为以下当事方识别官方信息来源：

当事方：{party}
上下文：{context}

请以 JSON 格式返回：
{{
    "party_name": "当事方名称",
    "party_type": "country | organization | person",
    "party_code": "ISO国家代码（如适用）",
    "official_gov": ["官方政府网站域名列表"],
    "official_agency": ["官方通讯社域名列表"],
    "local_mainstream": ["当地主流媒体域名列表"],
    "primary_language": "主要语言代码 (如 en, zh, ja)",
    "confidence": 0.0-1.0
}}

示例域名格式：
- 官方政府：whitehouse.gov, mofa.go.jp, fmprc.gov.cn
- 通讯社：reuters.com, xinhuanet.com, kyodonews.net
- 主流媒体：nytimes.com, asahi.com, people.com.cn

只返回确定存在且权威的域名，不要猜测。
"""

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config
        self.llm = ChatAnthropic(
            model=config.claude_model,
            temperature=0,
            max_tokens=2048,
        )
        self.firecrawl = FirecrawlTool(config)

    async def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行源发现"""
        parties = state.get("parties", [])
        query = state["query"]

        if not parties:
            # 如果没有识别到当事方，使用默认策略
            return {
                "discovered_sources": {},
                "status": "source_discovered",
            }

        discovered_sources = {}

        for party in parties[:self.config.max_parties]:
            try:
                source = await self._discover_party_sources(party, query)
                if source:
                    discovered_sources[party] = source
            except Exception as e:
                # 记录错误但继续处理其他当事方
                print(f"源发现失败 [{party}]: {e}")

        return {
            "discovered_sources": discovered_sources,
            "status": "source_discovered",
        }

    async def _discover_party_sources(
        self, party: str, context: str
    ) -> DiscoveredSource:
        """发现单个当事方的官方来源"""

        # 1. 使用 Claude 初步分析
        prompt = self.DISCOVERY_PROMPT.format(party=party, context=context)
        response = await self.llm.ainvoke(prompt)
        initial = self._parse_response(response.content)

        # 2. 使用 Firecrawl 验证和补充
        if self.config.verify_discovered_sources:
            verified = await self._verify_sources(party, initial)
        else:
            verified = initial

        return DiscoveredSource(
            party_name=verified.get("party_name", party),
            party_type=verified.get("party_type", "country"),
            party_code=verified.get("party_code", ""),
            official_gov=verified.get("official_gov", []),
            official_agency=verified.get("official_agency", []),
            local_mainstream=verified.get("local_mainstream", []),
            primary_language=verified.get("primary_language", "en"),
            discovery_time=datetime.utcnow(),
            confidence=verified.get("confidence", 0.7),
        )

    async def _verify_sources(
        self, party: str, initial: Dict
    ) -> Dict:
        """使用 Firecrawl 验证发现的源"""

        # 构建验证查询
        verification_queries = [
            f"{party} official government website",
            f"{party} official news agency",
            f"{party} main news media",
        ]

        # 执行搜索验证
        verified_domains = set()
        for query in verification_queries:
            try:
                results = await self.firecrawl.search(query, limit=5)
                for r in results:
                    domain = self._extract_domain(r.get("url", ""))
                    if domain:
                        verified_domains.add(domain)
            except Exception:
                pass

        # 交叉验证初步结果
        all_initial_domains = (
            initial.get("official_gov", []) +
            initial.get("official_agency", []) +
            initial.get("local_mainstream", [])
        )

        verified_count = len(set(all_initial_domains) & verified_domains)
        total_count = len(all_initial_domains)

        # 更新置信度
        if total_count > 0:
            initial["confidence"] = min(
                initial.get("confidence", 0.7),
                0.5 + (verified_count / total_count) * 0.5
            )

        return initial

    def _parse_response(self, content: str) -> Dict:
        """解析 Claude 响应"""
        import json
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        return {}

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return ""
```

### 4.4 分层搜索节点

```python
# src/services/langgraph_search/nodes/layer_search.py

from typing import Dict, Any, List
import asyncio

from ..state import SearchState, SearchResult, LayerSearchResult
from ..config import LangGraphSearchConfig
from ..tools.firecrawl_tool import FirecrawlTool


class LayerSearchNode:
    """分层搜索节点

    支持多种搜索类型：
    - site: 针对特定域名的精确搜索
    - multilang: 多语言搜索
    - general: 通用搜索
    - specialized: 专业来源搜索 (智库)
    """

    # 预定义的国际权威媒体
    INTERNATIONAL_MEDIA = [
        "reuters.com", "apnews.com", "afp.com",
        "bbc.com", "cnn.com", "nytimes.com",
        "theguardian.com", "washingtonpost.com",
        "aljazeera.com", "dw.com",
    ]

    # 预定义的智库
    THINK_TANKS = [
        "csis.org", "rand.org", "brookings.edu",
        "cfr.org", "carnegieendowment.org",
        "heritage.org", "aei.org",
        "iseas.edu.sg", "aspi.org.au",
    ]

    # 语言代码映射
    PARTY_LANGUAGE_MAP = {
        "美国": "en", "英国": "en", "澳大利亚": "en",
        "中国": "zh", "台湾": "zh",
        "日本": "ja",
        "韩国": "ko",
        "俄罗斯": "ru",
        "法国": "fr",
        "德国": "de",
        "西班牙": "es",
        "阿拉伯": "ar",
    }

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config
        self.firecrawl = FirecrawlTool(config)

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行分层搜索

        接收 Send 传递的参数，执行对应层级的搜索
        """
        layer = state.get("layer", 0)
        layer_name = state.get("layer_name", "Unknown")
        search_type = state.get("search_type", "general")
        query = state.get("query", "")
        keywords = state.get("keywords", [])
        time_range = state.get("time_range", "qdr:m")

        import time
        start_time = time.time()

        try:
            if search_type == "site":
                results = await self._site_search(state)
            elif search_type == "multilang":
                results = await self._multilang_search(state)
            elif search_type == "specialized":
                results = await self._specialized_search(state)
            else:
                results = await self._general_search(state)

            execution_time = int((time.time() - start_time) * 1000)

            layer_result = LayerSearchResult(
                layer=layer,
                layer_name=layer_name,
                queries_executed=[query],
                results=results,
                execution_time_ms=execution_time,
            )

            return {
                "layer_results": {layer: layer_result}
            }

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)

            return {
                "layer_results": {
                    layer: LayerSearchResult(
                        layer=layer,
                        layer_name=layer_name,
                        queries_executed=[query],
                        results=[],
                        execution_time_ms=execution_time,
                        error=str(e),
                    )
                }
            }

    async def _site_search(self, state: Dict) -> List[SearchResult]:
        """Site: 精确域名搜索"""
        results = []
        sources = state.get("sources", {})
        query = state.get("query", "")
        layer = state.get("layer", 0)
        layer_name = state.get("layer_name", "")
        time_range = state.get("time_range", "qdr:m")

        # 根据层级选择域名
        domains = []
        for party_name, source in sources.items():
            if layer == 0:  # 官方来源
                domains.extend(source.official_gov)
                domains.extend(source.official_agency)
            elif layer == 1:  # 主流媒体
                domains.extend(source.local_mainstream)

        # 为每个域名执行 site: 搜索
        tasks = []
        for domain in domains[:self.config.max_domains_per_layer]:
            site_query = f"site:{domain} {query}"
            tasks.append(self._execute_search(
                site_query,
                layer,
                layer_name,
                domain,
                time_range
            ))

        # 并发执行
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batch_results:
                if isinstance(batch, list):
                    results.extend(batch)

        return results

    async def _multilang_search(self, state: Dict) -> List[SearchResult]:
        """多语言搜索"""
        results = []
        parties = state.get("parties", [])
        query = state.get("query", "")
        layer = state.get("layer", 2)
        layer_name = state.get("layer_name", "周边地区")
        time_range = state.get("time_range", "qdr:m")

        # 为每个当事方确定语言
        languages = set()
        for party in parties:
            lang = self.PARTY_LANGUAGE_MAP.get(party, "en")
            languages.add(lang)

        # 添加英语作为基准
        languages.add("en")

        # 为每种语言执行搜索
        tasks = []
        for lang in languages:
            # TODO: 生成该语言的查询词
            lang_query = query  # 简化处理，实际应翻译
            tasks.append(self._execute_search(
                lang_query,
                layer,
                layer_name,
                f"lang:{lang}",
                time_range
            ))

        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batch_results:
                if isinstance(batch, list):
                    results.extend(batch)

        return results

    async def _general_search(self, state: Dict) -> List[SearchResult]:
        """通用搜索 (国际权威媒体)"""
        results = []
        query = state.get("query", "")
        layer = state.get("layer", 3)
        layer_name = state.get("layer_name", "国际权威")
        time_range = state.get("time_range", "qdr:m")

        # 为国际权威媒体执行 site: 搜索
        tasks = []
        for domain in self.INTERNATIONAL_MEDIA[:self.config.max_domains_per_layer]:
            site_query = f"site:{domain} {query}"
            tasks.append(self._execute_search(
                site_query,
                layer,
                layer_name,
                domain,
                time_range
            ))

        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batch_results:
                if isinstance(batch, list):
                    results.extend(batch)

        return results

    async def _specialized_search(self, state: Dict) -> List[SearchResult]:
        """专业来源搜索 (智库)"""
        results = []
        query = state.get("query", "")
        layer = state.get("layer", 4)
        layer_name = state.get("layer_name", "智库分析")
        time_range = state.get("time_range", "qdr:m")

        # 为智库执行 site: 搜索
        tasks = []
        for domain in self.THINK_TANKS[:self.config.max_domains_per_layer]:
            site_query = f"site:{domain} {query}"
            tasks.append(self._execute_search(
                site_query,
                layer,
                layer_name,
                domain,
                time_range
            ))

        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batch_results:
                if isinstance(batch, list):
                    results.extend(batch)

        return results

    async def _execute_search(
        self,
        query: str,
        layer: int,
        layer_name: str,
        source_domain: str,
        time_range: str,
    ) -> List[SearchResult]:
        """执行单次搜索"""
        try:
            raw_results = await self.firecrawl.search(
                query=query,
                limit=self.config.results_per_query,
                time_range=time_range,
            )

            # 转换为 SearchResult
            return [
                SearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    source_domain=source_domain,
                    layer=layer,
                    layer_name=layer_name,
                    source_tier=self._determine_tier(layer),
                    relevance_score=r.get("score", 0.5),
                    credibility_score=self._calculate_credibility(layer),
                    final_score=0.0,  # 稍后计算
                    language=r.get("language", "en"),
                )
                for r in raw_results
            ]
        except Exception as e:
            print(f"搜索失败 [{query[:50]}]: {e}")
            return []

    def _determine_tier(self, layer: int) -> int:
        """根据层级确定来源等级"""
        tier_map = {
            0: 1,  # 官方来源 → Tier 1
            1: 2,  # 主流媒体 → Tier 2
            2: 3,  # 周边地区 → Tier 3
            3: 2,  # 国际权威 → Tier 2
            4: 3,  # 智库分析 → Tier 3
        }
        return tier_map.get(layer, 4)

    def _calculate_credibility(self, layer: int) -> float:
        """根据层级计算基础可信度"""
        credibility_map = {
            0: 0.95,  # 官方来源
            1: 0.85,  # 主流媒体
            2: 0.75,  # 周边地区
            3: 0.85,  # 国际权威
            4: 0.80,  # 智库分析
        }
        return credibility_map.get(layer, 0.6)
```

### 4.5 聚合节点

```python
# src/services/langgraph_search/nodes/aggregator.py

from typing import Dict, Any, List
from collections import defaultdict
from urllib.parse import urlparse

from ..state import SearchState, SearchResult, LayerSearchResult
from ..config import LangGraphSearchConfig


class AggregatorNode:
    """结果聚合节点

    职责：
    1. URL 去重
    2. 多来源结果合并
    3. 分数计算
    4. 分层排序
    """

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config

    async def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行结果聚合"""
        layer_results = state.get("layer_results", {})

        # 1. 收集所有结果
        all_results: List[SearchResult] = []
        for layer_id, layer_result in layer_results.items():
            if layer_result and layer_result.results:
                all_results.extend(layer_result.results)

        # 2. URL 去重 (保留最高分数的)
        deduplicated = self._deduplicate_results(all_results)

        # 3. 计算最终分数
        scored = self._calculate_final_scores(deduplicated)

        # 4. 分层排序
        sorted_results = self._sort_results(scored)

        # 5. 生成统计信息
        statistics = self._generate_statistics(layer_results, sorted_results)

        return {
            "aggregated_results": sorted_results,
            "statistics": statistics,
            "status": "aggregated",
        }

    def _deduplicate_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """URL 去重，保留最高分数的结果"""
        url_map: Dict[str, SearchResult] = {}

        for result in results:
            normalized_url = self._normalize_url(result.url)

            if normalized_url not in url_map:
                url_map[normalized_url] = result
            else:
                existing = url_map[normalized_url]
                # 保留来源层级更高（数字更小）的
                if result.layer < existing.layer:
                    url_map[normalized_url] = result
                # 同层级保留分数更高的
                elif result.layer == existing.layer:
                    if result.relevance_score > existing.relevance_score:
                        url_map[normalized_url] = result

        return list(url_map.values())

    def _normalize_url(self, url: str) -> str:
        """URL 规范化"""
        try:
            parsed = urlparse(url)
            # 移除尾部斜杠、www、协议
            path = parsed.path.rstrip("/")
            host = parsed.netloc.replace("www.", "")
            return f"{host}{path}"
        except Exception:
            return url

    def _calculate_final_scores(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """计算最终分数"""
        for result in results:
            # 综合分数 = 相关性 * 0.4 + 可信度 * 0.4 + 层级加权 * 0.2
            layer_weight = self._get_layer_weight(result.layer)

            result.final_score = (
                result.relevance_score * 0.4 +
                result.credibility_score * 0.4 +
                layer_weight * 0.2
            )

        return results

    def _get_layer_weight(self, layer: int) -> float:
        """获取层级权重 (层级越低，权重越高)"""
        weight_map = {
            0: 1.0,   # 官方来源最高
            1: 0.9,   # 主流媒体
            2: 0.7,   # 周边地区
            3: 0.85,  # 国际权威
            4: 0.75,  # 智库分析
        }
        return weight_map.get(layer, 0.5)

    def _sort_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """分层排序

        排序规则：
        1. 先按层级排序 (官方 > 主流 > ...)
        2. 同层级内按最终分数排序
        """
        return sorted(
            results,
            key=lambda r: (r.layer, -r.final_score)
        )

    def _generate_statistics(
        self,
        layer_results: Dict[int, LayerSearchResult],
        aggregated: List[SearchResult],
    ) -> Dict:
        """生成统计信息"""
        stats = {
            "total_results": len(aggregated),
            "by_layer": {},
            "by_tier": defaultdict(int),
            "execution_times": {},
            "deduplication_rate": 0,
        }

        # 按层统计
        total_before_dedup = 0
        for layer_id, layer_result in layer_results.items():
            if layer_result:
                count = len(layer_result.results)
                total_before_dedup += count
                stats["by_layer"][layer_result.layer_name] = count
                stats["execution_times"][layer_result.layer_name] = (
                    layer_result.execution_time_ms
                )

        # 按 Tier 统计
        for result in aggregated:
            stats["by_tier"][f"Tier {result.source_tier}"] += 1

        # 去重率
        if total_before_dedup > 0:
            stats["deduplication_rate"] = round(
                (1 - len(aggregated) / total_before_dedup) * 100, 2
            )

        return stats
```

### 4.6 人工审核节点

```python
# src/services/langgraph_search/nodes/human_review.py

from typing import Dict, Any
from langgraph.types import interrupt, Command

from ..state import SearchState
from ..config import LangGraphSearchConfig


class HumanReviewNode:
    """人工审核节点

    使用 LangGraph 的 interrupt 功能实现 Human-in-the-loop
    """

    def __init__(self, config: LangGraphSearchConfig):
        self.config = config

    async def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行人工审核

        使用 interrupt() 暂停工作流，等待人工审核
        """
        aggregated = state.get("aggregated_results", [])
        validation_scores = state.get("validation_scores", {})

        # 找出需要审核的结果 (低置信度)
        review_needed = []
        for result in aggregated:
            url_score = validation_scores.get(result.url, 1.0)
            if url_score < self.config.review_threshold:
                review_needed.append({
                    "url": result.url,
                    "title": result.title,
                    "layer": result.layer_name,
                    "score": url_score,
                    "reason": "低置信度，需要人工确认",
                })

        if not review_needed:
            # 无需审核
            return {
                "review_completed": True,
                "needs_review": False,
            }

        # 使用 interrupt 暂停等待审核
        review_result = interrupt({
            "action": "review_search_results",
            "items_to_review": review_needed,
            "total_results": len(aggregated),
            "message": f"发现 {len(review_needed)} 条低置信度结果，请审核",
        })

        # 处理审核结果
        approved_urls = set(review_result.get("approved_urls", []))
        rejected_urls = set(review_result.get("rejected_urls", []))

        # 根据审核结果过滤
        filtered_results = [
            r for r in aggregated
            if r.url in approved_urls or r.url not in rejected_urls
        ]

        return {
            "aggregated_results": filtered_results,
            "review_completed": True,
            "needs_review": False,
        }
```

### 4.7 服务封装

```python
# src/services/langgraph_search/service.py

from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from .graph import SearchGraphBuilder
from .state import SearchState
from .config import LangGraphSearchConfig


class LangGraphSearchService:
    """LangGraph 搜索服务

    对外提供的服务接口，封装 LangGraph 搜索图
    """

    def __init__(self, config: Optional[LangGraphSearchConfig] = None):
        self.config = config or LangGraphSearchConfig()
        self._graph = None
        self._checkpointer = None

    def _get_checkpointer(self):
        """获取检查点存储"""
        if self._checkpointer is None:
            if self.config.checkpoint_type == "postgres":
                self._checkpointer = PostgresSaver.from_conn_string(
                    self.config.checkpoint_db_url
                )
            else:
                self._checkpointer = SqliteSaver.from_conn_string(
                    self.config.checkpoint_db_path
                )
        return self._checkpointer

    def _get_graph(self):
        """获取编译后的图"""
        if self._graph is None:
            builder = SearchGraphBuilder(self.config)
            self._graph = builder.compile(
                checkpointer=self._get_checkpointer()
            )
        return self._graph

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            options: 搜索选项

        Returns:
            搜索结果
        """
        graph = self._get_graph()

        # 生成唯一的 thread_id 用于状态追踪
        thread_id = str(uuid.uuid4())

        # 初始状态
        initial_state: SearchState = {
            "query": query,
            "user_id": user_id,
            "search_options": options or {},
            "log_id": thread_id,
            "status": "pending",
            "started_at": datetime.utcnow(),
            "needs_review": False,
            "review_completed": False,
            "cross_validation_done": False,
        }

        # 执行配置
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 执行图
        result = await graph.ainvoke(initial_state, config=config)

        return self._format_result(result)

    async def search_stream(
        self,
        query: str,
        user_id: Optional[str] = None,
        options: Optional[Dict] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式搜索

        Returns:
            异步迭代器，逐步返回搜索进度
        """
        graph = self._get_graph()
        thread_id = str(uuid.uuid4())

        initial_state: SearchState = {
            "query": query,
            "user_id": user_id,
            "search_options": options or {},
            "log_id": thread_id,
            "status": "pending",
            "started_at": datetime.utcnow(),
            "needs_review": False,
            "review_completed": False,
            "cross_validation_done": False,
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 流式执行
        async for event in graph.astream(initial_state, config=config):
            yield {
                "thread_id": thread_id,
                "event": event,
            }

    async def resume_with_review(
        self,
        thread_id: str,
        approved_urls: list,
        rejected_urls: list,
    ) -> Dict[str, Any]:
        """从人工审核恢复

        当搜索因人工审核而暂停时，使用此方法恢复
        """
        graph = self._get_graph()

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # 使用 Command 恢复执行
        result = await graph.ainvoke(
            Command(resume={
                "approved_urls": approved_urls,
                "rejected_urls": rejected_urls,
            }),
            config=config,
        )

        return self._format_result(result)

    async def get_state(self, thread_id: str) -> Dict[str, Any]:
        """获取搜索状态

        用于查询进行中或已完成的搜索状态
        """
        graph = self._get_graph()

        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        snapshot = graph.get_state(config)

        return {
            "thread_id": thread_id,
            "values": snapshot.values,
            "next": snapshot.next,
            "checkpoint_id": snapshot.config.get("configurable", {}).get("checkpoint_id"),
        }

    def _format_result(self, state: Dict) -> Dict[str, Any]:
        """格式化输出结果"""
        return {
            "log_id": state.get("log_id"),
            "status": state.get("status", "completed"),
            "query": state.get("query"),
            "parties": state.get("parties", []),
            "results": [
                {
                    "url": r.url,
                    "title": r.title,
                    "snippet": r.snippet,
                    "layer": r.layer,
                    "layer_name": r.layer_name,
                    "source_tier": r.source_tier,
                    "final_score": r.final_score,
                    "source_domain": r.source_domain,
                }
                for r in state.get("final_results", state.get("aggregated_results", []))
            ],
            "statistics": state.get("statistics", {}),
            "discovered_sources": {
                k: {
                    "party_name": v.party_name,
                    "official_gov": v.official_gov,
                    "official_agency": v.official_agency,
                    "local_mainstream": v.local_mainstream,
                }
                for k, v in state.get("discovered_sources", {}).items()
            },
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def _persist_to_database(
        self,
        state: Dict,
        task_id: str,
    ) -> None:
        """持久化搜索结果到数据库

        将 LangGraph 状态转换为数据库实体并存储

        存储策略:
        1. NLSearchLog: 存储 Claude 分析结果
        2. SearchResult: 存储每个搜索结果
        3. AggregatedSearchResult: 存储聚合后的结果
        """
        from src.services.langgraph_search.converters.result_converter import ResultConverter
        from src.services.langgraph_search.converters.aggregated_converter import AggregatedResultConverter
        from src.services.langgraph_search.converters.log_converter import SearchLogConverter

        # 获取 Repository 实例
        from src.infrastructure.database.repositories import (
            get_search_result_repository,
            get_aggregated_result_repository,
        )
        result_repo = get_search_result_repository()
        aggregated_repo = get_aggregated_result_repository()

        # 1. 保存搜索日志 (NLSearchLog)
        search_log = SearchLogConverter.create_search_log(
            query=state.get("query", ""),
            analysis=state.get("analysis", {}),
            parties=state.get("parties", []),
            keywords=state.get("keywords", []),
            time_range=state.get("time_range", "qdr:m"),
        )
        # Note: NLSearchLog 通过 SQLAlchemy 存储，此处省略实际保存代码

        # 2. 保存原始搜索结果 (SearchResult)
        layer_results = state.get("layer_results", {})
        for layer_id, layer_result in layer_results.items():
            if layer_result and layer_result.results:
                for lg_result in layer_result.results:
                    db_result = ResultConverter.to_db_search_result(
                        lg_result=lg_result,
                        task_id=task_id,
                    )
                    await result_repo.save(db_result)

        # 3. 保存聚合结果 (AggregatedSearchResult)
        aggregated_results = state.get("aggregated_results", [])
        for lg_result in aggregated_results:
            db_aggregated = AggregatedResultConverter.to_db_aggregated_result(
                lg_result=lg_result,
                smart_task_id=task_id,
                layer_results=layer_results,
            )
            await aggregated_repo.save(db_aggregated)
```

### 4.8 完整数据流示例

```python
# 完整数据流：从用户查询到数据库存储

async def complete_search_flow_example():
    """完整搜索流程示例

    展示数据如何从用户输入流转到数据库存储
    """
    from src.services.langgraph_search.service import LangGraphSearchService

    # 1. 初始化服务
    service = LangGraphSearchService()

    # 2. 执行搜索
    result = await service.search(
        query="美日韩联合军演最新动态",
        user_id="user_123",
    )

    # 3. 返回结果结构（兼容现有数据库格式）
    """
    result = {
        "log_id": "123456789012345678",  # 雪花算法ID

        # === 存储到 NLSearchLog ===
        "query": "美日韩联合军演最新动态",
        "parties": ["美国", "日本", "韩国"],

        # === 存储到 SearchResult / AggregatedSearchResult ===
        "results": [
            {
                "url": "https://www.defense.gov/...",
                "title": "US-Japan-Korea Joint Exercise",
                "snippet": "...",
                "layer": 0,                    # → metadata["layer"]
                "layer_name": "官方来源",       # → source
                "source_tier": 1,              # → metadata["source_tier"]
                "final_score": 0.92,           # → quality_score / composite_score
                "source_domain": "defense.gov", # → metadata["source_domain"]
            },
            # ... 更多结果
        ],

        # === 存储到 AggregatedSearchResult.metadata ===
        "statistics": {
            "total_results": 38,
            "by_layer": {
                "官方来源": 8,
                "主流媒体": 12,
                "周边地区": 10,
                "国际权威": 15,
                "智库分析": 5,
            },
            "deduplication_rate": 24,
        },

        # === 可选：存储到 metadata["discovered_sources"] ===
        "discovered_sources": {
            "美国": {
                "party_name": "美国",
                "official_gov": ["whitehouse.gov", "state.gov", "defense.gov"],
                "official_agency": ["apnews.com"],
                "local_mainstream": ["nytimes.com"],
            },
            "日本": {...},
            "韩国": {...},
        },

        "completed_at": "2025-01-08T12:00:00",
    }
    """
    return result
```

---

## 5. 配置管理

```python
# src/services/langgraph_search/config.py

from dataclasses import dataclass, field
from typing import Optional, List
import os


@dataclass
class LangGraphSearchConfig:
    """LangGraph 搜索配置"""

    # ===== Claude 配置 =====
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096

    # ===== Firecrawl 配置 =====
    firecrawl_api_key: str = field(
        default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", "")
    )
    firecrawl_timeout: int = 30

    # ===== 搜索配置 =====
    max_parties: int = 5               # 最大当事方数量
    max_domains_per_layer: int = 10    # 每层最大域名数
    results_per_query: int = 10        # 每次查询结果数

    # ===== 分层配置 =====
    enable_layer_0: bool = True        # 官方来源
    enable_layer_1: bool = True        # 主流媒体
    enable_layer_2: bool = True        # 周边地区
    enable_layer_3: bool = True        # 国际权威
    enable_layer_4: bool = True        # 智库分析

    # ===== 验证配置 =====
    enable_validation: bool = True
    min_results_for_validation: int = 5
    validation_threshold: float = 0.7

    # ===== 人工审核配置 =====
    enable_human_review: bool = False
    review_threshold: float = 0.5

    # ===== 源发现配置 =====
    verify_discovered_sources: bool = True

    # ===== 检查点配置 =====
    enable_checkpointing: bool = True
    checkpoint_type: str = "sqlite"    # sqlite | postgres
    checkpoint_db_path: str = "data/langgraph_checkpoints.db"
    checkpoint_db_url: str = field(
        default_factory=lambda: os.getenv("CHECKPOINT_DB_URL", "")
    )

    # ===== 性能配置 =====
    max_concurrent_searches: int = 5
    search_timeout: int = 60

    @classmethod
    def from_env(cls) -> "LangGraphSearchConfig":
        """从环境变量加载配置"""
        return cls(
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
            enable_validation=os.getenv("ENABLE_VALIDATION", "true").lower() == "true",
            enable_human_review=os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true",
            checkpoint_type=os.getenv("CHECKPOINT_TYPE", "sqlite"),
        )
```

---

## 6. API 集成

```python
# src/api/v1/endpoints/langgraph_search.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from src.services.langgraph_search.service import LangGraphSearchService
from src.services.langgraph_search.config import LangGraphSearchConfig

router = APIRouter(prefix="/langgraph-search", tags=["LangGraph Search"])

# 服务实例
_service: Optional[LangGraphSearchService] = None


def get_service() -> LangGraphSearchService:
    global _service
    if _service is None:
        config = LangGraphSearchConfig.from_env()
        _service = LangGraphSearchService(config)
    return _service


# ===== 请求/响应模型 =====

class SearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    log_id: str
    status: str
    query: str
    parties: List[str]
    results: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    discovered_sources: Dict[str, Any]


class ReviewRequest(BaseModel):
    thread_id: str
    approved_urls: List[str]
    rejected_urls: List[str]


# ===== API 端点 =====

@router.post("/search", response_model=SearchResponse)
async def create_search(request: SearchRequest):
    """创建搜索任务"""
    service = get_service()

    try:
        result = await service.search(
            query=request.query,
            user_id=request.user_id,
            options=request.options,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{thread_id}")
async def get_search_status(thread_id: str):
    """获取搜索状态"""
    service = get_service()

    try:
        state = await service.get_state(thread_id)
        return state
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/review")
async def submit_review(request: ReviewRequest):
    """提交人工审核结果"""
    service = get_service()

    try:
        result = await service.resume_with_review(
            thread_id=request.thread_id,
            approved_urls=request.approved_urls,
            rejected_urls=request.rejected_urls,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "4.0.0"}
```

---

## 7. 迁移路径

### 7.1 迁移阶段

```
┌─────────────────────────────────────────────────────────────────────┐
│                        迁移路径规划                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  阶段 1: 并行部署 (1-2 周)                                          │
│  ├─ 部署 LangGraph 搜索服务 (/langgraph-search/*)                  │
│  ├─ 保留原有服务 (/nl-search/*)                                     │
│  ├─ 通过 feature flag 控制流量                                      │
│  └─ 收集对比指标                                                    │
│                                                                     │
│  阶段 2: 灰度切换 (1-2 周)                                          │
│  ├─ 10% 流量切换到 LangGraph                                        │
│  ├─ 监控性能和质量指标                                              │
│  ├─ 逐步增加到 50%                                                  │
│  └─ 解决发现的问题                                                  │
│                                                                     │
│  阶段 3: 全量切换 (1 周)                                            │
│  ├─ 100% 流量切换到 LangGraph                                       │
│  ├─ 原服务保留为 fallback                                           │
│  └─ 稳定运行 1 周                                                   │
│                                                                     │
│  阶段 4: 清理 (1 周)                                                │
│  ├─ 移除原有搜索服务代码                                            │
│  ├─ 统一 API 端点                                                   │
│  └─ 更新文档                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 兼容性适配器

```python
# src/services/search_adapter.py

from typing import Dict, Any, Optional
import os

from src.services.nl_search.nl_search_service import NLSearchService
from src.services.langgraph_search.service import LangGraphSearchService


class SearchServiceAdapter:
    """搜索服务适配器

    在迁移期间提供统一接口，支持在两种实现之间切换
    """

    def __init__(self):
        self.use_langgraph = os.getenv("USE_LANGGRAPH_SEARCH", "false").lower() == "true"
        self.langgraph_ratio = float(os.getenv("LANGGRAPH_RATIO", "0"))

        self._nl_search = None
        self._langgraph = None

    @property
    def nl_search(self) -> NLSearchService:
        if self._nl_search is None:
            self._nl_search = NLSearchService()
        return self._nl_search

    @property
    def langgraph(self) -> LangGraphSearchService:
        if self._langgraph is None:
            self._langgraph = LangGraphSearchService()
        return self._langgraph

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """执行搜索

        根据配置决定使用哪个实现
        """
        import random

        # 根据比例决定使用哪个服务
        use_langgraph = (
            self.use_langgraph or
            random.random() < self.langgraph_ratio
        )

        if use_langgraph:
            try:
                result = await self.langgraph.search(query, user_id, kwargs)
                result["_backend"] = "langgraph"
                return result
            except Exception as e:
                # Fallback 到原服务
                print(f"LangGraph 搜索失败，回退到原服务: {e}")

        result = await self.nl_search.create_search(query, user_id, **kwargs)
        result["_backend"] = "nl_search"
        return result
```

---

## 8. 测试策略

### 8.1 单元测试

```python
# tests/unit/services/test_langgraph_search.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.langgraph_search.nodes.query_analyzer import QueryAnalyzerNode
from src.services.langgraph_search.nodes.source_discovery import SourceDiscoveryNode
from src.services.langgraph_search.config import LangGraphSearchConfig


@pytest.fixture
def config():
    return LangGraphSearchConfig()


class TestQueryAnalyzerNode:
    @pytest.mark.asyncio
    async def test_analyze_simple_query(self, config):
        node = QueryAnalyzerNode(config)
        node.llm = AsyncMock()
        node.llm.ainvoke.return_value = MagicMock(
            content='{"intent": "news", "parties": ["美国"], "keywords": ["科技"], "suggested_time_range": "w", "confidence": 0.9}'
        )

        state = {"query": "美国最新科技新闻"}
        result = await node(state)

        assert "parties" in result
        assert "美国" in result["parties"]
        assert result["time_range"] == "qdr:w"

    @pytest.mark.asyncio
    async def test_analyze_complex_query(self, config):
        node = QueryAnalyzerNode(config)
        node.llm = AsyncMock()
        node.llm.ainvoke.return_value = MagicMock(
            content='{"intent": "geopolitics", "parties": ["美国", "日本", "韩国"], "keywords": ["军演", "联合"], "suggested_time_range": "m", "confidence": 0.85}'
        )

        state = {"query": "美日韩联合军演最新动态"}
        result = await node(state)

        assert len(result["parties"]) == 3
        assert "军演" in result["keywords"]


class TestSourceDiscoveryNode:
    @pytest.mark.asyncio
    async def test_discover_us_sources(self, config):
        node = SourceDiscoveryNode(config)
        node.llm = AsyncMock()
        node.llm.ainvoke.return_value = MagicMock(
            content='{"party_name": "美国", "party_type": "country", "party_code": "US", "official_gov": ["whitehouse.gov", "state.gov"], "official_agency": ["reuters.com"], "local_mainstream": ["nytimes.com"], "primary_language": "en", "confidence": 0.9}'
        )
        node.firecrawl = AsyncMock()

        state = {"query": "美国政策", "parties": ["美国"]}
        result = await node(state)

        assert "美国" in result["discovered_sources"]
        source = result["discovered_sources"]["美国"]
        assert "whitehouse.gov" in source.official_gov
```

### 8.2 集成测试

```python
# tests/integration/test_langgraph_search_e2e.py

import pytest
from src.services.langgraph_search.service import LangGraphSearchService
from src.services.langgraph_search.config import LangGraphSearchConfig


@pytest.fixture
def service():
    config = LangGraphSearchConfig(
        enable_checkpointing=False,
        enable_human_review=False,
    )
    return LangGraphSearchService(config)


class TestLangGraphSearchE2E:
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_search_flow(self, service):
        """测试完整搜索流程"""
        result = await service.search(
            query="美日韩联合军演 2025",
            user_id="test_user",
        )

        assert result["status"] == "completed"
        assert len(result["results"]) > 0
        assert "statistics" in result

        # 验证分层结果
        layers_found = set(r["layer"] for r in result["results"])
        assert len(layers_found) >= 2  # 至少应有2层结果

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_source_discovery(self, service):
        """测试源发现功能"""
        result = await service.search(
            query="日本政府对华政策声明",
        )

        assert "discovered_sources" in result
        # 应该发现日本相关的官方来源
        if "日本" in result["discovered_sources"]:
            jp_sources = result["discovered_sources"]["日本"]
            assert len(jp_sources.get("official_gov", [])) > 0
```

---

## 9. 监控与可观测性

### 9.1 指标收集

```python
# src/services/langgraph_search/metrics.py

from prometheus_client import Counter, Histogram, Gauge
import time

# 搜索计数器
search_total = Counter(
    "langgraph_search_total",
    "Total number of searches",
    ["status", "backend"]
)

# 搜索延迟
search_latency = Histogram(
    "langgraph_search_latency_seconds",
    "Search latency in seconds",
    ["layer"]
)

# 结果数量
results_count = Histogram(
    "langgraph_search_results_count",
    "Number of results per search",
    ["layer"]
)

# 源发现成功率
source_discovery_success = Counter(
    "langgraph_source_discovery_total",
    "Source discovery attempts",
    ["party", "status"]
)

# 活跃搜索数
active_searches = Gauge(
    "langgraph_active_searches",
    "Number of active searches"
)
```

### 9.2 日志结构

```python
# src/services/langgraph_search/logging.py

import structlog
from typing import Dict, Any

logger = structlog.get_logger()


def log_search_start(thread_id: str, query: str, user_id: str = None):
    logger.info(
        "search_started",
        thread_id=thread_id,
        query=query[:100],
        user_id=user_id,
    )


def log_layer_search(thread_id: str, layer: int, layer_name: str, results_count: int, duration_ms: int):
    logger.info(
        "layer_search_completed",
        thread_id=thread_id,
        layer=layer,
        layer_name=layer_name,
        results_count=results_count,
        duration_ms=duration_ms,
    )


def log_search_complete(thread_id: str, total_results: int, duration_ms: int, statistics: Dict):
    logger.info(
        "search_completed",
        thread_id=thread_id,
        total_results=total_results,
        duration_ms=duration_ms,
        **statistics,
    )


def log_error(thread_id: str, error: str, context: Dict = None):
    logger.error(
        "search_error",
        thread_id=thread_id,
        error=error,
        context=context or {},
    )
```

---

## 10. 多用户数据隔离架构

### 10.1 架构总览

多用户环境下，LangGraph 搜索系统需要在各层实现数据隔离，确保用户数据安全和访问控制。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     多用户数据隔离架构 (v4.0.0)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  API 层 (FastAPI)                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  JWT 认证 → get_current_user() → user_id 注入到所有请求          │   │
│  │  ✅ 端点级权限检查                                               │   │
│  │  ✅ thread_id 归属验证                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  Service 层 (LangGraph)                                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  SearchState.user_id ← 强制从认证层传入                          │   │
│  │  thread_id = f"user_{user_id}_search_{uuid}"                    │   │
│  │  ✅ Checkpointer 命名空间隔离                                    │   │
│  │  ✅ 并行执行相互独立                                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  Converter 层                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ResultConverter.to_db_search_result(lg_result, task_id, user_id)│   │
│  │  AggregatedResultConverter.to_db_aggregated_result(..., user_id) │   │
│  │  ✅ 强制 user_id 参数                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  数据库层 (MongoDB)                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  SearchTask         { created_by: user_id, ... }                │   │
│  │  SearchResult       { user_id: user_id, task_id, ... }  🆕      │   │
│  │  AggregatedResult   { user_id: user_id, smart_task_id, ... } 🆕 │   │
│  │  ✅ 复合索引 (user_id, created_at)                               │   │
│  │  ✅ 所有查询默认携带 user_id 条件                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.2 现有实体用户隔离分析

**当前状态评估**:

| 实体 | 用户字段 | 状态 | 问题 |
|------|----------|------|------|
| SearchTask | created_by | ✅ 已有 | 无 |
| SearchResult | 无 | ❌ 缺失 | 需要通过 Task 间接关联 |
| AggregatedSearchResult | 无 | ❌ 缺失 | 需要通过 SmartTask 间接关联 |

**间接关联的问题**:
1. 查询效率低 - 需要 JOIN 两张表
2. 无法直接在结果集合上按用户过滤
3. 无法实施数据库层面的行级安全

### 10.3 实体修改方案

#### SearchResult 实体更新

```python
# src/core/domain/entities/search_result.py

@dataclass
class SearchResult:
    """搜索结果实体

    v4.0.0 更新: 添加 user_id 字段支持多用户隔离
    """
    id: str
    task_id: str
    user_id: str  # 🆕 新增字段 - 用户ID

    # 核心字段
    title: str
    url: str
    snippet: str

    # 来源信息
    source: str
    language: str
    published_date: Optional[datetime]

    # 内容
    markdown_content: Optional[str]
    html_content: Optional[str]

    # 评分
    relevance_score: float
    quality_score: float

    # 元数据
    metadata: Dict[str, Any]
    status: ResultStatus
    created_at: datetime
```

#### AggregatedSearchResult 实体更新

```python
# src/core/domain/entities/aggregated_search_result.py

@dataclass
class AggregatedSearchResult:
    """聚合搜索结果实体

    v4.0.0 更新: 添加 user_id 字段支持多用户隔离
    """
    id: str
    smart_task_id: str
    user_id: str  # 🆕 新增字段 - 用户ID

    # 基础字段
    title: str
    url: str
    content: str
    snippet: str

    # 聚合评分
    composite_score: float
    avg_relevance_score: float
    avg_quality_score: float

    # 多源信息
    sources: List[SourceInfo]
    source_count: int

    # 状态
    status: ResultStatus
    created_at: datetime
    updated_at: datetime
```

### 10.4 MongoDB 索引设计

```python
# scripts/init_user_isolation_indexes.py

async def create_user_isolation_indexes(db):
    """创建用户隔离所需的索引"""

    # search_results 集合索引
    await db.search_results.create_index([
        ("user_id", 1),
        ("created_at", -1)
    ], name="idx_user_created")

    await db.search_results.create_index([
        ("user_id", 1),
        ("task_id", 1)
    ], name="idx_user_task")

    await db.search_results.create_index([
        ("user_id", 1),
        ("status", 1),
        ("created_at", -1)
    ], name="idx_user_status_created")

    # aggregated_search_results 集合索引
    await db.aggregated_search_results.create_index([
        ("user_id", 1),
        ("created_at", -1)
    ], name="idx_user_created")

    await db.aggregated_search_results.create_index([
        ("user_id", 1),
        ("smart_task_id", 1)
    ], name="idx_user_smart_task")

    print("✅ 用户隔离索引创建完成")
```

### 10.5 LangGraph 状态隔离

#### 安全的 thread_id 生成

```python
# src/services/langgraph_search/utils/thread_id.py

import uuid
from datetime import datetime


def generate_secure_thread_id(user_id: str, operation: str = "search") -> str:
    """生成包含用户标识的安全 thread_id

    格式: user_{user_id}_{operation}_{timestamp}_{random}

    Args:
        user_id: 用户ID (雪花算法ID)
        operation: 操作类型 (search, resume, etc.)

    Returns:
        安全的 thread_id

    Example:
        >>> generate_secure_thread_id("123456789", "search")
        'user_123456789_search_20250108120000_a1b2c3d4'
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_part = str(uuid.uuid4())[:8]
    return f"user_{user_id}_{operation}_{timestamp}_{random_part}"


def validate_thread_id_ownership(thread_id: str, user_id: str) -> bool:
    """验证 thread_id 是否属于指定用户

    Args:
        thread_id: 待验证的 thread_id
        user_id: 当前用户ID

    Returns:
        是否归属当前用户
    """
    expected_prefix = f"user_{user_id}_"
    return thread_id.startswith(expected_prefix)


def extract_user_id_from_thread_id(thread_id: str) -> str:
    """从 thread_id 中提取用户ID

    Args:
        thread_id: 格式为 user_{user_id}_{operation}_{...} 的 thread_id

    Returns:
        用户ID

    Raises:
        ValueError: 如果 thread_id 格式无效
    """
    if not thread_id.startswith("user_"):
        raise ValueError(f"Invalid thread_id format: {thread_id}")

    parts = thread_id.split("_")
    if len(parts) < 3:
        raise ValueError(f"Invalid thread_id format: {thread_id}")

    return parts[1]
```

#### 更新后的 Service 层

```python
# src/services/langgraph_search/service.py (更新)

class LangGraphSearchService:
    """LangGraph 搜索服务 - 支持多用户隔离"""

    async def search(
        self,
        query: str,
        user_id: str,  # 必需参数
        options: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID (必需，用于数据隔离)
            options: 搜索选项

        Returns:
            搜索结果

        Raises:
            ValueError: 如果 user_id 为空
        """
        if not user_id:
            raise ValueError("user_id is required for search operations")

        graph = self._get_graph()

        # 使用安全的 thread_id 格式
        thread_id = generate_secure_thread_id(user_id, "search")

        initial_state: SearchState = {
            "query": query,
            "user_id": user_id,  # ✅ 强制传入用户ID
            "search_options": options or {},
            "log_id": thread_id,
            "status": "pending",
            "started_at": datetime.utcnow(),
            # ...
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_namespace": user_id,  # ✅ 命名空间隔离
            }
        }

        result = await graph.ainvoke(initial_state, config=config)

        # 持久化时传递 user_id
        await self._persist_to_database(result, thread_id, user_id)

        return self._format_result(result)

    async def get_state(
        self,
        thread_id: str,
        user_id: str,  # 必需参数
    ) -> Dict[str, Any]:
        """获取搜索状态

        Args:
            thread_id: 搜索线程ID
            user_id: 当前用户ID (用于权限验证)

        Returns:
            搜索状态

        Raises:
            PermissionError: 如果 thread_id 不属于当前用户
        """
        # ✅ 验证 thread_id 归属
        if not validate_thread_id_ownership(thread_id, user_id):
            raise PermissionError(
                f"User {user_id} does not have access to thread {thread_id}"
            )

        graph = self._get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)

        return {
            "thread_id": thread_id,
            "values": snapshot.values,
            "next": snapshot.next,
        }
```

### 10.6 API 层权限控制

```python
# src/api/v1/endpoints/langgraph_search.py (更新)

from fastapi import APIRouter, HTTPException, Depends
from src.api.deps import get_current_user
from src.core.domain.entities.auth.user import User

router = APIRouter(prefix="/langgraph-search", tags=["LangGraph Search"])


@router.post("/search", response_model=SearchResponse)
async def create_search(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),  # ✅ 强制认证
):
    """创建搜索任务

    用户ID从 JWT Token 中获取，不允许前端指定
    """
    service = get_service()

    try:
        result = await service.search(
            query=request.query,
            user_id=current_user.id,  # ✅ 使用认证用户ID
            options=request.options,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{thread_id}")
async def get_search_status(
    thread_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取搜索状态

    自动验证 thread_id 归属当前用户
    """
    service = get_service()

    try:
        state = await service.get_state(
            thread_id=thread_id,
            user_id=current_user.id,  # ✅ 传递用户ID用于验证
        )
        return state
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="无权访问此搜索状态"
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/results")
async def get_user_results(
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
):
    """获取当前用户的搜索结果

    自动按用户ID过滤，只返回当前用户的结果
    """
    repo = get_result_repository()

    results = await repo.find_by_user(
        user_id=current_user.id,  # ✅ 自动按用户过滤
        skip=skip,
        limit=limit,
    )
    return results
```

### 10.7 Repository 层查询隔离

```python
# src/infrastructure/persistence/repositories/mongo/search_result_repository.py

class SearchResultRepository:
    """搜索结果仓储 - 支持用户隔离"""

    async def find_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status: Optional[ResultStatus] = None,
    ) -> List[SearchResult]:
        """按用户查询搜索结果

        Args:
            user_id: 用户ID
            skip: 跳过条数
            limit: 返回条数
            status: 结果状态过滤

        Returns:
            用户的搜索结果列表
        """
        query = {"user_id": user_id}
        if status:
            query["status"] = status.value

        cursor = self.collection.find(query).sort(
            "created_at", -1
        ).skip(skip).limit(limit)

        return [self._to_entity(doc) async for doc in cursor]

    async def find_by_id_and_user(
        self,
        id: str,
        user_id: str,
    ) -> Optional[SearchResult]:
        """按ID和用户查询单个结果

        Args:
            id: 结果ID
            user_id: 用户ID (用于权限验证)

        Returns:
            搜索结果，如果不存在或不属于该用户则返回 None
        """
        doc = await self.collection.find_one({
            "id": id,
            "user_id": user_id,  # ✅ 同时验证用户归属
        })
        return self._to_entity(doc) if doc else None

    async def count_by_user(self, user_id: str) -> int:
        """统计用户的结果数量"""
        return await self.collection.count_documents({"user_id": user_id})
```

### 10.8 数据迁移脚本

```python
# scripts/migrate_user_id_to_results.py

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


async def migrate_user_id():
    """为现有搜索结果填充 user_id 字段

    从关联的 SearchTask.created_by 获取用户ID
    """
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.guanshan_db

    # 1. 迁移 search_results
    print("开始迁移 search_results...")
    migrated_results = 0

    async for result in db.search_results.find({"user_id": {"$exists": False}}):
        task = await db.search_tasks.find_one({"id": result["task_id"]})
        if task and task.get("created_by"):
            await db.search_results.update_one(
                {"_id": result["_id"]},
                {"$set": {"user_id": task["created_by"]}}
            )
            migrated_results += 1

    print(f"✅ search_results 迁移完成: {migrated_results} 条")

    # 2. 迁移 aggregated_search_results
    print("开始迁移 aggregated_search_results...")
    migrated_aggregated = 0

    async for result in db.aggregated_search_results.find({"user_id": {"$exists": False}}):
        task = await db.smart_tasks.find_one({"id": result["smart_task_id"]})
        if task and task.get("created_by"):
            await db.aggregated_search_results.update_one(
                {"_id": result["_id"]},
                {"$set": {"user_id": task["created_by"]}}
            )
            migrated_aggregated += 1

    print(f"✅ aggregated_search_results 迁移完成: {migrated_aggregated} 条")

    # 3. 验证迁移结果
    no_user_results = await db.search_results.count_documents({"user_id": {"$exists": False}})
    no_user_aggregated = await db.aggregated_search_results.count_documents({"user_id": {"$exists": False}})

    if no_user_results == 0 and no_user_aggregated == 0:
        print("✅ 所有数据迁移完成")
    else:
        print(f"⚠️ 仍有未迁移数据: results={no_user_results}, aggregated={no_user_aggregated}")


if __name__ == "__main__":
    asyncio.run(migrate_user_id())
```

### 10.9 实施清单

| 序号 | 任务 | 优先级 | 风险 | 状态 |
|------|------|--------|------|------|
| 1 | SearchResult 实体添加 user_id 字段 | P0 | 低 | 待实施 |
| 2 | AggregatedSearchResult 实体添加 user_id 字段 | P0 | 低 | 待实施 |
| 3 | 创建 MongoDB 用户隔离索引 | P0 | 低 | 待实施 |
| 4 | 实现 generate_secure_thread_id 工具函数 | P0 | 低 | 待实施 |
| 5 | 更新 ResultConverter 添加 user_id 参数 | P0 | 低 | 待实施 |
| 6 | 更新 AggregatedResultConverter 添加 user_id 参数 | P0 | 低 | 待实施 |
| 7 | 更新 LangGraphSearchService 传递 user_id | P0 | 低 | 待实施 |
| 8 | 更新 API 端点强制认证和权限检查 | P1 | 中 | 待实施 |
| 9 | 更新 Repository 添加用户过滤方法 | P0 | 低 | 待实施 |
| 10 | 执行历史数据迁移脚本 | P1 | 中 | 待实施 |
| 11 | 编写多用户隔离集成测试 | P2 | 低 | 待实施 |

### 10.10 验证检查点

**数据写入验证**:
- [ ] 新 SearchResult 必须携带 user_id，否则写入失败
- [ ] 新 AggregatedSearchResult 必须携带 user_id，否则写入失败
- [ ] thread_id 格式必须包含 user_id 前缀

**数据查询验证**:
- [ ] 查询 API 自动注入当前认证用户的 user_id
- [ ] 无法查询其他用户的搜索结果
- [ ] 跨用户数据访问返回 403 Forbidden

**状态管理验证**:
- [ ] get_state 验证 thread_id 归属当前用户
- [ ] resume_with_review 验证操作权限

---

## 11. 时间表与资源

### 11.1 实施时间表

| 阶段 | 任务 | 预计工期 | 依赖 |
|------|------|----------|------|
| **Week 1-2** | 核心框架搭建 | 2 周 | 无 |
| | - 状态模型设计 | 2 天 | |
| | - Graph 结构实现 | 3 天 | 状态模型 |
| | - 查询分析节点 | 2 天 | Graph 结构 |
| | - 源发现节点 | 3 天 | 查询分析 |
| **Week 3-4** | 分层搜索实现 | 2 周 | 核心框架 |
| | - Layer 0-1 (site: 搜索) | 3 天 | |
| | - Layer 2 (多语言) | 2 天 | |
| | - Layer 3-4 (通用/专业) | 2 天 | |
| | - 聚合节点 | 2 天 | 分层搜索 |
| **Week 5** | 增强功能 | 1 周 | 分层搜索 |
| | - 验证节点 | 2 天 | |
| | - 人工审核 | 2 天 | |
| | - 检查点集成 | 1 天 | |
| **Week 6** | API 集成与测试 | 1 周 | 增强功能 |
| | - API 端点 | 2 天 | |
| | - 单元测试 | 2 天 | |
| | - 集成测试 | 1 天 | |
| **Week 7-8** | 迁移与优化 | 2 周 | 测试完成 |
| | - 并行部署 | 3 天 | |
| | - 灰度切换 | 1 周 | 并行部署 |
| | - 性能优化 | 4 天 | |

### 11.2 资源需求

| 资源 | 规格 | 用途 |
|------|------|------|
| **开发人员** | 1-2 人 | 核心开发 |
| **Claude API** | Sonnet 4.5 | 查询分析、源发现 |
| **Firecrawl API** | 标准配额 | 搜索和抓取 |
| **PostgreSQL** | 可选 | 检查点存储 (生产) |
| **SQLite** | 本地 | 检查点存储 (开发) |

---

## 12. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| LangGraph 学习曲线 | 中 | 中 | 预留培训时间，从简单功能开始 |
| 并行搜索性能问题 | 中 | 高 | 设置超时和并发限制 |
| Claude API 限流 | 中 | 高 | 实现缓存和重试机制 |
| 状态管理复杂性 | 低 | 中 | 使用 Checkpointer 持久化 |
| 迁移期间服务中断 | 低 | 高 | 保留 fallback，灰度切换 |

---

## 13. 附录

### A. 参考资料

1. LangGraph 官方文档: https://langchain-ai.github.io/langgraph/
2. LangGraph Multi-Agent 示例: https://github.com/langchain-ai/langgraph/tree/main/examples
3. Tool_for_osint 项目: `~/Downloads/Tool_for_osint/`

### B. 相关文档

1. `docs/search_upgrade/requirements.md` - 搜索升级需求文档
2. `src/services/nl_search/` - 当前搜索服务实现

### C. 版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v1.0.0 | 2025-01-08 | Claude | 初始版本 |
| v1.1.0 | 2025-01-08 | Claude | 添加数据库字段映射 (3.1.1) 和完整数据流示例 (4.8) |
| v1.2.0 | 2025-01-08 | Claude | 添加多用户数据隔离架构 (第10章) |
| v2.0.0 | 2025-01-08 | Claude | **LangGraph 模块实现** - 完成核心模块开发 |
| v4.1.0 | 2025-01-08 | Claude | **Chat API 集成** - SearchEngineAdapter，配置化引擎切换 |

## 11. v2.0.0 实现详情 / Implementation Details

### 11.1 模块结构 / Module Structure

```
src/services/langgraph_search/
├── __init__.py              # 模块入口，导出主要类
├── state.py                 # SearchState 状态模型
├── config.py                # LangGraphSearchConfig 配置
├── graph.py                 # StateGraph 构建器
├── service.py               # LangGraphSearchService 主服务
├── converters/              # 数据转换器
│   ├── __init__.py
│   ├── result_converter.py  # SearchResult 转换
│   └── aggregated_converter.py  # AggregatedSearchResult 转换
├── nodes/                   # 图节点实现
│   ├── __init__.py
│   ├── query_analyzer.py    # 查询分析节点
│   ├── source_discovery.py  # 来源发现节点
│   ├── layer_search.py      # 分层搜索节点
│   ├── aggregator.py        # 结果聚合节点
│   ├── validator.py         # 结果验证节点
│   └── output.py            # 输出格式化节点
└── utils/                   # 工具函数
    ├── __init__.py
    ├── thread_id.py         # 线程ID生成与验证
    └── url_utils.py         # URL规范化工具
```

### 11.2 多用户数据隔离实现 / Multi-User Data Isolation

#### 11.2.1 实体更新 / Entity Updates

**SearchResult 实体** (`src/core/domain/entities/search_result.py`):
```python
# v2.0.0: 多用户数据隔离字段
user_id: str = ""      # 所属用户ID（用于数据隔离查询）
created_by: str = ""   # 创建者用户ID（记录操作者）
```

**AggregatedSearchResult 实体** (`src/core/domain/entities/aggregated_search_result.py`):
```python
# v2.0.0: 多用户数据隔离字段
user_id: str = ""      # 所属用户ID
created_by: str = ""   # 创建者用户ID
```

#### 11.2.2 线程ID安全机制 / Thread ID Security

```python
# 生成格式: user_{user_id}_{operation}_{timestamp}_{random}
thread_id = generate_secure_thread_id(user_id="12345", operation="search")
# 示例: user_12345_search_20250108_a1b2c3d4

# 验证所有权
is_owner = validate_thread_id_ownership(thread_id, user_id="12345")

# 提取用户ID
extracted_user_id = extract_user_id_from_thread_id(thread_id)
```

### 11.3 关键API / Key APIs

#### 11.3.1 执行搜索 / Execute Search
```python
service = LangGraphSearchService()
result = await service.execute_search(
    query="中美贸易谈判最新进展",
    user_id="12345",  # 必需参数
    options={"enable_layer_0": True}
)
```

#### 11.3.2 流式搜索 / Stream Search
```python
async for event in service.stream_search(query, user_id):
    print(f"Node: {event['node']}, Status: {event['status']}")
```

#### 11.3.3 恢复搜索 / Resume Search
```python
result = await service.resume_search(
    thread_id="user_12345_search_...",
    user_id="12345"
)
```

### 11.4 测试覆盖 / Test Coverage

| 测试模块 | 测试数量 | 状态 |
|---------|---------|------|
| test_thread_id.py | 25 | ✅ 通过 |
| test_url_utils.py | 25 | ✅ 通过 |
| test_state.py | 16 | ✅ 通过 |
| 其他测试 | 9 | ✅ 通过 |
| **总计** | **75** | **✅ 全部通过** |

### 11.5 依赖处理 / Dependency Handling

LangGraph 依赖采用可选导入模式，确保模块在未安装 langgraph 时不会崩溃：

```python
try:
    from langgraph.graph import StateGraph, END, START
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    HAS_SQLITE_SAVER = True
except ImportError:
    HAS_SQLITE_SAVER = False
```

### 11.6 下一步计划 / Next Steps

1. ~~**API端点**: 创建 FastAPI 路由端点~~ ✅ v4.1.0 已完成
2. **集成测试**: 添加端到端集成测试
3. **文档完善**: 添加 API 文档和使用示例
4. **性能优化**: 实现结果缓存和并行搜索

---

## 12. v4.1.0 Chat API 集成 / Chat API Integration

### 12.1 SearchEngineAdapter 架构 / Adapter Architecture

**文件**: `src/services/search_engine_adapter.py`

```python
# 配置枚举
class SearchEngine(str, Enum):
    NL_SEARCH = "nl_search"      # 原有 NL Search 服务
    LANGGRAPH = "langgraph"      # 新 LangGraph 搜索服务

# 适配器提供统一接口
search_engine_adapter = SearchEngineAdapter()
result = await search_engine_adapter.search(
    query="搜索内容",
    user_id="12345",
    search_mode="single"
)
```

### 12.2 配置方式 / Configuration

**环境变量**:
```bash
# 选择搜索引擎 (默认: nl_search)
SEARCH_ENGINE=langgraph

# 启用自动回退 (默认: true)
SEARCH_ENGINE_FALLBACK=true

# LangGraph 检查点 (默认: false)
LANGGRAPH_ENABLE_CHECKPOINTING=true
```

### 12.3 Chat Endpoint 更新 / Endpoint Updates

**文件**: `src/api/v1/endpoints/chat.py`

**变更**:
- 导入 `search_engine_adapter`
- 替换 `nl_search_service.create_search()` → `search_engine_adapter.search()`
- 添加引擎状态日志
- 错误处理和自动回退

**v4.0.0 更新内容**:
```python
# 使用搜索引擎适配器
result = await search_engine_adapter.search(
    query=request.question,
    user_id=str(current_user.id),
    search_mode=request.search_mode,
)

# 检查搜索是否成功
if not result.get("success", True):
    error_msg = result.get("error", "搜索失败")
    raise HTTPException(status_code=500, detail=f"搜索失败: {error_msg}")
```

### 12.4 回退机制 / Fallback Mechanism

当 LangGraph 搜索失败时，自动回退到 NL Search:

```
LangGraph 搜索 → 失败 → 检查 SEARCH_ENGINE_FALLBACK
                          ↓
                    enabled=true → NL Search 回退
                          ↓
                    enabled=false → 返回错误
```

### 12.5 结果格式转换 / Result Format Conversion

LangGraph 结果会自动转换为标准格式:

| LangGraph 字段 | 标准字段 | 说明 |
|---------------|---------|------|
| thread_id | log_id | 搜索标识 |
| results | results | 搜索结果列表 |
| statistics | analysis | 分析数据 |
| status | langgraph_status | 执行状态 |

### 12.6 版本历史更新 / Version History

| 版本 | 日期 | 变更 |
|------|------|------|
| v4.0.0 | 2025-01-08 | LangGraph 模块实现 |
| v4.1.0 | 2025-01-08 | Chat API 集成，SearchEngineAdapter |
