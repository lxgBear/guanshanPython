#!/usr/bin/env python
"""
测试完整内容抓取

验证Firecrawl API使用scrapeOptions后能否获取完整网页内容
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.core.domain.entities.search_config import UserSearchConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_content_scraping():
    """测试内容抓取功能"""

    logger.info("=" * 80)
    logger.info("🧪 测试: Firecrawl API 完整内容抓取")
    logger.info("=" * 80)

    try:
        # 初始化适配器
        adapter = FirecrawlSearchAdapter()

        # 创建搜索配置，限制为2条结果以节省API额度
        user_config = UserSearchConfig(
            template_name="default",
            overrides={
                "limit": 2,  # 只请求2条结果
                "scrape_formats": ["markdown", "html", "links"],  # 获取完整内容
                "only_main_content": True  # 只要主要内容
            }
        )

        # 执行搜索
        logger.info("\n📊 执行搜索:")
        logger.info(f"   - 查询: 'Python best practices 2024'")
        logger.info(f"   - 限制: 2条结果")
        logger.info(f"   - 抓取格式: markdown, html, links")
        logger.info("\n⏳ 正在调用API（可能需要10-30秒，因为要抓取完整内容）...\n")

        batch = await adapter.search(
            query="Python best practices 2024",
            user_config=user_config,
            task_id="content_test"
        )

        # 检查结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 API调用结果:")
        logger.info("=" * 80)
        logger.info(f"\n✅ 调用状态: {'成功' if batch.success else '失败'}")
        logger.info(f"   - 执行时间: {batch.execution_time_ms}ms")
        logger.info(f"   - 消耗积分: {batch.credits_used}")
        logger.info(f"   - 返回结果数: {batch.returned_count}")

        if not batch.success:
            logger.error(f"\n❌ 错误信息: {batch.error_message}")
            return False

        # 检查内容
        logger.info("\n" + "=" * 80)
        logger.info("🔍 内容检查:")
        logger.info("=" * 80)

        for i, result in enumerate(batch.results, 1):
            logger.info(f"\n【结果 {i}】")
            logger.info(f"   📄 标题: {result.title}")
            logger.info(f"   🔗 URL: {result.url}")
            logger.info(f"   📝 摘要长度: {len(result.snippet) if result.snippet else 0} 字符")

            # 检查content字段
            logger.info(f"\n   📦 content 字段:")
            if result.content:
                logger.info(f"      ✅ 有内容 - 长度: {len(result.content)} 字符")
                logger.info(f"      预览 (前300字符):")
                logger.info(f"      {'-' * 60}")
                logger.info(f"      {result.content[:300]}...")
                logger.info(f"      {'-' * 60}")
            else:
                logger.warning(f"      ❌ content为空")

            # 检查markdown_content字段
            logger.info(f"\n   📦 markdown_content 字段:")
            if result.markdown_content:
                logger.info(f"      ✅ 有markdown - 长度: {len(result.markdown_content)} 字符")
            else:
                logger.warning(f"      ❌ markdown_content为空")

            # 检查metadata中的html和links
            logger.info(f"\n   📦 metadata 字段:")
            if result.metadata.get('html_content'):
                logger.info(f"      ✅ 有html_content - 长度: {len(result.metadata['html_content'])} 字符")
            else:
                logger.warning(f"      ❌ 没有html_content")

            if result.metadata.get('extracted_links'):
                links_count = len(result.metadata['extracted_links'])
                logger.info(f"      ✅ 提取了 {links_count} 个链接")
                if links_count > 0:
                    logger.info(f"      前3个链接: {result.metadata['extracted_links'][:3]}")
            else:
                logger.warning(f"      ❌ 没有提取链接")

        # 最终评估
        logger.info("\n" + "=" * 80)
        logger.info("✨ 测试评估:")
        logger.info("=" * 80)

        has_content = any(r.content for r in batch.results)
        has_markdown = any(r.markdown_content for r in batch.results)

        if has_content and has_markdown:
            logger.info("\n✅ 测试通过:")
            logger.info("   ✅ API成功返回完整内容")
            logger.info("   ✅ content字段有数据")
            logger.info("   ✅ markdown_content字段有数据")
            logger.info("\n💡 说明:")
            logger.info("   - Firecrawl API的scrapeOptions参数工作正常")
            logger.info("   - 现在可以获取完整的网页内容用于AI分析")
            return True
        else:
            logger.error("\n❌ 测试失败:")
            if not has_content:
                logger.error("   ❌ content字段仍然为空")
            if not has_markdown:
                logger.error("   ❌ markdown_content字段为空")
            logger.error("\n💡 可能原因:")
            logger.error("   - scrapeOptions参数没有正确传递")
            logger.error("   - API响应格式有变化")
            logger.error("   - 某些网站阻止了内容抓取")
            return False

    except Exception as e:
        logger.error(f"❌ 测试过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    success = await test_content_scraping()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
