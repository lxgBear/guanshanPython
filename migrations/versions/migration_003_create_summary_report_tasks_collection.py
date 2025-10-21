"""
Migration 003: 创建 summary_report_tasks 集合和索引

功能:
- 创建 summary_report_tasks 集合（任务关联表）
- 添加索引以优化联表查询性能

索引说明:
- idx_report_id: 按报告ID查询
- idx_task_id_type: 按任务ID和类型查询（复合索引）
- idx_is_active: 按激活状态查询
- idx_priority: 按优先级排序
- idx_added_at: 按添加时间排序
"""

from migrations.base_migration import BaseMigration
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Migration003CreateSummaryReportTasksCollection(BaseMigration):
    """创建 summary_report_tasks 集合和索引"""

    version = "003"
    description = "创建 summary_report_tasks 集合和索引"

    async def upgrade(self) -> dict:
        """执行迁移"""
        collection = self.db.summary_report_tasks

        # 检查集合是否已存在
        collection_names = await self.db.list_collection_names()
        if "summary_report_tasks" not in collection_names:
            await self.db.create_collection("summary_report_tasks")
            logger.info("✅ 创建集合: summary_report_tasks")
        else:
            logger.info("ℹ️ 集合已存在: summary_report_tasks")

        # 创建索引
        created_count = 0

        # 单字段索引
        single_indexes = [
            ("report_id", 1),
            ("is_active", 1),
            ("priority", -1),  # 降序，高优先级在前
            ("added_at", -1),
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

        # 复合索引：任务ID + 类型（用于查找特定任务）
        try:
            await collection.create_index(
                [("task_id", 1), ("task_type", 1)],
                name="idx_task_id_type",
                background=True
            )
            logger.info("✅ 创建复合索引: idx_task_id_type")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 复合索引创建失败或已存在: {e}")

        # 复合索引：报告ID + 激活状态（用于查询报告的活跃任务）
        try:
            await collection.create_index(
                [("report_id", 1), ("is_active", 1)],
                name="idx_report_active",
                background=True
            )
            logger.info("✅ 创建复合索引: idx_report_active")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 复合索引创建失败或已存在: {e}")

        # 复合索引：报告ID + 任务ID + 类型（用于唯一性约束）
        try:
            await collection.create_index(
                [("report_id", 1), ("task_id", 1), ("task_type", 1)],
                name="idx_report_task_unique",
                unique=True,
                background=True
            )
            logger.info("✅ 创建唯一复合索引: idx_report_task_unique")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 唯一索引创建失败或已存在: {e}")

        return {
            'collection_created': "summary_report_tasks" not in collection_names,
            'indexes_created': created_count,
            'message': f'成功创建集合和 {created_count} 个索引'
        }

    async def downgrade(self) -> dict:
        """回滚迁移"""
        collection = self.db.summary_report_tasks

        # 删除所有索引
        try:
            await collection.drop_indexes()
            logger.info("✅ 删除所有索引")
        except Exception as e:
            logger.warning(f"⚠️ 删除索引失败: {e}")

        # 删除集合
        try:
            await self.db.drop_collection("summary_report_tasks")
            logger.info("✅ 删除集合: summary_report_tasks")
        except Exception as e:
            logger.warning(f"⚠️ 删除集合失败: {e}")

        return {
            'collection_dropped': True,
            'message': '成功回滚迁移'
        }

    async def validate(self) -> bool:
        """验证迁移结果"""
        collection_names = await self.db.list_collection_names()
        if "summary_report_tasks" not in collection_names:
            logger.error("❌ 验证失败: summary_report_tasks 集合不存在")
            return False

        logger.info("✅ 验证通过: summary_report_tasks 集合已创建")
        return True
