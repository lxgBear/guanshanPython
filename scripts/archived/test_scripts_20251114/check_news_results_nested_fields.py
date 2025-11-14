"""
检查 news_results 表中 news_results 嵌套字段的结构变化

分析最新记录，对比已知结构，发现新增字段
"""

import asyncio
import sys
import os
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def check_news_results_nested_structure():
    """检查 news_results 嵌套字段的结构"""

    print(f"\n{'='*80}")
    print(f"news_results 嵌套字段结构分析")
    print(f"{'='*80}")

    try:
        db = await get_mongodb_database()
        collection = db['news_results']

        # 统计总记录数
        total_count = await collection.count_documents({})
        print(f"\n📊 总记录数: {total_count}")

        # 查询最新的 10 条有 news_results 字段的记录
        print(f"\n🔍 查询包含 news_results 嵌套字段的最新记录...")
        cursor = collection.find(
            {"news_results": {"$exists": True, "$ne": None}}
        ).sort("created_at", -1).limit(10)

        results = await cursor.to_list(length=10)

        if not results:
            print(f"❌ 未找到包含 news_results 字段的记录")
            return

        print(f"✅ 找到 {len(results)} 条包含 news_results 的记录")

        # 已知的字段结构（v2.0.2）
        known_fields = {
            "title",
            "published_at",
            "source",
            "content",
            "category"
        }

        # 统计所有出现的字段
        all_fields = defaultdict(int)
        field_types = defaultdict(set)
        field_samples = defaultdict(list)

        print(f"\n{'='*80}")
        print(f"📝 分析每条记录的 news_results 字段结构")
        print(f"{'='*80}")

        for idx, result in enumerate(results, 1):
            news_results = result.get('news_results', {})

            print(f"\n记录 #{idx}")
            print(f"  ID: {result.get('_id')}")
            print(f"  创建时间: {result.get('created_at')}")
            print(f"  news_results 字段:")

            if not isinstance(news_results, dict):
                print(f"    ⚠️  不是字典类型: {type(news_results)}")
                continue

            # 统计字段
            for field_name, field_value in news_results.items():
                all_fields[field_name] += 1
                field_types[field_name].add(type(field_value).__name__)

                # 收集样本值（限制长度）
                if len(field_samples[field_name]) < 3:
                    if isinstance(field_value, str):
                        sample = field_value[:100] if len(field_value) > 100 else field_value
                    elif isinstance(field_value, dict):
                        sample = f"{{dict with {len(field_value)} keys}}"
                    elif isinstance(field_value, list):
                        sample = f"[list with {len(field_value)} items]"
                    else:
                        sample = str(field_value)
                    field_samples[field_name].append(sample)

                # 打印字段信息
                value_preview = str(field_value)[:80] if field_value is not None else "None"
                print(f"    - {field_name}: {value_preview}")

        # 汇总分析
        print(f"\n{'='*80}")
        print(f"📊 字段统计汇总")
        print(f"{'='*80}")

        print(f"\n总共发现 {len(all_fields)} 个不同的字段\n")

        # 已知字段
        print(f"✅ 已知字段（v2.0.2）:")
        for field in sorted(known_fields):
            if field in all_fields:
                count = all_fields[field]
                types = ', '.join(sorted(field_types[field]))
                print(f"   - {field:<20} 出现: {count}/{len(results)} 次   类型: {types}")
            else:
                print(f"   - {field:<20} ❌ 未在样本中出现")

        # 新增字段
        new_fields = set(all_fields.keys()) - known_fields
        if new_fields:
            print(f"\n🆕 新增字段（{len(new_fields)}个）:")
            for field in sorted(new_fields):
                count = all_fields[field]
                types = ', '.join(sorted(field_types[field]))
                print(f"   - {field:<20} 出现: {count}/{len(results)} 次   类型: {types}")

                # 显示样本值
                if field_samples[field]:
                    print(f"     样本值:")
                    for sample in field_samples[field][:2]:
                        print(f"       • {sample}")
        else:
            print(f"\n✅ 未发现新增字段（结构与 v2.0.2 一致）")

        # 字段类型详情
        print(f"\n{'='*80}")
        print(f"📋 完整字段类型详情")
        print(f"{'='*80}")

        for field in sorted(all_fields.keys()):
            count = all_fields[field]
            coverage = (count / len(results)) * 100
            types = ', '.join(sorted(field_types[field]))
            status = "🆕 新增" if field not in known_fields else "✅ 已知"

            print(f"\n{status} {field}")
            print(f"   出现率: {count}/{len(results)} ({coverage:.1f}%)")
            print(f"   类型: {types}")

            if field_samples[field]:
                print(f"   样本:")
                for sample in field_samples[field][:3]:
                    print(f"     • {sample}")

        # 生成实体更新建议
        if new_fields:
            print(f"\n{'='*80}")
            print(f"💡 实体定义更新建议")
            print(f"{'='*80}")

            print(f"\n建议在 src/core/domain/entities/processed_result.py 中更新 news_results 结构注释:")
            print(f"\n```python")
            print(f"# news_results 结构示例（v2.0.3）：")
            print(f"# {{")

            # 生成示例结构
            all_fields_sorted = sorted(all_fields.keys())
            for field in all_fields_sorted:
                types = field_types[field]
                type_str = types.pop() if len(types) == 1 else f"Union[{', '.join(sorted(types))}]"

                if field_samples[field]:
                    sample = field_samples[field][0]
                    if isinstance(sample, str) and not sample.startswith('{') and not sample.startswith('['):
                        comment = f'  # 示例: "{sample[:50]}..."' if len(sample) > 50 else f'  # 示例: "{sample}"'
                    else:
                        comment = f'  # 类型: {type_str}'
                else:
                    comment = f'  # 类型: {type_str}'

                status = "# 🆕 新增" if field not in known_fields else ""
                print(f'#     "{field}": ...,  {comment} {status}')

            print(f"# }}")
            print(f"```")

            # 生成 TypedDict 建议
            print(f"\n或者创建 TypedDict 定义:")
            print(f"\n```python")
            print(f"from typing import TypedDict, Optional")
            print(f"\nclass NewsResultsDict(TypedDict, total=False):")
            print(f'    """news_results 嵌套字段的类型定义（v2.0.3）"""')

            for field in all_fields_sorted:
                types = field_types[field]

                # 判断类型
                if 'dict' in types:
                    type_hint = "Dict[str, Any]"
                elif 'list' in types:
                    type_hint = "List[Any]"
                elif 'str' in types:
                    type_hint = "str"
                elif 'int' in types:
                    type_hint = "int"
                elif 'float' in types:
                    type_hint = "float"
                elif 'datetime' in types:
                    type_hint = "datetime"
                else:
                    type_hint = "Any"

                # 检查是否所有记录都有这个字段
                if all_fields[field] < len(results):
                    type_hint = f"Optional[{type_hint}]"

                status_comment = "  # 🆕 v2.0.3 新增" if field not in known_fields else ""
                print(f"    {field}: {type_hint}{status_comment}")

            print(f"```")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    await check_news_results_nested_structure()


if __name__ == "__main__":
    asyncio.run(main())
