"""检查爬取到的URL"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database

async def check_crawl_urls(task_id: str):
    """检查任务爬取到的URL"""
    try:
        db = await get_mongodb_database()
        
        # 查询 search_results
        results = await db.search_results.find(
            {"task_id": task_id}
        ).sort("created_at", -1).limit(10).to_list(length=10)
        
        print(f"\n{'='*80}")
        print(f"📊 任务 {task_id} 最近爬取的URL")
        print(f"{'='*80}\n")
        
        if not results:
            print("❌ 没有找到爬取结果")
            return
        
        print(f"📦 找到 {len(results)} 条结果:\n")
        
        for i, result in enumerate(results, 1):
            print(f"结果 #{i}:")
            print(f"  - URL: {result.get('url', 'N/A')}")
            print(f"  - 标题: {result.get('title', 'N/A')[:60]}...")
            print(f"  - 创建时间: {result.get('created_at')}")
            
            # 检查 metadata 中的时间信息
            metadata = result.get('metadata', {})
            if metadata:
                print(f"  - Metadata keys: {list(metadata.keys())}")
                if 'publishedTime' in metadata:
                    print(f"  - 发布时间: {metadata.get('publishedTime')}")
                if 'ogPublishedTime' in metadata:
                    print(f"  - OG发布时间: {metadata.get('ogPublishedTime')}")
            print()
        
        # 统计URL分布
        url_counts = {}
        for result in results:
            url = result.get('url', 'N/A')
            url_counts[url] = url_counts.get(url, 0) + 1
        
        print(f"\n📈 URL分布统计:")
        for url, count in url_counts.items():
            print(f"  - {url}: {count} 次")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_crawl_urls.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    asyncio.run(check_crawl_urls(task_id))
