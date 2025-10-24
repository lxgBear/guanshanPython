"""智能搜索结果仓储"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.core.domain.entities.smart_search_task import SmartSearchTask
from src.infrastructure.database.connection import get_mongodb_database


class SmartSearchResultRepository:
    """智能搜索结果仓储 - 使用独立的 smart_search_results 集合"""

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

    def _result_to_dict(
        self,
        result: SearchResult,
        task: Optional[SmartSearchTask] = None,
        sub_query_index: int = 0
    ) -> Dict[str, Any]:
        """将SearchResult实体转换为MongoDB文档

        Args:
            result: 搜索结果实体
            task: 智能搜索任务 (用于填充智能搜索特定字段)
            sub_query_index: 子查询索引

        Returns:
            MongoDB文档字典
        """
        doc = {
            "_id": str(result.id),
            "task_id": str(result.task_id),

            # 搜索结果核心数据
            "title": result.title,
            "url": result.url,
            "content": result.content,
            "snippet": result.snippet,

            # 元数据
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,

            # Firecrawl 特定字段
            "markdown_content": result.markdown_content,
            "html_content": result.html_content,
            "article_tag": result.article_tag,
            "article_published_time": result.article_published_time,

            # 精简的元数据
            "source_url": result.source_url,
            "http_status_code": result.http_status_code,
            "search_position": result.search_position,
            "metadata": result.metadata,

            # 质量指标
            "relevance_score": result.relevance_score,
            "quality_score": result.quality_score,

            # 状态与时间
            "status": result.status.value,
            "created_at": result.created_at,
            "processed_at": result.processed_at,

            # 测试模式标记
            "is_test_data": result.is_test_data,
        }

        # 添加智能搜索特定字段
        doc["sub_query_index"] = sub_query_index
        doc["original_query"] = ""
        doc["decomposed_query"] = ""
        doc["decomposition_reasoning"] = ""
        doc["query_focus"] = ""
        doc["relevance_to_original"] = 0.0
        doc["aggregation_priority"] = 0
        doc["sub_search_task_id"] = ""

        # 如果提供了任务信息，填充智能搜索特定字段
        if task:
            doc["original_query"] = task.original_query

            # 获取对应的子查询信息
            if sub_query_index < len(task.decomposed_queries):
                sub_query = task.decomposed_queries[sub_query_index]
                doc["decomposed_query"] = sub_query.query
                doc["decomposition_reasoning"] = sub_query.reasoning
                doc["query_focus"] = sub_query.focus

            # 设置聚合优先级 (可以基于相关性分数)
            doc["aggregation_priority"] = int(result.relevance_score * 100)

        return doc

    def _dict_to_result(self, doc: Dict[str, Any]) -> SearchResult:
        """将MongoDB文档转换为SearchResult实体

        Args:
            doc: MongoDB文档

        Returns:
            搜索结果实体
        """
        return SearchResult(
            id=UUID(doc["_id"]),
            task_id=UUID(doc["task_id"]),

            # 搜索结果核心数据
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),

            # 元数据
            source=doc.get("source", "web"),
            published_date=doc.get("published_date"),
            author=doc.get("author"),
            language=doc.get("language"),

            # Firecrawl 特定字段
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            article_tag=doc.get("article_tag"),
            article_published_time=doc.get("article_published_time"),

            # 精简的元数据
            source_url=doc.get("source_url"),
            http_status_code=doc.get("http_status_code"),
            search_position=doc.get("search_position"),
            metadata=doc.get("metadata", {}),

            # 质量指标
            relevance_score=doc.get("relevance_score", 0.0),
            quality_score=doc.get("quality_score", 0.0),

            # 状态与时间
            status=ResultStatus(doc.get("status", "pending")),
            created_at=doc.get("created_at", datetime.utcnow()),
            processed_at=doc.get("processed_at"),

            # 测试模式标记
            is_test_data=doc.get("is_test_data", False),
        )

    async def save_results(
        self,
        results: List[SearchResult],
        task: SmartSearchTask,
        sub_query_index: int = 0
    ) -> None:
        """批量保存搜索结果 (添加智能搜索特定字段)

        Args:
            results: 搜索结果列表
            task: 智能搜索任务
            sub_query_index: 子查询索引
        """
        if not results:
            return

        documents = []
        for result in results:
            doc = self._result_to_dict(result, task, sub_query_index)
            documents.append(doc)

        await (await self._get_collection()).insert_many(documents)

    async def get_results_by_task(
        self,
        task_id: str,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "aggregation_priority"
    ) -> Tuple[List[SearchResult], int]:
        """获取任务的搜索结果

        Args:
            task_id: 任务ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            sort_by: 排序字段 (aggregation_priority, relevance_score, created_at)

        Returns:
            (结果列表, 总数)
        """
        query = {"task_id": task_id}

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 排序规则
        sort_fields = []
        if sort_by == "aggregation_priority":
            sort_fields = [
                ("aggregation_priority", -1),
                ("relevance_score", -1),
                ("created_at", -1)
            ]
        elif sort_by == "relevance_score":
            sort_fields = [("relevance_score", -1), ("created_at", -1)]
        elif sort_by == "created_at":
            sort_fields = [("created_at", -1)]
        else:
            sort_fields = [("aggregation_priority", -1)]

        # 查询
        cursor = (await self._get_collection()).find(query).sort(sort_fields).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(self._dict_to_result(doc))

        return results, total

    async def get_results_by_sub_query(
        self,
        task_id: str,
        sub_query_index: int,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """获取特定子查询的结果

        Args:
            task_id: 任务ID
            sub_query_index: 子查询索引
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        query = {
            "task_id": task_id,
            "sub_query_index": sub_query_index
        }

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 查询
        cursor = (await self._get_collection()).find(query).sort([
            ("relevance_score", -1),
            ("created_at", -1)
        ]).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(self._dict_to_result(doc))

        return results, total

    async def get_top_results(
        self,
        task_id: str,
        limit: int = 10,
        min_relevance_score: float = 0.0
    ) -> List[SearchResult]:
        """获取任务的top结果 (按聚合优先级和相关性)

        Args:
            task_id: 任务ID
            limit: 返回的最大记录数
            min_relevance_score: 最小相关性分数阈值

        Returns:
            结果列表
        """
        query = {
            "task_id": task_id,
            "relevance_score": {"$gte": min_relevance_score}
        }

        cursor = (await self._get_collection()).find(query).sort([
            ("aggregation_priority", -1),
            ("relevance_score", -1),
            ("quality_score", -1)
        ]).limit(limit)

        results = []
        async for doc in cursor:
            results.append(self._dict_to_result(doc))

        return results

    async def get_results_by_original_query(
        self,
        original_query: str,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """根据原始查询获取结果 (跨任务查询)

        Args:
            original_query: 原始查询
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        query = {"original_query": original_query}

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 查询
        cursor = (await self._get_collection()).find(query).sort([
            ("created_at", -1),
            ("relevance_score", -1)
        ]).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(self._dict_to_result(doc))

        return results, total

    async def update_aggregation_priority(
        self,
        result_id: str,
        priority: int
    ) -> bool:
        """更新结果的聚合优先级

        Args:
            result_id: 结果ID
            priority: 新的优先级

        Returns:
            是否更新成功
        """
        result = await (await self._get_collection()).update_one(
            {"_id": result_id},
            {"$set": {"aggregation_priority": priority}}
        )

        return result.modified_count > 0

    async def update_relevance_to_original(
        self,
        result_id: str,
        relevance: float
    ) -> bool:
        """更新结果对原始查询的相关性

        Args:
            result_id: 结果ID
            relevance: 相关性分数 (0.0-1.0)

        Returns:
            是否更新成功
        """
        result = await (await self._get_collection()).update_one(
            {"_id": result_id},
            {"$set": {"relevance_to_original": relevance}}
        )

        return result.modified_count > 0

    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果

        Args:
            task_id: 任务ID

        Returns:
            删除的记录数
        """
        result = await (await self._get_collection()).delete_many({"task_id": task_id})
        return result.deleted_count

    async def count_results_by_task(self, task_id: str) -> int:
        """统计任务的结果数量

        Args:
            task_id: 任务ID

        Returns:
            结果数量
        """
        return await (await self._get_collection()).count_documents({"task_id": task_id})

    async def get_statistics_by_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务的结果统计信息

        Args:
            task_id: 任务ID

        Returns:
            统计信息字典
        """
        pipeline = [
            {"$match": {"task_id": task_id}},
            {"$group": {
                "_id": "$sub_query_index",
                "count": {"$sum": 1},
                "avg_relevance": {"$avg": "$relevance_score"},
                "avg_quality": {"$avg": "$quality_score"},
                "max_relevance": {"$max": "$relevance_score"},
                "min_relevance": {"$min": "$relevance_score"}
            }},
            {"$sort": {"_id": 1}}
        ]

        sub_query_stats = []
        async for doc in (await self._get_collection()).aggregate(pipeline):
            sub_query_stats.append({
                "sub_query_index": doc["_id"],
                "count": doc["count"],
                "avg_relevance_score": round(doc["avg_relevance"], 3),
                "avg_quality_score": round(doc["avg_quality"], 3),
                "max_relevance_score": round(doc["max_relevance"], 3),
                "min_relevance_score": round(doc["min_relevance"], 3)
            })

        # 总体统计
        total_count = await self.count_results_by_task(task_id)

        return {
            "total_count": total_count,
            "sub_query_statistics": sub_query_stats
        }

    # ==================== 状态管理方法 (v2.1.0新增) ====================

    async def get_results_by_status(
        self,
        task_id: str,
        status: ResultStatus,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """按状态筛选搜索结果

        Args:
            task_id: 任务ID
            status: 结果状态
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)
        """
        query = {
            "task_id": task_id,
            "status": status.value
        }

        # 总数
        total = await (await self._get_collection()).count_documents(query)

        # 查询
        cursor = (await self._get_collection()).find(query).sort([
            ("created_at", -1),
            ("relevance_score", -1)
        ]).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(self._dict_to_result(doc))

        return results, total

    async def count_by_status(self, task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            task_id: 任务ID

        Returns:
            状态计数字典 {"pending": 10, "archived": 5, ...}
        """
        pipeline = [
            {"$match": {"task_id": task_id}},
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
        from datetime import datetime

        update_data = {
            "status": new_status.value,
            "processed_at": datetime.utcnow()
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
        from datetime import datetime

        update_data = {
            "status": new_status.value,
            "processed_at": datetime.utcnow()
        }

        result = await (await self._get_collection()).update_many(
            {"_id": {"$in": result_ids}},
            {"$set": update_data}
        )

        return result.modified_count

    async def get_status_distribution(self, task_id: str) -> Dict[str, Any]:
        """获取状态分布统计

        Args:
            task_id: 任务ID

        Returns:
            状态分布统计信息
        """
        # 获取各状态计数
        status_counts = await self.count_by_status(task_id)
        total = sum(status_counts.values())

        # 计算百分比
        distribution = {}
        for status, count in status_counts.items():
            percentage = (count / total * 100) if total > 0 else 0
            distribution[status] = {
                "count": count,
                "percentage": round(percentage, 2)
            }

        return {
            "total": total,
            "distribution": distribution
        }
