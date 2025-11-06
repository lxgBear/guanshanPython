"""
执行测试任务并验证metadata字段提取优化

任务1 (244376860577325056): URL爬取任务 - 5页，max_depth=2
任务2 (244383648711102464): 关键词搜索任务 - 10条结果
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.repositories import SearchTaskRepository, SearchResultRepository
from src.services.task_scheduler import TaskSchedulerService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def execute_and_analyze_task(task_id: str, task_name: str):
    """执行任务并分析结果"""

    print(f"\n{'='*80}")
    print(f"执行任务: {task_name} (ID: {task_id})")
    print(f"{'='*80}")

    try:
        # 执行任务
        print(f"\n🚀 开始执行任务...")
        start_time = datetime.utcnow()

        # 创建调度器实例并执行任务
        scheduler = TaskSchedulerService()
        result = await scheduler.execute_task_now(task_id)

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        if result:
            print(f"✅ 任务执行成功 (耗时: {execution_time:.2f}秒)")
        else:
            print(f"❌ 任务执行失败 (耗时: {execution_time:.2f}秒)")
            return False

        # 分析结果
        print(f"\n📊 分析执行结果...")
        db = await get_mongodb_database()
        results_collection = db['search_results']

        # 查询最新的结果
        cursor = results_collection.find({"task_id": task_id}).sort("created_at", -1).limit(20)
        results = await cursor.to_list(length=20)

        if not results:
            print(f"⚠️ 未找到搜索结果")
            return False

        print(f"\n✅ 找到 {len(results)} 条搜索结果")

        # 分析字段提取情况
        print(f"\n{'='*80}")
        print(f"字段提取分析")
        print(f"{'='*80}")

        # 统计字段
        field_stats = {
            'title': {'count': 0, 'non_empty': 0},
            'url': {'count': 0, 'non_empty': 0},
            'published_date': {'count': 0, 'non_empty': 0},
            'author': {'count': 0, 'non_empty': 0},
            'language': {'count': 0, 'non_empty': 0},
            'article_tag': {'count': 0, 'non_empty': 0},
            'article_published_time': {'count': 0, 'non_empty': 0},
            'source_url': {'count': 0, 'non_empty': 0},
            'http_status_code': {'count': 0, 'non_empty': 0},
            'search_position': {'count': 0, 'non_empty': 0},
            'markdown_content': {'count': 0, 'non_empty': 0},
            'html_content': {'count': 0, 'non_empty': 0},
            'metadata': {'count': 0, 'non_empty': 0, 'size_bytes': []}
        }

        # 分析每条记录
        for idx, result in enumerate(results[:5], 1):  # 只显示前5条详情
            print(f"\n📄 记录 #{idx}")
            print(f"   ID: {result.get('_id')}")
            print(f"   Title: {result.get('title', 'N/A')[:60]}...")
            print(f"   URL: {result.get('url', 'N/A')[:60]}...")
            print(f"   Source: {result.get('source', 'N/A')}")

            # 检查每个字段
            for field in field_stats.keys():
                if field in result:
                    field_stats[field]['count'] += 1
                    value = result[field]

                    if field == 'metadata':
                        # 特殊处理metadata字段
                        if value:  # 非空
                            field_stats[field]['non_empty'] += 1
                            import json
                            size = len(json.dumps(value))
                            field_stats[field]['size_bytes'].append(size)
                            print(f"   ⚠️  metadata: 存在 (大小: {size} 字节)")
                        else:
                            print(f"   ✅ metadata: 空 (已优化)")
                    else:
                        # 其他字段
                        if value is not None and value != '':
                            field_stats[field]['non_empty'] += 1

        # 统计所有记录
        for result in results:
            for field in field_stats.keys():
                if field in result:
                    value = result[field]
                    if field == 'metadata':
                        if value:
                            import json
                            size = len(json.dumps(value))
                            field_stats[field]['size_bytes'].append(size)

        # 打印统计结果
        print(f"\n{'='*80}")
        print(f"字段提取统计 (共 {len(results)} 条记录)")
        print(f"{'='*80}")

        print(f"\n{'字段名':<25} {'存在率':<15} {'有值率':<15} {'状态'}")
        print("-"*80)

        for field, stats in field_stats.items():
            if field == 'metadata':
                continue

            exist_rate = (stats['count'] / len(results)) * 100
            non_empty_rate = (stats['non_empty'] / len(results)) * 100 if stats['count'] > 0 else 0

            status = "✅" if non_empty_rate >= 80 else "⚠️" if non_empty_rate >= 50 else "❌"

            print(f"{field:<25} {exist_rate:>5.1f}% ({stats['count']}/{len(results)}) "
                  f"{non_empty_rate:>5.1f}% ({stats['non_empty']}/{len(results)}) {status}")

        # metadata字段特殊统计
        print(f"\n{'-'*80}")
        print("metadata字段存储检查:")
        metadata_stats = field_stats['metadata']

        if metadata_stats['non_empty'] == 0:
            print(f"   ✅ 所有记录的metadata都为空 (v2.1.0优化生效)")
        else:
            print(f"   ⚠️  发现 {metadata_stats['non_empty']}/{len(results)} 条记录仍有metadata")
            if metadata_stats['size_bytes']:
                avg_size = sum(metadata_stats['size_bytes']) / len(metadata_stats['size_bytes'])
                total_size = sum(metadata_stats['size_bytes'])
                print(f"   平均大小: {avg_size:.1f} 字节")
                print(f"   总大小: {total_size} 字节 ({total_size/1024:.2f} KB)")

        return True

    except Exception as e:
        print(f"❌ 执行任务失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""

    print("\n" + "="*80)
    print("测试任务执行与验证")
    print("="*80)

    # 任务1：URL爬取任务
    print("\n" + "="*80)
    print("测试1: URL爬取任务 (crawl_url)")
    print("="*80)
    success1 = await execute_and_analyze_task(
        "244376860577325056",
        "无声之声 - URL爬取"
    )

    # 等待一段时间
    print("\n⏳ 等待5秒后执行下一个任务...")
    await asyncio.sleep(5)

    # 任务2：关键词搜索任务
    print("\n" + "="*80)
    print("测试2: 关键词搜索任务 (search_keyword)")
    print("="*80)
    success2 = await execute_and_analyze_task(
        "244383648711102464",
        "test1 - 关键词搜索"
    )

    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print(f"URL爬取任务: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"关键词搜索任务: {'✅ 成功' if success2 else '❌ 失败'}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
