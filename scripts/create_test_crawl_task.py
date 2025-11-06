"""创建测试爬取任务"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator.snowflake import SnowflakeGenerator

async def create_test_task():
    """创建测试爬取任务"""
    try:
        db = await get_mongodb_database()
        tasks_collection = db.search_tasks
        
        # 生成任务ID
        id_gen = SnowflakeGenerator()
        task_id = id_gen.generate_id()
        
        # 创建任务（使用最小配置，测试默认值）
        task = {
            "_id": str(task_id),
            "name": "测试默认排除首页",
            "task_type": "crawl_website",
            "crawl_url": "https://burmese.dvb.no/",
            "crawl_config": {
                "limit": 3,
                "max_depth": 2
                # 注意：不设置 exclude_paths，测试默认值
            },
            "status": "active",
            "is_active": False,  # 不启用定时任务
            "schedule_interval": "hourly",
            "created_at": None,
            "updated_at": None,
            "next_run_time": None,
            "last_executed_at": None,
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_results": 0,
            "total_credits_used": 0
        }
        
        await tasks_collection.insert_one(task)
        
        print(f"✅ 测试任务创建成功！")
        print(f"   - 任务ID: {task_id}")
        print(f"   - 任务名称: {task['name']}")
        print(f"   - 爬取URL: {task['crawl_url']}")
        print(f"   - 配置: {task['crawl_config']}")
        print(f"\n📝 说明: 此任务未设置 exclude_paths，将使用默认值 ['/$'] 自动排除首页")
        print(f"\n🚀 执行命令测试: python scripts/execute_task_now.py {task_id}")
        
        return str(task_id)
        
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(create_test_task())
