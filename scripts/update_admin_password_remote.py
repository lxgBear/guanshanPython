"""
更新远程 MongoDB admin 用户密码脚本

直接连接远程 MongoDB 更新密码

Usage:
    python scripts/update_admin_password_remote.py
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext


async def update_admin_password():
    """更新 admin 用户密码"""

    # 密码处理器
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

    # 新密码
    new_password = "Aa23456."
    password_hash = pwd_context.hash(new_password)

    # 远程 MongoDB 连接配置
    # 通过 VPN 连接到远程服务器 192.168.0.3:47017
    mongo_url = "mongodb://admin:jC5xXnjzbEepwChs@192.168.0.3:47017/?authSource=admin"
    db_name = "guanshan"

    print("=" * 50)
    print("更新远程 MongoDB admin 用户密码")
    print("=" * 50)
    print(f"连接: 192.168.0.3:47017")
    print(f"数据库: {db_name}")

    try:
        # 连接 MongoDB
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        collection = db["auth_users"]

        # 测试连接
        await client.admin.command('ping')
        print("✅ MongoDB 连接成功")

        # 查找 admin 用户
        admin_user = await collection.find_one({"username": "admin"})

        if not admin_user:
            print("❌ admin 用户不存在")
            return False

        print(f"找到 admin 用户: {admin_user.get('_id')}")

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

    except Exception as e:
        print(f"❌ 更新失败: {e}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(update_admin_password())
