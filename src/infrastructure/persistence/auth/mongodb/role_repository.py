"""
MongoDB 角色和权限仓储实现

使用 MongoDB 替代 MariaDB 存储角色和权限数据
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger
from src.infrastructure.id_generator import generate_string_id

logger = get_logger(__name__)


class MongoRoleRepository:
    """MongoDB 角色仓储"""

    COLLECTION_NAME = "auth_roles"

    async def _get_collection(self):
        """获取角色集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(
        self,
        code: str,
        name: str,
        level: int = 0,
        description: Optional[str] = None,
        parent_role_id: Optional[str] = None,
        permissions: List[str] = None,
        is_system: bool = False,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建角色"""
        collection = await self._get_collection()

        role_id = generate_string_id()
        now = datetime.utcnow()

        role_doc = {
            "_id": role_id,
            "code": code,
            "name": name,
            "level": level,
            "description": description,
            "parent_role_id": parent_role_id,
            "permissions": permissions or [],  # 权限代码列表
            "is_system": is_system,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by
        }

        await collection.insert_one(role_doc)
        logger.info(f"创建角色: {name} (Code: {code})")

        return role_doc

    async def get_by_id(self, role_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取角色"""
        collection = await self._get_collection()
        return await collection.find_one({"_id": role_id})

    async def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据代码获取角色"""
        collection = await self._get_collection()
        return await collection.find_one({"code": code})

    async def get_by_codes(self, codes: List[str]) -> List[Dict[str, Any]]:
        """根据代码列表获取角色"""
        collection = await self._get_collection()
        cursor = collection.find({"code": {"$in": codes}})
        return await cursor.to_list(length=len(codes))

    async def list_roles(
        self,
        is_active: Optional[bool] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """获取角色列表"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {}

        if is_active is not None:
            query["is_active"] = is_active

        if not include_system:
            query["is_system"] = False

        cursor = collection.find(query).sort("level", -1)
        return await cursor.to_list(length=100)

    async def update(
        self,
        role_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """更新角色"""
        collection = await self._get_collection()

        # 获取现有角色
        role = await self.get_by_id(role_id)
        if not role:
            return None

        # 系统角色不允许修改代码
        if role.get("is_system") and "code" in kwargs:
            del kwargs["code"]

        # 添加更新时间
        kwargs["updated_at"] = datetime.utcnow()

        # 移除 None 值
        update_data = {k: v for k, v in kwargs.items() if v is not None}

        if not update_data:
            return role

        result = await collection.update_one(
            {"_id": role_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            return await self.get_by_id(role_id)
        return role

    async def delete(self, role_id: str) -> bool:
        """删除角色（系统角色不可删除）"""
        collection = await self._get_collection()

        # 检查是否为系统角色
        role = await self.get_by_id(role_id)
        if not role or role.get("is_system"):
            return False

        result = await collection.delete_one({"_id": role_id})
        return result.deleted_count > 0

    async def assign_permissions(
        self,
        role_id: str,
        permission_codes: List[str],
        granted_by: Optional[str] = None
    ) -> bool:
        """分配权限给角色"""
        collection = await self._get_collection()

        result = await collection.update_one(
            {"_id": role_id},
            {
                "$set": {
                    "permissions": permission_codes,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"角色 {role_id} 权限更新: {permission_codes}")
            return True
        return False

    async def add_permission(
        self,
        role_id: str,
        permission_code: str
    ) -> bool:
        """添加单个权限"""
        collection = await self._get_collection()

        result = await collection.update_one(
            {"_id": role_id, "permissions": {"$ne": permission_code}},
            {
                "$addToSet": {"permissions": permission_code},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    async def remove_permission(
        self,
        role_id: str,
        permission_code: str
    ) -> bool:
        """移除单个权限"""
        collection = await self._get_collection()

        result = await collection.update_one(
            {"_id": role_id},
            {
                "$pull": {"permissions": permission_code},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0

    async def get_role_permissions(self, role_id: str) -> List[str]:
        """获取角色的所有权限代码"""
        role = await self.get_by_id(role_id)
        return role.get("permissions", []) if role else []

    async def check_code_exists(
        self,
        code: str,
        exclude_id: Optional[str] = None
    ) -> bool:
        """检查角色代码是否存在"""
        collection = await self._get_collection()
        query: Dict[str, Any] = {"code": code}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}
        count = await collection.count_documents(query)
        return count > 0


class MongoPermissionRepository:
    """MongoDB 权限仓储"""

    COLLECTION_NAME = "auth_permissions"

    async def _get_collection(self):
        """获取权限集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(
        self,
        code: str,
        name: str,
        module: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建权限"""
        collection = await self._get_collection()

        permission_id = generate_string_id()
        now = datetime.utcnow()

        permission_doc = {
            "_id": permission_id,
            "code": code,
            "name": name,
            "module": module,
            "description": description,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }

        await collection.insert_one(permission_doc)
        logger.info(f"创建权限: {name} (Code: {code})")

        return permission_doc

    async def get_by_id(self, permission_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取权限"""
        collection = await self._get_collection()
        return await collection.find_one({"_id": permission_id})

    async def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据代码获取权限"""
        collection = await self._get_collection()
        return await collection.find_one({"code": code})

    async def get_by_codes(self, codes: List[str]) -> List[Dict[str, Any]]:
        """根据代码列表获取权限"""
        collection = await self._get_collection()
        cursor = collection.find({"code": {"$in": codes}})
        return await cursor.to_list(length=len(codes))

    async def list_permissions(
        self,
        module: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        获取权限列表

        Returns:
            Tuple[List[Dict], List[str]]: (权限列表, 模块列表)
        """
        collection = await self._get_collection()

        query: Dict[str, Any] = {}

        if module:
            query["module"] = module

        if is_active is not None:
            query["is_active"] = is_active

        cursor = collection.find(query).sort([("module", 1), ("code", 1)])
        permissions = await cursor.to_list(length=500)

        # 获取所有不同的模块
        modules = await collection.distinct("module")
        modules.sort()

        return permissions, modules

    async def update(
        self,
        permission_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """更新权限"""
        collection = await self._get_collection()

        kwargs["updated_at"] = datetime.utcnow()
        update_data = {k: v for k, v in kwargs.items() if v is not None}

        if not update_data:
            return await self.get_by_id(permission_id)

        result = await collection.update_one(
            {"_id": permission_id},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            return await self.get_by_id(permission_id)
        return None

    async def check_code_exists(self, code: str) -> bool:
        """检查权限代码是否存在"""
        collection = await self._get_collection()
        count = await collection.count_documents({"code": code})
        return count > 0


async def create_role_indexes():
    """创建角色和权限相关索引"""
    db = await get_mongodb_database()

    # 角色集合索引
    roles = db[MongoRoleRepository.COLLECTION_NAME]
    await roles.create_index("code", unique=True, name="idx_role_code")
    await roles.create_index("is_active", name="idx_role_is_active")
    await roles.create_index("level", name="idx_role_level")
    await roles.create_index("is_system", name="idx_role_is_system")

    # 权限集合索引
    permissions = db[MongoPermissionRepository.COLLECTION_NAME]
    await permissions.create_index("code", unique=True, name="idx_permission_code")
    await permissions.create_index("module", name="idx_permission_module")
    await permissions.create_index("is_active", name="idx_permission_is_active")

    logger.info("✅ 角色和权限索引创建完成")
