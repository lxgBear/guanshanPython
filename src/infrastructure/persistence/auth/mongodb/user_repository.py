"""
MongoDB 用户仓储实现

使用 MongoDB 替代 MariaDB 存储用户认证数据
"""

from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger
from src.infrastructure.id_generator import generate_string_id

logger = get_logger(__name__)


class MongoUserRepository:
    """MongoDB 用户仓储"""

    COLLECTION_NAME = "auth_users"
    LOGIN_HISTORY_COLLECTION = "auth_login_history"

    async def _get_collection(self):
        """获取用户集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def _get_login_history_collection(self):
        """获取登录历史集合"""
        db = await get_mongodb_database()
        return db[self.LOGIN_HISTORY_COLLECTION]

    async def create(
        self,
        username: str,
        email: Optional[str],
        password_hash: str,
        display_name: Optional[str] = None,
        phone: Optional[str] = None,
        department: Optional[str] = None,
        roles: List[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建用户"""
        collection = await self._get_collection()

        user_id = generate_string_id()
        now = datetime.utcnow()

        user_doc = {
            "_id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "display_name": display_name,
            "phone": phone,
            "department": department,
            "roles": roles or [],
            "is_active": True,
            "is_locked": False,
            "lock_reason": None,
            "last_login": None,
            "login_attempts": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by
        }

        await collection.insert_one(user_doc)
        logger.info(f"创建用户: {username} (ID: {user_id})")

        return user_doc

    async def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        collection = await self._get_collection()
        return await collection.find_one({"_id": user_id})

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        collection = await self._get_collection()
        return await collection.find_one({"username": username})

    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取用户"""
        collection = await self._get_collection()
        return await collection.find_one({"email": email})

    async def get_user_with_permissions(
        self,
        user_id: str
    ) -> Optional[Tuple[Dict[str, Any], List[str], List[str]]]:
        """
        获取用户及其角色和权限

        Returns:
            Tuple[Dict, List[str], List[str]]: (用户文档, 角色代码列表, 权限代码列表)
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None

        role_codes = user.get("roles", [])

        # 从角色集合获取权限
        db = await get_mongodb_database()
        roles_collection = db["auth_roles"]

        permission_codes = []
        if role_codes:
            cursor = roles_collection.find(
                {"code": {"$in": role_codes}, "is_active": True},
                {"permissions": 1}
            )
            async for role_doc in cursor:
                permission_codes.extend(role_doc.get("permissions", []))

        # 去重
        permission_codes = list(set(permission_codes))

        return user, role_codes, permission_codes

    async def list_users(
        self,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        role_code: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取用户列表

        Returns:
            Tuple[List[Dict], int]: (用户列表, 总数)
        """
        collection = await self._get_collection()

        # 构建查询条件
        query: Dict[str, Any] = {}

        if keyword:
            query["$or"] = [
                {"username": {"$regex": keyword, "$options": "i"}},
                {"display_name": {"$regex": keyword, "$options": "i"}},
                {"email": {"$regex": keyword, "$options": "i"}}
            ]

        if is_active is not None:
            query["is_active"] = is_active

        if role_code:
            query["roles"] = role_code

        # 计算总数
        total = await collection.count_documents(query)

        # 分页查询
        skip = (page - 1) * size
        cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(size)

        users = await cursor.to_list(length=size)

        return users, total

    async def update(self, user_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """更新用户"""
        collection = await self._get_collection()

        # 添加更新时间
        kwargs["updated_at"] = datetime.utcnow()

        # 移除 None 值
        update_data = {k: v for k, v in kwargs.items() if v is not None}

        if not update_data:
            return await self.get_by_id(user_id)

        result = await collection.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            return await self.get_by_id(user_id)
        return None

    async def delete(self, user_id: str) -> bool:
        """删除用户"""
        collection = await self._get_collection()
        result = await collection.delete_one({"_id": user_id})
        return result.deleted_count > 0

    async def lock_user(self, user_id: str, reason: str) -> Optional[Dict[str, Any]]:
        """锁定用户"""
        return await self.update(user_id, is_locked=True, lock_reason=reason)

    async def unlock_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """解锁用户"""
        return await self.update(user_id, is_locked=False, lock_reason=None, login_attempts=0)

    async def increment_login_attempts(self, user_id: str) -> int:
        """增加登录尝试次数"""
        collection = await self._get_collection()
        result = await collection.find_one_and_update(
            {"_id": user_id},
            {"$inc": {"login_attempts": 1}},
            return_document=True
        )
        return result.get("login_attempts", 0) if result else 0

    async def reset_login_attempts(self, user_id: str) -> None:
        """重置登录尝试次数"""
        await self.update(user_id, login_attempts=0)

    async def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        await self.update(user_id, last_login=datetime.utcnow())

    async def assign_roles(
        self,
        user_id: str,
        role_codes: List[str],
        assigned_by: Optional[str] = None
    ) -> None:
        """分配角色给用户"""
        collection = await self._get_collection()
        await collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "roles": role_codes,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"用户 {user_id} 角色更新为: {role_codes}")

    async def add_role(
        self,
        user_id: str,
        role_code: str,
        assigned_by: Optional[str] = None
    ) -> bool:
        """给用户添加一个角色"""
        collection = await self._get_collection()
        result = await collection.update_one(
            {"_id": user_id, "roles": {"$ne": role_code}},
            {
                "$addToSet": {"roles": role_code},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    async def remove_role(self, user_id: str, role_code: str) -> bool:
        """移除用户的一个角色"""
        collection = await self._get_collection()
        result = await collection.update_one(
            {"_id": user_id},
            {
                "$pull": {"roles": role_code},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    async def get_user_roles(self, user_id: str) -> List[str]:
        """获取用户的所有角色代码"""
        user = await self.get_by_id(user_id)
        return user.get("roles", []) if user else []

    async def check_username_exists(self, username: str, exclude_id: Optional[str] = None) -> bool:
        """检查用户名是否存在"""
        collection = await self._get_collection()
        query: Dict[str, Any] = {"username": username}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}
        count = await collection.count_documents(query)
        return count > 0

    async def check_email_exists(self, email: str, exclude_id: Optional[str] = None) -> bool:
        """检查邮箱是否存在"""
        collection = await self._get_collection()
        query: Dict[str, Any] = {"email": email}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}
        count = await collection.count_documents(query)
        return count > 0

    async def record_login_history(
        self,
        user_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        status: str,
        fail_reason: Optional[str] = None
    ) -> None:
        """记录登录历史"""
        collection = await self._get_login_history_collection()

        history_id = generate_string_id()
        history_doc = {
            "_id": history_id,
            "user_id": user_id,
            "login_time": datetime.utcnow(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": status,
            "fail_reason": fail_reason
        }

        await collection.insert_one(history_doc)

    async def get_login_history(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户登录历史"""
        collection = await self._get_login_history_collection()
        cursor = collection.find(
            {"user_id": user_id}
        ).sort("login_time", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def list_users_by_permission(
        self,
        permission_code: str,
        keyword: Optional[str] = None,
        exclude_user_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取拥有指定权限的用户列表

        v2.8.0: 用于获取可选审核员列表

        通过角色关联查找拥有指定权限的用户
        """
        db = await get_mongodb_database()
        users_collection = await self._get_collection()
        roles_collection = db["auth_roles"]

        # 1. 先找出拥有该权限的角色
        roles_with_permission = await roles_collection.find(
            {"permissions": permission_code, "is_active": True},
            {"code": 1}
        ).to_list(length=100)

        role_codes = [r["code"] for r in roles_with_permission]

        if not role_codes:
            return [], 0

        # 2. 查找拥有这些角色的用户
        query: Dict[str, Any] = {
            "roles": {"$in": role_codes},
            "is_active": True,
            "is_locked": {"$ne": True}
        }

        # 排除指定用户
        if exclude_user_id:
            query["_id"] = {"$ne": exclude_user_id}

        # 关键词搜索
        if keyword:
            query["$or"] = [
                {"username": {"$regex": keyword, "$options": "i"}},
                {"display_name": {"$regex": keyword, "$options": "i"}},
                {"department": {"$regex": keyword, "$options": "i"}}
            ]

        # 获取总数
        total = await users_collection.count_documents(query)

        # 查询用户列表（不分页，通常审核员数量不会太多）
        cursor = users_collection.find(query).sort("username", 1)
        users = await cursor.to_list(length=200)  # 最多返回200个

        return users, total


async def create_auth_indexes():
    """创建认证相关索引"""
    db = await get_mongodb_database()

    # 用户集合索引
    users = db[MongoUserRepository.COLLECTION_NAME]
    await users.create_index("username", unique=True, name="idx_username")
    await users.create_index("email", unique=True, sparse=True, name="idx_email")
    await users.create_index("roles", name="idx_roles")
    await users.create_index("is_active", name="idx_is_active")
    await users.create_index("created_at", name="idx_created_at")

    # 登录历史索引
    login_history = db[MongoUserRepository.LOGIN_HISTORY_COLLECTION]
    await login_history.create_index("user_id", name="idx_user_id")
    await login_history.create_index("login_time", name="idx_login_time")
    await login_history.create_index(
        [("user_id", 1), ("login_time", -1)],
        name="idx_user_login_time"
    )

    logger.info("✅ 认证用户索引创建完成")
