"""数据迁移脚本：将 temp_ 格式的 task_id 迁移到雪花算法ID

目标:
1. 识别所有 task_id 以 'temp_' 开头的记录
2. 生成新的雪花算法ID替换
3. 保留迁移历史便于追溯和回滚
4. 提供详细的迁移报告

v1.5.0 数据迁移 - temp_ ID统一
"""

import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

import asyncio
from datetime import datetime
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

async def migrate_temp_task_ids():
    """迁移 temp_ 格式的 task_id 到雪花算法ID"""

    db = await get_mongodb_database()

    print("=" * 80)
    print("📦 数据迁移：temp_ ID → 雪花算法ID (v1.5.0)")
    print("=" * 80)

    # 1. 分析当前数据状态
    print("\n📊 【步骤1】分析当前数据...")

    # 统计 temp_ ID 数量
    temp_id_pattern = {"task_id": {"$regex": "^temp_"}}
    temp_count = await db.search_results.count_documents(temp_id_pattern)

    # 总记录数
    total_count = await db.search_results.count_documents({})

    print(f"  search_results 集合:")
    print(f"    总记录数: {total_count}")
    print(f"    temp_ ID记录: {temp_count}")
    print(f"    需迁移: {temp_count}")

    if temp_count == 0:
        print("\n✅ 所有记录已使用雪花算法ID，无需迁移")
        return

    # 抽样显示前5条 temp_ ID 记录
    print("\n  📋 抽样预览（前5条）:")
    sample_records = await db.search_results.find(
        temp_id_pattern,
        {"_id": 1, "task_id": 1, "title": 1}
    ).limit(5).to_list(length=5)

    for i, record in enumerate(sample_records, 1):
        task_id = record.get("task_id", "")
        title = record.get("title", "")[:40]
        print(f"    {i}. task_id: {task_id}")
        print(f"       title: {title}")
        print(f"       MongoDB _id: {record['_id']}")

    # 2. 确认迁移
    print("\n" + "=" * 80)
    print("⚠️  【步骤2】迁移确认")
    print(f"  将为 {temp_count} 条记录生成新的雪花算法ID")
    print("  此操作将:")
    print("    - 更新 task_id 字段为雪花算法ID")
    print("    - 在 migration_history 中保留原 temp_ ID")
    print("    - 支持通过 migration_history 回滚")
    print("=" * 80)

    # 自动确认（CLI环境自动执行）
    print("\n✅ 自动执行迁移...")
    proceed = True

    # 3. 执行迁移
    print("\n🔄 【步骤3】迁移 search_results 集合...")
    migrated = 0
    failed = 0
    batch_size = 100

    while True:
        # 每次从头查询 temp_ ID 记录（处理完一批后自动过滤）
        records = await db.search_results.find(
            temp_id_pattern,
            {"_id": 1, "task_id": 1}
        ).limit(batch_size).to_list(length=batch_size)

        if not records:
            break

        # 为每条记录生成并更新雪花ID
        for record in records:
            old_task_id = record["task_id"]

            try:
                # 生成新的雪花算法ID
                new_task_id = generate_string_id()

                # 更新记录
                result = await db.search_results.update_one(
                    {"_id": record["_id"]},
                    {
                        "$set": {"task_id": new_task_id},
                        "$push": {
                            "migration_history": {
                                "timestamp": datetime.now(),
                                "old_task_id": old_task_id,
                                "new_task_id": new_task_id,
                                "migration_type": "temp_to_snowflake",
                                "version": "v1.5.0",
                                "reason": "ID系统统一：temp_ UUID → 雪花算法"
                            }
                        }
                    }
                )

                if result.modified_count > 0:
                    migrated += 1
                    if migrated % 10 == 0:
                        print(f"    进度: {migrated}/{temp_count} ({migrated/temp_count*100:.1f}%)")
                else:
                    failed += 1
                    print(f"    ⚠️  更新失败（无修改）: MongoDB _id={record['_id']}")

            except Exception as e:
                failed += 1
                print(f"    ❌ 迁移失败: MongoDB _id={record['_id']}, 错误: {e}")

    print(f"  ✅ 迁移完成: 成功 {migrated}, 失败 {failed}")

    # 4. 验证迁移结果
    print("\n" + "=" * 80)
    print("✅ 【步骤4】验证迁移结果...")

    # 检查剩余 temp_ ID
    remaining_temp = await db.search_results.count_documents(temp_id_pattern)
    print(f"  剩余 temp_ ID: {remaining_temp}")

    # 检查迁移历史记录
    migrated_records_count = await db.search_results.count_documents({
        "migration_history": {
            "$elemMatch": {
                "migration_type": "temp_to_snowflake"
            }
        }
    })
    print(f"  带迁移历史的记录: {migrated_records_count}")

    # 5. 抽样验证（前5条迁移记录）
    print("\n📋 【步骤5】抽样验证（前5条迁移记录）...")

    migrated_samples = await db.search_results.find({
        "migration_history": {
            "$elemMatch": {
                "migration_type": "temp_to_snowflake"
            }
        }
    }).limit(5).to_list(length=5)

    for i, record in enumerate(migrated_samples, 1):
        task_id = record.get("task_id", "")
        title = record.get("title", "")[:30]
        migration_history = record.get("migration_history", [])

        # 获取最新的迁移记录
        latest_migration = migration_history[-1] if migration_history else {}
        old_task_id = latest_migration.get("old_task_id", "")

        # 验证新ID格式
        is_snowflake = task_id.isdigit() and len(task_id) > 10
        id_format = "✅ 雪花ID" if is_snowflake else "❌ 非雪花ID"

        print(f"    {i}. 新task_id: {task_id} ({id_format})")
        print(f"       原task_id: {old_task_id}")
        print(f"       标题: {title}")
        print(f"       迁移时间: {latest_migration.get('timestamp', 'N/A')}")

    # 6. 统计雪花ID格式
    print("\n📊 【步骤6】ID格式统计...")

    # 统计纯数字ID（雪花算法格式）
    snowflake_count = await db.search_results.count_documents({
        "task_id": {"$regex": "^[0-9]+$"}
    })

    # 统计非空ID
    non_empty_count = await db.search_results.count_documents({
        "task_id": {"$ne": "", "$exists": True}
    })

    snowflake_rate = (snowflake_count / non_empty_count * 100) if non_empty_count > 0 else 0

    print(f"  非空task_id总数: {non_empty_count}")
    print(f"  雪花算法ID: {snowflake_count} ({snowflake_rate:.1f}%)")
    print(f"  temp_ ID: {remaining_temp}")
    print(f"  其他格式: {non_empty_count - snowflake_count - remaining_temp}")

    # 7. 迁移报告
    print("\n" + "=" * 80)
    print("📊 【迁移报告】")
    print("=" * 80)
    print(f"  迁移前 temp_ ID: {temp_count}")
    print(f"  成功迁移: {migrated}")
    print(f"  失败: {failed}")
    print(f"  迁移后 temp_ ID: {remaining_temp}")
    print(f"  带迁移历史记录: {migrated_records_count}")

    success_rate = (migrated / temp_count * 100) if temp_count > 0 else 0
    print(f"\n  成功率: {success_rate:.1f}%")

    if failed == 0 and remaining_temp == 0:
        print("\n✅ 迁移完全成功！所有 temp_ ID 已转换为雪花算法ID")
    elif failed > 0:
        print(f"\n⚠️  迁移部分失败，请检查失败记录")
    else:
        print("\n✅ 迁移成功！")

    # 8. 回滚说明
    print("\n" + "=" * 80)
    print("🔄 【回滚说明】")
    print("=" * 80)
    print("  如需回滚，可执行以下 MongoDB 命令:")
    print()
    print("  // 单条回滚示例")
    print("  db.search_results.updateOne(")
    print("    {_id: ObjectId('...')},")
    print("    {")
    print("      $set: {")
    print("        task_id: '$arrayElemAt: [\"$migration_history.old_task_id\", -1]'")
    print("      },")
    print("      $pop: {migration_history: 1}")
    print("    }")
    print("  );")
    print()
    print("  或使用脚本批量回滚 (见文档 TASK_ID_UNIFICATION_ANALYSIS.md)")

async def verify_migration():
    """验证迁移结果（独立验证工具）"""

    db = await get_mongodb_database()

    print("\n" + "=" * 80)
    print("🔍 【独立验证】迁移结果检查")
    print("=" * 80)

    # 1. temp_ ID 检查
    temp_count = await db.search_results.count_documents({
        "task_id": {"$regex": "^temp_"}
    })
    print(f"\n  ❌ 剩余 temp_ ID: {temp_count}")

    # 2. 雪花ID格式检查
    snowflake_count = await db.search_results.count_documents({
        "task_id": {"$regex": "^[0-9]+$"}
    })
    total_count = await db.search_results.count_documents({
        "task_id": {"$ne": "", "$exists": True}
    })
    coverage = (snowflake_count / total_count * 100) if total_count > 0 else 0
    print(f"  ✅ 雪花算法ID: {snowflake_count}/{total_count} ({coverage:.1f}%)")

    # 3. 迁移历史检查
    with_history = await db.search_results.count_documents({
        "migration_history": {
            "$elemMatch": {
                "migration_type": "temp_to_snowflake"
            }
        }
    })
    print(f"  📋 带迁移历史: {with_history}")

    # 4. 结论
    print("\n" + "=" * 80)
    if temp_count == 0 and coverage >= 99.0:
        print("✅ 验证通过：ID系统统一完成")
    else:
        print("⚠️  验证异常：仍存在非雪花算法ID")
    print("=" * 80)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        # 验证模式
        asyncio.run(verify_migration())
    else:
        # 迁移模式
        asyncio.run(migrate_temp_task_ids())
