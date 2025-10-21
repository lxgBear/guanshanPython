#!/usr/bin/env python3
"""
生产数据库连接测试脚本
Production Database Connection Test Script

功能：
1. 测试MongoDB连接
2. 验证数据库权限
3. 检查集合列表
4. 测试基本CRUD操作
5. 显示数据库统计信息

使用方法：
    python scripts/test_production_database.py
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 颜色输出支持
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_success(text: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """打印警告信息"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    """打印信息"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

async def test_mongodb_connection():
    """测试MongoDB连接"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import settings

        print_header("生产数据库连接测试")

        # 显示连接信息（隐藏密码）
        connection_str = settings.MONGODB_URL
        # 隐藏密码显示
        if '@' in connection_str and '//' in connection_str:
            parts = connection_str.split('@')
            if len(parts) == 2:
                credentials_part = parts[0].split('//')[1]
                if ':' in credentials_part:
                    username = credentials_part.split(':')[0]
                    safe_connection = connection_str.replace(
                        credentials_part,
                        f"{username}:****"
                    )
                else:
                    safe_connection = connection_str
            else:
                safe_connection = connection_str
        else:
            safe_connection = connection_str

        print_info(f"连接字符串: {safe_connection}")
        print_info(f"数据库名称: {settings.MONGODB_DB_NAME}")
        print_info(f"连接池大小: {settings.MONGODB_MIN_POOL_SIZE}-{settings.MONGODB_MAX_POOL_SIZE}")

        # 1. 测试基本连接
        print("\n" + Colors.BOLD + "步骤 1/6: 测试基本连接" + Colors.RESET)
        try:
            client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=10000  # 10秒超时
            )

            # 测试连接
            await asyncio.wait_for(client.admin.command('ping'), timeout=10.0)
            print_success("MongoDB连接成功")

        except asyncio.TimeoutError:
            print_error("连接超时（10秒）")
            print_warning("可能原因：")
            print("  1. 服务器地址或端口错误")
            print("  2. 防火墙未开放端口 40717")
            print("  3. MongoDB服务未启动")
            print("  4. 网络连接问题")
            return False
        except Exception as e:
            print_error(f"连接失败: {e}")
            print_warning("请检查：")
            print("  1. .env文件中的MONGODB_URL是否正确")
            print("  2. 密码是否已填写（不能是YOUR_PASSWORD_HERE）")
            print("  3. 密码中的特殊字符是否已进行URL编码")
            return False

        # 2. 获取服务器信息
        print("\n" + Colors.BOLD + "步骤 2/6: 获取服务器信息" + Colors.RESET)
        try:
            server_info = await client.server_info()
            print_success(f"MongoDB版本: {server_info.get('version', 'unknown')}")
            print_info(f"服务器操作系统: {server_info.get('os', {}).get('name', 'unknown')}")
        except Exception as e:
            print_warning(f"无法获取服务器信息: {e}")

        # 3. 测试数据库访问
        print("\n" + Colors.BOLD + "步骤 3/6: 测试数据库访问权限" + Colors.RESET)
        try:
            db = client[settings.MONGODB_DB_NAME]

            # 列出所有集合
            collections = await db.list_collection_names()
            print_success(f"成功访问数据库: {settings.MONGODB_DB_NAME}")
            print_info(f"集合数量: {len(collections)}")

            if collections:
                print_info("现有集合:")
                for i, coll in enumerate(collections, 1):
                    # 获取每个集合的文档数
                    try:
                        count = await db[coll].count_documents({})
                        print(f"  {i}. {coll} ({count} 文档)")
                    except:
                        print(f"  {i}. {coll}")
            else:
                print_warning("数据库中没有集合（这是正常的，如果是新数据库）")

        except Exception as e:
            print_error(f"数据库访问失败: {e}")
            print_warning("可能原因：")
            print("  1. 用户权限不足")
            print("  2. 数据库名称错误")
            print("  3. authSource配置错误")
            return False

        # 4. 测试写入权限
        print("\n" + Colors.BOLD + "步骤 4/6: 测试写入权限" + Colors.RESET)
        test_collection = "connection_test"
        try:
            test_doc = {
                "test": "connection_test",
                "timestamp": datetime.utcnow(),
                "message": "This is a connection test document"
            }

            result = await db[test_collection].insert_one(test_doc)
            print_success(f"写入测试成功，文档ID: {result.inserted_id}")

        except Exception as e:
            print_error(f"写入测试失败: {e}")
            print_warning("用户可能没有写入权限")
            return False

        # 5. 测试读取权限
        print("\n" + Colors.BOLD + "步骤 5/6: 测试读取权限" + Colors.RESET)
        try:
            doc = await db[test_collection].find_one({"test": "connection_test"})
            if doc:
                print_success("读取测试成功")
                print_info(f"读取到的文档: {doc.get('message')}")
            else:
                print_warning("未找到测试文档")

        except Exception as e:
            print_error(f"读取测试失败: {e}")
            return False

        # 6. 清理测试数据
        print("\n" + Colors.BOLD + "步骤 6/6: 清理测试数据" + Colors.RESET)
        try:
            delete_result = await db[test_collection].delete_many({"test": "connection_test"})
            print_success(f"清理完成，删除了 {delete_result.deleted_count} 个测试文档")

            # 如果集合为空，删除集合
            count = await db[test_collection].count_documents({})
            if count == 0:
                await db[test_collection].drop()
                print_info("已删除空的测试集合")

        except Exception as e:
            print_warning(f"清理测试数据失败: {e}")

        # 7. 显示数据库统计信息
        print_header("数据库统计信息")
        try:
            stats = await db.command("dbStats")
            print(f"{Colors.BOLD}数据库:{Colors.RESET} {stats.get('db')}")
            print(f"{Colors.BOLD}集合数量:{Colors.RESET} {stats.get('collections')}")
            print(f"{Colors.BOLD}文档总数:{Colors.RESET} {stats.get('objects')}")

            # 转换字节为可读格式
            data_size = stats.get('dataSize', 0)
            storage_size = stats.get('storageSize', 0)

            def bytes_to_human(bytes_val):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.2f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.2f} TB"

            print(f"{Colors.BOLD}数据大小:{Colors.RESET} {bytes_to_human(data_size)}")
            print(f"{Colors.BOLD}存储大小:{Colors.RESET} {bytes_to_human(storage_size)}")
            print(f"{Colors.BOLD}索引数量:{Colors.RESET} {stats.get('indexes')}")

        except Exception as e:
            print_warning(f"无法获取统计信息: {e}")

        # 关闭连接
        client.close()

        print_header("测试完成")
        print_success("所有测试通过！生产数据库连接正常")
        print_info("可以开始使用应用程序")

        return True

    except ImportError as e:
        print_error(f"导入失败: {e}")
        print_warning("请确保已安装所需依赖:")
        print("  pip install motor pymongo python-dotenv pydantic-settings")
        return False
    except Exception as e:
        print_error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    # 检查.env文件是否存在
    env_file = project_root / ".env"
    if not env_file.exists():
        print_error(".env文件不存在")
        print_warning("请复制.env.production.example为.env并填写配置")
        return False

    # 检查是否填写了密码
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'YOUR_PASSWORD_HERE' in content:
            print_error("检测到未填写的密码占位符")
            print_warning("请编辑.env文件，将YOUR_PASSWORD_HERE替换为实际的MongoDB密码")
            print_info("文件位置: .env")
            print_info("需要修改的行: MONGODB_URL=mongodb://guanshan:YOUR_PASSWORD_HERE@...")
            return False

    # 运行测试
    success = await test_mongodb_connection()

    if not success:
        print_header("故障排查建议")
        print("\n1. 检查.env配置文件:")
        print("   - 确保MONGODB_URL已填写正确的密码")
        print("   - 密码中的特殊字符需要URL编码")
        print("   - 检查端口号是否正确（40717）")
        print("\n2. 检查网络连接:")
        print("   - 确保可以访问hancens.top")
        print("   - 检查防火墙是否开放40717端口")
        print("\n3. 检查MongoDB服务:")
        print("   - 确认MongoDB服务已启动")
        print("   - 检查用户名和密码是否正确")
        print("   - 验证authSource设置（应为guanshan）")
        print("\n4. 测试网络连接:")
        print("   ping hancens.top")
        print("   nc -zv hancens.top 40717")
        print("\n5. 查看详细错误日志:")
        print("   tail -f logs/app.log")

    return success

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
