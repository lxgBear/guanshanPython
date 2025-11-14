"""AI处理结果数据仓储

Version: v3.0.0 (模块化架构)
提供向后兼容的 ProcessedResultRepository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。

v2.0.0 职责分离架构：
- 管理 news_results 集合的所有数据访问操作
- 支持状态管理和用户操作
- 提供AI服务所需的查询和更新接口

v2.0.1 字段扩展：
- 支持原始字段（title, url, content等）
- 支持AI服务新增字段（content_zh, cls_results等）

v2.0.2 表名更新：
- 集合名从 processed_results_new 更新为 news_results
- 添加 news_results 嵌套字段和 content_cleaned 字段支持
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoProcessedResultRepository as _MongoProcessedResultRepository
)

logger = get_logger(__name__)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoProcessedResultRepository
class ProcessedResultRepository(_MongoProcessedResultRepository):
    """
    AI处理结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoProcessedResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoProcessedResultRepository

    注意：此类的所有功能已由父类 MongoProcessedResultRepository 实现。
    """
    pass
