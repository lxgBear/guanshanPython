#!/usr/bin/env python3
"""
清理 news_results 集合中 status 为 pending 的记录

功能:
1. 查询并统计 status="pending" 的记录数量
2. 提供 dry-run 模式安全预览
3. 删除待处理记录并验证结果
4. 记录详细的清理日志

使用场景:
- 清理长期未处理的 pending 记录
- 重置AI处理队列
- 释放数据库存储空间

安全保障:
- 默认 dry-run 模式（需要 --execute 才真正删除）
- 删除前显示详细统计信息
- 删除后验证结果
- 支持按时间范围过滤（可选）

用法:
    # 预览模式（不删除）
    python scripts/cleanup_pending_news_results.py

    # 执行删除
    python scripts/cleanup_pending_news_results.py --execute

    # 只删除7天前的 pending 记录
    python scripts/cleanup_pending_news_results.py --execute --days 7

作者: Claude Code
日期: 2025-11-18
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def get_pending_stats(db, days: int = None) -> dict:
    """获取 pending 记录统计信息

    Args:
        db: MongoDB 数据库实例
        days: 只统计 N 天前的记录（可选）

    Returns:
        统计信息字典
    """
    collection = db.news_results

    # 构建查询条件
    query = {"status": "pending"}

    # 可选：按时间过滤
    if days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query["created_at"] = {"$lt": cutoff_date}

    # 统计数量
    total_count = await collection.count_documents(query)

    # 获取样本数据（前5条）
    samples = []
    cursor = collection.find(query).limit(5)
    async for doc in cursor:
        samples.append({
            "id": str(doc.get("_id")),
            "task_id": doc.get("task_id", "N/A"),
            "title": doc.get("title", "N/A")[:50],
            "created_at": doc.get("created_at"),
            "url": doc.get("url", "N/A")[:60]
        })

    # 按任务分组统计
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$task_id",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]

    task_stats = []
    async for item in collection.aggregate(pipeline):
        task_stats.append({
            "task_id": item["_id"] or "unknown",
            "count": item["count"]
        })

    return {
        "total_count": total_count,
        "samples": samples,
        "task_stats": task_stats,
        "days_filter": days
    }


async def delete_pending_records(db, days: int = None, dry_run: bool = True) -> dict:
    """删除 pending 记录

    Args:
        db: MongoDB 数据库实例
        days: 只删除 N 天前的记录（可选）
        dry_run: 是否为预览模式

    Returns:
        删除结果字典
    """
    collection = db.news_results

    # 构建删除条件
    query = {"status": "pending"}

    if days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query["created_at"] = {"$lt": cutoff_date}

    if dry_run:
        # 预览模式：只统计不删除
        count = await collection.count_documents(query)
        return {
            "dry_run": True,
            "matched_count": count,
            "deleted_count": 0
        }
    else:
        # 执行删除
        result = await collection.delete_many(query)
        return {
            "dry_run": False,
            "matched_count": result.deleted_count,
            "deleted_count": result.deleted_count
        }


def print_stats(stats: dict):
    """打印统计信息"""
    print("\n" + "="*70)
    print("📊 Pending 记录统计")
    print("="*70)

    if stats["days_filter"]:
        print(f"⏰ 时间范围: {stats['days_filter']} 天前创建的记录")
    else:
        print(f"⏰ 时间范围: 所有时间")

    print(f"\n📈 总计: {stats['total_count']} 条 pending 记录\n")

    if stats["task_stats"]:
        print("📋 按任务分组统计 (Top 10):")
        for i, task_stat in enumerate(stats["task_stats"], 1):
            print(f"  {i}. Task ID: {task_stat['task_id'][:30]}")
            print(f"     数量: {task_stat['count']} 条")
        print()

    if stats["samples"]:
        print("🔍 样本数据 (前5条):")
        for i, sample in enumerate(stats["samples"], 1):
            print(f"\n  [{i}] ID: {sample['id']}")
            print(f"      Task: {sample['task_id'][:40]}")
            print(f"      Title: {sample['title']}")
            print(f"      URL: {sample['url']}")
            if sample['created_at']:
                print(f"      Created: {sample['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    print("="*70 + "\n")


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="清理 news_results 集合中 status 为 pending 的记录",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览模式（默认）
  python scripts/cleanup_pending_news_results.py

  # 执行删除
  python scripts/cleanup_pending_news_results.py --execute

  # 只删除7天前的记录
  python scripts/cleanup_pending_news_results.py --execute --days 7
        """
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行删除操作（默认为 dry-run 预览模式）"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="只处理 N 天前创建的记录（可选）"
    )

    args = parser.parse_args()

    # 打印标题
    print("\n" + "="*70)
    print("🗑️  清理 news_results Pending 记录")
    print("="*70)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not args.execute:
        print("模式: 🔍 DRY-RUN（预览模式，不会删除数据）")
        print("提示: 使用 --execute 参数执行实际删除")
    else:
        print("模式: ⚡ EXECUTE（将执行删除操作）")

    print()

    try:
        # 连接数据库
        print("📝 连接数据库...")
        db = await get_mongodb_database()
        print("✅ 数据库连接成功\n")

        # 获取统计信息
        print("📊 分析 pending 记录...")
        stats = await get_pending_stats(db, days=args.days)

        # 显示统计
        print_stats(stats)

        # 检查是否有数据需要清理
        if stats["total_count"] == 0:
            print("✅ 没有找到符合条件的 pending 记录")
            return 0

        # Dry-run 模式提示
        if not args.execute:
            print("💡 预览模式完成")
            print(f"   将删除 {stats['total_count']} 条记录")
            print(f"   使用 --execute 参数执行实际删除\n")
            return 0

        # 执行模式：确认删除
        print("⚠️  准备删除 pending 记录")
        print(f"   数量: {stats['total_count']} 条")
        if args.days:
            print(f"   范围: {args.days} 天前创建的记录")
        else:
            print(f"   范围: 所有 pending 记录")

        print("\n⚠️  此操作不可逆！")
        confirm = input("\n确认删除? (yes/no): ").strip().lower()

        if confirm != "yes":
            print("\n⏹️  取消删除操作")
            return 0

        # 执行删除
        print("\n🗑️  正在删除记录...")
        result = await delete_pending_records(db, days=args.days, dry_run=False)

        print(f"✅ 删除完成!")
        print(f"   删除记录数: {result['deleted_count']}")

        # 验证删除结果
        print("\n📝 验证删除结果...")
        verify_stats = await get_pending_stats(db, days=args.days)

        if verify_stats["total_count"] == 0:
            print("✅ 所有符合条件的 pending 记录已删除")
        else:
            print(f"⚠️  仍有 {verify_stats['total_count']} 条 pending 记录")
            print("   （可能是新创建的记录）")

        # 总结
        print("\n" + "="*70)
        print("🎉 清理完成!")
        print("="*70)
        print(f"✅ 已删除: {result['deleted_count']} 条 pending 记录")
        print(f"✅ 当前 pending 记录数: {verify_stats['total_count']}")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
