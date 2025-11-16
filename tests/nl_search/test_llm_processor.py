"""
测试 LLM 处理器

测试内容:
- 查询解析功能
- 查询精炼功能
- OpenAI API 集成
- 错误处理和重试机制
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from src.services.nl_search.llm_processor import LLMProcessor
from src.services.nl_search.config import NLSearchConfig


class TestLLMProcessorInit:
    """测试 LLMProcessor 初始化"""

    def test_init_with_valid_config(self):
        """测试使用有效配置初始化"""
        config = NLSearchConfig(llm_api_key="test-key-123")
        processor = LLMProcessor(config=config)

        assert processor.config == config
        assert processor.max_retries == 3
        assert processor.retry_delay == 1

    def test_init_without_api_key(self):
        """测试没有 API Key 时的初始化"""
        config = NLSearchConfig(llm_api_key=None)
        processor = LLMProcessor(config=config)

        assert processor.config == config
        assert processor.client is None

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        processor = LLMProcessor()

        assert processor.config is not None
        assert processor.max_retries == 3


@pytest.mark.asyncio
class TestQueryParse:
    """测试查询解析功能"""

    @pytest.fixture
    def processor(self):
        """创建 LLM 处理器实例"""
        config = NLSearchConfig(
            llm_api_key="test-key-123",
            llm_model="gpt-4",
            llm_temperature=0.7,
            llm_max_tokens=500
        )
        return LLMProcessor(config=config)

    async def test_parse_query_success(self, processor):
        """测试查询解析成功"""
        query_text = "最近有哪些AI技术突破"

        # Mock OpenAI API 响应
        mock_response = {
            "intent": "technology_news",
            "keywords": ["AI", "技术突破", "人工智能"],
            "entities": [
                {"type": "technology", "value": "AI"}
            ],
            "time_range": {
                "type": "recent",
                "from": "2024-06-01",
                "to": "2024-12-31"
            },
            "category": "tech",
            "confidence": 0.95
        }

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = json.dumps(mock_response)

            result = await processor.parse_query(query_text)

            assert result is not None
            assert result["intent"] == "technology_news"
            assert "AI" in result["keywords"]
            assert len(result["entities"]) > 0
            assert result["confidence"] == 0.95
            assert mock_call.call_count == 1

    async def test_parse_query_with_empty_text(self, processor):
        """测试空查询文本"""
        result = await processor.parse_query("")

        assert result is None

    async def test_parse_query_with_whitespace_only(self, processor):
        """测试仅空白字符的查询"""
        result = await processor.parse_query("   \n\t  ")

        assert result is None

    async def test_parse_query_without_client(self):
        """测试没有 LLM 客户端时的行为"""
        config = NLSearchConfig(llm_api_key=None)
        processor = LLMProcessor(config=config)

        result = await processor.parse_query("测试查询")

        assert result is None

    async def test_parse_query_with_markdown_response(self, processor):
        """测试 LLM 返回 Markdown 格式的 JSON"""
        query_text = "Python 数据分析"

        mock_response_data = {
            "intent": "tutorial",
            "keywords": ["Python", "数据分析"],
            "entities": [],
            "time_range": {"type": "none", "from": None, "to": None},
            "category": "education",
            "confidence": 0.85
        }

        # 模拟 Markdown 代码块格式
        markdown_response = f"```json\n{json.dumps(mock_response_data)}\n```"

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = markdown_response

            result = await processor.parse_query(query_text)

            assert result is not None
            assert result["intent"] == "tutorial"
            assert result["confidence"] == 0.85

    async def test_parse_query_with_invalid_json(self, processor):
        """测试 LLM 返回无效 JSON"""
        query_text = "测试查询"

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            # 首次调用返回无效 JSON
            # 第二次调用 fallback prompt 返回有效 JSON
            mock_call.side_effect = [
                "这不是 JSON 格式",
                json.dumps({
                    "intent": "general_info",
                    "keywords": ["测试"],
                    "entities": [],
                    "time_range": {"type": "none", "from": None, "to": None},
                    "category": "other",
                    "confidence": 0.7
                })
            ]

            result = await processor.parse_query(query_text)

            # 应该使用 fallback prompt 成功
            assert result is not None
            assert result["intent"] == "general_info"
            assert mock_call.call_count == 2

    async def test_parse_query_with_missing_fields(self, processor):
        """测试 LLM 返回缺少必需字段的 JSON"""
        query_text = "测试查询"

        # 缺少 category 和 confidence 字段
        incomplete_response = {
            "intent": "test",
            "keywords": ["测试"],
            "entities": []
        }

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = json.dumps(incomplete_response)

            result = await processor.parse_query(query_text)

            # 验证失败，返回 None
            assert result is None

    async def test_parse_query_with_llm_exception(self, processor):
        """测试 LLM 调用抛出异常"""
        query_text = "测试查询"

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.side_effect = Exception("API Error")

            result = await processor.parse_query(query_text)

            assert result is None


@pytest.mark.asyncio
class TestQueryRefine:
    """测试查询精炼功能"""

    @pytest.fixture
    def processor(self):
        """创建 LLM 处理器实例"""
        config = NLSearchConfig(llm_api_key="test-key-123")
        return LLMProcessor(config=config)

    async def test_refine_query_success(self, processor):
        """测试查询精炼成功"""
        query_text = "最近有哪些AI技术突破"
        llm_analysis = {
            "intent": "technology_news",
            "keywords": ["AI", "技术突破"]
        }

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = "AI 技术突破 2024 最新"

            result = await processor.refine_query(query_text, llm_analysis)

            assert result == "AI 技术突破 2024 最新"
            assert mock_call.call_count == 1

    async def test_refine_query_with_empty_text(self, processor):
        """测试空查询文本"""
        llm_analysis = {"intent": "test"}

        result = await processor.refine_query("", llm_analysis)

        assert result == ""

    async def test_refine_query_without_client(self):
        """测试没有 LLM 客户端时返回原始查询"""
        config = NLSearchConfig(llm_api_key=None)
        processor = LLMProcessor(config=config)

        query_text = "测试查询"
        llm_analysis = {"intent": "test"}

        result = await processor.refine_query(query_text, llm_analysis)

        assert result == query_text

    async def test_refine_query_with_markdown_response(self, processor):
        """测试去除 Markdown 代码块标记"""
        query_text = "测试查询"
        llm_analysis = {"intent": "test"}

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = "```测试 查询 关键词```"

            result = await processor.refine_query(query_text, llm_analysis)

            assert result == "测试 查询 关键词"

    async def test_refine_query_with_empty_response(self, processor):
        """测试 LLM 返回空响应"""
        query_text = "测试查询"
        llm_analysis = {"intent": "test"}

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = ""

            result = await processor.refine_query(query_text, llm_analysis)

            # 应该返回原始查询
            assert result == query_text

    async def test_refine_query_with_too_long_response(self, processor):
        """测试 LLM 返回过长的精炼查询"""
        query_text = "测试查询"
        llm_analysis = {"intent": "test"}

        # 生成 150 字符的长字符串
        long_response = "A" * 150

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.return_value = long_response

            result = await processor.refine_query(query_text, llm_analysis)

            # 应该被截断到 100 字符
            assert len(result) == 100

    async def test_refine_query_with_exception(self, processor):
        """测试精炼过程抛出异常"""
        query_text = "测试查询"
        llm_analysis = {"intent": "test"}

        with patch.object(processor, '_call_llm_with_retry') as mock_call:
            mock_call.side_effect = Exception("API Error")

            result = await processor.refine_query(query_text, llm_analysis)

            # 应该返回原始查询
            assert result == query_text


@pytest.mark.asyncio
class TestLLMAPICall:
    """测试 LLM API 调用和重试机制"""

    @pytest.fixture
    def processor(self):
        """创建 LLM 处理器实例"""
        config = NLSearchConfig(llm_api_key="test-key-123")
        processor = LLMProcessor(config=config)
        processor.retry_delay = 0.01  # 减少测试等待时间
        return processor

    async def test_call_llm_success(self, processor):
        """测试 LLM 调用成功"""
        prompt = "测试 Prompt"

        # Mock OpenAI 响应
        mock_response = Mock()
        mock_message = Mock()
        mock_message.content = "LLM 响应内容"
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        with patch.object(processor.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await processor._call_llm_with_retry(prompt)

            assert result == "LLM 响应内容"
            assert mock_create.call_count == 1

    async def test_call_llm_with_rate_limit_retry(self, processor):
        """测试 LLM 限流重试"""
        from openai import RateLimitError
        from httpx import Response, Request

        prompt = "测试 Prompt"

        # Mock OpenAI 响应
        mock_response = Mock()
        mock_message = Mock()
        mock_message.content = "成功响应"
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        # 创建 Mock HTTP Response 对象
        mock_http_request = Request("POST", "https://api.openai.com/v1/chat/completions")
        mock_http_response = Response(429, request=mock_http_request)

        with patch.object(processor.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            # 第一次限流，第二次成功
            mock_create.side_effect = [
                RateLimitError("Rate limit exceeded", response=mock_http_response, body=None),
                mock_response
            ]

            result = await processor._call_llm_with_retry(prompt)

            assert result == "成功响应"
            assert mock_create.call_count == 2

    async def test_call_llm_with_timeout_retry(self, processor):
        """测试 LLM 超时重试"""
        from openai import APITimeoutError

        prompt = "测试 Prompt"

        # Mock OpenAI 响应
        mock_response = Mock()
        mock_message = Mock()
        mock_message.content = "成功响应"
        mock_choice = Mock()
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        with patch.object(processor.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            # 第一次超时，第二次成功
            mock_create.side_effect = [
                APITimeoutError("Timeout"),
                mock_response
            ]

            result = await processor._call_llm_with_retry(prompt)

            assert result == "成功响应"
            assert mock_create.call_count == 2

    async def test_call_llm_max_retries_exceeded(self, processor):
        """测试重试次数耗尽"""
        from openai import APIError

        prompt = "测试 Prompt"

        with patch.object(processor.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            # 所有尝试都失败
            mock_create.side_effect = APIError("API Error", request=None, body=None)

            with pytest.raises(APIError):
                await processor._call_llm_with_retry(prompt)

            # 应该尝试 max_retries 次
            assert mock_create.call_count == processor.max_retries


class TestJSONParsing:
    """测试 JSON 解析功能"""

    def test_parse_valid_json(self):
        """测试解析有效 JSON"""
        processor = LLMProcessor()

        response_text = '{"intent": "test", "keywords": ["测试"]}'
        result = processor._parse_json_response(response_text)

        assert result is not None
        assert result["intent"] == "test"
        assert "测试" in result["keywords"]

    def test_parse_json_with_markdown(self):
        """测试解析带 Markdown 标记的 JSON"""
        processor = LLMProcessor()

        response_text = '```json\n{"intent": "test"}\n```'
        result = processor._parse_json_response(response_text)

        assert result is not None
        assert result["intent"] == "test"

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        processor = LLMProcessor()

        response_text = "这不是 JSON"
        result = processor._parse_json_response(response_text)

        assert result is None

    def test_parse_empty_response(self):
        """测试解析空响应"""
        processor = LLMProcessor()

        result = processor._parse_json_response("")

        assert result is None


class TestValidation:
    """测试验证功能"""

    def test_validate_complete_analysis(self):
        """测试验证完整的分析结果"""
        processor = LLMProcessor()

        analysis = {
            "intent": "test",
            "keywords": ["测试"],
            "entities": [],
            "category": "other",
            "confidence": 0.8
        }

        assert processor._validate_analysis(analysis) is True

    def test_validate_missing_field(self):
        """测试缺少必需字段"""
        processor = LLMProcessor()

        # 缺少 confidence 字段
        analysis = {
            "intent": "test",
            "keywords": ["测试"],
            "entities": [],
            "category": "other"
        }

        assert processor._validate_analysis(analysis) is False

    def test_validate_invalid_keywords_type(self):
        """测试 keywords 类型错误"""
        processor = LLMProcessor()

        analysis = {
            "intent": "test",
            "keywords": "not a list",  # 应该是列表
            "entities": [],
            "category": "other",
            "confidence": 0.8
        }

        assert processor._validate_analysis(analysis) is False

    def test_validate_invalid_confidence_range(self):
        """测试 confidence 范围无效"""
        processor = LLMProcessor()

        # confidence 超出范围
        analysis = {
            "intent": "test",
            "keywords": ["测试"],
            "entities": [],
            "category": "other",
            "confidence": 1.5  # 应该在 0.0-1.0 之间
        }

        assert processor._validate_analysis(analysis) is False


class TestDefaultAnalysis:
    """测试默认分析结果"""

    def test_get_default_analysis(self):
        """测试获取默认分析结果"""
        processor = LLMProcessor()

        query_text = "测试 查询 关键词"
        result = processor.get_default_analysis(query_text)

        assert result is not None
        assert result["intent"] == "general_info"
        assert len(result["keywords"]) > 0
        assert result["confidence"] == 0.5
        assert result["category"] == "other"

    def test_default_analysis_keyword_extraction(self):
        """测试默认分析的关键词提取"""
        processor = LLMProcessor()

        query_text = "Python 数据分析 机器学习 深度学习"
        result = processor.get_default_analysis(query_text)

        # 应该提取出关键词
        assert "Python" in result["keywords"]
        # 最多提取 5 个关键词
        assert len(result["keywords"]) <= 5
