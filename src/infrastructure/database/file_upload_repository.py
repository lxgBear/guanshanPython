"""文件上传仓储 MongoDB 实现

Version: v1.0.0

实现文件上传元数据的持久化，提供：
- 文件上传记录的CRUD操作
- 多维度过滤查询（用户、状态、存储类型、时间范围）
- 分页查询支持
- 统计信息查询

职责：
- 数据库操作：MongoDB 集合 file_uploads
- 实体转换：FileUpload <-> Dict（包含枚举类型转换）
- 异常处理：统一的错误日志和异常抛出
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClientSession

from src.core.domain.entities.file_upload import (
    FileUpload,
    UploadStatus,
    StorageProvider,
    FileCategory
)
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_repository import (
    IBasicRepository,
    RepositoryException
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoFileUploadRepository(IBasicRepository[FileUpload]):
    """文件上传仓储 MongoDB 实现

    集合: file_uploads

    索引建议:
    - file_id (唯一索引)
    - uploaded_by (用户查询)
    - status (状态筛选)
    - created_at (时间排序)
    - storage_provider (存储类型筛选)
    - (uploaded_by, status) 复合索引（用户文件列表查询）
    """

    def __init__(self, db=None):
        """初始化仓储

        Args:
            db: MongoDB数据库实例，如果为None则自动获取
        """
        self._db = db
        self.collection_name = "file_uploads"

    async def _get_collection(self):
        """获取MongoDB集合"""
        if self._db is None:
            self._db = await get_mongodb_database()
        return self._db[self.collection_name]

    def _to_document(self, file_upload: FileUpload) -> Dict[str, Any]:
        """实体转MongoDB文档

        Args:
            file_upload: 文件上传实体

        Returns:
            MongoDB文档字典
        """
        return {
            "file_id": file_upload.file_id,
            "original_filename": file_upload.original_filename,
            "stored_filename": file_upload.stored_filename,
            "display_name": file_upload.display_name,
            "file_size": file_upload.file_size,
            "mime_type": file_upload.mime_type,
            "file_extension": file_upload.file_extension,
            "category": file_upload.category.value,
            "storage_provider": file_upload.storage_provider.value,
            "storage_path": file_upload.storage_path,
            "storage_url": file_upload.storage_url,
            "status": file_upload.status.value,
            "upload_progress": file_upload.upload_progress,
            "content_hash": file_upload.content_hash,
            "uploaded_by": file_upload.uploaded_by,
            "created_at": file_upload.created_at,
            "updated_at": file_upload.updated_at,
            "metadata": file_upload.metadata,
            "tags": file_upload.tags
        }

    def _from_document(self, doc: Dict[str, Any]) -> FileUpload:
        """MongoDB文档转实体

        Args:
            doc: MongoDB文档字典

        Returns:
            文件上传实体
        """
        return FileUpload(
            file_id=doc["file_id"],
            original_filename=doc.get("original_filename", ""),
            stored_filename=doc.get("stored_filename", ""),
            display_name=doc.get("display_name"),
            file_size=doc.get("file_size", 0),
            mime_type=doc.get("mime_type", ""),
            file_extension=doc.get("file_extension", ""),
            category=FileCategory(doc.get("category", "other")),
            storage_provider=StorageProvider(doc.get("storage_provider", "local")),
            storage_path=doc.get("storage_path", ""),
            storage_url=doc.get("storage_url"),
            status=UploadStatus(doc.get("status", "pending")),
            upload_progress=doc.get("upload_progress", 0),
            content_hash=doc.get("content_hash"),
            uploaded_by=doc.get("uploaded_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            metadata=doc.get("metadata", {}),
            tags=doc.get("tags", [])
        )

    async def create(
        self,
        entity: FileUpload,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> str:
        """创建文件上传记录

        Args:
            entity: 文件上传实体
            session: MongoDB事务会话（可选）

        Returns:
            创建的文件ID

        Raises:
            RepositoryException: 创建失败时抛出
        """
        try:
            collection = await self._get_collection()
            doc = self._to_document(entity)
            await collection.insert_one(doc, session=session)
            logger.info(f"✅ 创建文件上传记录: {entity.file_id} - {entity.original_filename}")
            return entity.file_id

        except Exception as e:
            logger.error(f"❌ 创建文件上传记录失败: {e}")
            raise RepositoryException(f"创建文件上传记录失败: {e}", e)

    async def get_by_id(
        self,
        file_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> Optional[FileUpload]:
        """根据ID查询文件上传记录

        Args:
            file_id: 文件ID
            session: MongoDB事务会话（可选）

        Returns:
            文件上传实体或None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            doc = await collection.find_one({"file_id": file_id}, session=session)
            return self._from_document(doc) if doc else None

        except Exception as e:
            logger.error(f"❌ 查询文件上传记录失败 (ID: {file_id}): {e}")
            raise RepositoryException(f"查询文件上传记录失败: {e}", e)

    async def find_all(
        self,
        uploaded_by: Optional[str] = None,
        status: Optional[str] = None,
        storage_provider: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[FileUpload]:
        """查询所有文件上传记录（支持多维度过滤和分页）

        Args:
            uploaded_by: 上传者过滤
            status: 状态过滤
            storage_provider: 存储提供商过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            limit: 每页数量
            skip: 跳过数量

        Returns:
            文件上传实体列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            query = {}

            if uploaded_by:
                query["uploaded_by"] = uploaded_by
            if status:
                query["status"] = status
            if storage_provider:
                query["storage_provider"] = storage_provider

            # 时间范围过滤
            if start_date or end_date:
                query["created_at"] = {}
                if start_date:
                    query["created_at"]["$gte"] = start_date
                if end_date:
                    query["created_at"]["$lte"] = end_date

            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            docs = await cursor.to_list(length=limit)

            logger.debug(f"📋 查询文件上传列表: count={len(docs)}, filters={query}")
            return [self._from_document(doc) for doc in docs]

        except Exception as e:
            logger.error(f"❌ 查询文件上传列表失败: {e}")
            raise RepositoryException(f"查询文件上传列表失败: {e}", e)

    async def count(
        self,
        uploaded_by: Optional[str] = None,
        status: Optional[str] = None,
        storage_provider: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """统计文件上传数量

        Args:
            uploaded_by: 上传者过滤
            status: 状态过滤
            storage_provider: 存储提供商过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤

        Returns:
            文件上传数量

        Raises:
            RepositoryException: 统计失败时抛出
        """
        try:
            collection = await self._get_collection()
            query = {}

            if uploaded_by:
                query["uploaded_by"] = uploaded_by
            if status:
                query["status"] = status
            if storage_provider:
                query["storage_provider"] = storage_provider

            if start_date or end_date:
                query["created_at"] = {}
                if start_date:
                    query["created_at"]["$gte"] = start_date
                if end_date:
                    query["created_at"]["$lte"] = end_date

            return await collection.count_documents(query)

        except Exception as e:
            logger.error(f"❌ 统计文件上传失败: {e}")
            raise RepositoryException(f"统计文件上传失败: {e}", e)

    async def update(
        self,
        entity: FileUpload,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新文件上传记录

        Args:
            entity: 文件上传实体（必须包含有效的 file_id）
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            entity.updated_at = datetime.utcnow()
            doc = self._to_document(entity)

            result = await collection.update_one(
                {"file_id": entity.file_id},
                {"$set": doc},
                session=session
            )

            if result.modified_count > 0:
                logger.info(f"📝 更新文件上传记录: {entity.file_id}")

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新文件上传记录失败: {e}")
            raise RepositoryException(f"更新文件上传记录失败: {e}", e)

    async def delete(
        self,
        file_id: str,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """删除文件上传记录

        Args:
            file_id: 文件ID
            session: MongoDB事务会话（可选）

        Returns:
            是否删除成功

        Raises:
            RepositoryException: 删除失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"file_id": file_id}, session=session)

            if result.deleted_count > 0:
                logger.info(f"🗑️  删除文件上传记录: {file_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 删除文件上传记录失败: {e}")
            raise RepositoryException(f"删除文件上传记录失败: {e}", e)

    async def exists(
        self,
        file_id: str
    ) -> bool:
        """检查文件上传记录是否存在

        Args:
            file_id: 文件ID

        Returns:
            文件上传记录是否存在

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            result = await self.get_by_id(file_id)
            return result is not None
        except Exception as e:
            logger.error(f"❌ 检查文件上传记录是否存在失败 (ID: {file_id}): {e}")
            raise RepositoryException(f"检查文件上传记录是否存在失败: {e}", e)

    async def update_status(
        self,
        file_id: str,
        status: UploadStatus,
        session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """更新文件上传状态

        Args:
            file_id: 文件ID
            status: 新状态
            session: MongoDB事务会话（可选）

        Returns:
            是否更新成功

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.update_one(
                {"file_id": file_id},
                {
                    "$set": {
                        "status": status.value,
                        "updated_at": datetime.utcnow()
                    }
                },
                session=session
            )

            logger.debug(f"📝 更新文件状态: {file_id} -> {status.value}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新文件状态失败: {e}")
            raise RepositoryException(f"更新文件状态失败: {e}", e)
