#!/usr/bin/env python3
"""测试 content 字段移除后的功能

验证项：
1. SearchResult 实体创建（无 content 字段）
2. InstantSearchResult 实体创建（无 content 字段）
3. ProcessedResult 实体创建（无 content 字段）
4. 原始响应保存功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.domain.entities.search_result import SearchResult
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.processed_result import ProcessedResult
from src.core.domain.entities.firecrawl_raw_response import create_firecrawl_raw_response
from src.infrastructure.database.firecrawl_raw_repositories import get_firecrawl_raw_repository
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_search_result():
    """测试 SearchResult（无 content 字段）"""
    print("\n" + "="*60)
    print("✅ 测试 SearchResult 实体")
    print("="*60)

    try:
        result = SearchResult(
            task_id="test_task_123",
            title="测试标题",
            url="https://example.com/test",
            snippet="这是一个测试摘要",
            markdown_content="# 测试 Markdown 内容\n\n这是测试内容。",
            html_content="<h1>测试 HTML 内容</h1><p>这是测试内容。</p>"
        )

        print(f"✅ SearchResult 创建成功")
        print(f"   ID: {result.id}")
        print(f"   Title: {result.title}")
        print(f"   Markdown 长度: {len(result.markdown_content or '')}")

        # 验证没有 content 属性
        assert not hasattr(result, 'content') or result.content is None, "❌ SearchResult 不应该有 content 字段"
        print(f"✅ 确认：没有 content 字段")

        # 测试 to_summary()
        summary = result.to_summary()
        print(f"✅ to_summary() 工作正常")
        print(f"   Snippet: {summary.get('snippet', '')[:50]}...")

        return True

    except Exception as e:
        print(f"❌ SearchResult 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_instant_search_result():
    """测试 InstantSearchResult（无 content 字段）"""
    print("\n" + "="*60)
    print("✅ 测试 InstantSearchResult 实体")
    print("="*60)

    try:
        result = InstantSearchResult(
            task_id="test_task_456",
            title="即时搜索测试",
            url="https://example.com/instant",
            snippet="即时搜索摘要",
            markdown_content="即时搜索的 Markdown 内容"
        )

        print(f"✅ InstantSearchResult 创建成功")
        print(f"   ID: {result.id}")
        print(f"   Content Hash: {result.content_hash}")

        # 验证没有 content 属性
        assert not hasattr(result, 'content') or result.content is None, "❌ InstantSearchResult 不应该有 content 字段"
        print(f"✅ 确认：没有 content 字段")

        # 测试 to_summary()
        summary = result.to_summary()
        print(f"✅ to_summary() 工作正常")

        return True

    except Exception as e:
        print(f"❌ InstantSearchResult 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_processed_result():
    """测试 ProcessedResult（无 content 字段）"""
    print("\n" + "="*60)
    print("✅ 测试 ProcessedResult 实体")
    print("="*60)

    try:
        result = ProcessedResult(
            raw_result_id="raw_123",
            task_id="test_task_789",
            title="处理后结果",
            url="https://example.com/processed",
            snippet="处理后的摘要",
            markdown_content="处理后的 Markdown 内容"
        )

        print(f"✅ ProcessedResult 创建成功")
        print(f"   ID: {result.id}")
        print(f"   Status: {result.status.value}")

        # 验证没有 content 属性
        assert not hasattr(result, 'content') or result.content is None, "❌ ProcessedResult 不应该有 content 字段"
        print(f"✅ 确认：没有 content 字段")

        return True

    except Exception as e:
        print(f"❌ ProcessedResult 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_raw_response_storage():
    """测试原始响应存储"""
    print("\n" + "="*60)
    print("✅ 测试原始响应存储")
    print("="*60)

    try:
        # 创建原始响应
        raw_response = create_firecrawl_raw_response(
            task_id="test_task_raw",
            result_url="https://example.com/raw",
            raw_data={
                "title": "原始数据测试",
                "url": "https://example.com/raw",
                "markdown": "# 原始 Markdown\n这是完整的原始数据",
                "html": "<h1>原始 HTML</h1>",
                "metadata": {
                    "language": "zh",
                    "sourceURL": "https://example.com/raw"
                }
            },
            api_endpoint="search",
            response_time_ms=1500
        )

        print(f"✅ 原始响应实体创建成功")
        print(f"   ID: {raw_response.id}")
        print(f"   URL: {raw_response.result_url}")
        print(f"   Response Time: {raw_response.response_time_ms}ms")

        # 测试保存到数据库
        repo = await get_firecrawl_raw_repository()
        saved_id = await repo.create(raw_response)

        print(f"✅ 保存到数据库成功: {saved_id}")

        # 测试读取
        retrieved = await repo.get_by_id(raw_response.id)

        if retrieved:
            print(f"✅ 从数据库读取成功")
            print(f"   标题: {retrieved.raw_response.get('title')}")

            # 清理测试数据
            await repo.delete_by_task_id("test_task_raw")
            print(f"✅ 测试数据已清理")

            return True
        else:
            print(f"❌ 从数据库读取失败")
            return False

    except Exception as e:
        print(f"❌ 原始响应存储测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🧪 Content 字段移除测试")
    print("="*60)

    results = []

    # 执行所有测试
    results.append(await test_search_result())
    results.append(await test_instant_search_result())
    results.append(await test_processed_result())
    results.append(await test_raw_response_storage())

    # 汇总结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"总计: {total} 个测试")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")

    if all(results):
        print("\n🎉 所有测试通过！")
        print("="*60)
        return 0
    else:
        print("\n⚠️ 部分测试失败")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
