#!/usr/bin/env python3
"""
v4.28.0 数据迁移脚本：补充历史数据的 task_name 字段

功能说明：
1. 为 search_results 表补充 task_name（从 search_tasks.name 获取）
2. 为 langgraph_search_results 表补充 task_name（从 chat_conversations.name 获取）

使用方法：
    python scripts/migrate_backfill_task_name.py [--dry-run]

参数：
    --dry-run   只统计需要迁移的记录数，不执行实际迁移
"""

import asyncio
import sys
from typing import Dict, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, "/Users/lanxionggao/Documents/guanshanPython")

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def get_task_name_mapping(db: AsyncIOMotorDatabase, collection_name: str, id_field: str = "_id", name_field: str = "name") -> Dict[str, str]:
    """获取 ID 到名称的映射

    Args:
        db: 数据库连接
        collection_name: 集合名称
        id_field: ID 字段名
        name_field: 名称字段名

    Returns:
        ID 到名称的映射字典
    """
    mapping = {}
    collection = db[collection_name]

    async for doc in collection.find({name_field: {"$exists": True, "$ne": None}}, {id_field: 1, name_field: 1}):
        doc_id = str(doc.get(id_field, ""))
        name = doc.get(name_field)
        if doc_id and name:
            mapping[doc_id] = name

    logger.info(f"从 {collection_name} 获取了 {len(mapping)} 条名称映射")
    return mapping


async def migrate_search_results(db: AsyncIOMotorDatabase, dry_run: bool = False) -> Dict[str, int]:
    """迁移 search_results 表的 task_name

    Args:
        db: 数据库连接
        dry_run: 是否只统计不执行

    Returns:
        迁移统计信息
    """
    logger.info("=" * 60)
    logger.info("开始迁移 search_results 表...")

    collection = db["search_results"]

    # 1. 统计需要迁移的记录
    need_migrate_count = await collection.count_documents({
        "$or": [
            {"task_name": {"$exists": False}},
            {"task_name": None}
        ]
    })

    total_count = await collection.count_documents({})
    already_has_count = total_count - need_migrate_count

    logger.info(f"search_results 总记录数: {total_count}")
    logger.info(f"已有 task_name 的记录: {already_has_count}")
    logger.info(f"需要迁移的记录: {need_migrate_count}")

    if dry_run:
        return {
            "total": total_count,
            "need_migrate": need_migrate_count,
            "already_has": already_has_count,
            "migrated": 0,
            "failed": 0
        }

    if need_migrate_count == 0:
        logger.info("无需迁移")
        return {
            "total": total_count,
            "need_migrate": 0,
            "already_has": already_has_count,
            "migrated": 0,
            "failed": 0
        }

    # 2. 获取 search_tasks 的名称映射
    task_name_mapping = await get_task_name_mapping(db, "search_tasks")

    # 3. 批量更新
    migrated = 0
    failed = 0
    not_found = 0
    batch_size = 100

    cursor = collection.find({
        "$or": [
            {"task_name": {"$exists": False}},
            {"task_name": None}
        ]
    }, {"_id": 1, "task_id": 1})

    batch = []
    async for doc in cursor:
        doc_id = doc.get("_id")
        task_id = str(doc.get("task_id", ""))

        task_name = task_name_mapping.get(task_id)

        if task_name:
            batch.append({
                "filter": {"_id": doc_id},
                "update": {"$set": {"task_name": task_name}}
            })
        else:
            not_found += 1

        if len(batch) >= batch_size:
            try:
                from pymongo import UpdateOne
                operations = [UpdateOne(item["filter"], item["update"]) for item in batch]
                result = await collection.bulk_write(operations)
                migrated += result.modified_count
            except Exception as e:
                logger.error(f"批量更新失败: {e}")
                failed += len(batch)
            batch = []

    # 处理剩余批次
    if batch:
        try:
            from pymongo import UpdateOne
            operations = [UpdateOne(item["filter"], item["update"]) for item in batch]
            result = await collection.bulk_write(operations)
            migrated += result.modified_count
        except Exception as e:
            logger.error(f"批量更新失败: {e}")
            failed += len(batch)

    logger.info(f"search_results 迁移完成: 成功 {migrated}, 失败 {failed}, 未找到任务名 {not_found}")

    return {
        "total": total_count,
        "need_migrate": need_migrate_count,
        "already_has": already_has_count,
        "migrated": migrated,
        "failed": failed,
        "not_found": not_found
    }


async def migrate_langgraph_results(db: AsyncIOMotorDatabase, dry_run: bool = False) -> Dict[str, int]:
    """迁移 langgraph_search_results 表的 task_name

    Args:
        db: 数据库连接
        dry_run: 是否只统计不执行

    Returns:
        迁移统计信息
    """
    logger.info("=" * 60)
    logger.info("开始迁移 langgraph_search_results 表...")

    collection = db["langgraph_search_results"]

    # 1. 统计需要迁移的记录
    need_migrate_count = await collection.count_documents({
        "$or": [
            {"task_name": {"$exists": False}},
            {"task_name": None}
        ]
    })

    total_count = await collection.count_documents({})
    already_has_count = total_count - need_migrate_count

    logger.info(f"langgraph_search_results 总记录数: {total_count}")
    logger.info(f"已有 task_name 的记录: {already_has_count}")
    logger.info(f"需要迁移的记录: {need_migrate_count}")

    if dry_run:
        return {
            "total": total_count,
            "need_migrate": need_migrate_count,
            "already_has": already_has_count,
            "migrated": 0,
            "failed": 0
        }

    if need_migrate_count == 0:
        logger.info("无需迁移")
        return {
            "total": total_count,
            "need_migrate": 0,
            "already_has": already_has_count,
            "migrated": 0,
            "failed": 0
        }

    # 2. 获取 chat_conversations 的名称映射（使用 title 字段）
    conversation_name_mapping = await get_task_name_mapping(db, "chat_conversations", name_field="title")

    # 3. 批量更新
    migrated = 0
    failed = 0
    not_found = 0
    batch_size = 100

    cursor = collection.find({
        "$or": [
            {"task_name": {"$exists": False}},
            {"task_name": None}
        ]
    }, {"_id": 1, "conversation_id": 1})

    batch = []
    async for doc in cursor:
        doc_id = doc.get("_id")
        conversation_id = str(doc.get("conversation_id", ""))

        task_name = conversation_name_mapping.get(conversation_id)

        if task_name:
            batch.append({
                "filter": {"_id": doc_id},
                "update": {"$set": {"task_name": task_name}}
            })
        else:
            not_found += 1

        if len(batch) >= batch_size:
            try:
                from pymongo import UpdateOne
                operations = [UpdateOne(item["filter"], item["update"]) for item in batch]
                result = await collection.bulk_write(operations)
                migrated += result.modified_count
            except Exception as e:
                logger.error(f"批量更新失败: {e}")
                failed += len(batch)
            batch = []

    # 处理剩余批次
    if batch:
        try:
            from pymongo import UpdateOne
            operations = [UpdateOne(item["filter"], item["update"]) for item in batch]
            result = await collection.bulk_write(operations)
            migrated += result.modified_count
        except Exception as e:
            logger.error(f"批量更新失败: {e}")
            failed += len(batch)

    logger.info(f"langgraph_search_results 迁移完成: 成功 {migrated}, 失败 {failed}, 未找到任务名 {not_found}")

    return {
        "total": total_count,
        "need_migrate": need_migrate_count,
        "already_has": already_has_count,
        "migrated": migrated,
        "failed": failed,
        "not_found": not_found
    }


async def main():
    """主函数"""
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN 模式 - 只统计不执行实际迁移")
        logger.info("=" * 60)

    db = await get_mongodb_database()

    # 迁移 search_results
    search_stats = await migrate_search_results(db, dry_run)

    # 迁移 langgraph_search_results
    langgraph_stats = await migrate_langgraph_results(db, dry_run)

    # 汇总统计
    logger.info("=" * 60)
    logger.info("迁移完成汇总:")
    logger.info("-" * 60)
    logger.info(f"search_results:")
    logger.info(f"  总记录数: {search_stats['total']}")
    logger.info(f"  需要迁移: {search_stats['need_migrate']}")
    logger.info(f"  已迁移: {search_stats.get('migrated', 0)}")
    logger.info(f"  失败: {search_stats.get('failed', 0)}")
    logger.info(f"  未找到任务名: {search_stats.get('not_found', 0)}")
    logger.info("-" * 60)
    logger.info(f"langgraph_search_results:")
    logger.info(f"  总记录数: {langgraph_stats['total']}")
    logger.info(f"  需要迁移: {langgraph_stats['need_migrate']}")
    logger.info(f"  已迁移: {langgraph_stats.get('migrated', 0)}")
    logger.info(f"  失败: {langgraph_stats.get('failed', 0)}")
    logger.info(f"  未找到任务名: {langgraph_stats.get('not_found', 0)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
