"""手动执行任务脚本"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.task_scheduler import TaskSchedulerService


async def execute_task_manually(task_id: str):
    """手动执行任务"""
    try:
        print(f"\n{'='*80}")
        print(f"🚀 手动执行任务: {task_id}")
        print(f"{'='*80}\n")

        # 初始化调度器
        scheduler = TaskSchedulerService()

        # 执行任务
        result = await scheduler.execute_task_now(task_id)

        print(f"\n✅ 任务执行完成！")
        print(f"结果: {result}")
        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"\n❌ 任务执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python execute_task_now.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    asyncio.run(execute_task_manually(task_id))
