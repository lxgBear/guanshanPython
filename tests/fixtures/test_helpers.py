"""
测试辅助函数

提供异步测试辅助、数据验证、清理等实用函数。
"""

import asyncio
from typing import Callable, Optional, List, Any
from datetime import datetime

from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_result import SearchResult


# ==========================================
# 异步测试辅助
# ==========================================

async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """等待条件满足

    Args:
        condition: 条件函数
        timeout: 超时时间(秒)
        interval: 检查间隔(秒)
        error_message: 超时错误消息

    Returns:
        bool: 条件是否在超时前满足

    Raises:
        TimeoutError: 超时时抛出
    """
    start_time = asyncio.get_event_loop().time()

    while True:
        if condition():
            return True

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            raise TimeoutError(error_message)

        await asyncio.sleep(interval)


async def wait_for_task_execution(
    task_id: str,
    scheduler,
    timeout: float = 10.0
) -> bool:
    """等待任务执行完成

    Args:
        task_id: 任务ID
        scheduler: 调度器实例
        timeout: 超时时间(秒)

    Returns:
        bool: 任务是否执行完成
    """
    repo = await scheduler._get_task_repository()

    async def check_execution():
        task = await repo.get_by_id(task_id)
        return task and task.execution_count > 0

    try:
        await wait_for_condition(
            check_execution,
            timeout=timeout,
            error_message=f"任务 {task_id} 未在 {timeout}秒内执行完成"
        )
        return True
    except TimeoutError:
        return False


async def retry_async(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 0.5,
    *args,
    **kwargs
) -> Any:
    """异步函数重试

    Args:
        func: 异步函数
        max_attempts: 最大尝试次数
        delay: 重试间隔(秒)
        *args: 函数参数
        **kwargs: 函数关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

    raise last_exception


# ==========================================
# 数据验证
# ==========================================

def assert_search_result_valid(result: SearchResult, strict: bool = True):
    """验证SearchResult实体有效性

    Args:
        result: SearchResult实体
        strict: 是否严格验证(检查可选字段)

    Raises:
        AssertionError: 验证失败时抛出
    """
    # 必需字段
    assert result.id is not None, "result.id 不能为空"
    assert result.task_id, "result.task_id 不能为空"
    assert result.title, "result.title 不能为空"
    assert result.url, "result.url 不能为空"
    assert result.url.startswith("http"), "result.url 必须是有效URL"

    # 内容字段
    assert result.content, "result.content 不能为空"
    assert len(result.content) > 0, "result.content 长度必须>0"

    # 分数字段
    assert 0 <= result.relevance_score <= 1, "result.relevance_score 必须在0-1之间"

    # 状态字段
    assert result.status is not None, "result.status 不能为空"

    # 时间字段
    assert result.created_at is not None, "result.created_at 不能为空"
    assert isinstance(result.created_at, datetime), "result.created_at 必须是datetime类型"

    # 严格模式验证可选字段
    if strict:
        if result.markdown_content:
            assert len(result.markdown_content) <= 5000, "markdown_content 应该被截断到5000字符"


def assert_task_statistics_valid(task: SearchTask):
    """验证SearchTask统计数据有效性

    Args:
        task: SearchTask实体

    Raises:
        AssertionError: 验证失败时抛出
    """
    # 统计字段
    assert task.execution_count >= 0, "execution_count 不能为负数"
    assert task.success_count >= 0, "success_count 不能为负数"
    assert task.failure_count >= 0, "failure_count 不能为负数"

    # 统计一致性
    assert task.execution_count == task.success_count + task.failure_count, \
        "execution_count 必须等于 success_count + failure_count"

    # 成功率计算
    if task.execution_count > 0:
        expected_rate = (task.success_count / task.execution_count) * 100
        assert abs(task.success_rate - expected_rate) < 0.01, \
            f"success_rate 计算错误: 期望 {expected_rate}, 实际 {task.success_rate}"
    else:
        assert task.success_rate == 0, "未执行任务的成功率应该为0"


def assert_api_response_valid(
    response: dict,
    expected_status: str = "success",
    required_fields: Optional[List[str]] = None
):
    """验证API响应有效性

    Args:
        response: API响应字典
        expected_status: 期望的状态
        required_fields: 必需字段列表

    Raises:
        AssertionError: 验证失败时抛出
    """
    assert isinstance(response, dict), "响应必须是字典类型"

    if expected_status:
        assert response.get("status") == expected_status or \
               response.get("success") == (expected_status == "success"), \
               f"响应状态不正确: 期望 {expected_status}, 实际 {response.get('status')}"

    if required_fields:
        for field in required_fields:
            assert field in response, f"响应缺少必需字段: {field}"


# ==========================================
# 数据比较
# ==========================================

def assert_tasks_equal(task1: SearchTask, task2: SearchTask, ignore_fields: Optional[List[str]] = None):
    """比较两个SearchTask是否相等

    Args:
        task1: 第一个任务
        task2: 第二个任务
        ignore_fields: 忽略的字段列表

    Raises:
        AssertionError: 任务不相等时抛出
    """
    ignore_fields = ignore_fields or []

    if "id" not in ignore_fields:
        assert str(task1.id) == str(task2.id), f"任务ID不匹配: {task1.id} != {task2.id}"

    if "name" not in ignore_fields:
        assert task1.name == task2.name, f"任务名称不匹配: {task1.name} != {task2.name}"

    if "query" not in ignore_fields:
        assert task1.query == task2.query, f"搜索查询不匹配: {task1.query} != {task2.query}"

    if "is_active" not in ignore_fields:
        assert task1.is_active == task2.is_active, \
            f"活跃状态不匹配: {task1.is_active} != {task2.is_active}"

    if "schedule_interval" not in ignore_fields:
        assert task1.schedule_interval == task2.schedule_interval, \
            f"调度间隔不匹配: {task1.schedule_interval} != {task2.schedule_interval}"


# ==========================================
# 测试数据清理
# ==========================================

async def cleanup_test_tasks(scheduler, task_ids: List[str]):
    """清理测试任务

    Args:
        scheduler: 调度器实例
        task_ids: 任务ID列表
    """
    repo = await scheduler._get_task_repository()

    for task_id in task_ids:
        try:
            # 从调度器移除
            await scheduler.remove_task(task_id)
        except Exception:
            pass  # 忽略移除失败

        try:
            # 从仓储删除
            await repo.delete(task_id)
        except Exception:
            pass  # 忽略删除失败


async def cleanup_test_results(result_repo, task_id: str):
    """清理测试结果

    Args:
        result_repo: 结果仓储实例
        task_id: 任务ID
    """
    try:
        # 删除所有关联结果
        results, _ = await result_repo.get_results_by_task(task_id, page=1, page_size=1000)
        for result in results:
            try:
                await result_repo.delete(str(result.id))
            except Exception:
                pass  # 忽略删除失败
    except Exception:
        pass  # 忽略清理失败


async def cleanup_all_test_data(scheduler):
    """清理所有测试数据

    Args:
        scheduler: 调度器实例
    """
    repo = await scheduler._get_task_repository()
    result_repo = await scheduler._get_result_repository()

    # 查找所有测试任务(名称包含"测试"或"test")
    try:
        tasks, _ = await repo.list_tasks(page=1, page_size=1000)
        test_tasks = [t for t in tasks if "测试" in t.name or "test" in t.name.lower()]

        for task in test_tasks:
            task_id = str(task.id)

            # 清理结果
            if result_repo:
                await cleanup_test_results(result_repo, task_id)

            # 清理任务
            try:
                await scheduler.remove_task(task_id)
                await repo.delete(task_id)
            except Exception:
                pass
    except Exception:
        pass  # 忽略清理失败


# ==========================================
# 性能测试辅助
# ==========================================

class PerformanceTimer:
    """性能计时器"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """开始计时"""
        self.start_time = datetime.utcnow()

    def stop(self):
        """停止计时"""
        self.end_time = datetime.utcnow()

    def elapsed_ms(self) -> float:
        """获取经过的毫秒数"""
        if not self.start_time or not self.end_time:
            return 0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def elapsed_seconds(self) -> float:
        """获取经过的秒数"""
        return self.elapsed_ms() / 1000


def assert_performance(
    elapsed_ms: float,
    max_ms: float,
    message: Optional[str] = None
):
    """验证性能指标

    Args:
        elapsed_ms: 实际耗时(毫秒)
        max_ms: 最大允许耗时(毫秒)
        message: 自定义错误消息

    Raises:
        AssertionError: 性能不达标时抛出
    """
    if message is None:
        message = f"性能不达标: 耗时 {elapsed_ms:.2f}ms 超过限制 {max_ms}ms"

    assert elapsed_ms <= max_ms, message
