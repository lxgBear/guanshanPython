"""更新任务的 include_paths 和 exclude_paths 配置"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database

async def update_task_paths(task_id: str, include_paths: list, exclude_paths: list):
    """更新任务的路径过滤配置"""
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
        crawl_config['include_paths'] = include_paths
        crawl_config['exclude_paths'] = exclude_paths
        
        # 保存更新
        result = await tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"crawl_config": crawl_config}}
        )
        
        if result.modified_count > 0:
            print(f"✅ 已更新任务 {task_id} 的路径过滤配置")
            print(f"   - include_paths: {include_paths}")
            print(f"   - exclude_paths: {exclude_paths}")
            print(f"\n📋 完整配置: {crawl_config}")
        else:
            print(f"⚠️ 任务配置未改变")
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python update_task_paths.py <task_id> [include_path1,include_path2,...] [exclude_path1,exclude_path2,...]")
        print("示例: python update_task_paths.py 123 '/post/' ''")
        print("示例: python update_task_paths.py 123 '' '/$'")
        sys.exit(1)
    
    task_id = sys.argv[1]
    
    # 解析 include_paths
    include_paths = []
    if len(sys.argv) > 2 and sys.argv[2]:
        include_paths = [p.strip() for p in sys.argv[2].split(',') if p.strip()]
    
    # 解析 exclude_paths
    exclude_paths = []
    if len(sys.argv) > 3 and sys.argv[3]:
        exclude_paths = [p.strip() for p in sys.argv[3].split(',') if p.strip()]
    
    asyncio.run(update_task_paths(task_id, include_paths, exclude_paths))
