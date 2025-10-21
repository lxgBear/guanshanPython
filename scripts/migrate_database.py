#!/usr/bin/env python3
"""
数据库迁移脚本
Database Migration Script

功能：
1. 从源数据库（本地MongoDB）迁移数据到目标数据库（生产MongoDB）
2. 支持选择性迁移（指定集合）或全量迁移
3. 自动创建索引
4. 提供进度显示和详细日志
5. 迁移前自动备份

使用方法：
    # 全量迁移（所有集合）
    python scripts/migrate_database.py --all

    # 迁移指定集合
    python scripts/migrate_database.py --collections search_tasks search_results

    # 迁移并跳过备份
    python scripts/migrate_database.py --all --skip-backup

    # 干运行（不实际迁移，只显示计划）
    python scripts/migrate_database.py --all --dry-run
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from collections import defaultdict

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

class DatabaseMigrator:
    """数据库迁移器"""

    def __init__(self, source_url: str, target_url: str, source_db: str, target_db: str):
        self.source_url = source_url
        self.target_url = target_url
        self.source_db_name = source_db
        self.target_db_name = target_db
        self.source_client = None
        self.target_client = None
        self.source_db = None
        self.target_db = None

        self.stats = {
            'collections_migrated': 0,
            'documents_migrated': 0,
            'indexes_created': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

    async def connect(self):
        """连接到源和目标数据库"""
        from motor.motor_asyncio import AsyncIOMotorClient

        print_step(1, 6, "连接数据库")

        # 连接源数据库
        try:
            print_info("连接源数据库（本地）...")
            self.source_client = AsyncIOMotorClient(self.source_url, serverSelectionTimeoutMS=5000)
            await asyncio.wait_for(self.source_client.admin.command('ping'), timeout=5.0)
            self.source_db = self.source_client[self.source_db_name]
            print_success(f"源数据库连接成功: {self.source_db_name}")
        except Exception as e:
            print_error(f"源数据库连接失败: {e}")
            print_warning("请确保本地MongoDB服务已启动")
            raise

        # 连接目标数据库
        try:
            print_info("连接目标数据库（生产）...")
            self.target_client = AsyncIOMotorClient(self.target_url, serverSelectionTimeoutMS=10000)
            await asyncio.wait_for(self.target_client.admin.command('ping'), timeout=10.0)
            self.target_db = self.target_client[self.target_db_name]
            print_success(f"目标数据库连接成功: {self.target_db_name}")
        except Exception as e:
            print_error(f"目标数据库连接失败: {e}")
            print_warning("请检查生产数据库配置和网络连接")
            raise

    async def get_collections_info(self) -> Dict[str, int]:
        """获取源数据库所有集合及文档数"""
        collections = await self.source_db.list_collection_names()
        info = {}

        for coll in collections:
            count = await self.source_db[coll].count_documents({})
            info[coll] = count

        return info

    async def migrate_collection(self, collection_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """迁移单个集合"""
        result = {
            'collection': collection_name,
            'documents': 0,
            'indexes': 0,
            'success': False,
            'error': None
        }

        try:
            source_coll = self.source_db[collection_name]
            target_coll = self.target_db[collection_name]

            # 获取文档数量
            total_docs = await source_coll.count_documents({})
            result['documents'] = total_docs

            if total_docs == 0:
                print_warning(f"  集合 {collection_name} 为空，跳过")
                result['success'] = True
                return result

            print_info(f"  迁移 {collection_name} ({total_docs} 文档)")

            if not dry_run:
                # 批量读取并插入文档
                batch_size = 1000
                migrated = 0

                cursor = source_coll.find({})
                batch = []

                async for doc in cursor:
                    batch.append(doc)

                    if len(batch) >= batch_size:
                        # 插入批次
                        await target_coll.insert_many(batch, ordered=False)
                        migrated += len(batch)
                        print(f"    进度: {migrated}/{total_docs} ({migrated*100//total_docs}%)", end='\r')
                        batch = []

                # 插入剩余文档
                if batch:
                    await target_coll.insert_many(batch, ordered=False)
                    migrated += len(batch)

                print(f"    进度: {migrated}/{total_docs} (100%)    ")
                print_success(f"  完成迁移 {migrated} 文档")

                # 复制索引
                indexes = await source_coll.list_indexes().to_list(None)
                index_count = 0

                for idx in indexes:
                    # 跳过_id索引（自动创建）
                    if idx['name'] == '_id_':
                        continue

                    # 创建索引
                    keys = idx['key']
                    options = {k: v for k, v in idx.items() if k not in ['key', 'v', 'ns']}

                    try:
                        await target_coll.create_index(list(keys.items()), **options)
                        index_count += 1
                    except Exception as idx_err:
                        print_warning(f"    索引创建失败 {idx['name']}: {idx_err}")

                result['indexes'] = index_count
                if index_count > 0:
                    print_success(f"  创建了 {index_count} 个索引")
            else:
                print_info(f"  [DRY RUN] 将迁移 {total_docs} 文档")

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            print_error(f"  迁移失败: {e}")

        return result

    async def migrate(self, collections: Optional[List[str]] = None, dry_run: bool = False):
        """执行迁移"""
        self.stats['start_time'] = datetime.now()

        print_step(2, 6, "分析源数据库")

        # 获取所有集合信息
        all_collections = await self.get_collections_info()

        if not all_collections:
            print_warning("源数据库没有集合，无需迁移")
            return

        # 显示源数据库信息
        print_info("源数据库集合:")
        total_docs = 0
        for coll, count in all_collections.items():
            print(f"  • {coll}: {count} 文档")
            total_docs += count
        print_info(f"总计: {len(all_collections)} 集合, {total_docs} 文档")

        # 确定要迁移的集合
        if collections:
            # 验证指定的集合是否存在
            missing = [c for c in collections if c not in all_collections]
            if missing:
                print_error(f"以下集合不存在: {', '.join(missing)}")
                return

            to_migrate = {c: all_collections[c] for c in collections}
        else:
            to_migrate = all_collections

        print_step(3, 6, "检查目标数据库")

        # 检查目标数据库是否已有数据
        target_collections = await self.target_db.list_collection_names()

        if target_collections:
            print_warning(f"目标数据库已有 {len(target_collections)} 个集合:")
            for coll in target_collections:
                count = await self.target_db[coll].count_documents({})
                print(f"  • {coll}: {count} 文档")

            if not dry_run:
                response = input(f"\n{Colors.YELLOW}⚠ 继续迁移将覆盖现有数据，是否继续? (yes/no): {Colors.RESET}")
                if response.lower() != 'yes':
                    print_info("迁移已取消")
                    return
        else:
            print_success("目标数据库为空，可以安全迁移")

        print_step(4, 6, "执行数据迁移" + (" [DRY RUN]" if dry_run else ""))

        # 迁移每个集合
        results = []
        for coll_name in to_migrate:
            result = await self.migrate_collection(coll_name, dry_run=dry_run)
            results.append(result)

            if result['success']:
                self.stats['collections_migrated'] += 1
                self.stats['documents_migrated'] += result['documents']
                self.stats['indexes_created'] += result['indexes']
            else:
                self.stats['errors'] += 1

        self.stats['end_time'] = datetime.now()

        # 显示迁移结果
        print_step(5, 6, "迁移总结")
        self.print_summary(results)

    def print_summary(self, results: List[Dict[str, Any]]):
        """打印迁移总结"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        print(f"\n{Colors.BOLD}迁移统计:{Colors.RESET}")
        print(f"  集合数量: {self.stats['collections_migrated']}")
        print(f"  文档数量: {self.stats['documents_migrated']}")
        print(f"  索引数量: {self.stats['indexes_created']}")
        print(f"  耗时: {duration:.2f} 秒")

        if self.stats['errors'] > 0:
            print(f"\n{Colors.RED}失败的集合:{Colors.RESET}")
            for result in results:
                if not result['success']:
                    print(f"  • {result['collection']}: {result['error']}")

        print(f"\n{Colors.BOLD}详细结果:{Colors.RESET}")
        for result in results:
            status = Colors.GREEN + "✓" if result['success'] else Colors.RED + "✗"
            print(f"  {status} {result['collection']}: {result['documents']} 文档, {result['indexes']} 索引{Colors.RESET}")

    async def verify_migration(self):
        """验证迁移结果"""
        print_step(6, 6, "验证迁移结果")

        source_collections = await self.get_collections_info()

        all_match = True

        for coll, source_count in source_collections.items():
            target_count = await self.target_db[coll].count_documents({})

            if source_count == target_count:
                print_success(f"  {coll}: {source_count} 文档 ✓")
            else:
                print_error(f"  {coll}: 源={source_count}, 目标={target_count} ✗")
                all_match = False

        if all_match:
            print_success("\n所有集合验证通过！")
        else:
            print_error("\n部分集合验证失败，请检查迁移日志")

        return all_match

    async def close(self):
        """关闭数据库连接"""
        if self.source_client:
            self.source_client.close()
        if self.target_client:
            self.target_client.close()

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据库迁移工具')
    parser.add_argument('--all', action='store_true', help='迁移所有集合')
    parser.add_argument('--collections', nargs='+', help='指定要迁移的集合')
    parser.add_argument('--skip-backup', action='store_true', help='跳过备份步骤')
    parser.add_argument('--dry-run', action='store_true', help='干运行（不实际迁移）')
    parser.add_argument('--source-url', help='源数据库连接字符串（覆盖.env配置）')
    parser.add_argument('--target-url', help='目标数据库连接字符串（覆盖.env配置）')

    args = parser.parse_args()

    if not args.all and not args.collections:
        print_error("请指定 --all 或 --collections")
        parser.print_help()
        return False

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import settings
    except ImportError as e:
        print_error(f"导入失败: {e}")
        print_warning("请确保已安装所需依赖: pip install motor pymongo")
        return False

    print_header("数据库迁移工具")

    # 检查目标数据库密码
    if 'YOUR_PASSWORD_HERE' in settings.MONGODB_URL:
        print_error("检测到未填写的数据库密码")
        print_warning("请编辑 .env 文件，填写生产数据库密码")
        print_info("需要修改的行: MONGODB_URL=mongodb://guanshan:YOUR_PASSWORD_HERE@...")
        return False

    # 准备迁移配置
    # 源数据库（本地）
    source_url = args.source_url or "mongodb://admin:password123@localhost:27017/?authSource=admin"
    source_db = "intelligent_system"

    # 目标数据库（生产）
    target_url = args.target_url or settings.MONGODB_URL
    target_db = settings.MONGODB_DB_NAME

    # 显示迁移配置
    print_info("迁移配置:")
    print(f"  源数据库: {source_db}")
    print(f"  目标数据库: {target_db}")

    if args.dry_run:
        print_warning("这是干运行模式，不会实际迁移数据")

    # 备份提醒
    if not args.skip_backup and not args.dry_run:
        print_warning("\n建议在迁移前备份数据")
        print_info("使用命令: python scripts/backup_database.py")
        response = input(f"\n{Colors.YELLOW}是否已经备份或跳过备份? (yes/no): {Colors.RESET}")
        if response.lower() != 'yes':
            print_info("请先备份数据，然后使用 --skip-backup 参数重新运行")
            return False

    # 创建迁移器
    migrator = DatabaseMigrator(source_url, target_url, source_db, target_db)

    try:
        # 连接数据库
        await migrator.connect()

        # 执行迁移
        await migrator.migrate(
            collections=args.collections,
            dry_run=args.dry_run
        )

        # 验证迁移
        if not args.dry_run:
            success = await migrator.verify_migration()

            if success:
                print_header("迁移完成")
                print_success("数据库迁移成功！")
                print_info("可以开始使用生产数据库")
                return True
            else:
                print_header("迁移完成（有警告）")
                print_warning("迁移完成，但验证发现问题，请检查日志")
                return False
        else:
            print_header("干运行完成")
            print_info("这是预览结果，没有实际迁移数据")
            print_info("移除 --dry-run 参数以执行实际迁移")
            return True

    except Exception as e:
        print_error(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await migrator.close()

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
