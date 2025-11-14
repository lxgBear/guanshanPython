#!/usr/bin/env python3
"""
测试语言过滤功能

测试场景：
1. 使用中文关键词 + lang=en → 验证返回结果语言
2. 使用英文关键词 + lang=en → 验证返回结果语言
3. 分析Firecrawl API的lang参数作用机制
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.core.domain.entities.search_config import UserSearchConfig


async def test_language_filter():
    """测试语言过滤"""

    adapter = FirecrawlSearchAdapter()

    print("\n" + "="*70)
    print("语言过滤测试")
    print("="*70)

    # 测试1: 中文关键词 + lang=en
    print("\n【测试1】中文关键词 + lang=en")
    print("-"*70)

    config1 = UserSearchConfig(
        overrides={
            'limit': 3,
            'language': 'en'
        }
    )

    print(f"配置: language=en, limit=3")
    print(f"查询: 特朗普 关税")

    try:
        result1 = await adapter.search("特朗普 关税", config1)

        print(f"\n结果统计:")
        print(f"  总结果数: {result1.total_count}")
        print(f"  返回结果: {len(result1.results)}")

        print(f"\n结果详情:")
        for idx, r in enumerate(result1.results[:3], 1):
            print(f"\n  [{idx}] {r.title[:60]}")
            print(f"      URL: {r.url}")
            print(f"      语言: {r.language}")

            # 分析URL和标题语言
            is_chinese_url = any(x in r.url for x in ['.cn', '/zh', '/zh-', 'zh-Hans', 'zh-Hant'])
            has_chinese_chars = any('\u4e00' <= char <= '\u9fff' for char in r.title)

            if is_chinese_url:
                print(f"      ⚠️ URL包含中文标识")
            if has_chinese_chars:
                print(f"      ⚠️ 标题包含中文字符")

    except Exception as e:
        print(f"  ❌ 测试失败: {e}")

    # 测试2: 英文关键词 + lang=en
    print("\n" + "="*70)
    print("【测试2】英文关键词 + lang=en")
    print("-"*70)

    config2 = UserSearchConfig(
        overrides={
            'limit': 3,
            'language': 'en'
        }
    )

    print(f"配置: language=en, limit=3")
    print(f"查询: Trump tariff trade war")

    try:
        result2 = await adapter.search("Trump tariff trade war", config2)

        print(f"\n结果统计:")
        print(f"  总结果数: {result2.total_count}")
        print(f"  返回结果: {len(result2.results)}")

        print(f"\n结果详情:")
        for idx, r in enumerate(result2.results[:3], 1):
            print(f"\n  [{idx}] {r.title[:60]}")
            print(f"      URL: {r.url}")
            print(f"      语言: {r.language}")

            # 分析URL和标题语言
            is_chinese_url = any(x in r.url for x in ['.cn', '/zh', '/zh-', 'zh-Hans', 'zh-Hant'])
            has_chinese_chars = any('\u4e00' <= char <= '\u9fff' for char in r.title)

            if is_chinese_url:
                print(f"      ⚠️ URL包含中文标识")
            if has_chinese_chars:
                print(f"      ⚠️ 标题包含中文字符")

    except Exception as e:
        print(f"  ❌ 测试失败: {e}")

    # 总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)

    print("""
分析结论：
1. Firecrawl API的lang参数是一个"偏好"设置，不是硬性过滤
2. 当搜索关键词是中文时，即使lang=en，也会返回中文结果（匹配度优先）
3. 要获取特定语言的结果，需要：
   a) 使用对应语言的关键词
   b) 在查询中添加域名限制（如 site:*.com -site:*.cn）
   c) 在结果处理时根据metadata.language进行二次过滤

建议解决方案：
1. 如果用户设置language=en，自动在查询中排除中文域名
2. 在结果处理时添加语言过滤器
3. 在UI上提示用户使用对应语言的关键词以获得更好的结果
    """)


if __name__ == "__main__":
    asyncio.run(test_language_filter())
