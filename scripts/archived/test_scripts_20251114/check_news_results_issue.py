"""检查 news_results 数据问题"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database

async def check_issue(task_id: str):
    """检查 news_results 数据问题"""
    try:
        db = await get_mongodb_database()
        
        # 查询该任务的 news_results
        results = await db.news_results.find(
            {"task_id": task_id}
        ).limit(3).to_list(length=3)
        
        print(f"\n{'='*80}")
        print(f"📊 任务 {task_id} 的 news_results 数据问题分析")
        print(f"{'='*80}\n")
        
        if not results:
            print("❌ 没有找到数据")
            return
        
        for i, result in enumerate(results, 1):
            print(f"结果 #{i}:")
            print(f"  - _id: {result.get('_id')}")
            print(f"  - title: {result.get('title', 'N/A')[:60]}...")
            print(f"  - status 字段类型: {type(result.get('status'))}")
            print(f"  - status 值: {result.get('status')}")
            print(f"  - processing_status: {result.get('processing_status', 'N/A')}")
            print(f"  - 所有字段: {list(result.keys())}")
            print()
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_news_results_issue.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    asyncio.run(check_issue(task_id))
