"""
档案条目ID迁移脚本 - UUID字符串转雪花ID

功能:
- 扫描所有user_archives文档
- 识别使用UUID字符串ID的条目
- 转换为雪花ID (64位整数)
- 更新数据库记录

用法:
    python scripts/migrate_archive_item_ids.py --dry-run  # 预览要迁移的数据
    python scripts/migrate_archive_item_ids.py --execute  # 执行迁移
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_id
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ArchiveIDMigrator:
    """档案条目ID迁移器"""

    def __init__(self):
        self.db = None
        self.collection = None

    async def initialize(self):
        """初始化数据库连接"""
        self.db = await get_mongodb_database()
        self.collection = self.db["user_archives"]
        logger.info("数据库连接初始化成功")

    def is_uuid_string(self, value: Any) -> bool:
        """检查是否为UUID字符串"""
        if not isinstance(value, str):
            return False
        # UUID格式: 8-4-4-4-12 字符
        parts = value.split('-')
        return (
            len(parts) == 5 and
            len(parts[0]) == 8 and
            len(parts[1]) == 4 and
            len(parts[2]) == 4 and
            len(parts[3]) == 4 and
            len(parts[4]) == 12
        )

    async def find_archives_with_uuid_ids(self) -> List[Dict[str, Any]]:
        """查找使用UUID字符串ID的档案"""
        logger.info("🔍 扫描所有档案...")

        archives_to_migrate = []
        cursor = self.collection.find({})

        async for archive in cursor:
            archive_id = str(archive["_id"])
            items = archive.get("items", [])

            # 检查是否有UUID字符串ID
            has_uuid_ids = False
            uuid_count = 0

            for item in items:
                item_id = item.get("id")
                if self.is_uuid_string(item_id):
                    has_uuid_ids = True
                    uuid_count += 1

            if has_uuid_ids:
                archives_to_migrate.append({
                    "archive_id": archive_id,
                    "archive_name": archive.get("archive_name", "N/A"),
                    "user_id": archive.get("user_id"),
                    "total_items": len(items),
                    "uuid_items": uuid_count,
                    "items": items
                })

        logger.info(f"✅ 扫描完成，找到 {len(archives_to_migrate)} 个需要迁移的档案")
        return archives_to_migrate

    async def migrate_archive(self, archive_info: Dict[str, Any]) -> bool:
        """迁移单个档案的条目ID"""
        archive_id = archive_info["archive_id"]
        items = archive_info["items"]

        # 创建ID映射表
        id_mapping = {}
        new_items = []

        for item in items:
            old_id = item.get("id")
            new_item = item.copy()

            if self.is_uuid_string(old_id):
                # 生成新的雪花ID
                new_id = generate_id()
                id_mapping[old_id] = new_id
                new_item["id"] = new_id
                logger.debug(f"  UUID → Snowflake: {old_id} → {new_id}")
            else:
                # 已经是整数ID，保持不变
                new_item["id"] = old_id

            new_items.append(new_item)

        # 更新数据库
        from bson import ObjectId

        result = await self.collection.update_one(
            {"_id": ObjectId(archive_id)},
            {
                "$set": {
                    "items": new_items,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"✅ 档案 {archive_id} 迁移成功，转换了 {len(id_mapping)} 个ID")
            return True
        else:
            logger.warning(f"⚠️ 档案 {archive_id} 未修改")
            return False

    async def dry_run(self):
        """预览迁移 - 不执行实际修改"""
        logger.info("🔍 开始预览模式（不会修改数据）...\n")

        archives = await self.find_archives_with_uuid_ids()

        if not archives:
            logger.info("✅ 没有需要迁移的档案")
            return

        print(f"\n📊 发现 {len(archives)} 个档案需要迁移:\n")

        for idx, archive in enumerate(archives, 1):
            print(f"{idx}. 档案ID: {archive['archive_id']}")
            print(f"   名称: {archive['archive_name']}")
            print(f"   用户: {archive['user_id']}")
            print(f"   总条目数: {archive['total_items']}")
            print(f"   需迁移: {archive['uuid_items']} 个UUID条目")
            print()

        print(f"\n💡 运行 '--execute' 参数执行实际迁移")

    async def execute_migration(self):
        """执行迁移"""
        logger.info("🚀 开始执行迁移...\n")

        archives = await self.find_archives_with_uuid_ids()

        if not archives:
            logger.info("✅ 没有需要迁移的档案")
            return

        logger.info(f"📊 共 {len(archives)} 个档案需要迁移\n")

        success_count = 0
        failed_count = 0

        for idx, archive in enumerate(archives, 1):
            archive_id = archive['archive_id']
            print(f"\n[{idx}/{len(archives)}] 迁移档案: {archive_id}")
            print(f"  名称: {archive['archive_name']}")
            print(f"  UUID条目数: {archive['uuid_items']}")

            try:
                success = await self.migrate_archive(archive)
                if success:
                    success_count += 1
                    print(f"  ✅ 迁移成功")
                else:
                    failed_count += 1
                    print(f"  ⚠️ 迁移失败或无需更新")
            except Exception as e:
                failed_count += 1
                logger.error(f"  ❌ 迁移失败: {e}")

        print(f"\n" + "="*60)
        print(f"📊 迁移完成:")
        print(f"  ✅ 成功: {success_count}")
        print(f"  ❌ 失败: {failed_count}")
        print(f"  📋 总计: {len(archives)}")
        print("="*60)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="档案条目ID迁移工具")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式 - 只显示需要迁移的数据，不执行修改"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行模式 - 实际执行迁移操作"
    )

    args = parser.parse_args()

    # 如果没有提供任何参数，显示帮助信息
    if not args.dry_run and not args.execute:
        parser.print_help()
        print("\n💡 提示:")
        print("  1. 先运行 --dry-run 预览要迁移的数据")
        print("  2. 确认无误后运行 --execute 执行迁移")
        sys.exit(0)

    # 初始化迁移器
    migrator = ArchiveIDMigrator()
    await migrator.initialize()

    try:
        if args.dry_run:
            await migrator.dry_run()
        elif args.execute:
            await migrator.execute_migration()

    except Exception as e:
        logger.error(f"❌ 操作失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
