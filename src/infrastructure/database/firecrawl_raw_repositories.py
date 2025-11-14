"""Firecrawl 原始响应仓储层

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

⚠️ 临时仓储
用途：存储和查询 Firecrawl API 原始响应数据
用完后会删除

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoFirecrawlRawResponseRepository as _MongoFirecrawlRawResponseRepository
)
from typing import Optional


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoFirecrawlRawResponseRepository
class FirecrawlRawResponseRepository(_MongoFirecrawlRawResponseRepository):
    """
    Firecrawl原始响应仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoFirecrawlRawResponseRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoFirecrawlRawResponseRepository

    注意：此类的所有功能已由父类 MongoFirecrawlRawResponseRepository 实现。

    核心功能：
    - 原始响应的创建和批量创建
    - 按任务ID、URL查询响应
    - 统计响应数量和任务分布
    - 按任务删除和全量清理
    - 临时数据管理

    ⚠️ 临时仓储：用完后会删除
    """
    pass


# 创建单例实例
_repository_instance: Optional[FirecrawlRawResponseRepository] = None


async def get_firecrawl_raw_repository() -> FirecrawlRawResponseRepository:
    """获取 Firecrawl 原始响应仓储单例

    Returns:
        FirecrawlRawResponseRepository实例
    """
    global _repository_instance
    if _repository_instance is None:
        from src.infrastructure.database.connection import get_mongodb_database
        db = await get_mongodb_database()
        _repository_instance = FirecrawlRawResponseRepository(db)
    return _repository_instance
