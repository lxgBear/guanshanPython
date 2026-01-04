"""
NL Search 实体模块 (简化版)

包含:
- NLSearchLog: 自然语言搜索记录实体
- NLUserArchive: 用户档案实体
- NLUserSelection: 用户档案条目实体

v2.7.0 新增:
- ArchiveStatus: 档案审核状态枚举
- ArchiveReviewAction: 档案审核操作枚举
- ArchiveReviewHistory: 档案审核历史记录
"""
from .nl_search_log import NLSearchLog
from .nl_user_archive import (
    NLUserArchive,
    ArchiveStatus,
    ArchiveReviewAction,
    ArchiveReviewHistory,
)
from .nl_user_selection import NLUserSelection
from .enums import SearchStatus

__all__ = [
    "NLSearchLog",
    "NLUserArchive",
    "NLUserSelection",
    "SearchStatus",
    # v2.7.0: 审核流程相关
    "ArchiveStatus",
    "ArchiveReviewAction",
    "ArchiveReviewHistory",
]
