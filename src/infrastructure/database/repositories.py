"""
数据库仓储层实现

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.search_task import SearchTask, TaskStatus
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.database.connection import get_mongodb_database

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoTaskRepository as _MongoTaskRepository,
    MongoResultRepository as _MongoResultRepository
)

from src.utils.logger import get_logger

logger = get_logger(__name__)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoTaskRepository
class SearchTaskRepository(_MongoTaskRepository):
    """
    搜索任务仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoTaskRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoTaskRepository

    注意：此类的所有功能已由父类 MongoTaskRepository 实现。
    """
    pass


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoResultRepository
class SearchResultRepository(_MongoResultRepository):
    """
    搜索结果仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoResultRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoResultRepository

    注意：此类的所有功能已由父类 MongoResultRepository 实现。
    """
    pass
