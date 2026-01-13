"""LangGraph 搜索图构建器

构建 5 层分层搜索的 StateGraph。

Graph Structure:
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
    QueryAnalyzerNode,
    SourceDiscoveryNode,
    LayerSearchNode,
    AggregatorNode,
    ValidatorNode,
    OutputNode,
)
from .nodes.layer_search import create_layer_search_nodes

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
    """搜索图构建器

    构建基于 LangGraph 的 5 层分层搜索图。

    Features:
    - 动态层级启用/禁用
    - 并行层级搜索
    - 可配置的检查点
    - 多用户隔离支持
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
            anthropic_client: Anthropic 客户端
            checkpointer: 检查点保存器
        """
        self.config = config or LangGraphSearchConfig()
        self.firecrawl_client = firecrawl_client
        self.anthropic_client = anthropic_client
        self.checkpointer = checkpointer

        # 创建节点实例
        self._init_nodes()

    def _init_nodes(self) -> None:
        """初始化所有节点"""
        # 查询分析节点
        self.query_analyzer = QueryAnalyzerNode(
            config=self.config,
            anthropic_client=self.anthropic_client,
        )

        # 来源发现节点
        self.source_discovery = SourceDiscoveryNode(
            config=self.config,
            anthropic_client=self.anthropic_client,
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

        logger.info("Building search graph...")

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

        # 设置入口边
        graph.add_edge(START, "query_analyzer")
        graph.add_edge("query_analyzer", "source_discovery")

        # 从 source_discovery 到所有启用的层级搜索 (并行执行)
        enabled_layers = list(self.layer_search_nodes.keys())

        if enabled_layers:
            # ���用条件边实现并行分发 (Send API)
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
        anthropic_client: Anthropic 客户端
        checkpointer: 检查点保存器

    Returns:
        编译后的可执行图
    """
    builder = SearchGraphBuilder(
        config=config,
        firecrawl_client=firecrawl_client,
        anthropic_client=anthropic_client,
        checkpointer=checkpointer,
    )
    return builder.compile()
