#!/usr/bin/env python3
"""
数据库迁移脚本：为 instant_search_results 添加 search_type 字段

v2.1.0 即时+智能搜索统一架构迁移 - Phase 1

目标：
1. 为所有现有 instant_search_results 记录添加 search_type="instant"
2. 创建复合索引 (search_type, task_id, created_at)
3. 验证迁移结果

执行方式：
    python scripts/migrations/add_search_type_to_instant_results.py --execute

安全检查：
    python scripts/migrations/add_search_type_to_instant_results.py --dry-run
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_existing_search_type_field():
    """检查是否已存在 search_type 字段"""
    try:
        db = await get_mongodb_database()
        collection = db["instant_search_results"]

        # 检查是否有记录已经有 search_type 字段
        sample = await collection.find_one({"search_type": {"$exists": True}})

        if sample:
            logger.warning("⚠️ 检测到已有记录包含 search_type 字段，可能已经执行过迁移")
            return True

        logger.info("✅ 未检测到 search_type 字段，可以安全执行迁移")
        return False

    except Exception as e:
        logger.error(f"❌ 检查 search_type 字段失败: {e}")
        raise


async def get_migration_stats():
    """获取迁移前的统计信息"""
    try:
        db = await get_mongodb_database()
        collection = db["instant_search_results"]

        # 总记录数
        total_count = await collection.count_documents({})

        # 已有 search_type 的记录数
        with_search_type = await collection.count_documents({"search_type": {"$exists": True}})

        # 需要迁移的记录数
        needs_migration = total_count - with_search_type

        stats = {
            "total_count": total_count,
            "with_search_type": with_search_type,
            "needs_migration": needs_migration
        }

        logger.info(f"""
📊 迁移前统计:
   - 总记录数: {total_count}
   - 已有 search_type: {with_search_type}
   - 需要迁移: {needs_migration}
        """)

        return stats

    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {e}")
        raise


async def add_search_type_field_batch(batch_size: int = 1000, dry_run: bool = False):
    """批量添加 search_type 字段"""
    try:
        db = await get_mongodb_database()
        collection = db["instant_search_results"]

        # 查找所有没有 search_type 字段的记录
        query = {"search_type": {"$exists": False}}

        total_updated = 0
        batch_count = 0

        while True:
            # 分批获取需要更新的记录ID
            cursor = collection.find(query, {"_id": 1}).limit(batch_size)
            ids = [doc["_id"] async for doc in cursor]

            if not ids:
                break  # 没有更多记录需要更新

            batch_count += 1

            if dry_run:
                logger.info(f"🔍 [DRY-RUN] Batch {batch_count}: 将更新 {len(ids)} 条记录")
                total_updated += len(ids)
            else:
                # 批量更新
                result = await collection.update_many(
                    {"_id": {"$in": ids}},
                    {"$set": {"search_type": "instant"}}
                )

                total_updated += result.modified_count
                logger.info(f"✅ Batch {batch_count}: 成功更新 {result.modified_count} 条记录")

            # 如果本批次记录少于 batch_size，说明已经是最后一批
            if len(ids) < batch_size:
                break

        logger.info(f"{'🔍 [DRY-RUN]' if dry_run else '✅'} 总计更新: {total_updated} 条记录")
        return total_updated

    except Exception as e:
        logger.error(f"❌ 添加 search_type 字段失败: {e}")
        raise


async def create_search_type_index(dry_run: bool = False):
    """创建 search_type 复合索引"""
    try:
        db = await get_mongodb_database()
        collection = db["instant_search_results"]

        # 索引名称
        index_name = "idx_search_type_task_created"

        # 检查索引是否已存在
        existing_indexes = await collection.index_information()

        if index_name in existing_indexes:
            logger.warning(f"⚠️ 索引 {index_name} 已存在，跳过创建")
            return

        if dry_run:
            logger.info(f"🔍 [DRY-RUN] 将创建索引: {index_name} on (search_type, task_id, created_at)")
        else:
            # 创建复合索引：search_type + task_id + created_at（降序）
            await collection.create_index(
                [
                    ("search_type", 1),
                    ("task_id", 1),
                    ("created_at", -1)
                ],
                name=index_name,
                background=True  # 后台创建，不阻塞数据库操作
            )
            logger.info(f"✅ 成功创建索引: {index_name}")

    except Exception as e:
        logger.error(f"❌ 创建索引失败: {e}")
        raise


async def verify_migration():
    """验证迁移结果"""
    try:
        db = await get_mongodb_database()
        collection = db["instant_search_results"]

        # 总记录数
        total_count = await collection.count_documents({})

        # 有 search_type="instant" 的记录数
        instant_count = await collection.count_documents({"search_type": "instant"})

        # 没有 search_type 字段的记录数
        missing_count = await collection.count_documents({"search_type": {"$exists": False}})

        # 检查索引
        indexes = await collection.index_information()
        index_exists = "idx_search_type_task_created" in indexes

        logger.info(f"""
🔍 迁移验证结果:
   - 总记录数: {total_count}
   - search_type="instant": {instant_count}
   - 缺少 search_type: {missing_count}
   - 索引已创建: {'✅' if index_exists else '❌'}
        """)

        if missing_count > 0:
            logger.error(f"❌ 验证失败: 还有 {missing_count} 条记录缺少 search_type 字段")
            return False

        if not index_exists:
            logger.error("❌ 验证失败: 索引未创建")
            return False

        logger.info("✅ 迁移验证通过！")
        return True

    except Exception as e:
        logger.error(f"❌ 验证迁移结果失败: {e}")
        raise


async def run_migration(dry_run: bool = False, batch_size: int = 1000):
    """执行完整迁移流程"""
    try:
        logger.info("=" * 60)
        logger.info(f"开始迁移: 为 instant_search_results 添加 search_type 字段")
        logger.info(f"模式: {'DRY-RUN (不会实际修改数据)' if dry_run else 'EXECUTE (将实际修改数据)'}")
        logger.info(f"批处理大小: {batch_size}")
        logger.info("=" * 60)

        # Step 1: 检查是否已迁移
        logger.info("\n📋 Step 1: 检查现有状态...")
        already_migrated = await check_existing_search_type_field()

        # Step 2: 获取统计信息
        logger.info("\n📋 Step 2: 获取统计信息...")
        stats = await get_migration_stats()

        if stats["needs_migration"] == 0:
            logger.info("✅ 所有记录已有 search_type 字段，无需迁移")
            if not dry_run:
                # 即使记录已迁移，也要确保索引存在
                logger.info("\n📋 确保索引存在...")
                await create_search_type_index(dry_run=False)
            return

        # Step 3: 添加 search_type 字段
        logger.info(f"\n📋 Step 3: 批量添加 search_type 字段 (batch_size={batch_size})...")
        updated_count = await add_search_type_field_batch(batch_size=batch_size, dry_run=dry_run)

        # Step 4: 创建索引
        logger.info("\n📋 Step 4: 创建复合索引...")
        await create_search_type_index(dry_run=dry_run)

        # Step 5: 验证（仅在非 dry-run 模式下）
        if not dry_run:
            logger.info("\n📋 Step 5: 验证迁移结果...")
            success = await verify_migration()

            if success:
                logger.info("\n" + "=" * 60)
                logger.info("✅ 迁移成功完成！")
                logger.info("=" * 60)
            else:
                logger.error("\n" + "=" * 60)
                logger.error("❌ 迁移验证失败，请检查错误信息")
                logger.error("=" * 60)
                sys.exit(1)
        else:
            logger.info("\n" + "=" * 60)
            logger.info("🔍 DRY-RUN 完成，未实际修改数据")
            logger.info("执行实际迁移请运行: python scripts/migrations/add_search_type_to_instant_results.py --execute")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ 迁移失败: {e}")
        sys.exit(1)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="为 instant_search_results 添加 search_type 字段 (v2.1.0 Phase 1)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行实际迁移（默认为 dry-run 模式）"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="批处理大小（默认1000条）"
    )

    args = parser.parse_args()

    dry_run = not args.execute

    await run_migration(dry_run=dry_run, batch_size=args.batch_size)


if __name__ == "__main__":
    asyncio.run(main())
