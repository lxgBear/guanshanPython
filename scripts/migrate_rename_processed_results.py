#!/usr/bin/env python3
"""
数据库迁移脚本: 重命名 processed_results → processed_results_new

功能:
1. 检查 processed_results 集合是否存在
2. 检查 processed_results_new 集合是否已存在（防止冲突）
3. 重命名集合（保留所有数据和索引）
4. 验证迁移成功
5. 提供回滚功能

安全保障:
- 使用 MongoDB 原生 rename 操作（原子性）
- 迁移前验证
- 迁移后验证
- 支持回滚

作者: Claude Code
日期: 2025-11-04
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


async def check_collection_exists(db, collection_name: str) -> bool:
    """检查集合是否存在"""
    collections = await db.list_collection_names()
    return collection_name in collections


async def get_collection_stats(db, collection_name: str) -> dict:
    """获取集合统计信息"""
    try:
        stats = await db.command("collStats", collection_name)
        return {
            "count": stats.get("count", 0),
            "size": stats.get("size", 0),
            "storage_size": stats.get("storageSize", 0),
            "indexes": stats.get("nindexes", 0)
        }
    except Exception as e:
        logger.error(f"获取集合统计失败: {e}")
        return {}


async def migrate_forward():
    """
    执行迁移: processed_results → processed_results_new
    """
    print("\n" + "="*60)
    print("数据库迁移: 重命名 processed_results → processed_results_new")
    print("="*60)
    print(f"执行时间: {datetime.now().isoformat()}\n")

    try:
        # 连接数据库
        db = await get_mongodb_database()
        print("✅ 已连接到数据库\n")

        # 步骤 1: 检查源集合是否存在
        print("📝 步骤 1: 检查源集合...")
        source_exists = await check_collection_exists(db, "processed_results")

        if not source_exists:
            print("❌ 源集合 'processed_results' 不存在，无需迁移")
            print("ℹ️  可能已经完成迁移，请检查 processed_results_new 是否存在")

            # 检查目标集合
            target_exists = await check_collection_exists(db, "processed_results_new")
            if target_exists:
                target_stats = await get_collection_stats(db, "processed_results_new")
                print(f"\n✅ processed_results_new 已存在:")
                print(f"  - 记录数: {target_stats.get('count', 0)}")
                print(f"  - 数据大小: {target_stats.get('size', 0) / 1024:.2f} KB")
                print(f"  - 索引数: {target_stats.get('indexes', 0)}")

            return 0

        # 获取源集合统计
        source_stats = await get_collection_stats(db, "processed_results")
        print(f"✅ 源集合 'processed_results' 存在:")
        print(f"  - 记录数: {source_stats.get('count', 0)}")
        print(f"  - 数据大小: {source_stats.get('size', 0) / 1024:.2f} KB")
        print(f"  - 索引数: {source_stats.get('indexes', 0)}\n")

        # 步骤 2: 检查目标集合是否已存在
        print("📝 步骤 2: 检查目标集合...")
        target_exists = await check_collection_exists(db, "processed_results_new")

        if target_exists:
            print("⚠️ 目标集合 'processed_results_new' 已存在")
            print("\n请选择操作:")
            print("  1. 删除现有 processed_results_new 并重新迁移")
            print("  2. 放弃迁移（保留现有数据）")

            choice = input("\n请输入选择 (1/2): ").strip()

            if choice == "1":
                # 删除现有目标集合
                print("\n🗑️  删除现有 processed_results_new...")
                await db.drop_collection("processed_results_new")
                print("✅ 已删除现有集合\n")
            elif choice == "2":
                print("\n⏹️  放弃迁移，保留现有数据")
                return 0
            else:
                print("\n❌ 无效选择，退出迁移")
                return 1
        else:
            print("✅ 目标集合 'processed_results_new' 不存在，可以安全迁移\n")

        # 步骤 3: 执行重命名
        print("📝 步骤 3: 执行集合重命名...")
        print("⏳ 正在重命名 processed_results → processed_results_new...")

        # 使用 MongoDB 原生 rename 命令（原子操作）
        await db["processed_results"].rename("processed_results_new")

        print("✅ 集合重命名完成\n")

        # 步骤 4: 验证迁移
        print("📝 步骤 4: 验证迁移结果...")

        # 检查源集合是否已删除
        source_still_exists = await check_collection_exists(db, "processed_results")
        if source_still_exists:
            print("❌ 验证失败: 源集合 'processed_results' 仍然存在")
            return 1

        print("✅ 源集合 'processed_results' 已删除")

        # 检查目标集合是否已创建
        target_now_exists = await check_collection_exists(db, "processed_results_new")
        if not target_now_exists:
            print("❌ 验证失败: 目标集合 'processed_results_new' 不存在")
            return 1

        print("✅ 目标集合 'processed_results_new' 已创建")

        # 获取目标集合统计
        target_stats = await get_collection_stats(db, "processed_results_new")
        print(f"✅ 迁移后统计:")
        print(f"  - 记录数: {target_stats.get('count', 0)}")
        print(f"  - 数据大小: {target_stats.get('size', 0) / 1024:.2f} KB")
        print(f"  - 索引数: {target_stats.get('indexes', 0)}\n")

        # 验证数据完整性
        if source_stats.get("count") != target_stats.get("count"):
            print(f"⚠️ 警告: 记录数不匹配!")
            print(f"  源集合: {source_stats.get('count', 0)} 条")
            print(f"  目标集合: {target_stats.get('count', 0)} 条")
            print("  请手动检查数据完整性\n")
        else:
            print(f"✅ 数据完整性验证通过: {target_stats.get('count', 0)} 条记录\n")

        # 总结
        print("="*60)
        print("🎉 迁移成功完成!")
        print("="*60)
        print(f"✅ processed_results → processed_results_new")
        print(f"✅ 迁移记录数: {target_stats.get('count', 0)}")
        print(f"✅ 保留索引数: {target_stats.get('indexes', 0)}")
        print(f"\nℹ️  如需回滚，请运行:")
        print(f"   python scripts/migrate_rename_processed_results.py --rollback\n")

        return 0

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def migrate_rollback():
    """
    回滚迁移: processed_results_new → processed_results
    """
    print("\n" + "="*60)
    print("数据库回滚: 重命名 processed_results_new → processed_results")
    print("="*60)
    print(f"执行时间: {datetime.now().isoformat()}\n")

    try:
        # 连接数据库
        db = await get_mongodb_database()
        print("✅ 已连接到数据库\n")

        # 步骤 1: 检查源集合是否存在
        print("📝 步骤 1: 检查源集合...")
        source_exists = await check_collection_exists(db, "processed_results_new")

        if not source_exists:
            print("❌ 源集合 'processed_results_new' 不存在，无法回滚")
            return 1

        source_stats = await get_collection_stats(db, "processed_results_new")
        print(f"✅ 源集合 'processed_results_new' 存在:")
        print(f"  - 记录数: {source_stats.get('count', 0)}")
        print(f"  - 数据大小: {source_stats.get('size', 0) / 1024:.2f} KB")
        print(f"  - 索引数: {source_stats.get('indexes', 0)}\n")

        # 步骤 2: 检查目标集合是否已存在
        print("📝 步骤 2: 检查目标集合...")
        target_exists = await check_collection_exists(db, "processed_results")

        if target_exists:
            print("⚠️ 目标集合 'processed_results' 已存在")
            print("\n⚠️ 警告: 回滚将删除现有 'processed_results' 集合")
            print("请确认是否继续 (yes/no): ", end="")

            confirm = input().strip().lower()
            if confirm != "yes":
                print("\n⏹️  取消回滚")
                return 0

            # 删除现有目标集合
            print("\n🗑️  删除现有 processed_results...")
            await db.drop_collection("processed_results")
            print("✅ 已删除现有集合\n")
        else:
            print("✅ 目标集合 'processed_results' 不存在，可以安全回滚\n")

        # 步骤 3: 执行回滚
        print("📝 步骤 3: 执行回滚重命名...")
        print("⏳ 正在重命名 processed_results_new → processed_results...")

        await db["processed_results_new"].rename("processed_results")

        print("✅ 回滚完成\n")

        # 步骤 4: 验证回滚
        print("📝 步骤 4: 验证回滚结果...")

        # 检查源集合是否已删除
        source_still_exists = await check_collection_exists(db, "processed_results_new")
        if source_still_exists:
            print("❌ 验证失败: 源集合 'processed_results_new' 仍然存在")
            return 1

        print("✅ 源集合 'processed_results_new' 已删除")

        # 检查目标集合是否已创建
        target_now_exists = await check_collection_exists(db, "processed_results")
        if not target_now_exists:
            print("❌ 验证失败: 目标集合 'processed_results' 不存在")
            return 1

        print("✅ 目标集合 'processed_results' 已恢复")

        # 获取目标集合统计
        target_stats = await get_collection_stats(db, "processed_results")
        print(f"✅ 回滚后统计:")
        print(f"  - 记录数: {target_stats.get('count', 0)}")
        print(f"  - 数据大小: {target_stats.get('size', 0) / 1024:.2f} KB")
        print(f"  - 索引数: {target_stats.get('indexes', 0)}\n")

        # 总结
        print("="*60)
        print("🎉 回滚成功完成!")
        print("="*60)
        print(f"✅ processed_results_new → processed_results")
        print(f"✅ 恢复记录数: {target_stats.get('count', 0)}\n")

        return 0

    except Exception as e:
        print(f"\n❌ 回滚失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


def print_usage():
    """打印使用说明"""
    print("\n使用方法:")
    print("  python scripts/migrate_rename_processed_results.py           # 执行迁移")
    print("  python scripts/migrate_rename_processed_results.py --rollback # 回滚迁移\n")


async def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--rollback":
            return await migrate_rollback()
        elif sys.argv[1] in ["-h", "--help"]:
            print_usage()
            return 0
        else:
            print(f"❌ 未知参数: {sys.argv[1]}")
            print_usage()
            return 1
    else:
        return await migrate_forward()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
