"""即时搜索AI处理结果数据仓储

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

v2.1.0 即时+智能搜索统一架构：
- 管理 instant_processed_results 集合的所有数据访问操作
- 支持 search_type 字段区分即时搜索和智能搜索
- 支持状态管理和用户操作
- 提供AI服务所需的查询和更新接口

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoInstantProcessedResultRepository as _MongoInstantProcessedResultRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoInstantProcessedResultRepository
class InstantProcessedResultRepository(_MongoInstantProcessedResultRepository):
    """
    即时搜索AI处理结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoInstantProcessedResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoInstantProcessedResultRepository

    注意：此类的所有功能已由父类 MongoInstantProcessedResultRepository 实现。

    核心功能：
    - AI处理结果的生命周期管理
    - 状态流转（pending → processing → completed/failed）
    - 按任务和类型查询（支持即时和智能搜索）
    - 用户操作管理（留存、删除、评分、备注）
    - 统计分析和失败重试

    v2.1.0 统一架构支持：
    - task_id: 任务ID（兼容即时搜索和智能搜索）
    - search_type: 搜索类型（instant | smart）
    - status: 处理状态（pending, processing, completed, failed, archived, deleted）
    - user_rating: 用户评分（1-5）
    - user_notes: 用户备注
    """
    pass
