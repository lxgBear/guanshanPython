#!/usr/bin/env python3
"""
清理旧的 processed_results 集合

当前情况:
- processed_results_new 已经存在并且有数据（代码已指向新集合）
- processed_results 旧集合还在，但代码已不再使用
- 需要删除旧集合以避免混淆

功能:
1. 验证代码已指向 processed_results_new
2. 备份旧集合统计信息
3. 删除旧集合 processed_results
4. 为新集合创建必要的索引

安全保障:
- 删除前二次确认
- 显示详细的集合信息
- 提供数据备份建议

作者: Claude Code
日期: 2025-11-04
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def get_collection_info(db, collection_name: str) -> dict:
    """获取集合详细信息"""
    try:
        stats = await db.command("collStats", collection_name)

        # 获取索引信息
        collection = db[collection_name]
        indexes = await collection.index_information()

        return {
            "exists": True,
            "count": stats.get("count", 0),
            "size": stats.get("size", 0),
            "storage_size": stats.get("storageSize", 0),
            "indexes": list(indexes.keys()),
            "index_count": len(indexes)
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


async def verify_code_points_to_new_collection():
    """验证代码是否已指向新集合"""
    print("\n📝 验证代码配置...")

    # 读取 Repository 文件检查集合名
    repo_file = project_root / "src/infrastructure/database/processed_result_repositories.py"

    if not repo_file.exists():
        print("❌ 无法找到 Repository 文件")
        return False

    content = repo_file.read_text()

    if 'self.collection_name = "processed_results_new"' in content:
        print("✅ 代码已正确指向 processed_results_new")
        return True
    elif 'self.collection_name = "processed_results"' in content:
        print("❌ 代码仍指向旧集合 processed_results")
        print("ℹ️  请先运行代码修改，将集合名改为 processed_results_new")
        return False
    else:
        print("⚠️ 无法确认集合名配置")
        return False


async def backup_collection_stats(db, collection_name: str):
    """备份集合统计信息"""
    print(f"\n📝 备份 {collection_name} 统计信息...")

    info = await get_collection_info(db, collection_name)

    if not info.get("exists"):
        print(f"⚠️ 集合 {collection_name} 不存在")
        return

    # 保存到文件
    backup_file = project_root / f"claudedocs/backup_{collection_name}_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    backup_data = {
        "collection_name": collection_name,
        "backup_time": datetime.now().isoformat(),
        "stats": info
    }

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    print(f"✅ 统计信息已保存: {backup_file}")
    print(f"  - 记录数: {info['count']}")
    print(f"  - 数据大小: {info['size'] / 1024:.2f} KB")
    print(f"  - 索引: {', '.join(info['indexes'])}")


async def create_indexes_for_new_collection(db):
    """为新集合创建必要的索引"""
    print("\n📝 为 processed_results_new 创建索引...")

    collection = db['processed_results_new']

    # 获取现有索引
    existing_indexes = await collection.index_information()
    existing_index_names = set(existing_indexes.keys())

    print(f"现有索引: {', '.join(existing_index_names)}")

    # 定义需要的索引
    indexes_to_create = [
        {
            "name": "task_id_index",
            "keys": [("task_id", 1)],
            "description": "任务ID索引（查询某任务的所有结果）"
        },
        {
            "name": "status_index",
            "keys": [("status", 1)],
            "description": "状态索引（筛选不同状态的结果）"
        },
        {
            "name": "task_id_status_index",
            "keys": [("task_id", 1), ("status", 1)],
            "description": "任务ID+状态复合索引（常用组合查询）"
        },
        {
            "name": "created_at_index",
            "keys": [("created_at", -1)],
            "description": "创建时间索引（时间排序，降序）"
        }
    ]

    created_count = 0
    skipped_count = 0

    for index_config in indexes_to_create:
        index_name = index_config["name"]

        if index_name in existing_index_names:
            print(f"  ⏭️  跳过已存在的索引: {index_name}")
            skipped_count += 1
            continue

        try:
            await collection.create_index(
                index_config["keys"],
                name=index_name
            )
            print(f"  ✅ 创建索引: {index_name}")
            print(f"     说明: {index_config['description']}")
            created_count += 1
        except Exception as e:
            print(f"  ❌ 创建索引失败: {index_name} - {e}")

    print(f"\n📊 索引创建总结:")
    print(f"  ✅ 新创建: {created_count} 个")
    print(f"  ⏭️  跳过: {skipped_count} 个")


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("清理旧的 processed_results 集合")
    print("="*60)
    print(f"执行时间: {datetime.now().isoformat()}\n")

    try:
        # 步骤 1: 验证代码配置
        if not await verify_code_points_to_new_collection():
            print("\n❌ 代码配置验证失败，停止清理操作")
            return 1

        # 步骤 2: 连接数据库
        print("\n📝 连接数据库...")
        db = await get_mongodb_database()
        print("✅ 数据库连接成功\n")

        # 步骤 3: 检查集合状态
        print("📝 检查集合状态...")
        old_info = await get_collection_info(db, "processed_results")
        new_info = await get_collection_info(db, "processed_results_new")

        if not old_info.get("exists"):
            print("ℹ️  旧集合 processed_results 不存在，无需清理")

            # 但仍需检查新集合的索引
            if new_info.get("exists"):
                print(f"\n✅ processed_results_new 存在:")
                print(f"  - 记录数: {new_info['count']}")
                print(f"  - 索引数: {new_info['index_count']}")

                if new_info['index_count'] < 5:
                    print("\n⚠️  索引数量不足，需要创建索引")
                    await create_indexes_for_new_collection(db)

            return 0

        if not new_info.get("exists"):
            print("❌ 新集合 processed_results_new 不存在！")
            print("ℹ️  请先确保新集合已创建并有数据")
            return 1

        # 显示集合对比
        print("\n📊 集合对比:")
        print(f"\n旧集合 (processed_results):")
        print(f"  - 记录数: {old_info['count']}")
        print(f"  - 数据大小: {old_info['size'] / 1024:.2f} KB")
        print(f"  - 索引数: {old_info['index_count']}")
        print(f"  - 索引: {', '.join(old_info['indexes'])}")

        print(f"\n新集合 (processed_results_new):")
        print(f"  - 记录数: {new_info['count']}")
        print(f"  - 数据大小: {new_info['size'] / 1024:.2f} KB")
        print(f"  - 索引数: {new_info['index_count']}")
        print(f"  - 索引: {', '.join(new_info['indexes'])}")

        # 数据一致性检查
        if old_info['count'] != new_info['count']:
            print(f"\n⚠️ 警告: 两个集合的记录数不一致!")
            print(f"  旧集合: {old_info['count']} 条")
            print(f"  新集合: {new_info['count']} 条")
            print(f"\n建议先检查数据一致性，再继续删除操作")

            confirm = input("\n是否仍要继续删除旧集合? (yes/no): ").strip().lower()
            if confirm != "yes":
                print("\n⏹️  取消删除操作")
                return 0

        # 步骤 4: 备份统计信息
        await backup_collection_stats(db, "processed_results")

        # 步骤 5: 确认删除
        print("\n" + "="*60)
        print("⚠️  即将删除旧集合 processed_results")
        print("="*60)
        print(f"将删除 {old_info['count']} 条记录")
        print(f"数据大小: {old_info['size'] / 1024:.2f} KB")
        print("\n⚠️ 此操作不可逆！")
        print("建议:")
        print("  1. 确保已有数据备份")
        print("  2. 确保服务已停止或代码已指向新集合")
        print("  3. 统计信息已保存到 claudedocs/ 目录")

        confirm = input("\n确认删除旧集合? 请输入集合名 'processed_results' 以确认: ").strip()

        if confirm != "processed_results":
            print("\n⏹️  取消删除操作")
            return 0

        # 步骤 6: 删除旧集合
        print("\n📝 删除旧集合...")
        await db.drop_collection("processed_results")
        print("✅ 旧集合已删除")

        # 步骤 7: 验证删除
        print("\n📝 验证删除结果...")
        verify_info = await get_collection_info(db, "processed_results")

        if verify_info.get("exists"):
            print("❌ 验证失败: 旧集合仍然存在")
            return 1

        print("✅ 确认旧集合已删除")

        # 步骤 8: 为新集合创建索引
        if new_info['index_count'] < 5:
            await create_indexes_for_new_collection(db)
        else:
            print("\n✅ 新集合索引已完整，无需创建")

        # 总结
        print("\n" + "="*60)
        print("🎉 清理完成!")
        print("="*60)
        print(f"✅ 已删除旧集合: processed_results ({old_info['count']} 条记录)")
        print(f"✅ 当前使用集合: processed_results_new ({new_info['count']} 条记录)")
        print(f"✅ 统计信息已备份到 claudedocs/ 目录")
        print(f"\nℹ️  现在可以重启服务进行测试\n")

        return 0

    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
