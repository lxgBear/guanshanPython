#!/usr/bin/env python3
"""
VPN数据库连接测试脚本

测试通过VPN连接到线上MongoDB数据库
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 颜色输出
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

def print_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def print_success(msg: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {msg}")

def print_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")

def print_header(msg: str):
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.CYAN}{msg:^60}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")


async def test_mongodb_connection(
    mongodb_url: str,
    timeout: int = 5
) -> tuple[bool, Optional[str]]:
    """
    测试MongoDB连接

    Args:
        mongodb_url: MongoDB连接字符串
        timeout: 连接超时时间（秒）

    Returns:
        (是否成功, 错误信息)
    """
    client = None
    try:
        print_info(f"正在连接MongoDB...")
        print_info(f"  URL: {mongodb_url.split('@')[1] if '@' in mongodb_url else mongodb_url}")
        print_info(f"  超时: {timeout}秒")

        # 创建客户端
        client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=timeout * 1000,
            connectTimeoutMS=timeout * 1000
        )

        # 尝试连接
        await client.admin.command('ping')

        print_success("MongoDB连接成功!")

        # 获取服务器信息
        server_info = await client.server_info()
        print_info("服务器信息:")
        print(f"  - MongoDB版本: {server_info.get('version', 'N/A')}")
        print(f"  - 服务器时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 列出数据库
        db_names = await client.list_database_names()
        print_info(f"可用数据库 ({len(db_names)}):")
        for db_name in db_names:
            print(f"  - {db_name}")

        return True, None

    except ServerSelectionTimeoutError as e:
        error_msg = f"连接超时: {str(e)}"
        print_error(error_msg)
        print_warning("可能原因:")
        print("  1. VPN未连接或路由配置错误")
        print("  2. 数据库服务器地址或端口错误")
        print("  3. 防火墙阻止连接")
        return False, error_msg

    except ConnectionFailure as e:
        error_msg = f"连接失败: {str(e)}"
        print_error(error_msg)
        print_warning("可能原因:")
        print("  1. 认证信息错误（用户名/密码）")
        print("  2. 数据库服务未启动")
        print("  3. 网络配置问题")
        return False, error_msg

    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print_error(error_msg)
        return False, error_msg

    finally:
        if client:
            client.close()


async def test_specific_database(
    mongodb_url: str,
    db_name: str = "intelligent_system"
) -> bool:
    """
    测试特定数据库的访问权限

    Args:
        mongodb_url: MongoDB连接字符串
        db_name: 数据库名称

    Returns:
        是否成功
    """
    client = None
    try:
        print_info(f"测试数据库访问权限: {db_name}")

        client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
        db = client[db_name]

        # 列出集合
        collections = await db.list_collection_names()
        print_success(f"可访问集合 ({len(collections)}):")
        for collection in collections[:10]:  # 只显示前10个
            print(f"  - {collection}")

        if len(collections) > 10:
            print(f"  ... 还有 {len(collections) - 10} 个集合")

        # 测试读取权限
        if collections:
            test_collection = collections[0]
            count = await db[test_collection].count_documents({})
            print_info(f"测试集合 '{test_collection}' 文档数: {count}")

        return True

    except Exception as e:
        print_error(f"数据库访问失败: {str(e)}")
        return False

    finally:
        if client:
            client.close()


async def check_vpn_connectivity():
    """检查VPN连接状态"""
    print_header("检查VPN连接状态")

    # 检查utun接口
    import subprocess
    try:
        result = subprocess.run(
            ['ifconfig'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if 'utun' in result.stdout:
            print_success("检测到VPN接口 (utun)")

            # 提取utun接口信息
            for line in result.stdout.split('\n'):
                if 'utun' in line or ('inet ' in line and 'utun' in result.stdout[max(0, result.stdout.find(line)-200):result.stdout.find(line)]):
                    print(f"  {line.strip()}")
        else:
            print_warning("未检测到VPN接口 (utun)")
            print_info("请确保VPN已连接:")
            print("  ./scripts/vpn_connect.sh connect")
            return False

    except Exception as e:
        print_error(f"检查VPN接口失败: {str(e)}")
        return False

    return True


async def main():
    """主函数"""
    print_header("VPN数据库连接测试")

    # 1. 检查VPN连接
    vpn_connected = await check_vpn_connectivity()
    if not vpn_connected:
        print_warning("\n建议:")
        print("  1. 先连接VPN: ./scripts/vpn_connect.sh connect")
        print("  2. 检查VPN状态: ./scripts/vpn_connect.sh status")
        print("  3. 再运行此测试脚本")
        return 1

    # 2. 测试本地数据库连接
    print_header("测试本地数据库连接")

    local_url = "mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin"
    success, error = await test_mongodb_connection(local_url, timeout=3)

    if success:
        print_success("✓ 本地数据库连接正常\n")
    else:
        print_warning("✗ 本地数据库连接失败")
        print_info("  这是正常的，如果只使用VPN连接线上数据库\n")

    # 3. 测试VPN线上数据库连接
    print_header("测试VPN线上数据库连接")

    # 从环境变量或配置文件读取
    vpn_db_urls = [
        # 选项1: app_user
        "mongodb://app_user:MyStrongPassword123!@hancens.top:27017/intelligent_system?authSource=intelligent_system",
        # 选项2: admin用户（如果需要）
        # "mongodb://admin:AdminPassword789!@hancens.top:27017/admin?authSource=admin",
    ]

    for idx, vpn_url in enumerate(vpn_db_urls, 1):
        print_info(f"\n尝试连接 #{idx}")
        success, error = await test_mongodb_connection(vpn_url, timeout=10)

        if success:
            print_success("✓ VPN数据库连接成功!\n")

            # 测试具体数据库
            await test_specific_database(vpn_url)

            print_header("连接测试完成")
            print_success("所有测试通过!")
            print_info("\n您现在可以:")
            print("  1. 更新 .env 文件的 MONGODB_URL")
            print("  2. 启动应用程序连接VPN数据库")
            print("  3. 使用 ./scripts/vpn_connect.sh disconnect 断开VPN")

            return 0
        else:
            print_warning(f"✗ 连接失败")

    # 所有尝试都失败
    print_header("连接测试失败")
    print_error("无法连接到VPN数据库")
    print_warning("\n故障排查步骤:")
    print("  1. 确认VPN已连接: ./scripts/vpn_connect.sh status")
    print("  2. 检查VPN路由: netstat -rn | grep utun")
    print("  3. 测试数据库端口: nc -zv hancens.top 27017")
    print("  4. 检查VPN日志: ./scripts/vpn_connect.sh log")
    print("  5. 确认数据库凭据正确")

    return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_warning("\n测试已取消")
        sys.exit(130)
    except Exception as e:
        print_error(f"程序错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
