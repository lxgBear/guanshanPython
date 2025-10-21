#!/usr/bin/env python3
"""
数据库迁移命令行工具

使用方法:
    python scripts/run_migrations.py migrate        # 执行所有待执行的迁移
    python scripts/run_migrations.py migrate 001    # 执行到指定版本的迁移
    python scripts/run_migrations.py rollback 001   # 回滚指定版本的迁移
    python scripts/run_migrations.py status         # 查看迁移状态
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from migrations.migration_runner import MigrationRunner
from src.config import settings


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    # 连接数据库
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    # 创建迁移运行器
    runner = MigrationRunner(db)

    try:
        if command == "migrate":
            # 执行迁移
            target_version = sys.argv[2] if len(sys.argv) > 2 else None

            print("🚀 开始执行数据库迁移...")
            print("=" * 60)

            result = await runner.run_migrations(target_version)

            print("\n" + "=" * 60)
            print("✅ 迁移执行完成")
            print(f"   已执行: {result['executed']} 个迁移")
            print(f"   已跳过: {result['skipped']} 个迁移")

            if result.get('results'):
                print("\n📋 执行详情:")
                for r in result['results']:
                    print(f"   ✅ {r['version']}: {r['description']}")
                    if 'message' in r['result']:
                        print(f"      {r['result']['message']}")

        elif command == "rollback":
            # 回滚迁移
            if len(sys.argv) < 3:
                print("❌ 请指定要回滚的版本号")
                print("   用法: python scripts/run_migrations.py rollback 001")
                sys.exit(1)

            version = sys.argv[2]

            print(f"🔙 开始回滚迁移: {version}")
            print("=" * 60)

            result = await runner.rollback_migration(version)

            print("\n" + "=" * 60)
            if result['rolled_back']:
                print(f"✅ 迁移回滚成功: {version}")
                if 'message' in result['result']:
                    print(f"   {result['result']['message']}")
            else:
                print(f"⚠️ 迁移未回滚: {result.get('reason', 'unknown')}")

        elif command == "status":
            # 查看迁移状态
            print("📊 数据库迁移状态")
            print("=" * 60)

            status = await runner.get_migration_status()

            print(f"\n已应用迁移: {status['applied_count']} 个")
            if status['applied']:
                for m in status['applied']:
                    print(f"  ✅ {m['version']}: {m['description']}")
                    print(f"     应用时间: {m['applied_at']}")

            print(f"\n待执行迁移: {status['pending_count']} 个")
            if status['pending']:
                for m in status['pending']:
                    print(f"  ⏳ {m['version']}: {m['description']}")
            else:
                print("  (无待执行迁移)")

        else:
            print(f"❌ 未知命令: {command}")
            print(__doc__)
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
