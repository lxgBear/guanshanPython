"""发布条目仓储层

支持发布条目的 CRUD 操作和列表查询。
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.published_entry import (
    PublishedEntry,
    PublishedStatus,
    published_entry_to_mongo_doc,
    mongo_doc_to_published_entry,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PublishedEntryRepository:
    """发布条目仓储"""

    COLLECTION_NAME = "published_entries"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entry: PublishedEntry) -> PublishedEntry:
        """创建发布条目"""
        doc = published_entry_to_mongo_doc(entry)
        await self.collection.insert_one(doc)
        logger.info(f"创建发布条目成功: id={entry.id}, title={entry.title}")
        return entry

    async def get_by_id(self, entry_id: str) -> Optional[PublishedEntry]:
        """根据ID获取发布条目"""
        doc = await self.collection.find_one({"_id": entry_id})
        if doc:
            return mongo_doc_to_published_entry(doc)
        return None

    def _build_query(
        self,
        status: Optional[str] = None,
        primary_category: Optional[str] = None,
        secondary_categories: Optional[List[str]] = None,
        tertiary_categories: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        """构建通用查询条件"""
        query: Dict[str, Any] = {}

        if status:
            query["status"] = status

        if primary_category:
            query["primary_category"] = primary_category

        if secondary_categories:
            query["secondary_category"] = {"$in": secondary_categories}

        if tertiary_categories:
            query["tertiary_category"] = {"$in": tertiary_categories}

        if entry_types:
            query["entry_type"] = {"$in": entry_types}

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query.setdefault("published_at", {})["$gte"] = start_dt
            except (ValueError, AttributeError):
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query.setdefault("published_at", {})["$lte"] = end_dt
            except (ValueError, AttributeError):
                pass

        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"summary": {"$regex": keyword, "$options": "i"}},
            ]

        return query

    async def list_entries(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        primary_category: Optional[str] = None,
        secondary_categories: Optional[List[str]] = None,
        tertiary_categories: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "published_at",
        sort_order: int = -1,
        exclude_fields: Optional[List[str]] = None,
    ) -> Tuple[List[PublishedEntry], int]:
        """获取发布条目列表

        Args:
            page: 页码
            page_size: 每页数量
            status: 状态筛选 (published/archived)
            primary_category: 大类筛选
            secondary_categories: 细分类型筛选（多选）
            tertiary_categories: 地域筛选（多选）
            entry_types: 成果类型筛选（多选）
            start_date: 开始日期 (ISO format)
            end_date: 结束日期 (ISO format)
            keyword: 关键词搜索（标题、描述、摘要）
            sort_by: 排序字段
            sort_order: 排序方向 (-1=降序, 1=升序)
            exclude_fields: 排除的字段（用于列表优化，不返回大字段）
        """
        query = self._build_query(
            status=status,
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            tertiary_categories=tertiary_categories,
            entry_types=entry_types,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
        )

        total = await self.collection.count_documents(query)

        sort_field = sort_by if sort_by in [
            "published_at", "created_at", "reviewed_at", "title"
        ] else "published_at"

        # 构建 projection（排除大字段以优化列表查询）
        projection = None
        if exclude_fields:
            projection = {field: 0 for field in exclude_fields}

        cursor = self.collection.find(query, projection).sort(sort_field, sort_order)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        entries = []
        async for doc in cursor:
            entries.append(mongo_doc_to_published_entry(doc))

        return entries, total

    async def get_stats(
        self,
        status: Optional[str] = None,
        primary_category: Optional[str] = None,
        secondary_categories: Optional[List[str]] = None,
        tertiary_categories: Optional[List[str]] = None,
        entry_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取联动统计数据

        每个维度的统计排除该维度自身的筛选条件，但应用其他维度的筛选。
        """
        # 基础筛选条件（所有维度共用）
        base_params = dict(
            status=status,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
        )

        # entry_type 统计：排除 entry_types 筛选
        entry_type_query = self._build_query(
            **base_params,
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            tertiary_categories=tertiary_categories,
        )
        entry_type_stats = await self._aggregate_field("entry_type", entry_type_query)

        # primary_category 统计：排除 primary_category 筛选
        category_query = self._build_query(
            **base_params,
            entry_types=entry_types,
            secondary_categories=secondary_categories,
            tertiary_categories=tertiary_categories,
        )
        category_stats = await self._aggregate_field("primary_category", category_query)

        # secondary_category 统计：排除 secondary_categories 筛选
        sub_type_query = self._build_query(
            **base_params,
            primary_category=primary_category,
            entry_types=entry_types,
            tertiary_categories=tertiary_categories,
        )
        sub_type_stats = await self._aggregate_field("secondary_category", sub_type_query)

        # tertiary_category 统计：排除 tertiary_categories 筛选
        region_query = self._build_query(
            **base_params,
            primary_category=primary_category,
            entry_types=entry_types,
            secondary_categories=secondary_categories,
        )
        region_stats = await self._aggregate_field("tertiary_category", region_query)

        # 总数（应用所有筛选条件）
        total_query = self._build_query(
            **base_params,
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            tertiary_categories=tertiary_categories,
            entry_types=entry_types,
        )
        total = await self.collection.count_documents(total_query)

        return {
            "entry_type_stats": entry_type_stats,
            "category_stats": category_stats,
            "secondary_category_stats": sub_type_stats,
            "tertiary_category_stats": region_stats,
            "total": total,
        }

    async def _aggregate_field(
        self, field: str, query: Dict[str, Any]
    ) -> Dict[str, int]:
        """对指定字段进行分组计数聚合"""
        pipeline = [
            {"$match": query},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        ]
        result = {}
        async for doc in self.collection.aggregate(pipeline):
            key = doc["_id"]
            if key:  # 跳过空值
                result[key] = doc["count"]
        return result
