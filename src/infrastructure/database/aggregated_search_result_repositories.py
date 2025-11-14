"""聚合搜索结果仓储

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

v1.5.2 职责分离实现：
- 专用于 smart_search_results 集合
- 存储智能搜索的去重聚合结果
- 包含综合评分、多源信息等聚合字段

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoAggregatedSearchResultRepository as _MongoAggregatedSearchResultRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoAggregatedSearchResultRepository
class AggregatedSearchResultRepository(_MongoAggregatedSearchResultRepository):
    """
    聚合搜索结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoAggregatedSearchResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoAggregatedSearchResultRepository

    注意：此类的所有功能已由父类 MongoAggregatedSearchResultRepository 实现。

    核心功能：
    - 存储去重聚合后的搜索结果
    - 包含综合评分、多源信息、聚合统计
    - 与 instant_search_results 分离
    - 支持多维度查询和排序（按评分、来源数、相关性、时间）
    - 提供丰富的统计分析功能
    - 状态管理（单个和批量更新）

    智能搜索聚合字段：
    - smart_task_id: 智能搜索任务ID
    - composite_score: 综合评分
    - source_count: 来源数量（出现在多少个子查询中）
    - avg_relevance_score: 平均相关性评分
    - sources: 来源信息列表（SourceInfo）
    - status: 结果状态（unread, read, archived, deleted）
    """
    pass
