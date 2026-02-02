"""审核条目仓储层

v1.0.0 初始版本：
- 支持审核条目的 CRUD 操作
- 支持按状态、类型筛选
- 复用 InfoEntryRepository 的数据源获取逻辑
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from src.core.domain.entities.review_entry import (
    ReviewEntry,
    ReviewStatus,
    EntryType,
    review_entry_to_mongo_doc,
    mongo_doc_to_review_entry,
)
from src.core.domain.entities.info_entry import RawDataRef
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReviewEntryRepository:
    """审核条目仓储"""

    COLLECTION_NAME = "review_entries"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entry: ReviewEntry) -> ReviewEntry:
        """创建审核条目"""
        doc = review_entry_to_mongo_doc(entry)
        await self.collection.insert_one(doc)
        logger.info(f"创建审核条目成功: id={entry.id}, title={entry.title}, type={entry.entry_type.value}")
        return entry

    async def get_by_id(self, entry_id: str) -> Optional[ReviewEntry]:
        """根据ID获取审核条目"""
        doc = await self.collection.find_one({"_id": entry_id})
        if doc:
            return mongo_doc_to_review_entry(doc)
        return None

    async def update(self, entry: ReviewEntry) -> ReviewEntry:
        """更新审核条目"""
        entry.updated_at = datetime.utcnow()
        doc = review_entry_to_mongo_doc(entry)
        await self.collection.replace_one({"_id": entry.id}, doc)
        logger.info(f"更新审核条目成功: id={entry.id}")
        return entry

    async def delete(self, entry_id: str) -> bool:
        """删除审核条目"""
        result = await self.collection.delete_one({"_id": entry_id})
        if result.deleted_count > 0:
            logger.info(f"删除审核条目成功: id={entry_id}")
            return True
        return False

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        entry_type: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: int = -1,
    ) -> Tuple[List[ReviewEntry], int]:
        """
        获取用户的审核条目列表
        
        Args:
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            status: 状态筛选
            entry_type: 条目类型筛选
            keyword: 关键词搜索
            sort_by: 排序字段 (updated_at, created_at, submitted_at, title)
            sort_order: 排序方向 (-1=降序, 1=升序)
        """
        query: Dict[str, Any] = {"user_id": user_id}

        if status:
            query["status"] = status

        if entry_type:
            query["entry_type"] = entry_type

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询，支持动态排序
        sort_field = sort_by if sort_by in ["updated_at", "created_at", "submitted_at", "title"] else "updated_at"
        cursor = self.collection.find(query).sort(sort_field, sort_order)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        entries = []
        async for doc in cursor:
            entries.append(mongo_doc_to_review_entry(doc))

        return entries, total

    async def list_pending_reviews(
        self,
        page: int = 1,
        page_size: int = 20,
        entry_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[ReviewEntry], int]:
        """获取待审核列表（管理员用）"""
        query: Dict[str, Any] = {"status": ReviewStatus.PENDING_REVIEW.value}

        if entry_type:
            query["entry_type"] = entry_type

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询，按提交时间排序
        cursor = self.collection.find(query).sort("submitted_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        entries = []
        async for doc in cursor:
            entries.append(mongo_doc_to_review_entry(doc))

        return entries, total

    async def submit_for_review(self, entry_id: str, reviewer_id: str) -> Optional[ReviewEntry]:
        """提交审核

        Args:
            entry_id: 条目ID
            reviewer_id: 审核员ID
        """
        entry = await self.get_by_id(entry_id)
        if not entry:
            return None

        entry.submit_for_review(reviewer_id)
        return await self.update(entry)

    async def approve(
        self,
        entry_id: str,
        reviewer_id: str,
        comment: str = ""
    ) -> Optional[ReviewEntry]:
        """通过审核"""
        entry = await self.get_by_id(entry_id)
        if not entry:
            return None

        entry.approve(reviewer_id, comment)
        return await self.update(entry)

    async def reject(
        self,
        entry_id: str,
        reviewer_id: str,
        comment: str = ""
    ) -> Optional[ReviewEntry]:
        """退回审核"""
        entry = await self.get_by_id(entry_id)
        if not entry:
            return None

        entry.reject(reviewer_id, comment)
        return await self.update(entry)

    # ========== 数据源获取方法（复用 info_entry_repository 的逻辑） ==========

    async def fetch_raw_data_from_sources(
        self,
        data_refs: List[Dict[str, Any]],
    ) -> List[RawDataRef]:
        """从各数据源获取原始数据，统一字段名

        Args:
            data_refs: 前端传来的数据引用列表
                [{
                    "data_id": "xxx",
                    "data_type": "scheduled | smart-search | chat-search | upload | manual",
                }]

        Returns:
            统一格式的 RawDataRef 列表
        """
        raw_data_refs = []

        for ref_info in data_refs:
            data_id = ref_info.get("data_id", "")
            data_type = ref_info.get("data_type", "")

            try:
                raw_data_ref = await self._fetch_single_raw_data(data_id, data_type)
                if raw_data_ref:
                    raw_data_refs.append(raw_data_ref)
            except Exception as e:
                logger.warning(f"获取原始数据失败: data_id={data_id}, error={e}")

        return raw_data_refs

    async def _fetch_single_raw_data(
        self,
        data_id: str,
        data_type: str,
    ) -> Optional[RawDataRef]:
        """从单个数据源获取数据"""

        if data_type in ["scheduled", "manual"]:
            return await self._fetch_from_search_results(data_id)
        elif data_type == "smart-search":
            return await self._fetch_from_instant_search_results(data_id)
        elif data_type == "chat-search":
            return await self._fetch_from_langgraph_results(data_id)
        elif data_type == "upload":
            return await self._fetch_from_file_uploads(data_id)
        else:
            logger.warning(f"未知的数据类型: {data_type}")
            return None

    async def _fetch_from_search_results(self, data_id: str) -> Optional[RawDataRef]:
        """从 search_results 获取数据"""
        doc = await self.db.search_results.find_one({"_id": data_id})
        if not doc:
            try:
                oid = ObjectId(data_id)
                doc = await self.db.search_results.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            doc = await self.db.search_results.find_one({"id": data_id})
        if not doc:
            return None

        news_results = doc.get("news_results", {}) or {}
        translated_title = news_results.get("title_zh", "")
        translated_content = news_results.get("content_zh", "")
        translated_at = doc.get("translated_at")

        source = doc.get("source", "")
        data_source_type = doc.get("data_source_type", "")
        if data_source_type == "user_added" or source == "translated":
            origin_site = "手动录入"
            ref_data_type = "manual"
        else:
            origin_site = "定时任务"
            ref_data_type = "scheduled"

        return RawDataRef(
            data_id=str(doc.get("_id", "")),
            data_type=ref_data_type,
            source_collection="search_results",
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            origin_site=origin_site,
            published_date=doc.get("published_date"),
            markdown_content=doc.get("markdown_content", ""),
            html_content=doc.get("html_content", ""),
            snippet=doc.get("snippet", ""),
            translated_title=translated_title,
            translated_content=translated_content,
            translated_at=translated_at,
            task_name=doc.get("task_name", ""),
        )

    async def _fetch_from_instant_search_results(self, data_id: str) -> Optional[RawDataRef]:
        """从 instant_search_results 获取数据"""
        doc = await self.db.instant_search_results.find_one({"_id": data_id})
        if not doc:
            try:
                oid = ObjectId(data_id)
                doc = await self.db.instant_search_results.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            return None

        return RawDataRef(
            data_id=str(doc.get("_id", "")),
            data_type="smart-search",
            source_collection="instant_search_results",
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            origin_site=doc.get("source", "智能搜索"),
            published_date=doc.get("published_date"),
            markdown_content=doc.get("markdown_content", ""),
            html_content=doc.get("html_content", ""),
            snippet=doc.get("snippet", ""),
            translated_title=doc.get("translated_title", ""),
            translated_content=doc.get("translated_content", ""),
            translated_at=doc.get("translated_at"),
        )

    async def _fetch_from_langgraph_results(self, data_id: str) -> Optional[RawDataRef]:
        """从 langgraph_search_results 获取数据"""
        doc = await self.db.langgraph_search_results.find_one({"_id": data_id})
        if not doc:
            try:
                oid = ObjectId(data_id)
                doc = await self.db.langgraph_search_results.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            return None

        translator_dict = doc.get("translator_dict", {}) or {}
        translated_title = translator_dict.get("title_zh", "")
        translated_content = translator_dict.get("content_zh", "")

        return RawDataRef(
            data_id=str(doc.get("_id", "")),
            data_type="chat-search",
            source_collection="langgraph_search_results",
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            origin_site=doc.get("source", "Chat搜索"),
            published_date=doc.get("published_date"),
            markdown_content=doc.get("markdown_content", ""),
            html_content=doc.get("html_content", ""),
            snippet=doc.get("snippet", ""),
            translated_title=translated_title,
            translated_content=translated_content,
            translated_at=doc.get("ai_processed_at"),
        )

    async def _fetch_from_file_uploads(self, data_id: str) -> Optional[RawDataRef]:
        """从 file_uploads 获取数据"""
        doc = await self.db.file_uploads.find_one({"_id": data_id})
        if not doc:
            try:
                oid = ObjectId(data_id)
                doc = await self.db.file_uploads.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            doc = await self.db.file_uploads.find_one({"file_id": data_id})
        if not doc:
            return None

        return RawDataRef(
            data_id=str(doc.get("_id", "")),
            data_type="upload",
            source_collection="file_uploads",
            title=doc.get("title", doc.get("display_name", "")),
            url=doc.get("storage_url", ""),
            origin_site="文档上传",
            published_date=None,
            markdown_content=doc.get("content", ""),
            html_content="",
            snippet=doc.get("content", "")[:500] if doc.get("content") else "",
            translated_title="",
            translated_content="",
            translated_at=None,
        )
