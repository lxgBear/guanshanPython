"""数据源存档数据仓储层

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoArchivedDataRepository as _MongoArchivedDataRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoArchivedDataRepository
class ArchivedDataRepository(_MongoArchivedDataRepository):
    """
    存档数据仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoArchivedDataRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoArchivedDataRepository

    注意：此类的所有功能已由父类 MongoArchivedDataRepository 实现。

    核心功能：
    - 创建存档记录（confirm时自动触发）
    - 按数据源查询和分页
    - 防重复存档（原始数据ID查询）
    - 统计信息（按类型分组、内容大小）
    - 级联删除（删除数据源时清理存档）
    - 事务支持（跨集合同步）

    存档数据特定字段：
    - data_source_id: 所属数据源ID
    - original_data_id: 原始数据ID（防重复）
    - data_type: 数据类型（scheduled或instant）
    - content: 完整内容
    - markdown_content / html_content: Firecrawl抓取内容
    - archived_at / archived_by / archived_reason: 存档元信息
    - original_created_at / original_status: 原始数据追溯
    """
    pass
