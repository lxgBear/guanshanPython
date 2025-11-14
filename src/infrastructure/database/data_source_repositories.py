"""数据源仓储层

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoDataSourceRepository as _MongoDataSourceRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoDataSourceRepository
class DataSourceRepository(_MongoDataSourceRepository):
    """
    数据源仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoDataSourceRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoDataSourceRepository

    注意：此类的所有功能已由父类 MongoDataSourceRepository 实现。

    核心功能：
    - 数据源的CRUD操作
    - 多维度过滤查询（状态、类型、分类、创建者、时间范围）
    - 原始数据引用管理（添加、移除）
    - 统计信息维护
    - 事务支持（跨集合同步）

    数据源特定字段：
    - title: 数据源标题
    - description: 数据源描述
    - source_type: 数据源类型（scheduled, instant, mixed）
    - status: 数据源状态（draft, confirmed）
    - raw_data_refs: 原始数据引用列表
    - categories: 三级分类（primary_category, secondary_category, tertiary_category）
    - statistics: 统计信息（total_raw_data_count, scheduled_data_count, instant_data_count）
    """
    pass
