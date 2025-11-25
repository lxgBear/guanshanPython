"""
NL Search 端到端集成测试
验证从创建搜索到Firecrawl抓取再到存储的完整流程

测试覆盖:
1. 完整搜索流程（create_search → Firecrawl → storage → retrieval）
2. Firecrawl API调用验证
3. 数据存储完整性验证
4. 并发抓取控制验证
5. 错误处理和部分成功场景

版本: v2.0.0 (End-to-End Integration Tests)
日期: 2025-11-18
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

from src.services.nl_search.nl_search_service import NLSearchService
from src.services.nl_search.config import nl_search_config


@pytest.fixture
def service():
    """创建NLSearchService实例"""
    return NLSearchService()


@pytest.fixture
def mock_llm_analysis():
    """模拟LLM解析结果"""
    return {
        "intent": "technology_news",
        "keywords": ["GPT-5", "AI", "技术突破"],
        "temporal_context": "latest",
        "search_scope": "comprehensive"
    }


@pytest.fixture
def mock_gpt5_search_results():
    """模拟GPT5 Search返回的结果"""
    return [
        Mock(to_dict=Mock(return_value={
            "title": "GPT-5发布：OpenAI的最新突破",
            "url": "https://example1.com/gpt5-release",
            "snippet": "OpenAI今天正式发布了GPT-5模型，标志着AI技术的重大突破...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi"
        })),
        Mock(to_dict=Mock(return_value={
            "title": "AI技术新纪元：GPT-5的能力解析",
            "url": "https://example2.com/gpt5-capabilities",
            "snippet": "深入分析GPT-5的核心技术特性和性能提升...",
            "position": 2,
            "score": 0.90,
            "source": "serpapi"
        })),
        Mock(to_dict=Mock(return_value={
            "title": "GPT-5应用场景探索",
            "url": "https://example3.com/gpt5-applications",
            "snippet": "探讨GPT-5在各行业的实际应用可能性...",
            "position": 3,
            "score": 0.85,
            "source": "serpapi"
        }))
    ]


@pytest.fixture
def mock_firecrawl_results():
    """模拟Firecrawl抓取结果（为不同URL返回不同内容）"""
    def create_firecrawl_result(url: str) -> Mock:
        if "gpt5-release" in url:
            markdown = """# GPT-5发布：OpenAI的最新突破

OpenAI今天正式发布了GPT-5模型，这是该公司在大语言模型领域的又一重大突破。

## 核心特性

1. **性能提升**：相比GPT-4提升300%
2. **多模态能力**：支持文本、图像、音频、视频
3. **推理能力**：显著增强的逻辑推理和数学能力

## 技术细节

GPT-5采用了全新的训练架构，参数规模达到5万亿，训练数据覆盖截至2024年底的互联网内容。
"""
            metadata_dict = {
                "title": "GPT-5发布：OpenAI的最新突破",
                "description": "OpenAI发布GPT-5详情",
                "language": "zh-CN",
                "ogImage": "https://example1.com/gpt5.jpg"
            }
        elif "gpt5-capabilities" in url:
            markdown = """# AI技术新纪元：GPT-5的能力解析

## 语言理解能力

GPT-5在语言理解方面展现出前所未有的深度，能够准确把握复杂的上下文语境。

## 创作能力

从代码编写到文学创作，GPT-5都展现出专业水准的输出质量。
"""
            metadata_dict = {
                "title": "AI技术新纪元：GPT-5的能力解析",
                "description": "深度分析GPT-5能力",
                "language": "zh-CN"
            }
        else:
            markdown = """# GPT-5应用场景探索

## 企业应用

GPT-5可以帮助企业提升生产力，自动化复杂任务。

## 教育场景

个性化学习助手，适应每个学生的学习节奏。
"""
            metadata_dict = {
                "title": "GPT-5应用场景探索",
                "description": "GPT-5实际应用",
                "language": "zh-CN"
            }

        result = Mock()
        result.markdown = markdown
        result.html = f"<html><body>{markdown}</body></html>"
        result.metadata = Mock()
        result.metadata.dict = Mock(return_value=metadata_dict)
        return result

    return create_firecrawl_result


class TestNLSearchEndToEndIntegration:
    """端到端集成测试套件"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_search_flow_with_firecrawl_and_storage(
        self,
        service,
        mock_llm_analysis,
        mock_gpt5_search_results,
        mock_firecrawl_results
    ):
        """
        测试完整搜索流程：创建搜索 → Firecrawl抓取 → 存储 → 检索验证

        验证流程:
        1. create_search() 创建搜索记录
        2. LLM解析查询意图
        3. GPT5 Search返回URL列表
        4. Firecrawl并发抓取每个URL的内容
        5. 将抓取内容存储到nl_search_logs的search_results字段
        6. get_search_results() 检索验证存储的内容
        """
        # Mock外部依赖
        with patch.object(service.repository, 'create', return_value="test_log_id_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="GPT-5 最新技术突破 2024"), \
             patch.object(service.gpt5_adapter, 'search', return_value=mock_gpt5_search_results), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=lambda url, **kwargs: mock_firecrawl_results(url)), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update, \
             patch.object(service.repository, 'get_by_id', return_value={
                 "_id": "test_log_id_001",
                 "query_text": "GPT-5最新技术突破",
                 "created_at": datetime.utcnow()
             }), \
             patch.object(service.repository, 'get_search_results', return_value=None) as mock_get_results:

            # 步骤1: 创建搜索
            create_result = await service.create_search(
                query_text="GPT-5最新技术突破",
                user_id="integration_test_user"
            )

            # 验证创建结果
            assert create_result["log_id"] == "test_log_id_001"
            assert create_result["query_text"] == "GPT-5最新技术突破"
            assert "analysis" in create_result
            assert create_result["analysis"] == mock_llm_analysis

            # 步骤2: 验证Firecrawl被调用（3个URL，3次调用）
            assert service.firecrawl_adapter.scrape.call_count == 3

            # 验证每个URL都被抓取
            called_urls = [call[1]['url'] for call in service.firecrawl_adapter.scrape.call_args_list]
            assert "https://example1.com/gpt5-release" in called_urls
            assert "https://example2.com/gpt5-capabilities" in called_urls
            assert "https://example3.com/gpt5-applications" in called_urls

            # 步骤3: 验证update_search_results被调用
            assert mock_update.called
            update_call_args = mock_update.call_args

            # 验证存储的结果包含抓取内容
            stored_results = update_call_args[1]['search_results']
            assert len(stored_results) == 3

            # 验证第一个结果的抓取内容
            first_result = stored_results[0]
            assert first_result["scrape_success"] is True
            assert "markdown_content" in first_result
            assert "GPT-5发布" in first_result["markdown_content"]
            assert "html_content" in first_result
            assert "metadata" in first_result
            assert first_result["metadata"]["title"] == "GPT-5发布：OpenAI的最新突破"

            # 验证第二个结果
            second_result = stored_results[1]
            assert second_result["scrape_success"] is True
            assert "AI技术新纪元" in second_result["markdown_content"]

            # 验证第三个结果
            third_result = stored_results[2]
            assert third_result["scrape_success"] is True
            assert "应用场景" in third_result["markdown_content"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_partial_firecrawl_failure_scenario(
        self,
        service,
        mock_llm_analysis,
        mock_gpt5_search_results
    ):
        """
        测试部分Firecrawl抓取失败的场景

        验证:
        1. 部分URL抓取成功
        2. 部分URL抓取失败（标记scrape_success=False）
        3. 失败的URL仍然保留基本信息（title, url, snippet）
        4. 整体流程继续执行，不中断
        """
        # 创建混合结果的Firecrawl mock
        def mixed_firecrawl_results(url: str):
            if "example1.com" in url:
                # 第一个成功
                result = Mock()
                result.markdown = "# 成功抓取的内容"
                result.html = "<html>成功</html>"
                result.metadata = Mock()
                result.metadata.dict = Mock(return_value={"title": "成功页面"})
                return result
            elif "example2.com" in url:
                # 第二个失败
                raise Exception("Network timeout")
            else:
                # 第三个成功
                result = Mock()
                result.markdown = "# 另一个成功的内容"
                result.html = "<html>成功</html>"
                result.metadata = Mock()
                result.metadata.dict = Mock(return_value={"title": "成功页面2"})
                return result

        with patch.object(service.repository, 'create', return_value="test_log_id_002"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="测试查询"), \
             patch.object(service.gpt5_adapter, 'search', return_value=mock_gpt5_search_results), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mixed_firecrawl_results), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行搜索
            result = await service.create_search(
                query_text="测试部分失败",
                user_id="test_user"
            )

            # 验证结果
            assert mock_update.called
            stored_results = mock_update.call_args[1]['search_results']

            # 验证3个结果都存在
            assert len(stored_results) == 3

            # 验证成功和失败的标记
            success_count = sum(1 for r in stored_results if r.get("scrape_success") is True)
            failure_count = sum(1 for r in stored_results if r.get("scrape_success") is False)

            assert success_count == 2
            assert failure_count == 1

            # 验证失败的结果仍保留基本信息
            failed_result = next(r for r in stored_results if r.get("scrape_success") is False)
            assert "title" in failed_result
            assert "url" in failed_result
            assert "snippet" in failed_result
            assert "scrape_error" in failed_result
            assert "Network timeout" in failed_result["scrape_error"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_content_truncation_in_storage(
        self,
        service,
        mock_llm_analysis,
        mock_gpt5_search_results
    ):
        """
        测试内容截断在存储时的正确性

        验证:
        1. Markdown内容超过5000字符时被截断
        2. HTML内容超过10000字符时被截断
        3. 截断后的内容仍然有效
        """
        # 创建超长内容的Firecrawl结果
        long_content_result = Mock()
        long_content_result.markdown = "x" * 10000  # 超过5000限制
        long_content_result.html = "y" * 20000  # 超过10000限制
        long_content_result.metadata = Mock()
        long_content_result.metadata.dict = Mock(return_value={"title": "长内容测试"})

        with patch.object(service.repository, 'create', return_value="test_log_id_003"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="测试查询"), \
             patch.object(service.gpt5_adapter, 'search', return_value=mock_gpt5_search_results[:1]), \
             patch.object(service.firecrawl_adapter, 'scrape', return_value=long_content_result), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行搜索
            await service.create_search(
                query_text="测试内容截断",
                user_id="test_user"
            )

            # 验证存储的内容长度
            stored_results = mock_update.call_args[1]['search_results']
            first_result = stored_results[0]

            # 验证截断
            assert len(first_result["markdown_content"]) == 5000
            assert len(first_result["html_content"]) == 10000

            # 验证内容仍然有效
            assert first_result["markdown_content"] == "x" * 5000
            assert first_result["html_content"] == "y" * 10000

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_scraping_control(
        self,
        service,
        mock_llm_analysis,
        mock_firecrawl_results
    ):
        """
        测试并发抓取控制

        验证:
        1. Semaphore正确限制并发数
        2. 所有URL最终都被抓取
        3. 并发执行提升性能
        """
        # 创建更多的搜索结果（12个URL）
        large_search_results = []
        for i in range(12):
            large_search_results.append(
                Mock(to_dict=Mock(return_value={
                    "title": f"结果{i+1}",
                    "url": f"https://example.com/page{i+1}",
                    "snippet": f"摘要{i+1}",
                    "position": i+1,
                    "score": 0.95 - (i * 0.01),
                    "source": "serpapi"
                }))
            )

        scrape_times = []

        async def timed_scrape(url: str, **kwargs):
            """记录抓取时间的mock"""
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)  # 模拟100ms抓取时间
            scrape_times.append(asyncio.get_event_loop().time() - start)
            return mock_firecrawl_results(url)

        with patch.object(service.repository, 'create', return_value="test_log_id_004"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="测试查询"), \
             patch.object(service.gpt5_adapter, 'search', return_value=large_search_results), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=timed_scrape), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行搜索（使用并发数=3）
            import time
            start_time = time.time()

            await service.create_search(
                query_text="测试并发控制",
                user_id="test_user"
            )

            duration = time.time() - start_time

            # 验证所有URL都被抓取
            assert service.firecrawl_adapter.scrape.call_count == 12

            # 验证存储了12个结果
            stored_results = mock_update.call_args[1]['search_results']
            assert len(stored_results) == 12

            # 验证并发控制生效（12个任务,并发3,每个100ms ≈ 0.4秒）
            # 如果串行执行需要1.2秒，并发应该明显更快
            assert duration < 0.8, f"并发执行耗时 {duration:.2f}秒，未达到性能预期"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retrieval_after_storage(
        self,
        service,
        mock_llm_analysis,
        mock_gpt5_search_results,
        mock_firecrawl_results
    ):
        """
        测试存储后的检索功能

        验证:
        1. 成功存储后能够通过get_search_results检索
        2. 检索的结果包含完整的抓取内容
        3. 数据完整性验证
        """
        stored_results_data = None

        async def capture_stored_results(log_id: str, search_results: List[Dict], results_count: int):
            """捕获存储的数据"""
            nonlocal stored_results_data
            stored_results_data = search_results
            return True

        with patch.object(service.repository, 'create', return_value="test_log_id_005"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="测试查询"), \
             patch.object(service.gpt5_adapter, 'search', return_value=mock_gpt5_search_results), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=lambda url, **kwargs: mock_firecrawl_results(url)), \
             patch.object(service.repository, 'update_search_results', side_effect=capture_stored_results), \
             patch.object(service.repository, 'get_by_id', return_value={
                 "_id": "test_log_id_005",
                 "query_text": "测试检索",
                 "created_at": datetime.utcnow()
             }), \
             patch.object(service.repository, 'get_search_results', side_effect=lambda log_id: stored_results_data):

            # 步骤1: 创建并存储搜索
            await service.create_search(
                query_text="测试检索",
                user_id="test_user"
            )

            # 步骤2: 检索存储的结果
            retrieval_result = await service.get_search_results(
                log_id="test_log_id_005",
                limit=10,
                offset=0
            )

            # 验证检索结果
            assert retrieval_result is not None
            assert "results" in retrieval_result
            assert len(retrieval_result["results"]) == 3

            # 验证第一个结果的完整性
            first = retrieval_result["results"][0]
            assert first["title"] == "GPT-5发布：OpenAI的最新突破"
            assert first["url"] == "https://example1.com/gpt5-release"
            assert first["scrape_success"] is True
            assert "GPT-5发布" in first["markdown_content"]
            assert "html_content" in first
            assert "metadata" in first
            assert first["metadata"]["title"] == "GPT-5发布：OpenAI的最新突破"


class TestNLSearchSpecificLogID:
    """针对特定log_id的测试（模拟实际场景）"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_specific_log_id_249096312186568704_flow(self, service):
        """
        测试特定log_id (249096312186568704) 的完整流程

        这个测试模拟真实场景：
        1. 创建一个搜索记录，log_id为249096312186568704
        2. 验证返回的URL调用了Firecrawl Scrape接口
        3. 验证数据被正确存储到search_results字段
        """
        specific_log_id = "249096312186568704"

        # 模拟真实的搜索结果
        real_search_results = [
            Mock(to_dict=Mock(return_value={
                "title": "AI技术突破报告",
                "url": "https://thetibetpost.com/ai-breakthrough",
                "snippet": "最新AI技术发展报告...",
                "position": 1,
                "score": 0.95,
                "source": "serpapi"
            }))
        ]

        # 模拟真实的Firecrawl结果
        real_firecrawl_result = Mock()
        real_firecrawl_result.markdown = "# AI技术突破\n\n详细内容..."
        real_firecrawl_result.html = "<html><body>详细内容</body></html>"
        real_firecrawl_result.metadata = Mock()
        real_firecrawl_result.metadata.dict = Mock(return_value={
            "title": "AI技术突破报告",
            "description": "最新AI发展",
            "language": "zh-CN"
        })

        with patch.object(service.repository, 'create', return_value=specific_log_id), \
             patch.object(service.llm_processor, 'parse_query', return_value={"intent": "research"}), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="AI技术突破"), \
             patch.object(service.gpt5_adapter, 'search', return_value=real_search_results), \
             patch.object(service.firecrawl_adapter, 'scrape', return_value=real_firecrawl_result) as mock_scrape, \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行搜索
            result = await service.create_search(
                query_text="AI技术突破",
                user_id="real_user"
            )

            # 验证log_id
            assert result["log_id"] == specific_log_id

            # 验证Firecrawl被调用
            assert mock_scrape.called
            scrape_call = mock_scrape.call_args
            assert scrape_call[1]['url'] == "https://thetibetpost.com/ai-breakthrough"

            # 验证update_search_results被调用，存储了抓取内容
            assert mock_update.called
            update_call = mock_update.call_args

            # 验证log_id正确
            assert update_call[1]['log_id'] == specific_log_id

            # 验证存储的数据包含Firecrawl抓取的内容
            stored_data = update_call[1]['search_results']
            assert len(stored_data) == 1
            assert stored_data[0]["scrape_success"] is True
            assert "AI技术突破" in stored_data[0]["markdown_content"]
            assert stored_data[0]["metadata"]["title"] == "AI技术突破报告"


class TestMultiQuestionSearchIntegration:
    """多问题分解搜索集成测试套件"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_search_complete_flow(
        self,
        service,
        mock_llm_analysis
    ):
        """
        测试多问题搜索的完整流程

        验证:
        1. LLM分解查询为4个子问题
        2. 循环搜索每个子问题
        3. 聚合和去重结果
        4. 并发抓取内容
        5. 正确返回多问题搜索特有的字段
        """
        # Mock 4个子问题
        sub_queries = [
            "GPT-5最新发布和特性",
            "AI图像生成技术进展",
            "自动驾驶AI突破",
            "AI医疗诊断新应用"
        ]

        # Mock每个子问题的搜索结果（有部分URL重复）
        def create_mock_results_for_query(query: str, query_index: int):
            if query_index == 1:
                # 第一个查询
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "GPT-5发布详情",
                        "url": "https://example.com/gpt5-release",  # 重复URL
                        "snippet": "GPT-5正式发布...",
                        "position": 1,
                        "score": 0.95,
                        "source": "serpapi"
                    })),
                    Mock(to_dict=Mock(return_value={
                        "title": "GPT-5技术分析",
                        "url": "https://example.com/gpt5-tech",
                        "snippet": "深入分析GPT-5技术...",
                        "position": 2,
                        "score": 0.90,
                        "source": "serpapi"
                    }))
                ]
            elif query_index == 2:
                # 第二个查询（包含一个重复的URL）
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "AI图像生成革命",
                        "url": "https://example.com/ai-image",
                        "snippet": "图像生成技术突破...",
                        "position": 1,
                        "score": 0.92,
                        "source": "serpapi"
                    })),
                    Mock(to_dict=Mock(return_value={
                        "title": "GPT-5发布详情",  # 重复的URL，但分数更低
                        "url": "https://example.com/gpt5-release",
                        "snippet": "GPT-5正式发布...",
                        "position": 2,
                        "score": 0.88,  # 较低的分数
                        "source": "serpapi"
                    }))
                ]
            elif query_index == 3:
                # 第三个查询
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "自动驾驶新突破",
                        "url": "https://example.com/autonomous",
                        "snippet": "自动驾驶技术进展...",
                        "position": 1,
                        "score": 0.93,
                        "source": "serpapi"
                    }))
                ]
            else:
                # 第四个查询
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "AI医疗诊断应用",
                        "url": "https://example.com/ai-medical",
                        "snippet": "AI在医疗领域的应用...",
                        "position": 1,
                        "score": 0.91,
                        "source": "serpapi"
                    }))
                ]

        # Mock Firecrawl结果
        def mock_firecrawl(url: str, **kwargs):
            result = Mock()
            result.markdown = f"# Content from {url}\n\nDetailed content..."
            result.html = f"<html><body>Content from {url}</body></html>"
            result.metadata = Mock()
            result.metadata.dict = Mock(return_value={"title": f"Title for {url}"})
            return result

        # 设置search方法的side_effect，根据不同查询返回不同结果
        search_call_count = [0]
        def search_side_effect(query: str, max_results: int):
            search_call_count[0] += 1
            return create_mock_results_for_query(query, search_call_count[0])

        with patch.object(service.repository, 'create', return_value="multi_test_log_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'decompose_query', return_value=sub_queries), \
             patch.object(service.gpt5_adapter, 'search', side_effect=search_side_effect) as mock_search, \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mock_firecrawl) as mock_scrape, \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行多问题搜索
            result = await service.create_search(
                query_text="最近AI技术突破",
                user_id="multi_test_user",
                search_mode="multi"
            )

            # 验证返回的基本字段
            assert result["log_id"] == "multi_test_log_001"
            assert result["search_mode"] == "multi"
            assert "sub_queries" in result
            assert len(result["sub_queries"]) == 4
            assert result["sub_queries"] == sub_queries

            # 验证搜索被调用4次（每个子问题一次）
            assert mock_search.call_count == 4

            # 验证total_raw_results和total_unique_results
            assert "total_raw_results" in result
            assert "total_unique_results" in result
            assert result["total_raw_results"] == 6  # 总共6个原始结果
            # 去重后应该是5个（gpt5-release重复了）
            assert result["total_unique_results"] <= result["total_raw_results"]

            # 验证results字段包含去重后的结果
            assert "results" in result
            assert len(result["results"]) == 5  # 去重后5个唯一URL

            # 验证Firecrawl被调用（去重后的5个URL）
            assert mock_scrape.call_count == 5

            # 验证存储被调用
            assert mock_update.called
            stored_results = mock_update.call_args[1]['search_results']
            assert len(stored_results) == 5

            # 验证去重后的结果包含频率信息
            first_result = stored_results[0]
            if first_result["url"] == "https://example.com/gpt5-release":
                # 重复的URL应该有appearances字段
                assert "appearances_in_sub_queries" in first_result
                assert first_result["appearances_in_sub_queries"] == 2
                assert "related_sub_queries" in first_result
                assert len(first_result["related_sub_queries"]) == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_search_deduplication_and_scoring(
        self,
        service,
        mock_llm_analysis
    ):
        """
        测试多问题搜索的去重和评分逻辑

        验证:
        1. 基于URL去重
        2. 保留最高分数的结果
        3. 频率加成计算正确
        4. 最终分数排序正确
        """
        sub_queries = ["查询1", "查询2", "查询3", "查询4"]

        # 创建包含重复URL的搜索结果
        def create_results_with_duplicates(query: str, max_results: int):
            if query == "查询1":
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "结果A",
                        "url": "https://example.com/A",
                        "snippet": "内容A",
                        "position": 1,
                        "score": 0.90,  # 基础分数0.90
                        "source": "serpapi"
                    })),
                    Mock(to_dict=Mock(return_value={
                        "title": "结果B",
                        "url": "https://example.com/B",
                        "snippet": "内容B",
                        "position": 2,
                        "score": 0.80,
                        "source": "serpapi"
                    }))
                ]
            elif query == "查询2":
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "结果A再现",  # 重复URL
                        "url": "https://example.com/A",
                        "snippet": "内容A",
                        "position": 1,
                        "score": 0.85,  # 较低分数，不应该被采用
                        "source": "serpapi"
                    })),
                    Mock(to_dict=Mock(return_value={
                        "title": "结果C",
                        "url": "https://example.com/C",
                        "snippet": "内容C",
                        "position": 2,
                        "score": 0.75,
                        "source": "serpapi"
                    }))
                ]
            elif query == "查询3":
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "结果A第三次",  # 再次重复
                        "url": "https://example.com/A",
                        "snippet": "内容A",
                        "position": 1,
                        "score": 0.88,
                        "source": "serpapi"
                    }))
                ]
            else:
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": "结果D",
                        "url": "https://example.com/D",
                        "snippet": "内容D",
                        "position": 1,
                        "score": 0.70,
                        "source": "serpapi"
                    }))
                ]

        def mock_firecrawl(url: str, **kwargs):
            result = Mock()
            result.markdown = f"Content {url}"
            result.html = f"<html>{url}</html>"
            result.metadata = Mock()
            result.metadata.dict = Mock(return_value={"title": url})
            return result

        with patch.object(service.repository, 'create', return_value="dedup_test_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'decompose_query', return_value=sub_queries), \
             patch.object(service.gpt5_adapter, 'search', side_effect=create_results_with_duplicates), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mock_firecrawl), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行多问题搜索
            result = await service.create_search(
                query_text="测试去重",
                user_id="test_user",
                search_mode="multi"
            )

            # 获取存储的结果
            stored_results = mock_update.call_args[1]['search_results']

            # 验证去重：6个原始结果 → 4个唯一URL
            assert result["total_raw_results"] == 6
            assert len(stored_results) == 4

            # 找到URL A的结果
            result_a = next(r for r in stored_results if r["url"] == "https://example.com/A")

            # 验证保留了最高分数（0.90）
            base_score = 0.90
            # appearances = 3, 频率加成 = (3-1) * 0.1 = 0.2（默认配置）
            # 最终分数 = 0.90 + 0.2 = 1.0 (不超过1.0)
            expected_final_score = min(base_score + 0.2, 1.0)
            assert result_a["score"] == pytest.approx(expected_final_score, rel=0.01)

            # 验证出现次数
            assert result_a["appearances_in_sub_queries"] == 3
            assert len(result_a["related_sub_queries"]) == 3

            # 验证结果按分数排序（A应该排在最前面，因为有频率加成）
            assert stored_results[0]["url"] == "https://example.com/A"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_search_partial_failure_handling(
        self,
        service,
        mock_llm_analysis
    ):
        """
        测试多问题搜索中部分子问题失败的处理

        验证:
        1. 部分子问题搜索失败时继续执行其他子问题
        2. 成功的结果被正确聚合
        3. 整体流程不中断
        """
        sub_queries = ["查询1", "查询2-失败", "查询3", "查询4"]

        def search_with_partial_failure(query: str, max_results: int):
            if "失败" in query:
                raise Exception("Search API timeout")
            else:
                return [
                    Mock(to_dict=Mock(return_value={
                        "title": f"结果 for {query}",
                        "url": f"https://example.com/{query}",
                        "snippet": f"内容 {query}",
                        "position": 1,
                        "score": 0.90,
                        "source": "serpapi"
                    }))
                ]

        def mock_firecrawl(url: str, **kwargs):
            result = Mock()
            result.markdown = f"Content {url}"
            result.html = f"<html>{url}</html>"
            result.metadata = Mock()
            result.metadata.dict = Mock(return_value={"title": url})
            return result

        with patch.object(service.repository, 'create', return_value="failure_test_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'decompose_query', return_value=sub_queries), \
             patch.object(service.gpt5_adapter, 'search', side_effect=search_with_partial_failure), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mock_firecrawl), \
             patch.object(service.repository, 'update_search_results', return_value=True) as mock_update:

            # 执行多问题搜索（期望不抛异常）
            result = await service.create_search(
                query_text="测试部分失败",
                user_id="test_user",
                search_mode="multi"
            )

            # 验证返回结果
            assert result["log_id"] == "failure_test_001"
            assert result["search_mode"] == "multi"

            # 验证只有3个子问题成功（查询2失败）
            stored_results = mock_update.call_args[1]['search_results']
            assert len(stored_results) == 3  # 只有3个成功的查询

            # 验证total_raw_results只包含成功的结果
            assert result["total_raw_results"] == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_search_vs_single_search_comparison(
        self,
        service,
        mock_llm_analysis
    ):
        """
        对比测试single模式和multi模式的返回字段差异

        验证:
        1. Single模式返回refined_query
        2. Multi模式返回sub_queries, total_raw_results, total_unique_results
        3. 两种模式都返回results
        """
        sub_queries = ["子问题1", "子问题2", "子问题3", "子问题4"]

        def create_single_result(query: str, max_results: int):
            return [Mock(to_dict=Mock(return_value={
                "title": "单一结果",
                "url": "https://example.com/single",
                "snippet": "单一查询结果",
                "position": 1,
                "score": 0.95,
                "source": "serpapi"
            }))]

        def mock_firecrawl(url: str, **kwargs):
            result = Mock()
            result.markdown = "Content"
            result.html = "<html>Content</html>"
            result.metadata = Mock()
            result.metadata.dict = Mock(return_value={"title": "Title"})
            return result

        # 测试Single模式
        with patch.object(service.repository, 'create', return_value="single_test_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'refine_query', return_value="精炼查询"), \
             patch.object(service.gpt5_adapter, 'search', side_effect=create_single_result), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mock_firecrawl), \
             patch.object(service.repository, 'update_search_results', return_value=True):

            single_result = await service.create_search(
                query_text="测试查询",
                user_id="test_user",
                search_mode="single"
            )

            # 验证Single模式特有字段
            assert "refined_query" in single_result
            assert single_result["refined_query"] == "精炼查询"
            assert "sub_queries" not in single_result
            assert "total_raw_results" not in single_result
            assert "total_unique_results" not in single_result
            assert single_result["search_mode"] == "single"

        # 测试Multi模式
        with patch.object(service.repository, 'create', return_value="multi_test_001"), \
             patch.object(service.llm_processor, 'parse_query', return_value=mock_llm_analysis), \
             patch.object(service.repository, 'update_llm_analysis', return_value=True), \
             patch.object(service.llm_processor, 'decompose_query', return_value=sub_queries), \
             patch.object(service.gpt5_adapter, 'search', side_effect=create_single_result), \
             patch.object(service.firecrawl_adapter, 'scrape', side_effect=mock_firecrawl), \
             patch.object(service.repository, 'update_search_results', return_value=True):

            multi_result = await service.create_search(
                query_text="测试查询",
                user_id="test_user",
                search_mode="multi"
            )

            # 验证Multi模式特有字段
            assert "refined_query" not in multi_result
            assert "sub_queries" in multi_result
            assert len(multi_result["sub_queries"]) == 4
            assert "total_raw_results" in multi_result
            assert "total_unique_results" in multi_result
            assert multi_result["search_mode"] == "multi"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])
