#!/usr/bin/env python3
"""
手动执行任务 244746288889929728 测试 prompt 参数

任务配置:
- 目标网站: https://www.thetibetpost.com/
- 爬取页数: 10 页
- 爬取深度: 2
- Prompt: "只爬取近期一个月的数据 忽略旧版存档"
"""

import asyncio
import sys
import json
from datetime import datetime

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def execute_task():
    """手动执行爬取任务"""

    task_id = "244746288889929728"

    try:
        # 1. 查询任务配置
        db = await get_mongodb_database()
        task = await db.search_tasks.find_one({"_id": task_id})

        if not task:
            logger.error(f"❌ 任务 {task_id} 不存在")
            return False

        logger.info("=" * 60)
        logger.info(f"任务信息:")
        logger.info(f"  ID: {task_id}")
        logger.info(f"  名称: {task.get('name')}")
        logger.info(f"  URL: {task.get('crawl_url')}")
        logger.info(f"  类型: {task.get('task_type')}")
        logger.info("=" * 60)

        # 2. 提取配置
        crawl_config = task.get('crawl_config', {})
        url = task.get('crawl_url')

        logger.info(f"\n爬取配置:")
        for key, value in crawl_config.items():
            logger.info(f"  {key}: {value}")

        # 3. 初始化 Firecrawl 适配器
        logger.info(f"\n初始化 Firecrawl 适配器...")
        adapter = FirecrawlAdapter()

        # 4. 准备参数
        exclude_tags = crawl_config.get('exclude_tags', ['nav', 'footer', 'header'])
        # 处理数据库中存储的字符串格式
        if isinstance(exclude_tags, str):
            logger.warning(f"   exclude_tags 是字符串格式: {exclude_tags}, 使用默认值")
            exclude_tags = ['nav', 'footer', 'header']

        # 执行爬取
        logger.info(f"\n🚀 开始爬取...")
        logger.info(f"   目标: {url}")
        logger.info(f"   Prompt: {crawl_config.get('prompt', '无')}")

        start_time = datetime.now()

        results = await adapter.crawl(
            url=url,
            limit=int(crawl_config.get('limit', 10)),
            max_depth=int(crawl_config.get('max_depth', 2)),
            only_main_content=crawl_config.get('only_main_content', True),
            wait_for=int(crawl_config.get('wait_for', 1000)),
            exclude_tags=exclude_tags,
            prompt=crawl_config.get('prompt')  # 传递 prompt 参数
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 5. 分析结果
        logger.info(f"\n✅ 爬取完成")
        logger.info(f"   耗时: {duration:.2f} 秒")
        logger.info(f"   结果数: {len(results)} 页")

        if results:
            logger.info(f"\n📊 结果预览:")
            for i, result in enumerate(results[:3], 1):
                logger.info(f"\n   [{i}] {result.url}")

                # 处理 metadata (可能是 dict 或 Pydantic 对象)
                metadata = result.metadata
                if hasattr(metadata, 'model_dump'):
                    # Pydantic 对象
                    metadata_dict = metadata.model_dump()
                elif isinstance(metadata, dict):
                    metadata_dict = metadata
                else:
                    metadata_dict = {}

                title = metadata_dict.get('title', '无标题')
                logger.info(f"       标题: {title[:50]}...")

                # 检查发布时间
                pub_time = metadata_dict.get('article_published_time') or \
                          metadata_dict.get('og:article:published_time') or \
                          metadata_dict.get('published_time')

                if pub_time:
                    logger.info(f"       发布时间: {pub_time}")
                else:
                    logger.info(f"       发布时间: 未找到")

                # 显示内容长度
                content_length = len(result.markdown or result.content or '')
                logger.info(f"       内容长度: {content_length} 字符")

            if len(results) > 3:
                logger.info(f"\n   ... 还有 {len(results) - 3} 条结果")

        # 6. 保存结果示例
        logger.info(f"\n💾 保存结果示例到文件...")
        output_file = f"crawl_result_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        result_data = []
        for result in results:
            # 处理 metadata
            metadata = result.metadata
            if hasattr(metadata, 'model_dump'):
                metadata_dict = metadata.model_dump()
            elif isinstance(metadata, dict):
                metadata_dict = metadata
            else:
                metadata_dict = {}

            result_data.append({
                "url": result.url,
                "title": metadata_dict.get('title', ''),
                "published_time": metadata_dict.get('article_published_time') or
                                 metadata_dict.get('og:article:published_time') or
                                 metadata_dict.get('published_time'),
                "content_length": len(result.markdown or result.content or ''),
                "metadata_keys": list(metadata_dict.keys())
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        logger.info(f"   已保存到: {output_file}")

        # 7. 分析时间分布
        logger.info(f"\n📅 时间分布分析:")
        with_time = 0
        without_time = 0

        for result in results:
            metadata = result.metadata
            if hasattr(metadata, 'model_dump'):
                metadata_dict = metadata.model_dump()
            elif isinstance(metadata, dict):
                metadata_dict = metadata
            else:
                metadata_dict = {}

            pub_time = metadata_dict.get('article_published_time') or \
                      metadata_dict.get('og:article:published_time') or \
                      metadata_dict.get('published_time')

            if pub_time:
                with_time += 1
            else:
                without_time += 1

        logger.info(f"   包含发布时间: {with_time} 页")
        logger.info(f"   无发布时间: {without_time} 页")

        return True

    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 Firecrawl v2 API prompt 参数 - 手动执行任务")
    logger.info("=" * 60 + "\n")

    success = await execute_task()

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ 测试完成")
        logger.info("\n分析 prompt 参数效果:")
        logger.info("1. 检查结果文件中的发布时间分布")
        logger.info("2. 确认是否主要包含近期一个月的数据")
        logger.info("3. 验证是否过滤了旧版存档页面")
    else:
        logger.info("❌ 测试失败")
    logger.info("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
