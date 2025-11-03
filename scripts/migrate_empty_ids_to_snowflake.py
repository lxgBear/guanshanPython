"""数据迁移脚本：将空ID的记录迁移到雪花算法ID

目标：
1. 为所有id字段为空的search_results记录生成雪花ID
2. 为所有id字段为空的instant_search_results记录生成雪花ID
3. 保持其他字段不变，仅更新id字段
4. 提供详细的迁移报告

v1.5.0 数据迁移
"""

import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

import asyncio
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

async def migrate_empty_ids():
    db = await get_mongodb_database()

    print("=" * 80)
    print("📦 数据迁移：空ID → 雪花算法ID (v1.5.0)")
    print("=" * 80)

    # 1. 分析当前数据状态
    print("\n📊 【步骤1】分析当前数据...")

    scheduled_total = await db.search_results.count_documents({})
    scheduled_empty = await db.search_results.count_documents({
        "$or": [
            {"id": {"$exists": False}},
            {"id": ""},
            {"id": None}
        ]
    })

    instant_total = await db.instant_search_results.count_documents({})
    instant_empty = await db.instant_search_results.count_documents({
        "$or": [
            {"id": {"$exists": False}},
            {"id": ""},
            {"id": None}
        ]
    })

    print(f"  Scheduled集合:")
    print(f"    总记录数: {scheduled_total}")
    print(f"    空ID记录: {scheduled_empty}")
    print(f"    需迁移: {scheduled_empty}")

    print(f"\n  Instant集合:")
    print(f"    总记录数: {instant_total}")
    print(f"    空ID记录: {instant_empty}")
    print(f"    需迁移: {instant_empty}")

    total_to_migrate = scheduled_empty + instant_empty
    print(f"\n  📈 总计需迁移: {total_to_migrate} 条记录")

    if total_to_migrate == 0:
        print("\n✅ 所有记录已有ID，无需迁移")
        return

    # 2. 确认迁移
    print("\n" + "=" * 80)
    print("⚠️  【步骤2】迁移确认")
    print(f"  将为 {total_to_migrate} 条记录生成新的雪花算法ID")
    print("  此操作将修改数据库中的id字段")
    print("=" * 80)

    # 自动确认（生产环境应该改为手动确认）
    proceed = True

    if not proceed:
        print("❌ 迁移已取消")
        return

    # 3. 执行迁移 - Scheduled集合
    print("\n🔄 【步骤3】迁移 Scheduled 集合...")
    scheduled_migrated = 0
    scheduled_failed = 0

    if scheduled_empty > 0:
        # 修复：每次从头查询，直到没有空ID记录为止
        batch_size = 100

        while True:
            # 每次都从头查询空ID记录
            empty_records = await db.search_results.find(
                {
                    "$or": [
                        {"id": {"$exists": False}},
                        {"id": ""},
                        {"id": None}
                    ]
                },
                {"_id": 1}
            ).limit(batch_size).to_list(length=batch_size)

            if not empty_records:
                break

            # 为每条记录生成并更新雪花ID
            for record in empty_records:
                try:
                    new_id = generate_string_id()
                    result = await db.search_results.update_one(
                        {"_id": record["_id"]},
                        {"$set": {"id": new_id}}
                    )

                    if result.modified_count > 0:
                        scheduled_migrated += 1
                    else:
                        scheduled_failed += 1
                        print(f"    ⚠️  更新失败: MongoDB _id={record['_id']}")

                except Exception as e:
                    scheduled_failed += 1
                    print(f"    ❌ 迁移失败: MongoDB _id={record['_id']}, 错误: {e}")

            # 显示进度
            if scheduled_migrated % 50 == 0 and scheduled_migrated > 0:
                print(f"    进度: {scheduled_migrated}/{scheduled_empty}")

    print(f"  ✅ Scheduled集合迁移完成: 成功 {scheduled_migrated}, 失败 {scheduled_failed}")

    # 4. 执行迁移 - Instant集合
    print("\n🔄 【步骤4】迁移 Instant 集合...")
    instant_migrated = 0
    instant_failed = 0

    if instant_empty > 0:
        batch_size = 100

        while True:
            # 每次都从头查询空ID记录
            empty_records = await db.instant_search_results.find(
                {
                    "$or": [
                        {"id": {"$exists": False}},
                        {"id": ""},
                        {"id": None}
                    ]
                },
                {"_id": 1}
            ).limit(batch_size).to_list(length=batch_size)

            if not empty_records:
                break

            for record in empty_records:
                try:
                    new_id = generate_string_id()
                    result = await db.instant_search_results.update_one(
                        {"_id": record["_id"]},
                        {"$set": {"id": new_id}}
                    )

                    if result.modified_count > 0:
                        instant_migrated += 1
                    else:
                        instant_failed += 1
                        print(f"    ⚠️  更新失败: MongoDB _id={record['_id']}")

                except Exception as e:
                    instant_failed += 1
                    print(f"    ❌ 迁移失败: MongoDB _id={record['_id']}, 错误: {e}")

            if instant_migrated % 50 == 0 and instant_migrated > 0:
                print(f"    进度: {instant_migrated}/{instant_empty}")

    print(f"  ✅ Instant集合迁移完成: 成功 {instant_migrated}, 失败 {instant_failed}")

    # 5. 验证迁移结果
    print("\n" + "=" * 80)
    print("✅ 【步骤5】验证迁移结果...")

    scheduled_after_empty = await db.search_results.count_documents({
        "$or": [
            {"id": {"$exists": False}},
            {"id": ""},
            {"id": None}
        ]
    })

    instant_after_empty = await db.instant_search_results.count_documents({
        "$or": [
            {"id": {"$exists": False}},
            {"id": ""},
            {"id": None}
        ]
    })

    print(f"  Scheduled集合剩余空ID: {scheduled_after_empty}")
    print(f"  Instant集合剩余空ID: {instant_after_empty}")

    # 6. 抽样验证
    print("\n📋 【步骤6】抽样验证（前5条）...")

    sample_scheduled = await db.search_results.find({}).limit(5).to_list(length=5)
    print(f"\n  Scheduled集合样本:")
    for i, record in enumerate(sample_scheduled, 1):
        record_id = record.get("id", "")
        mongodb_id = record.get("_id")
        title = record.get("title", "")[:30]

        is_snowflake = record_id and "-" not in record_id and record_id.isdigit()
        id_format = "雪花ID" if is_snowflake else "其他格式"

        print(f"    {i}. ID: {record_id} ({id_format})")
        print(f"       MongoDB _id: {mongodb_id}")
        print(f"       标题: {title}")

    sample_instant = await db.instant_search_results.find({}).limit(5).to_list(length=5)
    print(f"\n  Instant集合样本:")
    for i, record in enumerate(sample_instant, 1):
        record_id = record.get("id", "")
        mongodb_id = record.get("_id")
        title = record.get("title", "")[:30]

        is_snowflake = record_id and "-" not in record_id and record_id.isdigit()
        id_format = "雪花ID" if is_snowflake else "其他格式"

        print(f"    {i}. ID: {record_id} ({id_format})")
        print(f"       MongoDB _id: {mongodb_id}")
        print(f"       标题: {title}")

    # 7. 迁移报告
    print("\n" + "=" * 80)
    print("📊 【迁移报告】")
    print("=" * 80)
    print(f"  Scheduled集合:")
    print(f"    迁移前空ID: {scheduled_empty}")
    print(f"    成功迁移: {scheduled_migrated}")
    print(f"    失败: {scheduled_failed}")
    print(f"    迁移后空ID: {scheduled_after_empty}")

    print(f"\n  Instant集合:")
    print(f"    迁移前空ID: {instant_empty}")
    print(f"    成功迁移: {instant_migrated}")
    print(f"    失败: {instant_failed}")
    print(f"    迁移后空ID: {instant_after_empty}")

    total_migrated = scheduled_migrated + instant_migrated
    total_failed = scheduled_failed + instant_failed

    print(f"\n  总计:")
    print(f"    成功迁移: {total_migrated} / {total_to_migrate}")
    print(f"    失败: {total_failed}")
    print(f"    成功率: {total_migrated / total_to_migrate * 100:.1f}%")

    if total_failed == 0 and (scheduled_after_empty + instant_after_empty) == 0:
        print("\n✅ 迁移完全成功！所有记录都已拥有雪花算法ID")
    elif total_failed > 0:
        print(f"\n⚠️  迁移部分失败，请检查失败记录")
    else:
        print("\n✅ 迁移成功！")

if __name__ == "__main__":
    asyncio.run(migrate_empty_ids())
