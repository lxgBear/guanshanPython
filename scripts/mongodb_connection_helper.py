#!/usr/bin/env python3
"""
MongoDB 连接辅助工具

用途:
1. 测试MongoDB连接
2. 查看数据库概况
3. 快速数据查询和分析
4. 数据导出

使用方法:
    python scripts/mongodb_connection_helper.py --help
"""

import argparse
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
except ImportError:
    print("❌ 错误: 未安装pymongo库")
    print("请运行: pip install pymongo")
    sys.exit(1)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ 警告: pandas未安装，部分功能不可用")
    print("建议运行: pip install pandas")


class MongoDBHelper:
    """MongoDB连接辅助类"""

    def __init__(self, connection_string: str):
        """
        初始化连接

        Args:
            connection_string: MongoDB连接字符串
        """
        self.connection_string = connection_string
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self) -> bool:
        """
        连接到MongoDB

        Returns:
            bool: 连接是否成功
        """
        try:
            print("🔄 正在连接MongoDB...")
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000
            )

            # 测试连接
            self.client.admin.command('ping')

            # 提取数据库名
            db_name = self._extract_db_name()
            self.db = self.client[db_name]

            print(f"✅ 连接成功! 数据库: {db_name}")
            return True

        except ServerSelectionTimeoutError:
            print("❌ 连接超时: 无法连接到MongoDB服务器")
            print("   请检查:")
            print("   1. 服务器IP地址和端口是否正确")
            print("   2. 防火墙是否开放端口")
            print("   3. 您的IP是否在白名单中")
            return False

        except OperationFailure as e:
            print(f"❌ 认证失败: {e}")
            print("   请检查:")
            print("   1. 用户名和密码是否正确")
            print("   2. 认证数据库是否正确 (authSource)")
            print("   3. 用户权限是否已配置")
            return False

        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

    def _extract_db_name(self) -> str:
        """从连接字符串中提取数据库名"""
        try:
            # mongodb://user:pass@host:port/dbname?params
            parts = self.connection_string.split('/')
            db_part = parts[3].split('?')[0]
            return db_part if db_part else 'intelligent_system'
        except:
            return 'intelligent_system'

    def show_overview(self) -> None:
        """显示数据库概况"""
        if not self.db:
            print("❌ 未连接到数据库")
            return

        print("\n" + "="*60)
        print("📊 数据库概况")
        print("="*60)

        try:
            collections = self.db.list_collection_names()
            print(f"\n总集合数: {len(collections)}\n")

            print(f"{'集合名称':<30} {'文档数量':>15} {'大小':>10}")
            print("-" * 60)

            total_docs = 0
            for collection_name in sorted(collections):
                try:
                    count = self.db[collection_name].count_documents({})
                    total_docs += count

                    # 获取集合统计信息
                    stats = self.db.command('collStats', collection_name)
                    size_kb = stats.get('size', 0) / 1024

                    size_str = f"{size_kb:.1f}KB" if size_kb < 1024 else f"{size_kb/1024:.1f}MB"

                    print(f"{collection_name:<30} {count:>15,} {size_str:>10}")

                except Exception as e:
                    print(f"{collection_name:<30} {'错误':>15} {str(e)[:10]:>10}")

            print("-" * 60)
            print(f"{'总计':<30} {total_docs:>15,}\n")

        except Exception as e:
            print(f"❌ 获取概况失败: {e}")

    def query_collection(self, collection_name: str, filter_dict: Dict = None,
                        limit: int = 10, fields: List[str] = None) -> None:
        """
        查询集合数据

        Args:
            collection_name: 集合名称
            filter_dict: 查询过滤条件
            limit: 返回文档数量限制
            fields: 需要返回的字段列表
        """
        if not self.db:
            print("❌ 未连接到数据库")
            return

        try:
            collection = self.db[collection_name]

            # 构建投影
            projection = None
            if fields:
                projection = {field: 1 for field in fields}

            # 查询
            filter_dict = filter_dict or {}
            cursor = collection.find(filter_dict, projection).limit(limit)

            results = list(cursor)

            print(f"\n🔍 查询结果 - {collection_name}")
            print(f"条件: {json.dumps(filter_dict, ensure_ascii=False)}")
            print(f"返回: {len(results)} 条记录\n")

            if not results:
                print("   (无数据)")
                return

            # 使用pandas显示（如果可用）
            if PANDAS_AVAILABLE:
                df = pd.DataFrame(results)
                print(df.to_string(max_rows=20, max_cols=10))
            else:
                # 简单打印
                for i, doc in enumerate(results[:10], 1):
                    print(f"\n--- 记录 {i} ---")
                    for key, value in doc.items():
                        if key != '_id':
                            print(f"{key}: {value}")

        except Exception as e:
            print(f"❌ 查询失败: {e}")

    def analyze_tasks(self, days: int = 7) -> None:
        """
        分析搜索任务统计

        Args:
            days: 分析最近N天的数据
        """
        if not self.db:
            print("❌ 未连接到数据库")
            return

        if not PANDAS_AVAILABLE:
            print("❌ 此功能需要pandas库，请运行: pip install pandas")
            return

        try:
            print(f"\n📈 搜索任务分析 (最近{days}天)")
            print("="*60)

            # 获取数据
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            tasks = list(self.db['search_tasks'].find(
                {'created_at': {'$gte': cutoff_date}},
                {'status': 1, 'created_at': 1, 'query': 1, 'target_website': 1}
            ))

            if not tasks:
                print("   (无数据)")
                return

            df = pd.DataFrame(tasks)

            # 1. 状态分布
            print("\n1️⃣ 任务状态分布:")
            status_counts = df['status'].value_counts()
            for status, count in status_counts.items():
                percentage = (count / len(df)) * 100
                print(f"   {status:<15} {count:>5} 条 ({percentage:.1f}%)")

            # 2. 每日趋势
            print("\n2️⃣ 每日创建数量:")
            df['date'] = pd.to_datetime(df['created_at']).dt.date
            daily_counts = df.groupby('date').size()
            for date, count in daily_counts.items():
                print(f"   {date}: {count} 条")

            # 3. 热门网站
            if 'target_website' in df.columns:
                print("\n3️⃣ 热门目标网站 (Top 10):")
                website_counts = df['target_website'].value_counts().head(10)
                for website, count in website_counts.items():
                    if pd.notna(website):
                        print(f"   {website:<40} {count:>3} 条")

            # 4. 总体统计
            print(f"\n📊 总计: {len(df)} 条任务")

        except KeyError:
            print("❌ 未找到 search_tasks 集合")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

    def export_collection(self, collection_name: str, output_file: str,
                         filter_dict: Dict = None, limit: int = None) -> None:
        """
        导出集合数据到CSV

        Args:
            collection_name: 集合名称
            output_file: 输出文件路径
            filter_dict: 查询过滤条件
            limit: 导出文档数量限制
        """
        if not self.db:
            print("❌ 未连接到数据库")
            return

        if not PANDAS_AVAILABLE:
            print("❌ 此功能需要pandas库，请运行: pip install pandas")
            return

        try:
            print(f"\n📦 导出数据: {collection_name}")

            collection = self.db[collection_name]
            filter_dict = filter_dict or {}

            cursor = collection.find(filter_dict)
            if limit:
                cursor = cursor.limit(limit)

            data = list(cursor)

            if not data:
                print("   (无数据可导出)")
                return

            df = pd.DataFrame(data)

            # 导出CSV
            df.to_csv(output_file, index=False, encoding='utf-8-sig')

            print(f"✅ 导出成功!")
            print(f"   文件: {output_file}")
            print(f"   记录数: {len(df)}")
            print(f"   列数: {len(df.columns)}")

        except Exception as e:
            print(f"❌ 导出失败: {e}")

    def test_permissions(self) -> None:
        """测试用户权限"""
        if not self.db:
            print("❌ 未连接到数据库")
            return

        print("\n🔐 权限测试")
        print("="*60)

        test_collection = 'permission_test_temp'

        # 测试读权限
        try:
            collections = self.db.list_collection_names()
            print("✅ 读权限: 正常")
        except Exception as e:
            print(f"❌ 读权限: 失败 - {e}")
            return

        # 测试写权限
        try:
            self.db[test_collection].insert_one({'test': 'data', 'timestamp': datetime.now()})
            print("✅ 写权限: 正常")

            # 清理测试数据
            self.db[test_collection].drop()
            print("✅ 删除权限: 正常")

        except OperationFailure as e:
            if 'not authorized' in str(e):
                print("⚠️ 写权限: 受限 (只读用户)")
                print("   当前用户只能查询数据，无法修改")
            else:
                print(f"❌ 写权限: 失败 - {e}")

    def close(self) -> None:
        """关闭连接"""
        if self.client:
            self.client.close()
            print("\n✅ 连接已关闭")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='MongoDB连接辅助工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 显示数据库概况
  python %(prog)s --connection "mongodb://user:pass@host:port/db?authSource=db" --overview

  # 查询search_tasks集合
  python %(prog)s --connection "..." --query search_tasks --limit 5

  # 分析最近7天的任务
  python %(prog)s --connection "..." --analyze --days 7

  # 导出数据到CSV
  python %(prog)s --connection "..." --export search_tasks --output tasks.csv

  # 测试权限
  python %(prog)s --connection "..." --test-permissions
        """
    )

    parser.add_argument(
        '--connection', '-c',
        required=True,
        help='MongoDB连接字符串'
    )

    parser.add_argument(
        '--overview', '-o',
        action='store_true',
        help='显示数据库概况'
    )

    parser.add_argument(
        '--query', '-q',
        metavar='COLLECTION',
        help='查询指定集合'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=10,
        help='查询结果数量限制 (默认: 10)'
    )

    parser.add_argument(
        '--fields', '-f',
        nargs='+',
        help='指定返回的字段'
    )

    parser.add_argument(
        '--analyze', '-a',
        action='store_true',
        help='分析搜索任务统计'
    )

    parser.add_argument(
        '--days', '-d',
        type=int,
        default=7,
        help='分析天数 (默认: 7)'
    )

    parser.add_argument(
        '--export', '-e',
        metavar='COLLECTION',
        help='导出集合到CSV'
    )

    parser.add_argument(
        '--output',
        metavar='FILE',
        help='导出文件路径'
    )

    parser.add_argument(
        '--test-permissions', '-t',
        action='store_true',
        help='测试用户权限'
    )

    args = parser.parse_args()

    # 创建辅助工具实例
    helper = MongoDBHelper(args.connection)

    # 连接数据库
    if not helper.connect():
        sys.exit(1)

    try:
        # 执行操作
        if args.overview:
            helper.show_overview()

        if args.query:
            helper.query_collection(
                args.query,
                limit=args.limit,
                fields=args.fields
            )

        if args.analyze:
            helper.analyze_tasks(days=args.days)

        if args.export:
            if not args.output:
                print("❌ 错误: 导出操作需要指定 --output 参数")
                sys.exit(1)
            helper.export_collection(
                args.export,
                args.output,
                limit=args.limit
            )

        if args.test_permissions:
            helper.test_permissions()

        # 如果没有指定任何操作，显示概况
        if not any([args.overview, args.query, args.analyze, args.export, args.test_permissions]):
            helper.show_overview()

    finally:
        helper.close()


if __name__ == '__main__':
    main()
