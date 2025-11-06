"""Firecrawl 原始响应仓储层

⚠️ 临时仓储
用途：存储和查询 Firecrawl API 原始响应数据
用完后会删除
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.domain.entities.firecrawl_raw_response import FirecrawlRawResponse
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FirecrawlRawResponseRepository:
    """Firecrawl 原始响应仓储（临时）"""

    def __init__(self):
        """初始化仓储"""
        self.collection_name = "firecrawl_raw_responses"
        self.collection = None

    async def _get_collection(self):
        """获取MongoDB集合"""
        if self.collection is None:
            db = await get_mongodb_database()
            self.collection = db[self.collection_name]
        return self.collection

    async def create(self, response: FirecrawlRawResponse) -> str:
        """创建原始响应记录

        Args:
            response: FirecrawlRawResponse实体

        Returns:
            创建的记录ID
        """
        collection = await self._get_collection()

        doc = response.to_dict()
        result = await collection.insert_one(doc)

        logger.info(f"保存 Firecrawl 原始响应: {response.id} (URL: {response.result_url})")

        return str(result.inserted_id)

    async def batch_create(self, responses: List[FirecrawlRawResponse]) -> int:
        """批量创建原始响应记录

        Args:
            responses: FirecrawlRawResponse实体列表

        Returns:
            创建的记录数量
        """
        if not responses:
            return 0

        collection = await self._get_collection()

        docs = [response.to_dict() for response in responses]
        result = await collection.insert_many(docs)

        count = len(result.inserted_ids)
        logger.info(f"批量保存 {count} 条 Firecrawl 原始响应")

        return count

    async def get_by_id(self, response_id: str) -> Optional[FirecrawlRawResponse]:
        """根据ID获取原始响应

        Args:
            response_id: 响应ID

        Returns:
            FirecrawlRawResponse实体或None
        """
        collection = await self._get_collection()
        doc = await collection.find_one({"id": response_id})

        if not doc:
            return None

        return self._dict_to_entity(doc)

    async def get_by_task_id(
        self,
        task_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[FirecrawlRawResponse]:
        """根据任务ID获取原始响应列表

        Args:
            task_id: 任务ID
            limit: 限制数量
            skip: 跳过数量

        Returns:
            FirecrawlRawResponse实体列表
        """
        collection = await self._get_collection()

        cursor = collection.find({"task_id": task_id}) \
            .sort("created_at", -1) \
            .limit(limit) \
            .skip(skip)

        docs = await cursor.to_list(length=limit)
        return [self._dict_to_entity(doc) for doc in docs]

    async def get_by_url(self, url: str) -> List[FirecrawlRawResponse]:
        """根据URL获取原始响应（可能有多次爬取）

        Args:
            url: 结果URL

        Returns:
            FirecrawlRawResponse实体列表
        """
        collection = await self._get_collection()

        cursor = collection.find({"result_url": url}).sort("created_at", -1)
        docs = await cursor.to_list(length=None)

        return [self._dict_to_entity(doc) for doc in docs]

    async def count_by_task_id(self, task_id: str) -> int:
        """统计任务的原始响应数量

        Args:
            task_id: 任务ID

        Returns:
            数量
        """
        collection = await self._get_collection()
        return await collection.count_documents({"task_id": task_id})

    async def delete_by_task_id(self, task_id: str) -> int:
        """删除任务的所有原始响应

        Args:
            task_id: 任务ID

        Returns:
            删除的数量
        """
        collection = await self._get_collection()
        result = await collection.delete_many({"task_id": task_id})

        logger.info(f"删除任务 {task_id} 的 {result.deleted_count} 条原始响应")

        return result.deleted_count

    async def delete_all(self) -> int:
        """删除所有原始响应（清理临时数据）

        Returns:
            删除的数量
        """
        collection = await self._get_collection()
        result = await collection.delete_many({})

        logger.warning(f"🗑️ 删除所有 Firecrawl 原始响应: {result.deleted_count} 条")

        return result.deleted_count

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计数据字典
        """
        collection = await self._get_collection()

        total_count = await collection.count_documents({})

        # 统计每个任务的响应数量
        pipeline = [
            {"$group": {
                "_id": "$task_id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]

        task_stats = await collection.aggregate(pipeline).to_list(length=10)

        return {
            "total_responses": total_count,
            "top_tasks": task_stats
        }

    def _dict_to_entity(self, doc: Dict[str, Any]) -> FirecrawlRawResponse:
        """将MongoDB文档转换为实体

        Args:
            doc: MongoDB文档

        Returns:
            FirecrawlRawResponse实体
        """
        return FirecrawlRawResponse(
            id=doc.get("id", ""),
            task_id=doc.get("task_id", ""),
            search_execution_id=doc.get("search_execution_id"),
            result_url=doc.get("result_url", ""),
            raw_response=doc.get("raw_response", {}),
            api_endpoint=doc.get("api_endpoint", ""),
            api_version=doc.get("api_version", "v1"),
            response_status_code=doc.get("response_status_code", 200),
            response_time_ms=doc.get("response_time_ms", 0),
            created_at=doc.get("created_at", datetime.utcnow())
        )


# 创建单例实例
_repository_instance: Optional[FirecrawlRawResponseRepository] = None


async def get_firecrawl_raw_repository() -> FirecrawlRawResponseRepository:
    """获取 Firecrawl 原始响应仓储单例

    Returns:
        FirecrawlRawResponseRepository实例
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = FirecrawlRawResponseRepository()
    return _repository_instance
