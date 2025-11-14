"""数据库基础设施模块

Version: v3.0.0 (模块化架构)

注意：此模块现在主要提供向后兼容。
新代码应使用 src.infrastructure.persistence 模块。
"""

from .connection import get_database_connection

__all__ = [
    "get_database_connection",
]