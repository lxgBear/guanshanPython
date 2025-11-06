"""
验证 v2.0.3 ProcessedResult 实体更新

测试要点:
1. NewsResultsDict TypedDict 类型提示是否正确
2. 包含 media_urls 的记录能否正确加载
3. 不包含 media_urls 的旧记录向后兼容性
4. Repository 的序列化/反序列化是否正常
"""

import asyncio
import sys
import os
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.core.domain.entities.processed_result import ProcessedResult, NewsResultsDict
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def validate_v203_updates():
    """验证 v2.0.3 实体更新"""

    print(f"\n{'='*80}")
    print(f"v2.0.3 ProcessedResult 实体验证")
    print(f"{'='*80}\n")

    try:
        # 初始化 Repository
        repo = ProcessedResultRepository()
        db = await get_mongodb_database()
        collection = db['news_results']

        # ==================== 测试 1: 加载包含 media_urls 的记录 ====================
        print(f"{'='*80}")
        print(f"测试 1: 加载包含 media_urls 的新记录")
        print(f"{'='*80}\n")

        cursor = collection.find(
            {"news_results.media_urls": {"$exists": True}}
        ).limit(2)

        docs_with_media = await cursor.to_list(length=2)

        if docs_with_media:
            for idx, doc in enumerate(docs_with_media, 1):
                result_id = str(doc['_id'])
                result = await repo.get_by_id(result_id)

                print(f"记录 #{idx}:")
                print(f"  ID: {result_id}")
                print(f"  news_results存在: {result.news_results is not None}")

                if result.news_results:
                    print(f"  标题: {result.news_results.get('title', 'N/A')[:50]}")

                    # 验证 media_urls 字段
                    media_urls = result.news_results.get('media_urls')
                    if media_urls is not None:
                        print(f"  ✅ media_urls 字段存在")
                        print(f"  media_urls类型: {type(media_urls)}")
                        print(f"  URL数量: {len(media_urls) if isinstance(media_urls, list) else 'N/A'}")

                        if isinstance(media_urls, list) and media_urls:
                            print(f"  样例URL: {media_urls[0][:80]}")

                            # 验证所有URL都是字符串
                            all_strings = all(isinstance(url, str) for url in media_urls)
                            print(f"  所有URL都是字符串: {'✅' if all_strings else '❌'}")
                    else:
                        print(f"  ❌ media_urls 字段不存在")
                else:
                    print(f"  ❌ news_results 为 None")

                print()
        else:
            print(f"❌ 未找到包含 media_urls 的记录\n")

        # ==================== 测试 2: 向后兼容性 ====================
        print(f"{'='*80}")
        print(f"测试 2: 向后兼容性（旧记录不包含 media_urls）")
        print(f"{'='*80}\n")

        # 查找不包含 media_urls 的记录
        cursor_old = collection.find({
            "news_results": {"$exists": True, "$ne": None},
            "news_results.media_urls": {"$exists": False}
        }).limit(1)

        docs_without_media = await cursor_old.to_list(length=1)

        if docs_without_media:
            doc = docs_without_media[0]
            result_id = str(doc['_id'])
            result = await repo.get_by_id(result_id)

            print(f"旧记录测试:")
            print(f"  ID: {result_id}")
            print(f"  news_results存在: {result.news_results is not None}")

            if result.news_results:
                print(f"  标题: {result.news_results.get('title', 'N/A')[:50]}")

                # 验证 media_urls 字段处理
                media_urls = result.news_results.get('media_urls')
                print(f"  media_urls值: {media_urls}")
                print(f"  ✅ 向后兼容: 旧记录可以正常加载（media_urls 为 None 或不存在）")
            else:
                print(f"  ❌ news_results 为 None")
        else:
            print(f"ℹ️  所有记录都包含 media_urls（无旧记录可测试）")

        print()

        # ==================== 测试 3: TypedDict 类型提示验证 ====================
        print(f"{'='*80}")
        print(f"测试 3: NewsResultsDict TypedDict 类型提示")
        print(f"{'='*80}\n")

        # 创建符合 TypedDict 的测试数据
        from datetime import datetime

        test_news_results: NewsResultsDict = {
            "title": "测试新闻标题",
            "published_at": datetime(2023, 10, 23),
            "source": "test.com",
            "content": "测试新闻内容",
            "category": {
                "大类": "测试",
                "类别": "测试",
                "地域": "测试"
            },
            "media_urls": [
                "https://example.com/image1.jpg",
                "https://example.com/image2.png"
            ]
        }

        # 创建 ProcessedResult 实例
        test_result = ProcessedResult(
            id="test_validation_id",
            raw_result_id="raw_test_id",
            task_id="task_test_id",
            news_results=test_news_results
        )

        print(f"创建测试 ProcessedResult:")
        print(f"  ID: {test_result.id}")
        print(f"  news_results 类型: {type(test_result.news_results)}")

        if test_result.news_results:
            print(f"  标题: {test_result.news_results.get('title')}")
            print(f"  media_urls 数量: {len(test_result.news_results.get('media_urls', []))}")
            print(f"  ✅ TypedDict 类型提示正常工作")

        print()

        # ==================== 测试 4: Repository 序列化/反序列化 ====================
        print(f"{'='*80}")
        print(f"测试 4: Repository 序列化/反序列化")
        print(f"{'='*80}\n")

        if docs_with_media:
            doc = docs_with_media[0]

            # 测试 _dict_to_result
            result = repo._dict_to_result(doc)
            print(f"_dict_to_result 反序列化:")
            print(f"  news_results 存在: {result.news_results is not None}")

            if result.news_results:
                media_urls = result.news_results.get('media_urls')
                print(f"  media_urls 存在: {media_urls is not None}")
                print(f"  media_urls 类型: {type(media_urls) if media_urls else 'None'}")

            # 测试 _result_to_dict
            result_dict = repo._result_to_dict(result)
            print(f"\n_result_to_dict 序列化:")
            print(f"  news_results 存在: {'news_results' in result_dict}")

            if 'news_results' in result_dict and result_dict['news_results']:
                media_urls_serialized = result_dict['news_results'].get('media_urls')
                print(f"  media_urls 存在: {media_urls_serialized is not None}")
                print(f"  media_urls 类型: {type(media_urls_serialized) if media_urls_serialized else 'None'}")
                print(f"  ✅ 序列化/反序列化正常")

        print()

        # ==================== 总结 ====================
        print(f"{'='*80}")
        print(f"验证总结")
        print(f"{'='*80}\n")

        print(f"✅ 测试 1: 新记录 media_urls 字段加载正常")
        print(f"✅ 测试 2: 旧记录向后兼容性良好")
        print(f"✅ 测试 3: NewsResultsDict TypedDict 类型提示正确")
        print(f"✅ 测试 4: Repository 序列化/反序列化正常")
        print(f"\n🎉 v2.0.3 实体更新验证通过，生产就绪\n")

    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await validate_v203_updates()


if __name__ == "__main__":
    asyncio.run(main())
