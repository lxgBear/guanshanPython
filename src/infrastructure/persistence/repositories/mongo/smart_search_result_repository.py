"""智能搜索结果仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 ISmartSearchResultRepository 接口，提供：
- 智能搜索结果的存储和查询（使用独立集合 smart_search_results）
- 按子查询索引分组查询
- 聚合优先级管理
- 结果状态管理（v2.1.0）
- 多维度统计分析

职责：
- 数据库操作：MongoDB 集合 smart_search_results
- 智能搜索特定字段管理
- 聚合查询优化
- 统计分析

智能搜索特定字段：
- original_query: 原始查询
- decomposed_query: 分解后的子查询
- decomposition_reasoning: 分解理由
- query_focus: 查询焦点
- sub_query_index: 子查询索引
- aggregation_priority: 聚合优先级
- relevance_to_original: 对原始查询的相关性
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.core.domain.entities.smart_search_task import SmartSearchTask
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_smart_search_repository import (
    ISmartSearchResultRepository
)
from src.infrastructure.persistence.interfaces.i_repository import RepositoryException
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoSmartSearchResultRepository(ISmartSearchResultRepository):
    """智能搜索结果仓储 MongoDB 实现

    集合: smart_search_results

    索引建议:
    - _id (默认)
    - task_id (查询优化)
    - (task_id, sub_query_index) 复合索引
    - (task_id, status) 复合索引
    - original_query (跨任务查询)
    - aggregation_priority (排序优化)
    - relevance_score (排序优化)
    - created_at (排序优化)

    v1.5.0 ID系统统一：
    - 所有ID使用雪花算法字符串格式
    - 移除UUID依赖
    """

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """初始化仓储

        Args:
            db: MongoDB数据库实例，如果为None则自动获取
        """
        self._db = db
        self.collection_name = "smart_search_results"

    async def _get_collection(self):
        """获取MongoDB集合"""
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

            # 设置聚合优先级 (基于相关性分数)
            doc["aggregation_priority"] = int(result.relevance_score * 100)

        return doc

    def _dict_to_result(self, doc: Dict[str, Any]) -> SearchResult:
        """将MongoDB文档转换为SearchResult实体

        Args:
            doc: MongoDB文档

        Returns:
            搜索结果实体
        """
        # v1.5.0: 优先使用id字段（雪花ID），fallback到_id（向后兼容）
        result_id = str(doc.get("id") or doc.get("_id", ""))
        task_id = str(doc.get("task_id", ""))

        return SearchResult(
            id=result_id,
            task_id=task_id,

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
        """批量保存搜索结果（添加智能搜索特定字段）

        Args:
            results: 搜索结果列表
            task: 智能搜索任务
            sub_query_index: 子查询索引

        Raises:
            RepositoryException: 保存失败时抛出
        """
        if not results:
            return

        try:
            documents = []
            for result in results:
                doc = self._result_to_dict(result, task, sub_query_index)
                documents.append(doc)

            await (await self._get_collection()).insert_many(documents)
            logger.info(
                f"✅ 批量保存智能搜索结果: task_id={task.id}, "
                f"sub_query_index={sub_query_index}, count={len(results)}"
            )

        except Exception as e:
            logger.error(f"❌ 批量保存智能搜索结果失败: {e}")
            raise RepositoryException(f"批量保存智能搜索结果失败: {e}", e)

    async def get_results_by_task(
        self,
        task_id: str,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "aggregation_priority"
    ) -> Tuple[List[SearchResult], int]:
        """获取任务的所有搜索结果

        Args:
            task_id: 任务ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            sort_by: 排序字段 (aggregation_priority, relevance_score, created_at)

        Returns:
            (结果列表, 总数)

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
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

            logger.debug(
                f"📋 查询任务结果: task_id={task_id}, sort_by={sort_by}, total={total}"
            )
            return results, total

        except Exception as e:
            logger.error(f"❌ 查询任务结果失败: {e}")
            raise RepositoryException(f"查询任务结果失败: {e}", e)

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

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
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

            logger.debug(
                f"📋 查询子查询结果: task_id={task_id}, "
                f"sub_query_index={sub_query_index}, total={total}"
            )
            return results, total

        except Exception as e:
            logger.error(f"❌ 查询子查询结果失败: {e}")
            raise RepositoryException(f"查询子查询结果失败: {e}", e)

    async def get_top_results(
        self,
        task_id: str,
        limit: int = 10,
        min_relevance_score: float = 0.0
    ) -> List[SearchResult]:
        """获取任务的top结果（按聚合优先级和相关性）

        Args:
            task_id: 任务ID
            limit: 返回的最大记录数
            min_relevance_score: 最小相关性分数阈值

        Returns:
            结果列表

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
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

            logger.debug(
                f"🎯 查询top结果: task_id={task_id}, "
                f"limit={limit}, min_score={min_relevance_score}, count={len(results)}"
            )
            return results

        except Exception as e:
            logger.error(f"❌ 查询top结果失败: {e}")
            raise RepositoryException(f"查询top结果失败: {e}", e)

    async def get_results_by_original_query(
        self,
        original_query: str,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[SearchResult], int]:
        """根据原始查询获取结果（跨任务查询）

        Args:
            original_query: 原始查询
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            (结果列表, 总数)

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
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

            logger.debug(
                f"📋 跨任务查询: original_query={original_query}, total={total}"
            )
            return results, total

        except Exception as e:
            logger.error(f"❌ 跨任务查询失败: {e}")
            raise RepositoryException(f"跨任务查询失败: {e}", e)

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

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": {"aggregation_priority": priority}}
            )

            logger.debug(f"📊 更新聚合优先级: result_id={result_id}, priority={priority}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新聚合优先级失败: {e}")
            raise RepositoryException(f"更新聚合优先级失败: {e}", e)

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

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": {"relevance_to_original": relevance}}
            )

            logger.debug(f"📊 更新原始相关性: result_id={result_id}, relevance={relevance}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新原始相关性失败: {e}")
            raise RepositoryException(f"更新原始相关性失败: {e}", e)

    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果

        Args:
            task_id: 任务ID

        Returns:
            删除的记录数

        Raises:
            RepositoryException: 删除失败时抛出
        """
        try:
            result = await (await self._get_collection()).delete_many({"task_id": task_id})
            logger.info(f"🗑️ 删除任务结果: task_id={task_id}, count={result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务结果失败: {e}")
            raise RepositoryException(f"删除任务结果失败: {e}", e)

    async def count_results_by_task(self, task_id: str) -> int:
        """统计任务的结果数量

        Args:
            task_id: 任务ID

        Returns:
            结果数量

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            count = await (await self._get_collection()).count_documents({"task_id": task_id})
            return count

        except Exception as e:
            logger.error(f"❌ 统计任务结果失败: {e}")
            raise RepositoryException(f"统计任务结果失败: {e}", e)

    async def get_statistics_by_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务的结果统计信息

        Args:
            task_id: 任务ID

        Returns:
            统计信息字典

        Raises:
            RepositoryException: 统计失败时抛出
        """
        try:
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

            logger.debug(f"📊 任务统计: task_id={task_id}, total={total_count}")
            return {
                "total_count": total_count,
                "sub_query_statistics": sub_query_stats
            }

        except Exception as e:
            logger.error(f"❌ 获取任务统计失败: {e}")
            raise RepositoryException(f"获取任务统计失败: {e}", e)

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

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
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

            logger.debug(
                f"📋 按状态查询: task_id={task_id}, "
                f"status={status.value}, total={total}"
            )
            return results, total

        except Exception as e:
            logger.error(f"❌ 按状态查询失败: {e}")
            raise RepositoryException(f"按状态查询失败: {e}", e)

    async def count_by_status(self, task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            task_id: 任务ID

        Returns:
            状态计数字典

        Raises:
            RepositoryException: 统计失败时抛出
        """
        try:
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

            logger.debug(f"📊 状态统计: task_id={task_id}, counts={status_counts}")
            return status_counts

        except Exception as e:
            logger.error(f"❌ 状态统计失败: {e}")
            raise RepositoryException(f"状态统计失败: {e}", e)

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

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            logger.debug(f"📝 更新结果状态: result_id={result_id}, status={new_status.value}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新结果状态失败: {e}")
            raise RepositoryException(f"更新结果状态失败: {e}", e)

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

        Raises:
            RepositoryException: 更新失败时抛出
        """
        try:
            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await (await self._get_collection()).update_many(
                {"_id": {"$in": result_ids}},
                {"$set": update_data}
            )

            logger.info(
                f"📝 批量更新状态: count={result.modified_count}, "
                f"status={new_status.value}"
            )
            return result.modified_count

        except Exception as e:
            logger.error(f"❌ 批量更新状态失败: {e}")
            raise RepositoryException(f"批量更新状态失败: {e}", e)

    async def get_status_distribution(self, task_id: str) -> Dict[str, Any]:
        """获取状态分布统计

        Args:
            task_id: 任务ID

        Returns:
            状态分布统计信息

        Raises:
            RepositoryException: 统计失败时抛出
        """
        try:
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

            logger.debug(f"📊 状态分布: task_id={task_id}, total={total}")
            return {
                "total": total,
                "distribution": distribution
            }

        except Exception as e:
            logger.error(f"❌ 获取状态分布失败: {e}")
            raise RepositoryException(f"获取状态分布失败: {e}", e)
