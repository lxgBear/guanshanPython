"""
Search History MongoDB Repository (v2.8.0)

存储用户自然语言搜索的历史记录，支持按 mongo_id 和 source 查询。

设计说明:
- 使用 MongoDB Motor 异步驱动
- 使用雪花算法 ID 保持一致性
- 支持用户隔离和分页查询
- 支持按 source 类型筛选
- 支持按 mongo_id 查询引用了特定结果的历史

集合名称: search_history

文档结构:
{
    "_id": "snowflake_id",              # 历史记录ID
    "user_id": 123,                     # 用户ID
    "conversation_id": "conv_id",       # 关联的对话ID (可选)
    "query": "请介绍关于西藏的新闻",      # 用户问题
    "answer": "根据搜索结果...",          # AI回答
    "results": [                        # 搜索结果引用
        {
            "mongo_id": "news_xxx",     # 原始数据ID
            "source": "新闻",           # 来源类型
            "title": "标题",            # 标题
            "score": 0.95,              # 相关性评分
            "category": {...}           # 分类信息
        }
    ],
    "results_count": 5,                 # 结果数量
    "metadata": {                       # 元数据
        "search_mode": "single",
        "answer_length": 500,
        "processing_time_ms": 1200
    },
    "created_at": ISODate,
    "updated_at": ISODate
}

版本: v2.8.0
日期: 2025-01-04
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class SearchHistoryRepository:
    """Search History MongoDB 仓库

    存储和查询用户的搜索历史记录。

    Example:
        >>> repo = SearchHistoryRepository()
        >>> history_id = await repo.create(
        ...     user_id=123,
        ...     query="关于西藏的新闻",
        ...     answer="根据搜索结果...",
        ...     results=[{"mongo_id": "xxx", "source": "新闻", ...}]
        ... )
        >>> histories = await repo.list_by_user(user_id=123)
    """

    def __init__(self):
        """初始化仓库"""
        self.db = None
        self.collection_name = "search_history"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create(
        self,
        user_id: int,
        query: str,
        answer: str,
        results: List[Dict[str, Any]],
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建搜索历史记录

        Args:
            user_id: 用户ID
            query: 用户问题
            answer: AI回答
            results: 搜索结果列表 (包含 mongo_id, source, title, score, category)
            conversation_id: 关联的对话ID (可选)
            metadata: 元数据 (可选)

        Returns:
            str: 新创建的历史记录ID
        """
        collection = await self._get_collection()

        history_id = generate_string_id()
        now = datetime.utcnow()

        document = {
            "_id": history_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "query": query,
            "answer": answer,
            "results": results,
            "results_count": len(results),
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now
        }

        await collection.insert_one(document)
        logger.info(f"Created search history: id={history_id}, user={user_id}, results={len(results)}")

        return history_id

    async def get_by_id(self, history_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """根据ID获取历史记录

        Args:
            history_id: 历史记录ID
            user_id: 用户ID (可选，用于权限过滤)

        Returns:
            历史记录文档或None
        """
        collection = await self._get_collection()

        query = {"_id": history_id}
        if user_id is not None:
            query["user_id"] = user_id

        return await collection.find_one(query)

    async def list_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取用户的搜索历史列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            source_filter: 按来源类型筛选 (可选)

        Returns:
            历史记录列表
        """
        collection = await self._get_collection()

        query: Dict[str, Any] = {"user_id": user_id}

        # 如果指定了 source_filter，只返回包含该来源类型的历史
        if source_filter:
            query["results.source"] = source_filter

        cursor = collection.find(
            query,
            {
                "_id": 1,
                "query": 1,
                "answer": {"$substr": ["$answer", 0, 200]},  # 只返回前200字符
                "results_count": 1,
                "conversation_id": 1,
                "metadata": 1,
                "created_at": 1
            }
        ).sort("created_at", -1).skip(offset).limit(limit)

        return await cursor.to_list(length=limit)

    async def find_by_mongo_id(
        self,
        mongo_id: str,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """查询包含特定 mongo_id 的历史记录

        Args:
            mongo_id: 原始数据的 MongoDB ID
            user_id: 用户ID (可选，用于权限过滤)
            limit: 返回数量限制

        Returns:
            包含该 mongo_id 的历史记录列表
        """
        collection = await self._get_collection()

        query: Dict[str, Any] = {"results.mongo_id": mongo_id}
        if user_id is not None:
            query["user_id"] = user_id

        cursor = collection.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_source(
        self,
        source: str,
        user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """按来源类型查询历史记录

        Args:
            source: 来源类型 (如 "新闻", "用户上传")
            user_id: 用户ID (可选，用于权限过滤)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            包含该来源类型的历史记录列表
        """
        collection = await self._get_collection()

        query: Dict[str, Any] = {"results.source": source}
        if user_id is not None:
            query["user_id"] = user_id

        cursor = collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_by_user(self, user_id: int) -> int:
        """统计用户的历史记录数量

        Args:
            user_id: 用户ID

        Returns:
            历史记录数量
        """
        collection = await self._get_collection()
        return await collection.count_documents({"user_id": user_id})

    async def delete(self, history_id: str, user_id: int) -> bool:
        """删除历史记录

        Args:
            history_id: 历史记录ID
            user_id: 用户ID (确保只能删除自己的记录)

        Returns:
            是否删除成功
        """
        collection = await self._get_collection()
        result = await collection.delete_one({"_id": history_id, "user_id": user_id})
        return result.deleted_count > 0

    async def get_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户搜索统计

        Args:
            user_id: 用户ID

        Returns:
            统计信息
        """
        collection = await self._get_collection()

        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_searches": {"$sum": 1},
                "total_results": {"$sum": "$results_count"},
                "avg_results_per_search": {"$avg": "$results_count"}
            }}
        ]

        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)

        if results:
            return {
                "total_searches": results[0].get("total_searches", 0),
                "total_results": results[0].get("total_results", 0),
                "avg_results_per_search": round(results[0].get("avg_results_per_search", 0), 2)
            }

        return {
            "total_searches": 0,
            "total_results": 0,
            "avg_results_per_search": 0
        }

    async def ensure_indexes(self):
        """确保索引存在"""
        collection = await self._get_collection()

        # 用户ID + 创建时间 (用于列表查询)
        await collection.create_index([("user_id", 1), ("created_at", -1)])

        # mongo_id 索引 (用于按结果ID查询)
        await collection.create_index([("results.mongo_id", 1)])

        # source 索引 (用于按来源类型查询)
        await collection.create_index([("results.source", 1)])

        # conversation_id 索引 (用于关联对话)
        await collection.create_index([("conversation_id", 1)])

        logger.info(f"Ensured indexes for collection: {self.collection_name}")


# 全局单例
search_history_repository = SearchHistoryRepository()
