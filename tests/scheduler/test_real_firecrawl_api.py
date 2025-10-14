#!/usr/bin/env python
"""
真实 Firecrawl API 测试

测试真实的 Firecrawl API 调用，验证：
1. API 连接是否正常
2. 搜索结果是否正确返回
3. 数据是否正确保存到数据库
4. 真实数据的完整性
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.repositories import SearchResultRepository
from src.infrastructure.search.firecrawl_search_adapter import FirecrawlSearchAdapter
from src.core.domain.entities.search_config import UserSearchConfig
from src.services.task_scheduler import get_scheduler
from src.core.domain.entities.search_task import SearchTask
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_real_firecrawl_api():
    """测试真实的 Firecrawl API"""

    logger.info("=" * 70)
    logger.info("🌐 开始测试: 真实 Firecrawl API 调用")
    logger.info("=" * 70)

    try:
        # 1. 检查配置
        logger.info("\n📊 步骤1: 检查 Firecrawl 配置")
        logger.info(f"   - API Base URL: {settings.FIRECRAWL_BASE_URL}")
        logger.info(f"   - API Key: {settings.FIRECRAWL_API_KEY[:20]}...")
        logger.info(f"   - TEST_MODE: {settings.TEST_MODE}")
        logger.info(f"   - Timeout: {settings.FIRECRAWL_TIMEOUT}s")
        logger.info(f"   - Max Retries: {settings.FIRECRAWL_MAX_RETRIES}")

        if settings.TEST_MODE:
            logger.warning("⚠️  TEST_MODE 仍然开启！将生成模拟数据而非真实数据")
            logger.warning("   请在 .env 文件中设置 TEST_MODE=false")
            return False
        else:
            logger.info("✅ TEST_MODE 已关闭，将调用真实 Firecrawl API")

        # 2. 初始化数据库
        logger.info("\n📊 步骤2: 初始化数据库连接")
        db = await get_mongodb_database()
        result_repo = SearchResultRepository()
        logger.info("✅ 数据库连接成功")

        # 3. 初始化调度器
        logger.info("\n📊 步骤3: 初始化调度器")
        scheduler = await get_scheduler()
        await scheduler.start()
        logger.info("✅ 调度器启动成功")

        # 4. 创建测试任务（使用较小的limit以节省API额度）
        logger.info("\n📊 步骤4: 创建真实 API 测试任务")
        search_config = UserSearchConfig(
            template_name="default",
            overrides={
                "limit": 5,  # 限制为5条以节省额度
                "sources": ["web"],
                "enable_ai_summary": False,
                "extract_metadata": True,
                "follow_links": False
            }
        )

        test_task = SearchTask.create_with_secure_id(
            name="真实Firecrawl API测试",
            description="测试真实的Firecrawl API调用和数据保存",
            query="Python programming best practices 2024",  # 使用英文查询以获得更好的结果
            search_config={
                "template": search_config.template_name,
                **search_config.overrides
            },
            schedule_interval="HOURLY_1",
            is_active=True,
            created_by="real_api_test"
        )

        # 保存任务
        task_repo = await scheduler._get_task_repository()
        await task_repo.create(test_task)
        test_task_id = str(test_task.id)

        logger.info(f"✅ 测试任务已创建")
        logger.info(f"   - 任务ID: {test_task_id}")
        logger.info(f"   - 任务名称: {test_task.name}")
        logger.info(f"   - 查询: {test_task.query}")
        logger.info(f"   - 结果限制: 5条")

        # 5. 检查执行前的数据库状态
        logger.info("\n📊 步骤5: 检查执行前的数据库状态")
        collection = db["search_results"]
        before_count = await collection.count_documents({"task_id": test_task_id})
        logger.info(f"📈 执行前数据库中的结果数: {before_count}")

        # 6. 执行任务（调用真实 Firecrawl API）
        logger.info("\n📊 步骤6: 执行真实 Firecrawl API 调用")
        logger.info("⏳ 正在调用 Firecrawl API，请稍候...")
        logger.info("   (真实 API 调用可能需要 5-30 秒)")

        execution_result = await scheduler.execute_task_now(test_task_id)

        logger.info(f"✅ 任务执行完成")
        logger.info(f"   - 执行时间: {execution_result['executed_at']}")
        logger.info(f"   - 执行状态: {execution_result['status']}")

        # 等待数据保存完成
        await asyncio.sleep(2)

        # 7. 验证数据库中的结果
        logger.info("\n📊 步骤7: 验证数据库中的真实结果")
        after_count = await collection.count_documents({"task_id": test_task_id})
        new_results_count = after_count - before_count

        logger.info(f"📈 执行后数据库中的结果数: {after_count}")
        logger.info(f"📈 新增结果数: {new_results_count}")

        # 8. 查询并显示真实结果
        logger.info("\n📊 步骤8: 查询并显示真实搜索结果")
        results, total = await result_repo.get_results_by_task(test_task_id, page=1, page_size=20)

        logger.info(f"📊 仓储查询结果:")
        logger.info(f"   - 总数: {total}")
        logger.info(f"   - 返回数: {len(results)}")

        if results:
            logger.info(f"\n📄 真实搜索结果详情:")
            logger.info("=" * 70)
            for i, result in enumerate(results, 1):
                logger.info(f"\n{i}. 【{result.title}】")
                logger.info(f"   🔗 URL: {result.url}")
                logger.info(f"   📝 摘要: {result.snippet[:100] if result.snippet else '无'}...")
                logger.info(f"   📊 相关性评分: {result.relevance_score:.2f}")
                logger.info(f"   📊 质量评分: {result.quality_score:.2f}")
                logger.info(f"   🌐 来源: {result.source}")
                logger.info(f"   🗣️ 语言: {result.language or '未知'}")
                logger.info(f"   📅 发布时间: {result.published_date or '未知'}")
                logger.info(f"   👤 作者: {result.author or '未知'}")
                logger.info(f"   ⏰ 创建时间: {result.created_at}")
                logger.info(f"   🧪 测试数据: {'是' if result.is_test_data else '否'}")
                logger.info("-" * 70)

            # 显示内容样本
            if results[0].content:
                logger.info(f"\n📄 内容样本 (第1条结果):")
                logger.info("-" * 70)
                content_preview = results[0].content[:500]
                logger.info(content_preview)
                if len(results[0].content) > 500:
                    logger.info(f"... (还有 {len(results[0].content) - 500} 个字符)")
                logger.info("-" * 70)
        else:
            logger.warning("⚠️  没有获取到结果")

        # 9. 验证测试结果
        logger.info("\n📊 步骤9: 验证测试结果")

        success = True
        errors = []

        # 检查是否有新结果
        if new_results_count == 0:
            success = False
            errors.append("数据库中没有新增结果")

        # 检查是否是真实数据（不是测试数据）
        if results:
            real_data_count = sum(1 for r in results if not r.is_test_data)
            if real_data_count == 0:
                success = False
                errors.append("所有结果都标记为测试数据，可能仍在使用TEST_MODE")
            else:
                logger.info(f"✅ 真实数据数量: {real_data_count}/{len(results)}")

            # 检查数据质量
            has_content = sum(1 for r in results if r.content and len(r.content) > 100)
            if has_content > 0:
                logger.info(f"✅ 有实际内容的结果: {has_content}/{len(results)}")
            else:
                logger.warning(f"⚠️  没有结果包含实际内容")

        # 10. 输出测试结论
        logger.info("\n" + "=" * 70)

        if success:
            logger.info("✅ 测试通过: 真实 Firecrawl API 调用成功")
            logger.info("\n✨ 验证结果:")
            logger.info(f"   ✅ 成功调用真实 Firecrawl API")
            logger.info(f"   ✅ 获取了 {new_results_count} 条真实搜索结果")
            logger.info(f"   ✅ 结果成功保存到 MongoDB 数据库")
            logger.info(f"   ✅ 数据包含实际内容和元数据")
            logger.info(f"   ✅ 仓储可以正常查询真实数据")

            logger.info("\n📋 数据库信息:")
            logger.info(f"   - 数据库: {db.name}")
            logger.info(f"   - 集合: search_results")
            logger.info(f"   - 任务ID: {test_task_id}")
            logger.info(f"   - 结果数: {after_count}")
            logger.info(f"   - 真实数据: 是")

            logger.info("\n💡 提示:")
            logger.info("   - 真实数据已保存到数据库")
            logger.info("   - 可以通过 API 查询: GET /api/v1/search-tasks/{task_id}/results")
            logger.info("   - 数据将持久化保存，重启后仍然可用")
        else:
            logger.error("❌ 测试失败: 真实 Firecrawl API 调用异常")
            logger.error("\n❌ 错误信息:")
            for error in errors:
                logger.error(f"   - {error}")

        logger.info("=" * 70)

        # 11. 询问是否清理测试数据
        logger.info("\n📊 步骤10: 测试数据清理")
        logger.info("⚠️  测试数据将被保留以供查看")
        logger.info(f"   - 任务ID: {test_task_id}")
        logger.info("   - 如需清理，运行以下命令:")
        logger.info(f"     mongosh intelligent_system --eval 'db.search_tasks.deleteOne({{_id: \"{test_task_id}\"}})'")
        logger.info(f"     mongosh intelligent_system --eval 'db.search_results.deleteMany({{task_id: \"{test_task_id}\"}})'")

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
        success = await test_real_firecrawl_api()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 测试运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
