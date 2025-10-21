"""
Migration 004: 创建 summary_report_data_items 集合和索引

功能:
- 创建 summary_report_data_items 集合（手动添加的数据项）
- 添加全文搜索索引和查询优化索引

索引说明:
- idx_report_id: 按报告ID查询
- idx_is_visible: 按可见性查询
- idx_importance: 按重要性排序
- idx_added_at: 按添加时间排序
- idx_text_search: 全文搜索索引（标题和内容）
- idx_report_visible: 复合索引（报告ID + 可见性）
"""

from migrations.base_migration import BaseMigration
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Migration004CreateSummaryReportDataItemsCollection(BaseMigration):
    """创建 summary_report_data_items 集合和索引"""

    version = "004"
    description = "创建 summary_report_data_items 集合和索引"

    async def upgrade(self) -> dict:
        """执行迁移"""
        collection = self.db.summary_report_data_items

        # 检查集合是否已存在
        collection_names = await self.db.list_collection_names()
        if "summary_report_data_items" not in collection_names:
            await self.db.create_collection("summary_report_data_items")
            logger.info("✅ 创建集合: summary_report_data_items")
        else:
            logger.info("ℹ️ 集合已存在: summary_report_data_items")

        created_count = 0

        # 单字段索引
        single_indexes = [
            ("report_id", 1),
            ("is_visible", 1),
            ("importance", -1),  # 降序，高重要性在前
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

        # 全文搜索索引（标题和内容）
        try:
            await collection.create_index(
                [
                    ("title", "text"),
                    ("content", "text")
                ],
                name="idx_text_search",
                weights={
                    "title": 10,      # 标题权重更高
                    "content": 5      # 内容权重较低
                },
                default_language="none",  # 支持中文
                background=True
            )
            logger.info("✅ 创建全文搜索索引: idx_text_search")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 全文搜索索引创建失败或已存在: {e}")

        # 复合索引：报告ID + 可见性
        try:
            await collection.create_index(
                [("report_id", 1), ("is_visible", 1)],
                name="idx_report_visible",
                background=True
            )
            logger.info("✅ 创建复合索引: idx_report_visible")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 复合索引创建失败或已存在: {e}")

        # 复合索引：报告ID + 重要性（用于排序查询）
        try:
            await collection.create_index(
                [("report_id", 1), ("importance", -1)],
                name="idx_report_importance",
                background=True
            )
            logger.info("✅ 创建复合索引: idx_report_importance")
            created_count += 1
        except Exception as e:
            logger.warning(f"⚠️ 复合索引创建失败或已存在: {e}")

        return {
            'collection_created': "summary_report_data_items" not in collection_names,
            'indexes_created': created_count,
            'message': f'成功创建集合和 {created_count} 个索引'
        }

    async def downgrade(self) -> dict:
        """回滚迁移"""
        collection = self.db.summary_report_data_items

        # 删除所有索引
        try:
            await collection.drop_indexes()
            logger.info("✅ 删除所有索引")
        except Exception as e:
            logger.warning(f"⚠️ 删除索引失败: {e}")

        # 删除集合
        try:
            await self.db.drop_collection("summary_report_data_items")
            logger.info("✅ 删除集合: summary_report_data_items")
        except Exception as e:
            logger.warning(f"⚠️ 删除集合失败: {e}")

        return {
            'collection_dropped': True,
            'message': '成功回滚迁移'
        }

    async def validate(self) -> bool:
        """验证迁移结果"""
        collection_names = await self.db.list_collection_names()
        if "summary_report_data_items" not in collection_names:
            logger.error("❌ 验证失败: summary_report_data_items 集合不存在")
            return False

        logger.info("✅ 验证通过: summary_report_data_items 集合已创建")
        return True
