#!/usr/bin/env python3
"""
Claude Search Agent v2.1 测试脚本

v2.1 新特性:
- country 参数 (ISO 国家代码)
- 查询运算符 (-wikipedia, "精确匹配")
- source_tier 来源分类
- 可信度评分
- 增强输出格式

用法:
    python scripts/search_with_agent_v2_1.py "东亚 政外"
    python scripts/search_with_agent_v2_1.py "中东局势" --save
    python scripts/search_with_agent_v2_1.py "欧洲经济" --save -o data/v21_results
"""
import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.nl_search.claude_search_agent_v2_1 import ClaudeSearchAgentV21


async def search_v21(query: str, save: bool = False, output_dir: str = "data/agent_v21_results"):
    """执行 v2.1 智能搜索"""
    print("\n" + "=" * 80)
    print("🚀 Claude Search Agent v2.1 测试")
    print("=" * 80)
    print(f"📝 查询: {query}")
    print(f"💾 保存: {'是' if save else '否'}")
    print("-" * 80)

    agent = ClaudeSearchAgentV21(test_mode=False)

    try:
        result = await agent.search(query)

        if save:
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = query.replace(" ", "_").replace("/", "_")[:30]
            filename = f"v21_{safe_query}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"\n💾 已保存: {filepath}")

        return result

    except Exception as e:
        print(f"\n❌ 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(description="Claude Search Agent v2.1")
    parser.add_argument("query", help="搜索查询")
    parser.add_argument("--save", "-s", action="store_true", help="保存结果")
    parser.add_argument("--output-dir", "-o", default="data/agent_v21_results", help="输出目录")

    args = parser.parse_args()
    result = asyncio.run(search_v21(args.query, args.save, args.output_dir))

    if result:
        stats = result.get("stats", {})
        print("\n" + "=" * 80)
        print("✅ v2.1 搜索完成!")
        print(f"   配置数: {stats.get('configs_count', 0)}")
        print(f"   结果数: {stats.get('total_results', 0)}")
        print(f"   耗时: {stats.get('execution_time', 0)}s")

        # 来源层级分布
        tier_stats = stats.get("by_source_tier", {})
        if tier_stats:
            print("\n📊 来源层级分布:")
            tier_labels = {
                "official": "官方来源",
                "local_mainstream": "当地主流",
                "intl_mainstream": "国际主流",
                "think_tank": "智库分析",
                "other": "其他",
            }
            for tier, count in tier_stats.items():
                if count > 0:
                    label = tier_labels.get(tier, tier)
                    print(f"   {label}: {count} 条")

        print("=" * 80)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
