"""查询分解缓存仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 IQueryDecompositionCacheRepository 接口，提供：
- LLM分解结果缓存管理（降低API成本）
- 缓存TTL管理（默认24小时）
- 缓存统计和清理功能

职责：
- 数据库操作：MongoDB 集合 query_decomposition_cache
- 缓存键计算：MD5(query + search_context)
- 命中统计维护
- 过期缓存清理

缓存策略：
- 缓存键：MD5(query + search_context)
- TTL：24小时自动过期
- 命中统计：记录缓存使用次数和最后使用时间
- Upsert操作：存在则更新，不存在则插入

注意：
- 缓存失败不应阻塞主流程
- 所有方法应捕获异常并返回默认值
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from src.core.domain.entities.query_decomposition import QueryDecomposition
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_smart_search_repository import (
    IQueryDecompositionCacheRepository
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoQueryDecompositionCacheRepository(IQueryDecompositionCacheRepository):
    """查询分解缓存仓储 MongoDB 实现

    集合: query_decomposition_cache

    索引建议:
    - query_hash (唯一索引)
    - expires_at (TTL索引，自动删除过期文档)
    - last_used_at (查询优化)
    - hit_count (统计优化)

    缓存文档结构:
    {
        "query_hash": "md5_hash_string",
        "original_query": "原始查询",
        "search_context": {...},
        "decomposition_result": {...},
        "llm_model": "gpt-4",
        "tokens_used": 1500,
        "hit_count": 5,
        "first_created_at": datetime,
        "last_used_at": datetime,
        "expires_at": datetime,
        "created_at": datetime,
        "updated_at": datetime
    }
    """

    def __init__(self):
        self.collection_name = "query_decomposition_cache"

    async def _get_collection(self):
        """获取MongoDB集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _calculate_cache_key(self, query: str, context: Dict[str, Any]) -> str:
        """计算缓存键

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
        """获取缓存的分解结果

        Args:
            query: 原始查询
            context: 搜索上下文

        Returns:
            QueryDecomposition或None

        业务逻辑：
        - 计算缓存键：MD5(query + context)
        - 检查是否过期（expires_at > now）
        - 命中则更新hit_count和last_used_at
        - 未命中返回None

        注意：
        - 缓存失败不抛出异常，返回None
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

                logger.info(
                    f"✅ 缓存命中: query_hash={query_hash}, "
                    f"hit_count={data['hit_count'] + 1}"
                )

                # 构建QueryDecomposition对象
                return QueryDecomposition.from_dict(data["decomposition_result"])

            logger.debug(f"🔍 缓存未命中: query_hash={query_hash}")
            return None

        except Exception as e:
            logger.error(f"❌ 获取缓存分解结果失败: {e}")
            # 缓存失败不应阻塞主流程，返回None
            return None

    async def save_decomposition(
        self,
        query: str,
        context: Dict[str, Any],
        decomposition: QueryDecomposition,
        ttl_hours: int = 24
    ) -> bool:
        """保存分解结果到缓存

        Args:
            query: 原始查询
            context: 搜索上下文
            decomposition: 分解结果
            ttl_hours: 过期时间（小时）

        Returns:
            是否成功

        业务逻辑：
        - 计算缓存键和过期时间
        - Upsert操作（存在则更新，不存在则插入）
        - 失败不抛出异常，返回False

        注意：
        - 缓存失败不应阻塞主流程
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

            logger.info(
                f"✅ 保存分解结果到缓存: query_hash={query_hash}, "
                f"expires_at={expires_at}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 保存分解结果到缓存失败: {e}")
            # 缓存失败不应阻塞主流程
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            统计信息字典
            {
                "total_cached": 100,
                "valid_cached": 80,
                "expired_cached": 20,
                "total_hits": 500,
                "avg_hits_per_cache": 5.0,
                "estimated_tokens_saved": 50000,
                "cache_hit_rate": 0.8
            }

        用途：
        - 监控缓存效果
        - 成本节约分析

        注意：
        - 统计失败返回空字典
        """
        try:
            collection = await self._get_collection()

            # 总缓存数
            total_cached = await collection.count_documents({})

            # 有效缓存数（未过期）
            valid_cached = await collection.count_documents({
                "expires_at": {"$gt": datetime.utcnow()}
            })

            # 总命中次数和token节约
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

            cache_hit_rate = round(stats["total_hits"] / total_cached, 2) if total_cached > 0 else 0.0

            result = {
                "total_cached": total_cached,
                "valid_cached": valid_cached,
                "expired_cached": total_cached - valid_cached,
                "total_hits": stats["total_hits"],
                "avg_hits_per_cache": round(stats["avg_hits"], 2),
                "estimated_tokens_saved": stats["total_tokens_saved"] * stats["total_hits"],
                "cache_hit_rate": cache_hit_rate
            }

            logger.info(
                f"📊 缓存统计: total={total_cached}, valid={valid_cached}, "
                f"hit_rate={cache_hit_rate}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ 获取缓存统计失败: {e}")
            return {}

    async def clear_expired_cache(self) -> int:
        """清理过期缓存

        Returns:
            删除的缓存数量

        用途：
        - 定期清理（如每日凌晨）
        - 释放存储空间

        注意：
        - 清理失败返回0
        """
        try:
            collection = await self._get_collection()

            result = await collection.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })

            deleted_count = result.deleted_count
            logger.info(f"🗑️ 清理过期缓存: 删除 {deleted_count} 条")

            return deleted_count

        except Exception as e:
            logger.error(f"❌ 清理过期缓存失败: {e}")
            return 0
