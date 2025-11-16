"""
NL Search 枚举定义
"""
from enum import Enum


class SearchStatus(str, Enum):
    """搜索状态枚举"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败

    def __str__(self):
        return self.value

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """检查状态是否有效"""
        return status in cls._value2member_map_
