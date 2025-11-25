"""
MongoDB NL Search Repository 测试
包含搜索结果存储（含抓取内容）的完整测试套件

测试覆盖:
1. 搜索记录CRUD操作
2. 搜索结果存储（包含markdown/html内容）
3. 索引创建和查询性能
4. 数据完整性验证

版本: v2.0.0 (MongoDB)
日期: 2025-11-18
"""
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.infrastructure.database.mongo_nl_search_repository import (
    MongoNLSearchLogRepository
)


@pytest.fixture
async def repository():
    """创建Repository实例"""
    repo = MongoNLSearchLogRepository()
    # 确保集合已初始化
    await repo._get_collection()
    return repo


@pytest.fixture
def sample_llm_analysis() -> Dict[str, Any]:
    """样例LLM分析结果"""
    return {
        "intent": "technology_news",
        "keywords": ["AI", "技术突破", "2024"],
        "entities": [
            {"type": "technology", "value": "AI"},
            {"type": "time", "value": "2024"}
        ],
        "time_range": {
            "type": "recent",
            "from": "2024-01-01",
            "to": "2024-12-31"
        },
        "confidence": 0.95
    }


@pytest.fixture
def sample_search_results() -> List[Dict[str, Any]]:
    """样例搜索结果（包含抓取内容）"""
    return [
        {
            "title": "GPT-5发布：AI技术新突破",
            "url": "https://example1.com/gpt5",
            "snippet": "OpenAI发布最新GPT-5模型...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi",
            # 🆕 抓取内容
            "markdown_content": "# GPT-5发布\n\nOpenAI今天正式发布了GPT-5模型，这是继GPT-4之后的又一重大突破...",
            "html_content": "<html><body><h1>GPT-5发布</h1><p>OpenAI今天正式发布...</p></body></html>",
            "metadata": {
                "title": "GPT-5发布 - OpenAI官网",
                "description": "最新AI技术突破",
                "language": "zh-CN",
                "ogImage": "https://example1.com/image1.jpg"
            },
            "scrape_success": True
        },
        {
            "title": "2024年AI技术回顾",
            "url": "https://example2.com/ai-review-2024",
            "snippet": "2024年人工智能领域取得了多项重大进展...",
            "position": 2,
            "score": 0.90,
            "source": "serpapi",
            # 🆕 抓取内容（部分失败示例）
            "markdown_content": None,
            "html_content": None,
            "metadata": {},
            "scrape_success": False,
            "scrape_error": "Connection timeout"
        },
        {
            "title": "深度学习最新研究进展",
            "url": "https://example3.com/deep-learning",
            "snippet": "深度学习在计算机视觉和自然语言处理领域...",
            "position": 3,
            "score": 0.85,
            "source": "serpapi",
            # 🆕 抓取内容
            "markdown_content": "## 深度学习最新进展\n\n本文介绍了2024年深度学习的最新研究成果...",
            "html_content": "<html><body><h2>深度学习最新进展</h2>...</body></html>",
            "metadata": {
                "title": "深度学习进展 - AI Research",
                "language": "zh-CN"
            },
            "scrape_success": True
        }
    ]


class TestBasicCRUD:
    """基础CRUD操作测试"""

    @pytest.mark.asyncio
    async def test_create_search_log(self, repository, sample_llm_analysis):
        """测试创建搜索记录"""
        # 创建记录
        log_id = await repository.create(
            query_text="最近有哪些AI技术突破",
            user_id="test_user_123",
            llm_analysis=sample_llm_analysis,
            search_config={"max_results": 10}
        )

        # 验证返回ID
        assert log_id is not None
        assert isinstance(log_id, str)

        # 查询验证
        log = await repository.get_by_id(log_id)
        assert log is not None
        assert log["query_text"] == "最近有哪些AI技术突破"
        assert log["user_id"] == "test_user_123"
        assert log["llm_analysis"]["intent"] == "technology_news"
        assert log["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """测试查询不存在的记录"""
        log = await repository.get_by_id("nonexistent_id_999")
        assert log is None

    @pytest.mark.asyncio
    async def test_update_llm_analysis(self, repository, sample_llm_analysis):
        """测试更新LLM分析结果"""
        # 创建记录
        log_id = await repository.create(
            query_text="测试查询",
            llm_analysis=None
        )

        # 更新分析结果
        success = await repository.update_llm_analysis(
            log_id=log_id,
            llm_analysis=sample_llm_analysis
        )

        assert success is True

        # 验证更新
        log = await repository.get_by_id(log_id)
        assert log["llm_analysis"]["intent"] == "technology_news"
        assert len(log["llm_analysis"]["keywords"]) == 3

    @pytest.mark.asyncio
    async def test_update_status(self, repository):
        """测试更新搜索状态"""
        # 创建记录
        log_id = await repository.create(
            query_text="测试查询"
        )

        # 更新状态
        success = await repository.update_status(
            log_id=log_id,
            status="completed",
            results_count=10
        )

        assert success is True

        # 验证更新
        log = await repository.get_by_id(log_id)
        assert log["status"] == "completed"
        assert log["results_count"] == 10


class TestSearchResultsStorage:
    """搜索结果存储测试（核心功能）"""

    @pytest.mark.asyncio
    async def test_update_search_results_with_scrape_content(
        self,
        repository,
        sample_search_results
    ):
        """测试保存包含抓取内容的搜索结果"""
        # 创建搜索记录
        log_id = await repository.create(
            query_text="AI技术突破"
        )

        # 保存搜索结果（包含抓取内容）
        success = await repository.update_search_results(
            log_id=log_id,
            search_results=sample_search_results,
            results_count=len(sample_search_results)
        )

        assert success is True

        # 验证保存的结果
        results = await repository.get_search_results(log_id)
        assert results is not None
        assert len(results) == 3

        # 验证第一个结果的抓取内容
        result1 = results[0]
        assert result1["title"] == "GPT-5发布：AI技术新突破"
        assert result1["markdown_content"].startswith("# GPT-5发布")
        assert result1["html_content"].startswith("<html>")
        assert result1["metadata"]["title"] == "GPT-5发布 - OpenAI官网"
        assert result1["scrape_success"] is True

        # 验证第二个结果（抓取失败）
        result2 = results[1]
        assert result2["scrape_success"] is False
        assert result2["scrape_error"] == "Connection timeout"
        assert result2["markdown_content"] is None

        # 验证第三个结果
        result3 = results[2]
        assert result3["scrape_success"] is True
        assert "深度学习" in result3["markdown_content"]

    @pytest.mark.asyncio
    async def test_update_search_results_without_scrape_content(
        self,
        repository
    ):
        """测试保存不含抓取内容的搜索结果（向后兼容）"""
        # 创建搜索记录
        log_id = await repository.create(
            query_text="测试查询"
        )

        # 保存基础搜索结果（不含抓取内容）
        basic_results = [
            {
                "title": "测试结果",
                "url": "https://example.com",
                "snippet": "测试摘要",
                "position": 1,
                "score": 0.95,
                "source": "serpapi"
            }
        ]

        success = await repository.update_search_results(
            log_id=log_id,
            search_results=basic_results,
            results_count=1
        )

        assert success is True

        # 验证保存的结果
        results = await repository.get_search_results(log_id)
        assert len(results) == 1
        assert results[0]["title"] == "测试结果"
        # 抓取字段不存在或为None
        assert results[0].get("markdown_content") is None

    @pytest.mark.asyncio
    async def test_get_search_results_nonexistent(self, repository):
        """测试获取不存在的搜索结果"""
        results = await repository.get_search_results("nonexistent_log_id")
        assert results is None

    @pytest.mark.asyncio
    async def test_update_search_results_large_content(
        self,
        repository
    ):
        """测试保存大量抓取内容"""
        # 创建搜索记录
        log_id = await repository.create(
            query_text="大内容测试"
        )

        # 创建包含大量内容的结果
        large_results = [
            {
                "title": f"结果 {i}",
                "url": f"https://example{i}.com",
                "snippet": f"摘要 {i}",
                "position": i,
                "score": 0.95 - i * 0.01,
                "source": "serpapi",
                "markdown_content": "x" * 4000,  # 4KB markdown
                "html_content": "y" * 9000,  # 9KB HTML
                "metadata": {"title": f"页面{i}"},
                "scrape_success": True
            }
            for i in range(1, 21)  # 20个结果
        ]

        # 保存结果
        success = await repository.update_search_results(
            log_id=log_id,
            search_results=large_results,
            results_count=20
        )

        assert success is True

        # 验证保存
        results = await repository.get_search_results(log_id)
        assert len(results) == 20

        # 验证数据完整性
        for i, result in enumerate(results, 1):
            assert result["title"] == f"结果 {i}"
            assert len(result["markdown_content"]) == 4000
            assert len(result["html_content"]) == 9000


class TestQueryOperations:
    """查询操作测试"""

    @pytest.mark.asyncio
    async def test_get_recent(self, repository):
        """测试获取最近记录"""
        # 创建多条记录
        log_ids = []
        for i in range(5):
            log_id = await repository.create(
                query_text=f"查询 {i}",
                user_id="test_user"
            )
            log_ids.append(log_id)

        # 查询最近3条
        logs = await repository.get_recent(limit=3, offset=0)

        assert len(logs) <= 3
        # 验证按时间倒序
        if len(logs) > 1:
            for i in range(len(logs) - 1):
                assert logs[i]["created_at"] >= logs[i + 1]["created_at"]

    @pytest.mark.asyncio
    async def test_get_recent_with_user_filter(self, repository):
        """测试按用户过滤"""
        # 创建不同用户的记录
        await repository.create(query_text="查询1", user_id="user_a")
        await repository.create(query_text="查询2", user_id="user_b")
        await repository.create(query_text="查询3", user_id="user_a")

        # 查询user_a的记录
        logs = await repository.get_recent(limit=10, offset=0, user_id="user_a")

        assert all(log["user_id"] == "user_a" for log in logs)

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, repository):
        """测试关键词搜索"""
        # 创建包含不同关键词的记录
        await repository.create(
            query_text="AI技术突破",
            llm_analysis={"keywords": ["AI", "技术"]}
        )
        await repository.create(
            query_text="深度学习进展",
            llm_analysis={"keywords": ["深度学习"]}
        )
        await repository.create(
            query_text="AI应用场景",
            llm_analysis={"keywords": ["AI", "应用"]}
        )

        # 搜索包含"AI"的记录
        logs = await repository.search_by_keyword("AI", limit=10)

        assert len(logs) >= 2
        assert all("AI" in log["query_text"] or "AI" in log.get("llm_analysis", {}).get("keywords", [])
                   for log in logs)

    @pytest.mark.asyncio
    async def test_count_total(self, repository):
        """测试统计总数"""
        # 创建记录
        for i in range(3):
            await repository.create(
                query_text=f"查询 {i}",
                user_id="test_user"
            )

        # 统计总数
        total = await repository.count_total(user_id="test_user")
        assert total >= 3


class TestDataCleanup:
    """数据清理测试"""

    @pytest.mark.asyncio
    async def test_delete_by_id(self, repository):
        """测试删除记录"""
        # 创建记录
        log_id = await repository.create(
            query_text="待删除的查询"
        )

        # 验证存在
        log = await repository.get_by_id(log_id)
        assert log is not None

        # 删除记录
        success = await repository.delete_by_id(log_id)
        assert success is True

        # 验证已删除
        log = await repository.get_by_id(log_id)
        assert log is None

    @pytest.mark.asyncio
    async def test_delete_old_records(self, repository):
        """测试删除旧记录"""
        # 创建旧记录（模拟）
        collection = await repository._get_collection()

        old_date = datetime.utcnow() - timedelta(days=35)
        await collection.insert_one({
            "_id": "old_log_1",
            "query_text": "旧查询1",
            "created_at": old_date,
            "updated_at": old_date
        })

        # 删除超过30天的记录
        deleted_count = await repository.delete_old_records(days=30)

        assert deleted_count >= 1


class TestIndexes:
    """索引测试"""

    @pytest.mark.asyncio
    async def test_create_indexes(self, repository):
        """测试创建索引"""
        # 创建索引
        await repository.create_indexes()

        # 验证索引存在
        collection = await repository._get_collection()
        indexes = await collection.list_indexes().to_list(length=None)

        index_names = [idx["name"] for idx in indexes]

        # 验证关键索引
        assert "created_at_desc" in index_names
        assert "user_created_idx" in index_names
        assert "status_idx" in index_names
        assert "query_text_idx" in index_names


class TestDataIntegrity:
    """数据完整性测试"""

    @pytest.mark.asyncio
    async def test_concurrent_updates(self, repository, sample_search_results):
        """测试并发更新"""
        import asyncio

        # 创建记录
        log_id = await repository.create(
            query_text="并发测试"
        )

        # 并发更新
        async def update_results():
            return await repository.update_search_results(
                log_id=log_id,
                search_results=sample_search_results,
                results_count=len(sample_search_results)
            )

        # 同时执行3个更新
        results = await asyncio.gather(
            update_results(),
            update_results(),
            update_results()
        )

        # 至少有一个成功
        assert any(results)

        # 验证数据完整性
        final_results = await repository.get_search_results(log_id)
        assert len(final_results) == 3

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self, repository):
        """测试特殊字符处理"""
        # 创建包含特殊字符的结果
        special_results = [
            {
                "title": "测试 \"引号\" 和 '单引号'",
                "url": "https://example.com?param=value&other=test",
                "snippet": "包含 <标签> 和 & 符号",
                "position": 1,
                "score": 0.95,
                "source": "serpapi",
                "markdown_content": "# 标题 \n\n代码: `console.log('test')`",
                "html_content": '<div class="content">测试内容</div>',
                "metadata": {
                    "title": "测试 \"特殊\" 字符",
                    "description": "包含 <> & 符号"
                },
                "scrape_success": True
            }
        ]

        # 创建记录
        log_id = await repository.create(
            query_text="特殊字符测试"
        )

        # 保存结果
        success = await repository.update_search_results(
            log_id=log_id,
            search_results=special_results,
            results_count=1
        )

        assert success is True

        # 验证数据保存正确
        results = await repository.get_search_results(log_id)
        assert results[0]["title"] == "测试 \"引号\" 和 '单引号'"
        assert "<标签>" in results[0]["snippet"]
        assert results[0]["metadata"]["title"] == "测试 \"特殊\" 字符"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
