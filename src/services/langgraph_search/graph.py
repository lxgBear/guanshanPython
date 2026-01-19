"""LangGraph 搜索图构建器 (v4.16.0)

提供搜索架构的 StateGraph 构建器。

## 架构版本

### v4.16.0 两步架构（默认）- TwoStepSearchGraphBuilder
START → keyword_generator → firecrawl_config → simplified_search → intent_filter → output → END

特点：
- 关键词生成和搜索配置分离
- 6 步关键词分析：理解意图 → 确认事件 → 提取关键词 → 理解关键词 → 组合搜索词 → 补充说明
- 优先级分层：Tier 1 (核心) / Tier 2 (重要) / Tier 3 (补充)
- 意图筛选：URL去重 + Claude LLM 意图匹配过滤

### 完整架构（备用）- SearchGraphBuilder
START → query_analyzer → source_discovery → [layer_searches || PARALLEL] → aggregator → validator → output → END

Layer Searches (并行):
- layer_0_search (官方来源)
- layer_1_search (主流媒体)
- layer_2_search (周边地区)
- layer_3_search (国际权威)
- layer_4_search (智库分析)
"""

import logging
from typing import Dict, Any, List, Optional, Literal

try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.types import Send
    HAS_LANGGRAPH = True
except ImportError:
    StateGraph = None
    END = None
    START = None
    Send = None
    HAS_LANGGRAPH = False

try:
    from langgraph.checkpoint.base import BaseCheckpointSaver
except ImportError:
    BaseCheckpointSaver = None

from .state import SearchState
from .config import LangGraphSearchConfig
from .nodes import (
    # v4.17.0: 两步关键词生成架构
    KeywordGeneratorNode,
    create_keyword_generator_node,
    FirecrawlConfigNode,
    create_firecrawl_config_node,
    SimplifiedSearchNode,
    create_simplified_search_node,
    RetrySearchNode,
    create_retry_search_node,
    IntentFilterNode,
    create_intent_filter_node,
    # 完整架构节点
    QueryAnalyzerNode,
    SourceDiscoveryNode,
    LayerSearchNode,
    AggregatorNode,
    ValidatorNode,
    OutputNode,
)
from .nodes.layer_search import create_layer_search_nodes
from .feature_flags import FeatureFlags

logger = logging.getLogger(__name__)


def route_to_parallel_layers(state: SearchState) -> List[Send]:
    """将搜索任务并行分发到多个层级

    使用 LangGraph Send API 实现并行执行

    Args:
        state: 当前搜索状态

    Returns:
        Send 对象列表，每个指向一个层级搜索节点
    """
    enabled_layers = list(state.get("enabled_layers", [0, 1, 2, 3, 4]))
    user_id = state.get("user_id", "")
    logger.info(f"[user:{user_id}] Routing to parallel layers: {enabled_layers}")

    # 为每个启用的层级创建 Send 对象
    return [
        Send(f"layer_{layer}_search", state)
        for layer in enabled_layers
    ]


class SearchGraphBuilder:
    """搜索图构建器（完整 5 层架构）

    构建基于 LangGraph 的 5 层分层搜索图。

    Features:
    - 动态层级启用/禁用
    - 并行层级搜索
    - 可配置的检查点
    - 多用户数据隔离

    注意：推荐使用 TwoStepSearchGraphBuilder（v4.11.0 两步架构）
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        firecrawl_client: Optional[Any] = None,
        anthropic_client: Optional[Any] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        """初始化图构建器

        Args:
            config: LangGraph 搜索配置
            firecrawl_client: Firecrawl 客户端
            anthropic_client: Anthropic 客户端（保留兼容性）
            checkpointer: 检查点保存器（用于状态持久化）
        """
        self.config = config or LangGraphSearchConfig()
        self.firecrawl_client = firecrawl_client
        self.checkpointer = checkpointer
        # 创建节点实例
        self._init_nodes()

    def _init_nodes(self) -> None:
        """初始化所有节点"""
        # 查询分析节点（规则化处理）
        self.query_analyzer = QueryAnalyzerNode(config=self.config)

        # 来源发���节点
        self.source_discovery = SourceDiscoveryNode(
            config=self.config,
        )

        # 分层搜索节点
        self.layer_search_nodes = create_layer_search_nodes(
            config=self.config,
            firecrawl_client=self.firecrawl_client,
        )

        # 聚合节点
        self.aggregator = AggregatorNode(config=self.config)

        # 验证节点
        self.validator = ValidatorNode(config=self.config)

        # 输出节点
        self.output = OutputNode(config=self.config)

    def build(self) -> Any:
        """构建搜索状态图

        Returns:
            编译后的 StateGraph

        Raises:
            ImportError: 如果 LangGraph 未安装
        """
        if not HAS_LANGGRAPH or StateGraph is None:
            raise ImportError(
                "LangGraph is not installed. Please install it with: "
                "pip install langgraph"
            )

        logger.info("[FullGraph] Building 5-layer search graph...")

        # 创建状态图
        graph = StateGraph(SearchState)

        # 添加核心节点
        graph.add_node("query_analyzer", self.query_analyzer)
        graph.add_node("source_discovery", self.source_discovery)

        # 添加分层搜索节点
        for layer, node in self.layer_search_nodes.items():
            graph.add_node(f"layer_{layer}_search", node)

        # 添加后处理节点
        graph.add_node("aggregator", self.aggregator)
        graph.add_node("validator", self.validator)
        graph.add_node("output", self.output)

        # 设置入口边: START → query_analyzer → ...
        graph.add_edge(START, "query_analyzer")
        graph.add_edge("query_analyzer", "source_discovery")

        # 从 source_discovery 到所有启用的层级搜索 (并行执行)
        enabled_layers = list(self.layer_search_nodes.keys())
        if enabled_layers:
            # 使用条件边实现并行分发 (Send API)
            graph.add_conditional_edges(
                "source_discovery",
                route_to_parallel_layers,
                [f"layer_{layer}_search" for layer in enabled_layers]
            )
            # 每个层级搜索完成后都汇聚到聚合器
            for layer in enabled_layers:
                graph.add_edge(f"layer_{layer}_search", "aggregator")
        else:
            # 如果没有启用的层级，直接到聚合器
            graph.add_edge("source_discovery", "aggregator")

        # 聚合器 → 验证器 → 输出 → 结束
        graph.add_edge("aggregator", "validator")
        graph.add_edge("validator", "output")
        graph.add_edge("output", END)

        logger.info(
            f"Graph built with {len(enabled_layers)} layer search nodes"
        )

        return graph

    def compile(self) -> Any:
        """编译搜索图

        Returns:
            编译后的可执行图

        Raises:
            ImportError: 如果 LangGraph 未安装
        """
        graph = self.build()

        # 编译图
        compile_kwargs = {}
        if self.checkpointer:
            compile_kwargs["checkpointer"] = self.checkpointer

        compiled = graph.compile(**compile_kwargs)

        logger.info("Graph compiled successfully")
        return compiled


def build_search_graph(
    config: Optional[LangGraphSearchConfig] = None,
    firecrawl_client: Optional[Any] = None,
    anthropic_client: Optional[Any] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> Any:
    """便捷函数：构建并编译搜索图

    Args:
        config: LangGraph 搜索配置
        firecrawl_client: Firecrawl 客户端
        anthropic_client: Anthropic 客户端（已不再使用，保留兼容性）
        checkpointer: 检查点保存器（用于状态持久化）

    Returns:
        编译后的可执行图

    Raises:
        ImportError: 如果 LangGraph 未安装
    """
    builder = SearchGraphBuilder(
        config=config,
        firecrawl_client=firecrawl_client,
        anthropic_client=anthropic_client,  # 保留参数兼容性
        checkpointer=checkpointer,
    )
    return builder.compile()


# ============================================================================
# 两步搜索图构建器 (v4.11.0) - 推荐
# ============================================================================

class TwoStepSearchGraphBuilder:
    """两步搜索图构建器 (v4.16.0) - 推荐

    将搜索流程拆分为多个独立步骤：
    1. keyword_generator: 6 步关键词分析（理解意图 → 确认事件 → 提取关键词 → 理解关键词 → 组合搜索词 → 补充说明）
    2. firecrawl_config: 根据分层关键词 (Tier 1/2/3) 生成 Firecrawl 搜索配置
    3. simplified_search: 执行 Firecrawl 搜索
    4. intent_filter: URL去重 + Claude LLM 意图匹配过滤

    流程图：
    START → keyword_generator → firecrawl_config → simplified_search → intent_filter → output → END

    优势：
    - 清晰的职责分离
    - 可调试性好（可以查看中间关键词）
    - 优先级分层：Tier 1 (核心) / Tier 2 (重要) / Tier 3 (补充)
    - 意图筛选：保存前过滤无关结果
    - 灵活的扩展性（可插入人工审核）
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        firecrawl_client: Optional[Any] = None,
        anthropic_client: Optional[Any] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ):
        """初始化两步图构建器

        Args:
            config: LangGraph 搜索配置
            firecrawl_client: Firecrawl 客户端
            anthropic_client: Anthropic 客户端（用于 LLM 关键词生成）
            checkpointer: 检查点保存器（用于状态持久化）
        """
        self.config = config or LangGraphSearchConfig()
        self.firecrawl_client = firecrawl_client
        self.checkpointer = checkpointer

        # 创建节点实例
        self._init_nodes(anthropic_client)

    def _init_nodes(self, anthropic_client: Optional[Any] = None) -> None:
        """初始化节点

        Args:
            anthropic_client: Anthropic 客户端
        """
        # Step 1: 关键词生成节点（使用 LLM）
        self.keyword_generator = KeywordGeneratorNode(
            config=self.config,
            anthropic_client=anthropic_client,
        )

        # Step 2: Firecrawl 配置生成节点（使用 LLM）
        self.firecrawl_config = FirecrawlConfigNode(
            config=self.config,
            anthropic_client=anthropic_client,
        )

        # Step 3: 简化搜索节点（执行 Firecrawl 搜索）
        self.simplified_search = SimplifiedSearchNode(
            config=self.config,
            firecrawl_client=self.firecrawl_client,
        )

        # Step 4: 重试搜索节点（v4.17.0 新增）- 结果不足时补充搜索
        self.retry_search = RetrySearchNode(
            config=self.config,
        )

        # Step 5: 意图筛选节点（URL去重 + LLM 意图匹配）
        self.intent_filter = IntentFilterNode(
            config=self.config,
            anthropic_client=anthropic_client,
        )

        # 输出节点
        self.output = OutputNode(config=self.config)

    def build(self) -> Any:
        """构建两步搜索状态图

        Returns:
            StateGraph 实例

        Raises:
            ImportError: 如果 LangGraph 未安装
        """
        if not HAS_LANGGRAPH or StateGraph is None:
            raise ImportError(
                "LangGraph is not installed. Please install it with: "
                "pip install langgraph"
            )

        logger.info("[TwoStepGraph] Building two-step search graph (v4.17.0)...")

        # 创建状态图
        graph = StateGraph(SearchState)

        # 添加节点
        graph.add_node("keyword_generator", self.keyword_generator)
        graph.add_node("firecrawl_config", self.firecrawl_config)
        graph.add_node("simplified_search", self.simplified_search)
        graph.add_node("retry_search", self.retry_search)
        graph.add_node("intent_filter", self.intent_filter)
        graph.add_node("output", self.output)

        # 添加边（v4.17.0 增加重试节点）
        graph.add_edge(START, "keyword_generator")
        graph.add_edge("keyword_generator", "firecrawl_config")
        graph.add_edge("firecrawl_config", "simplified_search")

        # 条件边：根据 should_retry 决定是否进行重试
        def should_retry_route(state: SearchState) -> str:
            return "retry_search" if state.get("should_retry", False) else "intent_filter"

        graph.add_conditional_edges("simplified_search", should_retry_route, ["retry_search", "intent_filter"])

        # 重试节点 → intent_filter
        graph.add_edge("retry_search", "intent_filter")

        # 意图筛选 → 输出 → 结束
        graph.add_edge("intent_filter", "output")
        graph.add_edge("output", END)

        logger.info(
            "[TwoStepGraph] Graph built: "
            "START → keyword_generator → firecrawl_config → simplified_search → [retry_search?] → intent_filter → output → END"
        )

        return graph

    def compile(self) -> Any:
        """编译两步搜索图

        Returns:
            编译后的可执行图

        Raises:
            ImportError: 如果 LangGraph 未安装
        """
        graph = self.build()

        # 编译图
        compile_kwargs = {}
        if self.checkpointer:
            compile_kwargs["checkpointer"] = self.checkpointer

        compiled = graph.compile(**compile_kwargs)

        logger.info("[TwoStepGraph] Graph compiled successfully")
        return compiled


def build_two_step_search_graph(
    config: Optional[LangGraphSearchConfig] = None,
    firecrawl_client: Optional[Any] = None,
    anthropic_client: Optional[Any] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> Any:
    """便捷函数：构建并编译两步搜索图

    Args:
        config: LangGraph 搜索配置
        firecrawl_client: Firecrawl 客户端
        anthropic_client: Anthropic 客户端
        checkpointer: 检查点保存器

    Returns:
        编译后的可执行图

    Raises:
        ImportError: 如果 LangGraph 未安装
    """
    builder = TwoStepSearchGraphBuilder(
        config=config,
        firecrawl_client=firecrawl_client,
        anthropic_client=anthropic_client,
        checkpointer=checkpointer,
    )
    return builder.compile()
