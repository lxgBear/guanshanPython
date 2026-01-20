"""调试搜索流程"""
import sys
import os
import asyncio

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython/src')

from services.langgraph_search.config import LangGraphSearchConfig
from services.langgraph_search.nodes import (
    KeywordGeneratorNode,
    FirecrawlConfigNode,
    SimplifiedSearchNode,
)
from services.langgraph_search.state import create_initial_state

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-791acc51e2284efc9080a2bcf338565c")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")

async def debug_nodes():
    """逐步调试各个节点"""
    query = "四川阿坝红旗大桥垮塌 西方主流媒体 2025年11月"

    config = LangGraphSearchConfig(
        firecrawl_api_key=FIRECRAWL_API_KEY,
        claude_api_key=ANTHROPIC_API_KEY,
    )

    state = create_initial_state(
        query=query,
        user_id="debug_user",
        log_id="debug_search",
    )

    print("=== Step 1: KeywordGenerator ===")
    keyword_node = KeywordGeneratorNode(config=config)
    try:
        result = keyword_node(state)
        print(f"KeywordGenerator result keys: {list(result.keys())}")
        tiered = result.get("keyword_generation", {}).get("tiered_keywords", {})
        print(f"  tier_1 count: {len(tiered.get('tier_1', []))}")
        print(f"  tier_2 count: {len(tiered.get('tier_2', []))}")
        print(f"  tier_3 count: {len(tiered.get('tier_3', []))}")
        state.update(result)
    except Exception as e:
        print(f"KeywordGenerator ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n=== Step 2: FirecrawlConfig ===")
    config_node = FirecrawlConfigNode(config=config)
    try:
        result = config_node(state)
        print(f"FirecrawlConfig result keys: {list(result.keys())}")
        configs = result.get("firecrawl_search_config", [])
        print(f"  Generated {len(configs)} search configs")
        for i, cfg in enumerate(configs[:5]):
            print(f"    {i+1}. query: {cfg.get('query', 'N/A')}, limit: {cfg.get('limit', 0)}, tier: {cfg.get('tier', 'N/A')}")
        state.update(result)
    except Exception as e:
        print(f"FirecrawlConfig ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n=== Step 3: SimplifiedSearch ===")
    print("  This step may take time...")
    search_node = SimplifiedSearchNode(config=config, firecrawl_client=None)  # 使用 None 将跳过实际搜索
    try:
        result = search_node(state)
        print(f"SimplifiedSearch result keys: {list(result.keys())}")
        state.update(result)
    except Exception as e:
        print(f"SimplifiedSearch ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    asyncio.run(debug_nodes())
