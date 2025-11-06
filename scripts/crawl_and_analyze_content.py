#!/usr/bin/env python3
"""
重新执行爬取任务，保存到数据库，并分析具体内容判断时间过滤效果

功能：
1. 执行带 prompt 的爬取任务
2. 将结果保存到 processed_results 集合
3. 提取内容中的时间信息
4. 分析内容判断是否为近期数据
"""

import asyncio
import sys
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.utils.logger import get_logger
from src.infrastructure.id_generator.snowflake import SnowflakeGenerator

logger = get_logger(__name__)

# 初始化 ID 生成器
id_generator = SnowflakeGenerator()


def extract_dates_from_text(text: str) -> List[str]:
    """从文本中提取日期信息"""
    if not text:
        return []

    # 匹配各种日期格式
    patterns = [
        r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?',  # 2025-11-06, 2025年11月6日
        r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # 11/06/2025
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',  # November 6, 2025
        r'\d{4}\.\d{1,2}\.\d{1,2}',  # 2025.11.06
    ]

    dates = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)

    return dates


def is_recent_date(date_str: str, days: int = 30) -> bool:
    """判断日期是否在最近N天内"""
    # 尝试多种日期格式解析
    formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日',
        '%m/%d/%Y', '%d/%m/%Y',
        '%Y.%m.%d',
        '%B %d, %Y', '%b %d, %Y'
    ]

    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str.strip(), fmt)
            cutoff_date = datetime.now() - timedelta(days=days)
            return parsed_date >= cutoff_date
        except ValueError:
            continue

    return False


async def crawl_and_save():
    """执行爬取并保存到数据库"""

    task_id = "244746288889929728"

    try:
        # 1. 连接数据库
        db = await get_mongodb_database()

        # 2. 查询任务配置
        task = await db.search_tasks.find_one({"_id": task_id})
        if not task:
            logger.error(f"❌ 任务 {task_id} 不存在")
            return False

        logger.info("=" * 60)
        logger.info(f"📋 任务信息:")
        logger.info(f"  ID: {task_id}")
        logger.info(f"  名称: {task.get('name')}")
        logger.info(f"  URL: {task.get('crawl_url')}")
        logger.info("=" * 60)

        # 3. 提取配置
        crawl_config = task.get('crawl_config', {})
        url = task.get('crawl_url')

        # 处理 exclude_tags
        exclude_tags = crawl_config.get('exclude_tags', ['nav', 'footer', 'header'])
        if isinstance(exclude_tags, str):
            exclude_tags = ['nav', 'footer', 'header']

        logger.info(f"\n🔧 爬取配置:")
        logger.info(f"  limit: {crawl_config.get('limit')}")
        logger.info(f"  max_depth: {crawl_config.get('max_depth')}")
        logger.info(f"  prompt: {crawl_config.get('prompt')}")

        # 4. 执行爬取
        logger.info(f"\n🚀 开始爬取...")
        adapter = FirecrawlAdapter()

        start_time = datetime.now()

        results = await adapter.crawl(
            url=url,
            limit=int(crawl_config.get('limit', 10)),
            max_depth=int(crawl_config.get('max_depth', 2)),
            only_main_content=crawl_config.get('only_main_content', True),
            wait_for=int(crawl_config.get('wait_for', 1000)),
            exclude_tags=exclude_tags,
            prompt=crawl_config.get('prompt')
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"\n✅ 爬取完成")
        logger.info(f"  耗时: {duration:.2f} 秒")
        logger.info(f"  结果数: {len(results)} 页")

        # 5. 分析并保存每个结果
        logger.info(f"\n💾 保存结果到数据库...")

        saved_count = 0
        content_analysis = []

        for i, result in enumerate(results, 1):
            # 处理 metadata
            metadata = result.metadata
            if hasattr(metadata, 'model_dump'):
                metadata_dict = metadata.model_dump()
            elif isinstance(metadata, dict):
                metadata_dict = metadata
            else:
                metadata_dict = {}

            # 提取内容
            content = result.markdown or result.content or ''
            title = metadata_dict.get('title', f'未命名页面 {i}')
            page_url = metadata_dict.get('url') or metadata_dict.get('og_url') or ''

            logger.info(f"\n  [{i}] 分析页面: {title[:50]}...")

            # 从内容中提取日期
            dates_in_content = extract_dates_from_text(content[:5000])  # 只分析前5000字符
            dates_in_title = extract_dates_from_text(title)
            all_dates = dates_in_title + dates_in_content

            # 判断是否为近期内容
            is_recent = False
            recent_dates = []
            old_dates = []

            for date_str in all_dates[:10]:  # 只检查前10个日期
                if is_recent_date(date_str, days=30):
                    is_recent = True
                    recent_dates.append(date_str)
                else:
                    old_dates.append(date_str)

            logger.info(f"      URL: {page_url[:60]}...")
            logger.info(f"      内容长度: {len(content)} 字符")
            logger.info(f"      提取日期数: {len(all_dates)}")
            if recent_dates:
                logger.info(f"      近期日期: {recent_dates[:3]}")
            if old_dates:
                logger.info(f"      旧日期: {old_dates[:3]}")
            logger.info(f"      判断: {'✅ 近期内容' if is_recent else '⚠️ 未确定或旧内容'}")

            # 保存到数据库
            result_id = id_generator.generate()

            processed_result = {
                "_id": result_id,
                "task_id": task_id,
                "url": page_url,
                "title": title,
                "markdown_content": result.markdown,
                "content": result.content,
                "html": result.html,
                "metadata": metadata_dict,
                "extracted_dates": all_dates[:10],
                "is_recent_content": is_recent,
                "recent_dates": recent_dates,
                "old_dates": old_dates,
                "content_length": len(content),
                "created_at": datetime.now(),
                "status": "active"
            }

            await db.processed_results.insert_one(processed_result)
            saved_count += 1

            # 记录分析结果
            content_analysis.append({
                "title": title,
                "url": page_url,
                "is_recent": is_recent,
                "dates_found": len(all_dates),
                "recent_dates": recent_dates,
                "old_dates": old_dates
            })

        logger.info(f"\n✅ 已保存 {saved_count} 条结果到数据库")

        # 6. 生成总体分析
        logger.info(f"\n" + "=" * 60)
        logger.info(f"📊 内容分析总结")
        logger.info(f"=" * 60)

        recent_count = sum(1 for item in content_analysis if item['is_recent'])
        unknown_count = len(content_analysis) - recent_count

        logger.info(f"\n总计爬取: {len(content_analysis)} 页")
        logger.info(f"  ✅ 近期内容: {recent_count} 页 ({recent_count/len(content_analysis)*100:.1f}%)")
        logger.info(f"  ⚠️  未确定/旧内容: {unknown_count} 页 ({unknown_count/len(content_analysis)*100:.1f}%)")

        # 显示近期内容详情
        if recent_count > 0:
            logger.info(f"\n✅ 近期内容详情:")
            for item in content_analysis:
                if item['is_recent']:
                    logger.info(f"\n  - {item['title'][:60]}...")
                    logger.info(f"    URL: {item['url'][:60]}...")
                    logger.info(f"    近期日期: {item['recent_dates'][:3]}")

        # 显示未确定内容
        if unknown_count > 0:
            logger.info(f"\n⚠️  未确定/旧内容:")
            for item in content_analysis:
                if not item['is_recent']:
                    logger.info(f"\n  - {item['title'][:60]}...")
                    logger.info(f"    URL: {item['url'][:60]}...")
                    if item['old_dates']:
                        logger.info(f"    旧日期: {item['old_dates'][:3]}")
                    else:
                        logger.info(f"    未找到日期信息")

        # 7. Prompt 效果评估
        logger.info(f"\n" + "=" * 60)
        logger.info(f"🎯 Prompt 参数效果评估")
        logger.info(f"=" * 60)
        logger.info(f"\nPrompt: \"{crawl_config.get('prompt')}\"")
        logger.info(f"\n评估结果:")

        if recent_count > 0:
            logger.info(f"  ✅ 找到 {recent_count} 页近期内容")
            logger.info(f"  ✅ Prompt 可能起到了过滤作用")
        else:
            logger.info(f"  ⚠️  未找到明确的近期日期信息")
            logger.info(f"  ⚠️  可能原因:")
            logger.info(f"     1. 网站内容确实是近期的，但没有明确标注日期")
            logger.info(f"     2. 需要更深入的内容分析")
            logger.info(f"     3. Prompt 效果需要对比测试验证")

        logger.info(f"\n建议:")
        logger.info(f"  1. 手动访问部分 URL 验证内容时效性")
        logger.info(f"  2. 执行不带 prompt 的对比测试")
        logger.info(f"  3. 使用更明确标注日期的网站测试")

        return True

    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("\n🚀 开始执行：爬取 + 数据库保存 + 内容分析\n")

    success = await crawl_and_save()

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ 任务完成")
        logger.info("\n可以通过以下方式查看结果:")
        logger.info("  1. 数据库查询: db.processed_results.find({task_id: '244746288889929728'})")
        logger.info("  2. 脚本分析: python scripts/analyze_crawl_results.py")
    else:
        logger.info("❌ 任务失败")
    logger.info("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
