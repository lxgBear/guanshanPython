"""LangGraph 搜索节点模块

提供搜索图的各个处理节点。

## v4.17.0 两步架构节点（推荐）
- keyword_generator: 关键词生成节点 - 6步分析: 理解意图 → 确认事件 → 提取关键词 → 理解关键词 → 组合搜索词 → 补充说明
- firecrawl_config: Firecrawl 配置生成节点 - 根据分层关键词(Tier 1/2/3)生成搜索配置
- simplified_search: 简化搜索节点 - 执行 Firecrawl 搜索并聚合结果
- retry_search: 重试搜索节点 - 结果不足时生成补充搜索
- intent_filter: 意图筛选节点 - URL去重 + Claude LLM 意图匹配过滤
- output: 输出格式化节点

## 完整架构节点（5层并行搜索，备用）
- query_analyzer: 查询分析节点
- source_discovery: 动态发现官方来源
- layer_search: 分层搜索执行
- aggregator: 结果聚合去重
- result_filter: 结果过滤 (黑名单/白名单)
- validator: 交叉验证
- quality_gate: 质量门控
"""

# v4.17.0: 两步关键词生成架构（推荐）
from .keyword_generator_node import KeywordGeneratorNode, create_keyword_generator_node
from .firecrawl_config_node import FirecrawlConfigNode, create_firecrawl_config_node
from .simplified_search import SimplifiedSearchNode, create_simplified_search_node
from .retry_search_node import RetrySearchNode, create_retry_search_node
from .intent_filter_node import IntentFilterNode, create_intent_filter_node
from .query_analyzer import QueryAnalyzerNode
from .source_discovery import SourceDiscoveryNode
from .layer_search import LayerSearchNode
from .aggregator import AggregatorNode
from .result_filter import ResultFilter, create_result_filter
from .validator import ValidatorNode
from .quality_gate import QualityGateNode, should_retry_search
from .output import OutputNode

__all__ = [
    # v4.17.0: 两步关键词生成架构（推荐）
    "KeywordGeneratorNode",
    "create_keyword_generator_node",
    "FirecrawlConfigNode",
    "create_firecrawl_config_node",
    "SimplifiedSearchNode",
    "create_simplified_search_node",
    "RetrySearchNode",
    "create_retry_search_node",
    "IntentFilterNode",
    "create_intent_filter_node",
    # 完整架构节点（5层并行搜索，备用）
    "QueryAnalyzerNode",
    "SourceDiscoveryNode",
    "LayerSearchNode",
    "AggregatorNode",
    "ResultFilter",
    "create_result_filter",
    "ValidatorNode",
    "QualityGateNode",
    "should_retry_search",
    "OutputNode",
]
