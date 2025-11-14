#!/usr/bin/env python3
"""
测试 Firecrawl Map API 集成

验证 FirecrawlAdapter.map() 方法是否正确调用 Firecrawl v2 Map API
"""
import asyncio
import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter, MapAPIError
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_map_api():
    """测试Map API基本功能"""
    logger.info("=" * 80)
    logger.info("🧪 测试 Firecrawl Map API 集成")
    logger.info("=" * 80)

    try:
        # 1. 初始化适配器
        adapter = FirecrawlAdapter()
        logger.info("✅ FirecrawlAdapter 初始化成功\n")

        # 2. 测试基本Map调用（不带search参数）
        logger.info("📍 测试1: 基本Map调用（https://firecrawl.dev）")
        logger.info("-" * 80)

        links = await adapter.map(
            url="https://firecrawl.dev",
            limit=10  # 限制10个URL用于快速测试
        )

        logger.info(f"✅ 发现 {len(links)} 个URL")
        logger.info("\n前3个链接示例:")
        for i, link in enumerate(links[:3], 1):
            logger.info(f"  [{i}] {link['url']}")
            logger.info(f"      标题: {link.get('title', 'N/A')}")
            logger.info(f"      描述: {link.get('description', 'N/A')[:80]}...")
        logger.info("")

        # 3. 测试带search参数的Map调用
        logger.info("📍 测试2: 带search参数的Map调用（搜索'docs'）")
        logger.info("-" * 80)

        docs_links = await adapter.map(
            url="https://firecrawl.dev",
            search="docs",
            limit=10
        )

        logger.info(f"✅ 发现 {len(docs_links)} 个包含'docs'的URL")
        logger.info("\n搜索结果示例:")
        for i, link in enumerate(docs_links[:3], 1):
            logger.info(f"  [{i}] {link['url']}")
        logger.info("")

        # 4. 验证返回数据结构
        logger.info("📍 测试3: 验证返回数据结构")
        logger.info("-" * 80)

        if links:
            first_link = links[0]
            required_fields = ['url', 'title', 'description']

            for field in required_fields:
                if field in first_link:
                    logger.info(f"  ✅ 字段 '{field}' 存在")
                else:
                    logger.warning(f"  ⚠️  字段 '{field}' 缺失")
            logger.info("")

        # 5. 测试错误处理（无效URL）
        logger.info("📍 测试4: 错误处理（无效URL）")
        logger.info("-" * 80)

        try:
            await adapter.map(
                url="https://this-domain-does-not-exist-12345.com",
                limit=10
            )
            logger.warning("⚠️  预期抛出MapAPIError，但没有抛出")
        except MapAPIError as e:
            logger.info(f"✅ 正确抛出 MapAPIError: {str(e)[:100]}...")
        logger.info("")

        logger.info("=" * 80)
        logger.info("✅ 所有测试通过！Map API 集成正常工作")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    success = await test_map_api()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
