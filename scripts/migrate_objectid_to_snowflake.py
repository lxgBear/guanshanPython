"""
ObjectId 迁移到雪花算法ID 脚本

将以下集合的 _id 从 ObjectId 格式迁移到雪花算法ID（字符串格式）：
- category_system: 生成新雪花ID
- data_sources: 使用现有 id 字段值
- file_uploads: 使用现有 file_id 字段值
- firecrawl_raw_responses: 使用现有 id 字段值

使用方法:
    python scripts/migrate_objectid_to_snowflake.py --mongo-uri "mongodb://..." [--dry-run]

参数:
    --mongo-uri: MongoDB连接字符串
    --dry-run: 仅预览，不实际执行迁移
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# 雪花ID生成器
from src.infrastructure.id_generator import generate_string_id


async def migrate_collection(
    db,
    collection_name: str,
    id_field: str = None,
    dry_run: bool = True
):
    """
    迁移单个集合

    Args:
        db: MongoDB数据库实例
        collection_name: 集合名称
        id_field: 用作新 _id 的字段名（如果为 None，则生成新雪花ID）
        dry_run: 是否为预览模式
    """
    collection = db[collection_name]

    # 查找所有使用 ObjectId 的文档
    cursor = collection.find({"_id": {"$type": "objectId"}})
    docs = await cursor.to_list(length=None)

    if not docs:
        print(f"  ✅ {collection_name}: 无需迁移（没有 ObjectId 格式的 _id）")
        return 0

    print(f"  📋 {collection_name}: 发现 {len(docs)} 条需要迁移的记录")

    migrated = 0
    for doc in docs:
        old_id = doc["_id"]

        # 确定新 _id
        if id_field and id_field in doc:
            new_id = str(doc[id_field])
        else:
            new_id = generate_string_id()

        if dry_run:
            print(f"    [预览] {old_id} -> {new_id}")
        else:
            # 创建新文档（使用新 _id）
            new_doc = dict(doc)
            new_doc["_id"] = new_id

            # 保留旧 ObjectId 作为 legacy_object_id（可选，便于追溯）
            new_doc["_legacy_object_id"] = str(old_id)

            try:
                # 插入新文档
                await collection.insert_one(new_doc)
                # 删除旧文档
                await collection.delete_one({"_id": old_id})
                migrated += 1
                print(f"    ✅ {old_id} -> {new_id}")
            except Exception as e:
                print(f"    ❌ 迁移失败 {old_id}: {e}")

    return migrated


async def main(mongo_uri: str, dry_run: bool = True):
    """主函数"""
    print("=" * 60)
    print("ObjectId 迁移到雪花算法ID")
    print("=" * 60)
    print(f"模式: {'预览模式 (--dry-run)' if dry_run else '实际执行'}")
    print(f"连接: {mongo_uri[:50]}...")
    print()

    # 连接数据库
    client = AsyncIOMotorClient(mongo_uri)
    db = client["guanshan"]

    # 迁移配置
    migrations = [
        {
            "collection": "category_system",
            "id_field": None,  # 生成新雪花ID
            "description": "分类系统配置"
        },
        {
            "collection": "data_sources",
            "id_field": "id",  # 使用现有 id 字段
            "description": "数据源"
        },
        {
            "collection": "file_uploads",
            "id_field": "file_id",  # 使用现有 file_id 字段
            "description": "文件上传"
        },
        {
            "collection": "firecrawl_raw_responses",
            "id_field": "id",  # 使用现有 id 字段
            "description": "Firecrawl原始响应"
        }
    ]

    total_migrated = 0

    for config in migrations:
        print(f"\n[{config['description']}] {config['collection']}")
        count = await migrate_collection(
            db,
            config["collection"],
            config["id_field"],
            dry_run
        )
        total_migrated += count

    print()
    print("=" * 60)
    if dry_run:
        print(f"预览完成: 共 {total_migrated} 条记录将被迁移")
        print("运行时去掉 --dry-run 参数以实际执行迁移")
    else:
        print(f"迁移完成: 共 {total_migrated} 条记录已迁移")
    print("=" * 60)

    # 验证迁移结果
    if not dry_run:
        print("\n验证迁移结果:")
        for config in migrations:
            collection = db[config["collection"]]
            objectid_count = await collection.count_documents({"_id": {"$type": "objectId"}})
            total_count = await collection.count_documents({})
            status = "✅" if objectid_count == 0 else "⚠️"
            print(f"  {status} {config['collection']}: {total_count} 条记录, {objectid_count} 条仍为 ObjectId")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ObjectId 迁移到雪花算法ID")
    parser.add_argument(
        "--mongo-uri",
        required=True,
        help="MongoDB 连接字符串"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不实际执行迁移"
    )

    args = parser.parse_args()

    asyncio.run(main(args.mongo_uri, args.dry_run))
