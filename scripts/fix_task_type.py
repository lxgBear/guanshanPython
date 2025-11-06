"""
修复任务类型

任务 244376860577325056 的 task_type 应该是 crawl_url 而不是 search_keyword
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def fix_task_type():
    """修复任务类型"""

    print(f"\n{'='*80}")
    print(f"修复任务类型")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        tasks_collection = db['search_tasks']

        task_id = "244376860577325056"

        # 查询任务
        task = await tasks_collection.find_one({"_id": task_id})

        if not task:
            print(f"❌ 未找到任务: {task_id}")
            return False

        print(f"\n📋 任务信息:")
        print(f"   名称: {task.get('name')}")
        print(f"   当前类型: {task.get('task_type')}")
        print(f"   URL: {task.get('crawl_url')}")

        print(f"\n🔧 修复操作:")
        print(f"   task_type: {task.get('task_type')} → crawl_url")

        # 更新任务类型
        result = await tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "task_type": "crawl_url",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            print(f"\n✅ 任务类型修复成功")
            return True
        else:
            print(f"\n⚠️ 任务未修改（可能已经是正确类型）")
            return False

    except Exception as e:
        print(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    await fix_task_type()


if __name__ == "__main__":
    asyncio.run(main())
