"""
NL Search MongoDB Repository

将 NL Search 日志从 MariaDB 迁移到 MongoDB，实现数据库架构统一。

设计说明:
- 使用 MongoDB Motor 异步驱动
- 使用雪花算法 ID 与其他集合保持一致
- 支持完整的 CRUD 操作和查询功能
- 优化索引提升查询性能

集合名称: nl_search_logs

文档结构:
{
    "_id": "244879702695698432",  # 雪花算法ID（字符串）
    "user_id": "user_123",  # 可选，用户ID
    "query_text": "最近有哪些AI技术突破",  # 用户查询
    "llm_analysis": {  # LLM 分析结果
        "intent": "technology_news",
        "keywords": ["AI", "技术突破"],
        "entities": ["AI", "技术"],
        "time_range": "recent",
        "confidence": 0.95
    },
    "search_config": {  # 搜索配置（可选）
        "max_results": 10,
        "source": "gpt5_search"
    },
    "results_count": 5,  # 返回结果数量
    "status": "completed",  # pending/completed/failed
    "created_at": ISODate("2025-11-17T08:00:00Z"),
    "updated_at": ISODate("2025-11-17T08:00:01Z")
}

版本: v2.0.0 (MongoDB)
日期: 2025-11-17
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class MongoNLSearchLogRepository:
    """NL Search MongoDB 仓库

    提供自然语言搜索日志的 MongoDB 存储和查询功能。

    Example:
        >>> repo = MongoNLSearchLogRepository()
        >>> log_id = await repo.create(
        ...     query_text="最近AI技术突破",
        ...     llm_analysis={"intent": "tech_news", "keywords": ["AI"]}
        ... )
        >>> log = await repo.get_by_id(log_id)
    """

    def __init__(self):
        """初始化仓库"""
        self.db = None
        self.collection_name = "nl_search_logs"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        llm_analysis: Optional[Dict[str, Any]] = None,
        search_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建搜索日志

        Args:
            query_text: 用户的自然语言查询
            user_id: 用户ID（可选）
            llm_analysis: LLM 分析结果（可选）
            search_config: 搜索配置（可选）

        Returns:
            str: 创建的日志ID（雪花算法ID字符串）

        Example:
            >>> log_id = await repo.create(
            ...     query_text="AI技术突破",
            ...     user_id="user_123",
            ...     llm_analysis={"intent": "tech_news"}
            ... )
        """
        collection = await self._get_collection()

        # 生成雪花ID（字符串格式）
        log_id = generate_string_id()

        # 准备文档
        document = {
            "_id": log_id,
            "query_text": query_text,
            "user_id": user_id,
            "llm_analysis": llm_analysis,
            "search_config": search_config,
            "results_count": 0,  # 初始为0，后续可更新
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # 插入文档
        await collection.insert_one(document)

        logger.info(f"创建 NL 搜索日志成功: ID={log_id}, query='{query_text[:30]}...'")
        return log_id

    async def get_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取搜索日志

        Args:
            log_id: 日志ID（雪花算法ID字符串）

        Returns:
            Optional[Dict]: 日志数据，不存在时返回 None

        Example:
            >>> log = await repo.get_by_id("244879702695698432")
            >>> if log:
            ...     print(log["query_text"])
        """
        collection = await self._get_collection()

        # 查询文档
        document = await collection.find_one({"_id": log_id})

        if not document:
            logger.debug(f"NL 搜索日志不存在: ID={log_id}")
            return None

        return document

    async def update_llm_analysis(
        self,
        log_id: str,
        llm_analysis: Dict[str, Any]
    ) -> bool:
        """更新 LLM 分析结果

        Args:
            log_id: 日志ID
            llm_analysis: 新的 LLM 分析结果

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update_llm_analysis(
            ...     log_id="244879702695698432",
            ...     llm_analysis={"intent": "updated", "confidence": 0.99}
            ... )
        """
        collection = await self._get_collection()

        # 更新文档
        result = await collection.update_one(
            {"_id": log_id},
            {
                "$set": {
                    "llm_analysis": llm_analysis,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        success = result.modified_count > 0
        if success:
            logger.info(f"更新 NL 搜索日志 LLM 分析成功: ID={log_id}")

        return success

    async def update_status(
        self,
        log_id: str,
        status: str,
        results_count: Optional[int] = None
    ) -> bool:
        """更新搜索状态

        Args:
            log_id: 日志ID
            status: 新状态（pending/completed/failed）
            results_count: 结果数量（可选）

        Returns:
            bool: 更新是否成功

        Example:
            >>> await repo.update_status(
            ...     log_id="244879702695698432",
            ...     status="completed",
            ...     results_count=10
            ... )
        """
        collection = await self._get_collection()

        # 准备更新数据
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }

        if results_count is not None:
            update_data["results_count"] = results_count

        # 更新文档
        result = await collection.update_one(
            {"_id": log_id},
            {"$set": update_data}
        )

        success = result.modified_count > 0
        if success:
            logger.info(f"更新 NL 搜索日志状态成功: ID={log_id}, status={status}")

        return success

    async def get_recent(
        self,
        limit: int = 10,
        offset: int = 0,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取最近的搜索日志

        Args:
            limit: 返回数量限制
            offset: 分页偏移量
            user_id: 可选的用户ID过滤

        Returns:
            List[Dict]: 搜索日志列表

        Example:
            >>> logs = await repo.get_recent(limit=10, offset=0)
            >>> for log in logs:
            ...     print(log["query_text"])
        """
        collection = await self._get_collection()

        # 构建查询条件
        query = {}
        if user_id:
            query["user_id"] = user_id

        # 查询文档（按创建时间倒序）
        cursor = collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        logs = await cursor.to_list(length=limit)

        return logs

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """根据关键词搜索日志

        在 query_text 和 llm_analysis.keywords 中搜索关键词。

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            user_id: 可选的用户ID过滤

        Returns:
            List[Dict]: 匹配的搜索日志列表

        Example:
            >>> logs = await repo.search_by_keyword("AI", limit=10)
        """
        collection = await self._get_collection()

        # 构建查询条件（使用 MongoDB 文本搜索或正则）
        query = {
            "$or": [
                {"query_text": {"$regex": keyword, "$options": "i"}},
                {"llm_analysis.keywords": {"$in": [keyword]}}
            ]
        }

        # 添加用户过滤
        if user_id:
            query["user_id"] = user_id

        # 查询文档
        cursor = collection.find(query).sort("created_at", -1).limit(limit)
        logs = await cursor.to_list(length=limit)

        return logs

    async def count_total(self, user_id: Optional[str] = None) -> int:
        """统计总记录数

        Args:
            user_id: 可选的用户ID过滤

        Returns:
            int: 总记录数

        Example:
            >>> total = await repo.count_total()
            >>> print(f"共有 {total} 条搜索记录")
        """
        collection = await self._get_collection()

        # 构建查询条件
        query = {}
        if user_id:
            query["user_id"] = user_id

        # 统计数量
        total = await collection.count_documents(query)
        return total

    async def delete_old_records(self, days: int = 30) -> int:
        """删除旧记录

        Args:
            days: 保留天数，删除超过此天数的记录

        Returns:
            int: 删除的记录数

        Example:
            >>> deleted = await repo.delete_old_records(days=30)
            >>> print(f"删除了 {deleted} 条旧记录")
        """
        collection = await self._get_collection()

        # 计算截止日期
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 删除旧记录
        result = await collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })

        deleted_count = result.deleted_count
        logger.info(f"删除 {deleted_count} 条旧的 NL 搜索日志 (>{days}天)")

        return deleted_count

    async def delete_by_id(self, log_id: str) -> bool:
        """根据 ID 删除记录

        Args:
            log_id: 日志ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete_by_id("244879702695698432")
        """
        collection = await self._get_collection()

        # 删除文档
        result = await collection.delete_one({"_id": log_id})

        success = result.deleted_count > 0
        if success:
            logger.info(f"删除 NL 搜索日志成功: ID={log_id}")

        return success

    async def create_indexes(self):
        """创建索引以优化查询性能

        创建的索引：
        1. created_at (倒序) - 优化最近查询
        2. user_id + created_at - 优化用户查询历史
        3. status - 优化状态过滤
        4. query_text (文本索引) - 优化关键词搜索

        Example:
            >>> await repo.create_indexes()
        """
        collection = await self._get_collection()

        # 1. 创建时间索引（倒序）
        await collection.create_index([("created_at", -1)], name="created_at_desc")

        # 2. 用户 + 创建时间复合索引
        await collection.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="user_created_idx"
        )

        # 3. 状态索引
        await collection.create_index([("status", 1)], name="status_idx")

        # 4. 查询文本索引（文本搜索）
        await collection.create_index([("query_text", "text")], name="query_text_idx")

        logger.info("NL 搜索日志索引创建完成")

    async def update_search_results(
        self,
        log_id: str,
        search_results: List[Dict[str, Any]],
        results_count: int
    ) -> bool:
        """
        更新搜索结果

        将搜索结果保存到搜索日志文档中（内嵌存储）。

        Args:
            log_id: 日志ID
            search_results: 搜索结果列表（字典格式）
            results_count: 结果数量

        Returns:
            bool: 更新是否成功

        Example:
            >>> await repo.update_search_results(
            ...     log_id="244879702695698432",
            ...     search_results=[
            ...         {
            ...             "title": "GPT-5发布",
            ...             "url": "https://example.com/gpt5",
            ...             "snippet": "...",
            ...             "position": 1,
            ...             "score": 0.95,
            ...             "source": "serpapi"
            ...         }
            ...     ],
            ...     results_count=10
            ... )
        """
        collection = await self._get_collection()

        # 更新文档
        result = await collection.update_one(
            {"_id": log_id},
            {
                "$set": {
                    "search_results": search_results,
                    "results_count": results_count,
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        success = result.modified_count > 0
        if success:
            logger.info(f"更新搜索结果成功: log_id={log_id}, count={results_count}")
        else:
            logger.warning(f"更新搜索结果失败: log_id={log_id}")

        return success

    async def get_search_results(
        self,
        log_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取搜索结果

        从搜索日志文档中提取搜索结果数组。

        Args:
            log_id: 日志ID

        Returns:
            Optional[List[Dict]]: 搜索结果列表，不存在时返回 None

        Example:
            >>> results = await repo.get_search_results("244879702695698432")
            >>> if results:
            ...     for r in results:
            ...         print(r["title"], r["url"])
        """
        collection = await self._get_collection()

        # 查询文档，仅返回搜索结果字段
        document = await collection.find_one(
            {"_id": log_id},
            {"search_results": 1, "_id": 0}
        )

        if not document:
            logger.debug(f"搜索记录不存在: log_id={log_id}")
            return None

        # 返回搜索结果数组（如果不存在则返回空列表）
        return document.get("search_results", [])


# 全局实例
mongo_nl_search_repository = MongoNLSearchLogRepository()
