"""
NL Search 实体模块 (简化版)

包含:
- NLSearchLog: 自然语言搜索记录实体
- NLUserArchive: 用户档案实体
- NLUserSelection: 用户档案条目实体
"""
from .nl_search_log import NLSearchLog
from .nl_user_archive import NLUserArchive
from .nl_user_selection import NLUserSelection
from .enums import SearchStatus

__all__ = [
    "NLSearchLog",
    "NLUserArchive",
    "NLUserSelection",
    "SearchStatus",
]
