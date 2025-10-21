"""
Migration 005: 创建 summary_report_versions 集合和索引

功能:
- 创建 summary_report_versions 集合（版本历史记录）
- 添加索引以优化版本查询和回滚操作

索引说明:
- idx_report_id: 按报告ID查询
- idx_version_number: 按版本号查询
- idx_created_at: 按创建时间排序
- idx_report_version: 复合索引（报告ID + 版本号，唯一约束）
"""

from migrations.base_migration import BaseMigration
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Migration005CreateSummaryReportVersionsCollection(BaseMigration):
    """创建 summary_report_versions 集合和索引"""

    version = "005"
    description = "创建 summary_report_versions 集合和索引"

    async def upgrade(self) -> dict:
        """执行迁移"""
        collection = self.db.summary_report_versions

        # 检查集合是否已存在
        collection_names = await self.db.list_collection_names()
        if "summary_report_versions" not in collection_names:
            await self.db.create_collection("summary_report_versions")
            logger.info("✅ 创建集合: summary_report_versions")
        else:
            logger.info("ℹ️ 集合已存在: summary_report_versions")

        created_count = 0

        # 单字段索引
        single_indexes = [
            ("report_id", 1),
            ("version_number", 1),
            ("created_at", -1),  # 降序，最新版本在前
        ]

        for field, direction in single_indexes:
            index_name = f"idx_{field}"
            try:
                await collection.create_index(
                    [(field, direction)],
                    name=index_name,
                    background=True
                )
                logger.info(f"✅ 创建索引: {index_name}")
                created_count += 1
            except Exception as e:
                logger.warning(f"⚠️ 索引创建失败或已存在: {index_name} - {e}")

        # 唯一复合索引：报告ID + 版本号（防止重复版本）
        try:
            await collection.create_index(
                [("report_id", 1), ("version_number", 1)],
                name="idx_report_version_unique",
                unique=True,
                background=True
            )
            logger.info("✅ 创建唯一复合索引: idx_report_version_unique")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 唯一索引创建失败或已存在: {e}")

        # 复合索引：报告ID + 创建时间（用于时间序列查询）
        try:
            await collection.create_index(
                [("report_id", 1), ("created_at", -1)],
                name="idx_report_created",
                background=True
            )
            logger.info("✅ 创建复合索引: idx_report_created")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 复合索引创建失败或已存在: {e}")

        return {
            'collection_created': "summary_report_versions" not in collection_names,
            'indexes_created': created_count,
            'message': f'成功创建集合和 {created_count} 个索引'
        }

    async def downgrade(self) -> dict:
        """回滚迁移"""
        collection = self.db.summary_report_versions

        # 删除所有索引
        try:
            await collection.drop_indexes()
            logger.info("✅ 删除所有索引")
        except Exception as e:
            logger.warning(f"⚠️ 删除索引失败: {e}")

        # 删除集合
        try:
            await self.db.drop_collection("summary_report_versions")
            logger.info("✅ 删除集合: summary_report_versions")
        except Exception as e:
            logger.warning(f"⚠️ 删除集合失败: {e}")

        return {
            'collection_dropped': True,
            'message': '成功回滚迁移'
        }

    async def validate(self) -> bool:
        """验证迁移结果"""
        collection_names = await self.db.list_collection_names()
        if "summary_report_versions" not in collection_names:
            logger.error("❌ 验证失败: summary_report_versions 集合不存在")
            return False

        logger.info("✅ 验证通过: summary_report_versions 集合已创建")
        return True
