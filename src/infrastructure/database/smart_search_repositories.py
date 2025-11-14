"""智能搜索数据仓储层实现

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。

v2.0.0 智能搜索系统：
- SmartSearchTaskRepository: 管理智能搜索任务
- QueryDecompositionCacheRepository: 管理LLM分解结果缓存（降低成本）

数据库：MongoDB (使用Motor异步驱动)
集合命名：
- smart_search_tasks
- query_decomposition_cache
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoSmartSearchTaskRepository as _MongoSmartSearchTaskRepository,
    MongoQueryDecompositionCacheRepository as _MongoQueryDecompositionCacheRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoSmartSearchTaskRepository
class SmartSearchTaskRepository(_MongoSmartSearchTaskRepository):
    """
    智能搜索任务仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoSmartSearchTaskRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoSmartSearchTaskRepository

    注意：此类的所有功能已由父类 MongoSmartSearchTaskRepository 实现。

    核心功能：
    - 智能搜索任务生命周期管理（分解→确认→执行→聚合）
    - 按状态、创建者筛选的分页查询
    - 复杂嵌套结构的实体转换
    """
    pass


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoQueryDecompositionCacheRepository
class QueryDecompositionCacheRepository(_MongoQueryDecompositionCacheRepository):
    """
    查询分解缓存仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoQueryDecompositionCacheRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoQueryDecompositionCacheRepository

    注意：此类的所有功能已由父类 MongoQueryDecompositionCacheRepository 实现。

    核心功能：
    - LLM分解结果缓存，降低API调用成本
    - 缓存键计算：MD5(query + search_context)
    - TTL管理：24小时自动过期
    - 命中统计：记录缓存使用次数
    - 缓存清理：定期清理过期缓存
    """
    pass
