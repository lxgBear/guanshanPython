#!/usr/bin/env python3
"""
更新任务配置以获取原始 HTML

目的：
- 将 only_main_content 设置为 False
- 将 exclude_tags 设置为空数组 []
- 确保获取完整的原始 HTML，不做任何过滤
"""

import asyncio
import sys

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def update_task_for_raw_html(task_id: str):
    """更新指定任务的配置以获取原始 HTML"""

    try:
        db = await get_mongodb_database()

        # 查询任务
        task = await db.search_tasks.find_one({"_id": task_id})
        if not task:
            logger.error(f"❌ 任务 {task_id} 不存在")
            return False

        logger.info("=" * 80)
        logger.info(f"📋 更新任务配置: {task.get('name')}")
        logger.info("=" * 80)

        # 获取当前配置
        current_config = task.get('crawl_config', {})

        logger.info(f"\n🔍 当前配置:")
        logger.info(f"  only_main_content: {current_config.get('only_main_content')}")
        logger.info(f"  exclude_tags: {current_config.get('exclude_tags')}")

        # 更新配置为原始 HTML 模式
        current_config['only_main_content'] = False
        current_config['exclude_tags'] = []

        logger.info(f"\n✅ 新配置 (原始 HTML 模式):")
        logger.info(f"  only_main_content: {current_config['only_main_content']}")
        logger.info(f"  exclude_tags: {current_config['exclude_tags']}")

        # 保留其他配置项
        logger.info(f"\n📝 保留的其他配置:")
        logger.info(f"  limit: {current_config.get('limit')}")
        logger.info(f"  max_depth: {current_config.get('max_depth')}")
        logger.info(f"  wait_for: {current_config.get('wait_for')}")
        logger.info(f"  prompt: {current_config.get('prompt')}")

        # 更新数据库
        result = await db.search_tasks.update_one(
            {"_id": task_id},
            {"$set": {"crawl_config": current_config}}
        )

        if result.modified_count > 0:
            logger.info(f"\n✅ 任务配置已更新")
            logger.info(f"\n💡 说明:")
            logger.info(f"  • only_main_content=false - 保留完整页面结构")
            logger.info(f"  • exclude_tags=[] - 不移除任何 HTML 标签")
            logger.info(f"  • 爬取结果将包含导航、页脚、广告等所有元素")
            logger.info(f"  • HTML 文件大小可能增加 2-5 倍")
            return True
        else:
            logger.warning(f"\n⚠️  任务配置未发生变化")
            return False

    except Exception as e:
        logger.error(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def update_all_crawl_tasks():
    """更新所有 crawl_website 类型任务的配置"""

    try:
        db = await get_mongodb_database()

        # 查询所有 crawl_website 任务
        tasks = await db.search_tasks.find({"task_type": "crawl_website"}).to_list(length=100)

        logger.info("=" * 80)
        logger.info(f"📊 批量更新所有爬取任务配置")
        logger.info("=" * 80)
        logger.info(f"\n找到 {len(tasks)} 个爬取任务\n")

        success_count = 0

        for task in tasks:
            task_id = task['_id']
            task_name = task.get('name', '未命名')

            logger.info(f"处理任务: {task_name} ({task_id})")

            # 获取当前配置
            current_config = task.get('crawl_config', {})

            # 更新配置
            current_config['only_main_content'] = False
            current_config['exclude_tags'] = []

            # 更新数据库
            result = await db.search_tasks.update_one(
                {"_id": task_id},
                {"$set": {"crawl_config": current_config}}
            )

            if result.modified_count > 0:
                logger.info(f"  ✅ 已更新\n")
                success_count += 1
            else:
                logger.info(f"  ⚠️  未变化\n")

        logger.info("=" * 80)
        logger.info(f"📈 更新完成: {success_count}/{len(tasks)} 个任务")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 批量更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""

    if len(sys.argv) > 1:
        # 更新指定任务
        task_id = sys.argv[1]
        logger.info(f"\n🎯 更新单个任务: {task_id}\n")
        success = await update_task_for_raw_html(task_id)
    else:
        # 更新所有任务
        logger.info(f"\n🎯 批量更新所有爬取任务\n")
        success = await update_all_crawl_tasks()

    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ 操作完成")
        logger.info("\n下一步:")
        logger.info("  1. 重新执行爬取任务")
        logger.info("  2. 对比 HTML 内容差异")
        logger.info("  3. 验证是否包含导航、页脚等元素")
    else:
        logger.info("❌ 操作失败")
    logger.info("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
