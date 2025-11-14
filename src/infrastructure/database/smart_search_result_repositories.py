"""智能搜索结果仓储

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。

v1.5.0 ID系统统一：
- 移除UUID依赖
- 所有ID使用雪花算法字符串格式
- 与系统ID标准保持一致
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoSmartSearchResultRepository as _MongoSmartSearchResultRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoSmartSearchResultRepository
class SmartSearchResultRepository(_MongoSmartSearchResultRepository):
    """
    智能搜索结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoSmartSearchResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoSmartSearchResultRepository

    注意：此类的所有功能已由父类 MongoSmartSearchResultRepository 实现。

    核心功能：
    - 使用独立的 smart_search_results 集合
    - 支持按子查询索引分组查询
    - 提供聚合优先级管理
    - 支持结果状态管理（v2.1.0）
    - 提供多维度统计分析

    智能搜索特定字段：
    - original_query: 原始查询
    - decomposed_query: 分解后的子查询
    - decomposition_reasoning: 分解理由
    - query_focus: 查询焦点
    - sub_query_index: 子查询索引
    - aggregation_priority: 聚合优先级
    - relevance_to_original: 对原始查询的相关性
    """
    pass
