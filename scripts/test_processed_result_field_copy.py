#!/usr/bin/env python3
"""
v2.0.1 原始字段复制测试脚本

测试内容：
1. 验证 create_pending_result() 复制原始字段
2. 验证 bulk_create_pending_results() 批量复制原始字段
3. 验证所有字段都被正确复制
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.infrastructure.database.repositories import SearchResultRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_single_field_copy():
    """测试 1: 验证单个记录原始字段复制"""
    print("\n" + "="*60)
    print("测试 1: 验证 create_pending_result() 复制原始字段")
    print("="*60)

    try:
        # 1. 创建测试用的原始搜索结果
        print("\n📝 步骤 1: 创建测试原始搜索结果...")
        search_result = SearchResult(
            task_id="test_task_v201",
            title="测试标题 - v2.0.1 Field Copy Test",
            url="https://test.example.com/v201",
            source_url="https://test.example.com",
            content="这是测试内容，用于验证字段复制功能。" * 10,
            snippet="这是测试摘要",
            markdown_content="# 测试 Markdown\n\n这是测试内容。",
            html_content="<html><body><h1>测试</h1></body></html>",
            author="测试作者",
            language="zh",
            source="test",
            metadata={"test_key": "test_value"},
            quality_score=0.85,
            relevance_score=0.92,
            search_position=1,
            status=ResultStatus.PENDING
        )

        # 保存到 search_results
        search_repo = SearchResultRepository()
        await search_repo.save_results([search_result])
        print(f"✅ 创建原始搜索结果: {search_result.id}")

        # 2. 使用 ProcessedResultRepository 创建待处理记录
        print("\n📝 步骤 2: 使用 create_pending_result() 创建待处理记录...")
        processed_repo = ProcessedResultRepository()
        processed_result = await processed_repo.create_pending_result(
            raw_result_id=str(search_result.id),
            task_id="test_task_v201"
        )
        print(f"✅ 创建待处理记录: {processed_result.id}")

        # 3. 验证字段是否被复制
        print("\n📝 步骤 3: 验证原始字段是否被正确复制...")

        # 检查基础字段
        assert processed_result.title == search_result.title, "标题未复制"
        assert processed_result.url == search_result.url, "URL未复制"
        assert processed_result.content == search_result.content, "内容未复制"
        assert processed_result.snippet == search_result.snippet, "摘要未复制"

        # 检查可选字段
        assert processed_result.markdown_content == search_result.markdown_content, "Markdown未复制"
        assert processed_result.html_content == search_result.html_content, "HTML未复制"
        assert processed_result.author == search_result.author, "作者未复制"
        assert processed_result.language == search_result.language, "语言未复制"

        # 检查元数据
        assert processed_result.metadata == search_result.metadata, "元数据未复制"
        assert processed_result.quality_score == search_result.quality_score, "质量分数未复制"
        assert processed_result.relevance_score == search_result.relevance_score, "相关性分数未复制"
        assert processed_result.search_position == search_result.search_position, "搜索位置未复制"

        print("✅ 所有原始字段验证通过！")
        print(f"  - 标题: {processed_result.title}")
        print(f"  - URL: {processed_result.url}")
        print(f"  - 内容长度: {len(processed_result.content)} 字符")
        print(f"  - 作者: {processed_result.author}")
        print(f"  - 质量分数: {processed_result.quality_score}")

        # 4. 清理测试数据
        db = await get_mongodb_database()
        await db['search_results'].delete_one({"_id": search_result.id})
        await db['processed_results'].delete_one({"_id": processed_result.id})
        print("\n🗑️ 清理测试数据完成")

        print("\n✅ 测试 1 通过: create_pending_result() 原始字段复制正常")
        return True

    except AssertionError as e:
        print(f"\n❌ 测试 1 失败: 字段验证失败 - {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_bulk_field_copy():
    """测试 2: 验证批量记录原始字段复制"""
    print("\n" + "="*60)
    print("测试 2: 验证 bulk_create_pending_results() 批量复制原始字段")
    print("="*60)

    try:
        # 1. 创建多个测试用的原始搜索结果
        print("\n📝 步骤 1: 创建 3 个测试原始搜索结果...")
        search_results = []
        for i in range(3):
            search_result = SearchResult(
                task_id="test_task_bulk_v201",
                title=f"批量测试标题 {i+1} - v2.0.1",
                url=f"https://test.example.com/bulk/{i+1}",
                content=f"批量测试内容 {i+1}" * 10,
                snippet=f"批量测试摘要 {i+1}",
                author=f"测试作者 {i+1}",
                quality_score=0.8 + i * 0.05,
                relevance_score=0.9 + i * 0.02,
                search_position=i + 1
            )
            search_results.append(search_result)

        # 保存到 search_results
        search_repo = SearchResultRepository()
        await search_repo.save_results(search_results)
        print(f"✅ 创建 {len(search_results)} 个原始搜索结果")

        # 2. 使用批量创建
        print("\n📝 步骤 2: 使用 bulk_create_pending_results() 批量创建待处理记录...")
        processed_repo = ProcessedResultRepository()
        raw_result_ids = [str(r.id) for r in search_results]
        processed_results = await processed_repo.bulk_create_pending_results(
            raw_result_ids=raw_result_ids,
            task_id="test_task_bulk_v201"
        )
        print(f"✅ 批量创建 {len(processed_results)} 个待处理记录")

        # 3. 验证每个记录的字段
        print("\n📝 步骤 3: 验证每个记录的原始字段...")
        for i, processed_result in enumerate(processed_results):
            original = search_results[i]

            assert processed_result.title == original.title, f"记录{i+1}标题未复制"
            assert processed_result.url == original.url, f"记录{i+1}URL未复制"
            assert processed_result.content == original.content, f"记录{i+1}内容未复制"
            assert processed_result.author == original.author, f"记录{i+1}作者未复制"
            assert processed_result.quality_score == original.quality_score, f"记录{i+1}质量分数未复制"

            print(f"  ✅ 记录 {i+1}: {processed_result.title} - 所有字段验证通过")

        # 4. 清理测试数据
        db = await get_mongodb_database()
        await db['search_results'].delete_many({
            "_id": {"$in": [r.id for r in search_results]}
        })
        await db['processed_results'].delete_many({
            "_id": {"$in": [r.id for r in processed_results]}
        })
        print("\n🗑️ 清理测试数据完成")

        print("\n✅ 测试 2 通过: bulk_create_pending_results() 批量复制正常")
        return True

    except AssertionError as e:
        print(f"\n❌ 测试 2 失败: 字段验证失败 - {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_missing_original_data():
    """测试 3: 验证找不到原始数据时的容错处理"""
    print("\n" + "="*60)
    print("测试 3: 验证找不到原始数据时的容错处理")
    print("="*60)

    try:
        print("\n📝 步骤 1: 使用不存在的 raw_result_id 创建待处理记录...")
        processed_repo = ProcessedResultRepository()

        # 使用一个不存在的ID
        fake_id = "fake_result_id_12345"
        processed_result = await processed_repo.create_pending_result(
            raw_result_id=fake_id,
            task_id="test_task_missing"
        )

        print(f"✅ 创建待处理记录成功: {processed_result.id}")

        # 验证创建了最小记录
        print("\n📝 步骤 2: 验证创建了最小记录...")
        assert processed_result.raw_result_id == fake_id, "raw_result_id不匹配"
        assert processed_result.task_id == "test_task_missing", "task_id不匹配"
        assert processed_result.title == "", "标题应为空"
        assert processed_result.content == "", "内容应为空"

        print("✅ 最小记录验证通过")
        print(f"  - raw_result_id: {processed_result.raw_result_id}")
        print(f"  - task_id: {processed_result.task_id}")
        print(f"  - 原始字段为空（符合预期）")

        # 清理测试数据
        db = await get_mongodb_database()
        await db['processed_results'].delete_one({"_id": processed_result.id})
        print("\n🗑️ 清理测试数据完成")

        print("\n✅ 测试 3 通过: 容错处理正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("v2.0.1 原始字段复制功能测试")
    print("="*60)
    print(f"测试时间: {datetime.now().isoformat()}")

    # 运行所有测试
    test_results = []

    test_results.append(await test_single_field_copy())
    test_results.append(await test_bulk_field_copy())
    test_results.append(await test_missing_original_data())

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(test_results)
    total = len(test_results)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！v2.0.1 原始字段复制功能正常")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
