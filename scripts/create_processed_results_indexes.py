#!/usr/bin/env python3
"""
为 processed_results_new 集合创建性能优化索引

v2.0.1 索引策略：
1. task_id - 单字段索引（查询某任务的所有结果）
2. status - 单字段索引（筛选不同状态）
3. task_id + status - 复合索引（常用组合查询）
4. created_at - 单字段索引（时间排序）
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def create_indexes():
    """创建 processed_results_new 集合的性能索引"""
    print("\n" + "="*60)
    print("processed_results_new 集合索引创建")
    print("="*60)
    print(f"执行时间: {datetime.now().isoformat()}\n")

    try:
        db = await get_mongodb_database()
        collection = db['processed_results_new']

        # 检查现有索引
        print("📊 步骤 1: 检查现有索引...")
        existing_indexes = await collection.index_information()
        print(f"现有索引数量: {len(existing_indexes)}")
        for name, info in existing_indexes.items():
            print(f"  - {name}: {info.get('key')}")

        # 创建索引
        print("\n📝 步骤 2: 创建新索引...")

        indexes_to_create = [
            {
                "name": "task_id_index",
                "keys": [("task_id", 1)],
                "description": "任务ID索引（查询某任务的所有结果）"
            },
            {
                "name": "status_index",
                "keys": [("status", 1)],
                "description": "状态索引（筛选不同状态的结果）"
            },
            {
                "name": "task_id_status_index",
                "keys": [("task_id", 1), ("status", 1)],
                "description": "任务ID+状态复合索引（常用组合查询）"
            },
            {
                "name": "created_at_index",
                "keys": [("created_at", -1)],  # -1 表示降序（最新的在前）
                "description": "创建时间索引（时间排序，降序）"
            }
        ]

        created_count = 0
        skipped_count = 0

        for index_config in indexes_to_create:
            index_name = index_config["name"]

            # 检查索引是否已存在
            if index_name in existing_indexes:
                print(f"  ⏭️  跳过已存在的索引: {index_name}")
                skipped_count += 1
                continue

            # 创建索引
            try:
                await collection.create_index(
                    index_config["keys"],
                    name=index_name
                )
                print(f"  ✅ 创建索引: {index_name}")
                print(f"     字段: {index_config['keys']}")
                print(f"     说明: {index_config['description']}")
                created_count += 1
            except Exception as e:
                print(f"  ❌ 创建索引失败: {index_name} - {e}")

        # 验证索引
        print("\n📊 步骤 3: 验证索引创建结果...")
        final_indexes = await collection.index_information()
        print(f"最终索引数量: {len(final_indexes)}")
        for name, info in final_indexes.items():
            print(f"  - {name}: {info.get('key')}")

        # 总结
        print("\n" + "="*60)
        print("索引创建总结")
        print("="*60)
        print(f"✅ 新创建: {created_count} 个")
        print(f"⏭️  跳过: {skipped_count} 个")
        print(f"📊 总计: {len(final_indexes)} 个索引")

        # 性能建议
        print("\n💡 性能优化建议:")
        print("  1. 查询时使用索引字段: task_id, status, created_at")
        print("  2. 复合查询优先使用 task_id + status")
        print("  3. 排序查询使用 created_at 索引")
        print("  4. 定期监控索引使用情况")

        return 0

    except Exception as e:
        print(f"\n❌ 创建索引失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def verify_index_performance():
    """验证索引性能"""
    print("\n" + "="*60)
    print("索引性能验证")
    print("="*60)

    try:
        db = await get_mongodb_database()
        collection = db['processed_results_new']

        # 测试查询性能
        test_queries = [
            {
                "name": "按 task_id 查询",
                "query": {"task_id": {"$exists": True}},
                "limit": 10
            },
            {
                "name": "按 status 筛选",
                "query": {"status": "completed"},
                "limit": 10
            },
            {
                "name": "task_id + status 组合",
                "query": {"task_id": {"$exists": True}, "status": "completed"},
                "limit": 10
            },
            {
                "name": "按 created_at 排序",
                "query": {},
                "sort": [("created_at", -1)],
                "limit": 10
            }
        ]

        print("\n📊 查询性能测试:")
        for test in test_queries:
            start = datetime.now()

            cursor = collection.find(test["query"]).limit(test.get("limit", 10))
            if "sort" in test:
                cursor = cursor.sort(test["sort"])

            results = await cursor.to_list(length=test.get("limit", 10))

            elapsed = (datetime.now() - start).total_seconds() * 1000
            print(f"  {test['name']}: {elapsed:.2f}ms (返回 {len(results)} 条)")

        print("\n✅ 性能验证完成")
        return 0

    except Exception as e:
        print(f"\n❌ 性能验证失败: {e}")
        return 1


async def main():
    """主函数"""
    # 创建索引
    result = await create_indexes()

    if result == 0:
        # 验证性能
        await verify_index_performance()

    return result


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
