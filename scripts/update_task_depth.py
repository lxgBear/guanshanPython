"""更新任务的 max_depth 配置"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database

async def update_task_depth(task_id: str, max_depth: int):
    """更新任务的 max_depth"""
    try:
        db = await get_mongodb_database()
        tasks_collection = db.search_tasks
        
        # 获取当前任务
        task = await tasks_collection.find_one({"_id": task_id})
        if not task:
            print(f"❌ 任务不存在: {task_id}")
            return
        
        # 更新 crawl_config
        crawl_config = task.get('crawl_config', {})
        crawl_config['max_depth'] = max_depth
        
        # 保存更新
        result = await tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"crawl_config": crawl_config}}
        )
        
        if result.modified_count > 0:
            print(f"✅ 已更新任务 {task_id} 的 max_depth 为 {max_depth}")
            print(f"📋 新配置: {crawl_config}")
        else:
            print(f"⚠️ 任务配置未改变")
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python update_task_depth.py <task_id> <max_depth>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    max_depth = int(sys.argv[2])
    asyncio.run(update_task_depth(task_id, max_depth))
