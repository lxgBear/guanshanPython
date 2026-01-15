"""LangGraph 搜索节点模块

提供搜索图的各个处理节点。

Nodes:
- query_analyzer: 协调器节点（v4.7.0: OSINT 架构）
  - intent_parser: 意图解析节点
  - keyword_generator: 关键词生成节点
- source_discovery: 动态发现官方来源
- layer_search: 分层搜索执行
- aggregator: 结果聚合去重
- result_filter: 结果过滤 (v4.5.1 黑名单/白名单)
- validator: 交叉验证
- quality_gate: 质量门控 (v3.7.2)
- output: 输出格式化
"""

from .query_analyzer import QueryAnalyzerNode
from .intent_parser import IntentParserNode
from .keyword_generator import KeywordGeneratorNode
from .source_discovery import SourceDiscoveryNode
from .layer_search import LayerSearchNode
from .aggregator import AggregatorNode
from .result_filter import ResultFilter, create_result_filter
from .validator import ValidatorNode
from .quality_gate import QualityGateNode, should_retry_search
from .output import OutputNode

__all__ = [
    # v4.7.0: OSINT 架构节点
    "QueryAnalyzerNode",
    "IntentParserNode",
    "KeywordGeneratorNode",
    # 原有节点
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
