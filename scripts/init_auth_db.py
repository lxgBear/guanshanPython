"""
认证数据库初始化脚本

用于创建认证相关的数据库表和初始数据

Usage:
    python -m scripts.init_auth_db
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.config import get_settings
from src.infrastructure.persistence.auth.models import Base
from src.infrastructure.auth import PasswordHandler


async def create_tables(engine):
    """创建数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")


async def init_roles(session: AsyncSession):
    """初始化角色数据"""
    roles_data = [
        ("admin", "系统管理员", 100, "系统最高权限，管理所有用户和配置", True),
        ("chief_reviewer", "总校审员", 80, "管理所有校审工作，分配任务", True),
        ("direction_reviewer", "方向校审员", 60, "负责特定方向的校审工作", True),
        ("reviewer", "校审员", 40, "执行具体校审任务", True),
        ("collector", "信息采集员", 30, "采集和录入信息", True),
        ("customer", "客户", 20, "查看和使用服务", True),
    ]

    for code, name, level, description, is_system in roles_data:
        # 检查是否已存在
        result = await session.execute(
            text("SELECT id FROM roles WHERE code = :code"),
            {"code": code}
        )
        if result.scalar():
            print(f"⏭️  角色 {code} 已存在，跳过")
            continue

        await session.execute(
            text("""
                INSERT INTO roles (code, name, level, description, is_system, is_active, created_at, updated_at)
                VALUES (:code, :name, :level, :description, :is_system, 1, NOW(), NOW())
            """),
            {
                "code": code,
                "name": name,
                "level": level,
                "description": description,
                "is_system": is_system
            }
        )
        print(f"✅ 创建角色: {name} ({code})")

    await session.commit()


async def init_permissions(session: AsyncSession):
    """初始化权限数据"""
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

    for code, name, module, description in permissions_data:
        # 检查是否已存在
        result = await session.execute(
            text("SELECT id FROM permissions WHERE code = :code"),
            {"code": code}
        )
        if result.scalar():
            print(f"⏭️  权限 {code} 已存在，跳过")
            continue

        await session.execute(
            text("""
                INSERT INTO permissions (code, name, module, description, is_active, created_at)
                VALUES (:code, :name, :module, :description, 1, NOW())
            """),
            {
                "code": code,
                "name": name,
                "module": module,
                "description": description
            }
        )
        print(f"✅ 创建权限: {name} ({code})")

    await session.commit()


async def init_role_permissions(session: AsyncSession):
    """初始化角色权限关联"""
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

    for role_code, permission_codes in role_permissions.items():
        # 获取角色ID
        result = await session.execute(
            text("SELECT id FROM roles WHERE code = :code"),
            {"code": role_code}
        )
        role_id = result.scalar()
        if not role_id:
            print(f"⚠️  角色 {role_code} 不存在")
            continue

        for perm_code in permission_codes:
            # 获取权限ID
            result = await session.execute(
                text("SELECT id FROM permissions WHERE code = :code"),
                {"code": perm_code}
            )
            perm_id = result.scalar()
            if not perm_id:
                print(f"⚠️  权限 {perm_code} 不存在")
                continue

            # 检查是否已存在
            result = await session.execute(
                text("""
                    SELECT id FROM role_permissions
                    WHERE role_id = :role_id AND permission_id = :perm_id
                """),
                {"role_id": role_id, "perm_id": perm_id}
            )
            if result.scalar():
                continue

            await session.execute(
                text("""
                    INSERT INTO role_permissions (role_id, permission_id, granted_at)
                    VALUES (:role_id, :perm_id, NOW())
                """),
                {"role_id": role_id, "perm_id": perm_id}
            )

        print(f"✅ 角色 {role_code} 权限配置完成")

    await session.commit()


async def init_admin_user(session: AsyncSession):
    """初始化管理员用户"""
    password_handler = PasswordHandler()

    # 检查是否已存在
    result = await session.execute(
        text("SELECT id FROM users WHERE username = 'admin'")
    )
    if result.scalar():
        print("⏭️  管理员用户已存在，跳过")
        return

    # 创建管理员用户
    password_hash = password_handler.hash_password("Admin@123")

    await session.execute(
        text("""
            INSERT INTO users (username, email, password_hash, display_name, is_active, created_at, updated_at)
            VALUES ('admin', 'admin@system.com', :password_hash, '系统管理员', 1, NOW(), NOW())
        """),
        {"password_hash": password_hash}
    )

    # 获取用户ID
    result = await session.execute(
        text("SELECT id FROM users WHERE username = 'admin'")
    )
    user_id = result.scalar()

    # 获取admin角色ID
    result = await session.execute(
        text("SELECT id FROM roles WHERE code = 'admin'")
    )
    role_id = result.scalar()

    # 分配角色
    if user_id and role_id:
        await session.execute(
            text("""
                INSERT INTO user_roles (user_id, role_id, assigned_at)
                VALUES (:user_id, :role_id, NOW())
            """),
            {"user_id": user_id, "role_id": role_id}
        )

    await session.commit()
    print("✅ 管理员用户创建完成 (用户名: admin, 密码: Admin@123)")


async def main():
    """主函数"""
    print("=" * 50)
    print("认证数据库初始化")
    print("=" * 50)

    settings = get_settings()

    # 创建数据库引擎
    engine = create_async_engine(
        settings.MARIADB_URL,
        echo=False
    )

    # 创建会话工厂
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    try:
        # 创建表
        await create_tables(engine)

        async with session_factory() as session:
            # 初始化角色
            print("\n📋 初始化角色...")
            await init_roles(session)

            # 初始化权限
            print("\n🔐 初始化权限...")
            await init_permissions(session)

            # 初始化角色权限关联
            print("\n🔗 配置角色权限...")
            await init_role_permissions(session)

            # 初始化管理员用户
            print("\n👤 初始化管理员...")
            await init_admin_user(session)

        print("\n" + "=" * 50)
        print("✅ 认证数据库初始化完成!")
        print("=" * 50)
        print("\n默认管理员账户:")
        print("  用户名: admin")
        print("  密码: Admin@123")
        print("\n请登录后立即修改密码!")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
