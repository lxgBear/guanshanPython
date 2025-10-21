"""
Firecrawl Search Adapter 单元测试

测试覆盖范围:
- 适配器初始化
- 搜索功能 (成功、失败、重试)
- 请求体构建
- 响应解析
- 批量搜索
- 错误处理
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import httpx

# 设置测试环境变量
os.environ["TESTING"] = "true"
os.environ["FIRECRAWL_API_KEY"] = "test-api-key"
os.environ["TEST_MODE"] = "false"  # 测试真实逻辑，不使用测试模式

from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.core.domain.entities.search_config import UserSearchConfig
from src.core.domain.entities.search_result import ResultStatus

from tests.fixtures import (
    create_mock_search_response,
    create_mock_error_response,
    create_mock_search_config,
    assert_search_result_valid,
    PerformanceTimer
)


class TestFirecrawlSearchAdapterInitialization:
    """测试适配器初始化"""

    def test_adapter_initialization(self):
        """测试适配器正确初始化"""
        adapter = FirecrawlSearchAdapter()

        # 验证API密钥配置
        assert adapter.api_key == "test-api-key"
        assert adapter.base_url == "https://api.firecrawl.dev"

        # 验证headers配置
        assert "Authorization" in adapter.headers
        assert adapter.headers["Authorization"] == "Bearer test-api-key"
        assert adapter.headers["Content-Type"] == "application/json"

        # 验证测试模式关闭
        assert adapter.is_test_mode == False

        # 验证配置管理器初始化
        assert adapter.config_manager is not None

    def test_adapter_test_mode_enabled(self):
        """测试适配器测试模式启用"""
        os.environ["TEST_MODE"] = "true"

        adapter = FirecrawlSearchAdapter()

        assert adapter.is_test_mode == True

        # 恢复环境变量
        os.environ["TEST_MODE"] = "false"


class TestSearchFunctionality:
    """测试搜索功能"""

    @pytest_asyncio.fixture
    async def adapter_with_mock(self):
        """创建带模拟HTTP客户端的适配器"""
        adapter = FirecrawlSearchAdapter()
        return adapter

    @pytest.mark.asyncio
    async def test_search_success_basic(self, adapter_with_mock):
        """测试基础搜索成功场景"""
        adapter = adapter_with_mock

        # 模拟HTTP响应
        mock_response = create_mock_search_response(count=10, api_version="v2")

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )

            # 执行搜索
            result_batch = await adapter.search(
                query="Python async",
                task_id="test_task_123"
            )

            # 验证结果
            assert result_batch.success == True
            assert len(result_batch.results) == 10
            assert result_batch.total_count == 10
            assert result_batch.credits_used == 1

            # 验证每个结果
            for result in result_batch.results:
                assert_search_result_valid(result, strict=False)
                assert result.task_id == "test_task_123"

    @pytest.mark.asyncio
    async def test_search_with_custom_config(self, adapter_with_mock):
        """测试带自定义配置的搜索"""
        adapter = adapter_with_mock

        # 创建自定义配置
        custom_config = UserSearchConfig(
            template_name="custom",
            overrides={
                "limit": 5,
                "language": "en",
                "time_range": "week",
                "include_domains": ["example.com", "test.com"]
            }
        )

        mock_response = create_mock_search_response(count=5)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )

            result_batch = await adapter.search(
                query="test query",
                user_config=custom_config,
                task_id="test_123"
            )

            # 验证请求被正确调用
            assert mock_post.called
            call_args = mock_post.call_args

            # 验证请求body包含自定义配置
            request_body = call_args[1]["json"]
            assert request_body["limit"] == 5
            assert request_body["lang"] == "en"
            assert request_body["tbs"] == "qdr:w"  # week
            assert "(site:example.com OR site:test.com)" in request_body["query"]

            # 验证结果
            assert result_batch.success == True
            assert len(result_batch.results) == 5

    @pytest.mark.asyncio
    async def test_search_test_mode(self):
        """测试测试模式返回模拟数据"""
        os.environ["TEST_MODE"] = "true"
        adapter = FirecrawlSearchAdapter()

        result_batch = await adapter.search(
            query="test query",
            task_id="test_123"
        )

        # 验证测试模式结果
        assert result_batch.is_test_mode == True
        assert len(result_batch.results) == 10
        assert result_batch.credits_used == 0  # 测试模式不消耗credits

        # 验证测试数据标记
        for result in result_batch.results:
            assert result.is_test_data == True

        # 恢复环境变量
        os.environ["TEST_MODE"] = "false"


class TestErrorHandling:
    """测试错误处理"""

    @pytest_asyncio.fixture
    async def adapter(self):
        return FirecrawlSearchAdapter()

    @pytest.mark.asyncio
    async def test_http_401_unauthorized(self, adapter):
        """测试401未授权错误"""
        mock_error = create_mock_error_response(
            status_code=401,
            message="Invalid API key"
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = mock_error
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response
            )
            mock_post.return_value = mock_response

            result_batch = await adapter.search(
                query="test",
                task_id="test_123"
            )

            # 验证错误被正确处理
            assert result_batch.success == False
            assert result_batch.error_message is not None
            assert "401" in result_batch.error_message

    @pytest.mark.asyncio
    async def test_http_429_rate_limit(self, adapter):
        """测试429速率限制错误"""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.json.return_value = {"error": "Rate limit exceeded"}
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=mock_response
            )
            mock_post.return_value = mock_response

            result_batch = await adapter.search(
                query="test",
                task_id="test_123"
            )

            assert result_batch.success == False
            assert "429" in result_batch.error_message

    @pytest.mark.asyncio
    async def test_timeout_error(self, adapter):
        """测试超时错误"""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            result_batch = await adapter.search(
                query="test",
                task_id="test_123"
            )

            assert result_batch.success == False
            assert "timeout" in result_batch.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, adapter):
        """测试连接错误"""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")

            result_batch = await adapter.search(
                query="test",
                task_id="test_123"
            )

            assert result_batch.success == False


class TestRequestBodyBuilding:
    """测试请求体构建"""

    def setup_method(self):
        self.adapter = FirecrawlSearchAdapter()

    def test_basic_request_body(self):
        """测试基础请求体构建"""
        config = {
            "limit": 10,
            "language": "zh"
        }

        body = self.adapter._build_request_body("test query", config)

        assert body["query"] == "test query"
        assert body["limit"] == 10
        assert body["lang"] == "zh"
        assert "scrapeOptions" in body
        assert body["scrapeOptions"]["formats"] == ["markdown", "html", "links"]
        assert body["scrapeOptions"]["onlyMainContent"] == True

    def test_request_body_with_domain_filter(self):
        """测试带域名过滤的请求体"""
        config = {
            "limit": 10,
            "include_domains": ["example.com", "test.com"]
        }

        body = self.adapter._build_request_body("test query", config)

        # 验证site:操作符被正确添加
        assert "(site:example.com OR site:test.com)" in body["query"]
        assert "test query" in body["query"]

    def test_request_body_with_time_range(self):
        """测试带时间范围的请求体"""
        config = {
            "limit": 10,
            "time_range": "month"
        }

        body = self.adapter._build_request_body("test query", config)

        assert body["tbs"] == "qdr:m"

    @pytest.mark.parametrize("time_range,expected_tbs", [
        ("day", "qdr:d"),
        ("week", "qdr:w"),
        ("month", "qdr:m"),
        ("year", "qdr:y"),
    ])
    def test_time_range_conversion(self, time_range, expected_tbs):
        """测试时间范围转换"""
        result = self.adapter._convert_time_range(time_range)
        assert result == expected_tbs


class TestResponseParsing:
    """测试响应解析"""

    def setup_method(self):
        self.adapter = FirecrawlSearchAdapter()

    def test_parse_v2_format(self):
        """测试v2格式响应解析"""
        data = create_mock_search_response(count=5, api_version="v2")

        results = self.adapter._parse_search_results(data, task_id="test_123")

        assert len(results) == 5
        for result in results:
            assert result.task_id == "test_123"
            assert result.title
            assert result.url
            assert result.content

    def test_parse_v0_format(self):
        """测试v0格式响应解析(向后兼容)"""
        data = create_mock_search_response(count=5, api_version="v0")

        results = self.adapter._parse_search_results(data, task_id="test_123")

        assert len(results) == 5

    def test_parse_empty_results(self):
        """测试空结果解析"""
        data = {
            "success": True,
            "data": {"web": []},
            "creditsUsed": 0
        }

        results = self.adapter._parse_search_results(data, task_id="test_123")

        assert len(results) == 0

    def test_markdown_truncation(self):
        """测试markdown内容截断"""
        # 创建超长markdown内容
        long_markdown = "# Test\n" + ("Content " * 2000)  # 超过5000字符

        data = {
            "success": True,
            "data": {
                "web": [{
                    "url": "https://example.com",
                    "title": "Test",
                    "description": "Test desc",
                    "markdown": long_markdown,
                    "metadata": {}
                }]
            }
        }

        results = self.adapter._parse_search_results(data, task_id="test_123")

        assert len(results) == 1
        # 验证markdown被截断到5000字符
        assert len(results[0].markdown_content) <= 5000

    def test_metadata_filtering(self):
        """测试metadata精简"""
        data = {
            "success": True,
            "data": {
                "web": [{
                    "url": "https://example.com",
                    "title": "Test",
                    "description": "Test desc",
                    "metadata": {
                        "language": "zh",
                        "og:type": "article",
                        "redundant_field1": "value1",
                        "redundant_field2": "value2"
                    }
                }]
            }
        }

        results = self.adapter._parse_search_results(data, task_id="test_123")

        # 验证只保留关键字段
        assert "language" in results[0].metadata
        assert "og_type" in results[0].metadata
        # 冗余字段应被过滤
        assert "redundant_field1" not in results[0].metadata


class TestBatchSearch:
    """测试批量搜索"""

    @pytest.mark.asyncio
    async def test_batch_search_success(self):
        """测试批量搜索成功"""
        adapter = FirecrawlSearchAdapter()

        queries = [
            {"query": "query1", "task_id": "task1"},
            {"query": "query2", "task_id": "task2"},
            {"query": "query3", "task_id": "task3"}
        ]

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = create_mock_search_response(count=5)
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )

            batches = await adapter.batch_search(queries)

            # 验证所有查询都被执行
            assert len(batches) == 3
            assert all(batch.success for batch in batches)

    @pytest.mark.asyncio
    async def test_batch_search_partial_failure(self):
        """测试批量搜索部分失败"""
        adapter = FirecrawlSearchAdapter()

        queries = [
            {"query": "query1", "task_id": "task1"},
            {"query": "query2", "task_id": "task2"},
        ]

        with patch("httpx.AsyncClient.post") as mock_post:
            # 第一个成功，第二个失败
            success_response = create_mock_search_response(count=5)
            mock_post.side_effect = [
                MagicMock(status_code=200, json=lambda: success_response),
                httpx.TimeoutException("Timeout")
            ]

            batches = await adapter.batch_search(queries)

            assert len(batches) == 2
            assert batches[0].success == True
            assert batches[1].success == False


class TestPerformance:
    """测试性能指标"""

    @pytest.mark.asyncio
    async def test_search_performance(self):
        """测试搜索性能"""
        adapter = FirecrawlSearchAdapter()

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = create_mock_search_response(count=10)
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response
            )

            timer = PerformanceTimer()
            timer.start()

            result_batch = await adapter.search(
                query="performance test",
                task_id="test_123"
            )

            timer.stop()

            # 验证响应时间记录
            assert result_batch.execution_time_ms > 0

            # 注意: 实际性能要求根据业务需求调整
            # 这里只是示例


# ==========================================
# 运行测试
# ==========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
