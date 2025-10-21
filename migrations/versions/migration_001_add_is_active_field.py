"""
Migration 001: 为 search_tasks 集合添加 is_active 字段

问题背景:
- 旧版本的任务文档缺少 is_active 字段
- 调度器只加载 is_active=True 的任务
- 导致旧任务无法被调度

解决方案:
- 为所有缺少 is_active 字段的任务添加该字段
- 默认值设置为 True（保持向后兼容）
"""

from datetime import datetime
from migrations.base_migration import BaseMigration


class Migration001AddIsActiveField(BaseMigration):
    """添加 is_active 字段到 search_tasks"""

    version = "001"
    description = "为 search_tasks 添加 is_active 字段"

    async def upgrade(self) -> dict:
        """执行迁移"""
        # 查找所有缺少 is_active 字段的任务
        tasks_without_field = await self.db.search_tasks.find(
            {'is_active': {'$exists': False}}
        ).to_list(10000)

        if not tasks_without_field:
            return {
                'modified_count': 0,
                'message': '所有任务已有 is_active 字段'
            }

        # 批量更新
        result = await self.db.search_tasks.update_many(
            {'is_active': {'$exists': False}},
            {
                '$set': {
                    'is_active': True,
                    'updated_at': datetime.utcnow()
                }
            }
        )

        return {
            'modified_count': result.modified_count,
            'matched_count': result.matched_count,
            'message': f'成功为 {result.modified_count} 个任务添加 is_active 字段'
        }

    async def downgrade(self) -> dict:
        """回滚迁移"""
        # 移除 is_active 字段
        result = await self.db.search_tasks.update_many(
            {},
            {'$unset': {'is_active': ''}}
        )

        return {
            'modified_count': result.modified_count,
            'message': f'成功移除 {result.modified_count} 个任务的 is_active 字段'
        }

    async def validate(self) -> bool:
        """验证迁移结果"""
        # 检查是否还有任务缺少 is_active 字段
        count = await self.db.search_tasks.count_documents(
            {'is_active': {'$exists': False}}
        )

        return count == 0
