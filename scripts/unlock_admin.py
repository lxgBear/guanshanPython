"""解锁被锁定的admin账户"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.auth.mongodb.user_repository import MongoUserRepository


async def unlock_admin():
    """解锁admin账户"""
    # 初始化数据库连接
    await get_mongodb_database()

    user_repo = MongoUserRepository()

    # 查找admin用户
    admin = await user_repo.get_by_username("admin")

    if not admin:
        print("❌ 未找到admin用户")
        return

    print(f"找到admin用户:")
    print(f"  - ID: {admin.get('_id')}")
    print(f"  - 用户名: {admin.get('username')}")
    print(f"  - 是否锁定: {admin.get('is_locked', False)}")
    print(f"  - 锁定原因: {admin.get('lock_reason', 'N/A')}")
    print(f"  - 登录失败次数: {admin.get('login_attempts', 0)}")

    if not admin.get('is_locked', False):
        print("\n✅ admin账户未被锁定，无需解锁")
        return

    # 解锁用户
    user_id = str(admin.get('_id'))
    result = await user_repo.unlock_user(user_id)

    if result:
        print("\n✅ admin账户解锁成功!")
        print(f"  - is_locked: False")
        print(f"  - login_attempts: 0")
    else:
        print("\n❌ 解锁失败")


if __name__ == "__main__":
    asyncio.run(unlock_admin())
