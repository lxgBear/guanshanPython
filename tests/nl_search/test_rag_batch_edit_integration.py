"""
RAG批量编辑集成测试

测试完整流程:
1. RAG查询 → 获取结果列表
2. 获取RAG内容 (url + markdown_content)
3. 批量编辑（保存快照）
4. 创建档案（使用快照）
5. 验证档案包含完整数据

版本: v1.0.0
日期: 2025-11-22
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from bson import ObjectId

from src.infrastructure.database.connection import get_mongodb_database
from src.services.nl_search.mongo_archive_service import mongo_archive_service


@pytest.mark.asyncio
class TestRAGBatchEditIntegration:
    """RAG批量编辑集成测试"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """测试前准备：创建测试数据"""
        self.db = await get_mongodb_database()

        # 创建测试用户（使用整数ID与archive保持一致）
        self.test_user_id = 1001

        # 清理测试数据
        await self.cleanup()

        # 创建测试数据：模拟RAG查询返回的news_results
        self.test_mongo_id = "test_mongo_id_001"
        self.test_news_result = {
            "_id": self.test_mongo_id,
            "url": "https://example.com/test-article",
            "markdown_content": "# 测试文章\n\n这是测试内容...",
            "title": "测试新闻标题",
            "source": "example.com",
            "news_results": {
                "title": "测试新闻标题",
                "content": "这是测试新闻的内容摘要",
                "category": {
                    "大类": "科技",
                    "类别": "人工智能",
                    "地域": "美国"
                },
                "published_at": datetime.utcnow(),
                "source": "example.com",
                "media_urls": []
            }
        }

        # 插入测试数据到news_results
        await self.db["news_results"].insert_one(self.test_news_result)

        yield

        # 测试后清理
        await self.cleanup()

    async def cleanup(self):
        """清理测试数据"""
        await self.db["news_results"].delete_many({"_id": {"$regex": "^test_"}})
        await self.db["user_edited_results"].delete_many({"user_id": self.test_user_id})
        await self.db["user_archives"].delete_many({"user_id": self.test_user_id})

    async def test_step1_get_rag_content(self):
        """步骤1: 测试获取RAG内容API"""
        # 模拟API调用：查询news_results
        result = await self.db["news_results"].find_one(
            {"_id": self.test_mongo_id},
            {
                "_id": 1,
                "url": 1,
                "markdown_content": 1,
                "title": 1,
                "source": 1
            }
        )

        # 验证返回数据
        assert result is not None
        assert result["_id"] == self.test_mongo_id
        assert result["url"] == "https://example.com/test-article"
        assert result["markdown_content"] == "# 测试文章\n\n这是测试内容..."
        assert result["title"] == "测试新闻标题"
        assert result["source"] == "example.com"

        print(f"✅ 步骤1通过: 成功获取RAG内容")

    async def test_step2_batch_edit_with_snapshot(self):
        """步骤2: 测试批量编辑（带快照）"""
        # 准备批量编辑数据
        edit_doc = {
            "news_result_id": self.test_mongo_id,
            "user_id": self.test_user_id,
            "snapshot": {
                "title": "测试新闻标题",
                "url": "https://example.com/test-article",
                "markdown_content": "# 测试文章\n\n这是测试内容...",
                "source": "example.com",
                "category": {
                    "大类": "科技",
                    "类别": "人工智能",
                    "地域": "美国"
                },
                "publish_time": "2025-11-22T10:00:00Z",
                "preview": "这是测试新闻的内容摘要"
            },
            "edited_title": "编辑后的标题",
            "edited_summary": "编辑后的摘要",
            "edited_category": {
                "大类": "科技",
                "类别": "AI技术",
                "地域": "全球"
            },
            "edited_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        # 保存到user_edited_results
        result = await self.db["user_edited_results"].update_one(
            {
                "news_result_id": self.test_mongo_id,
                "user_id": self.test_user_id
            },
            {"$set": edit_doc},
            upsert=True
        )

        # 验证保存成功
        assert result.matched_count > 0 or result.upserted_id is not None

        # 读取保存的记录
        saved = await self.db["user_edited_results"].find_one({
            "news_result_id": self.test_mongo_id,
            "user_id": self.test_user_id
        })

        # 验证快照完整性
        assert saved is not None
        assert "snapshot" in saved
        assert saved["snapshot"]["url"] == "https://example.com/test-article"
        assert saved["snapshot"]["markdown_content"] == "# 测试文章\n\n这是测试内容..."
        assert saved["edited_title"] == "编辑后的标题"

        print(f"✅ 步骤2通过: 成功保存批量编辑（带快照）")

    async def test_step3_create_archive_from_snapshot(self):
        """步骤3: 测试创建档案（从快照读取）"""
        # 先执行步骤2：保存批量编辑
        await self.test_step2_batch_edit_with_snapshot()

        # 创建档案（使用相同的user_id）
        archive_result = await mongo_archive_service.create_archive(
            user_id=self.test_user_id,
            archive_name="测试档案",
            items=[
                {
                    "news_result_id": self.test_mongo_id,
                    "edited_title": None,  # 应该从user_edited_results自动读取
                    "edited_summary": None
                }
            ],
            description="集成测试档案",
            tags=["测试"]
        )

        # 验证档案创建成功
        assert archive_result is not None
        assert "archive_id" in archive_result
        assert archive_result["items_count"] == 1

        archive_id = archive_result["archive_id"]

        # 获取档案详情
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=self.test_user_id
        )

        # 验证档案数据
        assert archive is not None
        assert len(archive["items"]) == 1

        item = archive["items"][0]

        # 验证显示标题（应该从user_edited_results读取）
        assert item["title"] == "编辑后的标题"
        assert item["content"] == "编辑后的摘要"

        # 🔥 关键验证：检查快照是否包含url和markdown_content
        # 需要直接从MongoDB读取原始快照数据
        raw_archive = await self.db["user_archives"].find_one({"_id": ObjectId(archive_id)})
        assert raw_archive is not None
        assert len(raw_archive["items"]) == 1

        raw_item = raw_archive["items"][0]
        snapshot = raw_item["snapshot_data"]

        # 验证快照包含完整数据
        assert "url" in snapshot
        assert snapshot["url"] == "https://example.com/test-article"
        assert "markdown_content" in snapshot
        assert snapshot["markdown_content"] == "# 测试文章\n\n这是测试内容..."

        print(f"✅ 步骤3通过: 成功创建档案（包含url和markdown_content）")

    async def test_complete_flow(self):
        """完整流程测试"""
        print("\n" + "="*60)
        print("🚀 开始RAG批量编辑完整流程测试")
        print("="*60 + "\n")

        # 步骤1: 获取RAG内容
        print("📋 步骤1: 获取RAG内容...")
        await self.test_step1_get_rag_content()

        # 步骤2: 批量编辑（保存快照）
        print("\n📝 步骤2: 批量编辑（保存快照）...")
        await self.test_step2_batch_edit_with_snapshot()

        # 步骤3: 创建档案（从快照读取）
        print("\n📦 步骤3: 创建档案（从快照读取）...")
        await self.test_step3_create_archive_from_snapshot()

        print("\n" + "="*60)
        print("✅ 完整流程测试通过！")
        print("="*60 + "\n")

    async def test_archive_fallback_to_news_results(self):
        """测试档案创建降级：未找到编辑记录时从news_results读取"""
        # 创建另一个测试记录（不保存到user_edited_results）
        test_mongo_id_2 = "test_mongo_id_002"
        await self.db["news_results"].insert_one({
            "_id": test_mongo_id_2,
            "url": "https://example.com/fallback-article",
            "markdown_content": "# 降级测试\n\n未编辑内容",
            "title": "降级测试标题",
            "source": "example.com",
            "news_results": {
                "title": "降级测试标题",
                "content": "降级测试内容",
                "category": {"大类": "科技", "类别": "AI", "地域": "中国"},
                "published_at": datetime.utcnow(),
                "source": "example.com",
                "media_urls": []
            }
        })

        # 创建档案（应该从news_results读取）
        archive_result = await mongo_archive_service.create_archive(
            user_id=1001,
            archive_name="降级测试档案",
            items=[
                {
                    "news_result_id": test_mongo_id_2,
                    "edited_title": "API传入的标题",
                    "edited_summary": "API传入的摘要"
                }
            ],
            description="测试降级逻辑",
            tags=["降级"]
        )

        # 验证档案创建成功
        assert archive_result is not None
        archive_id = archive_result["archive_id"]

        # 获取档案详情
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=self.test_user_id
        )

        # 验证档案数据
        assert archive is not None
        assert len(archive["items"]) == 1

        item = archive["items"][0]

        # 验证使用API传入的编辑内容
        assert item["title"] == "API传入的标题"
        assert item["content"] == "API传入的摘要"

        # 验证快照是从news_results创建的
        raw_archive = await self.db["user_archives"].find_one({"_id": ObjectId(archive_id)})
        raw_item = raw_archive["items"][0]
        snapshot = raw_item["snapshot_data"]

        # news_results创建的快照不包含url和markdown_content（因为在news_results字段中）
        # 这个测试验证降级逻辑正常工作
        assert snapshot["original_title"] == "降级测试标题"

        print(f"✅ 降级测试通过: 未找到编辑记录时成功从news_results读取")

        # 清理
        await self.db["news_results"].delete_one({"_id": test_mongo_id_2})


@pytest.mark.asyncio
async def test_performance_field_projection():
    """性能测试：字段投影优化"""
    db = await get_mongodb_database()

    # 创建测试数据
    test_id = "perf_test_001"
    large_content = "测试内容" * 1000  # 模拟大内容

    await db["news_results"].insert_one({
        "_id": test_id,
        "url": "https://example.com/perf",
        "markdown_content": large_content,
        "title": "性能测试",
        "source": "example.com",
        "news_results": {
            "title": "性能测试",
            "content": large_content,
            "category": {"大类": "科技", "类别": "AI", "地域": "中国"},
            "published_at": datetime.utcnow(),
            "source": "example.com",
            "media_urls": []
        },
        "other_large_field": "其他大字段" * 1000
    })

    # 测试完整查询（无投影）
    import time

    start = time.time()
    full_result = await db["news_results"].find_one({"_id": test_id})
    full_time = time.time() - start

    # 测试字段投影查询
    start = time.time()
    projected_result = await db["news_results"].find_one(
        {"_id": test_id},
        {
            "_id": 1,
            "url": 1,
            "markdown_content": 1,
            "title": 1,
            "source": 1
        }
    )
    projected_time = time.time() - start

    # 验证结果正确性
    assert projected_result["_id"] == test_id
    assert projected_result["url"] == "https://example.com/perf"
    assert projected_result["title"] == "性能测试"

    # 验证投影查询不包含未请求的字段
    assert "other_large_field" not in projected_result

    print(f"\n性能对比:")
    print(f"  完整查询: {full_time*1000:.2f}ms")
    print(f"  投影查询: {projected_time*1000:.2f}ms")
    print(f"  性能提升: {(full_time/projected_time):.2f}x")

    # 清理
    await db["news_results"].delete_one({"_id": test_id})


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
