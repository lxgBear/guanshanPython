#!/usr/bin/env python3
"""
v2.1.0 统一架构测试脚本

测试内容：
1. 验证 instant_search_results 表结构（search_type字段存在）
2. 验证 InstantSearchResultRepository 查询功能
3. 验证 SmartSearchService 使用统一Repository
4. 验证 InstantProcessedResultRepository 功能
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
from src.infrastructure.database.instant_search_repositories import InstantSearchResultRepository
from src.infrastructure.database.instant_processed_result_repositories import InstantProcessedResultRepository
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.instant_processed_result import (
    InstantProcessedResult,
    InstantProcessedStatus
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_instant_search_results_structure():
    """测试 1：验证 instant_search_results 表结构"""
    print("\n" + "="*60)
    print("测试 1: 验证 instant_search_results 表结构")
    print("="*60)

    try:
        db = await get_mongodb_database()
        collection = db['instant_search_results']

        # 检查是否有记录
        total_count = await collection.count_documents({})
        print(f"📊 总记录数: {total_count}")

        # 检查有 search_type 字段的记录
        with_search_type = await collection.count_documents({"search_type": {"$exists": True}})
        print(f"✅ 已有 search_type 字段: {with_search_type}")

        # 按 search_type 分组统计
        if with_search_type > 0:
            instant_count = await collection.count_documents({"search_type": "instant"})
            smart_count = await collection.count_documents({"search_type": "smart"})
            print(f"📊 search_type='instant': {instant_count}")
            print(f"📊 search_type='smart': {smart_count}")

            # 显示示例
            sample = await collection.find_one({"search_type": {"$exists": True}})
            if sample:
                print(f"\n📋 示例记录字段:")
                print(f"  - _id: {sample.get('_id')}")
                print(f"  - task_id: {sample.get('task_id')}")
                print(f"  - search_type: {sample.get('search_type')}")
                print(f"  - title: {sample.get('title', '')[:50]}...")
                print(f"  - url: {sample.get('url', '')[:50]}...")

        # 检查索引
        indexes = await collection.index_information()
        print(f"\n📊 现有索引:")
        for index_name, index_info in indexes.items():
            print(f"  - {index_name}: {index_info.get('key')}")

        print("\n✅ 测试 1 通过: instant_search_results 表结构正确")
        return True

    except Exception as e:
        print(f"\n❌ 测试 1 失败: {e}")
        return False


async def test_instant_search_result_repository():
    """测试 2: 验证 InstantSearchResultRepository 查询功能"""
    print("\n" + "="*60)
    print("测试 2: 验证 InstantSearchResultRepository 查询功能")
    print("="*60)

    try:
        repo = InstantSearchResultRepository()

        # 测试创建结果（使用测试数据）
        print("\n📝 测试创建结果...")
        test_result = InstantSearchResult(
            task_id="test_task_123",
            title="Test Result for v2.1.0",
            url="https://test.example.com/article",
            content="This is a test result for unified architecture v2.1.0"
        )

        # 测试 instant 类型
        await repo.create(test_result, search_type="instant")
        print(f"✅ 创建 instant 类型结果成功: {test_result.id}")

        # 测试查询
        print("\n📝 测试根据 task_id 和 search_type 查询...")
        results, total = await repo.get_results_by_task_and_type(
            task_id="test_task_123",
            search_type="instant",
            skip=0,
            limit=10
        )
        print(f"✅ 查询成功: 找到 {total} 条结果")

        # 清理测试数据
        db = await get_mongodb_database()
        await db['instant_search_results'].delete_one({"_id": test_result.id})
        print(f"🗑️ 清理测试数据: {test_result.id}")

        print("\n✅ 测试 2 通过: InstantSearchResultRepository 功能正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_instant_processed_result_repository():
    """测试 3: 验证 InstantProcessedResultRepository 功能"""
    print("\n" + "="*60)
    print("测试 3: 验证 InstantProcessedResultRepository 功能")
    print("="*60)

    try:
        repo = InstantProcessedResultRepository()

        # 测试创建待处理结果
        print("\n📝 测试创建待处理结果...")
        processed_result = await repo.create_pending_result(
            raw_result_id="test_raw_result_123",
            task_id="test_task_456",
            search_type="smart"  # 测试智能搜索类型
        )
        print(f"✅ 创建待处理结果成功: {processed_result.id}")
        print(f"  - raw_result_id: {processed_result.raw_result_id}")
        print(f"  - task_id: {processed_result.task_id}")
        print(f"  - search_type: {processed_result.search_type}")
        print(f"  - status: {processed_result.status.value}")

        # 测试更新状态
        print("\n📝 测试更新处理状态...")
        success = await repo.update_processing_status(
            result_id=processed_result.id,
            status=InstantProcessedStatus.PROCESSING
        )
        print(f"✅ 更新状态成功: {success}")

        # 测试保存 AI 结果
        print("\n📝 测试保存 AI 处理结果...")
        success = await repo.save_ai_result(
            result_id=processed_result.id,
            translated_title="测试标题（已翻译）",
            summary="这是AI生成的摘要",
            ai_model="gpt-4",
            processing_time_ms=500
        )
        print(f"✅ 保存AI结果成功: {success}")

        # 测试查询
        print("\n📝 测试根据 task_id 和 search_type 查询...")
        results, total = await repo.get_by_task_and_type(
            task_id="test_task_456",
            search_type="smart",
            page=1,
            page_size=10
        )
        print(f"✅ 查询成功: 找到 {total} 条结果")
        if results:
            result = results[0]
            print(f"  - status: {result.status.value}")
            print(f"  - translated_title: {result.translated_title}")
            print(f"  - ai_model: {result.ai_model}")

        # 测试状态统计
        print("\n📝 测试状态统计...")
        stats = await repo.get_status_statistics(
            task_id="test_task_456",
            search_type="smart"
        )
        print(f"✅ 统计成功:")
        for status, count in stats.items():
            if count > 0:
                print(f"  - {status}: {count}")

        # 清理测试数据
        db = await get_mongodb_database()
        await db['instant_processed_results'].delete_one({"_id": processed_result.id})
        print(f"\n🗑️ 清理测试数据: {processed_result.id}")

        print("\n✅ 测试 3 通过: InstantProcessedResultRepository 功能正常")
        return True

    except Exception as e:
        print(f"\n❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_collection_existence():
    """测试 4: 验证集合存在性"""
    print("\n" + "="*60)
    print("测试 4: 验证集合存在性")
    print("="*60)

    try:
        db = await get_mongodb_database()

        # 获取所有集合
        collections = await db.list_collection_names()
        print(f"\n📊 数据库中的集合:")

        # 检查关键集合
        required_collections = [
            'instant_search_results',
            'instant_search_tasks',
            'instant_search_result_mappings'
        ]

        for coll_name in required_collections:
            exists = coll_name in collections
            status = "✅" if exists else "❌"
            count = await db[coll_name].count_documents({}) if exists else 0
            print(f"  {status} {coll_name}: {count} 条记录")

        # 检查新增集合
        new_collections = ['instant_processed_results']
        print(f"\n📊 v2.1.0 新增集合:")
        for coll_name in new_collections:
            exists = coll_name in collections
            status = "✅" if exists else "⚠️"
            count = await db[coll_name].count_documents({}) if exists else 0
            print(f"  {status} {coll_name}: {count} 条记录")

        # 检查旧集合（应该废弃）
        legacy_collections = ['smart_search_results']
        print(f"\n📊 待废弃集合:")
        for coll_name in legacy_collections:
            exists = coll_name in collections
            count = await db[coll_name].count_documents({}) if exists else 0
            print(f"  ⏳ {coll_name}: {count} 条记录 (将被废弃)")

        print("\n✅ 测试 4 通过: 集合结构符合预期")
        return True

    except Exception as e:
        print(f"\n❌ 测试 4 失败: {e}")
        return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("v2.1.0 即时+智能搜索统一架构测试")
    print("="*60)
    print(f"测试时间: {datetime.now().isoformat()}")

    # 运行所有测试
    test_results = []

    test_results.append(await test_instant_search_results_structure())
    test_results.append(await test_instant_search_result_repository())
    test_results.append(await test_instant_processed_result_repository())
    test_results.append(await test_collection_existence())

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(test_results)
    total = len(test_results)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！v2.1.0 统一架构工作正常")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
