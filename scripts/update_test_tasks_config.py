"""
更新测试任务配置

任务1 (244376860577325056 - URL爬取):
  - max_depth: 2
  - limit: 5

任务2 (244383648711102464 - 关键词搜索):
  - limit: 10
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def update_task_config(task_id: str, search_config: dict):
    """更新任务配置"""

    print(f"\n{'='*80}")
    print(f"更新任务配置: {task_id}")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        tasks_collection = db['search_tasks']

        # 查询任务
        task = await tasks_collection.find_one({"_id": task_id})

        if not task:
            print(f"❌ 未找到任务: {task_id}")
            return False

        print(f"\n📋 任务信息:")
        print(f"   名称: {task.get('name')}")
        print(f"   类型: {task.get('task_type')}")

        print(f"\n🔧 原配置:")
        print(f"   {task.get('search_config', {})}")

        print(f"\n🔧 新配置:")
        print(f"   {search_config}")

        # 更新配置
        result = await tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "search_config": search_config,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            print(f"\n✅ 配置更新成功")
            return True
        else:
            print(f"\n⚠️ 配置未改变")
            return False

    except Exception as e:
        print(f"❌ 更新配置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""

    print("\n" + "="*80)
    print("测试任务配置更新")
    print("="*80)

    # 任务1：URL爬取任务
    task1_id = "244376860577325056"
    task1_config = {
        "max_depth": 2,
        "limit": 5,
        "only_main_content": True,
        "remove_base64_images": False,
        "block_ads": True,
        "wait_for": 0,
        "timeout": 30
    }

    success1 = await update_task_config(task1_id, task1_config)

    # 任务2：关键词搜索任务
    task2_id = "244383648711102464"
    task2_config = {
        "limit": 10,
        "sources": ["web", "news"],
        "language": "auto",
        "include_domains": [],
        "exclude_domains": [],
        "time_range": "week",
        "enable_ai_summary": True,
        "extract_metadata": False,
        "follow_links": False,
        "max_depth": 1
    }

    success2 = await update_task_config(task2_id, task2_config)

    print("\n" + "="*80)
    print("配置更新完成")
    print(f"任务1: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"任务2: {'✅ 成功' if success2 else '❌ 失败'}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
