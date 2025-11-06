"""
分析 MongoDB 重复键错误

检查 instant_search_result_mappings 表的索引和重复数据
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_duplicate_key_issue():
    """分析重复键问题"""

    print(f"\n{'='*80}")
    print(f"MongoDB 重复键问题分析")
    print(f"{'='*80}\n")

    try:
        db = await get_mongodb_database()
        mappings_collection = db['instant_search_result_mappings']

        # 1. 检查索引结构
        print(f"{'='*80}")
        print(f"1. 索引结构")
        print(f"{'='*80}\n")

        indexes = await mappings_collection.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"索引名: {idx.get('name')}")
            print(f"  键: {idx.get('key')}")
            print(f"  唯一: {idx.get('unique', False)}")
            print(f"  详细: {idx}")
            print()

        # 2. 查询是否有重复的 (search_execution_id, result_id) 组合
        print(f"{'='*80}")
        print(f"2. 重复键检查")
        print(f"{'='*80}\n")

        pipeline = [
            {
                "$group": {
                    "_id": {
                        "search_execution_id": "$search_execution_id",
                        "result_id": "$result_id"
                    },
                    "count": {"$sum": 1},
                    "ids": {"$push": "$_id"}
                }
            },
            {
                "$match": {
                    "count": {"$gt": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": 10
            }
        ]

        duplicates = await mappings_collection.aggregate(pipeline).to_list(length=None)

        if duplicates:
            print(f"发现 {len(duplicates)} 组重复键:\n")
            for dup in duplicates:
                print(f"search_execution_id: {dup['_id']['search_execution_id']}")
                print(f"result_id: {dup['_id']['result_id']}")
                print(f"重复次数: {dup['count']}")
                print(f"记录IDs: {dup['ids'][:5]}...")  # 只显示前5个
                print()
        else:
            print("✅ 未发现重复键\n")

        # 3. 统计信息
        print(f"{'='*80}")
        print(f"3. 统计信息")
        print(f"{'='*80}\n")

        total_mappings = await mappings_collection.count_documents({})
        print(f"总映射记录数: {total_mappings}")

        # 按 search_execution_id 分组统计
        pipeline_stats = [
            {
                "$group": {
                    "_id": "$search_execution_id",
                    "count": {"$sum": 1},
                    "unique_results": {"$addToSet": "$result_id"}
                }
            },
            {
                "$project": {
                    "count": 1,
                    "unique_results_count": {"$size": "$unique_results"}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": 5
            }
        ]

        stats = await mappings_collection.aggregate(pipeline_stats).to_list(length=None)

        print(f"\n最近5次搜索执行的映射统计:")
        for stat in stats:
            print(f"  search_execution_id: {stat['_id']}")
            print(f"    映射记录数: {stat['count']}")
            print(f"    唯一结果数: {stat['unique_results_count']}")
            if stat['count'] != stat['unique_results_count']:
                print(f"    ⚠️ 警告: 映射数 != 唯一结果数 (可能有重复)")
            print()

        # 4. 检查最近的错误案例
        print(f"{'='*80}")
        print(f"4. 检查测试中失败的 search_execution_id")
        print(f"{'='*80}\n")

        # 从错误日志中提取的 search_execution_id
        error_exec_id = "exec_244678791495421953"
        error_result_id = "244667936543330305"

        print(f"错误案例: search_execution_id={error_exec_id}, result_id={error_result_id}\n")

        # 查询这个组合是否已存在
        existing = await mappings_collection.find({
            "search_execution_id": error_exec_id,
            "result_id": error_result_id
        }).to_list(length=None)

        if existing:
            print(f"❌ 发现 {len(existing)} 条已存在的映射记录:\n")
            for record in existing:
                print(f"  _id: {record['_id']}")
                print(f"  task_id: {record.get('task_id')}")
                print(f"  search_position: {record.get('search_position')}")
                print(f"  created_at: {record.get('created_at')}")
                print()
        else:
            print(f"✅ 未找到已存在的映射记录（这组合应该可以插入）\n")

        # 5. 分析批量插入的逻辑问题
        print(f"{'='*80}")
        print(f"5. 批量插入逻辑分析")
        print(f"{'='*80}\n")

        print("问题可能原因:")
        print("1. 去重逻辑: 同一个 result_id 被多次发现，但映射表的唯一索引阻止重复")
        print("2. 批量插入: insert_many() 遇到重复键会失败，导致后续记录也无法插入")
        print("3. 事务问题: 没有使用 ordered=False 参数，一个失败导致整批失败\n")

        print("建议修复方案:")
        print("1. 使用 insert_many(ordered=False) 允许部分插入成功")
        print("2. 捕获重复键异常，只记录警告而不抛出错误")
        print("3. 批量插入前先过滤掉已存在的映射")
        print()

    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await analyze_duplicate_key_issue()


if __name__ == "__main__":
    asyncio.run(main())
