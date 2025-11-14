"""
检查Firecrawl API原始响应数据

查看firecrawl_raw_responses表中存储的原始API响应
分析markdown字段的实际内容
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


async def check_firecrawl_raw_data():
    """检查Firecrawl原始响应数据"""

    print(f"\n{'='*80}")
    print(f"Firecrawl API 原始响应数据检查")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        raw_collection = db['firecrawl_raw_responses']

        # 查询最近3条记录
        cursor = raw_collection.find().sort("created_at", -1).limit(3)
        results = await cursor.to_list(length=3)

        if not results:
            print(f"❌ 未找到原始响应记录")
            return

        print(f"\n📊 找到 {len(results)} 条原始API响应")
        print(f"{'='*80}")

        # 分析每条记录
        for idx, result in enumerate(results, 1):
            print(f"\n{'='*80}")
            print(f"📄 原始响应 #{idx}")
            print(f"{'='*80}")
            print(f"ID: {result.get('_id')}")
            print(f"Task ID: {result.get('task_id')}")
            print(f"URL: {result.get('result_url', 'N/A')[:80]}")
            print(f"API Endpoint: {result.get('api_endpoint', 'N/A')}")
            print(f"Created: {result.get('created_at', 'N/A')}")

            # 打印完整记录结构
            print(f"\n🔍 完整记录结构:")
            print(f"   所有字段: {list(result.keys())}")

            # 获取原始数据（字段名是 raw_response）
            raw_data = result.get('raw_response', {})

            print(f"\n📦 原始响应数据结构:")
            print(f"   类型: {type(raw_data)}")
            if isinstance(raw_data, dict):
                print(f"   顶层字段: {list(raw_data.keys())}")

            # 检查markdown字段
            if 'markdown' in raw_data:
                markdown = raw_data['markdown']
                print(f"\n📝 Markdown 字段:")
                print(f"   类型: {type(markdown)}")
                print(f"   长度: {len(markdown) if isinstance(markdown, str) else 'N/A'} 字符")

                if isinstance(markdown, str):
                    # 显示前500字符
                    preview = markdown[:500]
                    print(f"\n   预览（前500字符）:")
                    print(f"   {'-'*76}")
                    for line in preview.split('\n')[:15]:
                        print(f"   {line[:76]}")
                    print(f"   {'-'*76}")

                    # 分析内容
                    print(f"\n   内容分析:")
                    print(f"   - 是否以图片开头: {'是' if markdown.strip().startswith('![') else '否'}")
                    print(f"   - 是否包含导航链接: {'是' if '[首页]' in markdown or '[主要职责]' in markdown else '否'}")
                    print(f"   - 标题数量: {markdown.count('# ')}")
                    print(f"   - 链接数量: {markdown.count('[')}")
                    print(f"   - 段落数量: {markdown.count(chr(10) + chr(10))}")
                    print(f"   - 列表项数量: {markdown.count('- ') + markdown.count('* ')}")

            # 检查metadata字段
            if 'metadata' in raw_data:
                metadata = raw_data['metadata']
                print(f"\n🔍 Metadata 字段:")
                print(f"   字段: {list(metadata.keys()) if isinstance(metadata, dict) else 'N/A'}")

                # 显示部分metadata内容
                if isinstance(metadata, dict):
                    for key in ['title', 'description', 'language', 'author', 'og:type']:
                        if key in metadata:
                            value = metadata[key]
                            print(f"   - {key}: {str(value)[:60]}")

            # 检查html字段
            if 'html' in raw_data:
                html = raw_data['html']
                print(f"\n📄 HTML 字段:")
                print(f"   长度: {len(html) if isinstance(html, str) else 'N/A'} 字符")

            # 检查其他字段
            for key in ['url', 'title', 'description', 'source']:
                if key in raw_data:
                    value = raw_data[key]
                    print(f"\n{key}: {str(value)[:100]}")

        # 分析配置问题
        print(f"\n{'='*80}")
        print(f"📊 问题分析")
        print(f"{'='*80}")

        # 检查第一条记录的markdown内容特征
        if results:
            first_result = results[0]
            raw_data = first_result.get('raw_data', {})
            markdown = raw_data.get('markdown', '')

            if isinstance(markdown, str):
                has_navigation = any(nav in markdown for nav in ['[首页]', '[主要职责]', '[外交部]', 'navigation', 'menu'])
                has_header_footer = any(hf in markdown.lower() for hf in ['footer', 'header', 'copyright', '版权'])
                starts_with_image = markdown.strip().startswith('![')

                print(f"\n发现的问题:")
                if has_navigation:
                    print(f"   ⚠️  内容包含导航菜单链接")
                if has_header_footer:
                    print(f"   ⚠️  内容包含页眉/页脚")
                if starts_with_image:
                    print(f"   ⚠️  内容以图片开头（可能是logo或banner）")

                if has_navigation or has_header_footer or starts_with_image:
                    print(f"\n可能原因:")
                    print(f"   1. onlyMainContent 配置未生效")
                    print(f"   2. Firecrawl API 的主内容识别算法对某些网站效果不好")
                    print(f"   3. 需要使用 excludeTags 排除特定标签")
                    print(f"   4. 需要使用 includeTags 限制只提取特定标签")

                    print(f"\n建议方案:")
                    print(f"   1. 检查 scrapeOptions.onlyMainContent 是否正确传递给 API")
                    print(f"   2. 添加 excludeTags: ['nav', 'header', 'footer']")
                    print(f"   3. 尝试使用 includeTags: ['article', 'main', 'p']")
                    print(f"   4. 对比 Search API 和 Scrape API 返回的内容差异")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await check_firecrawl_raw_data()


if __name__ == "__main__":
    asyncio.run(main())
