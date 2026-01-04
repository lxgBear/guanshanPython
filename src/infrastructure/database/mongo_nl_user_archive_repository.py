"""
MongoDB 用户档案仓储层

提供档案的 CRUD 操作和查询功能（MongoDB 版本）。

设计说明:
- 使用 Motor 异步 MongoDB 驱动
- 集合名称: user_archives
- 文档结构: 扁平化设计，档案和条目在同一文档
- 支持原子操作和事务

v2.7.0: 新增审核流程支持
- 支持档案状态管理 (pending/approved/rejected)
- 支持审核历史记录
- 支持按状态筛选档案
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from src.core.domain.entities.nl_search import NLUserArchive, ArchiveStatus
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
        search_log_id: Optional[str] = None,
        search_task_id: Optional[str] = None,
        user_summary: Optional[str] = None
    ) -> Optional[str]:
        """创建档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            items: 档案条目列表
            description: 档案描述（可选）
            tags: 标签列表（可选）
            search_log_id: 关联的搜索记录ID（可选，来自自然语言搜索）
            search_task_id: 关联的定时任务ID（可选，来自定时搜索任务）v2.6.0新增
            user_summary: 用户内容总结（可选）v2.5.4新增 - 自动生成的条目汇总

        Returns:
            Optional[str]: 创建的档案ID（ObjectId字符串），失败时返回 None

        Example:
            >>> archive_id = await repo.create(
            ...     user_id=1001,
            ...     archive_name="AI技术突破",
            ...     items=[{"news_result_id": "...", ...}],
            ...     tags=["AI", "技术"],
            ...     search_task_id="248728141926559745",
            ...     user_summary="# AI技术突破\\n\\n## 1. GPT-5发布..."
            ... )
        """
        try:
            collection = await self._get_collection()

            now = datetime.utcnow()

            # 准备文档
            # v2.6.0: 新增 search_task_id 支持定时任务关联
            # v2.7.0: 新增审核流程字段
            document = {
                "user_id": user_id,
                "archive_name": archive_name,
                "description": description,
                "tags": tags or [],
                "search_log_id": search_log_id,
                "search_task_id": search_task_id,  # v2.6.0: 定时任务关联
                "items": items,  # 条目列表已包含所有字段
                "items_count": len(items),
                "user_summary": user_summary,  # v2.5.4: 自动生成的条目汇总
                # v2.7.0: 审核流程字段
                "status": ArchiveStatus.PENDING.value,  # 默认待审核状态
                "reviewer_id": None,
                "reviewer_name": None,
                "reviewed_at": None,
                "rejection_feedback": None,
                "submission_count": 1,
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
        user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        include_all_status: bool = False
    ) -> List[Dict[str, Any]]:
        """获取档案列表

        v2.7.0: 新增状态过滤支持

        Args:
            user_id: 用户ID（可选，不传则查询所有档案）
            limit: 返回数量限制
            offset: 分页偏移量
            status: 状态过滤（pending/approved/rejected），可选
            include_all_status: 是否包含所有状态（审核员权限）

        Returns:
            List[Dict]: 档案列表

        Example:
            >>> # 查询所有档案
            >>> archives = await repo.get_by_user(limit=10)
            >>> # 查询指定用户的档案
            >>> archives = await repo.get_by_user(user_id=1001, limit=10)
            >>> # 查询待审核的档案
            >>> archives = await repo.get_by_user(status="pending")
            >>> for archive in archives:
            ...     print(archive["archive_name"])
        """
        try:
            collection = await self._get_collection()

            # 构建查询条件
            query = {}
            if user_id is not None:
                query["user_id"] = user_id
            if status is not None:
                query["status"] = status
            elif not include_all_status:
                # 默认只返回已审核的档案（兼容旧版本行为）
                # 如果指定了 user_id，则返回该用户的所有状态档案
                if user_id is None:
                    query["status"] = ArchiveStatus.APPROVED.value

            cursor = collection.find(query).sort("created_at", -1).skip(offset).limit(limit)

            archives = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                # 确保旧数据有默认状态
                if "status" not in doc:
                    doc["status"] = ArchiveStatus.APPROVED.value
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
        tags: Optional[List[str]] = None,
        user_summary: Optional[str] = None,
        generated_report: Optional[str] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID
            archive_name: 新的档案名称（可选）
            description: 新的描述（可选）
            tags: 新的标签列表（可选）
            user_summary: 用户上传的内容总结（可选）v2.5.3新增
            generated_report: AI生成的摘要报告（可选）v2.5.9新增

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     archive_name="新档案名称",
            ...     description="新描述",
            ...     user_summary="用户自定义的内容总结...",
            ...     generated_report="AI生成的摘要报告..."
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

            # v2.5.3: 支持用户上传的内容总结
            if user_summary is not None:
                update_fields["user_summary"] = user_summary

            # v2.5.9: 支持AI生成的摘要报告
            if generated_report is not None:
                update_fields["generated_report"] = generated_report

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

            # v2.7.0: 新增状态索引
            await collection.create_index("status")

            logger.info("用户档案索引创建完成")

        except Exception as e:
            logger.error(f"创建索引失败: {e}")
            raise

    # ==================== v2.7.0: 审核流程方法 ====================

    async def update_status(
        self,
        archive_id: str,
        new_status: str,
        reviewer_id: Optional[int] = None,
        reviewer_name: Optional[str] = None,
        rejection_feedback: Optional[str] = None
    ) -> bool:
        """更新档案审核状态

        v2.7.0: 新增审核状态更新

        Args:
            archive_id: 档案ID
            new_status: 新状态（pending/approved/rejected）
            reviewer_id: 审核人ID（可选）
            reviewer_name: 审核人姓名（可选）
            rejection_feedback: 驳回原因（驳回时必填）

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update_status(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     new_status="approved",
            ...     reviewer_id=1001,
            ...     reviewer_name="审核员张三"
            ... )
        """
        try:
            collection = await self._get_collection()

            now = datetime.utcnow()

            update_fields = {
                "status": new_status,
                "updated_at": now
            }

            # 审核通过或驳回时设置审核信息
            if new_status in [ArchiveStatus.APPROVED.value, ArchiveStatus.REJECTED.value]:
                update_fields["reviewer_id"] = reviewer_id
                update_fields["reviewer_name"] = reviewer_name
                update_fields["reviewed_at"] = now

            # 驳回时设置驳回原因
            if new_status == ArchiveStatus.REJECTED.value:
                update_fields["rejection_feedback"] = rejection_feedback
            elif new_status == ArchiveStatus.APPROVED.value:
                # 审核通过时清除驳回原因
                update_fields["rejection_feedback"] = None

            result = await collection.update_one(
                {"_id": ObjectId(archive_id)},
                {"$set": update_fields}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"更新档案状态成功: ID={archive_id}, status={new_status}")
            return success

        except Exception as e:
            logger.error(f"更新档案状态失败: {e}")
            return False

    async def resubmit(
        self,
        archive_id: str
    ) -> bool:
        """重新提交被驳回的档案

        v2.7.0: 新增重新提交功能

        将已驳回的档案重新设为待审核状态，并增加提交次数。

        Args:
            archive_id: 档案ID

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.resubmit(archive_id="507f1f77bcf86cd799439011")
        """
        try:
            collection = await self._get_collection()

            now = datetime.utcnow()

            result = await collection.update_one(
                {
                    "_id": ObjectId(archive_id),
                    "status": ArchiveStatus.REJECTED.value  # 只能重新提交已驳回的
                },
                {
                    "$set": {
                        "status": ArchiveStatus.PENDING.value,
                        "reviewer_id": None,
                        "reviewer_name": None,
                        "reviewed_at": None,
                        # 保留 rejection_feedback 供参考
                        "updated_at": now
                    },
                    "$inc": {"submission_count": 1}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"重新提交档案成功: ID={archive_id}")
            return success

        except Exception as e:
            logger.error(f"重新提交档案失败: {e}")
            return False

    async def count_by_status(
        self,
        status: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> int:
        """统计指定状态的档案数量

        v2.7.0: 新增按状态统计

        Args:
            status: 状态（pending/approved/rejected），可选
            user_id: 用户ID（可选）

        Returns:
            int: 档案数量

        Example:
            >>> pending_count = await repo.count_by_status(status="pending")
            >>> user_pending = await repo.count_by_status(status="pending", user_id=1001)
        """
        try:
            collection = await self._get_collection()

            query = {}
            if status is not None:
                query["status"] = status
            if user_id is not None:
                query["user_id"] = user_id

            count = await collection.count_documents(query)
            return count

        except Exception as e:
            logger.error(f"统计档案数失败: {e}")
            raise
