"""检查数据库中旧状态的数据量

v1.5.2 状态迁移前的数据统计
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB 连接配置
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB_NAME = "guanshan"


async def check_old_status():
    """统计旧状态数据量"""
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DB_NAME]

    collections = [
        "search_results",
        "instant_search_results",
        "smart_search_results"
    ]

    print("=" * 80)
    print("v1.5.2 状态迁移 - 旧状态数据统计")
    print("=" * 80)
    print()

    total_processing = 0
    total_completed = 0

    for collection_name in collections:
        collection = db[collection_name]

        # 统计 processing 状态
        processing_count = await collection.count_documents({"status": "processing"})

        # 统计 completed 状态
        completed_count = await collection.count_documents({"status": "completed"})

        # 统计总数
        total_count = await collection.count_documents({})

        print(f"集合: {collection_name}")
        print(f"  总记录数: {total_count}")
        print(f"  processing 状态: {processing_count}")
        print(f"  completed 状态: {completed_count}")

        if processing_count > 0 or completed_count > 0:
            print(f"  需要迁移: {processing_count + completed_count} 条")
        else:
            print(f"  无需迁移")
        print()

        total_processing += processing_count
        total_completed += completed_count

    print("=" * 80)
    print(f"总计需要迁移:")
    print(f"  processing → pending: {total_processing} 条")
    print(f"  completed → archived: {total_completed} 条")
    print(f"  合计: {total_processing + total_completed} 条")
    print("=" * 80)

    client.close()


if __name__ == "__main__":
    asyncio.run(check_old_status())
