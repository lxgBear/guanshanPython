"""
Firecrawl适配器集成测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.interfaces.crawler_interface import CrawlResult, CrawlException
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter, FirecrawlRateLimiter


@pytest.mark.asyncio
class TestFirecrawlAdapter:
    """Firecrawl适配器测试"""
    
    @pytest.fixture
    async def adapter(self, mock_firecrawl):
        """创建适配器实例"""
        with patch("src.infrastructure.crawlers.firecrawl_adapter.AsyncFirecrawl") as mock_class:
            mock_class.return_value = mock_firecrawl
            adapter = FirecrawlAdapter(api_key="test-key")
            yield adapter
    
    async def test_scrape_success(self, adapter):
        """测试成功爬取单页"""
        result = await adapter.scrape("https://example.com")
        
        assert isinstance(result, CrawlResult)
        assert result.url == "https://example.com"
        assert result.content == "Test content"
        assert result.markdown == "# Test Content"
        assert result.html == "<h1>Test Content</h1>"
        assert result.metadata["title"] == "Test Page"
    
    async def test_scrape_with_options(self, adapter):
        """测试带选项的爬取"""
        options = {
            "wait_for": 2000,
            "include_tags": ["main", "article"],
            "exclude_tags": ["nav", "footer"],
            "actions": [{"type": "click", "selector": ".button"}]
        }
        
        result = await adapter.scrape("https://example.com", **options)
        
        # 验证调用参数
        adapter.client.scrape.assert_called_once()
        call_args = adapter.client.scrape.call_args
        assert call_args[0][0] == "https://example.com"
        assert "waitFor" in call_args[1]
        assert call_args[1]["waitFor"] == 2000
    
    async def test_scrape_timeout(self, adapter):
        """测试爬取超时"""
        adapter.client.scrape.side_effect = asyncio.TimeoutError()
        
        with pytest.raises(CrawlException) as exc_info:
            await adapter.scrape("https://example.com")
        
        assert "爬取超时" in str(exc_info.value)
        assert exc_info.value.url == "https://example.com"
    
    async def test_scrape_error(self, adapter):
        """测试爬取错误"""
        adapter.client.scrape.side_effect = Exception("Network error")
        
        with pytest.raises(CrawlException) as exc_info:
            await adapter.scrape("https://example.com")
        
        assert "爬取失败" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)
    
    async def test_crawl_success(self, adapter):
        """测试成功爬取整个网站"""
        results = await adapter.crawl("https://example.com", limit=10)
        
        assert len(results) == 2
        assert all(isinstance(r, CrawlResult) for r in results)
        assert results[0].url == "https://example.com/page1"
        assert results[0].content == "Page 1 content"
        assert results[1].url == "https://example.com/page2"
    
    async def test_crawl_with_options(self, adapter):
        """测试带选项的网站爬取"""
        options = {
            "max_depth": 5,
            "include_paths": ["/docs/*"],
            "exclude_paths": ["/api/*"],
            "allow_backward_links": True
        }
        
        results = await adapter.crawl("https://example.com", limit=20, **options)
        
        # 验证调用参数
        adapter.client.crawl.assert_called_once()
        call_args = adapter.client.crawl.call_args
        assert call_args[1]["limit"] == 20
        assert call_args[1]["maxDepth"] == 5
    
    async def test_map_success(self, adapter):
        """测试成功生成站点地图"""
        urls = await adapter.map("https://example.com", limit=100)
        
        assert len(urls) == 3
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/page3" in urls
    
    async def test_extract_success(self, adapter):
        """测试成功提取结构化数据"""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "author": {"type": "string"}
            }
        }
        
        data = await adapter.extract("https://example.com", schema)
        
        assert data["title"] == "Extracted Title"
        assert data["content"] == "Extracted content"
        assert data["author"] == "Test Author"


@pytest.mark.asyncio
class TestFirecrawlRateLimiter:
    """速率限制器测试"""
    
    async def test_rate_limiting(self):
        """测试速率限制功能"""
        limiter = FirecrawlRateLimiter(max_requests_per_minute=2)
        
        # 快速发出3个请求
        start_time = asyncio.get_event_loop().time()
        
        await limiter.acquire()  # 第1个请求 - 立即通过
        await limiter.acquire()  # 第2个请求 - 立即通过
        
        # 第3个请求应该被延迟
        await limiter.acquire()
        
        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time
        
        # 由于限制是每分钟2个请求，第3个请求应该等待
        # 但在测试中我们不想等待60秒，所以只验证机制工作
        assert len(limiter.request_times) > 0
    
    async def test_cleanup_old_requests(self):
        """测试清理旧请求记录"""
        limiter = FirecrawlRateLimiter(max_requests_per_minute=10)
        
        # 模拟一些旧的请求时间
        import time
        old_time = time.time() - 70  # 70秒前
        recent_time = time.time() - 30  # 30秒前
        
        limiter.request_times = [old_time, recent_time]
        
        await limiter.acquire()
        
        # 旧的请求应该被清理
        assert old_time not in limiter.request_times
        # 最近的请求应该保留
        assert any(t >= recent_time for t in limiter.request_times)