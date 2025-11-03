"""聚合搜索结果仓储

v1.5.2 职责分离实现：
- 专用于 smart_search_results 集合
- 存储智能搜索的去重聚合结果
- 包含综合评分、多源信息等聚合字段

架构说明：
- instant_search_results: 存储原始子搜索结果（InstantSearchResultRepository）
- smart_search_results: 存储聚合后的智能搜索结果（本Repository）
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.aggregated_search_result import (
    AggregatedSearchResult,
    SourceInfo
)
from src.core.domain.entities.search_result import ResultStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AggregatedSearchResultRepository:
    """聚合搜索结果仓储

    v1.5.2: 智能搜索专用结果存储

    职责：
    - 存储去重聚合后的搜索结果
    - 包含综合评分、多源信息、聚合统计
    - 与 instant_search_results 分离
    """

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """初始化仓储

        Args:
            db: MongoDB数据库实例，如果为None则自动获取
        """
        self._db = db
        self.collection_name = "smart_search_results"

    async def _get_collection(self):
        """获取集合"""
        if self._db is None:
            self._db = await get_mongodb_database()
        return self._db[self.collection_name]

    async def save_results(
        self,
        results: List[AggregatedSearchResult]
    ) -> int:
        """批量保存聚合搜索结果

        Args:
            results: 聚合搜索结果列表

        Returns:
            插入的记录数
        """
        if not results:
            logger.warning("保存聚合结果: 结果列表为空")
            return 0

        documents = []
        for result in results:
            doc = result.to_dict()
            # MongoDB使用 _id 作为主键
            doc["_id"] = doc["id"]
            documents.append(doc)

        try:
            await (await self._get_collection()).insert_many(documents)
            logger.info(
                f"保存聚合结果成功: task_id={results[0].smart_task_id}, "
                f"数量={len(results)}"
            )
            return len(results)

        except Exception as e:
            logger.error(f"保存聚合结果失败: {str(e)}")
            raise

    async def get_results_by_task(
        self,
        smart_task_id: str,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "composite_score"
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """获取任务的聚合搜索结果

        Args:
            smart_task_id: 智能搜索任务ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            sort_by: 排序字段（composite_score, avg_relevance_score, source_count, created_at）

        Returns:
            (结果列表, 总数)
        """
        query = {"smart_task_id": smart_task_id}

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 排序规则
        sort_fields = []
        if sort_by == "composite_score":
            sort_fields = [
                ("composite_score", -1),
                ("source_count", -1),
                ("avg_relevance_score", -1)
            ]
        elif sort_by == "source_count":
            sort_fields = [
                ("source_count", -1),
                ("composite_score", -1)
            ]
        elif sort_by == "avg_relevance_score":
            sort_fields = [
                ("avg_relevance_score", -1),
                ("composite_score", -1)
            ]
        elif sort_by == "created_at":
            sort_fields = [("created_at", -1)]
        else:
            sort_fields = [("composite_score", -1)]

        # 查询
        cursor = (await self._get_collection()).find(query).sort(sort_fields).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(AggregatedSearchResult.from_dict(doc))

        return results, total

    async def get_top_results(
        self,
        smart_task_id: str,
        limit: int = 10,
        min_composite_score: float = 0.0
    ) -> List[AggregatedSearchResult]:
        """获取任务的top结果（按综合评分）

        Args:
            smart_task_id: 智能搜索任务ID
            limit: 返回的最大记录数
            min_composite_score: 最小综合评分阈值

        Returns:
            结果列表
        """
        query = {
            "smart_task_id": smart_task_id,
            "composite_score": {"$gte": min_composite_score}
        }

        cursor = (await self._get_collection()).find(query).sort([
            ("composite_score", -1),
            ("source_count", -1),
            ("avg_relevance_score", -1)
        ]).limit(limit)

        results = []
        async for doc in cursor:
            results.append(AggregatedSearchResult.from_dict(doc))

        return results

    async def get_multi_source_results(
        self,
        smart_task_id: str,
        min_source_count: int = 2,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """获取多源结果（出现在多个查询中）

        Args:
            smart_task_id: 智能搜索任务ID
            min_source_count: 最小来源数量
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        query = {
            "smart_task_id": smart_task_id,
            "source_count": {"$gte": min_source_count}
        }

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 查询（按来源数量和综合评分排序）
        cursor = (await self._get_collection()).find(query).sort([
            ("source_count", -1),
            ("composite_score", -1)
        ]).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(AggregatedSearchResult.from_dict(doc))

        return results, total

    async def count_results_by_task(self, smart_task_id: str) -> int:
        """统计任务的结果数量

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            结果数量
        """
        return await (await self._get_collection()).count_documents(
            {"smart_task_id": smart_task_id}
        )

    async def get_statistics_by_task(self, smart_task_id: str) -> Dict[str, Any]:
        """获取任务的统计信息

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            统计信息字典
        """
        pipeline = [
            {"$match": {"smart_task_id": smart_task_id}},
            {"$group": {
                "_id": None,
                "total_count": {"$sum": 1},
                "avg_composite_score": {"$avg": "$composite_score"},
                "avg_source_count": {"$avg": "$source_count"},
                "max_composite_score": {"$max": "$composite_score"},
                "min_composite_score": {"$min": "$composite_score"},
                "multi_source_count": {
                    "$sum": {"$cond": [{"$gt": ["$source_count", 1]}, 1, 0]}
                },
                "single_source_count": {
                    "$sum": {"$cond": [{"$eq": ["$source_count", 1]}, 1, 0]}
                }
            }}
        ]

        stats = None
        async for doc in (await self._get_collection()).aggregate(pipeline):
            stats = {
                "total_results": doc["total_count"],
                "avg_composite_score": round(doc["avg_composite_score"], 3),
                "avg_source_count": round(doc["avg_source_count"], 2),
                "max_composite_score": round(doc["max_composite_score"], 3),
                "min_composite_score": round(doc["min_composite_score"], 3),
                "multi_source_results": doc["multi_source_count"],
                "single_source_results": doc["single_source_count"],
                "multi_source_ratio": round(
                    doc["multi_source_count"] / doc["total_count"] * 100, 2
                ) if doc["total_count"] > 0 else 0
            }

        return stats or {
            "total_results": 0,
            "avg_composite_score": 0,
            "avg_source_count": 0,
            "max_composite_score": 0,
            "min_composite_score": 0,
            "multi_source_results": 0,
            "single_source_results": 0,
            "multi_source_ratio": 0
        }

    async def delete_results_by_task(self, smart_task_id: str) -> int:
        """删除任务的所有结果

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            删除的记录数
        """
        result = await (await self._get_collection()).delete_many(
            {"smart_task_id": smart_task_id}
        )
        logger.info(
            f"删除聚合结果: task_id={smart_task_id}, "
            f"删除数量={result.deleted_count}"
        )
        return result.deleted_count

    async def update_result(self, result: AggregatedSearchResult) -> bool:
        """更新单个结果

        Args:
            result: 聚合搜索结果

        Returns:
            是否更新成功
        """
        result.updated_at = datetime.utcnow()
        doc = result.to_dict()

        update_result = await (await self._get_collection()).update_one(
            {"_id": result.id},
            {"$set": doc}
        )

        return update_result.modified_count > 0

    async def get_by_url(
        self,
        smart_task_id: str,
        url: str
    ) -> Optional[AggregatedSearchResult]:
        """根据URL查找结果（去重时使用）

        Args:
            smart_task_id: 智能搜索任务ID
            url: 结果URL

        Returns:
            聚合搜索结果（如果存在）
        """
        doc = await (await self._get_collection()).find_one({
            "smart_task_id": smart_task_id,
            "url": url
        })

        return AggregatedSearchResult.from_dict(doc) if doc else None

    # ==================== 状态管理方法 ====================

    async def get_results_by_status(
        self,
        smart_task_id: str,
        status: ResultStatus,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[AggregatedSearchResult], int]:
        """按状态筛选结果

        Args:
            smart_task_id: 智能搜索任务ID
            status: 结果状态
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        query = {
            "smart_task_id": smart_task_id,
            "status": status.value
        }

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 查询
        cursor = (await self._get_collection()).find(query).sort([
            ("composite_score", -1),
            ("created_at", -1)
        ]).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(AggregatedSearchResult.from_dict(doc))

        return results, total

    async def count_by_status(self, smart_task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            smart_task_id: 智能搜索任务ID

        Returns:
            状态计数字典
        """
        pipeline = [
            {"$match": {"smart_task_id": smart_task_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        status_counts = {status.value: 0 for status in ResultStatus}

        async for doc in (await self._get_collection()).aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]

        return status_counts

    async def update_result_status(
        self,
        result_id: str,
        new_status: ResultStatus
    ) -> bool:
        """更新单个结果状态

        Args:
            result_id: 结果ID
            new_status: 新状态

        Returns:
            是否更新成功
        """
        update_data = {
            "status": new_status.value,
            "updated_at": datetime.utcnow()
        }

        result = await (await self._get_collection()).update_one(
            {"_id": result_id},
            {"$set": update_data}
        )

        return result.modified_count > 0

    async def bulk_update_status(
        self,
        result_ids: List[str],
        new_status: ResultStatus
    ) -> int:
        """批量更新结果状态

        Args:
            result_ids: 结果ID列表
            new_status: 新状态

        Returns:
            更新的记录数
        """
        update_data = {
            "status": new_status.value,
            "updated_at": datetime.utcnow()
        }

        result = await (await self._get_collection()).update_many(
            {"_id": {"$in": result_ids}},
            {"$set": update_data}
        )

        return result.modified_count
