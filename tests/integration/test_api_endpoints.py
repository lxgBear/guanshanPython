"""
API端点集成测试
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from src.core.domain.interfaces.crawler_interface import CrawlResult, CrawlException


@pytest.mark.asyncio
class TestCrawlEndpoints:
    """爬取API端点测试"""
    
    @pytest.fixture
    async def mock_crawler(self, sample_crawl_result):
        """创建模拟爬虫"""
        crawler = AsyncMock()
        
        # 配置默认返回值
        crawler.scrape.return_value = sample_crawl_result
        crawler.crawl.return_value = [sample_crawl_result, sample_crawl_result]
        crawler.map.return_value = [
            "https://example.com/page1",
            "https://example.com/page2"
        ]
        crawler.extract.return_value = {
            "title": "Test Title",
            "content": "Test Content"
        }
        
        return crawler
    
    async def test_scrape_endpoint_success(self, async_client, mock_crawler):
        """测试爬取单页端点成功"""
        with patch("src.api.v1.endpoints.crawl.get_crawler", return_value=mock_crawler):
            response = await async_client.post(
                "/api/v1/crawl/scrape",
                json={
                    "url": "https://example.com",
                    "wait_for": 2000,
                    "exclude_tags": ["nav", "footer"]
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["url"] == "https://example.com"
        assert "content" in data
        assert "markdown" in data
    
    async def test_scrape_endpoint_failure(self, async_client, mock_crawler):
        """测试爬取单页端点失败"""
        mock_crawler.scrape.side_effect = CrawlException("爬取失败", url="https://example.com")
        
        with patch("src.api.v1.endpoints.crawl.get_crawler", return_value=mock_crawler):
            response = await async_client.post(
                "/api/v1/crawl/scrape",
                json={"url": "https://example.com"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "爬取失败" in data["error"]
    
    async def test_crawl_endpoint_success(self, async_client, mock_crawler):
        """测试爬取网站端点成功"""
        with patch("src.api.v1.endpoints.crawl.get_crawler", return_value=mock_crawler):
            response = await async_client.post(
                "/api/v1/crawl/crawl",
                json={
                    "url": "https://example.com",
                    "limit": 20,
                    "max_depth": 3,
                    "include_paths": ["/docs/*"]
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["pages_crawled"] == 2
        assert len(data["results"]) == 2
    
    async def test_map_endpoint_success(self, async_client, mock_crawler):
        """测试站点地图端点成功"""
        with patch("src.api.v1.endpoints.crawl.get_crawler", return_value=mock_crawler):
            response = await async_client.post(
                "/api/v1/crawl/map",
                json={
                    "url": "https://example.com",
                    "limit": 100
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["total_urls"] == 2
        assert len(data["urls"]) == 2
    
    async def test_extract_endpoint_success(self, async_client, mock_crawler):
        """测试数据提取端点成功"""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"}
            }
        }
        
        with patch("src.api.v1.endpoints.crawl.get_crawler", return_value=mock_crawler):
            response = await async_client.post(
                "/api/v1/crawl/extract",
                json={
                    "url": "https://example.com",
                    "schema": schema
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["extracted_data"]["title"] == "Test Title"
        assert data["extracted_data"]["content"] == "Test Content"
    
    async def test_test_endpoint(self, async_client):
        """测试服务健康检查端点"""
        with patch("src.api.v1.endpoints.crawl.FirecrawlAdapter"):
            response = await async_client.get("/api/v1/crawl/test")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["operational", "error"]
        assert "message" in data
        assert "firecrawl_configured" in data


@pytest.mark.asyncio
class TestMainEndpoints:
    """主应用端点测试"""
    
    async def test_health_check(self, async_client):
        """测试健康检查端点"""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data
    
    async def test_root_endpoint(self, async_client):
        """测试根路径端点"""
        response = await async_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    async def test_invalid_endpoint(self, async_client):
        """测试无效端点"""
        response = await async_client.get("/api/v1/invalid")
        
        assert response.status_code == 404
    
    async def test_request_validation(self, async_client):
        """测试请求验证"""
        # 发送无效的请求数据
        response = await async_client.post(
            "/api/v1/crawl/scrape",
            json={
                "url": "not-a-valid-url",  # 无效的URL
                "wait_for": "not-a-number"  # 无效的数字
            }
        )
        
        assert response.status_code == 422  # Validation error