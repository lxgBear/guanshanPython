#!/usr/bin/env python3
"""
搜索并保存结果脚本

功能:
1. 使用 Claude 查询优化 + Firecrawl 搜索
2. 不限制搜索结果数量
3. 保存所有搜索结果到本地 JSON 文件
4. v1.1.0: 多语言搜索支持 (中/英/日/韩)

用法:
    python scripts/search_and_save.py "东亚 政外"
    python scripts/search_and_save.py "东亚 政外" --max-results 100
    python scripts/search_and_save.py "东亚 政外" --multilang  # 多语言搜索
"""
import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.services.nl_search.config import nl_search_config
from src.infrastructure.llm.claude_client import create_claude_client


async def search_and_save(query: str, max_results: int = 50, output_dir: str = "data/search_results", multilang: bool = False):
    """
    执行搜索并保存所有结果

    Args:
        query: 搜索查询
        max_results: 最大结果数 (默认50)
        output_dir: 输出目录
        multilang: 是否启用多语言搜索
    """
    print("=" * 70)
    print(f"🔍 搜索并保存结果")
    print("=" * 70)
    print(f"📝 查询: {query}")
    print(f"📊 最大结果数: {max_results}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🌐 多语言搜索: {'启用' if multilang else '禁用'}")
    print("-" * 70)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 1. 使用 Claude 解析查询
    print("\n🤖 Step 1: Claude 解析查询...")
    claude_client = None
    analysis = {}
    optimized_query = query
    multilang_queries = {}

    if nl_search_config.claude_enabled:
        try:
            claude_client = create_claude_client()
            analysis = await claude_client.parse_query(query)
            print(f"   ✅ 解析完成:")
            print(f"      - intent: {analysis.get('intent', 'N/A')}")
            print(f"      - keywords: {analysis.get('keywords', [])}")
            print(f"      - entities: {analysis.get('entities', [])}")

            # 优化查询
            keywords = analysis.get('keywords', [])
            if keywords and nl_search_config.enable_query_optimization:
                optimized_query = " ".join(keywords)
                print(f"   🔄 优化后查询: '{query}' → '{optimized_query}'")

            # 多语言查询翻译
            if multilang:
                print("\n🌐 Step 1.5: 生成多语言查询...")
                multilang_queries = await claude_client.generate_multilang_queries(
                    query=query,
                    languages=["zh", "en", "ja", "ko"]
                )
                print(f"   ✅ 多语言查询:")
                for lang, lang_query in multilang_queries.items():
                    lang_names = {"zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语"}
                    print(f"      [{lang_names.get(lang, lang)}] {lang_query}")

        except Exception as e:
            print(f"   ⚠️ Claude 解析失败: {e}")
            if multilang:
                # 降级: 使用原始查询
                multilang_queries = {"zh": query}
    else:
        print("   ⚠️ Claude 未启用，使用原始查询")
        if multilang:
            multilang_queries = {"zh": query}

    # 2. 执行搜索
    adapter = FirecrawlSearchAdapter(test_mode=False)

    if multilang and multilang_queries:
        # 多语言搜索
        print(f"\n🌐 Step 2: 多语言 Firecrawl 搜索...")
        try:
            multilang_result = await adapter.multi_language_search(
                query=query,
                multilang_queries=multilang_queries,
                max_results_per_lang=max_results // len(multilang_queries),
                auto_time_filter=True
            )
            results_list = multilang_result["all_results"]
            print(f"   ✅ 多语言搜索完成: 获得 {len(results_list)} 个去重结果")
        except Exception as e:
            print(f"   ❌ 多语言搜索失败: {e}")
            results_list = []
            multilang_result = {}
    else:
        # 单语言搜索
        print(f"\n🌐 Step 2: Firecrawl 搜索...")
        try:
            results = await adapter.search(
                query=optimized_query,
                max_results=max_results,
                auto_detect_location=True,
                scrape_content=False,
                auto_time_filter=True
            )
            print(f"   ✅ 搜索完成: 获得 {len(results)} 个结果")
            results_list = [r.to_dict() for r in results]
            multilang_result = {}
        except Exception as e:
            print(f"   ❌ 搜索失败: {e}")
            results_list = []
            multilang_result = {}

    # 3. 保存结果
    print(f"\n💾 Step 3: 保存结果...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query.replace(" ", "_").replace("/", "_")[:30]
    mode_suffix = "_multilang" if multilang else ""
    filename = f"{safe_query}_{timestamp}{mode_suffix}.json"
    filepath = os.path.join(output_dir, filename)

    output_data = {
        "query": query,
        "optimized_query": optimized_query,
        "multilang_enabled": multilang,
        "multilang_queries": multilang_queries if multilang else {},
        "timestamp": datetime.now().isoformat(),
        "config": {
            "max_results": max_results,
            "claude_enabled": nl_search_config.claude_enabled,
            "query_optimization": nl_search_config.enable_query_optimization,
            "time_filter": nl_search_config.default_time_filter,
            "excluded_domains": nl_search_config.excluded_domains
        },
        "analysis": analysis,
        "result_count": len(results_list),
        "results": results_list
    }

    # 添加多语言搜索统计
    if multilang and multilang_result:
        output_data["multilang_stats"] = multilang_result.get("stats", {})
        output_data["results_by_lang"] = multilang_result.get("results_by_lang", {})

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"   ✅ 已保存到: {filepath}")

    # 4. 显示结果摘要
    print(f"\n📊 结果摘要:")
    print("-" * 70)

    if results_list:
        for i, r in enumerate(results_list[:10], 1):
            title = r.get('title', 'N/A')[:50]
            url = r.get('url', 'N/A')[:60]
            score = r.get('score', 0)
            source = r.get('source', '')
            print(f"[{i:2d}] [{score:.2f}] [{source}] {title}")
            print(f"     {url}")

        if len(results_list) > 10:
            print(f"\n     ... 还有 {len(results_list) - 10} 个结果 (详见 {filename})")

    print("\n" + "=" * 70)
    print(f"✅ 搜索完成! 共 {len(results_list)} 个结果已保存")
    print("=" * 70)

    return filepath, results_list


def main():
    parser = argparse.ArgumentParser(description="搜索并保存结果")
    parser.add_argument("query", help="搜索查询")
    parser.add_argument("--max-results", "-n", type=int, default=50, help="最大结果数 (默认50)")
    parser.add_argument("--output-dir", "-o", default="data/search_results", help="输出目录")
    parser.add_argument("--multilang", "-m", action="store_true", help="启用多语言搜索 (中/英/日/韩)")

    args = parser.parse_args()

    filepath, results = asyncio.run(
        search_and_save(
            query=args.query,
            max_results=args.max_results,
            output_dir=args.output_dir,
            multilang=args.multilang
        )
    )

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
