#!/usr/bin/env python3
"""
NL Search MongoDB 索引创建脚本

用于为 nl_search_logs 和 user_selection_events 集合创建优化索引，
提升查询性能。

版本: v1.0.0
日期: 2025-11-17
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.mongo_nl_search_repository import MongoNLSearchLogRepository
from src.infrastructure.database.user_selection_repository import UserSelectionEventRepository


async def create_all_indexes():
    """创建所有 NL Search 相关索引"""
    print("=" * 60)
    print("NL Search MongoDB 索引创建工具")
    print("=" * 60)
    print()

    try:
        # 1. 创建 nl_search_logs 索引
        print("📋 [1/2] 创建 nl_search_logs 集合索引...")
        nl_search_repo = MongoNLSearchLogRepository()
        await nl_search_repo.create_indexes()
        print("✅ nl_search_logs 索引创建完成")
        print()

        # 2. 创建 user_selection_events 索引
        print("📋 [2/2] 创建 user_selection_events 集合索引...")
        selection_repo = UserSelectionEventRepository()
        await selection_repo.create_indexes()
        print("✅ user_selection_events 索引创建完成")
        print()

        print("=" * 60)
        print("✅ 所有索引创建成功！")
        print("=" * 60)
        print()
        print("创建的索引列表:")
        print()
        print("nl_search_logs 集合:")
        print("  1. created_at_desc - 创建时间倒序索引")
        print("  2. user_created_idx - 用户+创建时间复合索引")
        print("  3. status_idx - 状态索引")
        print("  4. query_text_idx - 查询文本全文索引")
        print()
        print("user_selection_events 集合:")
        print("  1. log_time_idx - log_id+时间复合索引")
        print("  2. user_time_idx - user_id+时间复合索引")
        print("  3. time_idx - 时间倒序索引")
        print()

    except Exception as e:
        print(f"❌ 索引创建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    try:
        # 运行异步任务
        asyncio.run(create_all_indexes())
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
