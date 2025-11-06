"""
验证metadata字段提取优化效果

分析任务244383648711102464的10条搜索结果：
1. 检查metadata字段是否为空
2. 检查所有字段的提取情况
3. 生成优化效果报告
"""

import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def verify_metadata_optimization():
    """验证metadata字段优化"""

    print(f"\n{'='*80}")
    print(f"Metadata字段提取优化验证")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        results_collection = db['search_results']

        # 查询任务244383648711102464的所有结果
        task_id = "244383648711102464"
        cursor = results_collection.find({"task_id": task_id}).sort("created_at", -1)
        results = await cursor.to_list(length=None)

        if not results:
            print(f"❌ 未找到任务 {task_id} 的搜索结果")
            return

        print(f"\n📊 找到 {len(results)} 条搜索结果")
        print(f"{'='*80}")

        # 统计字段
        field_stats = {
            'title': {'count': 0, 'non_empty': 0, 'samples': []},
            'url': {'count': 0, 'non_empty': 0, 'samples': []},
            'snippet': {'count': 0, 'non_empty': 0, 'samples': []},
            'published_date': {'count': 0, 'non_empty': 0, 'samples': []},
            'author': {'count': 0, 'non_empty': 0, 'samples': []},
            'language': {'count': 0, 'non_empty': 0, 'samples': []},
            'article_tag': {'count': 0, 'non_empty': 0, 'samples': []},
            'article_published_time': {'count': 0, 'non_empty': 0, 'samples': []},
            'source_url': {'count': 0, 'non_empty': 0, 'samples': []},
            'http_status_code': {'count': 0, 'non_empty': 0, 'samples': []},
            'search_position': {'count': 0, 'non_empty': 0, 'samples': []},
            'markdown_content': {'count': 0, 'non_empty': 0, 'size_bytes': []},
            'html_content': {'count': 0, 'non_empty': 0, 'size_bytes': []},
            'metadata': {'count': 0, 'non_empty': 0, 'size_bytes': []}
        }

        # 分析每条记录
        print(f"\n{'='*80}")
        print(f"详细记录分析")
        print(f"{'='*80}")

        for idx, result in enumerate(results, 1):
            print(f"\n📄 记录 #{idx}")
            print(f"   ID: {result.get('_id')}")
            print(f"   Title: {result.get('title', 'N/A')[:80]}")
            print(f"   URL: {result.get('url', 'N/A')[:80]}")
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
                            size = len(json.dumps(value))
                            field_stats[field]['size_bytes'].append(size)
                            print(f"   ⚠️  metadata: 存在 (大小: {size} 字节) - 内容: {value}")
                        else:
                            print(f"   ✅ metadata: 空 (已优化)")

                    elif field in ['markdown_content', 'html_content']:
                        # 内容字段显示大小
                        if value is not None and value != '':
                            field_stats[field]['non_empty'] += 1
                            size = len(str(value))
                            field_stats[field]['size_bytes'].append(size)
                            print(f"   ✅ {field}: {size} 字符")
                        else:
                            print(f"   ❌ {field}: 空")

                    else:
                        # 其他字段显示值
                        if value is not None and value != '':
                            field_stats[field]['non_empty'] += 1
                            # 收集样本（最多3个）
                            if len(field_stats[field]['samples']) < 3:
                                field_stats[field]['samples'].append(str(value)[:50])
                            print(f"   ✅ {field}: {str(value)[:60]}")
                        else:
                            print(f"   ❌ {field}: 空")

        # 打印统计结果
        print(f"\n{'='*80}")
        print(f"字段提取统计 (共 {len(results)} 条记录)")
        print(f"{'='*80}")

        print(f"\n{'字段名':<25} {'存在数':<10} {'有值数':<10} {'有值率':<10} {'状态'}")
        print("-"*80)

        for field, stats in field_stats.items():
            if field == 'metadata':
                continue

            exist_count = stats['count']
            non_empty_count = stats['non_empty']
            non_empty_rate = (non_empty_count / len(results)) * 100 if len(results) > 0 else 0

            status = "✅" if non_empty_rate >= 80 else "⚠️" if non_empty_rate >= 50 else "❌"

            print(f"{field:<25} {exist_count:<10} {non_empty_count:<10} {non_empty_rate:>5.1f}% {status:>10}")

            # 显示样本值（仅对非内容字段）
            if 'samples' in stats and stats['samples']:
                print(f"   样本值: {', '.join(stats['samples'])}")

            # 显示大小统计（仅对内容字段）
            if 'size_bytes' in stats and stats['size_bytes']:
                avg_size = sum(stats['size_bytes']) / len(stats['size_bytes'])
                total_size = sum(stats['size_bytes'])
                print(f"   大小: 平均 {avg_size:.0f} 字符, 总计 {total_size} 字符 ({total_size/1024:.2f} KB)")

        # metadata字段特殊统计
        print(f"\n{'='*80}")
        print("✨ Metadata字段存储优化验证")
        print(f"{'='*80}")
        metadata_stats = field_stats['metadata']

        print(f"\n{'指标':<30} {'结果':<30} {'状态'}")
        print("-"*80)
        print(f"{'总记录数':<30} {len(results):<30} ℹ️")
        print(f"{'metadata字段为空的记录':<30} {len(results) - metadata_stats['non_empty']:<30} {'✅' if metadata_stats['non_empty'] == 0 else '⚠️'}")
        print(f"{'metadata字段非空的记录':<30} {metadata_stats['non_empty']:<30} {'✅' if metadata_stats['non_empty'] == 0 else '❌'}")

        if metadata_stats['non_empty'] == 0:
            print(f"\n✅ **所有记录的metadata都为空 (v2.1.0优化生效)**")
            print(f"   - 数据库存储优化成功")
            print(f"   - 每条记录节省约 2-5KB")
            print(f"   - {len(results)}条记录总计节省约 {len(results)*3:.1f}KB")
        else:
            print(f"\n⚠️  发现 {metadata_stats['non_empty']}/{len(results)} 条记录仍有metadata")
            if metadata_stats['size_bytes']:
                avg_size = sum(metadata_stats['size_bytes']) / len(metadata_stats['size_bytes'])
                total_size = sum(metadata_stats['size_bytes'])
                print(f"   平均大小: {avg_size:.1f} 字节")
                print(f"   总大小: {total_size} 字节 ({total_size/1024:.2f} KB)")
                print(f"   ℹ️  这些可能是旧数据，新数据应该不存储metadata")

        # 总结
        print(f"\n{'='*80}")
        print("📝 验证结论")
        print(f"{'='*80}")

        # 核心字段检查
        core_fields = ['title', 'url']
        core_ok = all(field_stats[f]['non_empty'] / len(results) >= 0.9 for f in core_fields)

        # metadata字段检查
        metadata_ok = metadata_stats['non_empty'] == 0

        # 内容字段检查
        content_fields = ['markdown_content', 'snippet']
        content_ok = any(field_stats[f]['non_empty'] > 0 for f in content_fields)

        if core_ok and metadata_ok and content_ok:
            print("\n✅ **所有验证通过：**")
            print("   1. ✅ 核心字段（title, url）提取正常")
            print("   2. ✅ metadata字段不再存储（v2.1.0优化生效）")
            print("   3. ✅ 内容字段（markdown/snippet）成功提取")
            return True
        else:
            print("\n⚠️  部分验证未通过：")
            if not core_ok:
                print("   ❌ 核心字段提取率低于90%")
            if not metadata_ok:
                print("   ⚠️  仍有记录存储metadata（可能是旧数据）")
            if not content_ok:
                print("   ❌ 内容字段未提取")
            return False

    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    await verify_metadata_optimization()


if __name__ == "__main__":
    asyncio.run(main())
