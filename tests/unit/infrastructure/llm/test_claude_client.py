"""
Claude API 客户端单元测试

测试覆盖:
- ClaudeConfig 配置
- ClaudeClient 初始化
- 辅助函数 (Source Tier, Credibility, Time Verification)
- 实体类 (DecomposedQuery, QueryDecomposition)
- 工厂函数
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.infrastructure.llm.claude_client import (
    ClaudeConfig,
    ClaudeClient,
    DecomposedQuery,
    QueryDecomposition,
    create_claude_client,
    classify_source_tier,
    calculate_credibility,
    verify_publish_date,
    SOURCE_TIER_RULES,
    CREDIBILITY_LEVELS,
    TIME_CONFIDENCE_LEVELS
)


# ==================== Test Configuration ====================

class TestClaudeConfig:
    """测试 ClaudeConfig 配置"""

    def test_default_config(self):
        """测试: 默认配置值"""
        config = ClaudeConfig()

        assert config.base_url == "http://23.106.129.19:2828/api"
        assert config.api_key == ""
        assert config.model == "claude-sonnet-4-20250514"
        assert config.timeout == 60
        assert config.max_tokens == 1500

    def test_custom_config(self):
        """测试: 自定义配置"""
        config = ClaudeConfig(
            base_url="https://custom.api",
            api_key="test-key-123",
            model="claude-opus-4-20250514",
            timeout=120,
            max_tokens=3000
        )

        assert config.base_url == "https://custom.api"
        assert config.api_key == "test-key-123"
        assert config.model == "claude-opus-4-20250514"
        assert config.timeout == 120
        assert config.max_tokens == 3000


class TestClaudeClientInit:
    """测试 ClaudeClient 初始化"""

    def test_init_default_config(self):
        """测试: 使用默认配置初始化"""
        client = ClaudeClient()

        assert client.config.base_url == "http://23.106.129.19:2828/api"
        assert client.config.model == "claude-sonnet-4-20250514"

    def test_init_custom_config(self):
        """测试: 使用自定义配置初始化"""
        config = ClaudeConfig(api_key="test-key")
        client = ClaudeClient(config)

        assert client.config.api_key == "test-key"

    def test_base_url_trailing_slash_removed(self):
        """测试: 自动移除 base_url 末尾斜杠"""
        client = ClaudeClient(ClaudeConfig(
            base_url="http://api.example.com/"
        ))

        assert client.base_url == "http://api.example.com"

    def test_init_without_api_key_warning(self, caplog):
        """测试: 没有 API Key 时发出警告"""
        import logging
        with caplog.at_level(logging.WARNING):
            ClaudeClient(ClaudeConfig(api_key=""))

        assert "API Key 未配置" in caplog.text


# ==================== Test Source Tier Classification ====================

class TestClassifySourceTier:
    """测试来源层级分类"""

    def test_classify_gov_domain(self):
        """测试: .gov 域名分类为官方"""
        result = classify_source_tier("https://www.whitehouse.gov/news")

        assert result["tier"] == "official"
        assert result["tier_score"] == 1.0
        assert result["tier_label"] == "官方"

    def test_classify_edu_domain(self):
        """测试: .edu 域名分类为官方"""
        result = classify_source_tier("https://mit.edu/research")

        assert result["tier"] == "official"
        assert result["tier_score"] == 1.0

    def test_classify_gov_cn_domain(self):
        """测试: .gov.cn 域名分类为官方"""
        result = classify_source_tier("https://www.mfa.gov.cn/news")

        assert result["tier"] == "official"

    def test_classify_reuters_domain(self):
        """测试: Reuters 分类为权威"""
        result = classify_source_tier("https://reuters.com/world/news")

        assert result["tier"] == "authoritative"
        assert result["tier_score"] == 0.9

    def test_classify_nytimes_domain(self):
        """测试: NYT 分类为主流"""
        result = classify_source_tier("https://nytimes.com/2024/01/01/world")

        assert result["tier"] == "mainstream"
        assert result["tier_score"] == 0.8

    def test_classify_scmp_domain(self):
        """测试: SCMP 分类为主流"""
        result = classify_source_tier("https://scmp.com/news")

        assert result["tier"] == "mainstream"

    def test_classify_csis_domain(self):
        """测试: CSIS 分类为专业"""
        result = classify_source_tier("https://csis.org/analysis")

        assert result["tier"] == "specialized"
        assert result["tier_score"] == 0.75

    def test_classify_arxiv_domain(self):
        """测试: arXiv 分类为专业"""
        result = classify_source_tier("https://arxiv.org/abs/1234")

        assert result["tier"] == "specialized"

    def test_classify_medium_domain(self):
        """测试: Medium 分类为一般"""
        result = classify_source_tier("https://medium.com/@user/article")

        assert result["tier"] == "general"
        assert result["tier_score"] == 0.6

    def test_classify_twitter_domain(self):
        """测试: Twitter 分类为社交"""
        result = classify_source_tier("https://twitter.com/user/status/123")

        assert result["tier"] == "social"
        assert result["tier_score"] == 0.4

    def test_classify_x_domain(self):
        """测试: X.com 分类为社交"""
        result = classify_source_tier("https://x.com/user/status/123")

        assert result["tier"] == "social"

    def test_classify_zhihu_domain(self):
        """测试: 知乎分类为社交"""
        result = classify_source_tier("https://zhihu.com/question/123")

        assert result["tier"] == "social"

    def test_classify_empty_url(self):
        """测试: 空 URL"""
        result = classify_source_tier("")

        assert result["tier"] == "general"
        assert result["tier_label"] == "未知"

    def test_classify_null_url(self):
        """测试: None URL"""
        result = classify_source_tier(None)

        assert result["tier"] == "general"
        assert result["tier_label"] == "未知"

    def test_classify_unknown_domain(self):
        """测试: 未知域名"""
        result = classify_source_tier("https://unknown-website.com/article")

        assert result["tier"] == "general"
        assert result["tier_score"] == 0.6

    def test_all_tiers_have_scores(self):
        """测试: 所有层级都有评分"""
        expected_tiers = ["official", "authoritative", "mainstream", "specialized", "general", "social"]

        for tier in expected_tiers:
            assert tier in SOURCE_TIER_RULES
            assert "tier_score" in SOURCE_TIER_RULES[tier]
            assert 0.0 <= SOURCE_TIER_RULES[tier]["tier_score"] <= 1.0


# ==================== Test Credibility Calculation ====================

class TestCalculateCredibility:
    """测试可信度计算"""

    def test_calculate_credibility_confirmed(self):
        """测试: 确认级可信度"""
        result = calculate_credibility(
            rerank_score=0.95,
            tier_score=0.9,
            has_date=True,
            multiple_sources=True
        )

        assert result["level"] == "confirmed"
        assert result["symbol"] == "✅"
        assert result["score"] >= 0.9
        assert result["label"] == "确认"

    def test_calculate_credibility_reliable(self):
        """测试: 可信"""
        result = calculate_credibility(
            rerank_score=0.95,  # 提高分数使结果 > 0.7
            tier_score=0.9,
            has_date=False,
            multiple_sources=False
        )

        assert result["level"] == "reliable"
        assert result["symbol"] == "🟢"
        assert result["label"] == "可信"

    def test_calculate_credibility_unverified(self):
        """测试: 待核实"""
        result = calculate_credibility(
            rerank_score=0.85,  # 使结果在 0.5-0.7 范围内
            tier_score=0.75,   # 0.85 * 0.75 = 0.6375
            has_date=False,
            multiple_sources=False
        )

        assert result["level"] == "unverified"
        assert result["symbol"] == "🟡"
        assert result["label"] == "待核实"

    def test_calculate_credibility_questionable(self):
        """测试: 存疑"""
        result = calculate_credibility(
            rerank_score=0.4,
            tier_score=0.4,
            has_date=False,
            multiple_sources=False
        )

        assert result["level"] == "questionable"
        assert result["symbol"] == "🟠"
        assert result["label"] == "存疑"

    def test_calculate_credibility_unreliable(self):
        """测试: 不可靠"""
        result = calculate_credibility(
            rerank_score=0.1,
            tier_score=0.2,
            has_date=False,
            multiple_sources=False
        )

        assert result["level"] == "unreliable"
        assert result["symbol"] == "🔴"
        assert result["label"] == "不可靠"

    def test_calculate_credibility_score_clamped_at_1(self):
        """测试: 分数上限为1"""
        result = calculate_credibility(
            rerank_score=1.5,  # 超过范围
            tier_score=1.0,
            has_date=True,
            multiple_sources=True
        )

        assert result["score"] <= 1.0

    def test_calculate_credibility_score_minimum_0(self):
        """测试: 分数下限为0"""
        result = calculate_credibility(
            rerank_score=0.0,
            tier_score=0.0,
            has_date=False,
            multiple_sources=False
        )

        assert result["score"] >= 0.0

    def test_calculate_credibility_date_bonus(self):
        """测试: 有日期加分"""
        without_date = calculate_credibility(0.8, 0.8, False, False)
        with_date = calculate_credibility(0.8, 0.8, True, False)

        assert with_date["score"] > without_date["score"]

    def test_calculate_credibility_multi_source_bonus(self):
        """测试: 多源验证加分"""
        without_multi = calculate_credibility(0.8, 0.8, False, False)
        with_multi = calculate_credibility(0.8, 0.8, False, True)

        assert with_multi["score"] > without_multi["score"]

    def test_all_credibility_levels_defined(self):
        """测试: 所有可信度级别都有定义"""
        expected_levels = ["confirmed", "reliable", "unverified", "questionable", "unreliable"]

        for level in expected_levels:
            assert level in CREDIBILITY_LEVELS
            assert "symbol" in CREDIBILITY_LEVELS[level]
            assert "range" in CREDIBILITY_LEVELS[level]


# ==================== Test Time Verification ====================

class TestVerifyPublishDate:
    """测试发布日期验证"""

    def test_verify_date_iso_format_high_confidence(self):
        """测试: ISO 格式日期 - 高置信度"""
        result = verify_publish_date("2024-01-15")

        assert result["confidence"] == "high"
        assert result["symbol"] == "🕐"
        assert result["label"] == "高置信度"
        assert result["score_bonus"] == 0.1
        assert result["parsed_date"] == "2024-01-15"

    def test_verify_date_iso_with_time(self):
        """测试: ISO 格式带时间"""
        result = verify_publish_date("2024-01-15T10:30:00")

        assert result["confidence"] == "high"

    def test_verify_date_chinese_format(self):
        """测试: 中文日期格式"""
        result = verify_publish_date("2024年1月15日")

        assert result["confidence"] == "high"

    def test_verify_date_us_format(self):
        """测试: 美式日期格式"""
        result = verify_publish_date("December 15, 2024")

        assert result["confidence"] == "high"

    def test_verify_date_relative_hours_ago_medium_confidence(self):
        """测试: 相对时间 (小时前) - 中置信度"""
        result = verify_publish_date("2小时前")

        assert result["confidence"] == "medium"
        assert result["symbol"] == "🕑"
        assert result["label"] == "中置信度"

    def test_verify_date_relative_days_ago(self):
        """测试: 相对时间 (天前)"""
        result = verify_publish_date("3天前")

        assert result["confidence"] == "medium"

    def test_verify_date_yesterday(self):
        """测试: 昨天"""
        result = verify_publish_date("昨天")

        assert result["confidence"] == "medium"

    def test_verify_date_today(self):
        """测试: 今天"""
        result = verify_publish_date("今天")

        assert result["confidence"] == "medium"

    def test_verify_date_just_now(self):
        """测试: 刚刚"""
        result = verify_publish_date("刚刚")

        assert result["confidence"] == "medium"

    def test_verify_date_invalid_low_confidence(self):
        """测试: 无效日期 - 低置信度"""
        result = verify_publish_date("some random text")

        assert result["confidence"] == "low"
        assert result["symbol"] == "🕒"
        assert result["label"] == "低置信度"
        assert result["score_bonus"] == 0.0

    def test_verify_date_empty_none_confidence(self):
        """测试: 空日期"""
        result = verify_publish_date("")

        assert result["confidence"] == "none"
        assert result["symbol"] == "❓"
        assert result["label"] == "无日期"
        assert result["parsed_date"] is None

    def test_verify_date_null(self):
        """测试: None 日期"""
        result = verify_publish_date(None)

        assert result["confidence"] == "none"
        assert result["score_bonus"] == 0.0
        assert result["parsed_date"] is None

    def test_all_time_confidence_levels_defined(self):
        """测试: 所有时间置信度级别都有定义"""
        expected_levels = ["high", "medium", "low", "none"]

        for level in expected_levels:
            assert level in TIME_CONFIDENCE_LEVELS
            assert "symbol" in TIME_CONFIDENCE_LEVELS[level]


# ==================== Test Factory Function ====================

class TestCreateClaudeClient:
    """测试工厂函数"""

    def test_create_claude_client_default(self):
        """测试: 使用默认值创建客户端"""
        with patch.dict("os.environ", {}, clear=True):
            client = create_claude_client()

            assert client.config.base_url == "http://23.106.129.19:2828/api"
            assert client.config.model == "claude-sonnet-4-20250514"

    def test_create_claude_client_with_env_vars(self):
        """测试: 使用环境变量创建客户端"""
        env_vars = {
            "ANTHROPIC_BASE_URL": "https://custom.api",
            "ANTHROPIC_AUTH_TOKEN": "env-key-123",
            "CLAUDE_MODEL": "claude-opus-4-20250514"
        }

        with patch.dict("os.environ", env_vars, clear=False):
            client = create_claude_client()

            assert client.config.base_url == "https://custom.api"
            assert client.config.api_key == "env-key-123"
            assert client.config.model == "claude-opus-4-20250514"

    def test_create_claude_client_params_override_env(self):
        """测试: 参数覆盖环境变量"""
        env_vars = {
            "ANTHROPIC_BASE_URL": "https://env.api",
            "ANTHROPIC_AUTH_TOKEN": "env-key",
            "CLAUDE_MODEL": "env-model"
        }

        with patch.dict("os.environ", env_vars, clear=False):
            client = create_claude_client(
                base_url="https://param.api",
                api_key="param-key",
                model="param-model"
            )

            # 参数优先级高于环境变量
            assert client.config.base_url == "https://param.api"
            assert client.config.api_key == "param-key"
            assert client.config.model == "param-model"


# ==================== Test Query Decomposition Entity ====================

class TestQueryDecomposition:
    """测试查询分解实体"""

    def test_query_decomposition_to_dict(self):
        """测试: 转换为字典"""
        decomposition = QueryDecomposition(
            decomposed_queries=[
                DecomposedQuery(
                    query="子查询1",
                    reasoning="理由1",
                    focus="关注点1"
                ),
                DecomposedQuery(
                    query="子查询2",
                    reasoning="理由2",
                    focus="关注点2"
                )
            ],
            overall_strategy="整体策略",
            tokens_used=100,
            model="claude-sonnet-4"
        )

        result = decomposition.to_dict()

        assert result["overall_strategy"] == "整体策略"
        assert result["tokens_used"] == 100
        assert result["model"] == "claude-sonnet-4"
        assert len(result["decomposed_queries"]) == 2
        assert result["decomposed_queries"][0]["query"] == "子查询1"

    def test_query_decomposition_from_dict(self):
        """测试: 从字典创建"""
        data = {
            "decomposed_queries": [
                {"query": "子查询1", "reasoning": "理由1", "focus": "关注点1"}
            ],
            "overall_strategy": "策略",
            "tokens_used": 50,
            "model": "gpt-4"
        }

        decomposition = QueryDecomposition.from_dict(data)

        assert len(decomposition.decomposed_queries) == 1
        assert decomposition.decomposed_queries[0].query == "子查询1"
        assert decomposition.overall_strategy == "策略"
        assert decomposition.tokens_used == 50

    def test_decomposed_query_dataclass(self):
        """测试: DecomposedQuery 数据类"""
        query = DecomposedQuery(
            query="测试查询",
            reasoning="测试理由",
            focus="测试关注点"
        )

        assert query.query == "测试查询"
        assert query.reasoning == "测试理由"
        assert query.focus == "测试关注点"

    def test_query_decomposition_default_values(self):
        """测试: 默认值"""
        decomposition = QueryDecomposition()

        assert decomposition.decomposed_queries == []
        assert decomposition.overall_strategy == ""
        assert decomposition.tokens_used == 0
        assert decomposition.model == "gpt-4"


# ==================== Test Error Handling ====================

class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_parse_query_no_api_key_raises_error(self):
        """测试: 没有 API Key 时抛出异常"""
        client = ClaudeClient(ClaudeConfig(api_key=""))

        with pytest.raises(ValueError, match="API Key 未配置"):
            await client.parse_query("test query")

    def test_classify_source_tier_invalid_url(self):
        """测试: 无效URL不会崩溃"""
        # 不应该抛出异常
        result = classify_source_tier("not-a-valid-url")

        assert result is not None
        assert "tier" in result

    def test_verify_date_non_string_input(self):
        """测试: 非字符串输入不会崩溃"""
        result = verify_publish_date(12345)

        assert result is not None
        assert "confidence" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
