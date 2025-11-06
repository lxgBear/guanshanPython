"""
检查search_results表中markdown_content字段的内容

分析最近的记录，查看markdown_content是否正确
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_markdown_content():
    """检查markdown_content字段内容"""

    print(f"\n{'='*80}")
    print(f"Markdown Content 内容检查")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        results_collection = db['search_results']

        # 查询最近5条记录
        cursor = results_collection.find().sort("created_at", -1).limit(5)
        results = await cursor.to_list(length=5)

        if not results:
            print(f"❌ 未找到搜索结果记录")
            return

        print(f"\n📊 找到 {len(results)} 条最近的搜索结果")
        print(f"{'='*80}")

        # 分析每条记录
        for idx, result in enumerate(results, 1):
            print(f"\n{'='*80}")
            print(f"📄 记录 #{idx}")
            print(f"{'='*80}")
            print(f"ID: {result.get('_id')}")
            print(f"Task ID: {result.get('task_id')}")
            print(f"Title: {result.get('title', 'N/A')[:80]}")
            print(f"URL: {result.get('url', 'N/A')[:80]}")
            print(f"Source: {result.get('source', 'N/A')}")
            print(f"Created: {result.get('created_at', 'N/A')}")

            # 检查markdown_content
            markdown_content = result.get('markdown_content', '')

            print(f"\n📝 Markdown Content 分析:")
            print(f"   长度: {len(markdown_content)} 字符")

            if not markdown_content:
                print(f"   ❌ 内容为空")
            else:
                # 显示前300字符
                preview = markdown_content[:300]
                print(f"\n   预览（前300字符）:")
                print(f"   {'-'*76}")
                for line in preview.split('\n')[:10]:
                    print(f"   {line[:76]}")
                print(f"   {'-'*76}")

                # 分析内容类型
                print(f"\n   内容类型分析:")
                if markdown_content.strip().startswith('<'):
                    print(f"   ⚠️  内容似乎是HTML格式（以 < 开头）")
                elif markdown_content.strip().startswith('{') or markdown_content.strip().startswith('['):
                    print(f"   ⚠️  内容似乎是JSON格式")
                elif '# ' in markdown_content or '## ' in markdown_content:
                    print(f"   ✅ 内容包含Markdown标题")
                elif markdown_content.count('\n') < 5 and len(markdown_content) < 500:
                    print(f"   ⚠️  内容过短，可能只是摘要")
                else:
                    print(f"   ℹ️  内容似乎是普通文本")

                # 检查是否包含完整文章内容
                indicators = {
                    '段落分隔': markdown_content.count('\n\n'),
                    '链接数量': markdown_content.count('['),
                    '标题数量': markdown_content.count('# '),
                    '列表项': markdown_content.count('- ') + markdown_content.count('* '),
                }
                print(f"\n   内容特征:")
                for key, value in indicators.items():
                    print(f"   - {key}: {value}")

            # 检查html_content
            html_content = result.get('html_content', '')
            print(f"\n📄 HTML Content 分析:")
            print(f"   长度: {len(html_content)} 字符")

            if html_content:
                html_preview = html_content[:200]
                print(f"   预览（前200字符）: {html_preview[:200]}...")

            # 检查snippet
            snippet = result.get('snippet', '')
            print(f"\n📋 Snippet 分析:")
            print(f"   长度: {len(snippet)} 字符")
            if snippet:
                print(f"   内容: {snippet[:150]}")

        # 总结
        print(f"\n{'='*80}")
        print(f"📊 总结分析")
        print(f"{'='*80}")

        # 统计各种情况
        empty_markdown = sum(1 for r in results if not r.get('markdown_content'))
        short_markdown = sum(1 for r in results if r.get('markdown_content') and len(r.get('markdown_content', '')) < 500)
        html_like_markdown = sum(1 for r in results if r.get('markdown_content', '').strip().startswith('<'))

        print(f"\n问题分析:")
        print(f"   - markdown_content为空: {empty_markdown}/{len(results)}")
        print(f"   - markdown_content过短(<500字符): {short_markdown}/{len(results)}")
        print(f"   - markdown_content像HTML: {html_like_markdown}/{len(results)}")

        if empty_markdown > 0 or short_markdown > len(results) / 2 or html_like_markdown > 0:
            print(f"\n⚠️  发现问题:")
            if empty_markdown > 0:
                print(f"   - 有 {empty_markdown} 条记录的markdown_content为空")
            if short_markdown > len(results) / 2:
                print(f"   - 有 {short_markdown} 条记录的markdown_content过短")
            if html_like_markdown > 0:
                print(f"   - 有 {html_like_markdown} 条记录的markdown_content是HTML格式")

            print(f"\n可能原因:")
            print(f"   1. Firecrawl API未返回markdown格式内容")
            print(f"   2. API配置中未启用markdown格式提取")
            print(f"   3. 数据提取逻辑有误，取了错误的字段")
            print(f"   4. Search API只返回摘要，需要Scrape API获取完整内容")
        else:
            print(f"\n✅ markdown_content内容正常")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await check_markdown_content()


if __name__ == "__main__":
    asyncio.run(main())
