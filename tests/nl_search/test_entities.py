"""
测试 NL Search 实体 (简化版)

测试内容:
- NLSearchLog 实体的创建和属性
- LLM 分析结果的解析
- 实体的辅助方法
"""
import pytest
from datetime import datetime

from src.core.domain.entities.nl_search import NLSearchLog, SearchStatus


class TestNLSearchLog:
    """测试 NLSearchLog 实体"""

    def test_create_log_basic(self):
        """测试创建基础搜索记录"""
        log = NLSearchLog(
            query_text="最近有哪些AI技术突破"
        )

        assert log.query_text == "最近有哪些AI技术突破"
        assert log.llm_analysis is None
        assert log.id is None
        assert log.created_at is None

    def test_create_log_with_analysis(self):
        """测试创建包含分析结果的记录"""
        llm_analysis = {
            "intent": "technology_news",
            "keywords": ["AI", "技术突破"],
            "confidence": 0.95
        }

        log = NLSearchLog(
            query_text="AI技术",
            llm_analysis=llm_analysis
        )

        assert log.query_text == "AI技术"
        assert log.llm_analysis["intent"] == "technology_news"
        assert len(log.llm_analysis["keywords"]) == 2
        assert log.llm_analysis["confidence"] == 0.95

    def test_log_with_id_and_timestamp(self):
        """测试包含 ID 和时间戳的记录"""
        now = datetime.now()
        log = NLSearchLog(
            id=123456,
            query_text="测试查询",
            created_at=now
        )

        assert log.id == 123456
        assert log.query_text == "测试查询"
        assert log.created_at == now

    def test_has_llm_analysis_property(self):
        """测试 has_llm_analysis 属性"""
        # 没有分析结果
        log1 = NLSearchLog(query_text="test")
        assert log1.has_llm_analysis is False

        # 有分析结果
        log2 = NLSearchLog(
            query_text="test",
            llm_analysis={"intent": "test"}
        )
        assert log2.has_llm_analysis is True

        # 空分析结果
        log3 = NLSearchLog(
            query_text="test",
            llm_analysis={}
        )
        assert log3.has_llm_analysis is False

    def test_keywords_property(self):
        """测试 keywords 属性"""
        # 没有关键词
        log1 = NLSearchLog(query_text="test")
        assert log1.keywords == []

        # 有关键词
        log2 = NLSearchLog(
            query_text="test",
            llm_analysis={"keywords": ["AI", "技术", "2024"]}
        )
        assert log2.keywords == ["AI", "技术", "2024"]

    def test_intent_property(self):
        """测试 intent 属性"""
        # 没有意图
        log1 = NLSearchLog(query_text="test")
        assert log1.intent is None

        # 有意图
        log2 = NLSearchLog(
            query_text="test",
            llm_analysis={"intent": "technology_news"}
        )
        assert log2.intent == "technology_news"

    def test_confidence_property(self):
        """测试 confidence 属性"""
        # 没有置信度
        log1 = NLSearchLog(query_text="test")
        assert log1.confidence == 0.0

        # 有置信度
        log2 = NLSearchLog(
            query_text="test",
            llm_analysis={"confidence": 0.95}
        )
        assert log2.confidence == 0.95

    def test_repr_and_str(self):
        """测试字符串表示"""
        log = NLSearchLog(
            id=123456,
            query_text="测试非常长的查询文本，用于测试字符串截断功能，确保显示正常"
        )

        repr_str = repr(log)
        assert "NLSearchLog" in repr_str
        assert "123456" in repr_str

        str_str = str(log)
        assert "NL Search #123456" in str_str
        assert "测试非常长" in str_str


class TestSearchStatus:
    """测试 SearchStatus 枚举"""

    def test_status_values(self):
        """测试状态值"""
        assert SearchStatus.PENDING.value == "pending"
        assert SearchStatus.PROCESSING.value == "processing"
        assert SearchStatus.COMPLETED.value == "completed"
        assert SearchStatus.FAILED.value == "failed"

    def test_status_str(self):
        """测试状态字符串转换"""
        assert str(SearchStatus.PENDING) == "pending"
        assert str(SearchStatus.COMPLETED) == "completed"

    def test_is_valid(self):
        """测试状态验证"""
        assert SearchStatus.is_valid("pending") is True
        assert SearchStatus.is_valid("completed") is True
        assert SearchStatus.is_valid("invalid") is False
        assert SearchStatus.is_valid("") is False


class TestNLSearchLogValidation:
    """测试 NLSearchLog 验证"""

    def test_query_text_required(self):
        """测试 query_text 必填"""
        with pytest.raises(ValueError):
            NLSearchLog()

    def test_query_text_length(self):
        """测试 query_text 长度限制"""
        # 正常长度
        log1 = NLSearchLog(query_text="AI技术")
        assert log1.query_text == "AI技术"

        # 边界测试 - 最小长度
        log2 = NLSearchLog(query_text="A")
        assert log2.query_text == "A"

        # 边界测试 - 最大长度 (1000)
        long_text = "A" * 1000
        log3 = NLSearchLog(query_text=long_text)
        assert len(log3.query_text) == 1000

    def test_llm_analysis_optional(self):
        """测试 llm_analysis 可选"""
        log = NLSearchLog(query_text="test")
        assert log.llm_analysis is None

        log_with_analysis = NLSearchLog(
            query_text="test",
            llm_analysis={"key": "value"}
        )
        assert log_with_analysis.llm_analysis == {"key": "value"}
