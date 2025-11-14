"""FirecrawlRawResponse MongoDB Repository 实现

Version: v3.0.0 (模块化架构)

⚠️ 临时仓储实现
提供Firecrawl API原始响应的MongoDB持久化。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.firecrawl_raw_response import FirecrawlRawResponse
from src.infrastructure.persistence.interfaces import IFirecrawlRawResponseRepository
from src.infrastructure.persistence.exceptions import RepositoryException
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoFirecrawlRawResponseRepository(IFirecrawlRawResponseRepository):
    """FirecrawlRawResponse MongoDB Repository 实现

    集合名称: firecrawl_raw_responses

    核心功能：
    - 原始响应的创建和批量创建
    - 按任务ID、URL查询响应
    - 统计响应数量和任务分布
    - 按任务删除和全量清理
    - 临时数据管理
    """

    COLLECTION_NAME = "firecrawl_raw_responses"

    def __init__(self, db: AsyncIOMotorDatabase):
        """初始化Repository

        Args:
            db: MongoDB数据库实例
        """
        self.db = db
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entity: FirecrawlRawResponse) -> str:
        """创建原始响应记录"""
        try:
            doc = entity.to_dict()
            result = await self.collection.insert_one(doc)
            logger.info(
                f"保存 Firecrawl 原始响应: {entity.id} (URL: {entity.result_url})"
            )
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"❌ 创建原始响应失败: {entity.id}, 错误: {e}")
            raise RepositoryException(f"创建原始响应失败: {e}")

    async def batch_create(self, entities: List[FirecrawlRawResponse]) -> int:
        """批量创建原始响应记录"""
        if not entities:
            return 0

        try:
            docs = [entity.to_dict() for entity in entities]
            result = await self.collection.insert_many(docs)
            count = len(result.inserted_ids)
            logger.info(f"批量保存 {count} 条 Firecrawl 原始响应")
            return count
        except Exception as e:
            logger.error(f"❌ 批量创建原始响应失败, 错误: {e}")
            raise RepositoryException(f"批量创建原始响应失败: {e}")

    async def get_by_id(self, response_id: str) -> Optional[FirecrawlRawResponse]:
        """根据ID获取原始响应"""
        try:
            doc = await self.collection.find_one({"id": response_id})
            return self._dict_to_entity(doc) if doc else None
        except Exception as e:
            logger.error(f"❌ 查询原始响应失败: {response_id}, 错误: {e}")
            raise RepositoryException(f"查询原始响应失败: {e}")

    async def get_by_task_id(
        self,
        task_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[FirecrawlRawResponse]:
        """根据任务ID获取原始响应列表"""
        try:
            cursor = self.collection.find({"task_id": task_id}) \
                .sort("created_at", -1) \
                .limit(limit) \
                .skip(skip)

            docs = await cursor.to_list(length=limit)
            return [self._dict_to_entity(doc) for doc in docs]
        except Exception as e:
            logger.error(f"❌ 按任务查询原始响应失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"按任务查询原始响应失败: {e}")

    async def get_by_url(self, url: str) -> List[FirecrawlRawResponse]:
        """根据URL获取原始响应（可能有多次爬取）"""
        try:
            cursor = self.collection.find({"result_url": url}).sort("created_at", -1)
            docs = await cursor.to_list(length=None)
            return [self._dict_to_entity(doc) for doc in docs]
        except Exception as e:
            logger.error(f"❌ 按URL查询原始响应失败: {url}, 错误: {e}")
            raise RepositoryException(f"按URL查询原始响应失败: {e}")

    async def count_by_task_id(self, task_id: str) -> int:
        """统计任务的原始响应数量"""
        try:
            return await self.collection.count_documents({"task_id": task_id})
        except Exception as e:
            logger.error(f"❌ 统计原始响应数量失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"统计原始响应数量失败: {e}")

    async def delete_by_task_id(self, task_id: str) -> int:
        """删除任务的所有原始响应"""
        try:
            result = await self.collection.delete_many({"task_id": task_id})
            logger.info(f"删除任务 {task_id} 的 {result.deleted_count} 条原始响应")
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ 删除原始响应失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"删除原始响应失败: {e}")

    async def delete_all(self) -> int:
        """删除所有原始响应（清理临时数据）"""
        try:
            result = await self.collection.delete_many({})
            logger.warning(
                f"🗑️ 删除所有 Firecrawl 原始响应: {result.deleted_count} 条"
            )
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ 删除所有原始响应失败, 错误: {e}")
            raise RepositoryException(f"删除所有原始响应失败: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            total_count = await self.collection.count_documents({})

            # 统计每个任务的响应数量
            pipeline = [
                {"$group": {
                    "_id": "$task_id",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]

            task_stats = await self.collection.aggregate(pipeline).to_list(length=10)

            return {
                "total_responses": total_count,
                "top_tasks": task_stats
            }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败, 错误: {e}")
            raise RepositoryException(f"获取统计信息失败: {e}")

    def _dict_to_entity(self, doc: Dict[str, Any]) -> FirecrawlRawResponse:
        """将MongoDB文档转换为实体"""
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
