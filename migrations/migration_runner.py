"""
数据库迁移运行器

负责执行迁移脚本、跟踪迁移状态、支持回滚操作。
"""

import importlib
import pkgutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Type
from motor.motor_asyncio import AsyncIOMotorDatabase

from .base_migration import BaseMigration
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MigrationRunner:
    """数据库迁移运行器"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.migrations_collection = db['schema_migrations']

    async def init_migration_tracking(self):
        """初始化迁移跟踪集合"""
        await self.migrations_collection.create_index("version", unique=True)
        logger.info("✅ 迁移跟踪系统已初始化")

    async def get_applied_migrations(self) -> List[str]:
        """获取已应用的迁移版本列表"""
        migrations = await self.migrations_collection.find().sort("version", 1).to_list(1000)
        return [m['version'] for m in migrations]

    async def record_migration(self, migration: BaseMigration, result: dict):
        """记录迁移执行"""
        await self.migrations_collection.update_one(
            {'version': migration.version},
            {
                '$set': {
                    'version': migration.version,
                    'description': migration.description,
                    'applied_at': datetime.utcnow(),
                    'result': result
                }
            },
            upsert=True
        )
        logger.info(f"✅ 记录迁移: {migration.version} - {migration.description}")

    async def remove_migration_record(self, version: str):
        """移除迁移记录（用于回滚）"""
        await self.migrations_collection.delete_one({'version': version})
        logger.info(f"🔙 移除迁移记录: {version}")

    def discover_migrations(self) -> List[Type[BaseMigration]]:
        """
        自动发现所有迁移类

        Returns:
            List[Type[BaseMigration]]: 迁移类列表，按版本号排序
        """
        migrations = []
        migrations_dir = Path(__file__).parent / 'versions'

        if not migrations_dir.exists():
            logger.warning(f"迁移目录不存在: {migrations_dir}")
            return migrations

        # 导入 migrations.versions 包下的所有模块
        for importer, module_name, is_pkg in pkgutil.iter_modules([str(migrations_dir)]):
            if module_name.startswith('_'):
                continue

            try:
                module = importlib.import_module(f'migrations.versions.{module_name}')

                # 查找 BaseMigration 的子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, BaseMigration) and
                        attr != BaseMigration):
                        migrations.append(attr)

            except Exception as e:
                logger.error(f"加载迁移模块失败 {module_name}: {e}")

        # 按版本号排序
        migrations.sort(key=lambda m: m.version)
        return migrations

    async def run_migrations(self, target_version: Optional[str] = None) -> Dict[str, any]:
        """
        执行迁移

        Args:
            target_version: 目标版本号，None表示执行所有未应用的迁移

        Returns:
            dict: 执行结果统计
        """
        await self.init_migration_tracking()

        applied = await self.get_applied_migrations()
        all_migrations = self.discover_migrations()

        # 实例化迁移类
        migration_instances = [MigrationClass(self.db) for MigrationClass in all_migrations]

        # 过滤出需要执行的迁移
        pending = [
            m for m in migration_instances
            if m.version not in applied and
            (target_version is None or m.version <= target_version)
        ]

        if not pending:
            logger.info("✅ 没有待执行的迁移")
            return {'executed': 0, 'skipped': len(applied)}

        logger.info(f"📋 发现 {len(pending)} 个待执行迁移")

        executed_count = 0
        results = []

        for migration in pending:
            try:
                logger.info(f"🔄 执行迁移: {migration.version} - {migration.description}")

                # 执行迁移
                migration.executed_at = datetime.utcnow()
                result = await migration.upgrade()

                # 验证迁移结果
                if not await migration.validate():
                    raise Exception(f"迁移验证失败: {migration.version}")

                # 记录迁移
                await self.record_migration(migration, result)

                executed_count += 1
                results.append({
                    'version': migration.version,
                    'description': migration.description,
                    'result': result
                })

                logger.info(f"✅ 迁移成功: {migration.version}")

            except Exception as e:
                logger.error(f"❌ 迁移失败: {migration.version} - {e}")
                raise

        logger.info(f"🎉 迁移完成: 执行了 {executed_count} 个迁移")

        return {
            'executed': executed_count,
            'skipped': len(applied),
            'results': results
        }

    async def rollback_migration(self, version: str) -> Dict[str, any]:
        """
        回滚指定版本的迁移

        Args:
            version: 要回滚的版本号

        Returns:
            dict: 回滚结果
        """
        applied = await self.get_applied_migrations()

        if version not in applied:
            logger.warning(f"⚠️ 迁移未应用，无需回滚: {version}")
            return {'rolled_back': False, 'reason': 'not_applied'}

        # 查找迁移类
        all_migrations = self.discover_migrations()
        migration_class = next((m for m in all_migrations if m.version == version), None)

        if not migration_class:
            raise Exception(f"未找到迁移类: {version}")

        try:
            migration = migration_class(self.db)
            logger.info(f"🔙 回滚迁移: {version} - {migration.description}")

            # 执行回滚
            result = await migration.downgrade()

            # 移除迁移记录
            await self.remove_migration_record(version)

            logger.info(f"✅ 回滚成功: {version}")

            return {
                'rolled_back': True,
                'version': version,
                'result': result
            }

        except Exception as e:
            logger.error(f"❌ 回滚失败: {version} - {e}")
            raise

    async def get_migration_status(self) -> Dict[str, any]:
        """
        获取迁移状态

        Returns:
            dict: 迁移状态信息
        """
        applied = await self.get_applied_migrations()
        all_migrations = self.discover_migrations()

        pending = [
            {'version': m.version, 'description': m.description}
            for MigrationClass in all_migrations
            for m in [MigrationClass(self.db)]
            if m.version not in applied
        ]

        applied_details = []
        for version in applied:
            record = await self.migrations_collection.find_one({'version': version})
            if record:
                applied_details.append({
                    'version': record['version'],
                    'description': record['description'],
                    'applied_at': record['applied_at'].isoformat()
                })

        return {
            'applied_count': len(applied),
            'pending_count': len(pending),
            'applied': applied_details,
            'pending': pending
        }
