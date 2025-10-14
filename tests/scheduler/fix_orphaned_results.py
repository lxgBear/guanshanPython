#!/usr/bin/env python
"""
修复孤立的搜索结果

为 search_results 集合中没有对应任务的结果创建任务记录。
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.repositories import SearchTaskRepository
from src.core.domain.entities.search_task import SearchTask, ScheduleInterval, TaskStatus
from src.core.domain.entities.search_config import UserSearchConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def fix_orphaned_results():
    """修复孤立的搜索结果"""

    logger.info("=" * 70)
    logger.info("🔧 开始修复: 为孤立的搜索结果创建任务记录")
    logger.info("=" * 70)

    try:
        # 1. 初始化数据库连接
        logger.info("\n📊 步骤1: 初始化数据库连接")
        db = await get_mongodb_database()
        logger.info(f"✅ 数据库连接成功: {db.name}")

        # 2. 初始化任务仓储
        logger.info("\n📊 步骤2: 初始化任务仓储")
        task_repo = SearchTaskRepository()
        logger.info("✅ 任务仓储初始化成功")

        # 3. 查找所有孤立的 task_id
        logger.info("\n📊 步骤3: 查找孤立的搜索结果")
        task_ids = await db.search_results.distinct('task_id')
        logger.info(f"📈 发现 {len(task_ids)} 个不同的 task_id")

        orphaned_task_ids = []
        for task_id in task_ids:
            task = await db.search_tasks.find_one({'_id': task_id})
            if not task:
                count = await db.search_results.count_documents({'task_id': task_id})
                orphaned_task_ids.append((task_id, count))
                logger.warning(f"⚠️  task_id {task_id}: 有 {count} 条结果，但无任务记录")

        if not orphaned_task_ids:
            logger.info("\n✅ 没有发现孤立的搜索结果")
            return True

        logger.info(f"\n发现 {len(orphaned_task_ids)} 个孤立的 task_id，共 {sum(c for _, c in orphaned_task_ids)} 条结果")

        # 4. 为每个孤立的 task_id 创建任务
        logger.info("\n📊 步骤4: 创建任务记录")
        logger.info("-" * 70)

        created_count = 0
        for task_id, result_count in orphaned_task_ids:
            # 从结果中获取一条示例，提取查询信息
            sample_result = await db.search_results.find_one({'task_id': task_id})

            if not sample_result:
                logger.error(f"❌ 无法找到 task_id {task_id} 的示例结果")
                continue

            # 尝试从结果中推断查询内容
            query = sample_result.get('metadata', {}).get('query', f"任务_{task_id}")
            title = sample_result.get('title', '')
            title = title[:30] if title else f"恢复的任务_{task_id}"

            logger.info(f"\n🔧 为 task_id {task_id} 创建任务:")
            logger.info(f"   结果数: {result_count}")
            logger.info(f"   推断查询: {query}")

            # 创建任务文档（直接使用字典，绕过 Repository 的序列化）
            task_doc = {
                '_id': task_id,  # 使用原有的 task_id
                'name': f"恢复任务-{task_id[-8:]}",  # 使用 task_id 的后8位作为名称
                'description': f"自动恢复的任务（原有 {result_count} 条搜索结果）",
                'query': query,
                'search_config': {'template': 'default', 'overrides': {}},
                'schedule_interval': 'DAILY',  # 默认每天执行
                'is_active': False,  # 默认不激活，由用户手动激活
                'status': 'paused',
                'created_by': 'system_auto_recovery',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'last_executed_at': None,
                'next_run_time': datetime.utcnow() + timedelta(days=1),
                'execution_count': 0,
                'success_count': 0,
                'failure_count': 0,
                'total_results': result_count,  # 使用现有结果数
                'total_credits_used': 0
            }

            try:
                # 直接插入到 MongoDB
                await db.search_tasks.insert_one(task_doc)
                created_count += 1
                logger.info(f"   ✅ 任务创建成功")
                logger.info(f"      任务ID: {task_doc['_id']}")
                logger.info(f"      任务名称: {task_doc['name']}")
                logger.info(f"      状态: 未激活（需手动激活）")
                logger.info(f"      调度间隔: {task_doc['schedule_interval']}")
            except Exception as e:
                logger.error(f"   ❌ 任务创建失败: {e}")

        logger.info("\n" + "-" * 70)
        logger.info(f"📊 创建结果统计:")
        logger.info(f"   待创建: {len(orphaned_task_ids)} 个")
        logger.info(f"   成功: {created_count} 个")
        logger.info(f"   失败: {len(orphaned_task_ids) - created_count} 个")

        # 5. 验证修复结果
        logger.info("\n📊 步骤5: 验证修复结果")
        logger.info("-" * 70)

        for task_id, _ in orphaned_task_ids:
            task = await db.search_tasks.find_one({'_id': task_id})
            if task:
                logger.info(f"✅ task_id {task_id}: 任务已存在")
            else:
                logger.error(f"❌ task_id {task_id}: 任务仍然缺失")

        # 6. 输出总结
        logger.info("\n" + "=" * 70)
        logger.info("📋 修复总结:")
        logger.info("=" * 70)
        logger.info(f"✅ 成功为 {created_count} 个孤立的结果创建了任务记录")
        logger.info("\n💡 后续操作:")
        logger.info("   1. 检查创建的任务是否正确")
        logger.info("   2. 根据需要修改任务的名称、查询和调度间隔")
        logger.info("   3. 将需要的任务设置为 is_active=true 以启用调度")
        logger.info("   4. 重启应用以加载新任务到调度器")
        logger.info("\n📝 使用 API 激活任务:")
        logger.info("   PATCH /api/v1/search-tasks/{task_id}")
        logger.info("   Body: {\"is_active\": true}")
        logger.info("=" * 70)

        return created_count > 0

    except Exception as e:
        logger.error(f"❌ 修复过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    try:
        success = await fix_orphaned_results()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  修复被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 修复运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
