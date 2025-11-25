"""
NL Search Service 测试
包含内容抓取功能的完整测试套件

测试覆盖:
1. 基本搜索流程
2. Firecrawl并发抓取
3. 错误处理
4. 配置控制
5. 性能验证

版本: v2.0.0 (MongoDB + Firecrawl)
日期: 2025-11-18
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.services.nl_search.nl_search_service import NLSearchService
from src.services.nl_search.config import nl_search_config


@pytest.fixture
def service():
    """创建NLSearchService实例"""
    return NLSearchService()


@pytest.fixture
def mock_search_results():
    """模拟搜索结果"""
    return [
        {
            "title": "GPT-5发布",
            "url": "https://example1.com/gpt5",
            "snippet": "OpenAI发布GPT-5...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi"
        },
        {
            "title": "AI技术突破",
            "url": "https://example2.com/ai-breakthrough",
            "snippet": "2024年AI技术...",
            "position": 2,
            "score": 0.90,
            "source": "serpapi"
        },
        {
            "title": "深度学习进展",
            "url": "https://example3.com/deep-learning",
            "snippet": "最新深度学习研究...",
            "position": 3,
            "score": 0.85,
            "source": "serpapi"
        }
    ]


@pytest.fixture
def mock_firecrawl_result():
    """模拟Firecrawl抓取结果"""
    mock_result = Mock()
    mock_result.markdown = "# GPT-5发布\n\nOpenAI今天正式发布了GPT-5模型..."
    mock_result.html = "<html><body><h1>GPT-5发布</h1><p>OpenAI今天正式发布...</p></body></html>"
    mock_result.metadata = Mock()
    mock_result.metadata.dict = Mock(return_value={
        "title": "GPT-5发布 - OpenAI",
        "description": "最新AI突破",
        "language": "zh-CN",
        "ogImage": "https://example.com/image.jpg"
    })
    return mock_result


class TestNLSearchServiceBasic:
    """基础搜索流程测试"""

    @pytest.mark.asyncio
    async def test_create_search_success(self, service):
        """测试成功创建搜索（不含抓取）"""
        # Mock dependencies
        with patch.object(service.repository, 'create', return_value="test_log_id"), \
             patch.object(service.llm_processor, 'parse_query', return_value={
                 "intent": "technology_news",
                 "keywords": ["AI", "技术突破"]
             }), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="AI技术突破 2024"), \
             patch.object(service.gpt5_adapter, 'search', return_value=[
                 Mock(to_dict=Mock(return_value={
                     "title": "GPT-5",
                     "url": "https://example.com",
                     "snippet": "test"
                 }))
             ]), \
             patch.object(service, '_scrape_search_results_concurrent', return_value=[
                 {"title": "GPT-5", "url": "https://example.com", "snippet": "test"}
             ]), \
             patch.object(service.repository, 'update_search_results', return_value=True):

            # 执行测试
            result = await service.create_search(
                query_text="最近AI技术突破",
                user_id="test_user"
            )

            # 验证结果
            assert result["log_id"] == "test_log_id"
            assert result["query_text"] == "最近AI技术突破"
            assert "analysis" in result
            assert "refined_query" in result
            assert "results" in result

    @pytest.mark.asyncio
    async def test_create_search_with_empty_query(self, service):
        """测试空查询文本"""
        with pytest.raises(ValueError, match="查询文本不能为空"):
            await service.create_search(query_text="", user_id="test_user")

    @pytest.mark.asyncio
    async def test_create_search_llm_failure(self, service):
        """测试LLM解析失败"""
        with patch.object(service.repository, 'create', return_value="test_log_id"), \
             patch.object(service.llm_processor, 'parse_query', side_effect=Exception("LLM API Error")):

            with pytest.raises(Exception, match="LLM API Error"):
                await service.create_search(
                    query_text="测试查询",
                    user_id="test_user"
                )


class TestFirecrawlScraping:
    """Firecrawl内容抓取测试"""

    @pytest.mark.asyncio
    async def test_scrape_search_results_concurrent_success(
        self,
        service,
        mock_search_results,
        mock_firecrawl_result
    ):
        """测试并发抓取成功"""
        # Mock Firecrawl adapter
        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            return_value=mock_firecrawl_result
        ):
            # 执行抓取
            enriched_results = await service._scrape_search_results_concurrent(
                search_results=mock_search_results,
                max_concurrent=3
            )

            # 验证结果
            assert len(enriched_results) == 3

            # 验证第一个结果的抓取内容
            result = enriched_results[0]
            assert result["scrape_success"] is True
            assert "markdown_content" in result
            assert "html_content" in result
            assert "metadata" in result
            assert len(result["markdown_content"]) <= 5000  # 内容限制
            assert len(result["html_content"]) <= 10000  # 内容限制

    @pytest.mark.asyncio
    async def test_scrape_with_disabled_auto_scrape(
        self,
        service,
        mock_search_results
    ):
        """测试禁用自动抓取"""
        # 修改配置
        original_value = nl_search_config.enable_auto_scrape
        nl_search_config.enable_auto_scrape = False

        try:
            # 执行抓取（应该跳过）
            enriched_results = await service._scrape_search_results_concurrent(
                search_results=mock_search_results,
                max_concurrent=3
            )

            # 验证：结果未被修改
            assert enriched_results == mock_search_results
            assert "markdown_content" not in enriched_results[0]

        finally:
            # 恢复配置
            nl_search_config.enable_auto_scrape = original_value

    @pytest.mark.asyncio
    async def test_scrape_with_missing_url(self, service):
        """测试缺少URL的结果"""
        # 创建缺少URL的结果
        results_no_url = [
            {"title": "测试标题", "snippet": "摘要"}
        ]

        # 执行抓取
        enriched_results = await service._scrape_search_results_concurrent(
            search_results=results_no_url,
            max_concurrent=3
        )

        # 验证：结果未被抓取
        assert enriched_results[0] == results_no_url[0]
        assert "scrape_success" not in enriched_results[0]

    @pytest.mark.asyncio
    async def test_scrape_with_api_error(
        self,
        service,
        mock_search_results
    ):
        """测试Firecrawl API错误"""
        # Mock Firecrawl抛出异常
        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            side_effect=Exception("Firecrawl API Error")
        ):
            # 执行抓取
            enriched_results = await service._scrape_search_results_concurrent(
                search_results=mock_search_results,
                max_concurrent=3
            )

            # 验证：所有结果标记为失败
            for result in enriched_results:
                assert result["scrape_success"] is False
                assert "Firecrawl API Error" in result["scrape_error"]

    @pytest.mark.asyncio
    async def test_scrape_concurrent_limit(
        self,
        service,
        mock_search_results,
        mock_firecrawl_result
    ):
        """测试并发数限制"""
        # 创建10个结果
        large_results = mock_search_results * 4  # 12个结果

        scrape_count = 0

        async def mock_scrape(*args, **kwargs):
            nonlocal scrape_count
            scrape_count += 1
            await asyncio.sleep(0.1)  # 模拟抓取延迟
            return mock_firecrawl_result

        # Mock Firecrawl
        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            side_effect=mock_scrape
        ):
            # 执行抓取（并发数=3）
            start_time = asyncio.get_event_loop().time()
            await service._scrape_search_results_concurrent(
                search_results=large_results,
                max_concurrent=3
            )
            duration = asyncio.get_event_loop().time() - start_time

            # 验证：总共抓取12次
            assert scrape_count == 12

            # 验证：并发控制生效（12个任务,并发3,每个0.1秒 ≈ 0.4秒）
            assert duration < 0.6  # 允许一定误差

    @pytest.mark.asyncio
    async def test_scrape_content_truncation(
        self,
        service,
        mock_search_results
    ):
        """测试内容长度截断"""
        # 创建超长内容的Firecrawl结果
        long_content_result = Mock()
        long_content_result.markdown = "a" * 10000  # 超过5000限制
        long_content_result.html = "b" * 20000  # 超过10000限制
        long_content_result.metadata = Mock()
        long_content_result.metadata.dict = Mock(return_value={})

        # Mock Firecrawl
        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            return_value=long_content_result
        ):
            # 执行抓取
            enriched_results = await service._scrape_search_results_concurrent(
                search_results=mock_search_results[:1],
                max_concurrent=1
            )

            # 验证：内容被截断
            result = enriched_results[0]
            assert len(result["markdown_content"]) == 5000
            assert len(result["html_content"]) == 10000


class TestServiceIntegration:
    """服务层集成测试"""

    @pytest.mark.asyncio
    async def test_get_search_results_with_scrape_content(self, service):
        """测试获取包含抓取内容的搜索结果"""
        # Mock repository返回包含抓取内容的结果
        mock_log = {
            "_id": "test_log_id",
            "query_text": "测试查询",
            "created_at": datetime.utcnow()
        }

        mock_results = [
            {
                "title": "测试结果",
                "url": "https://example.com",
                "snippet": "测试摘要",
                "position": 1,
                "score": 0.95,
                "source": "serpapi",
                # 抓取内容
                "markdown_content": "# 测试内容",
                "html_content": "<html>...</html>",
                "metadata": {"title": "测试页面"},
                "scrape_success": True
            }
        ]

        with patch.object(service.repository, 'get_by_id', return_value=mock_log), \
             patch.object(service.repository, 'get_search_results', return_value=mock_results):

            # 执行测试
            result = await service.get_search_results(
                log_id="test_log_id",
                limit=10,
                offset=0
            )

            # 验证结果包含抓取内容
            assert result is not None
            assert len(result["results"]) == 1
            assert result["results"][0]["markdown_content"] == "# 测试内容"
            assert result["results"][0]["scrape_success"] is True

    @pytest.mark.asyncio
    async def test_get_service_status(self, service):
        """测试服务状态"""
        status = await service.get_service_status()

        # 验证状态信息
        assert "enabled" in status
        assert "version" in status
        assert "llm_configured" in status
        assert "search_configured" in status


class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_scrape_performance_baseline(
        self,
        service,
        mock_search_results,
        mock_firecrawl_result
    ):
        """测试抓取性能基准"""
        # 创建20个结果
        large_results = mock_search_results * 7  # 21个结果

        async def mock_scrape(*args, **kwargs):
            await asyncio.sleep(0.05)  # 模拟50ms抓取时间
            return mock_firecrawl_result

        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            side_effect=mock_scrape
        ):
            # 执行抓取并测量时间
            import time
            start_time = time.time()

            await service._scrape_search_results_concurrent(
                search_results=large_results,
                max_concurrent=3
            )

            duration = time.time() - start_time

            # 验证性能：21个任务,并发3,每个50ms ≈ 0.35秒
            # 允许一定开销,设置为1秒上限
            assert duration < 1.0, f"抓取耗时 {duration:.2f}秒，超过性能预期"

    @pytest.mark.asyncio
    async def test_memory_usage_with_large_content(
        self,
        service,
        mock_search_results
    ):
        """测试大量内容的内存使用"""
        # 创建100个结果
        large_results = mock_search_results * 34  # 102个结果

        # 模拟大内容
        large_content_result = Mock()
        large_content_result.markdown = "x" * 4000
        large_content_result.html = "y" * 9000
        large_content_result.metadata = Mock()
        large_content_result.metadata.dict = Mock(return_value={})

        with patch.object(
            service.firecrawl_adapter,
            'scrape',
            return_value=large_content_result
        ):
            # 执行抓取
            enriched_results = await service._scrape_search_results_concurrent(
                search_results=large_results,
                max_concurrent=5
            )

            # 验证：所有结果都被处理
            assert len(enriched_results) == 102

            # 验证：内存占用合理（简单检查对象数量）
            import sys
            total_size = sum(
                sys.getsizeof(r.get("markdown_content", "")) +
                sys.getsizeof(r.get("html_content", ""))
                for r in enriched_results
            )

            # 预期: 102 * (4000 + 9000) ≈ 1.3MB
            assert total_size < 2 * 1024 * 1024, "内存占用超过2MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
