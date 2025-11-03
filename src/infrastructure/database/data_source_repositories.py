"""数据源仓储层

提供数据源的持久化操作，包括：
- 基础CRUD操作
- 状态过滤查询
- 游标分页支持
- MongoDB事务支持（用于状态同步）
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClientSession

from src.core.domain.entities.data_source import DataSource, RawDataReference
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataSourceRepository:
    """数据源仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.data_sources

    async def create(
        self,
        data_source: DataSource,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> DataSource:
        """创建数据源

        Args:
            data_source: 数据源实体
            session: MongoDB事务会话（可选）

        Returns:
            创建的数据源实体
        """
        doc = self._to_document(data_source)
        await self.collection.insert_one(doc, session=session)
        logger.info(f"✅ 创建数据源: {data_source.id} - {data_source.title}")
        return data_source

    async def find_by_id(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> Optional[DataSource]:
        """根据ID查询数据源

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            数据源实体，如果不存在则返回None
        """
        doc = await self.collection.find_one(
            {"id": data_source_id},
            session=session
        )
        return self._from_document(doc) if doc else None

    async def find_all(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[DataSource]:
        """查询所有数据源（支持过滤和分页）

        Args:
            created_by: 创建者过滤
            status: 状态过滤（draft或confirmed）
            source_type: 数据源类型过滤（scheduled, instant, mixed）
            start_date: 开始日期过滤（创建时间）
            end_date: 结束日期过滤（创建时间）
            primary_category: 第一级分类过滤
            secondary_category: 第二级分类过滤
            tertiary_category: 第三级分类过滤
            limit: 每页数量
            skip: 跳过数量

        Returns:
            数据源实体列表
        """
        query = {}

        if created_by:
            query["created_by"] = created_by

        if status:
            query["status"] = status

        if source_type:
            query["source_type"] = source_type

        # 时间范围过滤
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        # 分类过滤
        if primary_category:
            query["primary_category"] = primary_category

        if secondary_category:
            query["secondary_category"] = secondary_category

        if tertiary_category:
            query["tertiary_category"] = tertiary_category

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._from_document(doc) for doc in docs]

    async def count(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None
    ) -> int:
        """统计数据源数量

        Args:
            created_by: 创建者过滤
            status: 状态过滤
            source_type: 数据源类型过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            primary_category: 第一级分类过滤
            secondary_category: 第二级分类过滤
            tertiary_category: 第三级分类过滤

        Returns:
            数据源数量
        """
        query = {}

        if created_by:
            query["created_by"] = created_by

        if status:
            query["status"] = status

        if source_type:
            query["source_type"] = source_type

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        # 分类过滤
        if primary_category:
            query["primary_category"] = primary_category

        if secondary_category:
            query["secondary_category"] = secondary_category

        if tertiary_category:
            query["tertiary_category"] = tertiary_category

        return await self.collection.count_documents(query)

    async def update(
        self,
        data_source_id: str,
        update_data: Dict[str, Any],
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新数据源

        Args:
            data_source_id: 数据源ID
            update_data: 更新数据字典
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功
        """
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"id": data_source_id},
            {"$set": update_data},
            session=session
        )

        if result.modified_count > 0:
            logger.info(f"📝 更新数据源: {data_source_id}")

        return result.modified_count > 0

    async def delete(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """删除数据源

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            是否删除成功
        """
        result = await self.collection.delete_one(
            {"id": data_source_id},
            session=session
        )
        logger.info(f"🗑️  删除数据源: {data_source_id}")
        return result.deleted_count > 0

    async def add_raw_data_ref(
        self,
        data_source_id: str,
        raw_data_ref: RawDataReference,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """添加原始数据引用

        Args:
            data_source_id: 数据源ID
            raw_data_ref: 原始数据引用
            session: MongoDB事务会话（可选）

        Returns:
            是否添加成功
        """
        result = await self.collection.update_one(
            {"id": data_source_id},
            {
                "$push": {"raw_data_refs": raw_data_ref.to_dict()},
                "$set": {"updated_at": datetime.utcnow()}
            },
            session=session
        )
        return result.modified_count > 0

    async def remove_raw_data_ref(
        self,
        data_source_id: str,
        data_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """移除原始数据引用

        Args:
            data_source_id: 数据源ID
            data_id: 原始数据ID
            session: MongoDB事务会话（可选）

        Returns:
            是否移除成功
        """
        result = await self.collection.update_one(
            {"id": data_source_id},
            {
                "$pull": {"raw_data_refs": {"data_id": data_id}},
                "$set": {"updated_at": datetime.utcnow()}
            },
            session=session
        )
        return result.modified_count > 0

    async def update_statistics(
        self,
        data_source_id: str,
        total_count: int,
        scheduled_count: int,
        instant_count: int,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新统计信息

        Args:
            data_source_id: 数据源ID
            total_count: 总数
            scheduled_count: 定时任务数据数量
            instant_count: 即时搜索数据数量
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功
        """
        result = await self.collection.update_one(
            {"id": data_source_id},
            {
                "$set": {
                    "total_raw_data_count": total_count,
                    "scheduled_data_count": scheduled_count,
                    "instant_data_count": instant_count,
                    "updated_at": datetime.utcnow()
                }
            },
            session=session
        )
        return result.modified_count > 0

    async def find_by_raw_data_id(
        self,
        data_id: str,
        data_type: str
    ) -> List[DataSource]:
        """查找包含指定原始数据的所有数据源

        Args:
            data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）

        Returns:
            数据源实体列表
        """
        query = {
            "raw_data_refs": {
                "$elemMatch": {
                    "data_id": data_id,
                    "data_type": data_type
                }
            }
        }

        cursor = self.collection.find(query)
        docs = await cursor.to_list(length=None)
        return [self._from_document(doc) for doc in docs]

    # ==========================================
    # 文档转换方法
    # ==========================================

    def _to_document(self, data_source: DataSource) -> Dict[str, Any]:
        """实体转MongoDB文档

        Args:
            data_source: 数据源实体

        Returns:
            MongoDB文档字典
        """
        return {
            "id": data_source.id,
            "title": data_source.title,
            "description": data_source.description,
            "source_type": data_source.source_type.value,
            "status": data_source.status.value,
            "raw_data_refs": [ref.to_dict() for ref in data_source.raw_data_refs],
            "edited_content": data_source.edited_content,
            "content_version": data_source.content_version,
            "total_raw_data_count": data_source.total_raw_data_count,
            "scheduled_data_count": data_source.scheduled_data_count,
            "instant_data_count": data_source.instant_data_count,
            "created_by": data_source.created_by,
            "created_at": data_source.created_at,
            "confirmed_by": data_source.confirmed_by,
            "confirmed_at": data_source.confirmed_at,
            "updated_by": data_source.updated_by,
            "updated_at": data_source.updated_at,
            "tags": data_source.tags,
            "metadata": data_source.metadata,
            # 分类字段
            "primary_category": data_source.primary_category,
            "secondary_category": data_source.secondary_category,
            "tertiary_category": data_source.tertiary_category,
            "custom_tags": data_source.custom_tags
        }

    def _from_document(self, doc: Dict[str, Any]) -> DataSource:
        """MongoDB文档转实体

        Args:
            doc: MongoDB文档字典

        Returns:
            数据源实体
        """
        # 重构原始数据引用
        raw_data_refs = [
            RawDataReference(
                data_id=ref["data_id"],
                data_type=ref["data_type"],
                title=ref.get("title", ""),
                url=ref.get("url", ""),
                snippet=ref.get("snippet", ""),
                added_at=ref.get("added_at"),
                added_by=ref.get("added_by", "")
            )
            for ref in doc.get("raw_data_refs", [])
        ]

        from src.core.domain.entities.data_source import (
            DataSourceStatus,
            DataSourceType
        )

        return DataSource(
            id=doc["id"],
            title=doc.get("title", ""),
            description=doc.get("description", ""),
            source_type=DataSourceType(doc.get("source_type", "mixed")),
            status=DataSourceStatus(doc.get("status", "draft")),
            raw_data_refs=raw_data_refs,
            edited_content=doc.get("edited_content", ""),
            content_version=doc.get("content_version", 1),
            total_raw_data_count=doc.get("total_raw_data_count", 0),
            scheduled_data_count=doc.get("scheduled_data_count", 0),
            instant_data_count=doc.get("instant_data_count", 0),
            created_by=doc.get("created_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            confirmed_by=doc.get("confirmed_by"),
            confirmed_at=doc.get("confirmed_at"),
            updated_by=doc.get("updated_by", ""),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            tags=doc.get("tags", []),
            metadata=doc.get("metadata", {}),
            # 分类字段
            primary_category=doc.get("primary_category"),
            secondary_category=doc.get("secondary_category"),
            tertiary_category=doc.get("tertiary_category"),
            custom_tags=doc.get("custom_tags", [])
        )
