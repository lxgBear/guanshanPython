#!/usr/bin/env python3
"""
数据库迁移脚本：为搜索结果添加status字段

功能：
- 为 search_results 集合添加 status 字段（默认值：pending）
- 为 instant_search_results 集合添加 status 字段（默认值：pending）
- 幂等操作（可安全重复运行）
- 提供进度跟踪和错误处理

运行方式：
    python migrations/add_status_field_to_search_results.py

环境变量：
    使用 .env 文件中的 MONGODB_URL 配置
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


class StatusFieldMigration:
    """Status字段迁移器"""

    def __init__(self, db_url: str, db_name: str):
        """初始化迁移器

        Args:
            db_url: MongoDB连接URL
            db_name: 数据库名称
        """
        self.client = AsyncIOMotorClient(db_url)
        self.db = self.client[db_name]
        self.search_results_collection = self.db.search_results
        self.instant_search_results_collection = self.db.instant_search_results

    async def close(self):
        """关闭数据库连接"""
        self.client.close()

    async def migrate_search_results(self) -> dict:
        """迁移search_results集合

        Returns:
            迁移结果统计
        """
        logger.info("📊 开始迁移 search_results 集合...")

        # 统计需要迁移的文档数
        total_count = await self.search_results_collection.count_documents({})
        logger.info(f"总文档数: {total_count}")

        # 查找没有status字段的文档
        no_status_count = await self.search_results_collection.count_documents(
            {"status": {"$exists": False}}
        )
        logger.info(f"需要添加status字段的文档数: {no_status_count}")

        if no_status_count == 0:
            logger.info("✅ 所有文档已有status字段，无需迁移")
            return {
                "collection": "search_results",
                "total": total_count,
                "migrated": 0,
                "already_migrated": total_count,
                "success": True
            }

        # 批量更新：添加status字段
        try:
            result = await self.search_results_collection.update_many(
                {"status": {"$exists": False}},
                {
                    "$set": {
                        "status": "pending",
                        "processed_at": None
                    }
                }
            )

            migrated_count = result.modified_count
            logger.info(f"✅ 成功迁移 {migrated_count} 条文档")

            return {
                "collection": "search_results",
                "total": total_count,
                "migrated": migrated_count,
                "already_migrated": total_count - migrated_count,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ 迁移失败: {str(e)}")
            return {
                "collection": "search_results",
                "total": total_count,
                "migrated": 0,
                "error": str(e),
                "success": False
            }

    async def migrate_instant_search_results(self) -> dict:
        """迁移instant_search_results集合

        Returns:
            迁移结果统计
        """
        logger.info("📊 开始迁移 instant_search_results 集合...")

        # 统计需要迁移的文档数
        total_count = await self.instant_search_results_collection.count_documents({})
        logger.info(f"总文档数: {total_count}")

        # 查找没有status字段的文档
        no_status_count = await self.instant_search_results_collection.count_documents(
            {"status": {"$exists": False}}
        )
        logger.info(f"需要添加status字段的文档数: {no_status_count}")

        if no_status_count == 0:
            logger.info("✅ 所有文档已有status字段，无需迁移")
            return {
                "collection": "instant_search_results",
                "total": total_count,
                "migrated": 0,
                "already_migrated": total_count,
                "success": True
            }

        # 批量更新：添加status字段
        try:
            result = await self.instant_search_results_collection.update_many(
                {"status": {"$exists": False}},
                {
                    "$set": {
                        "status": "pending"
                    }
                }
            )

            migrated_count = result.modified_count
            logger.info(f"✅ 成功迁移 {migrated_count} 条文档")

            return {
                "collection": "instant_search_results",
                "total": total_count,
                "migrated": migrated_count,
                "already_migrated": total_count - migrated_count,
                "success": True
            }

        except Exception as e:
            logger.error(f"❌ 迁移失败: {str(e)}")
            return {
                "collection": "instant_search_results",
                "total": total_count,
                "migrated": 0,
                "error": str(e),
                "success": False
            }

    async def run_migration(self) -> dict:
        """运行完整迁移

        Returns:
            迁移结果汇总
        """
        logger.info("=" * 60)
        logger.info("🚀 开始数据库迁移：添加status字段")
        logger.info("=" * 60)

        start_time = datetime.now()

        # 迁移 search_results
        search_results_result = await self.migrate_search_results()

        # 迁移 instant_search_results
        instant_search_results_result = await self.migrate_instant_search_results()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 汇总结果
        summary = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "results": {
                "search_results": search_results_result,
                "instant_search_results": instant_search_results_result
            },
            "overall_success": (
                search_results_result["success"] and
                instant_search_results_result["success"]
            )
        }

        # 打印汇总报告
        logger.info("\n" + "=" * 60)
        logger.info("📋 迁移完成报告")
        logger.info("=" * 60)
        logger.info(f"总耗时: {duration:.2f}秒")
        logger.info(f"\n1. search_results:")
        logger.info(f"   - 总文档数: {search_results_result['total']}")
        logger.info(f"   - 本次迁移: {search_results_result['migrated']}")
        logger.info(f"   - 已有字段: {search_results_result.get('already_migrated', 0)}")
        logger.info(f"\n2. instant_search_results:")
        logger.info(f"   - 总文档数: {instant_search_results_result['total']}")
        logger.info(f"   - 本次迁移: {instant_search_results_result['migrated']}")
        logger.info(f"   - 已有字段: {instant_search_results_result.get('already_migrated', 0)}")

        if summary["overall_success"]:
            logger.info("\n✅ 迁移全部成功！")
        else:
            logger.error("\n❌ 迁移过程中出现错误，请检查日志")

        logger.info("=" * 60)

        return summary

    async def verify_migration(self) -> dict:
        """验证迁移结果

        Returns:
            验证结果
        """
        logger.info("\n" + "=" * 60)
        logger.info("🔍 验证迁移结果...")
        logger.info("=" * 60)

        # 验证 search_results
        search_no_status = await self.search_results_collection.count_documents(
            {"status": {"$exists": False}}
        )
        search_with_status = await self.search_results_collection.count_documents(
            {"status": {"$exists": True}}
        )

        # 验证 instant_search_results
        instant_no_status = await self.instant_search_results_collection.count_documents(
            {"status": {"$exists": False}}
        )
        instant_with_status = await self.instant_search_results_collection.count_documents(
            {"status": {"$exists": True}}
        )

        verification = {
            "search_results": {
                "with_status": search_with_status,
                "without_status": search_no_status,
                "pass": search_no_status == 0
            },
            "instant_search_results": {
                "with_status": instant_with_status,
                "without_status": instant_no_status,
                "pass": instant_no_status == 0
            }
        }

        logger.info(f"\n1. search_results:")
        logger.info(f"   - 有status字段: {search_with_status}")
        logger.info(f"   - 无status字段: {search_no_status}")
        logger.info(f"   - 验证结果: {'✅ 通过' if verification['search_results']['pass'] else '❌ 失败'}")

        logger.info(f"\n2. instant_search_results:")
        logger.info(f"   - 有status字段: {instant_with_status}")
        logger.info(f"   - 无status字段: {instant_no_status}")
        logger.info(f"   - 验证结果: {'✅ 通过' if verification['instant_search_results']['pass'] else '❌ 失败'}")

        overall_pass = (
            verification["search_results"]["pass"] and
            verification["instant_search_results"]["pass"]
        )

        if overall_pass:
            logger.info("\n✅ 验证通过：所有文档都已有status字段")
        else:
            logger.error("\n❌ 验证失败：仍有文档缺少status字段")

        logger.info("=" * 60)

        return verification


async def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()

    db_url = os.getenv("MONGODB_URL")
    db_name = os.getenv("MONGODB_DATABASE", "guanshan_search")

    if not db_url:
        logger.error("❌ 缺少环境变量 MONGODB_URL")
        sys.exit(1)

    logger.info(f"数据库连接: {db_url}")
    logger.info(f"数据库名称: {db_name}")

    # 创建迁移器
    migrator = StatusFieldMigration(db_url, db_name)

    try:
        # 运行迁移
        migration_result = await migrator.run_migration()

        # 验证迁移
        verification_result = await migrator.verify_migration()

        # 返回成功或失败状态码
        if migration_result["overall_success"] and all(
            v["pass"] for v in verification_result.values()
        ):
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ 迁移过程发生异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())
