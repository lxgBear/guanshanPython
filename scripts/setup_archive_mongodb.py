#!/usr/bin/env python3
"""
档案管理 MongoDB 集合创建和索引脚本

用途: 创建 user_archives 集合并创建索引
作者: Archive System Setup
日期: 2025-11-17
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.mongo_nl_user_archive_repository import MongoNLUserArchiveRepository


async def main():
    """主函数"""
    print("="*60)
    print("档案管理系统 - MongoDB 集合和索引创建")
    print("="*60)

    try:
        repo = MongoNLUserArchiveRepository()

        print("\n🚀 开始创建索引...")
        await repo.create_indexes()

        print("\n✅ 索引创建完成！")
        print("\n📊 已创建的索引:")
        print("  1. 用户ID + 创建时间复合索引 (user_id, created_at)")
        print("  2. 搜索记录关联索引 (search_log_id)")
        print("  3. 标签索引 (tags)")

        print("\n" + "="*60)
        print("✅ MongoDB 档案管理系统已就绪！")
        print("="*60)

        print("\n📋 集合信息:")
        print(f"  集合名称: user_archives")
        print(f"  数据库: guanshan (线上MongoDB)")
        print(f"  存储方式: 嵌入式文档（档案和条目在同一文档）")

        return 0

    except Exception as e:
        print(f"\n❌ 脚本执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
