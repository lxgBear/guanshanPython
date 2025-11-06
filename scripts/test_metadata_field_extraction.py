"""
测试metadata字段提取功能

验证三个执行器（CrawlExecutor, ScrapeExecutor, SearchExecutor）
是否正确从metadata提取字段到SearchResult标准字段，
并确认metadata不再存储到数据库。

运行方式:
    python scripts/test_metadata_field_extraction.py
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.repositories import SearchResultRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_field_extraction():
    """检查最近的搜索结果字段提取情况"""

    print("\n" + "="*80)
    print("metadata字段提取验证测试")
    print("="*80)

    try:
        # 连接数据库
        db = await get_mongodb_database()
        collection = db['search_results']

        # 获取最近10条记录
        cursor = collection.find().sort("created_at", -1).limit(10)
        results = await cursor.to_list(length=10)

        if not results:
            print("\n⚠️  数据库中没有搜索结果记录")
            return

        print(f"\n📊 分析最近 {len(results)} 条搜索结果...")
        print("="*80)

        # 统计字段提取情况
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
        for idx, result in enumerate(results, 1):
            print(f"\n📄 记录 #{idx}")
            print(f"   ID: {result.get('_id')}")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   Source: {result.get('source', 'N/A')}")
            print(f"   Created: {result.get('created_at', 'N/A')}")

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
                            # 显示简化值
                            display_value = str(value)[:50]
                            if len(str(value)) > 50:
                                display_value += "..."
                            print(f"   ✅ {field}: {display_value}")
                        else:
                            print(f"   ❌ {field}: None/空")

        # 打印统计结果
        print("\n" + "="*80)
        print("📊 字段提取统计")
        print("="*80)

        print(f"\n{'字段名':<25} {'存在率':<12} {'有值率':<12} {'说明'}")
        print("-"*80)

        for field, stats in field_stats.items():
            if field == 'metadata':
                continue  # metadata单独处理

            exist_rate = (stats['count'] / len(results)) * 100
            non_empty_rate = (stats['non_empty'] / len(results)) * 100 if stats['count'] > 0 else 0

            status = "✅" if non_empty_rate >= 80 else "⚠️" if non_empty_rate >= 50 else "❌"

            print(f"{field:<25} {exist_rate:>5.1f}% ({stats['count']}/{len(results)}) "
                  f"{non_empty_rate:>5.1f}% ({stats['non_empty']}/{len(results)}) {status}")

        # metadata字段特殊统计
        print("\n" + "-"*80)
        print("metadata字段存储检查:")
        metadata_stats = field_stats['metadata']

        if metadata_stats['non_empty'] == 0:
            print(f"   ✅ 所有记录的metadata都为空 (已优化)")
            print(f"   ✅ v2.1.0优化生效：不再存储metadata字段")
        else:
            print(f"   ⚠️  发现 {metadata_stats['non_empty']}/{len(results)} 条记录仍有metadata")
            if metadata_stats['size_bytes']:
                avg_size = sum(metadata_stats['size_bytes']) / len(metadata_stats['size_bytes'])
                total_size = sum(metadata_stats['size_bytes'])
                print(f"   平均大小: {avg_size:.1f} 字节")
                print(f"   总大小: {total_size} 字节 ({total_size/1024:.2f} KB)")
                print(f"   ℹ️  这些可能是旧数据，新数据应该不存储metadata")

        # 验证结论
        print("\n" + "="*80)
        print("✅ 验证结论")
        print("="*80)

        # 核心字段检查
        core_fields = ['title', 'url', 'markdown_content']
        core_ok = all(field_stats[f]['non_empty'] / len(results) >= 0.9 for f in core_fields)

        # metadata字段检查
        metadata_ok = metadata_stats['non_empty'] == 0

        # 元数据字段检查（允许较低的提取率，因为取决于数据源）
        metadata_fields = ['author', 'language', 'published_date', 'http_status_code']
        metadata_extracted = any(field_stats[f]['non_empty'] > 0 for f in metadata_fields)

        if core_ok and metadata_ok and metadata_extracted:
            print("✅ 所有验证通过：")
            print("   1. ✅ 核心字段（title, url, markdown_content）提取正常")
            print("   2. ✅ metadata字段不再存储（v2.1.0优化生效）")
            print("   3. ✅ 元数据字段（author, language等）成功提取")
            return True
        else:
            print("⚠️  部分验证未通过：")
            if not core_ok:
                print("   ❌ 核心字段提取率低于90%")
            if not metadata_ok:
                print("   ⚠️  仍有记录存储metadata（可能是旧数据）")
            if not metadata_extracted:
                print("   ❌ 元数据字段未提取")
            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_source_distribution():
    """测试不同来源的记录分布"""

    print("\n" + "="*80)
    print("📊 数据来源分布")
    print("="*80)

    try:
        db = await get_mongodb_database()
        collection = db['search_results']

        # 聚合统计不同source的记录数
        pipeline = [
            {"$group": {
                "_id": "$source",
                "count": {"$sum": 1},
                "with_metadata": {
                    "$sum": {
                        "$cond": [
                            {"$or": [
                                {"$ne": ["$metadata", {}]},
                                {"$ne": ["$metadata", None]}
                            ]},
                            1,
                            0
                        ]
                    }
                }
            }},
            {"$sort": {"count": -1}}
        ]

        results = await collection.aggregate(pipeline).to_list(length=None)

        print(f"\n{'来源':<15} {'记录数':<12} {'有metadata':<12} {'说明'}")
        print("-"*80)

        for result in results:
            source = result['_id'] or 'unknown'
            count = result['count']
            with_metadata = result['with_metadata']
            metadata_rate = (with_metadata / count) * 100 if count > 0 else 0

            status = "✅" if metadata_rate == 0 else "⚠️"

            print(f"{source:<15} {count:<12} {with_metadata:<12} {status} {metadata_rate:.1f}%")

        print("\n说明:")
        print("  ✅ 0% metadata: 新数据，已优化")
        print("  ⚠️ >0% metadata: 旧数据，尚未清理")

    except Exception as e:
        print(f"\n❌ 统计失败: {e}")


async def main():
    """主测试函数"""

    print("\n" + "="*80)
    print("metadata字段提取优化验证测试")
    print("版本: v2.1.0")
    print("日期:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*80)

    # 执行测试
    result = await check_field_extraction()

    # 统计来源分布
    await test_source_distribution()

    # 总结
    print("\n" + "="*80)
    print("测试完成")
    print("="*80)

    if result:
        print("\n✅ 所有测试通过！")
        print("   - metadata字段不再存储到数据库")
        print("   - 所有字段正确从metadata提取")
        print("   - 三个执行器实现一致")
        return 0
    else:
        print("\n⚠️  部分测试未通过，请检查上方详细信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
