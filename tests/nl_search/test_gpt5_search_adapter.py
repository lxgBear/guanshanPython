"""
GPT-5 搜索适配器测试

测试覆盖:
- 初始化测试 (3 个)
- 搜索功能测试 (8 个)
- 结果解析测试 (4 个)
- 结果过滤和排序测试 (5 个)
- 批量搜索测试 (3 个)
- 错误处理测试 (4 个)
- 重试机制测试 (3 个)
- 异步上下文管理器测试 (2 个)

总计: 32 个测试
目标覆盖率: >85%
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# 导入被测试的类
from src.services.nl_search.gpt5_search_adapter import (
    GPT5SearchAdapter,
    SearchResult
)
from src.services.nl_search.config import NLSearchConfig


# ==================== 测试辅助函数 ====================

def create_mock_search_response(query: str, num_results: int = 5) -> Dict[str, Any]:
    """创建模拟的搜索 API 响应"""
    organic_results = []
    for i in range(num_results):
        organic_results.append({
            "position": i + 1,
            "title": f"结果 {i+1}: {query}",
            "link": f"https://example.com/{query}-{i+1}",
            "snippet": f"这是关于 {query} 的搜索结果摘要 {i+1}"
        })

    return {
        "organic_results": organic_results,
        "search_metadata": {
            "status": "Success",
            "total_results": num_results
        }
    }


# ==================== SearchResult 数据类测试 ====================

class TestSearchResult:
    """SearchResult 数据类测试"""

    def test_search_result_creation(self):
        """测试创建 SearchResult"""
        result = SearchResult(
            title="测试标题",
            url="https://example.com",
            snippet="测试摘要",
            position=1,
            score=0.95,
            source="test"
        )

        assert result.title == "测试标题"
        assert result.url == "https://example.com"
        assert result.snippet == "测试摘要"
        assert result.position == 1
        assert result.score == 0.95
        assert result.source == "test"

    def test_search_result_to_dict(self):
        """测试 SearchResult 转换为字典"""
        result = SearchResult(
            title="测试标题",
            url="https://example.com"
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["title"] == "测试标题"
        assert result_dict["url"] == "https://example.com"
        assert "snippet" in result_dict
        assert "position" in result_dict
        assert "score" in result_dict
        assert "source" in result_dict


# ==================== GPT5SearchAdapter 初始化测试 ====================

class TestGPT5SearchAdapterInit:
    """GPT5SearchAdapter 初始化测试"""

    def test_init_with_valid_config(self):
        """测试使用有效配置初始化"""
        adapter = GPT5SearchAdapter(
            api_key="test_api_key",
            test_mode=False,
            timeout=30
        )

        assert adapter.api_key == "test_api_key"
        assert adapter.test_mode is False
        assert adapter.timeout == 30
        assert adapter.client is not None

    def test_init_without_api_key(self):
        """测试没有 API Key 时的初始化"""
        adapter = GPT5SearchAdapter(test_mode=True)

        # 测试模式下不需要 API Key
        assert adapter.test_mode is True
        assert adapter.client is not None

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        with patch('src.services.nl_search.gpt5_search_adapter.nl_search_config') as mock_config:
            mock_config.gpt5_search_api_key = "default_key"
            mock_config.gpt5_max_results = 10

            adapter = GPT5SearchAdapter()

            assert adapter.api_key == "default_key"
            assert adapter.max_results == 10


# ==================== 搜索功能测试 ====================

class TestSearch:
    """搜索功能测试"""

    @pytest.mark.asyncio
    async def test_search_in_test_mode(self):
        """测试搜索（测试模式）"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("AI技术", max_results=5)

        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.source == "test" for r in results)
        assert all("AI技术" in r.title for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """测试空查询"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_whitespace_query(self):
        """测试仅空白字符的查询"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("   ")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_without_api_key_raises_error(self):
        """测试没有 API Key 时搜索抛出错误"""
        adapter = GPT5SearchAdapter(api_key=None, test_mode=False)

        with pytest.raises(ValueError, match="API Key 未配置"):
            await adapter.search("测试查询")

    @pytest.mark.asyncio
    async def test_search_success_with_mock_api(self):
        """测试搜索成功（模拟 API）"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock HTTP 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = create_mock_search_response("AI", 5)

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = await adapter.search("AI", max_results=5)

            assert len(results) == 5
            assert all(isinstance(r, SearchResult) for r in results)
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_custom_language(self):
        """测试使用自定义语言搜索"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("AI", language="en")

        assert len(results) > 0
        # 测试模式下不验证语言参数，仅确保不抛出异常

    @pytest.mark.asyncio
    async def test_search_returns_sorted_results(self):
        """测试搜索返回排序后的结果"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("技术", max_results=10)

        # 验证结果按 score 降序排列
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self):
        """测试搜索尊重最大结果数限制"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.search("测试", max_results=3)

        assert len(results) == 3


# ==================== 结果解析测试 ====================

class TestResultParsing:
    """结果解析测试"""

    def test_parse_search_results_success(self):
        """测试解析搜索结果成功"""
        adapter = GPT5SearchAdapter(test_mode=True)

        data = create_mock_search_response("测试", 3)
        results = adapter._parse_search_results(data)

        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].title == "结果 1: 测试"
        assert results[0].position == 1

    def test_parse_search_results_empty(self):
        """测试解析空结果"""
        adapter = GPT5SearchAdapter(test_mode=True)

        data = {"organic_results": []}
        results = adapter._parse_search_results(data)

        assert results == []

    def test_parse_search_results_missing_fields(self):
        """测试解析缺少字段的结果"""
        adapter = GPT5SearchAdapter(test_mode=True)

        data = {
            "organic_results": [
                {"position": 1},  # 缺少 title, link, snippet
                {"title": "标题2", "link": "https://example.com/2"}  # 缺少 position
            ]
        }

        results = adapter._parse_search_results(data)

        assert len(results) == 2
        assert results[0].title == ""
        assert results[1].position == 0

    def test_parse_search_results_invalid_item_skipped(self):
        """测试跳过无效的结果项"""
        adapter = GPT5SearchAdapter(test_mode=True)

        data = {
            "organic_results": [
                {"position": 1, "title": "有效结果", "link": "https://example.com/1"},
                None,  # 无效项
                {"position": 2, "title": "另一个有效结果", "link": "https://example.com/2"}
            ]
        }

        # 注意：_parse_search_results 会尝试解析所有项，None 会导致 AttributeError
        # 但会被 try-except 捕获并跳过
        with patch('src.services.nl_search.gpt5_search_adapter.logger'):
            results = adapter._parse_search_results(data)

        # 只有 2 个有效结果
        assert len(results) == 2


# ==================== 结果过滤和排序测试 ====================

class TestFilterAndSort:
    """结果过滤和排序测试"""

    def test_filter_and_sort_removes_duplicates(self):
        """测试去除重复 URL"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = [
            SearchResult(title="结果1", url="https://example.com/1", score=0.9, position=1),
            SearchResult(title="结果2", url="https://example.com/1", score=0.8, position=2),  # 重复
            SearchResult(title="结果3", url="https://example.com/2", score=0.7, position=3)
        ]

        filtered = adapter._filter_and_sort_results(results, max_results=10)

        assert len(filtered) == 2
        assert filtered[0].url == "https://example.com/1"
        assert filtered[1].url == "https://example.com/2"

    def test_filter_and_sort_by_score(self):
        """测试按 score 排序"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = [
            SearchResult(title="结果1", url="https://example.com/1", score=0.7, position=1),
            SearchResult(title="结果2", url="https://example.com/2", score=0.9, position=2),
            SearchResult(title="结果3", url="https://example.com/3", score=0.8, position=3)
        ]

        sorted_results = adapter._filter_and_sort_results(results, max_results=10)

        assert sorted_results[0].score == 0.9
        assert sorted_results[1].score == 0.8
        assert sorted_results[2].score == 0.7

    def test_filter_and_sort_limits_results(self):
        """测试限制结果数量"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = [
            SearchResult(title=f"结果{i}", url=f"https://example.com/{i}", score=1.0-i*0.1, position=i)
            for i in range(10)
        ]

        limited = adapter._filter_and_sort_results(results, max_results=5)

        assert len(limited) == 5

    def test_filter_and_sort_empty_list(self):
        """测试空结果列表"""
        adapter = GPT5SearchAdapter(test_mode=True)

        filtered = adapter._filter_and_sort_results([], max_results=10)

        assert filtered == []

    def test_filter_and_sort_by_position_when_same_score(self):
        """测试相同 score 时按 position 排序"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = [
            SearchResult(title="结果1", url="https://example.com/1", score=0.9, position=3),
            SearchResult(title="结果2", url="https://example.com/2", score=0.9, position=1),
            SearchResult(title="结果3", url="https://example.com/3", score=0.9, position=2)
        ]

        sorted_results = adapter._filter_and_sort_results(results, max_results=10)

        # 相同 score 时，按 position 升序
        assert sorted_results[0].position == 1
        assert sorted_results[1].position == 2
        assert sorted_results[2].position == 3


# ==================== 批量搜索测试 ====================

class TestBatchSearch:
    """批量搜索测试"""

    @pytest.mark.asyncio
    async def test_batch_search_success(self):
        """测试批量搜索成功"""
        adapter = GPT5SearchAdapter(test_mode=True)

        queries = ["AI", "Python", "机器学习"]
        results = await adapter.batch_search(queries, max_results_per_query=5)

        assert len(results) == 3
        assert "AI" in results
        assert "Python" in results
        assert "机器学习" in results
        assert all(len(r) == 5 for r in results.values())

    @pytest.mark.asyncio
    async def test_batch_search_empty_list(self):
        """测试空查询列表"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = await adapter.batch_search([])

        assert results == {}

    @pytest.mark.asyncio
    async def test_batch_search_handles_errors(self):
        """测试批量搜索处理错误"""
        adapter = GPT5SearchAdapter(test_mode=False, api_key=None)

        queries = ["查询1", "查询2"]

        # 没有 API Key，搜索会失败
        results = await adapter.batch_search(queries)

        # 失败的查询返回空列表
        assert len(results) == 2
        assert results["查询1"] == []
        assert results["查询2"] == []


# ==================== 错误处理测试 ====================

class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_search_api_error_response(self):
        """测试搜索 API 返回错误"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock HTTP 错误响应
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="搜索 API 返回错误"):
                await adapter.search("测试查询")

    @pytest.mark.asyncio
    async def test_search_json_decode_error(self):
        """测试 JSON 解析错误"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock 无效 JSON 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(Exception):
                await adapter.search("测试查询")

    @pytest.mark.asyncio
    async def test_search_timeout_error(self):
        """测试搜索超时错误"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock 超时异常
        import httpx

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(httpx.TimeoutException):
                await adapter.search("测试查询")

    @pytest.mark.asyncio
    async def test_search_network_error(self):
        """测试网络错误"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock 网络异常
        import httpx

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.NetworkError("Network error")

            with pytest.raises(httpx.NetworkError):
                await adapter.search("测试查询")


# ==================== 重试机制测试 ====================

class TestRetryMechanism:
    """重试机制测试（需要 tenacity 库）"""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """测试超时时重试"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        import httpx

        # Mock: 前 2 次超时，第 3 次成功
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = create_mock_search_response("测试", 3)

        call_count = 0

        async def mock_get_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = mock_get_with_retry

            # 应该重试并最终成功
            results = await adapter.search("测试")

            assert len(results) == 3
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """测试重试次数耗尽"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        import httpx

        # Mock: 总是超时
        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(httpx.TimeoutException):
                await adapter.search("测试")

            # 应该重试 3 次
            assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """测试不可重试的错误不重试"""
        adapter = GPT5SearchAdapter(api_key="test_key", test_mode=False)

        # Mock 非网络错误（如 API Key 错误）
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(adapter.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="搜索 API 返回错误"):
                await adapter.search("测试")

            # 不应重试
            assert mock_get.call_count == 1


# ==================== 异步上下文管理器测试 ====================

class TestAsyncContextManager:
    """异步上下文管理器测试"""

    @pytest.mark.asyncio
    async def test_async_context_manager_enter(self):
        """测试异步上下文管理器进入"""
        async with GPT5SearchAdapter(test_mode=True) as adapter:
            assert adapter is not None
            assert adapter.client is not None

    @pytest.mark.asyncio
    async def test_async_context_manager_exit(self):
        """测试异步上下文管理器退出（关闭客户端）"""
        adapter = GPT5SearchAdapter(test_mode=True)

        async with adapter:
            pass  # 进入和退出

        # 客户端应该被关闭
        # 注意：httpx.AsyncClient 关闭后，is_closed 属性为 True
        assert adapter.client.is_closed


# ==================== 测试辅助模拟数据生成 ====================

class TestGenerateTestResults:
    """测试模拟数据生成"""

    def test_generate_test_results_correct_count(self):
        """测试生成正确数量的模拟结果"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = adapter._generate_test_results("测试查询", max_results=7)

        assert len(results) == 7

    def test_generate_test_results_contains_query(self):
        """测试模拟结果包含查询关键词"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = adapter._generate_test_results("Python", max_results=5)

        assert all("Python" in r.title for r in results)

    def test_generate_test_results_decreasing_scores(self):
        """测试模拟结果分数递减"""
        adapter = GPT5SearchAdapter(test_mode=True)

        results = adapter._generate_test_results("AI", max_results=10)

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
