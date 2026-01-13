"""LangGraph 结果转换器模块

提供 LangGraph 内部数据结构与数据库实体之间的双向转换。
"""

from .result_converter import ResultConverter
from .aggregated_converter import AggregatedResultConverter

__all__ = [
    "ResultConverter",
    "AggregatedResultConverter",
]
