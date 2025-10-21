"""性能监控工具

提供性能监控装饰器和慢查询检测功能
"""
import time
import functools
from typing import Callable, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


def monitor_query_performance(
    operation_name: str,
    slow_threshold: float = 1.0
):
    """
    查询性能监控装饰器

    Args:
        operation_name: 操作名称（用于日志和指标）
        slow_threshold: 慢查询阈值（秒），超过此值将记录警告日志

    Usage:
        @monitor_query_performance("cross_task_search", slow_threshold=1.0)
        async def search_across_tasks(self, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # 记录执行时间
                if duration > slow_threshold:
                    logger.warning(
                        f"⚠️  慢查询检测 - {operation_name} "
                        f"耗时: {duration:.3f}s (阈值: {slow_threshold}s)"
                    )
                else:
                    logger.debug(
                        f"✅ {operation_name} 完成 - "
                        f"耗时: {duration:.3f}s"
                    )

                # TODO: 发送监控指标到监控系统
                # metrics.histogram(f"query.{operation_name}.duration", duration)

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"❌ 查询失败 - {operation_name} "
                    f"耗时: {duration:.3f}s, 错误: {e}"
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if duration > slow_threshold:
                    logger.warning(
                        f"⚠️  慢查询检测 - {operation_name} "
                        f"耗时: {duration:.3f}s (阈值: {slow_threshold}s)"
                    )
                else:
                    logger.debug(
                        f"✅ {operation_name} 完成 - "
                        f"耗时: {duration:.3f}s"
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"❌ 查询失败 - {operation_name} "
                    f"耗时: {duration:.3f}s, 错误: {e}"
                )
                raise

        # 检测是否为异步函数
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class PerformanceTracker:
    """
    性能追踪器（单例模式）

    用于收集和聚合性能指标
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.metrics = {}
            cls._instance.slow_queries = []
        return cls._instance

    def record_query(
        self,
        operation_name: str,
        duration: float,
        success: bool = True
    ):
        """记录查询性能"""
        if operation_name not in self.metrics:
            self.metrics[operation_name] = {
                "count": 0,
                "total_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "success_count": 0,
                "error_count": 0
            }

        metric = self.metrics[operation_name]
        metric["count"] += 1
        metric["total_time"] += duration
        metric["min_time"] = min(metric["min_time"], duration)
        metric["max_time"] = max(metric["max_time"], duration)

        if success:
            metric["success_count"] += 1
        else:
            metric["error_count"] += 1

    def record_slow_query(
        self,
        operation_name: str,
        duration: float,
        query_params: dict
    ):
        """记录慢查询"""
        self.slow_queries.append({
            "operation": operation_name,
            "duration": duration,
            "params": query_params,
            "timestamp": time.time()
        })

        # 只保留最近100条慢查询
        if len(self.slow_queries) > 100:
            self.slow_queries = self.slow_queries[-100:]

    def get_metrics(self) -> dict:
        """获取性能指标"""
        result = {}
        for op_name, metric in self.metrics.items():
            if metric["count"] > 0:
                result[op_name] = {
                    "count": metric["count"],
                    "avg_time": metric["total_time"] / metric["count"],
                    "min_time": metric["min_time"],
                    "max_time": metric["max_time"],
                    "success_rate": metric["success_count"] / metric["count"] * 100,
                    "error_count": metric["error_count"]
                }
        return result

    def get_slow_queries(self, limit: int = 20) -> list:
        """获取最近的慢查询"""
        return sorted(
            self.slow_queries,
            key=lambda x: x["duration"],
            reverse=True
        )[:limit]

    def reset(self):
        """重置统计信息"""
        self.metrics = {}
        self.slow_queries = []


# 全局性能追踪器实例
performance_tracker = PerformanceTracker()
