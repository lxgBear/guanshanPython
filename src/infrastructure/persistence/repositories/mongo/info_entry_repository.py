"""信息条目仓储层

v1.0.0 初始版本：
- 支持条目的 CRUD 操作
- 支持从多个数据源获取原始数据并创建条目

v1.1.1 兼容性修复：
- 所有数据源查询支持 ObjectId 格式（兼容旧数据）
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from src.core.domain.entities.info_entry import (
    InfoEntry,
    RawDataRef,
    EntryStatus,
    info_entry_to_mongo_doc,
    mongo_doc_to_info_entry,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InfoEntryRepository:
    """信息条目仓储"""

    COLLECTION_NAME = "info_entries"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entry: InfoEntry) -> InfoEntry:
        """创建条目"""
        doc = info_entry_to_mongo_doc(entry)
        await self.collection.insert_one(doc)
        logger.info(f"创建条目成功: id={entry.id}, title={entry.title}")
        return entry

    async def get_by_id(self, entry_id: str) -> Optional[InfoEntry]:
        """根据ID获取条目"""
        doc = await self.collection.find_one({"_id": entry_id})
        if doc:
            return mongo_doc_to_info_entry(doc)
        return None

    async def update(self, entry: InfoEntry) -> InfoEntry:
        """更新条目"""
        entry.updated_at = datetime.utcnow()
        doc = info_entry_to_mongo_doc(entry)
        await self.collection.replace_one({"_id": entry.id}, doc)
        logger.info(f"更新条目成功: id={entry.id}")
        return entry

    async def delete(self, entry_id: str) -> bool:
        """删除条目"""
        result = await self.collection.delete_one({"_id": entry_id})
        if result.deleted_count > 0:
            logger.info(f"删除条目成功: id={entry_id}")
            return True
        return False

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        tag_search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
    ) -> Tuple[List[InfoEntry], int]:
        """获取用户的条目列表

        v4.34.0: 新增分类筛选、标签搜索、时间范围筛选、排序参数
        """
        query: Dict[str, Any] = {"user_id": user_id}

        if status:
            query["status"] = status

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]

        # v4.34.0: 分类筛选
        if primary_category:
            query["primary_category"] = primary_category

        if secondary_category:
            query["secondary_category"] = secondary_category

        if tertiary_category:
            query["tertiary_category"] = tertiary_category

        # v4.34.0: 标签模糊搜索
        if tag_search:
            query["tags"] = {"$regex": tag_search, "$options": "i"}

        # v4.34.0: 时间范围筛选
        if start_date or end_date:
            time_query = {}
            if start_date:
                time_query["$gte"] = start_date
            if end_date:
                time_query["$lte"] = end_date
            query["created_at"] = time_query

        # 获取总数
        total = await self.collection.count_documents(query)

        # 分页查询，支持动态排序
        sort_field = sort_by if sort_by in ["created_at", "updated_at", "title"] else "created_at"
        cursor = self.collection.find(query).sort(sort_field, sort_order)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        entries = []
        async for doc in cursor:
            entries.append(mongo_doc_to_info_entry(doc))

        return entries, total

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
                    "source_task_id": "任务ID"
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
            # 定时任务 或 手动录入 -> search_results
            return await self._fetch_from_search_results(data_id)

        elif data_type == "smart-search":
            # 智能搜索 -> instant_search_results
            return await self._fetch_from_instant_search_results(data_id)

        elif data_type == "chat-search":
            # Chat搜索 -> langgraph_search_results
            return await self._fetch_from_langgraph_results(data_id)

        elif data_type == "upload":
            # 文档上传 -> file_uploads
            return await self._fetch_from_file_uploads(data_id)

        else:
            logger.warning(f"未知的数据类型: {data_type}")
            return None

    async def _fetch_from_search_results(self, data_id: str) -> Optional[RawDataRef]:
        """从 search_results 获取数据

        v1.1.1: 支持多种 ID 格式查询（字符串 _id、ObjectId _id、id 字段）
        """
        doc = await self.db.search_results.find_one({"_id": data_id})
        if not doc:
            # 尝试用 ObjectId 格式查询（兼容旧数据）
            try:
                oid = ObjectId(data_id)
                doc = await self.db.search_results.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            # 尝试用 id 字段查询
            doc = await self.db.search_results.find_one({"id": data_id})
        if not doc:
            return None

        # 获取翻译内容（从嵌入的 news_results 字段）
        news_results = doc.get("news_results", {}) or {}
        translated_title = news_results.get("title_zh", "")
        translated_content = news_results.get("content_zh", "")
        translated_at = doc.get("translated_at")

        # 判断来源类型
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
            task_name=doc.get("task_name", ""),  # v1.1.0 新增
        )

    async def _fetch_from_instant_search_results(self, data_id: str) -> Optional[RawDataRef]:
        """从 instant_search_results 获取数据

        v1.1.1: 支持多种 ID 格式查询（字符串 _id、ObjectId _id）
        """
        doc = await self.db.instant_search_results.find_one({"_id": data_id})
        if not doc:
            # 尝试用 ObjectId 格式查询（兼容旧数据）
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
        """从 langgraph_search_results 获取数据

        v1.1.1: 支持多种 ID 格式查询（字符串 _id、ObjectId _id）
        """
        doc = await self.db.langgraph_search_results.find_one({"_id": data_id})
        if not doc:
            # 尝试用 ObjectId 格式查询（兼容旧数据）
            try:
                oid = ObjectId(data_id)
                doc = await self.db.langgraph_search_results.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            return None

        # 获取翻译内容（从 translator_dict 字段）
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
        """从 file_uploads 获取数据

        v1.1.1: 支持多种 ID 格式查询（字符串 _id、ObjectId _id、file_id 字段）
        """
        doc = await self.db.file_uploads.find_one({"_id": data_id})
        if not doc:
            # 尝试用 ObjectId 格式查询（兼容旧数据）
            try:
                oid = ObjectId(data_id)
                doc = await self.db.file_uploads.find_one({"_id": oid})
            except Exception:
                pass
        if not doc:
            # 尝试用 file_id 字段查询
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
