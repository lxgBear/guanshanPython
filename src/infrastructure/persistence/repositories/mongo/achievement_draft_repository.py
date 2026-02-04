"""AchievementDraft MongoDB 仓储实现"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.achievement_draft import (
    AchievementDraft,
    AchievementStatus,
    achievement_draft_to_mongo_doc,
    mongo_doc_to_achievement_draft,
)


class AchievementDraftRepository:
    """AchievementDraft MongoDB 仓储"""

    COLLECTION_NAME = "achievement_drafts"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(self, draft: AchievementDraft) -> AchievementDraft:
        """创建草稿"""
        collection = await self._get_collection()
        doc = achievement_draft_to_mongo_doc(draft)
        await collection.insert_one(doc)
        return draft

    async def get_by_id(self, draft_id: str) -> Optional[AchievementDraft]:
        """根据ID获取草稿"""
        collection = await self._get_collection()
        doc = await collection.find_one({"_id": draft_id})
        if doc:
            return mongo_doc_to_achievement_draft(doc)
        return None

    async def update(self, draft: AchievementDraft) -> AchievementDraft:
        """更新草稿"""
        collection = await self._get_collection()
        draft.updated_at = datetime.utcnow()
        doc = achievement_draft_to_mongo_doc(draft)
        await collection.replace_one({"_id": draft.id}, doc)
        return draft

    async def delete(self, draft_id: str) -> bool:
        """删除草稿"""
        collection = await self._get_collection()
        result = await collection.delete_one({"_id": draft_id})
        return result.deleted_count > 0

    async def list_by_author(
        self,
        author_id: str,
        status: Optional[AchievementStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """根据作者ID列出草稿"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {"author_id": author_id}
        if status:
            query["status"] = status.value

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("created_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_by_reviewer(
        self,
        reviewer_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """根据当前审核员ID列出待审核草稿"""
        collection = await self._get_collection()

        query = {
            "current_reviewer_id": reviewer_id,
            "status": AchievementStatus.PENDING_REVIEW.value,
        }

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("submitted_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_all(
        self,
        status: Optional[AchievementStatus] = None,
        primary_category: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出所有草稿（管理员）"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value
        if primary_category:
            query["primary_category"] = primary_category
        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
            ]

        total = await collection.count_documents(query)

        cursor = collection.find(query).sort("created_at", -1)
        cursor = cursor.skip((page - 1) * page_size).limit(page_size)

        items = []
        async for doc in cursor:
            items.append(mongo_doc_to_achievement_draft(doc))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# 单例
achievement_draft_repository = AchievementDraftRepository()
