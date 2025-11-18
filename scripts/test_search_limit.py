#!/usr/bin/env python3
"""
测试 gpt-5-search-api 结果限制和控制台打印
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.nl_search.config import NLSearchConfig
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter


async def test_search_limit():
    """测试搜索结果限制为5条并打印到控制台"""

    # 配置 (max_search_results 默认已改为5)
    config = NLSearchConfig(
        llm_api_key="sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f",
        llm_base_url="https://api.gpt.ge/v1",
        search_model="gpt-5-search-api"
    )

    print(f"配置: max_search_results = {config.max_search_results}")

    # 创建适配器
    adapter = GPT5SearchAdapter(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url
    )

    try:
        # 测试查询
        queries = [
            "深度学习最新进展",
            "Rust编程语言特性",
            "量子计算应用"
        ]

        for query in queries:
            print(f"\n{'='*80}")
            print(f"执行搜索: {query}")
            print(f"{'='*80}")

            results = await adapter.search(query)

            print(f"\n✅ 返回结果数量: {len(results)}")

            # 搜索结果会自动在控制台打印 (通过 _print_search_results)

            await asyncio.sleep(2)  # 避免速率限制

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(test_search_limit())
