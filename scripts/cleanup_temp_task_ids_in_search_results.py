"""
清理 search_results 中的 temp_ task_id 记录

策略: 直接删除 (因为记录数少，且为今天刚创建)

版本: v1.0.0
日期: 2025-11-23
"""
import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

import asyncio
import json
from datetime import datetime
from bson import ObjectId
from src.infrastructure.database.connection import get_mongodb_database

def json_serial(obj):
    """JSON序列化处理"""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

async def cleanup_temp_task_ids():
    """清理 temp_ task_id 记录"""
    db = await get_mongodb_database()

    print("="*80)
    print("🧹 清理 search_results temp_ task_id 记录")
    print("="*80)

    # 1. 识别记录
    print("\n📊 【步骤1】识别 temp_ task_id 记录...")

    temp_task_ids = [
        'temp_85bf1005cbad4ba7',
        'temp_bd7e6f7017124b24',
        'temp_e4997e658d2c4e18'
    ]

    # 统计
    total_count = 0
    for task_id in temp_task_ids:
        count = await db["search_results"].count_documents({"task_id": task_id})
        print(f"  {task_id}: {count} 条")
        total_count += count

    print(f"\n  总计: {total_count} 条记录")

    if total_count == 0:
        print("\n✅ 无需清理")
        return

    # 2. 备份
    print("\n💾 【步骤2】导出备份...")

    backup_records = []
    for task_id in temp_task_ids:
        records = await db["search_results"].find({"task_id": task_id}).to_list(length=None)
        backup_records.extend(records)

    # 导出到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"/tmp/search_results_temp_task_id_backup_{timestamp}.json"

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_records, f, ensure_ascii=False, indent=2, default=json_serial)

    print(f"  ✅ 备份文件: {backup_file}")
    print(f"  记录数: {len(backup_records)}")

    # 3. 删除
    print("\n🗑️  【步骤3】删除 temp_ task_id 记录...")

    deleted_count = 0
    for task_id in temp_task_ids:
        result = await db["search_results"].delete_many({"task_id": task_id})
        deleted_count += result.deleted_count
        print(f"  {task_id}: 删除 {result.deleted_count} 条")

    print(f"\n  ✅ 总计删除: {deleted_count} 条记录")

    # 4. 验证
    print("\n✅ 【步骤4】验证清理结果...")

    remaining = 0
    for task_id in temp_task_ids:
        count = await db["search_results"].count_documents({"task_id": task_id})
        remaining += count

    print(f"  剩余 temp_ task_id 记录: {remaining}")

    if remaining == 0:
        print("\n✅ 清理完成！")
    else:
        print(f"\n⚠️  仍有 {remaining} 条记录未删除")

    # 5. 摘要
    print("\n" + "="*80)
    print("📊 【清理摘要】")
    print("="*80)
    print(f"  识别记录: {total_count}")
    print(f"  删除记录: {deleted_count}")
    print(f"  剩余记录: {remaining}")
    print(f"  备份文件: {backup_file}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(cleanup_temp_task_ids())
