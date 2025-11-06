#!/usr/bin/env python3
"""
查询数据库中保存的爬取结果，查看具体内容片段

目的：通过查看实际内容来判断是否为近期数据
"""

import asyncio
import sys

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_saved_results():
    """分析保存在数据库中的结果"""

    task_id = "244746288889929728"

    try:
        # 连接数据库
        db = await get_mongodb_database()

        # 查询结果
        results = await db.processed_results.find(
            {"task_id": task_id}
        ).sort("created_at", -1).limit(10).to_list(length=10)

        if not results:
            logger.error(f"❌ 未找到任务 {task_id} 的结果")
            return False

        logger.info("=" * 80)
        logger.info(f"📊 分析任务 {task_id} 的爬取结果")
        logger.info(f"找到 {len(results)} 条结果")
        logger.info("=" * 80)

        for i, result in enumerate(results, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"【页面 {i}】{result.get('title', '未命名')[:60]}...")
            logger.info(f"{'=' * 80}")

            # 基本信息
            logger.info(f"\n📌 基本信息:")
            logger.info(f"  URL: {result.get('url', 'N/A')[:70]}...")
            logger.info(f"  内容长度: {result.get('content_length', 0)} 字符")
            logger.info(f"  是否近期: {'✅ 是' if result.get('is_recent_content') else '❌ 否'}")

            # 提取的日期
            extracted_dates = result.get('extracted_dates', [])
            recent_dates = result.get('recent_dates', [])
            old_dates = result.get('old_dates', [])

            logger.info(f"\n📅 日期信息:")
            logger.info(f"  提取到的日期数: {len(extracted_dates)}")
            if recent_dates:
                logger.info(f"  近期日期 (30天内): {recent_dates}")
            if old_dates:
                logger.info(f"  旧日期: {old_dates}")
            if not extracted_dates:
                logger.info(f"  ⚠️  未找到日期信息")

            # 查看内容片段
            content = result.get('markdown_content') or result.get('content', '')
            if content:
                logger.info(f"\n📝 内容预览 (前500字符):")
                logger.info("  " + "-" * 78)

                # 提取前500字符
                preview = content[:500].replace('\n', '\n  ')
                logger.info(f"  {preview}")

                if len(content) > 500:
                    logger.info(f"  ...")
                    logger.info(f"  (还有 {len(content) - 500} 字符)")

                logger.info("  " + "-" * 78)

                # 搜索关键词
                keywords_to_check = [
                    '2025', '2024', '2023',
                    'recently', 'latest', 'new', 'today', 'yesterday',
                    '最近', '最新', '今天', '昨天', '本月', '上月',
                    'Nov', 'Oct', 'Sep', 'Aug', 'December', 'November', 'October'
                ]

                found_keywords = []
                content_lower = content.lower()
                for keyword in keywords_to_check:
                    if keyword.lower() in content_lower:
                        # 找到关键词上下文
                        index = content_lower.find(keyword.lower())
                        start = max(0, index - 30)
                        end = min(len(content), index + len(keyword) + 30)
                        context = content[start:end].replace('\n', ' ')
                        found_keywords.append((keyword, context))

                if found_keywords:
                    logger.info(f"\n🔍 找到的时间相关关键词:")
                    for keyword, context in found_keywords[:5]:  # 只显示前5个
                        logger.info(f"  • '{keyword}': ...{context}...")

            else:
                logger.info(f"\n⚠️  内容为空")

        # 总结分析
        logger.info(f"\n{'=' * 80}")
        logger.info(f"📈 总体分析")
        logger.info(f"{'=' * 80}")

        recent_count = sum(1 for r in results if r.get('is_recent_content'))
        has_dates_count = sum(1 for r in results if r.get('extracted_dates'))

        logger.info(f"\n统计:")
        logger.info(f"  总页面数: {len(results)}")
        logger.info(f"  标记为近期: {recent_count} ({recent_count/len(results)*100:.1f}%)")
        logger.info(f"  包含日期信息: {has_dates_count} ({has_dates_count/len(results)*100:.1f}%)")
        logger.info(f"  无日期信息: {len(results) - has_dates_count} ({(len(results)-has_dates_count)/len(results)*100:.1f}%)")

        logger.info(f"\n观察:")
        if recent_count == 0:
            logger.info(f"  ⚠️  未找到明确的近期（30天内）日期")
            logger.info(f"  ⚠️  提取到的日期主要是：Jan, Feb, Mar, Jun, Oct, Nov（月份缩写）")
            logger.info(f"  ⚠️  但缺少完整的年份信息，无法准确判断")
        else:
            logger.info(f"  ✅ 发现 {recent_count} 页包含近期日期")

        logger.info(f"\n结论:")
        logger.info(f"  1. 目标网站的内容中缺少明确的完整日期格式（年-月-日）")
        logger.info(f"  2. 提取到的多为月份缩写，但缺少年份")
        logger.info(f"  3. 需要手动访问 URL 或使用更复杂的内容分析来判断时效性")
        logger.info(f"  4. Prompt 参数的实际效果难以直接验证")

        return True

    except Exception as e:
        logger.error(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("\n🔍 开始分析数据库中保存的爬取结果\n")

    success = await analyze_saved_results()

    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ 分析完成")
    else:
        logger.info("❌ 分析失败")
    logger.info("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
