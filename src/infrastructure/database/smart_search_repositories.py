"""智能搜索数据仓储层实现

v2.0.0 智能搜索系统：
- SmartSearchTaskRepository: 管理智能搜索任务
- QueryDecompositionCacheRepository: 管理LLM分解结果缓存（降低成本）

数据库：MongoDB (使用Motor异步驱动)
集合命名：
- smart_search_tasks
- query_decomposition_cache
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import hashlib

from src.core.domain.entities.smart_search_task import SmartSearchTask, SmartSearchStatus, SubSearchResult
from src.core.domain.entities.query_decomposition import QueryDecomposition, DecomposedQuery
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SmartSearchTaskRepository:
    """智能搜索任务仓储"""

    def __init__(self):
        self.collection_name = "smart_search_tasks"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _task_to_dict(self, task: SmartSearchTask) -> Dict[str, Any]:
        """将任务实体转换为字典（用于数据库存储）"""
        return {
            "_id": task.id,
            "name": task.name,
            "description": task.description,
            "original_query": task.original_query,
            "search_config": task.search_config,

            # 分解阶段
            "decomposed_queries": [
                {
                    "query": q.query,
                    "reasoning": q.reasoning,
                    "focus": q.focus
                }
                for q in task.decomposed_queries
            ],
            "llm_model": task.llm_model,
            "llm_reasoning": task.llm_reasoning,
            "decomposition_tokens_used": task.decomposition_tokens_used,

            # 确认阶段
            "user_confirmed_queries": task.user_confirmed_queries,
            "user_modifications": task.user_modifications,

            # 执行阶段
            "sub_search_task_ids": task.sub_search_task_ids,
            "sub_search_results": {
                task_id: {
                    "query": r.query,
                    "task_id": r.task_id,
                    "status": r.status,
                    "result_count": r.result_count,
                    "credits_used": r.credits_used,
                    "execution_time_ms": r.execution_time_ms,
                    "error": r.error,
                    "retryable": r.retryable
                }
                for task_id, r in task.sub_search_results.items()
            },

            # 聚合统计
            "aggregated_stats": task.aggregated_stats,

            # 状态管理
            "status": task.status.value,
            "created_by": task.created_by,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "confirmed_at": task.confirmed_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,

            # 元数据
            "execution_time_ms": task.execution_time_ms or task.calculate_execution_time(),
            "error_message": task.error_message
        }

    def _dict_to_task(self, data: Dict[str, Any]) -> SmartSearchTask:
        """将字典转换为任务实体"""
        # 转换DecomposedQuery列表
        decomposed_queries = [
            DecomposedQuery(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in data.get("decomposed_queries", [])
        ]

        # 转换SubSearchResult字典
        sub_search_results = {
            task_id: SubSearchResult(
                query=r["query"],
                task_id=r["task_id"],
                status=r["status"],
                result_count=r.get("result_count", 0),
                credits_used=r.get("credits_used", 0),
                execution_time_ms=r.get("execution_time_ms", 0),
                error=r.get("error"),
                retryable=r.get("retryable", False)
            )
            for task_id, r in data.get("sub_search_results", {}).items()
        }

        return SmartSearchTask(
            id=data["_id"],
            name=data["name"],
            description=data.get("description", "智能搜索任务"),
            original_query=data["original_query"],
            search_config=data.get("search_config", {}),

            decomposed_queries=decomposed_queries,
            llm_model=data.get("llm_model", "gpt-4"),
            llm_reasoning=data.get("llm_reasoning", ""),
            decomposition_tokens_used=data.get("decomposition_tokens_used", 0),

            user_confirmed_queries=data.get("user_confirmed_queries", []),
            user_modifications=data.get("user_modifications", {}),

            sub_search_task_ids=data.get("sub_search_task_ids", []),
            sub_search_results=sub_search_results,

            aggregated_stats=data.get("aggregated_stats", {}),

            status=SmartSearchStatus(data.get("status", "awaiting_confirmation")),
            created_by=data.get("created_by", "system"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            confirmed_at=data.get("confirmed_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),

            execution_time_ms=data.get("execution_time_ms", 0),
            error_message=data.get("error_message")
        )

    async def create(self, task: SmartSearchTask) -> SmartSearchTask:
        """创建智能搜索任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)

            await collection.insert_one(task_dict)
            logger.info(f"创建智能搜索任务成功: {task.name} (ID: {task.id})")

            return task

        except Exception as e:
            logger.error(f"创建智能搜索任务失败: {e}")
            raise

    async def get_by_id(self, task_id: str) -> Optional[SmartSearchTask]:
        """根据ID获取任务"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": task_id})

            if data:
                return self._dict_to_task(data)
            return None

        except Exception as e:
            logger.error(f"获取智能搜索任务失败: {e}")
            raise

    async def update(self, task: SmartSearchTask) -> SmartSearchTask:
        """更新智能搜索任务"""
        try:
            collection = await self._get_collection()
            task_dict = self._task_to_dict(task)
            task_dict.pop("_id")  # 移除ID字段

            result = await collection.update_one(
                {"_id": task.id},
                {"$set": task_dict}
            )

            if result.matched_count == 0:
                raise ValueError(f"智能搜索任务不存在: {task.id}")

            logger.info(f"更新智能搜索任务成功: {task.name} (ID: {task.id})")
            return task

        except Exception as e:
            logger.error(f"更新智能搜索任务失败: {e}")
            raise

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Tuple[List[SmartSearchTask], int]:
        """获取智能搜索任务列表"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            filter_dict = {}

            if status:
                filter_dict["status"] = status

            if created_by:
                filter_dict["created_by"] = created_by

            # 计算总数
            total = await collection.count_documents(filter_dict)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(page_size)

            tasks = []
            async for data in cursor:
                tasks.append(self._dict_to_task(data))

            return tasks, total

        except Exception as e:
            logger.error(f"获取智能搜索任务列表失败: {e}")
            raise

    async def delete(self, task_id: str) -> bool:
        """删除智能搜索任务"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": task_id})

            if result.deleted_count > 0:
                logger.info(f"删除智能搜索任务成功: {task_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"删除智能搜索任务失败: {e}")
            raise


class QueryDecompositionCacheRepository:
    """
    查询分解缓存仓储

    作用：缓存LLM分解结果，降低API调用成本
    缓存策略：
    - 缓存键：MD5(query + search_context)
    - TTL：24小时自动过期
    - 命中统计：记录缓存使用次数
    """

    def __init__(self):
        self.collection_name = "query_decomposition_cache"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _calculate_cache_key(self, query: str, context: Dict[str, Any]) -> str:
        """
        计算缓存键

        Args:
            query: 原始查询
            context: 搜索上下文

        Returns:
            MD5哈希字符串
        """
        # 构建缓存键内容
        cache_content = f"{query}|{context.get('target_domains', '')}|{context.get('language', '')}|{context.get('time_range', '')}"

        # MD5哈希
        return hashlib.md5(cache_content.encode()).hexdigest()

    async def get_cached_decomposition(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Optional[QueryDecomposition]:
        """
        获取缓存的分解结果

        Args:
            query: 原始查询
            context: 搜索上下文

        Returns:
            QueryDecomposition或None
        """
        try:
            collection = await self._get_collection()
            query_hash = self._calculate_cache_key(query, context)

            # 查询缓存
            data = await collection.find_one({
                "query_hash": query_hash,
                "expires_at": {"$gt": datetime.utcnow()}  # 未过期
            })

            if data:
                # 更新命中次数和最后使用时间
                await collection.update_one(
                    {"_id": data["_id"]},
                    {
                        "$inc": {"hit_count": 1},
                        "$set": {"last_used_at": datetime.utcnow()}
                    }
                )

                logger.info(f"缓存命中: query_hash={query_hash}, hit_count={data['hit_count'] + 1}")

                # 构建QueryDecomposition对象
                return QueryDecomposition.from_dict(data["decomposition_result"])

            logger.debug(f"缓存未命中: query_hash={query_hash}")
            return None

        except Exception as e:
            logger.error(f"获取缓存分解结果失败: {e}")
            # 缓存失败不应阻塞主流程，返回None
            return None

    async def save_decomposition(
        self,
        query: str,
        context: Dict[str, Any],
        decomposition: QueryDecomposition,
        ttl_hours: int = 24
    ) -> bool:
        """
        保存分解结果到缓存

        Args:
            query: 原始查询
            context: 搜索上下文
            decomposition: 分解结果
            ttl_hours: 过期时间（小时）

        Returns:
            是否成功
        """
        try:
            collection = await self._get_collection()
            query_hash = self._calculate_cache_key(query, context)

            now = datetime.utcnow()
            expires_at = now + timedelta(hours=ttl_hours)

            # 构建缓存文档
            cache_doc = {
                "query_hash": query_hash,
                "original_query": query,
                "search_context": context,
                "decomposition_result": decomposition.to_dict(),
                "llm_model": decomposition.model,
                "tokens_used": decomposition.tokens_used,
                "hit_count": 0,
                "first_created_at": now,
                "last_used_at": now,
                "expires_at": expires_at,
                "created_at": now,
                "updated_at": now
            }

            # Upsert操作（如果存在则更新，不存在则插入）
            await collection.update_one(
                {"query_hash": query_hash},
                {"$set": cache_doc},
                upsert=True
            )

            logger.info(f"保存分解结果到缓存: query_hash={query_hash}, expires_at={expires_at}")
            return True

        except Exception as e:
            logger.error(f"保存分解结果到缓存失败: {e}")
            # 缓存失败不应阻塞主流程
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        try:
            collection = await self._get_collection()

            # 总缓存数
            total_cached = await collection.count_documents({})

            # 有效缓存数（未过期）
            valid_cached = await collection.count_documents({
                "expires_at": {"$gt": datetime.utcnow()}
            })

            # 总命中次数
            pipeline = [
                {"$group": {
                    "_id": None,
                    "total_hits": {"$sum": "$hit_count"},
                    "avg_hits": {"$avg": "$hit_count"},
                    "total_tokens_saved": {"$sum": "$tokens_used"}
                }}
            ]

            cursor = collection.aggregate(pipeline)
            stats_result = await cursor.to_list(length=1)

            if stats_result:
                stats = stats_result[0]
            else:
                stats = {
                    "total_hits": 0,
                    "avg_hits": 0.0,
                    "total_tokens_saved": 0
                }

            return {
                "total_cached": total_cached,
                "valid_cached": valid_cached,
                "expired_cached": total_cached - valid_cached,
                "total_hits": stats["total_hits"],
                "avg_hits_per_cache": round(stats["avg_hits"], 2),
                "estimated_tokens_saved": stats["total_tokens_saved"] * stats["total_hits"],
                "cache_hit_rate": round(stats["total_hits"] / total_cached, 2) if total_cached > 0 else 0.0
            }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}

    async def clear_expired_cache(self) -> int:
        """
        清理过期缓存

        Returns:
            删除的缓存数量
        """
        try:
            collection = await self._get_collection()

            result = await collection.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })

            deleted_count = result.deleted_count
            logger.info(f"清理过期缓存: 删除 {deleted_count} 条")

            return deleted_count

        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0
