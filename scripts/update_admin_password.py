"""
更新 admin 用户密码脚本

Usage:
    python -m scripts.update_admin_password
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.auth import PasswordHandler


async def update_admin_password():
    """更新 admin 用户密码"""
    password_handler = PasswordHandler()

    # 新密码
    new_password = "Aa23456."

    # 生成密码哈希
    password_hash = password_handler.hash_password(new_password)

    # 获取数据库连接
    db = await get_mongodb_database()
    collection = db["auth_users"]

    # 查找 admin 用户
    admin_user = await collection.find_one({"username": "admin"})

    if not admin_user:
        print("❌ admin 用户不存在")
        return False

    # 更新密码
    result = await collection.update_one(
        {"username": "admin"},
        {"$set": {"password_hash": password_hash}}
    )

    if result.modified_count > 0:
        print("✅ admin 密码更新成功")
        print(f"   新密码: {new_password}")
        return True
    else:
        print("⚠️  密码未更新（可能已是相同密码）")
        return False


async def main():
    """主函数"""
    print("=" * 50)
    print("更新 admin 用户密码")
    print("=" * 50)

    try:
        await update_admin_password()
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
