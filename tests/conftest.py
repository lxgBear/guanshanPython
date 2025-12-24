"""
pytest配置和公共fixtures
"""
import os
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

# 设置测试环境变量
os.environ["TESTING"] = "true"
os.environ["FIRECRAWL_API_KEY"] = "test-api-key"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRATION_HOURS", "24")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """创建异步HTTP客户端"""
    from src.main import app
    from httpx import ASGITransport
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_client() -> TestClient:
    """创建同步测试客户端"""
    from src.main import app
    return TestClient(app)


@pytest.fixture
def mock_firecrawl():
    """模拟Firecrawl客户端"""
    mock_client = AsyncMock()
    
    # 模拟scrape方法
    mock_client.scrape.return_value = {
        "success": True,
        "data": {
            "url": "https://example.com",
            "content": "Test content",
            "markdown": "# Test Content",
            "html": "<h1>Test Content</h1>",
            "metadata": {"title": "Test Page"}
        }
    }
    
    # 模拟crawl方法
    mock_client.crawl.return_value = {
        "success": True,
        "data": [
            {
                "url": "https://example.com/page1",
                "content": "Page 1 content",
                "markdown": "# Page 1"
            },
            {
                "url": "https://example.com/page2", 
                "content": "Page 2 content",
                "markdown": "# Page 2"
            }
        ]
    }
    
    # 模拟map方法
    mock_client.map.return_value = {
        "urls": [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3"
        ]
    }
    
    # 模拟extract方法
    mock_client.extract.return_value = {
        "data": {
            "title": "Extracted Title",
            "content": "Extracted content",
            "author": "Test Author"
        }
    }
    
    return mock_client


@pytest.fixture
def sample_crawl_result():
    """样本爬取结果"""
    from src.core.domain.interfaces.crawler_interface import CrawlResult
    
    return CrawlResult(
        url="https://example.com",
        content="Sample content",
        markdown="# Sample Content",
        html="<h1>Sample Content</h1>",
        metadata={"title": "Sample Page", "timestamp": "2024-01-01"},
        screenshot=None
    )


@pytest.fixture
def sample_document():
    """样本文档实体"""
    from src.core.domain.entities.document import Document, DocumentStatus

    return Document(
        url="https://example.com",
        content="Sample document content",
        title="Sample Document",
        status=DocumentStatus.PENDING,
        metadata={"source": "test"}
    )


# ==========================================
# 认证相关 Fixtures
# ==========================================

@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "username": "testuser",
        "password": "TestPassword123",
        "email": "test@example.com",
        "display_name": "测试用户",
        "phone": "13800138000",
        "department": "测试部门",
        "role_codes": ["reviewer"]
    }


@pytest.fixture
def test_admin_data():
    """测试管理员数据"""
    return {
        "username": "admin",
        "password": "Admin@123",
        "email": "admin@system.com",
        "display_name": "系统管理员",
        "role_codes": ["admin"]
    }


@pytest.fixture
def test_role_data():
    """测试角色数据"""
    return {
        "code": "test_role",
        "name": "测试角色",
        "level": 50,
        "description": "用于测试的角色",
        "permission_codes": ["user:read", "user:list"]
    }


@pytest.fixture
def jwt_handler():
    """JWT处理器实例"""
    from src.infrastructure.auth import JWTHandler
    return JWTHandler()


@pytest.fixture
def password_handler():
    """密码处理器实例"""
    from src.infrastructure.auth import PasswordHandler
    return PasswordHandler()


@pytest.fixture
def test_access_token(jwt_handler):
    """测试访问令牌"""
    return jwt_handler.create_access_token(
        user_id=1,
        username="testuser",
        roles=["reviewer"],
        permissions=["user:read", "info:create"]
    )


@pytest.fixture
def test_admin_token(jwt_handler):
    """测试管理员令牌"""
    return jwt_handler.create_access_token(
        user_id=1,
        username="admin",
        roles=["admin"],
        permissions=["user:create", "user:read", "user:update", "user:delete"]
    )