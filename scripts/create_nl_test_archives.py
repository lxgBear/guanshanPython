#!/usr/bin/env python3
"""创建NL Search测试档案数据脚本

用途：为 /api/v1/nl-search/user-archives 接口提供测试数据
集合：user_archives

使用示例：
    # 快速创建5条测试档案
    python scripts/create_nl_test_archives.py --quick 5

    # 为特定用户创建档案
    python scripts/create_nl_test_archives.py --user-id 1001 --count 10

    # 查看已创建的档案
    python scripts/create_nl_test_archives.py --list 10

    # 清理测试数据
    python scripts/create_nl_test_archives.py --cleanup
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
import argparse
from bson import ObjectId

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger
from src.infrastructure.id_generator import generate_id

logger = get_logger(__name__)


class NLArchiveTestDataCreator:
    """NL Search档案测试数据创建器"""

    def __init__(self):
        self.db = None
        self.archives_collection = None
        self.news_results_collection = None

    async def initialize(self):
        """初始化数据库连接"""
        self.db = await get_mongodb_database()
        self.archives_collection = self.db["user_archives"]
        self.news_results_collection = self.db["news_results"]
        logger.info("✅ 数据库连接已建立 (user_archives和news_results集合)")

    async def create_test_archive(
        self,
        user_id: int,
        archive_name: str,
        description: str,
        tags: List[str],
        items_count: int = 3
    ) -> str:
        """创建单个测试档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            description: 档案描述
            tags: 标签列表
            items_count: 档案条目数量

        Returns:
            创建的档案ID
        """
        try:
            now = datetime.utcnow()

            # 创建档案条目（模拟新闻数据）
            items = []
            for i in range(items_count):
                item = {
                    "id": generate_id(),  # 使用雪花ID生成器
                    "news_result_id": str(ObjectId()),  # 模拟news_result_id
                    "edited_title": f"{archive_name} - 条目 {i+1}",
                    "edited_summary": f"这是 {archive_name} 的第 {i+1} 个条目的摘要内容。包含详细的信息和数据。",
                    "user_notes": f"用户备注 {i+1}",
                    "user_rating": (i % 5) + 1,  # 评分1-5
                    "snapshot_data": {
                        "original_title": f"原始标题 {i+1}",
                        "original_url": f"https://example.com/news/{i+1}",
                        "original_summary": f"原始摘要内容 {i+1}...",
                        "published_date": now.isoformat(),
                        "source": "test_source"
                    },
                    "display_order": i,
                    "created_at": now
                }
                items.append(item)

            # 创建档案文档
            document = {
                "user_id": user_id,
                "archive_name": archive_name,
                "description": description,
                "tags": tags,
                "search_log_id": None,
                "items": items,
                "items_count": len(items),
                "created_at": now,
                "updated_at": now,
                "metadata": {"test": True}  # 标记为测试数据
            }

            # 插入数据库
            result = await self.archives_collection.insert_one(document)
            archive_id = str(result.inserted_id)

            logger.info(f"✅ 创建档案: {archive_id} - {archive_name} ({items_count}个条目)")
            return archive_id

        except Exception as e:
            logger.error(f"❌ 创建档案失败: {e}")
            raise

    async def quick_create(self, user_id: int, count: int) -> List[str]:
        """快速创建多个测试档案

        Args:
            user_id: 用户ID
            count: 创建数量

        Returns:
            创建的档案ID列表
        """
        archive_ids = []

        # 预定义的档案模板
        templates = [
            {
                "name": "AI技术突破 #{n}",
                "description": "2024年人工智能领域的重要技术突破汇总",
                "tags": ["AI", "技术", "突破"],
                "items_count": 3
            },
            {
                "name": "区块链应用 #{n}",
                "description": "区块链技术在各行业的创新应用案例",
                "tags": ["区块链", "应用", "创新"],
                "items_count": 4
            },
            {
                "name": "量子计算进展 #{n}",
                "description": "量子计算领域的最新研究成果",
                "tags": ["量子计算", "科研", "前沿"],
                "items_count": 2
            },
            {
                "name": "5G网络部署 #{n}",
                "description": "全球5G网络建设和商用进展",
                "tags": ["5G", "通信", "网络"],
                "items_count": 5
            },
            {
                "name": "清洁能源发展 #{n}",
                "description": "可再生能源和新能源技术发展动态",
                "tags": ["能源", "环保", "可持续"],
                "items_count": 3
            }
        ]

        for i in range(count):
            template = templates[i % len(templates)]
            archive_id = await self.create_test_archive(
                user_id=user_id,
                archive_name=template["name"].replace("{n}", str(i+1)),
                description=template["description"],
                tags=template["tags"],
                items_count=template["items_count"]
            )
            archive_ids.append(archive_id)
            logger.info(f"进度: {i+1}/{count}")

        return archive_ids

    async def create_from_news_results(
        self,
        user_id: int,
        archive_name: str,
        description: str,
        news_count: int = 3,
        tags: List[str] = None
    ) -> str:
        """从news_results表中读取真实新闻创建档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            description: 档案描述
            news_count: 要包含的新闻条目数量
            tags: 标签列表

        Returns:
            创建的档案ID
        """
        try:
            # 从news_results表中随机获取新闻
            cursor = self.news_results_collection.aggregate([
                {"$sample": {"size": news_count}}
            ])
            news_list = await cursor.to_list(length=news_count)

            if not news_list:
                logger.warning("⚠️ news_results表中没有数据")
                return None

            now = datetime.utcnow()
            items = []

            for i, news in enumerate(news_list):
                # 从真实新闻数据构建档案条目
                item = {
                    "id": generate_id(),  # 使用雪花ID生成器
                    "news_result_id": news.get("_id"),
                    "edited_title": news.get("title", f"新闻标题 {i+1}"),
                    "edited_summary": news.get("snippet", news.get("content", "")[:200]),
                    "user_notes": f"来自真实新闻数据 {i+1}",
                    "user_rating": 5,
                    "snapshot_data": {
                        "original_title": news.get("title"),
                        "original_url": news.get("url") or news.get("source_url"),
                        "original_summary": news.get("snippet") or news.get("content", "")[:200],
                        "published_date": news.get("published_date") or news.get("created_at").isoformat() if news.get("created_at") else now.isoformat(),
                        "source": news.get("source", "未知来源"),
                        "content": news.get("content"),
                        "categories": news.get("categories", []),
                        "quality_score": news.get("quality_score"),
                        "relevance_score": news.get("relevance_score")
                    },
                    "display_order": i,
                    "created_at": now
                }
                items.append(item)

            # 创建档案文档
            document = {
                "user_id": user_id,
                "archive_name": archive_name,
                "description": description,
                "tags": tags or ["真实数据", "新闻"],
                "search_log_id": None,
                "items": items,
                "items_count": len(items),
                "created_at": now,
                "updated_at": now,
                "metadata": {"test": True, "data_source": "news_results"}
            }

            # 插入数据库
            result = await self.archives_collection.insert_one(document)
            archive_id = str(result.inserted_id)

            logger.info(f"✅ 从真实新闻创建档案: {archive_id} - {archive_name} ({len(items)}个条目)")
            return archive_id

        except Exception as e:
            logger.error(f"❌ 从新闻创建档案失败: {e}")
            raise

    async def list_archives(self, user_id: int = None, limit: int = 10):
        """列出档案列表

        Args:
            user_id: 用户ID筛选（可选）
            limit: 返回数量限制
        """
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id

            cursor = self.archives_collection.find(query).sort("created_at", -1).limit(limit)
            archives = await cursor.to_list(length=limit)

            print(f"\n📋 档案列表 (共 {len(archives)} 条):")
            print("=" * 80)

            for idx, archive in enumerate(archives, 1):
                archive_id = str(archive["_id"])
                user_id = archive.get("user_id", "N/A")
                name = archive.get("archive_name", "N/A")
                items_count = archive.get("items_count", 0)
                created_at = archive.get("created_at", "N/A")
                tags = archive.get("tags", [])

                print(f"{idx}. [{archive_id}]")
                print(f"   用户: {user_id} | 名称: {name}")
                print(f"   条目数: {items_count} | 标签: {', '.join(tags)}")
                print(f"   创建时间: {created_at}")
                print()

        except Exception as e:
            logger.error(f"❌ 查询档案列表失败: {e}")
            raise

    async def cleanup_test_data(self, user_id: int = None):
        """清理测试数据

        Args:
            user_id: 用户ID筛选（可选，如果提供则只删除该用户的测试数据）
        """
        try:
            query = {"metadata.test": True}
            if user_id:
                query["user_id"] = user_id

            result = await self.archives_collection.delete_many(query)
            logger.info(f"🗑️  删除测试档案: {result.deleted_count} 条")

            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 清理测试数据失败: {e}")
            raise

    async def get_stats(self, user_id: int = None):
        """获取统计信息

        Args:
            user_id: 用户ID筛选（可选）
        """
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id

            total = await self.archives_collection.count_documents(query)
            test_count = await self.archives_collection.count_documents({**query, "metadata.test": True})

            print(f"\n📊 统计信息:")
            print(f"- 总档案数: {total}")
            print(f"- 测试档案数: {test_count}")
            print(f"- 正式档案数: {total - test_count}")

            if user_id:
                print(f"- 用户ID: {user_id}")

        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            raise


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="创建NL Search测试档案数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 快速创建5条测试档案（默认user_id=1001，使用假数据）
  python scripts/create_nl_test_archives.py --quick 5

  # 使用真实新闻数据创建档案（从news_results表）
  python scripts/create_nl_test_archives.py --real 3

  # 为指定用户创建档案
  python scripts/create_nl_test_archives.py --user-id 2001 --count 10

  # 查看档案列表
  python scripts/create_nl_test_archives.py --list 20

  # 查看指定用户的档案
  python scripts/create_nl_test_archives.py --user-id 1001 --list 10

  # 查看统计信息
  python scripts/create_nl_test_archives.py --stats

  # 清理所有测试数据
  python scripts/create_nl_test_archives.py --cleanup

  # 只清理指定用户的测试数据
  python scripts/create_nl_test_archives.py --user-id 1001 --cleanup
        """
    )

    parser.add_argument("--user-id", type=int, default=1001, help="用户ID (默认: 1001)")
    parser.add_argument("--quick", type=int, metavar="N", help="快速创建N条测试档案（假数据）")
    parser.add_argument("--real", type=int, metavar="N", help="从news_results创建N条真实数据档案")
    parser.add_argument("--count", type=int, metavar="N", help="创建N条档案（同--quick）")
    parser.add_argument("--list", type=int, metavar="N", help="列出最近N条档案")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--cleanup", action="store_true", help="清理测试数据")

    args = parser.parse_args()

    creator = NLArchiveTestDataCreator()
    await creator.initialize()

    try:
        # 清理模式
        if args.cleanup:
            print(f"\n⚠️  警告: 即将删除测试数据!")
            if args.user_id != 1001:
                print(f"   范围: 用户ID={args.user_id}的测试档案")
            else:
                print("   范围: 所有测试档案")

            confirm = input("确认继续? (yes/no): ").strip().lower()
            if confirm == "yes":
                count = await creator.cleanup_test_data(args.user_id if args.user_id != 1001 else None)
                print(f"\n✅ 清理完成: 删除 {count} 条档案")
            else:
                print("❌ 已取消")
            return

        # 统计模式
        if args.stats:
            await creator.get_stats(args.user_id if args.user_id != 1001 else None)
            return

        # 列表模式
        if args.list:
            await creator.list_archives(args.user_id if args.user_id != 1001 else None, args.list)
            return

        # 真实新闻数据创建模式
        if args.real:
            print(f"\n📰 从news_results表创建 {args.real} 条真实新闻档案...")
            print(f"   用户ID: {args.user_id}")

            archive_ids = []
            for i in range(args.real):
                archive_id = await creator.create_from_news_results(
                    user_id=args.user_id,
                    archive_name=f"真实新闻档案 #{i+1}",
                    description=f"从news_results表获取的真实新闻数据",
                    news_count=3,
                    tags=["真实数据", "新闻"]
                )
                if archive_id:
                    archive_ids.append(archive_id)
                logger.info(f"进度: {i+1}/{args.real}")

            print(f"\n✅ 成功创建 {len(archive_ids)} 条真实新闻档案")
            print(f"\n验证命令:")
            print(f"curl \"http://localhost:8000/api/v1/nl-search/user-archives?user_id={args.user_id}&limit=10&offset=0\"")
            return

        # 创建模式
        count = args.quick or args.count
        if count:
            print(f"\n🚀 快速创建 {count} 条测试档案...")
            print(f"   用户ID: {args.user_id}")

            archive_ids = await creator.quick_create(args.user_id, count)

            print(f"\n✅ 成功创建 {len(archive_ids)} 条档案")
            print(f"\n验证命令:")
            print(f"curl \"http://localhost:8000/api/v1/nl-search/user-archives?user_id={args.user_id}&limit=10&offset=0\"")
            return

        # 默认：显示帮助
        parser.print_help()

    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
