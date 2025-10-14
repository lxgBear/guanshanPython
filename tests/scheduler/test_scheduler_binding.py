#!/usr/bin/env python
"""
调度器任务绑定验证测试

验证数据库中的任务是否正确绑定到APScheduler调度器。
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.repositories import SearchTaskRepository
from src.services.task_scheduler import get_scheduler
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def verify_scheduler_binding():
    """验证调度器任务绑定"""

    logger.info("=" * 70)
    logger.info("🧪 开始测试: 调度器任务绑定验证")
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

        # 3. 查询数据库中的所有任务
        logger.info("\n📊 步骤3: 查询数据库中的所有任务")
        all_tasks, total = await task_repo.list_tasks(page=1, page_size=100)
        logger.info(f"📈 数据库中共有 {total} 个任务")

        if total == 0:
            logger.warning("⚠️ 数据库中没有任务")
            return False

        # 4. 分析任务状态
        logger.info("\n📊 步骤4: 分析任务状态")
        active_count = 0
        inactive_count = 0

        logger.info("\n任务列表：")
        logger.info("-" * 70)
        for task in all_tasks:
            status_emoji = "🟢" if task.is_active else "🔴"
            logger.info(f"{status_emoji} 任务ID: {task.id}")
            logger.info(f"   名称: {task.name}")
            logger.info(f"   查询: {task.query}")
            logger.info(f"   状态: {'活跃' if task.is_active else '未激活'}")
            logger.info(f"   调度间隔: {task.schedule_interval}")
            logger.info(f"   下次执行: {task.next_run_time or '未设置'}")
            logger.info(f"   创建时间: {task.created_at}")
            logger.info("")

            if task.is_active:
                active_count += 1
            else:
                inactive_count += 1

        logger.info("-" * 70)
        logger.info(f"📊 任务统计:")
        logger.info(f"   🟢 活跃任务: {active_count} 个")
        logger.info(f"   🔴 未激活任务: {inactive_count} 个")

        # 5. 启动调度器并验证绑定
        logger.info("\n📊 步骤5: 启动调度器")
        scheduler = await get_scheduler()
        await scheduler.start()
        logger.info("✅ 调度器启动成功")

        # 6. 检查调度器中的任务
        logger.info("\n📊 步骤6: 检查调度器中的任务")
        scheduled_jobs = scheduler.scheduler.get_jobs()

        logger.info(f"📈 调度器中共有 {len(scheduled_jobs)} 个任务")
        logger.info("\n调度器任务列表：")
        logger.info("-" * 70)

        search_task_jobs = [job for job in scheduled_jobs if job.id.startswith('search_task_')]

        if not search_task_jobs:
            logger.warning("⚠️ 调度器中没有搜索任务")
        else:
            for job in search_task_jobs:
                logger.info(f"⏰ Job ID: {job.id}")
                logger.info(f"   名称: {job.name}")
                logger.info(f"   下次执行: {job.next_run_time}")
                logger.info(f"   触发器: {job.trigger}")
                logger.info("")

        # 7. 验证绑定关系
        logger.info("\n📊 步骤7: 验证任务绑定关系")
        logger.info("-" * 70)

        bound_count = 0
        unbound_count = 0

        for task in all_tasks:
            if not task.is_active:
                continue

            job_id = f"search_task_{task.id}"
            job = scheduler.scheduler.get_job(job_id)

            if job:
                logger.info(f"✅ 任务已绑定: {task.name}")
                logger.info(f"   数据库ID: {task.id}")
                logger.info(f"   调度器Job ID: {job_id}")
                logger.info(f"   下次执行: {job.next_run_time}")
                bound_count += 1
            else:
                logger.error(f"❌ 任务未绑定: {task.name}")
                logger.error(f"   数据库ID: {task.id}")
                logger.error(f"   期望的Job ID: {job_id}")
                logger.error(f"   状态: is_active={task.is_active}")
                unbound_count += 1

            logger.info("")

        logger.info("-" * 70)
        logger.info(f"📊 绑定统计:")
        logger.info(f"   ✅ 已绑定: {bound_count} 个活跃任务")
        logger.info(f"   ❌ 未绑定: {unbound_count} 个活跃任务")

        # 8. 测试结论
        logger.info("\n" + "=" * 70)

        success = (active_count > 0 and unbound_count == 0)

        if success:
            logger.info("✅ 测试通过: 所有活跃任务都已正确绑定到调度器")
            logger.info("\n✨ 验证结果:")
            logger.info(f"   ✅ 数据库中有 {active_count} 个活跃任务")
            logger.info(f"   ✅ 所有活跃任务都已绑定到APScheduler")
            logger.info(f"   ✅ 调度器将按计划自动执行这些任务")
        else:
            if active_count == 0:
                logger.warning("⚠️ 测试结果: 数据库中没有活跃任务")
                logger.warning("\n💡 建议:")
                logger.warning("   1. 使用API创建新任务")
                logger.warning("   2. 或者激活现有任务（设置 is_active=true）")
            else:
                logger.error("❌ 测试失败: 存在未绑定的活跃任务")
                logger.error("\n❌ 问题:")
                logger.error(f"   - {unbound_count} 个活跃任务未绑定到调度器")
                logger.error("\n💡 可能原因:")
                logger.error("   1. 调度器启动失败")
                logger.error("   2. 任务的schedule_interval字段无效")
                logger.error("   3. _schedule_task方法执行异常")

        logger.info("=" * 70)

        # 9. 如果有未绑定的任务，尝试手动绑定
        if unbound_count > 0:
            logger.info("\n📊 步骤8: 尝试修复未绑定的任务")
            for task in all_tasks:
                if not task.is_active:
                    continue

                job_id = f"search_task_{task.id}"
                job = scheduler.scheduler.get_job(job_id)

                if not job:
                    logger.info(f"🔧 尝试绑定任务: {task.name}")
                    try:
                        await scheduler._schedule_task(task)
                        logger.info(f"   ✅ 绑定成功")
                    except Exception as e:
                        logger.error(f"   ❌ 绑定失败: {e}")

            # 重新检查
            logger.info("\n📊 重新检查绑定状态:")
            scheduled_jobs_after = scheduler.scheduler.get_jobs()
            search_task_jobs_after = [job for job in scheduled_jobs_after if job.id.startswith('search_task_')]
            logger.info(f"📈 调度器中现有 {len(search_task_jobs_after)} 个搜索任务")

        # 停止调度器
        await scheduler.stop()
        logger.info("\n✅ 调度器已停止")

        return success

    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    try:
        success = await verify_scheduler_binding()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 测试运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
