"""LangGraph 智能搜索服务模块

v4.0.0 - 基于 LangGraph 的多 Agent 协作搜索系统
v4.5.3 - 新增批量转移服务，支持将 LangGraph 结果转移到 news_results

Features:
- 5层分层搜索: 官方 → 主流 → 周边 → 国际 → 智库
- 动态源发现: 根据当事方自动识别官方来源
- 并行执行: 多层搜索并行执行
- 状态持久化: 支持中断恢复
- 多用户隔离: 完整的用户数据隔离架构
- 批量转移: 支持 LangGraph 结果转移到 AI 处理队列
"""

from .service import LangGraphSearchService
from .state import SearchState, SearchResult, LayerSearchResult, DiscoveredSource
from .config import LangGraphSearchConfig
from .transfer_service import LangGraphTransferService, langgraph_transfer_service

__all__ = [
    "LangGraphSearchService",
    "SearchState",
    "SearchResult",
    "LayerSearchResult",
    "DiscoveredSource",
    "LangGraphSearchConfig",
    "LangGraphTransferService",
    "langgraph_transfer_service",
]

__version__ = "4.5.3"
