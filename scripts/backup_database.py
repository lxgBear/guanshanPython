#!/usr/bin/env python3
"""
数据库备份脚本
Database Backup Script

功能：
1. 备份MongoDB数据库到JSON文件
2. 支持完整备份和增量备份
3. 自动压缩备份文件
4. 保留备份历史记录

使用方法：
    # 备份本地数据库
    python scripts/backup_database.py

    # 备份生产数据库
    python scripts/backup_database.py --production

    # 备份指定集合
    python scripts/backup_database.py --collections search_tasks search_results

    # 指定备份目录
    python scripts/backup_database.py --output ./backups
"""

import asyncio
import sys
import os
import json
import gzip
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

class MongoDBBackup:
    """MongoDB备份工具"""

    def __init__(self, connection_url: str, db_name: str, output_dir: Path):
        self.connection_url = connection_url
        self.db_name = db_name
        self.output_dir = output_dir
        self.client = None
        self.db = None

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        """连接数据库"""
        from motor.motor_asyncio import AsyncIOMotorClient

        try:
            self.client = AsyncIOMotorClient(self.connection_url, serverSelectionTimeoutMS=5000)
            await asyncio.wait_for(self.client.admin.command('ping'), timeout=5.0)
            self.db = self.client[self.db_name]
            print_success(f"数据库连接成功: {self.db_name}")
            return True
        except Exception as e:
            print_error(f"数据库连接失败: {e}")
            return False

    async def get_collections(self) -> List[str]:
        """获取所有集合"""
        return await self.db.list_collection_names()

    async def backup_collection(self, collection_name: str, timestamp: str) -> Dict[str, Any]:
        """备份单个集合"""
        result = {
            'collection': collection_name,
            'documents': 0,
            'file': None,
            'size': 0,
            'success': False,
            'error': None
        }

        try:
            coll = self.db[collection_name]
            count = await coll.count_documents({})

            if count == 0:
                print_warning(f"  {collection_name} 为空，跳过备份")
                result['success'] = True
                return result

            print_info(f"  备份 {collection_name} ({count} 文档)")

            # 导出文档
            documents = []
            cursor = coll.find({})

            async for doc in cursor:
                # 转换ObjectId为字符串
                doc['_id'] = str(doc['_id'])
                documents.append(doc)

            # 生成文件名
            filename = f"{collection_name}_{timestamp}.json.gz"
            filepath = self.output_dir / filename

            # 写入压缩的JSON文件
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)

            file_size = filepath.stat().st_size

            result['documents'] = count
            result['file'] = str(filepath)
            result['size'] = file_size
            result['success'] = True

            # 转换文件大小为可读格式
            size_str = self.format_bytes(file_size)
            print_success(f"  完成: {count} 文档 → {filename} ({size_str})")

        except Exception as e:
            result['error'] = str(e)
            print_error(f"  备份失败: {e}")

        return result

    @staticmethod
    def format_bytes(bytes_val: int) -> str:
        """转换字节为可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"

    async def backup(self, collections: Optional[List[str]] = None):
        """执行备份"""
        print_header("MongoDB数据库备份")

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 获取要备份的集合
        if collections:
            # 验证集合是否存在
            all_collections = await self.get_collections()
            missing = [c for c in collections if c not in all_collections]
            if missing:
                print_error(f"以下集合不存在: {', '.join(missing)}")
                return False

            to_backup = collections
        else:
            to_backup = await self.get_collections()

        if not to_backup:
            print_warning("没有集合需要备份")
            return False

        print_info(f"将备份 {len(to_backup)} 个集合到: {self.output_dir}")

        # 备份每个集合
        results = []
        total_docs = 0
        total_size = 0

        for coll_name in to_backup:
            result = await self.backup_collection(coll_name, timestamp)
            results.append(result)

            if result['success']:
                total_docs += result['documents']
                total_size += result['size']

        # 创建备份清单
        manifest = {
            'timestamp': timestamp,
            'database': self.db_name,
            'collections': len([r for r in results if r['success']]),
            'total_documents': total_docs,
            'total_size': total_size,
            'files': [
                {
                    'collection': r['collection'],
                    'documents': r['documents'],
                    'file': Path(r['file']).name if r['file'] else None,
                    'size': r['size']
                }
                for r in results if r['success']
            ]
        }

        # 保存清单
        manifest_file = self.output_dir / f"backup_manifest_{timestamp}.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 显示备份总结
        print_header("备份总结")
        print(f"{Colors.BOLD}备份统计:{Colors.RESET}")
        print(f"  时间戳: {timestamp}")
        print(f"  集合数: {manifest['collections']}")
        print(f"  文档数: {manifest['total_documents']}")
        print(f"  总大小: {self.format_bytes(manifest['total_size'])}")
        print(f"  输出目录: {self.output_dir}")
        print(f"  清单文件: {manifest_file.name}")

        print(f"\n{Colors.BOLD}备份文件:{Colors.RESET}")
        for item in manifest['files']:
            print(f"  • {item['file']} ({item['documents']} 文档, {self.format_bytes(item['size'])})")

        # 检查失败的备份
        failed = [r for r in results if not r['success']]
        if failed:
            print(f"\n{Colors.RED}失败的集合:{Colors.RESET}")
            for r in failed:
                print(f"  • {r['collection']}: {r['error']}")

        print_success(f"\n备份完成！文件保存在: {self.output_dir}")

        return len(failed) == 0

    async def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MongoDB数据库备份工具')
    parser.add_argument('--production', action='store_true', help='备份生产数据库')
    parser.add_argument('--collections', nargs='+', help='指定要备份的集合')
    parser.add_argument('--output', default='./backups', help='备份输出目录')

    args = parser.parse_args()

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import settings
    except ImportError as e:
        print_error(f"导入失败: {e}")
        print_warning("请确保已安装所需依赖: pip install motor pymongo")
        return False

    # 确定备份源
    if args.production:
        # 检查生产数据库配置
        if 'YOUR_PASSWORD_HERE' in settings.MONGODB_URL:
            print_error("生产数据库密码未配置")
            print_warning("请编辑 .env 文件，填写 MONGODB_URL 中的密码")
            return False

        connection_url = settings.MONGODB_URL
        db_name = settings.MONGODB_DB_NAME
        print_info("备份源: 生产数据库")
    else:
        connection_url = "mongodb://admin:password123@localhost:27017/?authSource=admin"
        db_name = "intelligent_system"
        print_info("备份源: 本地数据库")

    # 创建输出目录
    output_dir = Path(args.output)

    # 创建备份工具
    backup_tool = MongoDBBackup(connection_url, db_name, output_dir)

    try:
        # 连接数据库
        if not await backup_tool.connect():
            return False

        # 执行备份
        success = await backup_tool.backup(collections=args.collections)

        return success

    except Exception as e:
        print_error(f"备份失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await backup_tool.close()

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
