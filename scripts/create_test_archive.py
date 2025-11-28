#!/usr/bin/env python3
"""创建测试存档数据脚本

用途：为前端调试提供快速创建存档数据的功能
运行方式：python scripts/create_test_archive.py [options]

使用示例：
    # 交互式创建
    python scripts/create_test_archive.py

    # 命令行参数创建
    python scripts/create_test_archive.py \
        --title "测试新闻" \
        --url "https://example.com/news" \
        --content "这是一篇测试新闻的完整内容..." \
        --creator "test_user"

    # 批量创建（使用JSON文件）
    python scripts/create_test_archive.py --batch test_data.json

    # 快速创建（使用默认值）
    python scripts/create_test_archive.py --quick
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import argparse
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.data_source import (
    DataSource,
    RawDataReference,
    DataSourceStatus,
    DataSourceType
)
from src.core.domain.entities.archived_data import ArchivedData
from src.infrastructure.id_generator import generate_string_id
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ArchiveTestDataCreator:
    """存档测试数据创建器"""

    def __init__(self):
        self.db = None
        self.data_sources_collection = None
        self.archives_collection = None

    async def initialize(self):
        """初始化数据库连接"""
        self.db = await get_mongodb_database()
        self.data_sources_collection = self.db["data_sources"]
        self.archives_collection = self.db["data_source_archived_data"]
        logger.info("✅ 数据库连接已建立")

    async def create_archive_from_text(
        self,
        title: str,
        url: str,
        content: str,
        creator: str = "test_user",
        description: str = "",
        snippet: Optional[str] = None,
        data_type: str = "instant",
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        custom_tags: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """从文本创建完整的存档数据

        Args:
            title: 标题
            url: URL
            content: 完整内容
            creator: 创建者
            description: 数据源描述
            snippet: 摘要（可选，默认使用content前150字符）
            data_type: 数据类型（instant或scheduled）
            primary_category: 第一级分类
            secondary_category: 第二级分类
            tertiary_category: 第三级分类
            custom_tags: 自定义标签列表

        Returns:
            包含data_source_id和archive_id的字典
        """
        try:
            # 1. 生成ID
            original_data_id = generate_string_id()
            data_source_id = generate_string_id()
            archive_id = generate_string_id()

            # 2. 创建snippet（如果未提供）
            if snippet is None:
                snippet = content[:150] + "..." if len(content) > 150 else content

            # 3. 创建RawDataReference
            raw_data_ref = RawDataReference(
                data_id=original_data_id,
                data_type=data_type,
                title=title,
                url=url,
                snippet=snippet,
                added_at=datetime.utcnow(),
                added_by=creator
            )

            # 4. 创建DataSource（已确定状态）
            data_source = DataSource(
                id=data_source_id,
                title=title if not description else f"{title}的数据源",
                description=description or f"测试数据源 - {title}",
                source_type=DataSourceType.INSTANT if data_type == "instant" else DataSourceType.SCHEDULED,
                status=DataSourceStatus.CONFIRMED,
                raw_data_refs=[raw_data_ref],
                created_by=creator,
                created_at=datetime.utcnow(),
                confirmed_by=creator,
                confirmed_at=datetime.utcnow(),
                updated_by=creator,
                updated_at=datetime.utcnow(),
                primary_category=primary_category,
                secondary_category=secondary_category,
                tertiary_category=tertiary_category,
                custom_tags=custom_tags or []
            )

            # 5. 创建ArchivedData
            archived_data = ArchivedData(
                id=archive_id,
                data_source_id=data_source_id,
                original_data_id=original_data_id,
                data_type=data_type,
                title=title,
                url=url,
                content=content,
                snippet=snippet,
                archived_at=datetime.utcnow(),
                archived_by=creator,
                archived_reason="confirm",
                original_created_at=datetime.utcnow(),
                original_status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={"test": True, "creator": creator}
            )

            # 6. 保存到MongoDB
            await self.data_sources_collection.insert_one(
                self._data_source_to_dict(data_source)
            )
            logger.info(f"✅ 创建数据源: {data_source_id}")

            await self.archives_collection.insert_one(
                self._archived_data_to_dict(archived_data)
            )
            logger.info(f"✅ 创建存档: {archive_id}")

            return {
                "data_source_id": data_source_id,
                "archive_id": archive_id,
                "original_data_id": original_data_id
            }

        except Exception as e:
            logger.error(f"❌ 创建存档数据失败: {e}")
            raise

    async def batch_create_from_json(self, json_file_path: str) -> List[Dict[str, str]]:
        """从JSON文件批量创建存档数据

        JSON格式示例:
        [
            {
                "title": "新闻标题1",
                "url": "https://example.com/1",
                "content": "完整内容...",
                "creator": "user1",
                "description": "数据源描述",
                "primary_category": "新闻",
                "secondary_category": "科技",
                "custom_tags": ["AI", "技术"]
            },
            ...
        ]

        Args:
            json_file_path: JSON文件路径

        Returns:
            创建结果列表
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data_list = json.load(f)

            results = []
            for idx, data in enumerate(data_list, 1):
                logger.info(f"🔄 创建第 {idx}/{len(data_list)} 条数据...")
                result = await self.create_archive_from_text(**data)
                results.append(result)

            logger.info(f"✅ 批量创建完成: {len(results)} 条")
            return results

        except Exception as e:
            logger.error(f"❌ 批量创建失败: {e}")
            raise

    async def quick_create(self, count: int = 1) -> List[Dict[str, str]]:
        """快速创建测试数据（使用默认值）

        Args:
            count: 创建数量

        Returns:
            创建结果列表
        """
        results = []
        for i in range(1, count + 1):
            result = await self.create_archive_from_text(
                title=f"测试新闻 #{i}",
                url=f"https://example.com/test-news-{i}",
                content=f"这是第{i}条测试新闻的完整内容。\n\n" +
                        "这篇文章包含了详细的信息和数据。" * 10,
                creator="test_user",
                description=f"测试数据源 #{i}",
                data_type="instant",
                primary_category="测试",
                secondary_category="自动生成",
                custom_tags=["test", f"batch-{i}"]
            )
            results.append(result)
            logger.info(f"✅ 快速创建进度: {i}/{count}")

        return results

    async def list_recent_archives(self, limit: int = 10):
        """列出最近创建的存档"""
        cursor = self.archives_collection.find().sort("created_at", -1).limit(limit)
        archives = await cursor.to_list(length=limit)

        print(f"\n📋 最近 {len(archives)} 条存档:")
        print("-" * 80)
        for idx, archive in enumerate(archives, 1):
            print(f"{idx}. [{archive['id']}] {archive.get('title', 'N/A')}")
            print(f"   URL: {archive.get('url', 'N/A')}")
            print(f"   创建时间: {archive.get('created_at', 'N/A')}")
            print(f"   数据源ID: {archive.get('data_source_id', 'N/A')}")
            print()

    async def cleanup_test_data(self):
        """清理测试数据（删除metadata.test=true的记录）"""
        # 删除测试存档
        archive_result = await self.archives_collection.delete_many(
            {"metadata.test": True}
        )
        logger.info(f"🗑️  删除测试存档: {archive_result.deleted_count} 条")

        # 删除测试数据源
        ds_result = await self.data_sources_collection.delete_many(
            {"metadata.test": True}
        )
        logger.info(f"🗑️  删除测试数据源: {ds_result.deleted_count} 条")

        return {
            "archives_deleted": archive_result.deleted_count,
            "data_sources_deleted": ds_result.deleted_count
        }

    def _data_source_to_dict(self, data_source: DataSource) -> Dict[str, Any]:
        """DataSource转MongoDB文档"""
        return {
            "id": data_source.id,
            "title": data_source.title,
            "description": data_source.description,
            "source_type": data_source.source_type.value,
            "status": data_source.status.value,
            "raw_data_refs": [ref.to_dict() for ref in data_source.raw_data_refs],
            "edited_content": data_source.edited_content,
            "content_version": data_source.content_version,
            "total_raw_data_count": data_source.total_raw_data_count,
            "scheduled_data_count": data_source.scheduled_data_count,
            "instant_data_count": data_source.instant_data_count,
            "created_by": data_source.created_by,
            "created_at": data_source.created_at,
            "confirmed_by": data_source.confirmed_by,
            "confirmed_at": data_source.confirmed_at,
            "updated_by": data_source.updated_by,
            "updated_at": data_source.updated_at,
            "tags": data_source.tags,
            "metadata": {"test": True},  # 标记为测试数据
            "primary_category": data_source.primary_category,
            "secondary_category": data_source.secondary_category,
            "tertiary_category": data_source.tertiary_category,
            "custom_tags": data_source.custom_tags
        }

    def _archived_data_to_dict(self, archived_data: ArchivedData) -> Dict[str, Any]:
        """ArchivedData转MongoDB文档"""
        return {
            "id": archived_data.id,
            "data_source_id": archived_data.data_source_id,
            "original_data_id": archived_data.original_data_id,
            "data_type": archived_data.data_type,
            "title": archived_data.title,
            "url": archived_data.url,
            "content": archived_data.content,
            "snippet": archived_data.snippet,
            "published_date": archived_data.published_date,
            "markdown_content": archived_data.markdown_content,
            "html_content": archived_data.html_content,
            "type_specific_fields": archived_data.type_specific_fields,
            "metadata": archived_data.metadata,
            "archived_at": archived_data.archived_at,
            "archived_by": archived_data.archived_by,
            "archived_reason": archived_data.archived_reason,
            "original_created_at": archived_data.original_created_at,
            "original_status": archived_data.original_status,
            "created_at": archived_data.created_at,
            "updated_at": archived_data.updated_at,
        }


async def interactive_create():
    """交互式创建存档"""
    print("\n🎯 交互式创建存档数据")
    print("=" * 80)

    title = input("标题: ").strip()
    url = input("URL: ").strip()

    print("\n内容（输入多行内容，输入单独一行'END'结束）:")
    content_lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        content_lines.append(line)
    content = "\n".join(content_lines)

    creator = input("\n创建者 [test_user]: ").strip() or "test_user"
    description = input("数据源描述 [可选]: ").strip()

    # 分类信息
    primary_category = input("一级分类 [可选]: ").strip() or None
    secondary_category = input("二级分类 [可选]: ").strip() or None
    tertiary_category = input("三级分类 [可选]: ").strip() or None

    tags_input = input("自定义标签（逗号分隔）[可选]: ").strip()
    custom_tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else None

    creator_obj = ArchiveTestDataCreator()
    await creator_obj.initialize()

    result = await creator_obj.create_archive_from_text(
        title=title,
        url=url,
        content=content,
        creator=creator,
        description=description,
        primary_category=primary_category,
        secondary_category=secondary_category,
        tertiary_category=tertiary_category,
        custom_tags=custom_tags
    )

    print("\n✅ 创建成功!")
    print(f"数据源ID: {result['data_source_id']}")
    print(f"存档ID: {result['archive_id']}")
    print(f"原始数据ID: {result['original_data_id']}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="创建测试存档数据脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 交互式创建
  python scripts/create_test_archive.py

  # 命令行参数创建
  python scripts/create_test_archive.py --title "测试" --url "https://test.com" --content "内容"

  # 快速创建5条测试数据
  python scripts/create_test_archive.py --quick 5

  # 批量创建（从JSON文件）
  python scripts/create_test_archive.py --batch test_data.json

  # 列出最近的存档
  python scripts/create_test_archive.py --list 20

  # 清理测试数据
  python scripts/create_test_archive.py --cleanup
        """
    )

    parser.add_argument("--title", help="标题")
    parser.add_argument("--url", help="URL")
    parser.add_argument("--content", help="完整内容")
    parser.add_argument("--creator", default="test_user", help="创建者 (默认: test_user)")
    parser.add_argument("--description", help="数据源描述")
    parser.add_argument("--snippet", help="摘要")
    parser.add_argument("--data-type", choices=["instant", "scheduled"],
                       default="instant", help="数据类型 (默认: instant)")

    # 分类参数
    parser.add_argument("--primary-category", help="一级分类")
    parser.add_argument("--secondary-category", help="二级分类")
    parser.add_argument("--tertiary-category", help="三级分类")
    parser.add_argument("--tags", help="自定义标签（逗号分隔）")

    # 模式选择
    parser.add_argument("--quick", type=int, metavar="N",
                       help="快速创建N条测试数据")
    parser.add_argument("--batch", metavar="JSON_FILE",
                       help="从JSON文件批量创建")
    parser.add_argument("--list", type=int, metavar="N",
                       help="列出最近N条存档")
    parser.add_argument("--cleanup", action="store_true",
                       help="清理所有测试数据")

    args = parser.parse_args()

    creator = ArchiveTestDataCreator()
    await creator.initialize()

    try:
        # 清理模式
        if args.cleanup:
            print("\n⚠️  警告: 即将删除所有测试数据!")
            confirm = input("确认继续? (yes/no): ").strip().lower()
            if confirm == "yes":
                result = await creator.cleanup_test_data()
                print(f"\n✅ 清理完成:")
                print(f"   删除存档: {result['archives_deleted']} 条")
                print(f"   删除数据源: {result['data_sources_deleted']} 条")
            else:
                print("❌ 已取消")
            return

        # 列表模式
        if args.list:
            await creator.list_recent_archives(args.list)
            return

        # 快速创建模式
        if args.quick:
            print(f"\n🚀 快速创建 {args.quick} 条测试数据...")
            results = await creator.quick_create(args.quick)
            print(f"\n✅ 成功创建 {len(results)} 条数据")
            for idx, result in enumerate(results, 1):
                print(f"{idx}. 数据源ID: {result['data_source_id']}, "
                      f"存档ID: {result['archive_id']}")
            return

        # 批量创建模式
        if args.batch:
            print(f"\n📦 从文件批量创建: {args.batch}")
            results = await creator.batch_create_from_json(args.batch)
            print(f"\n✅ 成功创建 {len(results)} 条数据")
            return

        # 命令行参数创建模式
        if args.title and args.url and args.content:
            custom_tags = [tag.strip() for tag in args.tags.split(",")] if args.tags else None

            result = await creator.create_archive_from_text(
                title=args.title,
                url=args.url,
                content=args.content,
                creator=args.creator,
                description=args.description or "",
                snippet=args.snippet,
                data_type=args.data_type,
                primary_category=args.primary_category,
                secondary_category=args.secondary_category,
                tertiary_category=args.tertiary_category,
                custom_tags=custom_tags
            )

            print("\n✅ 创建成功!")
            print(f"数据源ID: {result['data_source_id']}")
            print(f"存档ID: {result['archive_id']}")
            print(f"原始数据ID: {result['original_data_id']}")
            return

        # 默认：交互式创建
        await interactive_create()

    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
    except Exception as e:
        logger.error(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
