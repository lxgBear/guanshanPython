"""AchievementReviewLog MongoDB 仓储实现"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.achievement_review_log import (
    AchievementReviewLog,
    ReviewAction,
    review_log_to_mongo_doc,
    mongo_doc_to_review_log,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AchievementReviewLogRepository:
    """AchievementReviewLog MongoDB 仓储"""

    COLLECTION_NAME = "achievement_review_logs"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.COLLECTION_NAME]

    async def create(self, log: AchievementReviewLog) -> AchievementReviewLog:
        """创建审核日志"""
        collection = await self._get_collection()
        doc = review_log_to_mongo_doc(log)
        await collection.insert_one(doc)
        logger.info(f"创建审核日志成功: id={log.id}, achievement_id={log.achievement_id}, action={log.action.value}")
        return log

    async def get_by_achievement_id(
        self,
        achievement_id: str,
    ) -> List[AchievementReviewLog]:
        """获取某个草稿的所有审核日志"""
        collection = await self._get_collection()

        cursor = collection.find({"achievement_id": achievement_id}).sort("created_at", 1)

        logs = []
        async for doc in cursor:
            logs.append(mongo_doc_to_review_log(doc))

        return logs

    async def get_latest_by_achievement_id(
        self,
        achievement_id: str,
    ) -> Optional[AchievementReviewLog]:
        """获取某个草稿的最新审核日志"""
        collection = await self._get_collection()

        doc = await collection.find_one(
            {"achievement_id": achievement_id},
            sort=[("created_at", -1)]
        )

        if doc:
            return mongo_doc_to_review_log(doc)
        return None

    async def get_previous_reviewer(
        self,
        achievement_id: str,
        current_level: int,
    ) -> Optional[Dict[str, Any]]:
        """获取上一级审核员信息（用于退回上一级）"""
        collection = await self._get_collection()

        # 查找上一级的审核记录（forward 或 submit 操作）
        doc = await collection.find_one(
            {
                "achievement_id": achievement_id,
                "review_level": current_level - 1,
                "action": {"$in": [ReviewAction.FORWARD.value, ReviewAction.SUBMIT.value]},
            },
            sort=[("created_at", -1)]
        )

        if doc:
            return {
                "reviewer_id": doc.get("operator_id", ""),
                "reviewer_name": doc.get("operator_name", ""),
                "level": current_level - 1,
            }
        return None

    async def count_by_operator(
        self,
        operator_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[ReviewAction]] = None,
    ) -> int:
        """统计审核员的审核数量"""
        collection = await self._get_collection()

        query: Dict[str, Any] = {"operator_id": operator_id}

        if actions:
            query["action"] = {"$in": [a.value for a in actions]}
        else:
            # 默认统计所有审核操作（排除 submit 和 resubmit）
            query["action"] = {"$in": [
                ReviewAction.APPROVE.value,
                ReviewAction.FORWARD.value,
                ReviewAction.RETURN_TO_AUTHOR.value,
                ReviewAction.RETURN_TO_PREVIOUS.value,
                ReviewAction.VOID.value,
            ]}

        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lt"] = end_date

        return await collection.count_documents(query)

    async def get_review_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """获取审核统计（按审核员分组）"""
        collection = await self._get_collection()

        match_stage: Dict[str, Any] = {
            "action": {"$in": [
                ReviewAction.APPROVE.value,
                ReviewAction.FORWARD.value,
                ReviewAction.RETURN_TO_AUTHOR.value,
                ReviewAction.RETURN_TO_PREVIOUS.value,
                ReviewAction.VOID.value,
            ]}
        }

        if start_date or end_date:
            match_stage["created_at"] = {}
            if start_date:
                match_stage["created_at"]["$gte"] = start_date
            if end_date:
                match_stage["created_at"]["$lt"] = end_date

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": {
                    "operator_id": "$operator_id",
                    "operator_name": "$operator_name",
                },
                "total": {"$sum": 1},
                "approved": {"$sum": {"$cond": [{"$eq": ["$action", "approve"]}, 1, 0]}},
                "forwarded": {"$sum": {"$cond": [{"$eq": ["$action", "forward"]}, 1, 0]}},
                "returned": {"$sum": {"$cond": [{"$in": ["$action", ["return_to_author", "return_to_previous"]]}, 1, 0]}},
                "voided": {"$sum": {"$cond": [{"$eq": ["$action", "void"]}, 1, 0]}},
            }},
            {"$sort": {"total": -1}},
        ]

        results = []
        async for doc in collection.aggregate(pipeline):
            results.append({
                "operator_id": doc["_id"]["operator_id"],
                "operator_name": doc["_id"]["operator_name"],
                "total": doc["total"],
                "approved": doc["approved"],
                "forwarded": doc["forwarded"],
                "returned": doc["returned"],
                "voided": doc["voided"],
            })

        return results


# 单例
achievement_review_log_repository = AchievementReviewLogRepository()
