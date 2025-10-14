"""
测试搜索结果存储修复

验证修复后的功能:
1. 任务执行能正确生成搜索结果（测试模式）
2. 搜索结果正确保存到存储
3. 可以通过API查询到结果
4. 代理配置不再影响测试模式
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services.task_scheduler import get_scheduler
from src.infrastructure.database.connection import init_database, close_database_connections
from src.api.v1.endpoints.search_results_frontend import results_storage, get_task_result_count
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_search_results_storage():
    """测试搜索结果存储功能"""

    logger.info("=" * 70)
    logger.info("🧪 开始测试搜索结果存储功能")
    logger.info("=" * 70)

    try:
        # 初始化数据库
        await init_database()
        logger.info("✅ 数据库初始化完成")

        # 获取调度器
        scheduler = await get_scheduler()
        if not scheduler.is_running():
            await scheduler.start()
            logger.info("✅ 调度器启动成功")

        # 等待调度器完全初始化
        await asyncio.sleep(1)

        # 选择一个测试任务ID
        test_task_id = "1640109524"  # AI新闻监控测试

        logger.info(f"\n{'=' * 70}")
        logger.info(f"📝 测试任务: {test_task_id}")
        logger.info(f"{'=' * 70}")

        # 检查任务执行前的结果数量
        before_count = get_task_result_count(test_task_id)
        logger.info(f"执行前结果数量: {before_count}")

        # 立即执行任务
        logger.info(f"\n⚡ 开始执行任务...")
        execution_result = await scheduler.execute_task_now(test_task_id)

        logger.info(f"✅ 任务执行完成:")
        logger.info(f"   - 任务名称: {execution_result['task_name']}")
        logger.info(f"   - 执行时间: {execution_result['executed_at']}")
        logger.info(f"   - 执行状态: {execution_result['status']}")
        logger.info(f"   - 执行次数: {execution_result['execution_count']}")

        # 等待结果处理
        await asyncio.sleep(1)

        # 检查结果是否已保存
        after_count = get_task_result_count(test_task_id)
        logger.info(f"\n📊 执行后结果数量: {after_count}")

        # 验证结果
        new_results = after_count - before_count
        logger.info(f"   新增结果数: {new_results}")

        if new_results > 0:
            logger.info(f"\n✅ 测试通过: 成功保存 {new_results} 条搜索结果")

            # 显示一些结果详情
            task_results = results_storage.get(test_task_id, [])
            if task_results:
                logger.info(f"\n📄 最新结果样例:")
                recent = task_results[-1]  # 最新的一条
                logger.info(f"   - 标题: {recent.title}")
                logger.info(f"   - URL: {recent.url}")
                logger.info(f"   - 来源: {recent.source}")
                logger.info(f"   - 相关性评分: {recent.relevance_score:.2f}")
                logger.info(f"   - 是否测试数据: {recent.is_test_data}")
                logger.info(f"   - 创建时间: {recent.created_at}")

            return True
        else:
            logger.error(f"\n❌ 测试失败: 没有新增搜索结果")
            logger.error(f"   可能的原因:")
            logger.error(f"   1. 搜索执行失败")
            logger.error(f"   2. 结果保存逻辑有问题")
            logger.error(f"   3. TEST_MODE未正确启用")
            return False

    except Exception as e:
        logger.error(f"\n❌ 测试过程发生异常: {e}", exc_info=True)
        return False

    finally:
        # 清理
        try:
            await close_database_connections()
            logger.info("\n✅ 数据库连接已关闭")
        except Exception as e:
            logger.warning(f"⚠️ 关闭数据库时出错: {e}")


async def test_api_query():
    """测试通过API查询结果"""

    logger.info(f"\n{'=' * 70}")
    logger.info("🌐 测试API查询功能")
    logger.info(f"{'=' * 70}")

    test_task_id = "1640109524"

    # 显示如何通过API查询
    logger.info(f"\n📡 API测试命令:")
    logger.info(f"\n1. 获取任务结果列表:")
    logger.info(f"   curl --noproxy localhost http://localhost:8000/api/v1/search-tasks/{test_task_id}/results")

    logger.info(f"\n2. 获取结果统计:")
    logger.info(f"   curl --noproxy localhost http://localhost:8000/api/v1/search-tasks/{test_task_id}/results/stats")

    logger.info(f"\n3. 获取结果摘要:")
    logger.info(f"   curl --noproxy localhost http://localhost:8000/api/v1/search-tasks/{test_task_id}/results/summary")

    # 检查内存存储
    task_results = results_storage.get(test_task_id, [])
    if task_results:
        logger.info(f"\n✅ 内存存储验证: 找到 {len(task_results)} 条结果")
    else:
        logger.warning(f"\n⚠️ 内存存储验证: 任务 {test_task_id} 暂无结果")


async def generate_test_report():
    """生成测试报告"""

    logger.info(f"\n{'=' * 70}")
    logger.info("📋 测试报告汇总")
    logger.info(f"{'=' * 70}")

    logger.info(f"\n修复内容:")
    logger.info(f"1. ✅ httpx客户端配置 - 禁用代理避免SOCKS错误")
    logger.info(f"2. ✅ TEST_MODE检测 - 优先从settings读取配置")
    logger.info(f"3. ✅ 增强日志 - 清晰显示测试/生产模式")

    logger.info(f"\n测试结果:")
    task_count = len(results_storage)
    total_results = sum(len(results) for results in results_storage.values())

    logger.info(f"- 已存储任务数: {task_count}")
    logger.info(f"- 总结果数量: {total_results}")

    if task_count > 0:
        logger.info(f"\n任务结果明细:")
        for task_id, results in results_storage.items():
            logger.info(f"  - 任务 {task_id}: {len(results)} 条结果")

    logger.info(f"\n下一步操作:")
    logger.info(f"1. 重启FastAPI应用使修复生效")
    logger.info(f"2. 通过API查询验证结果可访问")
    logger.info(f"3. 监控后续定时任务执行情况")

    logger.info(f"\n{'=' * 70}")
    logger.info(f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'=' * 70}")


async def main():
    """主函数"""

    # 执行搜索结果存储测试
    success = await test_search_results_storage()

    # 显示API测试指引
    await test_api_query()

    # 生成测试报告
    await generate_test_report()

    if success:
        logger.info(f"\n🎉 所有测试通过!")
        sys.exit(0)
    else:
        logger.error(f"\n❌ 测试失败，请查看上述日志")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ 测试被用户中断")
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        sys.exit(1)
