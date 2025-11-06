"""检查详细的metadata信息"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database

async def check_metadata(task_id: str):
    """检查metadata详细信息"""
    try:
        db = await get_mongodb_database()
        
        # 查询最近5条结果
        results = await db.search_results.find(
            {"task_id": task_id}
        ).sort("created_at", -1).limit(5).to_list(length=5)
        
        print(f"\n{'='*80}")
        print(f"📊 任务 {task_id} 最近5条结果的详细信息")
        print(f"{'='*80}\n")
        
        for i, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            
            print(f"结果 #{i}:")
            print(f"  - 标题: {result.get('title', 'N/A')[:80]}")
            print(f"  - URL字段: {result.get('url', '(空)')}")
            print(f"  - Metadata中的URL: {metadata.get('url', '(空)')}")
            print(f"  - Source URL: {metadata.get('source_url', '(空)')}")
            print(f"  - 发布时间 (published_time): {metadata.get('published_time', '(空)')}")
            print(f"  - 修改时间 (modified_time): {metadata.get('modified_time', '(空)')}")
            print(f"  - DC创建时间 (dc_date_created): {metadata.get('dc_date_created', '(空)')}")
            print(f"  - 创建时间: {result.get('created_at')}")
            print()
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_detailed_metadata.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    asyncio.run(check_metadata(task_id))
