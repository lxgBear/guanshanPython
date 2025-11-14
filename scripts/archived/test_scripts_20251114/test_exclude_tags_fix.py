"""
测试excludeTags配置修复效果

验证默认exclude_tags配置是否有效减少导航内容
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.services.task_scheduler import TaskSchedulerService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_exclude_tags_fix():
    """测试exclude_tags配置修复效果"""

    print(f"\n{'='*80}")
    print(f"ExcludeTags 配置修复效果测试")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        tasks_collection = db['search_tasks']
        results_collection = db['search_results']

        # 使用测试任务 244383648711102464 重新执行
        task_id = "244383648711102464"

        print(f"\n📋 测试任务信息")
        print(f"{'='*80}")

        task = await tasks_collection.find_one({"_id": task_id})
        if not task:
            print(f"❌ 未找到任务 {task_id}")
            return

        print(f"任务ID: {task_id}")
        print(f"任务名称: {task.get('name', 'N/A')}")
        print(f"任务类型: {task.get('task_type', 'N/A')}")
        print(f"关键词: {task.get('query', 'N/A')}")

        # 获取修复前的最新结果（用于对比）
        print(f"\n📊 获取修复前的结果样本（最新5条）")
        print(f"{'='*80}")

        old_cursor = results_collection.find(
            {"task_id": task_id}
        ).sort("created_at", -1).limit(5)
        old_results = await old_cursor.to_list(length=5)

        if old_results:
            print(f"✅ 找到 {len(old_results)} 条修复前的记录")

            # 分析修复前的内容质量
            old_stats = {
                "total_links": 0,
                "total_chars": 0,
                "has_navigation": 0,
                "avg_link_density": 0
            }

            for result in old_results:
                markdown = result.get('markdown_content', '')
                if markdown:
                    old_stats["total_chars"] += len(markdown)
                    old_stats["total_links"] += markdown.count('[')

                    # 检查是否包含导航链接
                    if any(nav in markdown for nav in ['[首页]', '[主要职责]', '[外交部]', '导航', 'navigation']):
                        old_stats["has_navigation"] += 1

            if old_stats["total_chars"] > 0:
                old_stats["avg_link_density"] = (old_stats["total_links"] / old_stats["total_chars"]) * 1000

            print(f"\n   修复前统计:")
            print(f"   - 总字符数: {old_stats['total_chars']:,}")
            print(f"   - 总链接数: {old_stats['total_links']}")
            print(f"   - 包含导航: {old_stats['has_navigation']}/{len(old_results)}")
            print(f"   - 平均链接密度: {old_stats['avg_link_density']:.2f} 个/千字符")
        else:
            print(f"⚠️  未找到修复前的记录")
            old_stats = None

        # 执行任务（使用新配置）
        print(f"\n🚀 使用新配置执行任务")
        print(f"{'='*80}")
        print(f"   配置: excludeTags = ['nav', 'header', 'footer', 'aside', 'form']")

        scheduler = TaskSchedulerService()
        result = await scheduler.execute_task_now(task_id)

        if result:
            print(f"✅ 任务执行成功")
        else:
            print(f"❌ 任务执行失败")
            return

        # 等待一会儿让数据写入
        await asyncio.sleep(2)

        # 获取修复后的最新结果
        print(f"\n📊 获取修复后的结果")
        print(f"{'='*80}")

        new_cursor = results_collection.find(
            {"task_id": task_id}
        ).sort("created_at", -1).limit(10)
        new_results = await new_cursor.to_list(length=10)

        if not new_results:
            print(f"❌ 未找到新结果")
            return

        print(f"✅ 找到 {len(new_results)} 条修复后的记录")

        # 分析修复后的内容质量
        new_stats = {
            "total_links": 0,
            "total_chars": 0,
            "has_navigation": 0,
            "avg_link_density": 0,
            "samples": []
        }

        for idx, result in enumerate(new_results[:5], 1):  # 只分析前5条
            markdown = result.get('markdown_content', '')
            title = result.get('title', 'N/A')

            if markdown:
                char_count = len(markdown)
                link_count = markdown.count('[')
                has_nav = any(nav in markdown for nav in ['[首页]', '[主要职责]', '[外交部]', '导航', 'navigation'])

                new_stats["total_chars"] += char_count
                new_stats["total_links"] += link_count
                if has_nav:
                    new_stats["has_navigation"] += 1

                new_stats["samples"].append({
                    "idx": idx,
                    "title": title[:50],
                    "chars": char_count,
                    "links": link_count,
                    "has_nav": has_nav,
                    "link_density": (link_count / char_count) * 1000 if char_count > 0 else 0
                })

        if new_stats["total_chars"] > 0:
            new_stats["avg_link_density"] = (new_stats["total_links"] / new_stats["total_chars"]) * 1000

        print(f"\n   修复后统计:")
        print(f"   - 总字符数: {new_stats['total_chars']:,}")
        print(f"   - 总链接数: {new_stats['total_links']}")
        print(f"   - 包含导航: {new_stats['has_navigation']}/{len(new_stats['samples'])}")
        print(f"   - 平均链接密度: {new_stats['avg_link_density']:.2f} 个/千字符")

        # 显示样本详情
        print(f"\n   样本详情:")
        for sample in new_stats["samples"]:
            nav_indicator = "⚠️ 有导航" if sample["has_nav"] else "✅ 无导航"
            print(f"   [{sample['idx']}] {sample['title']}")
            print(f"       字符: {sample['chars']:,} | 链接: {sample['links']} | 密度: {sample['link_density']:.2f}/千字符 | {nav_indicator}")

        # 对比分析
        if old_stats:
            print(f"\n{'='*80}")
            print(f"📈 修复效果对比")
            print(f"{'='*80}")

            print(f"\n   指标对比:")
            print(f"   {'指标':<20} {'修复前':<20} {'修复后':<20} {'改善'}")
            print(f"   {'-'*76}")

            # 链接密度对比
            old_density = old_stats['avg_link_density']
            new_density = new_stats['avg_link_density']
            density_improvement = ((old_density - new_density) / old_density * 100) if old_density > 0 else 0
            print(f"   {'链接密度(个/千字符)':<20} {old_density:<20.2f} {new_density:<20.2f} {density_improvement:+.1f}%")

            # 导航内容占比
            old_nav_ratio = (old_stats['has_navigation'] / len(old_results) * 100) if old_results else 0
            new_nav_ratio = (new_stats['has_navigation'] / len(new_stats['samples']) * 100) if new_stats['samples'] else 0
            nav_improvement = old_nav_ratio - new_nav_ratio
            print(f"   {'导航内容占比(%)':<20} {old_nav_ratio:<20.1f} {new_nav_ratio:<20.1f} {nav_improvement:+.1f}%")

            # 评估修复效果
            print(f"\n   修复效果评估:")
            if density_improvement >= 50:
                print(f"   ✅ 链接密度降低 {density_improvement:.1f}% - 效果显著")
            elif density_improvement >= 30:
                print(f"   ✅ 链接密度降低 {density_improvement:.1f}% - 效果良好")
            elif density_improvement >= 10:
                print(f"   ⚠️  链接密度降低 {density_improvement:.1f}% - 效果一般")
            else:
                print(f"   ❌ 链接密度降低 {density_improvement:.1f}% - 效果不明显")

            if new_nav_ratio == 0:
                print(f"   ✅ 导航内容完全移除 - 完美")
            elif new_nav_ratio < old_nav_ratio / 2:
                print(f"   ✅ 导航内容减少 {nav_improvement:.1f}% - 效果显著")
            elif new_nav_ratio < old_nav_ratio:
                print(f"   ⚠️  导航内容减少 {nav_improvement:.1f}% - 效果一般")
            else:
                print(f"   ❌ 导航内容未明显改善")

        print(f"\n{'='*80}")
        print(f"✅ 测试完成")
        print(f"{'='*80}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await test_exclude_tags_fix()


if __name__ == "__main__":
    asyncio.run(main())
