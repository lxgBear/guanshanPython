#!/usr/bin/env python3
"""
使用 prompt 参数爬取 news 页面，并将结果保存到 news_results 表

URL: https://www.thetibetpost.com/news
Prompt: "只爬取近期一个月的数据 忽略旧版存档"
存储位置: news_results 集合
"""

import asyncio
import sys
import re
from datetime import datetime, timedelta
from typing import List

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.infrastructure.id_generator.snowflake import SnowflakeGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 初始化 ID 生成器
id_generator = SnowflakeGenerator()


def extract_dates_from_text(text: str) -> List[str]:
    """从文本中提取日期信息"""
    if not text:
        return []

    patterns = [
        r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?',
        r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',
        r'\d{4}\.\d{1,2}\.\d{1,2}',
    ]

    dates = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)

    return dates


def extract_year_from_path(text: str) -> List[str]:
    """从图片路径中提取年份"""
    if not text:
        return []

    # 匹配 Pics-YYYY 格式
    pattern = r'Pics-(\d{4})'
    matches = re.findall(pattern, text)
    return matches


async def crawl_news_page():
    """爬取 news 页面并保存到数据库"""

    url = "https://www.thetibetpost.com/news"
    prompt = "只爬取近期一个月的数据 忽略旧版存档"

    try:
        # 连接数据库
        db = await get_mongodb_database()

        logger.info("=" * 80)
        logger.info(f"🚀 开始爬取 News 页面")
        logger.info("=" * 80)
        logger.info(f"\n目标 URL: {url}")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"存储位置: news_results 集合\n")

        # 初始化 Firecrawl 适配器
        adapter = FirecrawlAdapter()

        # 执行爬取
        logger.info("🔄 正在爬取...")
        start_time = datetime.now()

        results = await adapter.crawl(
            url=url,
            limit=10,
            max_depth=2,
            only_main_content=True,
            wait_for=1000,
            exclude_tags=['nav', 'footer', 'header'],
            prompt=prompt
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"\n✅ 爬取完成")
        logger.info(f"   耗时: {duration:.2f} 秒")
        logger.info(f"   结果数: {len(results)} 页\n")

        # 分析并保存每个结果
        logger.info("💾 保存结果到 news_results 表...")
        logger.info("=" * 80)

        saved_count = 0
        analysis_summary = []

        for i, result in enumerate(results, 1):
            # 处理 metadata
            metadata = result.metadata
            if hasattr(metadata, 'model_dump'):
                metadata_dict = metadata.model_dump()
            elif isinstance(metadata, dict):
                metadata_dict = metadata
            else:
                metadata_dict = {}

            # 提取基本信息
            title = metadata_dict.get('title', f'未命名页面 {i}')
            page_url = metadata_dict.get('url') or metadata_dict.get('og_url') or ''
            content = result.markdown or result.content or ''

            logger.info(f"\n[{i}] 分析页面: {title[:60]}...")
            logger.info(f"    URL: {page_url[:70]}...")

            # 从内容中提取日期
            dates_in_content = extract_dates_from_text(content[:3000])
            years_in_path = extract_year_from_path(content[:3000])

            logger.info(f"    内容长度: {len(content)} 字符")
            logger.info(f"    提取日期: {len(dates_in_content)} 个")
            if years_in_path:
                logger.info(f"    图片路径年份: {set(years_in_path)}")

            # 判断是否为近期内容（包含 2025 年标记）
            is_recent = '2025' in str(years_in_path) or '2025' in content[:1000]

            logger.info(f"    判断: {'✅ 2025年内容' if is_recent else '⚠️ 未确定'}")

            # 生成唯一 ID
            result_id = id_generator.generate()

            # 构建保存对象
            news_result = {
                "_id": result_id,
                "url": page_url,
                "title": title,
                "markdown": result.markdown,
                "html": result.html,
                "metadata": metadata_dict,
                "extracted_dates": dates_in_content[:10],
                "path_years": list(set(years_in_path)),
                "is_recent_content": is_recent,
                "content_length": len(content),
                "crawl_config": {
                    "source_url": url,
                    "prompt": prompt,
                    "limit": 10,
                    "max_depth": 2
                },
                "created_at": datetime.now(),
                "status": "active"
            }

            # 保存到数据库
            await db.news_results.insert_one(news_result)
            saved_count += 1

            # 记录分析结果
            analysis_summary.append({
                "title": title,
                "url": page_url,
                "is_recent": is_recent,
                "years": years_in_path,
                "dates": dates_in_content[:3]
            })

        logger.info(f"\n✅ 已保存 {saved_count} 条结果到 news_results 表")

        # 生成总结
        logger.info("\n" + "=" * 80)
        logger.info("📊 内容分析总结")
        logger.info("=" * 80)

        recent_count = sum(1 for item in analysis_summary if item['is_recent'])

        logger.info(f"\n总计爬取: {len(analysis_summary)} 页")
        logger.info(f"  ✅ 2025年内容: {recent_count} 页 ({recent_count/len(analysis_summary)*100:.1f}%)")
        logger.info(f"  ⚠️  其他/未确定: {len(analysis_summary) - recent_count} 页")

        # 显示 2025 年内容详情
        if recent_count > 0:
            logger.info(f"\n✅ 包含 2025 年标记的页面:")
            for item in analysis_summary:
                if item['is_recent']:
                    logger.info(f"\n  • {item['title'][:60]}...")
                    logger.info(f"    URL: {item['url'][:60]}...")
                    if item['years']:
                        logger.info(f"    年份: {set(item['years'])}")
                    if item['dates']:
                        logger.info(f"    日期: {item['dates']}")

        # Prompt 效果评估
        logger.info("\n" + "=" * 80)
        logger.info("🎯 Prompt 参数效果评估")
        logger.info("=" * 80)
        logger.info(f"\nPrompt: \"{prompt}\"")

        if recent_count > 0:
            logger.info(f"\n✅ 发现 {recent_count} 页包含 2025 年标记")
            logger.info(f"✅ 占比 {recent_count/len(analysis_summary)*100:.1f}%")
            logger.info(f"✅ Prompt 可能起到了引导作用")
        else:
            logger.info(f"\n⚠️  未找到 2025 年标记")
            logger.info(f"⚠️  需要进一步分析具体内容")

        return True

    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("\n🚀 开始执行：爬取 News 页面 + 数据库保存 + 内容分析\n")

    success = await crawl_news_page()

    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ 任务完成")
        logger.info("\n查看结果:")
        logger.info("  数据库查询: db.news_results.find().sort({created_at: -1}).limit(10)")
        logger.info("  Python 查询: python scripts/analyze_news_results.py")
    else:
        logger.info("❌ 任务失败")
    logger.info("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
