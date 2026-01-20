"""
MongoDB 认证数据库初始化脚本

用于创建认证相关的集合索引和初始数据

Usage:
    python -m scripts.init_auth_mongodb
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.auth import PasswordHandler
from src.infrastructure.persistence.auth.mongodb import (
    MongoUserRepository,
    MongoRoleRepository,
    MongoPermissionRepository,
    create_auth_indexes,
    create_role_indexes,
)


async def init_permissions():
    """初始化权限数据"""
    permission_repo = MongoPermissionRepository()

    permissions_data = [
        # 用户管理
        ("user:create", "创建用户", "user", "允许创建新用户"),
        ("user:read", "查看用户", "user", "允许查看用户信息"),
        ("user:update", "更新用户", "user", "允许更新用户信息"),
        ("user:delete", "删除用户", "user", "允许删除用户"),
        ("user:list", "用户列表", "user", "允许查看用户列表"),

        # 角色管理
        ("role:create", "创建角色", "role", "允许创建新角色"),
        ("role:read", "查看角色", "role", "允许查看角色信息"),
        ("role:update", "更新角色", "role", "允许更新角色信息"),
        ("role:delete", "删除角色", "role", "允许删除角色"),
        ("role:assign", "分配角色", "role", "允许分配用户角色"),

        # 信息采集
        ("info:create", "采集信息", "info", "允许采集新信息"),
        ("info:read", "查看信息", "info", "允许查看信息"),
        ("info:update", "编辑信息", "info", "允许编辑信息"),
        ("info:delete", "删除信息", "info", "允许删除信息"),

        # 校审管理
        ("review:assign", "分配校审任务", "review", "允许分配校审任务"),
        ("review:execute", "执行校审", "review", "允许执行校审任务"),
        ("review:approve", "审批校审", "review", "允许审批校审结果"),
        ("review:read", "查看校审", "review", "允许查看校审信息"),

        # NL搜索
        ("search:basic", "基础搜索", "search", "允许使用基础搜索功能"),
        ("search:advanced", "高级搜索", "search", "允许使用高级搜索功能"),
        ("search:multilang", "多语言搜索", "search", "允许使用多语言搜索功能"),

        # 系统管理
        ("system:config", "系统配置", "system", "允许修改系统配置"),
        ("system:log", "系统日志", "system", "允许查看系统日志"),
        ("system:api", "API管理", "system", "允许管理API"),
    ]

    created_count = 0
    for code, name, module, description in permissions_data:
        # 检查是否已存在
        if await permission_repo.check_code_exists(code):
            print(f"⏭️  权限 {code} 已存在，跳过")
            continue

        await permission_repo.create(
            code=code,
            name=name,
            module=module,
            description=description
        )
        created_count += 1
        print(f"✅ 创建权限: {name} ({code})")

    print(f"📊 权限初始化完成: 新增 {created_count} 个")


async def init_roles():
    """初始化角色数据（包含权限映射）"""
    role_repo = MongoRoleRepository()

    # 角色与权限映射
    role_permissions = {
        "admin": [
            "user:create", "user:read", "user:update", "user:delete", "user:list",
            "role:create", "role:read", "role:update", "role:delete", "role:assign",
            "info:create", "info:read", "info:update", "info:delete",
            "review:assign", "review:execute", "review:approve", "review:read",
            "search:basic", "search:advanced", "search:multilang",
            "system:config", "system:log", "system:api",
        ],
        "chief_reviewer": [
            "user:create", "user:read", "user:update", "user:list", "role:assign",
            "info:create", "info:read", "info:update", "info:delete",
            "review:assign", "review:execute", "review:approve", "review:read",
            "search:basic", "search:advanced", "search:multilang",
            "system:log",
        ],
        "direction_reviewer": [
            "user:read", "user:list",
            "info:create", "info:read", "info:update", "info:delete",
            "review:assign", "review:execute", "review:approve", "review:read",
            "search:basic", "search:advanced", "search:multilang",
        ],
        "reviewer": [
            "info:create", "info:read", "info:update",
            "review:execute", "review:read",
            "search:basic", "search:advanced", "search:multilang",
        ],
        "collector": [
            "info:create", "info:read", "info:update",
            "search:basic", "search:advanced",
        ],
        "customer": [
            "search:basic",
        ],
    }

    roles_data = [
        ("admin", "系统管理员", 100, "系统最高权限，管理所有用户和配置", True),
        ("chief_reviewer", "总校审员", 80, "管理所有校审工作，分配任务", True),
        ("direction_reviewer", "方向校审员", 60, "负责特定方向的校审工作", True),
        ("reviewer", "校审员", 40, "执行具体校审任务", True),
        ("collector", "信息采集员", 30, "采集和录入信息", True),
        ("customer", "客户", 20, "查看和使用服务", True),
    ]

    created_count = 0
    for code, name, level, description, is_system in roles_data:
        # 检查是否已存在
        if await role_repo.check_code_exists(code):
            print(f"⏭️  角色 {code} 已存在，跳过")
            continue

        permissions = role_permissions.get(code, [])
        await role_repo.create(
            code=code,
            name=name,
            level=level,
            description=description,
            permissions=permissions,
            is_system=is_system
        )
        created_count += 1
        print(f"✅ 创建角色: {name} ({code}) - {len(permissions)} 个权限")

    print(f"📊 角色初始化完成: 新增 {created_count} 个")


async def init_admin_user():
    """初始化管理员用户"""
    user_repo = MongoUserRepository()
    password_handler = PasswordHandler()

    # 检查是否已存在
    existing = await user_repo.get_by_username("admin")
    if existing:
        print("⏭️  管理员用户已存在，跳过")
        return

    # 创建管理员用户
    password_hash = password_handler.hash_password("123456")

    await user_repo.create(
        username="admin",
        email="admin@system.com",
        password_hash=password_hash,
        display_name="系统管理员",
        roles=["admin"]  # 直接分配 admin 角色
    )

    print("✅ 管理员用户创建完成 (用户名: admin, 密码: 123456)")


async def main():
    """主函数"""
    print("=" * 50)
    print("MongoDB 认证数据库初始化")
    print("=" * 50)

    try:
        # 创建索引
        print("\n📁 创建集合索引...")
        await create_auth_indexes()
        await create_role_indexes()

        # 初始化权限
        print("\n🔐 初始化权限...")
        await init_permissions()

        # 初始化角色
        print("\n📋 初始化角色...")
        await init_roles()

        # 初始化管理员用户
        print("\n👤 初始化管理员...")
        await init_admin_user()

        print("\n" + "=" * 50)
        print("✅ MongoDB 认证数据库初始化完成!")
        print("=" * 50)
        print("\n默认管理员账户:")
        print("  用户名: admin")
        print("  密码: 123456")
        print("\n请登录后立即修改密码!")

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
