#!/usr/bin/env python3
"""
用户档案 user_summary 字段回填/重新生成脚本
Backfill & Regenerate User Summary Script (v2.5.7)

功能：
1. 查找 user_archives 集合中缺少 user_summary 字段的记录 (默认模式)
2. 重新生成所有档案的 user_summary (--regenerate-all 模式)
3. 重新生成指定档案的 user_summary (--id 模式)
4. 使用与 create_archive 相同的逻辑生成 user_summary
5. 更新档案的 user_summary 字段
6. 支持干运行模式（预览不实际执行）

使用方法：
    # 回填缺失的 user_summary（默认模式）
    python scripts/backfill_user_summary.py

    # 重新生成所有档案的 user_summary
    python scripts/backfill_user_summary.py --regenerate-all

    # 重新生成指定档案的 user_summary
    python scripts/backfill_user_summary.py --id 69369627167397cbe79bd714

    # 干运行（不实际更新，只显示统计）
    python scripts/backfill_user_summary.py --dry-run

    # 限制处理数量（用于测试）
    python scripts/backfill_user_summary.py --regenerate-all --limit 3 --dry-run

    # 显示生成的 user_summary 内容
    python scripts/backfill_user_summary.py --dry-run --verbose
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

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
    print(f"{Colors.GREEN}  {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}  {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}  {text}{Colors.RESET}")


def print_info(text: str):
    print(f"{Colors.BLUE}  {text}{Colors.RESET}")


def print_step(step: int, total: int, text: str):
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}[{step}/{total}] {text}{Colors.RESET}")


def generate_user_summary(archive_name: str, items: List[Dict[str, Any]]) -> str:
    """生成档案的 user_summary 字段 (v2.5.8)

    使用与 MongoArchiveService._generate_user_summary 相同的逻辑

    Args:
        archive_name: 档案名称
        items: 档案条目列表

    Returns:
        str: 格式化的 Markdown 总结
    """
    lines = [f"# {archive_name}", ""]

    for idx, item in enumerate(items, start=1):
        snapshot = item.get("snapshot_data", {})

        # 获取标题：优先使用编辑版本，否则使用快照原始标题
        title = item.get("edited_title") or snapshot.get("original_title", "未知标题")

        # 获取URL：优先 original_url，回退到 url (v2.5.8 兼容不同数据源)
        url = snapshot.get("original_url") or snapshot.get("url")

        # 获取内容：优先使用编辑摘要，否则使用快照原始内容
        content = item.get("edited_summary") or snapshot.get("original_content", "")
        # 限制内容长度，避免过长
        if content and len(content) > 2000:
            content = content[:2000] + "..."

        # 构建条目
        lines.append(f"## {idx}. {title}")
        # 仅当URL存在时显示来源行
        if url:
            lines.append(f"来源: {url}")
        if content:
            lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


class UserSummaryBackfiller:
    """用户档案 user_summary 回填器"""

    def __init__(self, db):
        self.db = db
        self.collection = db.user_archives

        # 统计信息
        self.stats = {
            'total_archives': 0,
            'missing_summary': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

        self.error_log = []

    async def get_archives_missing_summary(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取缺少 user_summary 的档案"""
        print_info("查询缺少 user_summary 的档案...")

        # 查询 user_summary 为 null 或不存在的档案
        query = {
            "$or": [
                {"user_summary": None},
                {"user_summary": ""},
                {"user_summary": {"$exists": False}}
            ]
        }

        cursor = self.collection.find(query)

        if limit:
            cursor = cursor.limit(limit)

        archives = await cursor.to_list(length=None)

        print_success(f"找到 {len(archives)} 个缺少 user_summary 的档案")
        return archives

    async def get_all_archives(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有档案（用于重新生成）"""
        print_info("查询所有档案...")

        cursor = self.collection.find({})

        if limit:
            cursor = cursor.limit(limit)

        archives = await cursor.to_list(length=None)

        print_success(f"找到 {len(archives)} 个档案")
        return archives

    async def get_archive_by_id(self, archive_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取档案"""
        print_info(f"查询档案: {archive_id}...")

        try:
            from bson import ObjectId
            archive = await self.collection.find_one({"_id": ObjectId(archive_id)})

            if archive:
                print_success(f"找到档案: {archive.get('archive_name', '未命名')}")
                return archive
            else:
                print_error(f"档案不存在: {archive_id}")
                return None
        except Exception as e:
            print_error(f"查询失败: {e}")
            return None

    async def update_archive_summary(
        self,
        archive_id: str,
        user_summary: str,
        dry_run: bool = False
    ) -> bool:
        """更新档案的 user_summary"""
        try:
            if not dry_run:
                from bson import ObjectId
                result = await self.collection.update_one(
                    {"_id": ObjectId(archive_id)},
                    {
                        "$set": {
                            "user_summary": user_summary,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                return result.modified_count > 0
            return True
        except Exception as e:
            self.error_log.append({
                'archive_id': archive_id,
                'error': str(e)
            })
            self.stats['errors'] += 1
            return False

    async def process_archive(
        self,
        archive: Dict[str, Any],
        dry_run: bool = False,
        verbose: bool = False
    ) -> bool:
        """处理单个档案"""
        archive_id = str(archive.get("_id"))
        archive_name = archive.get("archive_name", "未命名档案")
        items = archive.get("items", [])

        print_info(f"处理档案: {archive_name[:40]}...")
        print_info(f"  ID: {archive_id}")
        print_info(f"  条目数: {len(items)}")

        if not items:
            print_warning(f"  跳过: 档案没有条目")
            self.stats['skipped'] += 1
            return True

        # 生成 user_summary
        try:
            user_summary = generate_user_summary(archive_name, items)
            summary_length = len(user_summary)
            print_info(f"  生成 user_summary: {summary_length} 字符")

            if verbose:
                # 显示预览（前500字符）
                preview = user_summary[:500] + "..." if len(user_summary) > 500 else user_summary
                print(f"\n{Colors.CYAN}--- 预览 ---{Colors.RESET}")
                print(preview)
                print(f"{Colors.CYAN}--- 结束 ---{Colors.RESET}\n")

            # 更新数据库
            if await self.update_archive_summary(archive_id, user_summary, dry_run):
                self.stats['updated'] += 1
                print_success(f"  {'[DRY RUN] 将' if dry_run else ''}更新成功")
                return True
            else:
                print_error(f"  更新失败")
                return False

        except Exception as e:
            print_error(f"  处理失败: {str(e)}")
            self.error_log.append({
                'archive_id': archive_id,
                'error': str(e)
            })
            self.stats['errors'] += 1
            return False

    async def backfill(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False,
        verbose: bool = False,
        regenerate_all: bool = False,
        archive_id: Optional[str] = None
    ):
        """执行回填/重新生成

        Args:
            limit: 限制处理数量
            dry_run: 干运行模式
            verbose: 显示详细信息
            regenerate_all: 重新生成所有档案
            archive_id: 指定档案ID
        """
        self.stats['start_time'] = datetime.now()

        # 确定运行模式
        if archive_id:
            mode = "单个档案"
        elif regenerate_all:
            mode = "重新生成所有"
        else:
            mode = "回填缺失"

        print_step(1, 4, f"分析现有数据 [{mode}]")

        # 获取统计信息
        self.stats['total_archives'] = await self.collection.count_documents({})

        missing_query = {
            "$or": [
                {"user_summary": None},
                {"user_summary": ""},
                {"user_summary": {"$exists": False}}
            ]
        }
        self.stats['missing_summary'] = await self.collection.count_documents(missing_query)

        print_info(f"总档案数量: {self.stats['total_archives']}")
        print_info(f"缺少 user_summary: {self.stats['missing_summary']}")

        if limit:
            print_warning(f"限制处理数量: {limit} 个档案")

        # 获取需要处理的档案
        print_step(2, 4, "获取待处理档案")

        if archive_id:
            # 单个档案模式
            archive = await self.get_archive_by_id(archive_id)
            archives = [archive] if archive else []
        elif regenerate_all:
            # 重新生成所有档案
            archives = await self.get_all_archives(limit=limit)
        else:
            # 默认：只处理缺失的档案
            archives = await self.get_archives_missing_summary(limit=limit)

        if not archives:
            print_warning("没有需要处理的档案")
            return

        # 处理每个档案
        action_name = "重新生成" if (regenerate_all or archive_id) else "回填"
        print_step(3, 4, f"执行{action_name}" + (" [DRY RUN]" if dry_run else ""))

        for idx, archive in enumerate(archives, 1):
            print(f"\n{Colors.BOLD}[{idx}/{len(archives)}]{Colors.RESET}")
            await self.process_archive(archive, dry_run=dry_run, verbose=verbose)

        self.stats['end_time'] = datetime.now()

        # 显示总结
        print_step(4, 4, f"{action_name}总结")
        self.print_summary(dry_run, action_name)

    def print_summary(self, dry_run: bool, action_name: str = "回填"):
        """打印回填/重新生成总结"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        print(f"\n{Colors.BOLD}{action_name}统计:{Colors.RESET}")
        print(f"  总档案数量: {self.stats['total_archives']}")
        print(f"  缺少 user_summary: {self.stats['missing_summary']}")
        print(f"  成功更新: {self.stats['updated']}")
        print(f"  跳过 (无条目): {self.stats['skipped']}")
        print(f"  错误数量: {self.stats['errors']}")
        print(f"  耗时: {duration:.2f} 秒")

        if dry_run:
            print_warning("\n这是干运行模式，没有实际写入数据库")

        if self.error_log:
            print(f"\n{Colors.RED}错误详情:{Colors.RESET}")
            for err in self.error_log[:10]:
                print(f"  * {err['archive_id']}: {err['error']}")
            if len(self.error_log) > 10:
                print(f"  ... 还有 {len(self.error_log) - 10} 个错误未显示")

        # 成功率统计
        total_processed = self.stats['updated'] + self.stats['skipped'] + self.stats['errors']
        if total_processed > 0:
            success_rate = (self.stats['updated'] / total_processed) * 100
            print(f"\n{Colors.BOLD}成功率: {success_rate:.2f}%{Colors.RESET}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='用户档案 user_summary 回填/重新生成工具 (v2.5.7)')
    parser.add_argument('--dry-run', action='store_true', help='干运行（不实际更新）')
    parser.add_argument('--limit', type=int, help='限制处理的档案数量')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示生成的 user_summary 预览')
    parser.add_argument('--regenerate-all', action='store_true', help='重新生成所有档案的 user_summary')
    parser.add_argument('--id', type=str, dest='archive_id', help='指定要重新生成的档案ID')

    args = parser.parse_args()

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import settings
    except ImportError as e:
        print_error(f"导入失败: {e}")
        print_warning("请确保已安装所需依赖: pip install motor pymongo")
        return False

    # 确定运行模式标题
    if args.archive_id:
        mode_title = f"单个档案重新生成 (ID: {args.archive_id})"
    elif args.regenerate_all:
        mode_title = "重新生成所有档案"
    else:
        mode_title = "回填缺失档案"

    print_header(f"用户档案 user_summary 工具 (v2.5.7)\n{mode_title}")

    if args.dry_run:
        print_warning("这是干运行模式，不会实际写入数据")

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

    # 创建回填器
    backfiller = UserSummaryBackfiller(db)

    # 确定操作名称
    action_name = "重新生成" if (args.regenerate_all or args.archive_id) else "回填"

    try:
        # 执行回填/重新生成
        await backfiller.backfill(
            limit=args.limit,
            dry_run=args.dry_run,
            verbose=args.verbose,
            regenerate_all=args.regenerate_all,
            archive_id=args.archive_id
        )

        # 判断结果
        if backfiller.stats['errors'] == 0:
            print_header(f"{action_name}完成")
            print_success(f"所有档案 user_summary {action_name}成功！")
            return True
        else:
            print_header(f"{action_name}完成（有错误）")
            print_warning(f"{action_name}完成，但有 {backfiller.stats['errors']} 个错误")
            print_info("请检查上方的错误详情")
            return False

    except Exception as e:
        print_error(f"{action_name}失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
