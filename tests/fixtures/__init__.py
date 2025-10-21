"""测试固件模块"""

from .mock_data import (
    create_mock_search_response,
    create_mock_error_response,
    create_mock_search_task,
    create_mock_search_result,
    create_mock_search_config,
    create_mock_result_batch,
    create_bulk_mock_tasks,
    create_bulk_mock_results
)

from .test_helpers import (
    wait_for_condition,
    wait_for_task_execution,
    retry_async,
    assert_search_result_valid,
    assert_task_statistics_valid,
    assert_api_response_valid,
    assert_tasks_equal,
    cleanup_test_tasks,
    cleanup_test_results,
    cleanup_all_test_data,
    PerformanceTimer,
    assert_performance
)

__all__ = [
    # Mock data generators
    "create_mock_search_response",
    "create_mock_error_response",
    "create_mock_search_task",
    "create_mock_search_result",
    "create_mock_search_config",
    "create_mock_result_batch",
    "create_bulk_mock_tasks",
    "create_bulk_mock_results",

    # Test helpers
    "wait_for_condition",
    "wait_for_task_execution",
    "retry_async",
    "assert_search_result_valid",
    "assert_task_statistics_valid",
    "assert_api_response_valid",
    "assert_tasks_equal",
    "cleanup_test_tasks",
    "cleanup_test_results",
    "cleanup_all_test_data",
    "PerformanceTimer",
    "assert_performance",
]
