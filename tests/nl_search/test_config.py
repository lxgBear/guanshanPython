"""
测试 NL Search 配置

测试内容:
- 配置加载和默认值
- 环境变量覆盖
- 配置验证方法
"""
import pytest
from unittest.mock import patch

from src.services.nl_search.config import NLSearchConfig, nl_search_config


class TestNLSearchConfig:
    """测试 NLSearchConfig 配置类"""

    def test_default_values(self):
        """测试默认配置值"""
        config = NLSearchConfig()

        # 功能开关默认关闭
        assert config.enabled is False

        # LLM 配置默认值
        assert config.llm_model == "gpt-4"
        assert config.llm_temperature == 0.7
        assert config.llm_max_tokens == 500

        # GPT-5 搜索配置
        assert config.gpt5_max_results == 10

        # Scrape 配置
        assert config.scrape_timeout == 30
        assert config.scrape_max_concurrent == 3

        # 业务配置
        assert config.max_results_per_query == 20
        assert config.enable_auto_scrape is True

        # 性能配置
        assert config.query_timeout == 30
        assert config.cache_ttl == 3600

    def test_is_enabled(self):
        """测试 is_enabled 方法"""
        config = NLSearchConfig(enabled=False)
        assert config.is_enabled() is False

        config_enabled = NLSearchConfig(enabled=True)
        assert config_enabled.is_enabled() is True

    def test_validate_llm_config(self):
        """测试 LLM 配置验证"""
        # 没有 API Key
        config1 = NLSearchConfig(llm_api_key=None)
        assert config1.validate_llm_config() is False

        # 空 API Key
        config2 = NLSearchConfig(llm_api_key="")
        assert config2.validate_llm_config() is False

        # 有效 API Key
        config3 = NLSearchConfig(llm_api_key="sk-test123")
        assert config3.validate_llm_config() is True

    def test_validate_gpt5_config(self):
        """测试 GPT-5 配置验证"""
        # 没有 API Key
        config1 = NLSearchConfig(gpt5_search_api_key=None)
        assert config1.validate_gpt5_config() is False

        # 有效 API Key
        config2 = NLSearchConfig(gpt5_search_api_key="gpt5-key-123")
        assert config2.validate_gpt5_config() is True

    def test_repr_hides_sensitive_info(self):
        """测试 repr 方法隐藏敏感信息"""
        config = NLSearchConfig(
            llm_api_key="sk-secret123",
            gpt5_search_api_key="gpt5-secret456"
        )

        repr_str = repr(config)

        # 应该包含配置信息
        assert "NLSearchConfig" in repr_str
        assert "enabled" in repr_str
        assert "llm_model" in repr_str

        # 不应该包含敏感信息
        assert "sk-secret123" not in repr_str
        assert "gpt5-secret456" not in repr_str

    def test_global_config_instance(self):
        """测试全局配置实例"""
        # nl_search_config 应该是 NLSearchConfig 的实例
        assert isinstance(nl_search_config, NLSearchConfig)
        assert nl_search_config.enabled is False  # 默认关闭


class TestNLSearchConfigValidation:
    """测试配置验证规则"""

    def test_temperature_range(self):
        """测试 temperature 范围验证"""
        # 有效范围 (0.0-2.0)
        config1 = NLSearchConfig(llm_temperature=0.0)
        assert config1.llm_temperature == 0.0

        config2 = NLSearchConfig(llm_temperature=1.0)
        assert config2.llm_temperature == 1.0

        config3 = NLSearchConfig(llm_temperature=2.0)
        assert config3.llm_temperature == 2.0

    def test_max_tokens_range(self):
        """测试 max_tokens 范围验证"""
        # 有效范围 (1-4096)
        config1 = NLSearchConfig(llm_max_tokens=1)
        assert config1.llm_max_tokens == 1

        config2 = NLSearchConfig(llm_max_tokens=500)
        assert config2.llm_max_tokens == 500

        config3 = NLSearchConfig(llm_max_tokens=4096)
        assert config3.llm_max_tokens == 4096

    def test_timeout_range(self):
        """测试超时时间范围验证"""
        # scrape_timeout 范围 (5-300)
        config1 = NLSearchConfig(scrape_timeout=5)
        assert config1.scrape_timeout == 5

        config2 = NLSearchConfig(scrape_timeout=300)
        assert config2.scrape_timeout == 300

        # query_timeout 范围 (5-300)
        config3 = NLSearchConfig(query_timeout=5)
        assert config3.query_timeout == 5

    def test_concurrent_limit(self):
        """测试并发限制"""
        config = NLSearchConfig(scrape_max_concurrent=5)
        assert config.scrape_max_concurrent == 5

    def test_results_limit(self):
        """测试结果数量限制"""
        config = NLSearchConfig(
            gpt5_max_results=20,
            max_results_per_query=50
        )

        assert config.gpt5_max_results == 20
        assert config.max_results_per_query == 50
