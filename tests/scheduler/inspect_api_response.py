#!/usr/bin/env python
"""
检查Firecrawl API响应数据

查看数据库中保存的原始API响应，分析content字段为何为空
"""

import sys
import asyncio
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def inspect_api_response():
    """检查API响应数据"""

    logger.info("=" * 80)
    logger.info("🔍 检查 Firecrawl API 响应数据")
    logger.info("=" * 80)

    try:
        # 连接数据库
        db = await get_mongodb_database()
        collection = db["search_results"]

        # 查询最近的一条搜索结果
        logger.info("\n📊 查询最近的搜索结果...")
        result = await collection.find_one(
            {"is_test_data": False},  # 只看真实数据
            sort=[("created_at", -1)]  # 按创建时间倒序
        )

        if not result:
            logger.warning("⚠️  没有找到真实搜索结果")
            return

        logger.info(f"✅ 找到搜索结果")
        logger.info(f"   - 任务ID: {result.get('task_id')}")
        logger.info(f"   - 标题: {result.get('title')}")
        logger.info(f"   - URL: {result.get('url')}")
        logger.info(f"   - 创建时间: {result.get('created_at')}")

        # 检查各个字段
        logger.info("\n" + "=" * 80)
        logger.info("📋 字段检查:")
        logger.info("=" * 80)

        content = result.get('content', '')
        snippet = result.get('snippet', '')
        markdown_content = result.get('markdown_content', '')

        logger.info(f"\n1. content 字段:")
        logger.info(f"   - 类型: {type(content)}")
        logger.info(f"   - 长度: {len(content) if content else 0}")
        logger.info(f"   - 值: {content if content else '(空)'}")

        logger.info(f"\n2. snippet 字段:")
        logger.info(f"   - 类型: {type(snippet)}")
        logger.info(f"   - 长度: {len(snippet) if snippet else 0}")
        logger.info(f"   - 值: {snippet[:200] if snippet else '(空)'}...")

        logger.info(f"\n3. markdown_content 字段:")
        logger.info(f"   - 类型: {type(markdown_content)}")
        logger.info(f"   - 长度: {len(markdown_content) if markdown_content else 0}")
        logger.info(f"   - 值: {markdown_content[:200] if markdown_content else '(空)'}...")

        # 检查原始API响应数据
        logger.info("\n" + "=" * 80)
        logger.info("🔍 原始API响应数据 (raw_data):")
        logger.info("=" * 80)

        raw_data = result.get('raw_data', {})
        if raw_data:
            logger.info(f"\n📦 raw_data 字段列表:")
            for key in raw_data.keys():
                value = raw_data.get(key)
                if isinstance(value, str):
                    logger.info(f"   - {key}: {type(value).__name__} (长度: {len(value)})")
                    if len(value) > 0:
                        preview = value[:200] if len(value) > 200 else value
                        logger.info(f"     预览: {preview}...")
                else:
                    logger.info(f"   - {key}: {type(value).__name__} = {value}")

            # 美化输出完整的raw_data
            logger.info(f"\n📄 完整 raw_data (JSON格式):")
            logger.info("-" * 80)
            logger.info(json.dumps(raw_data, indent=2, ensure_ascii=False))
            logger.info("-" * 80)
        else:
            logger.warning("⚠️  raw_data 为空")

        # 分析问题
        logger.info("\n" + "=" * 80)
        logger.info("🔬 问题分析:")
        logger.info("=" * 80)

        if not content and not markdown_content:
            logger.warning("\n⚠️  发现问题:")
            logger.warning("   - content 字段为空")
            logger.warning("   - markdown_content 字段也为空")

            if 'content' not in raw_data and 'markdown' not in raw_data:
                logger.warning("\n❌ 原因: API响应中没有返回 content 或 markdown 字段")
                logger.info("\n💡 可能的原因:")
                logger.info("   1. Firecrawl /search API 默认不返回完整内容")
                logger.info("   2. 需要使用 /scrape API 来获取网页完整内容")
                logger.info("   3. 或者在search请求中添加额外参数")
            elif raw_data.get('content') == '':
                logger.warning("\n❌ 原因: API返回了content字段，但值为空字符串")
            else:
                logger.info("\n✅ API返回了content，但代码没有正确解析")
        else:
            logger.info("\n✅ 内容字段有数据")

    except Exception as e:
        logger.error(f"❌ 检查过程发生错误: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await inspect_api_response()


if __name__ == "__main__":
    asyncio.run(main())
