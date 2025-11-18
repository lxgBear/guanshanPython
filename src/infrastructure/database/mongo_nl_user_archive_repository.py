"""
MongoDB 用户档案仓储层

提供档案的 CRUD 操作和查询功能（MongoDB 版本）。

设计说明:
- 使用 Motor 异步 MongoDB 驱动
- 集合名称: user_archives
- 文档结构: 扁平化设计，档案和条目在同一文档
- 支持原子操作和事务
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from src.core.domain.entities.nl_search import NLUserArchive
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoNLUserArchiveRepository:
    """MongoDB 用户档案仓储

    提供档案数据的 CRUD 操作和查询功能。

    集合结构:
    {
        "_id": ObjectId,
        "user_id": int,
        "archive_name": str,
        "description": str,
        "tags": [str],
        "search_log_id": int,
        "items": [
            {
                "id": str (UUID),
                "news_result_id": str (ObjectId),
                "edited_title": str,
                "edited_summary": str,
                "user_notes": str,
                "user_rating": int,
                "snapshot_data": dict,
                "display_order": int,
                "created_at": datetime
            }
        ],
        "items_count": int,
        "created_at": datetime,
        "updated_at": datetime
    }

    Example:
        >>> repo = MongoNLUserArchiveRepository()
        >>> archive_id = await repo.create(
        ...     user_id=1001,
        ...     archive_name="AI技术突破汇总",
        ...     items=[...]
        ... )
    """

    def __init__(self):
        """初始化仓储"""
        self.db = None
        self.collection_name = "user_archives"

    async def _get_collection(self):
        """获取集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create(
        self,
        user_id: int,
        archive_name: str,
        items: List[Dict[str, Any]],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_log_id: Optional[int] = None
    ) -> Optional[str]:
        """创建档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            items: 档案条目列表
            description: 档案描述（可选）
            tags: 标签列表（可选）
            search_log_id: 关联的搜索记录ID（可选）

        Returns:
            Optional[str]: 创建的档案ID（ObjectId字符串），失败时返回 None

        Example:
            >>> archive_id = await repo.create(
            ...     user_id=1001,
            ...     archive_name="AI技术突破",
            ...     items=[{"news_result_id": "...", ...}],
            ...     tags=["AI", "技术"]
            ... )
        """
        try:
            collection = await self._get_collection()

            now = datetime.utcnow()

            # 准备文档
            document = {
                "user_id": user_id,
                "archive_name": archive_name,
                "description": description,
                "tags": tags or [],
                "search_log_id": search_log_id,
                "items": items,  # 条目列表已包含所有字段
                "items_count": len(items),
                "created_at": now,
                "updated_at": now
            }

            # 插入文档
            result = await collection.insert_one(document)
            archive_id = str(result.inserted_id)

            logger.info(f"创建用户档案成功: ID={archive_id}, user={user_id}, name='{archive_name}'")
            return archive_id

        except Exception as e:
            logger.error(f"创建用户档案失败: {e}")
            return None

    async def get_by_id(self, archive_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取档案

        Args:
            archive_id: 档案ID（ObjectId字符串）

        Returns:
            Optional[Dict]: 档案文档，不存在时返回 None

        Example:
            >>> archive = await repo.get_by_id("507f1f77bcf86cd799439011")
            >>> if archive:
            ...     print(archive["archive_name"])
        """
        try:
            collection = await self._get_collection()

            document = await collection.find_one({"_id": ObjectId(archive_id)})

            if document:
                # 转换 ObjectId 为字符串
                document["_id"] = str(document["_id"])
                return document

            return None

        except Exception as e:
            logger.error(f"查询档案失败: {e}")
            raise

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户的档案列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[Dict]: 档案列表

        Example:
            >>> archives = await repo.get_by_user(user_id=1001, limit=10)
            >>> for archive in archives:
            ...     print(archive["archive_name"])
        """
        try:
            collection = await self._get_collection()

            cursor = collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).skip(offset).limit(limit)

            archives = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                archives.append(doc)

            return archives

        except Exception as e:
            logger.error(f"查询用户档案列表失败: {e}")
            raise

    async def update(
        self,
        archive_id: str,
        archive_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID
            archive_name: 新的档案名称（可选）
            description: 新的描述（可选）
            tags: 新的标签列表（可选）

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     archive_name="新档案名称",
            ...     description="新描述"
            ... )
        """
        try:
            collection = await self._get_collection()

            # 构建更新字段
            update_fields = {"updated_at": datetime.utcnow()}

            if archive_name is not None:
                update_fields["archive_name"] = archive_name

            if description is not None:
                update_fields["description"] = description

            if tags is not None:
                update_fields["tags"] = tags

            if not update_fields:
                logger.warning("更新档案时未提供任何字段")
                return False

            # 执行更新
            result = await collection.update_one(
                {"_id": ObjectId(archive_id)},
                {"$set": update_fields}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"更新档案成功: ID={archive_id}")
            return success

        except Exception as e:
            logger.error(f"更新档案失败: {e}")
            return False

    async def delete(self, archive_id: str) -> bool:
        """删除档案

        Args:
            archive_id: 档案ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete(archive_id="507f1f77bcf86cd799439011")
        """
        try:
            collection = await self._get_collection()

            result = await collection.delete_one({"_id": ObjectId(archive_id)})

            success = result.deleted_count > 0
            if success:
                logger.info(f"删除档案成功: ID={archive_id}")
            return success

        except Exception as e:
            logger.error(f"删除档案失败: {e}")
            raise

    async def add_items(
        self,
        archive_id: str,
        items: List[Dict[str, Any]]
    ) -> bool:
        """向档案添加条目

        Args:
            archive_id: 档案ID
            items: 新增条目列表

        Returns:
            bool: 添加是否成功

        Example:
            >>> success = await repo.add_items(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     items=[{"news_result_id": "...", ...}]
            ... )
        """
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": ObjectId(archive_id)},
                {
                    "$push": {"items": {"$each": items}},
                    "$inc": {"items_count": len(items)},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"添加档案条目成功: archive={archive_id}, count={len(items)}")
            return success

        except Exception as e:
            logger.error(f"添加档案条目失败: {e}")
            return False

    async def remove_item(
        self,
        archive_id: str,
        item_id: str
    ) -> bool:
        """从档案移除条目

        Args:
            archive_id: 档案ID
            item_id: 条目ID

        Returns:
            bool: 移除是否成功

        Example:
            >>> success = await repo.remove_item(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     item_id="item-uuid-123"
            ... )
        """
        try:
            collection = await self._get_collection()

            result = await collection.update_one(
                {"_id": ObjectId(archive_id)},
                {
                    "$pull": {"items": {"id": item_id}},
                    "$inc": {"items_count": -1},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"移除档案条目成功: archive={archive_id}, item={item_id}")
            return success

        except Exception as e:
            logger.error(f"移除档案条目失败: {e}")
            return False

    async def count_by_user(self, user_id: int) -> int:
        """统计用户的档案总数

        Args:
            user_id: 用户ID

        Returns:
            int: 档案总数

        Example:
            >>> total = await repo.count_by_user(user_id=1001)
            >>> print(f"用户共有 {total} 个档案")
        """
        try:
            collection = await self._get_collection()

            count = await collection.count_documents({"user_id": user_id})
            return count

        except Exception as e:
            logger.error(f"统计用户档案数失败: {e}")
            raise

    async def create_indexes(self):
        """创建索引

        为常用查询字段创建索引以提升性能。

        Example:
            >>> await repo.create_indexes()
        """
        try:
            collection = await self._get_collection()

            # 用户ID索引（用于列表查询）
            await collection.create_index([("user_id", 1), ("created_at", -1)])

            # 搜索记录关联索引
            await collection.create_index("search_log_id")

            # 标签索引（用于按标签筛选）
            await collection.create_index("tags")

            logger.info("用户档案索引创建完成")

        except Exception as e:
            logger.error(f"创建索引失败: {e}")
            raise
