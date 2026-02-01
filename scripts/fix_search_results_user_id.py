#!/usr/bin/env python3
"""
修复 search_results 集合中缺少 user_id 字段的数据

问题描述：
    - search_results 集合中的数据没有 user_id 字段
    - 导致 unified-results API 按用户查询时返回空结果

修复策略：
    1. 通过 task_id 关联 search_tasks 获取 created_by
    2. 将 created_by 设置为 search_results 的 user_id

使用方法：
    python scripts/fix_search_results_user_id.py

v4.32.0 - 2026-01-31
"""

import asyncio
import sys
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def fix_search_results_user_id():
    """修复 search_results 集合中缺少 user_id 的数据"""

    # 从环境变量获取 MongoDB 连接配置
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://admin:jC5xXnjzbEepwChs@192.168.0.3:47017/guanshan?authSource=admin")
    db_name = os.getenv("MONGODB_DB_NAME", "guanshan")

    print(f"📡 连接 MongoDB: {mongodb_url.split('@')[1] if '@' in mongodb_url else mongodb_url}")

    # 连接 MongoDB
    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]

    print("=" * 60)
    print("修复 search_results 集合中缺少 user_id 的数据")
    print("=" * 60)

    # 1. 统计需要修复的记录数
    search_results = db.search_results
    search_tasks = db.search_tasks

    # 查找没有 user_id 或 user_id 为空的记录
    missing_user_id_count = await search_results.count_documents({
        "$or": [
            {"user_id": {"$exists": False}},
            {"user_id": ""},
            {"user_id": None}
        ]
    })

    print(f"\n📊 需要修复的记录数: {missing_user_id_count}")

    if missing_user_id_count == 0:
        print("✅ 没有需要修复的记录")
        return

    # 2. 获取所有任务的 created_by 映射
    print("\n📋 正在获取任务创建者映射...")
    task_user_map = {}
    async for task in search_tasks.find({}, {"_id": 1, "created_by": 1}):
        task_id = str(task.get("_id", ""))
        created_by = task.get("created_by", "")
        if task_id and created_by:
            task_user_map[task_id] = created_by

    print(f"   找到 {len(task_user_map)} 个任务的用户映射")

    # 3. 批量更新记录
    print("\n🔧 开始修复数据...")

    fixed_count = 0
    skipped_count = 0
    batch_size = 100

    cursor = search_results.find({
        "$or": [
            {"user_id": {"$exists": False}},
            {"user_id": ""},
            {"user_id": None}
        ]
    })

    batch = []
    async for doc in cursor:
        task_id = str(doc.get("task_id", ""))
        user_id = task_user_map.get(task_id, "")

        if user_id:
            batch.append({
                "filter": {"_id": doc["_id"]},
                "update": {
                    "$set": {
                        "user_id": user_id,
                        "created_by": user_id,
                        "data_source_type": "scheduled_crawl"
                    }
                }
            })

            if len(batch) >= batch_size:
                # 执行批量更新
                for item in batch:
                    await search_results.update_one(item["filter"], item["update"])
                fixed_count += len(batch)
                print(f"   已修复 {fixed_count} 条记录...")
                batch = []
        else:
            skipped_count += 1

    # 处理剩余的批次
    if batch:
        for item in batch:
            await search_results.update_one(item["filter"], item["update"])
        fixed_count += len(batch)

    print(f"\n✅ 修复完成!")
    print(f"   - 已修复: {fixed_count} 条")
    print(f"   - 跳过(无法关联任务): {skipped_count} 条")

    # 4. 验证修复结果
    print("\n📊 验证修复结果...")
    remaining = await search_results.count_documents({
        "$or": [
            {"user_id": {"$exists": False}},
            {"user_id": ""},
            {"user_id": None}
        ]
    })
    print(f"   剩余未修复记录: {remaining} 条")

    # 5. 统计各用户的记录数
    print("\n📊 各用户记录统计:")
    pipeline = [
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    async for stat in search_results.aggregate(pipeline):
        user_id = stat["_id"] or "(空)"
        count = stat["count"]
        print(f"   - {user_id}: {count} 条")

    client.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(fix_search_results_user_id())
