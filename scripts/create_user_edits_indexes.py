#!/usr/bin/env python3
"""
用户编辑结果表索引创建脚本

用于为 user_edited_results 集合创建优化索引

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.user_edit_repository import user_edit_repository


async def create_indexes():
    """创建所有索引"""
    print("=" * 60)
    print("用户编辑结果表索引创建工具")
    print("=" * 60)
    print()

    try:
        print("📋 创建 user_edited_results 集合索引...")
        print()

        await user_edit_repository.create_indexes()

        print()
        print("=" * 60)
        print("✅ 所有索引创建成功！")
        print("=" * 60)
        print()
        print("创建的索引列表:")
        print()
        print("user_edited_results 集合:")
        print("  1. editor_time_idx - 编辑人+编辑时间复合索引")
        print("  2. source_ref_idx - 来源记录引用索引")
        print("  3. task_edited_idx - 任务+编辑时间复合索引")
        print("  4. created_desc_idx - 创建时间倒序索引")
        print("  5. fulltext_idx - 标题和内容全文搜索索引")
        print()

        print("💡 提示:")
        print("  - 批量编辑功能现在可以使用了")
        print("  - 查询性能已优化")
        print("  - 支持按编辑人、任务、时间快速查询")
        print()

    except Exception as e:
        print(f"❌ 索引创建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    try:
        asyncio.run(create_indexes())
    except KeyboardInterrupt:
        print("\n\n⚠️  索引创建被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
