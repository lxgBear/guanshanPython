"""即时搜索实体层单元测试

测试内容：
- InstantSearchResult的content_hash计算
- InstantSearchResult的URL规范化
- InstantSearchResultMapping的创建
"""

import pytest
from datetime import datetime

from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.instant_search_result_mapping import (
    InstantSearchResultMapping,
    create_result_mapping
)
from src.core.domain.entities.instant_search_task import InstantSearchTask, InstantSearchStatus


class TestInstantSearchResult:
    """测试 InstantSearchResult 实体"""

    def test_content_hash_generation(self):
        """测试content_hash自动生成"""
        result = InstantSearchResult(
            task_id="test-task-001",
            title="Test Article",
            url="https://example.com/article",
            content="This is test content"
        )

        # content_hash应该自动生成
        assert result.content_hash != ""
        assert len(result.content_hash) == 32  # MD5哈希长度

    def test_content_hash_consistency(self):
        """测试相同内容生成相同的content_hash"""
        result1 = InstantSearchResult(
            task_id="task-001",
            title="Same Title",
            url="https://example.com/same",
            content="Same content"
        )

        result2 = InstantSearchResult(
            task_id="task-002",
            title="Same Title",
            url="https://example.com/same",
            content="Same content"
        )

        # 相同的内容应该生成相同的hash
        assert result1.content_hash == result2.content_hash

    def test_content_hash_difference(self):
        """测试不同内容生成不同的content_hash"""
        result1 = InstantSearchResult(
            task_id="task-001",
            title="Title 1",
            url="https://example.com/1",
            content="Content 1"
        )

        result2 = InstantSearchResult(
            task_id="task-001",
            title="Title 2",
            url="https://example.com/2",
            content="Content 2"
        )

        # 不同的内容应该生成不同的hash
        assert result1.content_hash != result2.content_hash

    def test_url_normalization(self):
        """测试URL规范化"""
        test_cases = [
            # (input_url, expected_normalized)
            ("http://example.com/page?id=123#section", "https://example.com/page"),
            ("https://example.com/page/", "https://example.com/page"),
            ("https://Example.Com/Page", "https://example.com/Page"),
            ("http://example.com/page?utm_source=test", "https://example.com/page"),
        ]

        for input_url, expected in test_cases:
            result = InstantSearchResult(
                task_id="test",
                title="Test",
                url=input_url,
                content="Test content"
            )
            assert result.url_normalized == expected

    def test_record_new_discovery(self):
        """测试记录新发现"""
        result = InstantSearchResult(
            task_id="task-001",
            title="Test",
            url="https://example.com",
            content="Test"
        )

        initial_found_count = result.found_count
        initial_unique_searches = result.unique_searches

        # 记录新发现
        result.record_new_discovery("exec-002")

        assert result.found_count == initial_found_count + 1
        assert result.unique_searches == initial_unique_searches + 1


class TestInstantSearchResultMapping:
    """测试 InstantSearchResultMapping 实体"""

    def test_mapping_creation(self):
        """测试映射创建"""
        mapping = create_result_mapping(
            search_execution_id="exec-001",
            result_id="result-001",
            task_id="task-001",
            search_position=1,
            relevance_score=0.95,
            is_first_discovery=True
        )

        assert mapping.search_execution_id == "exec-001"
        assert mapping.result_id == "result-001"
        assert mapping.task_id == "task-001"
        assert mapping.search_position == 1
        assert mapping.relevance_score == 0.95
        assert mapping.is_first_discovery is True

    def test_mapping_id_generation(self):
        """测试映射ID自动生成"""
        mapping = create_result_mapping(
            search_execution_id="exec-001",
            result_id="result-001",
            task_id="task-001"
        )

        # ID应该自动生成
        assert mapping.id != ""
        assert len(mapping.id) > 0


class TestInstantSearchTask:
    """测试 InstantSearchTask 实体"""

    def test_task_creation(self):
        """测试任务创建"""
        task = InstantSearchTask(
            name="Test Search",
            query="test query",
            search_config={"limit": 10}
        )

        # 检查默认值
        assert task.status == InstantSearchStatus.PENDING
        assert task.total_results == 0
        assert task.new_results == 0
        assert task.shared_results == 0

    def test_search_mode_detection(self):
        """测试搜索模式检测"""
        # Search模式
        task1 = InstantSearchTask(
            name="Search Task",
            query="test query"
        )
        assert task1.get_search_mode() == "search"

        # Crawl模式
        task2 = InstantSearchTask(
            name="Crawl Task",
            crawl_url="https://example.com"
        )
        assert task2.get_search_mode() == "crawl"

        # Crawl优先于Search
        task3 = InstantSearchTask(
            name="Mixed Task",
            query="test query",
            crawl_url="https://example.com"
        )
        assert task3.get_search_mode() == "crawl"

    def test_mark_as_completed(self):
        """测试标记完成"""
        task = InstantSearchTask(
            name="Test Task",
            query="test"
        )

        task.mark_as_completed(
            total=10,
            new=7,
            shared=3,
            credits=1,
            execution_time=2500
        )

        assert task.status == InstantSearchStatus.COMPLETED
        assert task.total_results == 10
        assert task.new_results == 7
        assert task.shared_results == 3
        assert task.credits_used == 1
        assert task.execution_time_ms == 2500
        assert task.completed_at is not None

    def test_mark_as_failed(self):
        """测试标记失败"""
        task = InstantSearchTask(
            name="Test Task",
            query="test"
        )

        error_message = "Connection timeout"
        task.mark_as_failed(error_message)

        assert task.status == InstantSearchStatus.FAILED
        assert task.error_message == error_message
        assert task.completed_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
