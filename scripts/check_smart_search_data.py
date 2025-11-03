#!/usr/bin/env python3
"""检查 smart_search_results 数据"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from src.infrastructure.database.connection import get_mongodb_database

async def check_collections():
    db = await get_mongodb_database()

    # 检查 smart_search_results
    smart_count = await db['smart_search_results'].count_documents({})
    print(f"📊 smart_search_results 记录数: {smart_count}")

    if smart_count > 0:
        sample = await db['smart_search_results'].find_one()
        print(f"📋 示例文档字段: {list(sample.keys())}")
        print(f"\n🔍 智能搜索特有字段:")
        for field in ['sub_query_index', 'original_query', 'decomposed_query', 'decomposition_reasoning', 'query_focus', 'relevance_to_original', 'aggregation_priority']:
            if field in sample:
                print(f"  - {field}: {sample[field]}")

    # 检查 instant_search_results
    instant_count = await db['instant_search_results'].count_documents({})
    print(f"\n📊 instant_search_results 记录数: {instant_count}")

    # 检查有 search_type 字段的记录
    with_type = await db['instant_search_results'].count_documents({"search_type": {"$exists": True}})
    print(f"📊 已有 search_type 字段: {with_type}")

if __name__ == "__main__":
    asyncio.run(check_collections())
