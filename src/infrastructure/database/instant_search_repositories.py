"""即时搜索数据仓储层实现

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。

v1.3.0 架构说明：
- InstantSearchTaskRepository: 管理即时搜索任务
- InstantSearchResultRepository: 管理搜索结果（支持content_hash去重）
- InstantSearchResultMappingRepository: 管理搜索-结果映射关系（核心）

数据库：MongoDB (使用Motor异步驱动)
集合命名：
- instant_search_tasks
- instant_search_results
- instant_search_result_mappings
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoInstantSearchTaskRepository as _MongoInstantSearchTaskRepository,
    MongoInstantSearchResultRepository as _MongoInstantSearchResultRepository,
    MongoInstantSearchResultMappingRepository as _MongoInstantSearchResultMappingRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoInstantSearchTaskRepository
class InstantSearchTaskRepository(_MongoInstantSearchTaskRepository):
    """
    即时搜索任务仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoInstantSearchTaskRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoInstantSearchTaskRepository

    注意：此类的所有功能已由父类 MongoInstantSearchTaskRepository 实现。
    """
    pass


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoInstantSearchResultRepository
class InstantSearchResultRepository(_MongoInstantSearchResultRepository):
    """
    即时搜索结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoInstantSearchResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoInstantSearchResultRepository

    注意：此类的所有功能已由父类 MongoInstantSearchResultRepository 实现。

    核心功能：
    - 基于 content_hash 的去重机制
    - 发现统计信息维护
    - 按任务ID和搜索类型查询
    """
    pass


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoInstantSearchResultMappingRepository
class InstantSearchResultMappingRepository(_MongoInstantSearchResultMappingRepository):
    """
    即时搜索结果映射仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoInstantSearchResultMappingRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoInstantSearchResultMappingRepository

    注意：此类的所有功能已由父类 MongoInstantSearchResultMappingRepository 实现。

    核心功能：
    - 搜索执行与结果的多对多关系管理
    - 搜索发现历史完整追踪
    - 正向查询（某次搜索发现了哪些结果）
    - 反向查询（某个结果被哪些搜索发现）
    - 批量创建映射记录（v2.1.2重复键容错）
    """
    pass
