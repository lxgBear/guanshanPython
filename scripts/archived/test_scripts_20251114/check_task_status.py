"""检查任务执行状态和结果"""
import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database


async def check_task_status(task_id: str):
    """检查任务状态和结果数据"""
    try:
        db = await get_mongodb_database()

        # 1. 查询任务信息
        print(f"\n{'='*80}")
        print(f"🔍 检查任务: {task_id}")
        print(f"{'='*80}\n")

        tasks_collection = db.search_tasks
        task = await tasks_collection.find_one({"_id": task_id})

        if not task:
            print(f"❌ 任务不存在: {task_id}")
            return

        print("📋 任务基本信息:")
        print(f"  - ID: {task.get('_id')}")
        print(f"  - 名称: {task.get('name')}")
        print(f"  - 类型: {task.get('task_type', 'N/A')}")
        print(f"  - 状态: {task.get('status')}")
        print(f"  - 是否激活: {task.get('is_active')}")
        print(f"  - 查询词: {task.get('query', 'N/A')}")
        print(f"  - 爬取URL: {task.get('crawl_url', 'N/A')}")
        print(f"  - 创建时间: {task.get('created_at')}")
        print(f"  - 下次执行: {task.get('next_run_time')}")
        print(f"  - 最后执行: {task.get('last_executed_at')}")

        # 显示错误信息（v2.0.1 新增）
        if task.get('last_error'):
            print(f"\n⚠️  最后错误信息:")
            print(f"  - 错误: {task.get('last_error')}")
            print(f"  - 时间: {task.get('last_error_time')}")

        # 2. 查询执行历史
        print(f"\n📊 执行历史:")
        execution_history = task.get('execution_history', [])
        if execution_history:
            print(f"  - 总执行次数: {len(execution_history)}")
            # 显示最近3次执行
            recent_executions = sorted(execution_history, key=lambda x: x.get('execution_time', datetime.min), reverse=True)[:3]
            for i, exec_info in enumerate(recent_executions, 1):
                print(f"\n  执行记录 #{i}:")
                print(f"    - 执行时间: {exec_info.get('execution_time')}")
                print(f"    - 状态: {exec_info.get('status')}")
                print(f"    - 结果数: {exec_info.get('results_count', 0)}")
                print(f"    - 耗时: {exec_info.get('duration_seconds', 0)}秒")
                if exec_info.get('error_message'):
                    print(f"    - 错误: {exec_info.get('error_message')}")
        else:
            print("  ⚠️ 无执行历史记录")

        # 3. 查询 search_results
        print(f"\n📦 search_results 结果:")
        search_results = db.search_results
        results_count = await search_results.count_documents({"task_id": task_id})
        print(f"  - 结果数量: {results_count}")

        if results_count > 0:
            # 显示最新的3条结果
            cursor = search_results.find({"task_id": task_id}).sort("created_at", -1).limit(3)
            results = await cursor.to_list(length=3)
            print(f"\n  最新结果示例:")
            for i, result in enumerate(results, 1):
                print(f"\n  结果 #{i}:")
                print(f"    - ID: {result.get('_id')}")
                print(f"    - 标题: {result.get('title', 'N/A')[:50]}...")
                print(f"    - URL: {result.get('url', 'N/A')[:60]}...")
                print(f"    - 创建时间: {result.get('created_at')}")
                print(f"    - 状态: {result.get('status', 'N/A')}")
        else:
            print("  ❌ 没有找到任何结果数据")

        # 4. 查询 news_results
        print(f"\n📰 news_results (AI处理结果):")
        news_results = db.news_results
        news_count = await news_results.count_documents({"task_id": task_id})
        print(f"  - 结果数量: {news_count}")

        if news_count > 0:
            cursor = news_results.find({"task_id": task_id}).sort("created_at", -1).limit(3)
            results = await cursor.to_list(length=3)
            print(f"\n  最新结果示例:")
            for i, result in enumerate(results, 1):
                print(f"\n  结果 #{i}:")
                print(f"    - ID: {result.get('_id')}")
                print(f"    - 标题: {result.get('title', 'N/A')[:50]}...")
                print(f"    - URL: {result.get('url', 'N/A')[:60]}...")
                print(f"    - 状态: {result.get('status', 'N/A')}")
                print(f"    - 处理状态: {result.get('processing_status', 'N/A')}")

        # 5. 配置信息
        print(f"\n⚙️ 任务配置:")
        if task.get('search_config'):
            print(f"  search_config: {task.get('search_config')}")
        if task.get('crawl_config'):
            print(f"  crawl_config: {task.get('crawl_config')}")

        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_task_status.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    asyncio.run(check_task_status(task_id))
