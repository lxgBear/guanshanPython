#!/usr/bin/env python3
"""
NL Search 集成测试
测试 api.gpt.ge 架构升级后的完整流程
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.nl_search.config import NLSearchConfig
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter
from src.services.nl_search.llm_processor import LLMProcessor


async def test_gpt5_search():
    """测试 gpt-5-search-api 搜索功能"""
    print("\n" + "=" * 60)
    print("测试 1: GPT-5 Search API")
    print("=" * 60)

    # 配置
    config = NLSearchConfig(
        llm_api_key="sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f",
        llm_base_url="https://api.gpt.ge/v1",
        search_model="gpt-5-search-api",
        max_search_results=5
    )

    # 创建适配器
    adapter = GPT5SearchAdapter(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url
    )

    try:
        # 执行搜索
        query = "Python 异步编程最佳实践"
        print(f"\n查询: {query}")

        results = await adapter.search(query, max_results=5)

        print(f"\n✅ 搜索成功，找到 {len(results)} 个结果:\n")

        for idx, result in enumerate(results, 1):
            print(f"{idx}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   摘要: {result.snippet[:100]}...")
            print(f"   评分: {result.score:.2f}")
            print()

        return True

    except Exception as e:
        print(f"\n❌ 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await adapter.close()


async def test_llm_processor():
    """测试 LLM 查询分解功能 (gpt-4o)"""
    print("\n" + "=" * 60)
    print("测试 2: LLM Processor (gpt-4o)")
    print("=" * 60)

    # 配置
    config = NLSearchConfig(
        llm_api_key="sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f",
        llm_base_url="https://api.gpt.ge/v1",
        llm_model="gpt-4o",
        llm_max_tokens=500
    )

    # 创建处理器
    processor = LLMProcessor(config=config)

    try:
        # 测试查询解析
        query = "GPT-5最新发展趋势"
        print(f"\n查询: {query}")

        analysis = await processor.parse_query(query)

        if analysis:
            print("\n✅ 查询解析成功:\n")
            print(f"意图: {analysis.get('intent')}")
            print(f"关键词: {analysis.get('keywords')}")
            print(f"实体: {analysis.get('entities')}")
            print(f"分类: {analysis.get('category')}")
            print(f"置信度: {analysis.get('confidence')}")

            # 测试查询精炼
            refined = await processor.refine_query(query, analysis)
            print(f"\n精炼查询: {refined}")

            return True
        else:
            print("\n❌ 查询解析失败")
            return False

    except Exception as e:
        print(f"\n❌ LLM 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_integrated_workflow():
    """测试完整的集成工作流"""
    print("\n" + "=" * 60)
    print("测试 3: 集成工作流 (LLM + Search)")
    print("=" * 60)

    # 配置
    config = NLSearchConfig(
        llm_api_key="sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f",
        llm_base_url="https://api.gpt.ge/v1",
        llm_model="gpt-4o",
        search_model="gpt-5-search-api",
        max_search_results=3
    )

    # 创建组件
    processor = LLMProcessor(config=config)
    adapter = GPT5SearchAdapter(
        api_key=config.llm_api_key,
        base_url=config.llm_base_url
    )

    try:
        query = "最新的机器学习技术有哪些"
        print(f"\n原始查询: {query}")

        # Step 1: LLM 解析查询
        print("\n[1/3] 解析查询...")
        analysis = await processor.parse_query(query)

        if not analysis:
            print("   ⚠️  查询解析失败，使用原始查询")
            refined_query = query
        else:
            print(f"   ✓ 意图: {analysis.get('intent')}")
            print(f"   ✓ 关键词: {analysis.get('keywords')}")

            # Step 2: 精炼查询
            print("\n[2/3] 精炼查询...")
            refined_query = await processor.refine_query(query, analysis)
            print(f"   ✓ 精炼查询: {refined_query}")

        # Step 3: 执行搜索
        print("\n[3/3] 执行搜索...")
        results = await adapter.search(refined_query, max_results=3)

        print(f"\n✅ 集成流程成功！找到 {len(results)} 个结果:\n")

        for idx, result in enumerate(results, 1):
            print(f"{idx}. {result.title}")
            print(f"   {result.url}")
            print()

        return True

    except Exception as e:
        print(f"\n❌ 集成流程失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await adapter.close()


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("NL Search api.gpt.ge 集成测试")
    print("=" * 60)

    results = []

    # 测试 1: GPT-5 Search
    result1 = await test_gpt5_search()
    results.append(("GPT-5 Search API", result1))

    await asyncio.sleep(2)  # 避免速率限制

    # 测试 2: LLM Processor
    result2 = await test_llm_processor()
    results.append(("LLM Processor (gpt-4o)", result2))

    await asyncio.sleep(2)

    # 测试 3: 集成工作流
    result3 = await test_integrated_workflow()
    results.append(("Integrated Workflow", result3))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n🎉 所有测试通过！api.gpt.ge 架构升级成功")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
