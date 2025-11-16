"""
NL Search 实体模块 (简化版)

包含:
- NLSearchLog: 自然语言搜索记录实体
"""
from .nl_search_log import NLSearchLog
from .enums import SearchStatus

__all__ = [
    "NLSearchLog",
    "SearchStatus",
]
