"""修复 news_results 集合中错误的 status 字段值

问题: status 字段被错误地存储为标题字符串,而不是有效的 ProcessedStatus 枚举值
解决: 将所有无效的 status 值重置为 'pending'
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 有效的 ProcessedStatus 枚举值
VALID_STATUSES = ['pending', 'processing', 'completed', 'failed', 'archived', 'deleted']


async def fix_corrupted_status():
    """修复损坏的 status 字段"""

    # 连接数据库
    client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
    db = client.guanshan
    collection = db.news_results

    print("🔍 检查损坏的 status 字段...")

    # 查找所有 status 不在有效值范围内的文档
    cursor = collection.find({
        'status': {'$nin': VALID_STATUSES}
    })

    corrupted_docs = []
    async for doc in cursor:
        corrupted_docs.append(doc)

    if not corrupted_docs:
        print("✅ 未发现损坏的 status 字段")
        return

    print(f"⚠️  发现 {len(corrupted_docs)} 条损坏的记录:")
    for doc in corrupted_docs[:5]:  # 只显示前5条
        doc_id = doc.get('_id')
        current_status = doc.get('status')
        title = doc.get('title', 'N/A')[:50]
        print(f"  - ID: {doc_id}")
        print(f"    当前status: {current_status}")
        print(f"    标题: {title}")
        print()

    # 修复
    print(f"🔧 开始修复 {len(corrupted_docs)} 条记录...")

    result = await collection.update_many(
        {'status': {'$nin': VALID_STATUSES}},
        {'$set': {'status': 'pending'}}
    )

    print(f"✅ 修复完成!")
    print(f"   匹配文档数: {result.matched_count}")
    print(f"   修改文档数: {result.modified_count}")

    # 验证修复结果
    print("\n🔍 验证修复结果...")
    remaining = await collection.count_documents({
        'status': {'$nin': VALID_STATUSES}
    })

    if remaining == 0:
        print("✅ 所有记录已成功修复!")
    else:
        print(f"⚠️  仍有 {remaining} 条记录未修复")

    client.close()


if __name__ == "__main__":
    asyncio.run(fix_corrupted_status())
