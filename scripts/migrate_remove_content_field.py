#!/usr/bin/env python3
"""数据库迁移脚本：移除 content 字段

目标：
1. 从 search_results 集合移除 content 字段
2. 从 instant_search_results 集合移除 content 字段
3. 保留 markdown_content 作为主要内容字段

原因：
- content 和 markdown_content 内容重复/冲突
- content 通常是 markdown_content 的截断版本
- 统一使用 markdown_content 可以减少数据冗余

注意事项：
- 此操作不可逆（除非有备份）
- 移除前建议先备份数据库
- processed_results_new 集合保持不变（暂不修改）
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_content_field_usage():
    """分析 content 字段的使用情况"""
    print("\n" + "=" * 60)
    print("📊 分析 content 字段使用情况")
    print("=" * 60)

    db = await get_mongodb_database()

    # 分析 search_results
    print("\n[1] search_results 集合:")
    try:
        search_results = db["search_results"]
        total = await search_results.count_documents({})
        with_content = await search_results.count_documents({"content": {"$exists": True, "$ne": ""}})
        with_markdown = await search_results.count_documents({"markdown_content": {"$exists": True, "$ne": None}})

        print(f"   总记录数: {total}")
        print(f"   有 content 字段: {with_content}")
        print(f"   有 markdown_content 字段: {with_markdown}")

        # 采样分析
        if total > 0:
            sample = await search_results.find_one({"content": {"$exists": True}})
            if sample:
                content_len = len(sample.get("content", ""))
                markdown_len = len(sample.get("markdown_content", "") or "")
                print(f"   示例记录:")
                print(f"     content 长度: {content_len} 字符")
                print(f"     markdown_content 长度: {markdown_len} 字符")

    except Exception as e:
        print(f"   ❌ 分析失败: {e}")

    # 分析 instant_search_results
    print("\n[2] instant_search_results 集合:")
    try:
        instant_results = db["instant_search_results"]
        total = await instant_results.count_documents({})
        with_content = await instant_results.count_documents({"content": {"$exists": True, "$ne": ""}})
        with_markdown = await instant_results.count_documents({"markdown_content": {"$exists": True, "$ne": None}})

        print(f"   总记录数: {total}")
        print(f"   有 content 字段: {with_content}")
        print(f"   有 markdown_content 字段: {with_markdown}")

        # 采样分析
        if total > 0:
            sample = await instant_results.find_one({"content": {"$exists": True}})
            if sample:
                content_len = len(sample.get("content", ""))
                markdown_len = len(sample.get("markdown_content", "") or "")
                print(f"   示例记录:")
                print(f"     content 长度: {content_len} 字符")
                print(f"     markdown_content 长度: {markdown_len} 字符")

    except Exception as e:
        print(f"   ❌ 分析失败: {e}")

    print("\n" + "=" * 60)


async def remove_content_field_from_search_results():
    """从 search_results 集合移除 content 字段"""
    print("\n" + "=" * 60)
    print("🗑️  移除 search_results.content 字段")
    print("=" * 60)

    db = await get_mongodb_database()
    collection = db["search_results"]

    try:
        # 统计移除前的情况
        total = await collection.count_documents({})
        with_field = await collection.count_documents({"content": {"$exists": True}})

        print(f"\n移除前统计:")
        print(f"  总记录数: {total}")
        print(f"  有 content 字段: {with_field}")

        if with_field == 0:
            print("\n✅ 没有记录包含 content 字段，无需移除")
            return

        # 执行移除
        print(f"\n开始移除 content 字段...")
        result = await collection.update_many(
            {"content": {"$exists": True}},
            {"$unset": {"content": ""}}
        )

        print(f"\n✅ 移除完成:")
        print(f"  修改记录数: {result.modified_count}")

        # 验证
        remaining = await collection.count_documents({"content": {"$exists": True}})
        print(f"  剩余 content 字段: {remaining}")

        if remaining == 0:
            print("\n🎉 search_results.content 字段已完全移除")
        else:
            print(f"\n⚠️  仍有 {remaining} 条记录包含 content 字段")

    except Exception as e:
        print(f"\n❌ 移除失败: {e}")
        raise

    print("=" * 60)


async def remove_content_field_from_instant_search_results():
    """从 instant_search_results 集合移除 content 字段"""
    print("\n" + "=" * 60)
    print("🗑️  移除 instant_search_results.content 字段")
    print("=" * 60)

    db = await get_mongodb_database()
    collection = db["instant_search_results"]

    try:
        # 统计移除前的情况
        total = await collection.count_documents({})
        with_field = await collection.count_documents({"content": {"$exists": True}})

        print(f"\n移除前统计:")
        print(f"  总记录数: {total}")
        print(f"  有 content 字段: {with_field}")

        if with_field == 0:
            print("\n✅ 没有记录包含 content 字段，无需移除")
            return

        # 执行移除
        print(f"\n开始移除 content 字段...")
        result = await collection.update_many(
            {"content": {"$exists": True}},
            {"$unset": {"content": ""}}
        )

        print(f"\n✅ 移除完成:")
        print(f"  修改记录数: {result.modified_count}")

        # 验证
        remaining = await collection.count_documents({"content": {"$exists": True}})
        print(f"  剩余 content 字段: {remaining}")

        if remaining == 0:
            print("\n🎉 instant_search_results.content 字段已完全移除")
        else:
            print(f"\n⚠️  仍有 {remaining} 条记录包含 content 字段")

    except Exception as e:
        print(f"\n❌ 移除失败: {e}")
        raise

    print("=" * 60)


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🔧 数据库迁移：移除 content 字段")
    print("=" * 60)

    # 步骤 1: 分析当前情况
    await analyze_content_field_usage()

    # 询问用户确认
    print("\n⚠️  警告：此操作将永久删除 content 字段数据")
    print("建议：移除前请先备份数据库")
    print("\n是否继续？")
    print("  [1] 继续执行迁移")
    print("  [2] 仅分析，不执行")
    print("  [3] 退出")

    try:
        choice = input("\n请选择 (1/2/3): ").strip()
    except KeyboardInterrupt:
        print("\n\n❌ 用户取消操作")
        return

    if choice == "1":
        print("\n开始执行迁移...")

        # 步骤 2: 移除 search_results.content
        await remove_content_field_from_search_results()

        # 步骤 3: 移除 instant_search_results.content
        await remove_content_field_from_instant_search_results()

        print("\n" + "=" * 60)
        print("✅ 迁移完成")
        print("=" * 60)
        print("\n后续步骤:")
        print("1. 更新代码中的实体定义（移除 content 字段）")
        print("2. 更新所有使用 content 的代码改用 markdown_content")
        print("3. 运行测试验证功能正常")
        print("=" * 60)

    elif choice == "2":
        print("\n✅ 仅执行了分析，未修改数据")

    else:
        print("\n❌ 取消操作")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
