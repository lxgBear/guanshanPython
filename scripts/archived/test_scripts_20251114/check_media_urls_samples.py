"""
检查 media_urls 字段的样本数据

了解 media_urls 的实际内容和数据类型
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_media_urls_samples():
    """检查 media_urls 字段的样本"""

    print(f"\n{'='*80}")
    print(f"media_urls 字段样本数据分析")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        collection = db['news_results']

        # 查询有 media_urls 的记录
        cursor = collection.find(
            {"news_results.media_urls": {"$exists": True}}
        ).limit(5)

        results = await cursor.to_list(length=5)

        if not results:
            print(f"❌ 未找到包含 media_urls 的记录")
            return

        print(f"✅ 找到 {len(results)} 条包含 media_urls 的记录\n")

        for idx, result in enumerate(results, 1):
            news_results = result.get('news_results', {})
            media_urls = news_results.get('media_urls', [])

            print(f"{'='*80}")
            print(f"样本 #{idx}")
            print(f"{'='*80}")
            print(f"ID: {result.get('_id')}")
            print(f"Title: {news_results.get('title', 'N/A')[:60]}...")
            print(f"\nmedia_urls 字段:")
            print(f"  类型: {type(media_urls)}")
            print(f"  长度: {len(media_urls) if isinstance(media_urls, list) else 'N/A'}")

            if isinstance(media_urls, list):
                print(f"\n  内容:")
                for i, url in enumerate(media_urls[:10], 1):  # 只显示前10个
                    url_str = str(url)[:100]
                    print(f"    [{i}] {url_str}")
                    print(f"        类型: {type(url).__name__}")

                if len(media_urls) > 10:
                    print(f"    ... 还有 {len(media_urls) - 10} 个URL")
            else:
                print(f"  ⚠️  不是列表类型")

            print()

        # 统计分析
        print(f"{'='*80}")
        print(f"📊 统计分析")
        print(f"{'='*80}")

        all_urls = []
        for result in results:
            news_results = result.get('news_results', {})
            media_urls = news_results.get('media_urls', [])
            if isinstance(media_urls, list):
                all_urls.extend(media_urls)

        print(f"\n总URL数: {len(all_urls)}")
        print(f"平均每条记录URL数: {len(all_urls) / len(results):.1f}")

        # URL类型统计
        if all_urls:
            url_types = {}
            for url in all_urls[:20]:  # 分析前20个
                if isinstance(url, str):
                    # 提取文件扩展名
                    if '.' in url:
                        ext = url.split('.')[-1].split('?')[0].split('#')[0].lower()
                        url_types[ext] = url_types.get(ext, 0) + 1

            if url_types:
                print(f"\n文件类型分布（前20个URL）:")
                for ext, count in sorted(url_types.items(), key=lambda x: -x[1]):
                    print(f"  - .{ext}: {count}")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await check_media_urls_samples()


if __name__ == "__main__":
    asyncio.run(main())
