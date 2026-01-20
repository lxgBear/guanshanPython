"""
结构化日志基础设施

使用 structlog 提供结构化日志功能，支持:
- JSON格式输出
- 节点生命周期日志
- 错误追踪
"""

import logging
import sys
import time
from contextvars import ContextVar
from functools import lru_cache
from typing import Any

import structlog
from structlog.typing import FilteringBoundLogger

from ..config.settings import get_settings

# 上下文变量，用于跨异步调用传递请求ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def _add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """添加请求ID到日志"""
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def setup_logging(
    level: str | None = None,
    json_format: bool = True,
    force_configure: bool = False,
) -> None:
    """配置结构化日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        json_format: 是否使用JSON格式输出
        force_configure: 是否强制重新配置
    """
    settings = get_settings()
    log_level = level or settings.log_level

    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
        force=force_configure,
    )

    # 定义处理器链
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_format:
        # JSON格式输出 (生产环境)
        # 使用 ensure_ascii=False 以正确显示中文
        shared_processors.extend(
            [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ]
        )
    else:
        # 控制台友好格式 (开发环境)
        shared_processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@lru_cache(maxsize=32)
def get_logger(name: str) -> FilteringBoundLogger:
    """获取结构化日志器

    Args:
        name: 日志器名称 (通常是模块或节点名)

    Returns:
        结构化日志器实例
    """
    return structlog.get_logger(name)


# === 节点生命周期日志宏 ===


def log_node_start(
    logger: FilteringBoundLogger,
    node_name: str,
    input_keys: list[str],
    extra: dict[str, Any] | None = None,
) -> float:
    """记录节点开始执行

    Args:
        logger: 日志器实例
        node_name: 节点名称
        input_keys: 输入状态键列表
        extra: 额外日志字段

    Returns:
        开始时间戳 (用于计算执行时长)
    """
    start_time = time.perf_counter()
    log_data = {
        "event": "node_start",
        "node": node_name,
        "inputs": input_keys,
    }
    if extra:
        log_data.update(extra)

    logger.info(**log_data)
    return start_time


def log_node_end(
    logger: FilteringBoundLogger,
    node_name: str,
    output_keys: list[str],
    start_time: float,
    extra: dict[str, Any] | None = None,
) -> None:
    """记录节点执行完成

    Args:
        logger: 日志器实例
        node_name: 节点名称
        output_keys: 输出状态键列表
        start_time: 开始时间戳 (从 log_node_start 返回)
        extra: 额外日志字段
    """
    duration_ms = (time.perf_counter() - start_time) * 1000
    log_data = {
        "event": "node_end",
        "node": node_name,
        "outputs": output_keys,
        "duration_ms": round(duration_ms, 2),
    }
    if extra:
        log_data.update(extra)

    logger.info(**log_data)


def log_node_error(
    logger: FilteringBoundLogger,
    node_name: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> None:
    """记录节点执行错误

    Args:
        logger: 日志器实例
        node_name: 节点名称
        error: 异常对象
        context: 错误上下文
    """
    log_data: dict[str, Any] = {
        "event": "node_error",
        "node": node_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    # 如果是 NodeError，添加更多信息
    from .errors import NodeError

    if isinstance(error, NodeError):
        log_data.update(
            {
                "error_category": error.error_type.value,
                "severity": error.severity.value,
                "recoverable": error.recoverable,
                "recovery_strategy": error.recovery_strategy.value,
            }
        )

    if context:
        log_data["context"] = context

    logger.error(**log_data, exc_info=True)


def log_node_fallback(
    logger: FilteringBoundLogger,
    node_name: str,
    reason: str,
    fallback_action: str,
) -> None:
    """记录节点降级处理

    Args:
        logger: 日志器实例
        node_name: 节点名称
        reason: 降级原因
        fallback_action: 降级操作描述
    """
    logger.warning(
        event="node_fallback",
        node=node_name,
        reason=reason,
        fallback_action=fallback_action,
    )


def log_node_retry(
    logger: FilteringBoundLogger,
    node_name: str,
    attempt: int,
    max_attempts: int,
    error: Exception,
) -> None:
    """记录节点重试

    Args:
        logger: 日志器实例
        node_name: 节点名称
        attempt: 当前尝试次数
        max_attempts: 最大尝试次数
        error: 触发重试的错误
    """
    logger.warning(
        event="node_retry",
        node=node_name,
        attempt=attempt,
        max_attempts=max_attempts,
        error_type=type(error).__name__,
        error_message=str(error),
    )


# 初始化默认日志配置
setup_logging()
