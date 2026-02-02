"""LangGraph 搜索结果实体模型

v4.5.2 新增：专用于 LangGraph 智能搜索系统的结果实体

与 SearchResult 的关系：
- 继承 SearchResult 的���有基础字段
- 新增 LangGraph 特定的字段：layer, layer_name, source_tier, category
- 使用独立的 MongoDB 集合：langgraph_search_results
- 实现智能搜索数据与常规搜索结果的数据隔离

v4.5.5 更新：
- 新增 translator_status: AI 翻译状态 (pending/processing/completed/failed)
- 新增 translator_dict: AI 翻译总结内容
- 新增 transferred_to_news: 是否已转移到 news_results 表
- 新增 transferred_at: 转移时间

v4.8.1 更新：
- 移除所有评分字段：relevance_score, quality_score, credibility_score, final_score
- 移除 multi_source_bonus, recency_bonus, layer_weight

v4.28.0 更新：
- 继承父类 SearchResult 的 task_name 字段（冗余存储，来自 chat_conversations.name）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from enum import Enum

from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.id_generator import generate_string_id


class LangGraphResultStatus(str, Enum):
    """LangGraph 结果处理状态

    v4.7.0 新增：用于标记搜索结果的处理状态

    状态说明:
    - PENDING: 未处理 - 默认状态，等待用户操作
    - TRANSFERRED: 已入库 - 已转移到 news_results 表供 AI 处理
    - DISCARDED: 已废弃 - 用户标记为不需要的结果
    """
    PENDING = "pending"          # 未处理 - 默认状态
    TRANSFERRED = "transferred"  # 已入库 - 已转移到 news_results
    DISCARDED = "discarded"      # 已废弃 - 用户标记为废弃


@dataclass
class LangGraphSearchResult(SearchResult):
    """LangGraph 智能搜索结果实体

    v4.5.2 新增：用于存储 LangGraph 7节点智能搜索系统的结果

    v4.8.1 更新：移除所有评分字段

    继承 SearchResult 的所有字段：
    - id, task_id, user_id, created_by
    - title, url, snippet, source
    - markdown_content, article_tag, article_published_time (v4.9.2: 移除 html_content)
    - content_hash, metadata, status, created_at, processed_at

    新增 LangGraph 特定字段：
    - layer: 搜索层级 (0-4)
    - layer_name: 层级名称
    - source_tier: 来源可信度等级 (1-6)
    - category: 分类信息 {"大类": "", "类别": "", "地域": ""}
    """

    # ==================== 关联字段 ====================

    # v4.6.0: 关联对话会话（用于前端查询历史会话的搜索结果）
    conversation_id: Optional[str] = None  # 关联 chat_conversations._id

    # ==================== LangGraph 特定字段 ====================

    # 搜索层级信息
    layer: int = 0  # 搜索层级 (0=官方来源, 1=主流媒体, 2=区域媒体, 3=国际媒体, 4=智库机构)
    layer_name: str = ""  # 层级名称: "官方来源", "主流媒体", "区域媒体", "国际媒体", "智库机构"

    # 来源可信度
    source_tier: int = 1  # 来源可信度等级 (1=最高, 6=最低)

    # 分类信息
    category: Optional[Dict[str, str]] = None  # 分类信息: {"大类": "", "类别": "", "地域": ""}

    # v4.5.3: 数据来源分类
    data_source_type: str = "langgraph"  # 数据来源: langgraph, nl_search, manual_upload, api_import

    # v4.5.3: AI 处理状态标记
    ai_processed: bool = False  # 是否已被 AI 微服务处理
    ai_processed_at: Optional[datetime] = None  # AI 处理时间
    ai_model: Optional[str] = None  # 处理使用的 AI 模型

    # v4.5.5: AI 翻译状态与内容
    translator_status: Optional[str] = None  # AI 翻译状态: pending/processing/completed/failed
    translator_dict: Optional[Dict[str, Any]] = None  # AI 翻译总结内容

    # v4.5.5: 数据转移标记
    transferred_to_news: bool = False  # 是否已转移到 news_results 表
    transferred_at: Optional[datetime] = None  # 转移时间

    # v4.7.0: 结果处理状态
    langgraph_status: str = "pending"  # 处理状态: pending/transferred/discarded

    def __post_init__(self):
        """初始化后处理"""
        # 确保父类的 content_hash 已生成
        if not self.content_hash:
            self.ensure_content_hash()

        # 设置默认分类
        if self.category is None:
            self.category = {"大类": "未分类", "类别": "未分类", "地域": "未知"}

    def to_summary(self) -> Dict[str, Any]:
        """返回摘要信息（包含 LangGraph 特定字段）"""
        base_summary = super().to_summary()
        base_summary.update({
            # v4.6.0: 关联字段
            "conversation_id": self.conversation_id,
            # LangGraph 特定字段
            "layer": self.layer,
            "layer_name": self.layer_name,
            "source_tier": self.source_tier,
            "category": self.category,
            # v4.5.5: 新增字段
            "translator_status": self.translator_status,
            "translator_dict": self.translator_dict,
            "transferred_to_news": self.transferred_to_news,
            "transferred_at": self.transferred_at,
            # v4.7.0: 处理状态
            "langgraph_status": self.langgraph_status,
        })
        return base_summary

    def get_layer_config(self) -> Dict[str, Any]:
        """获取层级配置信息

        Returns:
            层级配置字典: {name, weight, tier, description}
        """
        layer_configs = {
            0: {
                "name": "官方来源",
                "weight": 1.0,
                "tier_range": (1, 2),
                "description": "政府网站、官方机构、中央通讯社"
            },
            1: {
                "name": "主流媒体",
                "weight": 0.9,
                "tier_range": (2, 3),
                "description": "国家级主流媒体、权威新闻机构"
            },
            2: {
                "name": "区域媒体",
                "weight": 0.8,
                "tier_range": (3, 4),
                "description": "地区性媒体、行业媒体"
            },
            3: {
                "name": "国际媒体",
                "weight": 0.7,
                "tier_range": (3, 4),
                "description": "国际新闻机构、外国媒体"
            },
            4: {
                "name": "智库机构",
                "weight": 0.85,
                "tier_range": (2, 4),
                "description": "研究机构、智库、学术组织"
            },
        }

        return layer_configs.get(
            self.layer,
            {
                "name": "未知来源",
                "weight": 0.5,
                "tier_range": (5, 6),
                "description": "未知或未分类来源"
            }
        )


@dataclass
class LangGraphSearchResultBatch:
    """LangGraph 搜索结果批次

    v4.5.2 新增：用于批量存储 LangGraph 搜索结果
    """
    # 批次ID（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 关联信息
    task_id: str = ""
    user_id: str = ""
    thread_id: str = ""  # LangGraph 线程 ID

    # 搜索查询
    query: str = ""
    search_mode: str = "single"  # single/multi

    # 结果数据
    results: list = field(default_factory=list)
    total_count: int = 0

    # LangGraph 统计信息
    statistics: Dict[str, Any] = field(default_factory=dict)

    # 状态与时间
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_result(self, result: LangGraphSearchResult) -> None:
        """添加结果"""
        self.results.append(result)
        self.total_count = len(self.results)

    def get_layer_distribution(self) -> Dict[int, int]:
        """获取层级分布统计

        Returns:
            各层级结果数量: {0: 5, 1: 10, ...}
        """
        distribution = {}
        for result in self.results:
            layer = result.layer if isinstance(result, LangGraphSearchResult) else 0
            distribution[layer] = distribution.get(layer, 0) + 1
        return distribution

    # v4.8.1: 已移除 get_average_scores 方法，因为评分字段已删除
