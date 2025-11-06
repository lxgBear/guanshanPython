"""
检查测试任务配置和状态

用于查看两个测试任务的详细信息：
1. 244376860577325056 - URL爬取任务
2. 244383648711102464 - 关键词搜索任务
"""

import asyncio
import sys
import os
from datetime import datetime
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_task_info(task_id: str):
    """检查单个任务的详细信息"""

    print(f"\n{'='*80}")
    print(f"任务ID: {task_id}")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        tasks_collection = db['search_tasks']

        # 查询任务
        task = await tasks_collection.find_one({"_id": task_id})

        if not task:
            print(f"❌ 未找到任务: {task_id}")
            return None

        # 打印任务信息
        print(f"\n📋 基本信息:")
        print(f"   任务名称: {task.get('name', 'N/A')}")
        print(f"   任务类型: {task.get('task_type', 'N/A')}")
        print(f"   状态: {task.get('status', 'N/A')}")
        print(f"   创建时间: {task.get('created_at', 'N/A')}")

        print(f"\n🔍 搜索配置:")
        if task.get('query'):
            print(f"   关键词: {task.get('query')}")
        if task.get('crawl_url'):
            print(f"   URL: {task.get('crawl_url')}")

        search_config = task.get('search_config', {})
        print(f"   配置: {search_config}")

        print(f"\n📊 执行配置:")
        print(f"   调度类型: {task.get('schedule_type', 'N/A')}")
        print(f"   执行模式: {task.get('execution_mode', 'N/A')}")

        print(f"\n📈 执行统计:")
        print(f"   总执行次数: {task.get('total_executions', 0)}")
        print(f"   成功次数: {task.get('successful_executions', 0)}")
        print(f"   失败次数: {task.get('failed_executions', 0)}")

        if task.get('last_execution_at'):
            print(f"   上次执行: {task.get('last_execution_at')}")
        if task.get('next_execution_at'):
            print(f"   下次执行: {task.get('next_execution_at')}")

        # 查询该任务的搜索结果数量
        results_collection = db['search_results']
        result_count = await results_collection.count_documents({"task_id": task_id})
        print(f"\n📦 搜索结果数量: {result_count}")

        return task

    except Exception as e:
        print(f"❌ 查询任务失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """主函数"""

    print("\n" + "="*80)
    print("测试任务配置检查")
    print("="*80)

    # 测试任务ID列表
    task_ids = [
        "244376860577325056",  # URL爬取任务
        "244383648711102464"   # 关键词搜索任务
    ]

    for task_id in task_ids:
        await check_task_info(task_id)

    print("\n" + "="*80)
    print("检查完成")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
