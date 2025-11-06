#!/usr/bin/env python3
"""
修复数据库中 search_config 字段数据类型错误

问题：某些任务的 search_config 字段被错误地存储为 float (0.0) 而非 dict
原因：MongoDB 写入时类型不匹配
影响：导致API调用时出现 "'float' object has no attribute 'get'" 错误

修复策略:
1. 查找所有 search_config 不是 dict 类型的任务
2. 将这些任务的 search_config 重置为空字典 {}
3. 同时检查和修复 crawl_config 字段
"""

import asyncio
import sys

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def fix_corrupted_config_fields():
    """修复所有配置字段类型错误"""

    try:
        db = await get_mongodb_database()

        logger.info("=" * 80)
        logger.info("📊 开始扫描数据库中的配置字段类型错误")
        logger.info("=" * 80)

        # 查询所有任务
        tasks = await db.search_tasks.find({}).to_list(length=None)

        logger.info(f"\n找到 {len(tasks)} 个任务\n")

        corrupted_tasks = []

        # 检查每个任务
        for task in tasks:
            task_id = task.get("_id")
            task_name = task.get("name", "未命名")
            search_config = task.get("search_config")
            crawl_config = task.get("crawl_config")

            issues = []

            # 检查 search_config
            if not isinstance(search_config, dict):
                issues.append(f"search_config 类型错误: {type(search_config).__name__} = {search_config}")

            # 检查 crawl_config
            if not isinstance(crawl_config, dict):
                issues.append(f"crawl_config 类型错误: {type(crawl_config).__name__} = {crawl_config}")

            if issues:
                corrupted_tasks.append({
                    "id": task_id,
                    "name": task_name,
                    "issues": issues,
                    "search_config": search_config,
                    "crawl_config": crawl_config
                })

        logger.info(f"🔍 扫描结果：")
        logger.info(f"  总任务数: {len(tasks)}")
        logger.info(f"  有问题的任务: {len(corrupted_tasks)}")
        logger.info(f"  正常任务: {len(tasks) - len(corrupted_tasks)}\n")

        if not corrupted_tasks:
            logger.info("✅ 所有任务的配置字段类型正确，无需修复")
            return True

        # 显示问题详情
        logger.info("⚠️  发现以下问题任务:\n")
        for idx, task in enumerate(corrupted_tasks, 1):
            logger.info(f"[{idx}] 任务: {task['name']} (ID: {task['id']})")
            for issue in task['issues']:
                logger.info(f"    ❌ {issue}")

        # 自动执行修复
        logger.info("\n" + "=" * 80)
        logger.info("🔧 开始修复...\n")

        success_count = 0
        for task in corrupted_tasks:
            task_id = task['id']
            task_name = task['name']

            # 构建更新字段
            update_fields = {}

            if not isinstance(task['search_config'], dict):
                update_fields['search_config'] = {}
                logger.info(f"修复 {task_name} (ID: {task_id}): search_config -> {{}}")

            if not isinstance(task['crawl_config'], dict):
                update_fields['crawl_config'] = {}
                logger.info(f"修复 {task_name} (ID: {task_id}): crawl_config -> {{}}")

            # 执行更新
            if update_fields:
                result = await db.search_tasks.update_one(
                    {"_id": task_id},
                    {"$set": update_fields}
                )

                if result.modified_count > 0:
                    success_count += 1
                    logger.info(f"  ✅ 修复成功\n")
                else:
                    logger.warning(f"  ⚠️  未修改（可能已被修复）\n")

        logger.info("=" * 80)
        logger.info(f"📈 修复完成统计:")
        logger.info(f"  发现问题: {len(corrupted_tasks)} 个任务")
        logger.info(f"  修复成功: {success_count} 个任务")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("\n🚀 开始执行：修复配置字段类型错误\n")

    success = await fix_corrupted_config_fields()

    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ 修复完成")
        logger.info("\n建议下一步:")
        logger.info("  1. 重启 API 服务")
        logger.info("  2. 测试 API 端点")
    else:
        logger.info("❌ 修复失败")
    logger.info("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
