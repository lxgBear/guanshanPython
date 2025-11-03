#!/usr/bin/env python3
"""
数据源存档历史数据迁移脚本
Archive Historical Data Migration Script

功能：
1. 迁移历史上已确认的数据源，将其原始数据存档
2. 避免重复存档（检查已存在的存档记录）
3. 支持批量处理和错误恢复
4. 提供详细的进度显示和日志
5. 支持干运行模式（预览不实际执行）

使用方法：
    # 干运行（不实际存档，只显示统计）
    python scripts/migrate_archive_historical_data.py --dry-run

    # 实际执行存档（全部已确认的数据源）
    python scripts/migrate_archive_historical_data.py

    # 指定存档操作者
    python scripts/migrate_archive_historical_data.py --archived-by "admin@example.com"

    # 限制处理数量（用于测试）
    python scripts/migrate_archive_historical_data.py --limit 10 --dry-run

注意事项：
- 此脚本仅处理状态为 CONFIRMED 的数据源
- 已存档的数据不会重复存档
- 出错的记录会被记录但不会中断整体流程
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

def print_step(step: int, total: int, text: str):
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}[{step}/{total}] {text}{Colors.RESET}")


class ArchiveDataMigrator:
    """历史数据存档迁移器"""

    def __init__(self, db, archived_by: str = "migration_script"):
        self.db = db
        self.archived_by = archived_by

        # 集合引用
        self.data_source_collection = db.data_sources
        self.search_results_collection = db.search_results
        self.instant_results_collection = db.instant_search_results
        self.archived_data_collection = db.data_source_archived_data

        # 统计信息
        self.stats = {
            'total_data_sources': 0,
            'confirmed_data_sources': 0,
            'data_sources_processed': 0,
            'scheduled_archived': 0,
            'instant_archived': 0,
            'already_archived': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

        self.error_log = []

    async def get_confirmed_data_sources(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有已确认的数据源"""
        print_info("查询已确认的数据源...")

        query = {"status": "CONFIRMED"}
        cursor = self.data_source_collection.find(query)

        if limit:
            cursor = cursor.limit(limit)

        data_sources = await cursor.to_list(length=None)

        print_success(f"找到 {len(data_sources)} 个已确认的数据源")
        return data_sources

    async def check_already_archived(self, original_data_id: str, data_type: str) -> bool:
        """检查数据是否已经存档"""
        existing = await self.archived_data_collection.find_one({
            "original_data_id": original_data_id,
            "data_type": data_type
        })
        return existing is not None

    async def archive_scheduled_data(self, data_id: str, data_source_id: str, dry_run: bool = False) -> bool:
        """存档scheduled类型数据"""
        try:
            # 检查是否已存档
            if await self.check_already_archived(data_id, "scheduled"):
                self.stats['already_archived'] += 1
                return True

            # 获取原始数据
            raw_doc = await self.search_results_collection.find_one({"id": data_id})
            if not raw_doc:
                print_warning(f"    未找到scheduled数据: {data_id}")
                return False

            if not dry_run:
                # 导入实体类
                from src.core.domain.entities.search_result import SearchResult, ResultStatus
                from src.core.domain.entities.archived_data import ArchivedData

                # 转换为实体
                search_result = self._doc_to_search_result(raw_doc)

                # 创建存档记录
                archived_data = ArchivedData.from_search_result(
                    search_result=search_result,
                    data_source_id=data_source_id,
                    archived_by=self.archived_by,
                    archived_reason="migration"
                )

                # 转换为文档并插入
                from src.infrastructure.database.archived_data_repositories import ArchivedDataRepository
                repo = ArchivedDataRepository(self.db)
                doc = repo._to_document(archived_data)
                await self.archived_data_collection.insert_one(doc)

            self.stats['scheduled_archived'] += 1
            return True

        except Exception as e:
            print_error(f"    存档scheduled数据失败 {data_id}: {str(e)}")
            self.error_log.append({
                'data_id': data_id,
                'data_type': 'scheduled',
                'error': str(e)
            })
            self.stats['errors'] += 1
            return False

    async def archive_instant_data(self, data_id: str, data_source_id: str, dry_run: bool = False) -> bool:
        """存档instant类型数据"""
        try:
            # 检查是否已存档
            if await self.check_already_archived(data_id, "instant"):
                self.stats['already_archived'] += 1
                return True

            # 获取原始数据
            raw_doc = await self.instant_results_collection.find_one({"id": data_id})
            if not raw_doc:
                print_warning(f"    未找到instant数据: {data_id}")
                return False

            if not dry_run:
                # 导入实体类
                from src.core.domain.entities.instant_search_result import InstantSearchResult, InstantSearchResultStatus
                from src.core.domain.entities.archived_data import ArchivedData

                # 转换为实体
                instant_result = self._doc_to_instant_search_result(raw_doc)

                # 创建存档记录
                archived_data = ArchivedData.from_instant_search_result(
                    instant_result=instant_result,
                    data_source_id=data_source_id,
                    archived_by=self.archived_by,
                    archived_reason="migration"
                )

                # 转换为文档并插入
                from src.infrastructure.database.archived_data_repositories import ArchivedDataRepository
                repo = ArchivedDataRepository(self.db)
                doc = repo._to_document(archived_data)
                await self.archived_data_collection.insert_one(doc)

            self.stats['instant_archived'] += 1
            return True

        except Exception as e:
            print_error(f"    存档instant数据失败 {data_id}: {str(e)}")
            self.error_log.append({
                'data_id': data_id,
                'data_type': 'instant',
                'error': str(e)
            })
            self.stats['errors'] += 1
            return False

    async def process_data_source(self, data_source: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """处理单个数据源的存档"""
        result = {
            'data_source_id': data_source['id'],
            'title': data_source.get('title', 'Untitled'),
            'scheduled_count': 0,
            'instant_count': 0,
            'success': True,
            'errors': []
        }

        data_source_id = data_source['id']
        print_info(f"  处理数据源: {result['title']} ({data_source_id})")

        # 处理scheduled类型数据
        scheduled_ids = data_source.get('scheduled_result_ids', [])
        if scheduled_ids:
            print_info(f"    存档 {len(scheduled_ids)} 个scheduled结果...")
            for idx, data_id in enumerate(scheduled_ids, 1):
                if await self.archive_scheduled_data(data_id, data_source_id, dry_run):
                    result['scheduled_count'] += 1
                else:
                    result['errors'].append(f"scheduled:{data_id}")
                    result['success'] = False

                # 进度显示
                if idx % 10 == 0 or idx == len(scheduled_ids):
                    print(f"      进度: {idx}/{len(scheduled_ids)}", end='\r')
            print()  # 换行

        # 处理instant类型数据
        instant_ids = data_source.get('instant_result_ids', [])
        if instant_ids:
            print_info(f"    存档 {len(instant_ids)} 个instant结果...")
            for idx, data_id in enumerate(instant_ids, 1):
                if await self.archive_instant_data(data_id, data_source_id, dry_run):
                    result['instant_count'] += 1
                else:
                    result['errors'].append(f"instant:{data_id}")
                    result['success'] = False

                # 进度显示
                if idx % 10 == 0 or idx == len(instant_ids):
                    print(f"      进度: {idx}/{len(instant_ids)}", end='\r')
            print()  # 换行

        if result['success']:
            print_success(f"  完成: scheduled={result['scheduled_count']}, instant={result['instant_count']}")
        else:
            print_warning(f"  部分成功: {len(result['errors'])} 个错误")

        return result

    async def migrate(self, limit: Optional[int] = None, dry_run: bool = False):
        """执行迁移"""
        self.stats['start_time'] = datetime.now()

        print_step(1, 4, "分析现有数据")

        # 获取统计信息
        self.stats['total_data_sources'] = await self.data_source_collection.count_documents({})
        self.stats['confirmed_data_sources'] = await self.data_source_collection.count_documents({"status": "CONFIRMED"})

        print_info(f"总数据源数量: {self.stats['total_data_sources']}")
        print_info(f"已确认数据源: {self.stats['confirmed_data_sources']}")

        if limit:
            print_warning(f"限制处理数量: {limit} 个数据源")

        # 获取已确认的数据源
        print_step(2, 4, "获取待处理数据源")
        data_sources = await self.get_confirmed_data_sources(limit=limit)

        if not data_sources:
            print_warning("没有需要处理的数据源")
            return

        # 处理每个数据源
        print_step(3, 4, "执行存档迁移" + (" [DRY RUN]" if dry_run else ""))

        results = []
        for idx, data_source in enumerate(data_sources, 1):
            print_info(f"[{idx}/{len(data_sources)}] 处理数据源")
            result = await self.process_data_source(data_source, dry_run=dry_run)
            results.append(result)
            self.stats['data_sources_processed'] += 1

        self.stats['end_time'] = datetime.now()

        # 显示总结
        print_step(4, 4, "迁移总结")
        self.print_summary(results, dry_run)

    def print_summary(self, results: List[Dict[str, Any]], dry_run: bool):
        """打印迁移总结"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        print(f"\n{Colors.BOLD}迁移统计:{Colors.RESET}")
        print(f"  总数据源数量: {self.stats['total_data_sources']}")
        print(f"  已确认数据源: {self.stats['confirmed_data_sources']}")
        print(f"  已处理数据源: {self.stats['data_sources_processed']}")
        print(f"  Scheduled存档: {self.stats['scheduled_archived']}")
        print(f"  Instant存档: {self.stats['instant_archived']}")
        print(f"  已存在跳过: {self.stats['already_archived']}")
        print(f"  错误数量: {self.stats['errors']}")
        print(f"  耗时: {duration:.2f} 秒")

        if dry_run:
            print_warning("\n这是干运行模式，没有实际写入数据库")

        if self.error_log:
            print(f"\n{Colors.RED}错误详情:{Colors.RESET}")
            for err in self.error_log[:10]:  # 只显示前10个错误
                print(f"  • {err['data_type']}:{err['data_id']} - {err['error']}")
            if len(self.error_log) > 10:
                print(f"  ... 还有 {len(self.error_log) - 10} 个错误未显示")

        # 成功率统计
        total_items = self.stats['scheduled_archived'] + self.stats['instant_archived'] + self.stats['errors']
        if total_items > 0:
            success_rate = ((self.stats['scheduled_archived'] + self.stats['instant_archived']) / total_items) * 100
            print(f"\n{Colors.BOLD}成功率: {success_rate:.2f}%{Colors.RESET}")

    def _doc_to_search_result(self, doc: Dict[str, Any]):
        """转换MongoDB文档为SearchResult实体"""
        from src.core.domain.entities.search_result import SearchResult, ResultStatus

        # 处理UUID字段
        doc_id = doc.get("id")
        task_id = doc.get("task_id")

        # 处理datetime字段
        published_date = doc.get("published_date")
        if isinstance(published_date, str):
            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))

        # 处理status枚举
        status_value = doc.get("status", "pending")
        try:
            status = ResultStatus(status_value)
        except ValueError:
            status = ResultStatus.PENDING

        return SearchResult(
            id=UUID(doc_id) if isinstance(doc_id, str) else doc_id,
            task_id=UUID(task_id) if isinstance(task_id, str) else task_id,
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),
            published_date=published_date,
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            search_position=doc.get("search_position", 0),
            relevance_score=doc.get("relevance_score", 0.0),
            quality_score=doc.get("quality_score", 0.0),
            source=doc.get("source", ""),
            author=doc.get("author"),
            language=doc.get("language"),
            metadata=doc.get("metadata", {}),
            status=status,
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow())
        )

    def _doc_to_instant_search_result(self, doc: Dict[str, Any]):
        """转换MongoDB文档为InstantSearchResult实体"""
        from src.core.domain.entities.instant_search_result import InstantSearchResult, InstantSearchResultStatus

        # 处理datetime字段
        def parse_datetime(dt):
            if dt is None:
                return None
            if isinstance(dt, str):
                return datetime.fromisoformat(dt.replace('Z', '+00:00'))
            return dt

        # 处理status枚举
        status_value = doc.get("status", "pending")
        try:
            status = InstantSearchResultStatus(status_value)
        except ValueError:
            status = InstantSearchResultStatus.PENDING

        return InstantSearchResult(
            id=doc.get("id", ""),
            task_id=doc.get("task_id", ""),
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),
            published_date=parse_datetime(doc.get("published_date")),
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            content_hash=doc.get("content_hash", ""),
            url_normalized=doc.get("url_normalized", ""),
            relevance_score=doc.get("relevance_score", 0.0),
            quality_score=doc.get("quality_score", 0.0),
            source=doc.get("source", ""),
            author=doc.get("author"),
            language=doc.get("language"),
            metadata=doc.get("metadata", {}),
            first_found_at=parse_datetime(doc.get("first_found_at")),
            last_found_at=parse_datetime(doc.get("last_found_at")),
            found_count=doc.get("found_count", 1),
            unique_searches=doc.get("unique_searches", []),
            status=status,
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow())
        )


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据源存档历史数据迁移工具')
    parser.add_argument('--dry-run', action='store_true', help='干运行（不实际存档）')
    parser.add_argument('--limit', type=int, help='限制处理的数据源数量')
    parser.add_argument('--archived-by', default='migration_script', help='存档操作者标识')

    args = parser.parse_args()

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import settings
    except ImportError as e:
        print_error(f"导入失败: {e}")
        print_warning("请确保已安装所需依赖: pip install motor pymongo")
        return False

    print_header("数据源存档历史数据迁移工具")

    if args.dry_run:
        print_warning("这是干运行模式，不会实际写入数据")

    print_info(f"存档操作者: {args.archived_by}")

    # 连接数据库
    try:
        print_info("连接MongoDB数据库...")
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
            serverSelectionTimeoutMS=5000
        )
        await asyncio.wait_for(client.admin.command('ping'), timeout=5.0)
        db = client[settings.MONGODB_DB_NAME]
        print_success(f"数据库连接成功: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        print_error(f"数据库连接失败: {e}")
        return False

    # 创建迁移器
    migrator = ArchiveDataMigrator(db, archived_by=args.archived_by)

    try:
        # 执行迁移
        await migrator.migrate(limit=args.limit, dry_run=args.dry_run)

        # 判断迁移结果
        if migrator.stats['errors'] == 0:
            print_header("迁移完成")
            print_success("所有数据源存档成功！")
            return True
        else:
            print_header("迁移完成（有错误）")
            print_warning(f"迁移完成，但有 {migrator.stats['errors']} 个错误")
            print_info("请检查上方的错误详情")
            return False

    except Exception as e:
        print_error(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
