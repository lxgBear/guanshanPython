#!/usr/bin/env python
"""
数据库持久化验证测试

验证调度器执行任务后，搜索结果是否正确保存到MongoDB数据库。
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
from src.services.task_scheduler import get_scheduler
from src.core.domain.entities.search_task import SearchTask
from src.core.domain.entities.search_config import UserSearchConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def verify_database_persistence():
    """验证数据库持久化功能"""

    logger.info("=" * 70)
    logger.info("🧪 开始测试: 数据库持久化验证")
    logger.info("=" * 70)

    try:
        # 1. 初始化数据库连接
        logger.info("\n📊 步骤1: 初始化数据库连接")
        db = await get_mongodb_database()
        logger.info(f"✅ 数据库连接成功: {db.name}")

        # 2. 初始化结果仓储
        logger.info("\n📊 步骤2: 初始化结果仓储")
        result_repo = SearchResultRepository()
        logger.info("✅ 结果仓储初始化成功")

        # 3. 获取调度器实例
        logger.info("\n📊 步骤3: 获取调度器实例")
        scheduler = await get_scheduler()
        await scheduler.start()
        logger.info("✅ 调度器启动成功")

        # 4. 获取现有任务（使用第一个任务）
        logger.info("\n📊 步骤4: 获取现有任务")
        task_repo = await scheduler._get_task_repository()

        # 查询所有任务，获取第一个
        tasks, total = await task_repo.list_tasks(page=1, page_size=1, is_active=True)

        if not tasks or total == 0:
            logger.error("❌ 数据库中没有任务，请先创建任务")
            logger.error("   提示: 运行 python tests/scheduler/test_real_firecrawl_api.py 创建测试任务")
            return False

        test_task = tasks[0]
        test_task_id = str(test_task.id)

        logger.info(f"✅ 使用现有任务")
        logger.info(f"   - 任务ID: {test_task_id}")
        logger.info(f"   - 任务名称: {test_task.name}")
        logger.info(f"   - 查询: {test_task.query}")
        logger.info(f"   - 创建者: {test_task.created_by}")

        # 5. 检查数据库中任务前的结果数量
        logger.info("\n📊 步骤5: 检查执行前的数据库状态")
        collection = db["search_results"]
        before_count = await collection.count_documents({"task_id": test_task_id})
        logger.info(f"📈 执行前数据库中的结果数: {before_count}")

        # 6. 立即执行任务
        logger.info("\n📊 步骤6: 执行测试任务")
        execution_result = await scheduler.execute_task_now(test_task_id)
        logger.info(f"✅ 任务执行完成")
        logger.info(f"   - 执行时间: {execution_result['executed_at']}")
        logger.info(f"   - 执行状态: {execution_result['status']}")

        # 等待一下确保数据已保存
        await asyncio.sleep(1)

        # 7. 验证数据库中的结果
        logger.info("\n📊 步骤7: 验证数据库中的结果")
        after_count = await collection.count_documents({"task_id": test_task_id})
        new_results_count = after_count - before_count

        logger.info(f"📈 执行后数据库中的结果数: {after_count}")
        logger.info(f"📈 新增结果数: {new_results_count}")

        # 8. 使用仓储查询结果
        logger.info("\n📊 步骤8: 使用仓储查询结果")
        results, total = await result_repo.get_results_by_task(test_task_id, page=1, page_size=20)

        logger.info(f"📊 仓储查询结果:")
        logger.info(f"   - 总数: {total}")
        logger.info(f"   - 返回数: {len(results)}")

        if results:
            logger.info(f"\n📄 结果示例 (前3条):")
            for i, result in enumerate(results[:3], 1):
                logger.info(f"   {i}. 标题: {result.title}")
                logger.info(f"      URL: {result.url}")
                logger.info(f"      来源: {result.source}")
                logger.info(f"      相关性: {result.relevance_score:.2f}")
                logger.info(f"      创建时间: {result.created_at}")

        # 8.5. 打印 Firecrawl 原始数据（用于数据筛选）
        logger.info("\n📊 步骤8.5: 打印 Firecrawl API 原始数据")
        logger.info("=" * 70)
        logger.info("以下是 Firecrawl API 返回的原始数据，帮助筛选需要入库的字段：")
        logger.info("=" * 70)

        if results:
            import json
            # 只打印第一条结果的完整原始数据作为示例
            first_result = results[0]
            if hasattr(first_result, 'raw_data') and first_result.raw_data:
                logger.info("\n【第1条结果的 Firecrawl 原始数据】")
                logger.info(json.dumps(first_result.raw_data, indent=2, ensure_ascii=False))

                # 分析可用字段
                logger.info("\n" + "=" * 70)
                logger.info("📋 Firecrawl 原始数据字段分析：")
                logger.info("=" * 70)
                logger.info(f"可用字段列表: {list(first_result.raw_data.keys())}")
                logger.info("\n各字段说明：")
                for key, value in first_result.raw_data.items():
                    value_type = type(value).__name__
                    value_len = len(value) if isinstance(value, (str, list, dict)) else "N/A"
                    logger.info(f"  - {key:20} 类型: {value_type:10} 长度: {value_len}")

                # 打印当前已入库的字段
                logger.info("\n" + "=" * 70)
                logger.info("💾 当前已入库的字段映射：")
                logger.info("=" * 70)
                logger.info(f"  SearchResult.title          ← raw_data['title']")
                logger.info(f"  SearchResult.url            ← raw_data['url']")
                logger.info(f"  SearchResult.content        ← raw_data['markdown'] or raw_data['html']")
                logger.info(f"  SearchResult.snippet        ← raw_data['description']")
                logger.info(f"  SearchResult.source         ← raw_data['source']")
                logger.info(f"  SearchResult.published_date ← raw_data['publishedDate']")
                logger.info(f"  SearchResult.author         ← raw_data['author']")
                logger.info(f"  SearchResult.language       ← raw_data['language']")
                logger.info(f"  SearchResult.relevance_score← raw_data['score']")
                logger.info(f"  SearchResult.metadata       ← raw_data['metadata'] + html + links")
                logger.info(f"  SearchResult.markdown_content← raw_data['markdown']")
                logger.info(f"  SearchResult.raw_data       ← 完整原始数据")

                logger.info("\n💡 建议：请根据以上原始数据结构，决定是否需要添加新字段到数据库模型")
            else:
                logger.warning("⚠️  第一条结果没有 raw_data 字段")
        else:
            logger.warning("⚠️  没有结果可以显示原始数据")

        logger.info("=" * 70)

        # 9. 验证测试结果
        logger.info("\n📊 步骤9: 验证测试结果")

        success = True
        errors = []

        # 检查是否有新结果
        if new_results_count == 0:
            success = False
            errors.append("数据库中没有新增结果")
        else:
            logger.info(f"✅ 获取到 {new_results_count} 条新结果")

        # 检查仓储查询是否正常
        if total != after_count:
            logger.warning(f"⚠️  仓储查询总数({total})与数据库计数({after_count})不一致")

        # 10. 输出测试结论
        logger.info("\n" + "=" * 70)

        if success:
            logger.info("✅ 测试通过: 数据库持久化功能正常")
            logger.info("\n✨ 验证结果:")
            logger.info(f"   ✅ 调度器成功触发任务执行")
            logger.info(f"   ✅ Firecrawl API 获取了 {new_results_count} 条搜索结果")
            logger.info(f"   ✅ 结果成功保存到MongoDB数据库")
            logger.info(f"   ✅ 仓储可以正常查询和读取结果")
            logger.info(f"   ✅ 数据持久化到 search_results 集合")

            logger.info("\n📋 数据库信息:")
            logger.info(f"   - 数据库: {db.name}")
            logger.info(f"   - 集合: search_results")
            logger.info(f"   - 任务ID: {test_task_id}")
            logger.info(f"   - 任务名称: {test_task.name}")
            logger.info(f"   - 总结果数: {after_count}")
        else:
            logger.error("❌ 测试失败: 数据库持久化功能异常")
            logger.error("\n❌ 错误信息:")
            for error in errors:
                logger.error(f"   - {error}")

        logger.info("=" * 70)

        # 11. 保留测试数据（不清理）
        logger.info("\n📊 步骤10: 测试数据保留")
        logger.info("⚠️  测试数据将被保留在数据库中以供查看")
        logger.info(f"   - 任务ID: {test_task_id}")
        logger.info(f"   - 数据库: {db.name}")
        logger.info(f"   - 集合: search_results")
        logger.info(f"   - 结果数: {after_count}条")
        logger.info("\n💡 如需清理，运行以下命令:")
        logger.info(f"   mongosh {db.name} --eval 'db.search_tasks.deleteOne({{_id: \"{test_task_id}\"}})'")
        logger.info(f"   mongosh {db.name} --eval 'db.search_results.deleteMany({{task_id: \"{test_task_id}\"}})'")

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
        success = await verify_database_persistence()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ 测试运行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
