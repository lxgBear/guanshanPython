"""数据源存档数据仓储层

提供存档数据的持久化操作，包括：
- 创建存档记录（confirm时自动触发）
- 查询存档数据（分页支持）
- 统计存档数量
- 删除存档数据（级联删除）
- MongoDB事务支持
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClientSession

from src.core.domain.entities.archived_data import ArchivedData
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ArchivedDataRepository:
    """存档数据仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.data_source_archived_data

    async def create(
        self,
        archived_data: ArchivedData,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> ArchivedData:
        """创建存档记录

        通常在数据源confirm操作时，由Service层事务调用

        Args:
            archived_data: 存档数据实体
            session: MongoDB事务会话（必须提供以保证事务一致性）

        Returns:
            创建的存档数据实体
        """
        doc = self._to_document(archived_data)
        await self.collection.insert_one(doc, session=session)
        logger.info(f"✅ 创建存档记录: {archived_data.id} (数据源: {archived_data.data_source_id}, 类型: {archived_data.data_type})")
        return archived_data

    async def find_by_data_source(
        self,
        data_source_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[ArchivedData]:
        """按数据源查询存档数据（分页）

        Args:
            data_source_id: 数据源ID
            limit: 每页数量
            skip: 跳过数量

        Returns:
            存档数据实体列表
        """
        cursor = self.collection.find(
            {"data_source_id": data_source_id}
        ).sort("created_at", -1).skip(skip).limit(limit)

        docs = await cursor.to_list(length=limit)
        return [self._from_document(doc) for doc in docs]

    async def count_by_data_source(
        self,
        data_source_id: str
    ) -> int:
        """统计数据源的存档数量

        Args:
            data_source_id: 数据源ID

        Returns:
            存档记录数量
        """
        return await self.collection.count_documents(
            {"data_source_id": data_source_id}
        )

    async def find_by_id(
        self,
        archived_data_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> Optional[ArchivedData]:
        """根据ID查询存档数据

        Args:
            archived_data_id: 存档数据ID
            session: MongoDB事务会话（可选）

        Returns:
            存档数据实体，如果不存在则返回None
        """
        doc = await self.collection.find_one(
            {"id": archived_data_id},
            session=session
        )
        return self._from_document(doc) if doc else None

    async def find_by_original_data_id(
        self,
        original_data_id: str,
        data_type: str
    ) -> Optional[ArchivedData]:
        """根据原始数据ID查询存档（防重复存档）

        Args:
            original_data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）

        Returns:
            存档数据实体，如果不存在则返回None
        """
        doc = await self.collection.find_one({
            "original_data_id": original_data_id,
            "data_type": data_type
        })
        return self._from_document(doc) if doc else None

    async def delete_by_data_source(
        self,
        data_source_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> int:
        """删除数据源的所有存档记录（级联删除）

        通常在删除数据源时由Service层事务调用

        Args:
            data_source_id: 数据源ID
            session: MongoDB事务会话（可选）

        Returns:
            删除的记录数量
        """
        result = await self.collection.delete_many(
            {"data_source_id": data_source_id},
            session=session
        )
        deleted_count = result.deleted_count
        logger.info(f"🗑️  删除数据源存档: {data_source_id}，共{deleted_count}条记录")
        return deleted_count

    async def get_statistics(
        self,
        data_source_id: str
    ) -> Dict[str, Any]:
        """获取数据源存档统计信息

        Args:
            data_source_id: 数据源ID

        Returns:
            统计信息字典
        """
        pipeline = [
            {"$match": {"data_source_id": data_source_id}},
            {
                "$group": {
                    "_id": "$data_type",
                    "count": {"$sum": 1},
                    "total_content_size": {"$sum": {"$strLenCP": "$content"}}
                }
            }
        ]

        results = await self.collection.aggregate(pipeline).to_list(length=None)

        stats = {
            "data_source_id": data_source_id,
            "total_count": 0,
            "scheduled_count": 0,
            "instant_count": 0,
            "total_content_size": 0,
            "by_type": {}
        }

        for result in results:
            data_type = result["_id"]
            count = result["count"]
            content_size = result["total_content_size"]

            stats["total_count"] += count
            stats["total_content_size"] += content_size
            stats["by_type"][data_type] = {
                "count": count,
                "content_size": content_size
            }

            if data_type == "scheduled":
                stats["scheduled_count"] = count
            elif data_type == "instant":
                stats["instant_count"] = count

        return stats

    async def find_with_pagination(
        self,
        data_source_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ArchivedData], int]:
        """分页查询存档数据（含总数）

        Args:
            data_source_id: 数据源ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            (存档数据列表, 总记录数) 元组
        """
        skip = (page - 1) * page_size

        # 并行执行查询和计数
        cursor = self.collection.find(
            {"data_source_id": data_source_id}
        ).sort("created_at", -1).skip(skip).limit(page_size)

        docs, total = await asyncio.gather(
            cursor.to_list(length=page_size),
            self.count_by_data_source(data_source_id)
        )

        archived_list = [self._from_document(doc) for doc in docs]
        return archived_list, total

    # ==========================================
    # 文档转换方法
    # ==========================================

    def _to_document(self, archived_data: ArchivedData) -> Dict[str, Any]:
        """实体转MongoDB文档

        Args:
            archived_data: 存档数据实体

        Returns:
            MongoDB文档字典
        """
        return {
            "id": archived_data.id,
            "data_source_id": archived_data.data_source_id,
            "original_data_id": archived_data.original_data_id,
            "data_type": archived_data.data_type,
            # 核心内容
            "title": archived_data.title,
            "url": archived_data.url,
            "content": archived_data.content,  # 完整内容
            "snippet": archived_data.snippet,
            "published_date": archived_data.published_date,
            # Firecrawl字段
            "markdown_content": archived_data.markdown_content,
            "html_content": archived_data.html_content,
            # 类型特定字段和元数据
            "type_specific_fields": archived_data.type_specific_fields,
            "metadata": archived_data.metadata,
            # 存档元信息
            "archived_at": archived_data.archived_at,
            "archived_by": archived_data.archived_by,
            "archived_reason": archived_data.archived_reason,
            # 原始数据追溯
            "original_created_at": archived_data.original_created_at,
            "original_status": archived_data.original_status,
            # 系统字段
            "created_at": archived_data.created_at,
            "updated_at": archived_data.updated_at,
        }

    def _from_document(self, doc: Dict[str, Any]) -> ArchivedData:
        """MongoDB文档转实体

        Args:
            doc: MongoDB文档字典

        Returns:
            存档数据实体
        """
        return ArchivedData(
            id=doc["id"],
            data_source_id=doc.get("data_source_id", ""),
            original_data_id=doc.get("original_data_id", ""),
            data_type=doc.get("data_type", ""),
            # 核心内容
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),
            published_date=doc.get("published_date"),
            # Firecrawl字段
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            # 类型特定字段和元数据
            type_specific_fields=doc.get("type_specific_fields", {}),
            metadata=doc.get("metadata", {}),
            # 存档元信息
            archived_at=doc.get("archived_at", datetime.utcnow()),
            archived_by=doc.get("archived_by", ""),
            archived_reason=doc.get("archived_reason", "confirm"),
            # 原始数据追溯
            original_created_at=doc.get("original_created_at"),
            original_status=doc.get("original_status", ""),
            # 系统字段
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )


# 需要导入asyncio用于并行查询
import asyncio
