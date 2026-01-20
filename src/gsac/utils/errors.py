"""
OSINT搜索错误处理框架

提供统一的错误类型、严重程度和恢复策略定义
"""

from enum import Enum
from typing import Any


class ErrorSeverity(Enum):
    """错误严重程度"""

    WARNING = "warning"  # 可降级继续
    ERROR = "error"  # 节点失败，需要回退
    CRITICAL = "critical"  # 工作流终止


class NodeErrorType(Enum):
    """节点错误类型"""

    # === LLM相关错误 ===
    LLM_CONNECTION_ERROR = "llm_connection_error"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_INVALID_RESPONSE = "llm_invalid_response"
    LLM_PARSING_ERROR = "llm_parsing_error"

    # === Firecrawl相关错误 ===
    FIRECRAWL_CONNECTION_ERROR = "firecrawl_connection_error"
    FIRECRAWL_RATE_LIMIT = "firecrawl_rate_limit"
    FIRECRAWL_TIMEOUT = "firecrawl_timeout"
    FIRECRAWL_INVALID_URL = "firecrawl_invalid_url"
    FIRECRAWL_SCRAPE_FAILED = "firecrawl_scrape_failed"

    # === 数据验证错误 ===
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"

    # === 业务逻辑错误 ===
    NO_RESULTS_FOUND = "no_results_found"
    ITERATION_LIMIT_EXCEEDED = "iteration_limit_exceeded"
    EMPTY_CONTENT = "empty_content"

    # === 通用错误 ===
    UNKNOWN_ERROR = "unknown_error"


class ErrorRecoveryStrategy(Enum):
    """错误恢复策略"""

    RETRY = "retry"  # 重试
    FALLBACK = "fallback"  # 降级处理
    SKIP = "skip"  # 跳过当前项
    ABORT = "abort"  # 终止工作流
    DEFAULT_VALUE = "default"  # 使用默认值


class NodeError(Exception):
    """节点错误基类

    属性:
        error_type: 错误类型枚举
        message: 错误描述信息
        severity: 错误严重程度
        node_name: 发生错误的节点名称
        context: 错误上下文信息
        recoverable: 是否可恢复
        recovery_strategy: 建议的恢复策略
    """

    def __init__(
        self,
        error_type: NodeErrorType,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        node_name: str = "",
        context: dict[str, Any] | None = None,
        recoverable: bool = True,
        recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.FALLBACK,
    ):
        self.error_type = error_type
        self.message = message
        self.severity = severity
        self.node_name = node_name
        self.context = context or {}
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"NodeError("
            f"type={self.error_type.value}, "
            f"severity={self.severity.value}, "
            f"node={self.node_name}, "
            f"recoverable={self.recoverable}"
            f")"
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式，便于日志记录"""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "severity": self.severity.value,
            "node_name": self.node_name,
            "context": self.context,
            "recoverable": self.recoverable,
            "recovery_strategy": self.recovery_strategy.value,
        }


# === 便捷错误创建函数 ===


def create_llm_error(
    message: str,
    node_name: str,
    error_type: NodeErrorType = NodeErrorType.LLM_CONNECTION_ERROR,
    context: dict[str, Any] | None = None,
) -> NodeError:
    """创建LLM相关错误"""
    return NodeError(
        error_type=error_type,
        message=message,
        severity=ErrorSeverity.ERROR,
        node_name=node_name,
        context=context,
        recoverable=True,
        recovery_strategy=ErrorRecoveryStrategy.FALLBACK,
    )


def create_firecrawl_error(
    message: str,
    node_name: str,
    error_type: NodeErrorType = NodeErrorType.FIRECRAWL_CONNECTION_ERROR,
    context: dict[str, Any] | None = None,
) -> NodeError:
    """创建Firecrawl相关错误"""
    return NodeError(
        error_type=error_type,
        message=message,
        severity=ErrorSeverity.WARNING,
        node_name=node_name,
        context=context,
        recoverable=True,
        recovery_strategy=ErrorRecoveryStrategy.SKIP,
    )


def create_validation_error(
    message: str,
    node_name: str,
    error_type: NodeErrorType = NodeErrorType.INVALID_INPUT,
    context: dict[str, Any] | None = None,
) -> NodeError:
    """创建数据验证错误"""
    return NodeError(
        error_type=error_type,
        message=message,
        severity=ErrorSeverity.ERROR,
        node_name=node_name,
        context=context,
        recoverable=False,
        recovery_strategy=ErrorRecoveryStrategy.ABORT,
    )


def create_business_error(
    message: str,
    node_name: str,
    error_type: NodeErrorType = NodeErrorType.NO_RESULTS_FOUND,
    context: dict[str, Any] | None = None,
) -> NodeError:
    """创建业务逻辑错误"""
    return NodeError(
        error_type=error_type,
        message=message,
        severity=ErrorSeverity.WARNING,
        node_name=node_name,
        context=context,
        recoverable=True,
        recovery_strategy=ErrorRecoveryStrategy.DEFAULT_VALUE,
    )
