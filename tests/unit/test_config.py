"""
配置模块单元测试
"""
import os
import pytest
from unittest.mock import patch

from pydantic import ValidationError


class TestSettings:
    """Settings配置测试"""
    
    def test_default_settings(self):
        """测试默认配置"""
        # 设置必要的环境变量
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "test-key-123"
        }, clear=False):
            from src.config import Settings
            
            settings = Settings()
            
            assert settings.APP_NAME == "关山智能系统"
            assert settings.VERSION == "1.0.0"
            assert settings.DEBUG == True
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 8000
            assert settings.FIRECRAWL_API_KEY == "test-key-123"
    
    def test_custom_settings_from_env(self):
        """测试从环境变量加载配置"""
        with patch.dict(os.environ, {
            "APP_NAME": "Custom App",
            "VERSION": "2.0.0",
            "DEBUG": "false",
            "PORT": "9000",
            "FIRECRAWL_API_KEY": "custom-key"
        }, clear=False):
            from src.config import Settings
            
            settings = Settings()
            
            assert settings.APP_NAME == "Custom App"
            assert settings.VERSION == "2.0.0"
            assert settings.DEBUG == False
            assert settings.PORT == 9000
            assert settings.FIRECRAWL_API_KEY == "custom-key"
    
    def test_invalid_firecrawl_key(self):
        """测试无效的Firecrawl API密钥"""
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "your-firecrawl-api-key-here"
        }, clear=False):
            from src.config import Settings
            
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "请提供有效的Firecrawl API密钥" in str(exc_info.value)
    
    def test_missing_firecrawl_key(self):
        """测试缺少Firecrawl API密钥"""
        with patch.dict(os.environ, {}, clear=True):
            # 添加其他必要的环境变量，但不包括FIRECRAWL_API_KEY
            os.environ["APP_NAME"] = "Test App"
            
            from src.config import Settings
            
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "FIRECRAWL_API_KEY" in str(exc_info.value)
    
    def test_database_urls(self):
        """测试数据库URL配置"""
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "test-key",
            "MONGODB_URL": "mongodb://localhost:27017/test",
            "MARIADB_URL": "mysql://user:pass@localhost/test",
            "REDIS_URL": "redis://localhost:6379/0",
            "RABBITMQ_URL": "amqp://guest:guest@localhost:5672/",
            "QDRANT_URL": "http://localhost:6333"
        }, clear=False):
            from src.config import Settings
            
            settings = Settings()
            
            assert settings.MONGODB_URL == "mongodb://localhost:27017/test"
            assert settings.MARIADB_URL == "mysql://user:pass@localhost/test"
            assert settings.REDIS_URL == "redis://localhost:6379/0"
            assert settings.RABBITMQ_URL == "amqp://guest:guest@localhost:5672/"
            assert settings.QDRANT_URL == "http://localhost:6333"
    
    def test_allowed_origins(self):
        """测试CORS允许的源"""
        with patch.dict(os.environ, {
            "FIRECRAWL_API_KEY": "test-key",
            "ALLOWED_ORIGINS": '["http://localhost:3000","https://example.com"]'
        }, clear=False):
            from src.config import Settings
            
            settings = Settings()
            
            assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
            assert "https://example.com" in settings.ALLOWED_ORIGINS
            assert "http://localhost:8000" in settings.ALLOWED_ORIGINS  # 默认值