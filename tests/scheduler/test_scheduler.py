"""
测试定时任务调度器功能

功能:
1. 创建测试定时任务
2. 立即执行任务（测试背景任务执行）
3. 验证任务执行结果
4. 生成测试报告

使用方法:
    python test_scheduler.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import settings
from src.core.domain.entities.search_task import SearchTask, ScheduleInterval, TaskStatus
from src.core.domain.entities.search_config import UserSearchConfig
from src.services.task_scheduler import get_scheduler
from src.infrastructure.database.connection import init_database, close_database_connections
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulerTestRunner:
    """调度器测试运行器"""

    def __init__(self):
        self.test_task_id: str = ""
        self.test_results: Dict[str, Any] = {}

    async def setup(self):
        """初始化测试环境"""
        logger.info("=" * 60)
        logger.info("🧪 开始调度器功能测试")
        logger.info("=" * 60)

        # 初始化数据库（可选）
        try:
            await init_database()
            logger.info("✅ 数据库连接初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ 数据库连接失败，将使用内存模式: {e}")

        # 获取并启动调度器
        scheduler = await get_scheduler()
        if not scheduler.is_running():
            await scheduler.start()
            logger.info("✅ 调度器启动成功")
        else:
            logger.info("ℹ️ 调度器已在运行中")

    async def create_test_task(self) -> SearchTask:
        """创建测试任务"""
        logger.info("\n" + "-" * 60)
        logger.info("📝 步骤1: 创建测试定时任务")
        logger.info("-" * 60)

        # 创建测试搜索配置
        search_config = UserSearchConfig(
            template_name="default",
            overrides={
                "limit": 5,
                "sources": ["web"],
                "enable_ai_summary": False,
                "extract_metadata": True,
                "follow_links": False
            }
        )

        # 创建测试任务
        test_task = SearchTask.create_with_secure_id(
            name="测试任务-调度器功能验证",
            description="测试定时任务调度器的创建和立即执行功能",
            query="Python async programming",
            search_config={
                "template": search_config.template_name,
                **search_config.overrides
            },
            schedule_interval="HOURLY_1",  # 每小时执行
            is_active=True,
            created_by="test_runner"
        )

        self.test_task_id = str(test_task.id)

        logger.info(f"✅ 任务创建成功")
        logger.info(f"   任务ID: {test_task.id}")
        logger.info(f"   任务名称: {test_task.name}")
        logger.info(f"   搜索关键词: {test_task.query}")
        logger.info(f"   调度间隔: {test_task.get_schedule_interval().description}")
        logger.info(f"   是否使用安全ID: {test_task.is_secure_id()}")

        # 添加任务到调度器
        scheduler = await get_scheduler()
        try:
            # 先保存到仓储
            repo = await scheduler._get_task_repository()
            saved_task = await repo.create(test_task)

            # 添加到调度器
            await scheduler.add_task(saved_task)
            logger.info("✅ 任务已添加到调度器")

            return saved_task
        except Exception as e:
            logger.error(f"❌ 添加任务到调度器失败: {e}")
            raise

    async def execute_task_immediately(self) -> Dict[str, Any]:
        """立即执行任务（测试背景执行功能）"""
        logger.info("\n" + "-" * 60)
        logger.info("⚡ 步骤2: 立即执行任务（测试背景执行）")
        logger.info("-" * 60)

        scheduler = await get_scheduler()

        try:
            # 记录执行前状态
            logger.info(f"正在执行任务 ID: {self.test_task_id}")
            execution_start = datetime.utcnow()

            # 立即执行任务
            result = await scheduler.execute_task_now(self.test_task_id)

            execution_end = datetime.utcnow()
            execution_time = (execution_end - execution_start).total_seconds()

            logger.info("✅ 任务执行完成")
            logger.info(f"   执行时间: {execution_time:.2f}秒")
            logger.info(f"   任务状态: {result.get('status')}")
            logger.info(f"   执行成功: {result.get('last_execution_success')}")
            logger.info(f"   总执行次数: {result.get('execution_count')}")

            return {
                "success": True,
                "execution_time": execution_time,
                "result": result
            }

        except Exception as e:
            logger.error(f"❌ 任务执行失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def verify_task_execution(self) -> Dict[str, Any]:
        """验证任务执行结果"""
        logger.info("\n" + "-" * 60)
        logger.info("🔍 步骤3: 验证任务执行结果")
        logger.info("-" * 60)

        scheduler = await get_scheduler()

        try:
            # 获取任务详情
            repo = await scheduler._get_task_repository()
            task = await repo.get_by_id(self.test_task_id)

            if not task:
                logger.error("❌ 无法找到任务")
                return {"success": False, "error": "任务不存在"}

            # 检查任务执行统计
            logger.info("📊 任务执行统计:")
            logger.info(f"   总执行次数: {task.execution_count}")
            logger.info(f"   成功次数: {task.success_count}")
            logger.info(f"   失败次数: {task.failure_count}")
            logger.info(f"   成功率: {task.success_rate:.2f}%")
            logger.info(f"   最后执行时间: {task.last_executed_at}")

            # 获取下次执行时间
            next_run = scheduler.get_task_next_run(self.test_task_id)
            if next_run:
                logger.info(f"   下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

            # 验证结果
            verification_passed = (
                task.execution_count > 0 and
                task.last_executed_at is not None
            )

            if verification_passed:
                logger.info("✅ 任务执行验证通过")
            else:
                logger.warning("⚠️ 任务执行验证未完全通过")

            return {
                "success": verification_passed,
                "task_stats": {
                    "execution_count": task.execution_count,
                    "success_count": task.success_count,
                    "failure_count": task.failure_count,
                    "success_rate": task.success_rate,
                    "last_executed_at": task.last_executed_at.isoformat() if task.last_executed_at else None
                }
            }

        except Exception as e:
            logger.error(f"❌ 验证失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        logger.info("\n" + "-" * 60)
        logger.info("📊 调度器状态检查")
        logger.info("-" * 60)

        scheduler = await get_scheduler()

        try:
            status = scheduler.get_status()
            running_tasks = scheduler.get_running_tasks()

            logger.info(f"调度器状态: {status.get('status')}")
            logger.info(f"活跃任务数: {status.get('active_jobs')}")
            logger.info(f"运行中任务数: {running_tasks.get('count')}")

            if status.get('next_run_time'):
                logger.info(f"下次执行时间: {status.get('next_run_time')}")

            return {
                "scheduler_status": status,
                "running_tasks": running_tasks
            }

        except Exception as e:
            logger.error(f"❌ 获取状态失败: {e}")
            return {"error": str(e)}

    async def cleanup(self):
        """清理测试数据"""
        logger.info("\n" + "-" * 60)
        logger.info("🧹 清理测试环境")
        logger.info("-" * 60)

        scheduler = await get_scheduler()

        try:
            # 移除测试任务
            await scheduler.remove_task(self.test_task_id)
            logger.info(f"✅ 已从调度器移除测试任务: {self.test_task_id}")

            # 从仓储删除任务
            repo = await scheduler._get_task_repository()
            await repo.delete(self.test_task_id)
            logger.info("✅ 已从数据库删除测试任务")

        except Exception as e:
            logger.warning(f"⚠️ 清理过程出现错误: {e}")

        # 关闭数据库连接
        try:
            await close_database_connections()
            logger.info("✅ 数据库连接已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 关闭数据库连接时出错: {e}")

    async def generate_report(self):
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("📋 测试报告")
        logger.info("=" * 60)

        execution_result = self.test_results.get("execution", {})
        verification_result = self.test_results.get("verification", {})
        scheduler_status = self.test_results.get("scheduler_status", {})

        logger.info(f"测试时间: {datetime.utcnow().isoformat()}")
        logger.info(f"测试任务ID: {self.test_task_id}")
        logger.info("")

        # 执行结果
        logger.info("1. 任务执行测试:")
        if execution_result.get("success"):
            logger.info(f"   ✅ 测试通过")
            logger.info(f"   执行时间: {execution_result.get('execution_time', 0):.2f}秒")
        else:
            logger.info(f"   ❌ 测试失败: {execution_result.get('error', 'Unknown error')}")

        # 验证结果
        logger.info("")
        logger.info("2. 任务验证测试:")
        if verification_result.get("success"):
            logger.info(f"   ✅ 验证通过")
            stats = verification_result.get("task_stats", {})
            logger.info(f"   执行次数: {stats.get('execution_count', 0)}")
            logger.info(f"   成功率: {stats.get('success_rate', 0):.2f}%")
        else:
            logger.info(f"   ❌ 验证失败: {verification_result.get('error', 'Unknown error')}")

        # 调度器状态
        logger.info("")
        logger.info("3. 调度器状态:")
        if scheduler_status:
            status = scheduler_status.get("scheduler_status", {})
            logger.info(f"   状态: {status.get('status', 'unknown')}")
            logger.info(f"   活跃任务数: {status.get('active_jobs', 0)}")

        # 总体结论
        logger.info("")
        logger.info("=" * 60)
        overall_success = (
            execution_result.get("success", False) and
            verification_result.get("success", False)
        )

        if overall_success:
            logger.info("✅ 调度器功能测试全部通过")
            logger.info("   - 任务创建功能正常")
            logger.info("   - 立即执行功能正常")
            logger.info("   - 背景任务执行正常")
            logger.info("   - 任务统计功能正常")
        else:
            logger.info("❌ 调度器功能测试存在问题")
            logger.info("   请查看上述详细日志以定位问题")

        logger.info("=" * 60)

    async def run(self):
        """运行完整的测试流程"""
        try:
            # 初始化
            await self.setup()

            # 创建测试任务
            await self.create_test_task()

            # 等待1秒确保任务已添加到调度器
            await asyncio.sleep(1)

            # 立即执行任务
            execution_result = await self.execute_task_immediately()
            self.test_results["execution"] = execution_result

            # 等待任务执行完成
            await asyncio.sleep(2)

            # 验证执行结果
            verification_result = await self.verify_task_execution()
            self.test_results["verification"] = verification_result

            # 获取调度器状态
            scheduler_status = await self.get_scheduler_status()
            self.test_results["scheduler_status"] = scheduler_status

            # 生成报告
            await self.generate_report()

        except Exception as e:
            logger.error(f"❌ 测试过程发生异常: {e}", exc_info=True)
            raise

        finally:
            # 清理
            await self.cleanup()


async def main():
    """主函数"""
    test_runner = SchedulerTestRunner()
    await test_runner.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ 测试被用户中断")
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        sys.exit(1)
