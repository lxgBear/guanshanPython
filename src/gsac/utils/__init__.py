"""
gs-ai-crawl 工具模块

提供日志、错误处理等基础设施
"""

from .errors import (
    ErrorRecoveryStrategy,
    ErrorSeverity,
    NodeError,
    NodeErrorType,
)
from .logging import (
    get_logger,
    log_node_end,
    log_node_error,
    log_node_start,
    setup_logging,
)

__all__ = [
    # 错误处理
    "NodeError",
    "NodeErrorType",
    "ErrorSeverity",
    "ErrorRecoveryStrategy",
    # 日志
    "get_logger",
    "setup_logging",
    "log_node_start",
    "log_node_end",
    "log_node_error",
]
