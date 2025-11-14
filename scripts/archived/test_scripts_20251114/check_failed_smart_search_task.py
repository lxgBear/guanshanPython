"""
检查失败的智能搜索任务

分析任务 244662805996929024 为什么所有子搜索都失败
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_failed_task():
    """检查失败的智能搜索任务"""

    task_id = "244662805996929024"

    print(f"\n{'='*80}")
    print(f"检查失败的智能搜索任务: {task_id}")
    print(f"{'='*80}\n")

    try:
        db = await get_mongodb_database()

        # 1. 查询智能搜索任务
        smart_tasks = db['smart_search_tasks']
        task = await smart_tasks.find_one({"_id": task_id})

        if not task:
            print(f"❌ 任务不存在: {task_id}\n")
            return

        print(f"📋 智能搜索任务详情")
        print(f"{'='*80}\n")
        print(f"ID: {task['_id']}")
        print(f"名称: {task.get('name', 'N/A')}")
        print(f"原始查询: {task.get('original_query', 'N/A')}")
        print(f"状态: {task.get('status', 'N/A')}")
        print(f"错误信息: {task.get('error_message', 'N/A')}")
        print(f"创建时间: {task.get('created_at', 'N/A')}")
        print(f"确认时间: {task.get('confirmed_at', 'N/A')}")

        # 2. 分解的查询
        print(f"\n{'='*80}")
        print(f"📝 LLM分解的查询")
        print(f"{'='*80}\n")

        decomposed_queries = task.get('decomposed_queries', [])
        if decomposed_queries:
            for idx, q in enumerate(decomposed_queries, 1):
                print(f"{idx}. {q.get('query', 'N/A')}")
                print(f"   原因: {q.get('reasoning', 'N/A')}")
        else:
            print("无分解查询")

        # 3. 用户确认的查询
        print(f"\n{'='*80}")
        print(f"✅ 用户确认的查询")
        print(f"{'='*80}\n")

        confirmed_queries = task.get('user_confirmed_queries', [])
        if confirmed_queries:
            for idx, q in enumerate(confirmed_queries, 1):
                print(f"{idx}. {q}")
        else:
            print("无确认查询")

        # 4. 子搜索结果
        print(f"\n{'='*80}")
        print(f"🔍 子搜索执行结果")
        print(f"{'='*80}\n")

        sub_search_results = task.get('sub_search_results', {})
        sub_task_ids = task.get('sub_search_task_ids', [])

        if sub_search_results:
            for task_id, result in sub_search_results.items():
                print(f"任务 {task_id}:")
                print(f"  查询: {result.get('query', 'N/A')}")
                print(f"  状态: {result.get('status', 'N/A')}")
                print(f"  结果数: {result.get('result_count', 0)}")
                print(f"  错误: {result.get('error', 'N/A')}")
                print(f"  执行时间: {result.get('execution_time_ms', 0)}ms")
                print()
        else:
            print("无子搜索结果")

        # 5. 检查子搜索任务详情
        if sub_task_ids:
            print(f"{'='*80}")
            print(f"📊 子搜索任务详情 (从 instant_search_tasks 查询)")
            print(f"{'='*80}\n")

            instant_tasks = db['instant_search_tasks']
            for idx, sub_task_id in enumerate(sub_task_ids, 1):
                sub_task = await instant_tasks.find_one({"_id": sub_task_id})

                if sub_task:
                    print(f"{idx}. 任务 {sub_task_id}:")
                    print(f"   查询: {sub_task.get('query', 'N/A')}")
                    print(f"   状态: {sub_task.get('status', 'N/A')}")
                    print(f"   错误: {sub_task.get('error_message', 'N/A')}")
                    print(f"   结果数: {sub_task.get('total_results', 0)}")
                    print(f"   credits: {sub_task.get('credits_used', 0)}")
                    print(f"   执行时间: {sub_task.get('execution_time_ms', 0)}ms")

                    # 检查 Firecrawl 响应
                    if sub_task.get('firecrawl_response'):
                        response = sub_task['firecrawl_response']
                        print(f"   Firecrawl响应:")
                        print(f"     - success: {response.get('success', 'N/A')}")
                        if not response.get('success'):
                            print(f"     - error: {response.get('error', 'N/A')}")

                    print()
                else:
                    print(f"{idx}. 任务 {sub_task_id}: ❌ 不存在\n")

        # 6. 聚合统计
        print(f"{'='*80}")
        print(f"📈 聚合统计")
        print(f"{'='*80}\n")

        stats = task.get('aggregated_stats', {})
        if stats:
            print(f"总搜索数: {stats.get('total_searches', 0)}")
            print(f"成功搜索: {stats.get('successful_searches', 0)}")
            print(f"失败搜索: {stats.get('failed_searches', 0)}")
            print(f"总结果数: {stats.get('total_results_raw', 0)}")
            print(f"去重后结果: {stats.get('total_results_deduplicated', 0)}")
            print(f"总credits: {stats.get('total_credits_used', 0)}")
        else:
            print("无统计信息")

        print()

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await check_failed_task()


if __name__ == "__main__":
    asyncio.run(main())
