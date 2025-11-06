#!/usr/bin/env python3
"""
更新任务 244746288889929728 添加 prompt 参数

测试自然语言 prompt 过滤爬取结果: "只爬取近期一个月的数据 忽略旧版存档"
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def update_task_prompt():
    """更新任务的 crawl_config 添加 prompt 参数"""

    task_id = "244746288889929728"
    prompt_text = "只爬取近期一个月的数据 忽略旧版存档"

    try:
        db = await get_mongodb_database()

        # 1. 查询当前任务配置
        logger.info(f"查询任务 {task_id} 的当前配置...")
        task = await db.search_tasks.find_one({"_id": task_id})

        if not task:
            logger.error(f"❌ 任务 {task_id} 不存在")
            return False

        logger.info(f"✅ 找到任务: {task.get('name')}")
        logger.info(f"   当前 crawl_config: {task.get('crawl_config')}")

        # 2. 更新 crawl_config 添加 prompt
        current_config = task.get('crawl_config', {})
        current_config['prompt'] = prompt_text

        logger.info(f"\n准备更新 crawl_config:")
        logger.info(f"   新增 prompt: {prompt_text}")

        # 3. 执行更新
        result = await db.search_tasks.update_one(
            {"_id": task_id},
            {"$set": {"crawl_config": current_config}}
        )

        if result.modified_count > 0:
            logger.info(f"\n✅ 成功更新任务配置")

            # 4. 验证更新结果
            updated_task = await db.search_tasks.find_one({"_id": task_id})
            logger.info(f"\n更新后的 crawl_config:")
            for key, value in updated_task.get('crawl_config', {}).items():
                logger.info(f"   {key}: {value}")

            return True
        else:
            logger.warning(f"⚠️ 未修改任何文档（可能配置已存在）")
            return False

    except Exception as e:
        logger.error(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("测试 Firecrawl v2 API prompt 参数")
    logger.info("=" * 60)

    success = await update_task_prompt()

    logger.info("\n" + "=" * 60)
    if success:
        logger.info("✅ 任务配置更新成功")
        logger.info("\n下一步:")
        logger.info("1. 重启 API 服务使 FirecrawlAdapter 修改生效")
        logger.info("2. 手动执行任务或等待调度执行")
        logger.info("3. 检查爬取结果验证 prompt 过滤效果")
    else:
        logger.info("❌ 任务配置更新失败")
    logger.info("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
