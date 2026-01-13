"""
Claude Search Session MongoDB Repository

存储 Claude Search Agent v2.1 的搜索会话和结果。

设计说明:
- 使用 MongoDB Motor 异步驱动
- 使用雪花算法 ID 保持一致性
- 内嵌存储 results 数组（单文档事务性）
- 支持用户隔离和查询隔离

集合名称: claude_search_sessions

文档结构:
{
    "_id": "snowflake_id",           # 会话ID
    "query": "南海争端",              # 原始查询
    "version": "v2.1.0",             # Agent版本
    "user_id": "optional_user",       # 用户ID（隔离用）
    "configs": [...],                 # 搜索配置数组
    "results": [                      # 搜索结果数组
        {
            "source_id": "ZH-00-001",
            "title": "...",
            "url": "...",
            "snippet": "...",
            "source_tier": "official",
            "source_tier_label": "官方来源",
            "credibility_score": 0.95,
            "language": "zh",
            "country": "CN",
            "search_query": "...",
            "published_date": "",
            "time_verified": false,
            "relevance_score": 1.0,
            "position": 1
        }
    ],
    "stats": {
        "total_results": 32,
        "configs_count": 6,
        "success_count": 6,
        "raw_results_count": 32,
        "by_source_tier": {...},
        "by_language": {...},
        "execution_time": 16.21
    },
    "timestamp": "2025-12-25T16:41:12.422221",
    "created_at": ISODate,
    "updated_at": ISODate
}

版本: v1.0.0
日期: 2025-12-25
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class ClaudeSearchSessionRepository:
    """Claude Search Session MongoDB 仓库

    存储和查询 Claude Search Agent v2.1 的搜索会话。

    Example:
        >>> repo = ClaudeSearchSessionRepository()
        >>> session_id = await repo.create_session(
        ...     query="南海争端",
        ...     version="v2.1.0",
        ...     configs=[...],
        ...     results=[...],
        ...     stats={...}
        ... )
        >>> session = await repo.get_by_id(session_id)
    """

    def __init__(self):
        """初始化仓库"""
        self.db = None
        self.collection_name = "claude_search_sessions"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create_session(
        self,
        query: str,
        version: str,
        configs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        stats: Dict[str, Any],
        user_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> str:
        """创建搜索会话

        Args:
            query: 原始用户查询
            version: Agent 版本号 (e.g., "v2.1.0")
            configs: 搜索配置数组
            results: 搜索结果数组 (EnhancedSearchResult[])
            stats: 统计信息
            user_id: 用户ID（可选，用于隔离）
            timestamp: 搜索时间戳（可选）

        Returns:
            str: 创建的会话ID（雪花算法ID字符串）

        Example:
            >>> session_id = await repo.create_session(
            ...     query="南海争端",
            ...     version="v2.1.0",
            ...     configs=[{"query": "...", "lang": "zh"}],
            ...     results=[{"source_id": "ZH-00-001", ...}],
            ...     stats={"total_results": 32, ...}
            ... )
        """
        collection = await self._get_collection()

        # 生成雪花ID（字符串格式）
        session_id = generate_string_id()

        # 准备文档
        document = {
            "_id": session_id,
            "query": query,
            "version": version,
            "user_id": user_id,
            "configs": configs,
            "results": results,
            "stats": stats,
            "timestamp": timestamp or datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # 插入文档
        await collection.insert_one(document)

        logger.info(
            f"创建 Claude 搜索会话成功: ID={session_id}, "
            f"query='{query[:30]}...', results={len(results)}"
        )
        return session_id

    async def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取搜索会话

        Args:
            session_id: 会话ID（雪花算法ID字符串）

        Returns:
            Optional[Dict]: 会话数据，不存在时返回 None

        Example:
            >>> session = await repo.get_by_id("248728141926559744")
            >>> if session:
            ...     print(session["query"], len(session["results"]))
        """
        collection = await self._get_collection()

        document = await collection.find_one({"_id": session_id})

        if not document:
            logger.debug(f"搜索会话不存在: ID={session_id}")
            return None

        return document

    async def get_results(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话的搜索结果

        Args:
            session_id: 会话ID

        Returns:
            Optional[List[Dict]]: 搜索结果列表，不存在时返回 None

        Example:
            >>> results = await repo.get_results("248728141926559744")
            >>> for r in results:
            ...     print(r["title"], r["source_tier"])
        """
        collection = await self._get_collection()

        # 仅返回 results 字段
        document = await collection.find_one(
            {"_id": session_id},
            {"results": 1, "_id": 0}
        )

        if not document:
            return None

        return document.get("results", [])

    async def get_by_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """根据查询文本搜索会话

        Args:
            query: 搜索的查询文本（支持部分匹配）
            user_id: 可选的用户ID过滤
            limit: 返回数量限制

        Returns:
            List[Dict]: 匹配的会话列表

        Example:
            >>> sessions = await repo.get_by_query("南海", limit=5)
        """
        collection = await self._get_collection()

        # 构建查询条件
        filter_query = {
            "query": {"$regex": query, "$options": "i"}
        }

        if user_id:
            filter_query["user_id"] = user_id

        # 查询（按创建时间倒序）
        cursor = collection.find(filter_query).sort("created_at", -1).limit(limit)
        sessions = await cursor.to_list(length=limit)

        return sessions

    async def get_recent(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取最近的搜索会话

        Args:
            limit: 返回数量限制
            offset: 分页偏移量
            user_id: 可选的用户ID过滤

        Returns:
            List[Dict]: 搜索会话列表

        Example:
            >>> sessions = await repo.get_recent(limit=10)
            >>> for s in sessions:
            ...     print(s["query"], s["stats"]["total_results"])
        """
        collection = await self._get_collection()

        # 构建查询条件
        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id

        # 查询（按创建时间倒序）
        cursor = collection.find(filter_query).sort("created_at", -1).skip(offset).limit(limit)
        sessions = await cursor.to_list(length=limit)

        return sessions

    async def get_by_source_tier(
        self,
        source_tier: str,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """按来源层级查询结果

        从所有会话中查找指定来源层级的结果。

        Args:
            source_tier: 来源层级 (official/local_mainstream/intl_mainstream/think_tank/other)
            limit: 返回数量限制
            user_id: 可选的用户ID过滤

        Returns:
            List[Dict]: 匹配的搜索结果列表

        Example:
            >>> official_results = await repo.get_by_source_tier("official", limit=20)
        """
        collection = await self._get_collection()

        # 使用聚合管道
        pipeline = [
            # 展开 results 数组
            {"$unwind": "$results"},
            # 过滤来源层级
            {"$match": {"results.source_tier": source_tier}},
        ]

        if user_id:
            pipeline.insert(0, {"$match": {"user_id": user_id}})

        pipeline.extend([
            # 按创建时间排序
            {"$sort": {"created_at": -1}},
            # 限制数量
            {"$limit": limit},
            # 提取结果
            {"$replaceRoot": {"newRoot": "$results"}}
        ])

        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=limit)

        return results

    async def get_stats_summary(
        self,
        user_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """获取统计汇总

        Args:
            user_id: 可选的用户ID过滤
            days: 统计天数

        Returns:
            Dict: 统计汇总信息

        Example:
            >>> stats = await repo.get_stats_summary(days=7)
            >>> print(stats["total_sessions"], stats["total_results"])
        """
        collection = await self._get_collection()

        # 计算截止日期
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 构建基础查询
        match_query = {"created_at": {"$gte": cutoff_date}}
        if user_id:
            match_query["user_id"] = user_id

        # 聚合统计
        pipeline = [
            {"$match": match_query},
            {"$group": {
                "_id": None,
                "total_sessions": {"$sum": 1},
                "total_results": {"$sum": {"$size": "$results"}},
                "avg_execution_time": {"$avg": "$stats.execution_time"},
                "source_tier_counts": {"$push": "$stats.by_source_tier"}
            }}
        ]

        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            return {
                "total_sessions": 0,
                "total_results": 0,
                "avg_execution_time": 0,
                "period_days": days
            }

        stats = result[0]
        stats["period_days"] = days
        del stats["_id"]

        return stats

    async def count_total(self, user_id: Optional[str] = None) -> int:
        """统计总会话数

        Args:
            user_id: 可选的用户ID过滤

        Returns:
            int: 总会话数

        Example:
            >>> total = await repo.count_total()
        """
        collection = await self._get_collection()

        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id

        return await collection.count_documents(filter_query)

    async def delete_by_id(self, session_id: str) -> bool:
        """根据 ID 删除会话

        Args:
            session_id: 会话ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete_by_id("248728141926559744")
        """
        collection = await self._get_collection()

        result = await collection.delete_one({"_id": session_id})

        success = result.deleted_count > 0
        if success:
            logger.info(f"删除搜索会话成功: ID={session_id}")

        return success

    async def delete_old_sessions(self, days: int = 30) -> int:
        """删除旧会话

        Args:
            days: 保留天数，删除超过此天数的会话

        Returns:
            int: 删除的会话数

        Example:
            >>> deleted = await repo.delete_old_sessions(days=30)
        """
        collection = await self._get_collection()

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })

        deleted_count = result.deleted_count
        logger.info(f"删除 {deleted_count} 个旧的搜索会话 (>{days}天)")

        return deleted_count

    async def create_indexes(self):
        """创建索引以优化查询性能

        创建的索引：
        1. created_at (倒序) - 优化最近查询
        2. user_id + created_at - 优化用户查询历史
        3. query (文本索引) - 优化关键词搜索
        4. results.source_tier - 优化来源层级查询
        5. version - 优化版本过滤

        Example:
            >>> await repo.create_indexes()
        """
        collection = await self._get_collection()

        # 1. 创建时间索引（倒序）
        await collection.create_index(
            [("created_at", -1)],
            name="created_at_desc"
        )

        # 2. 用户 + 创建时间复合索引
        await collection.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="user_created_idx"
        )

        # 3. 查询文本索引
        await collection.create_index(
            [("query", "text")],
            name="query_text_idx"
        )

        # 4. 来源层级索引（用于聚合查询）
        await collection.create_index(
            [("results.source_tier", 1)],
            name="results_source_tier_idx"
        )

        # 5. 版本索引
        await collection.create_index(
            [("version", 1)],
            name="version_idx"
        )

        # 6. 用户+查询复合索引（用于去重检查）
        await collection.create_index(
            [("user_id", 1), ("query", 1), ("created_at", -1)],
            name="user_query_time_idx"
        )

        logger.info("Claude 搜索会话索引创建完成")


# 全局实例
claude_search_session_repository = ClaudeSearchSessionRepository()
