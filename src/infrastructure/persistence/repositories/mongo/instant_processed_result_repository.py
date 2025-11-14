"""InstantProcessedResult MongoDB Repository 实现

Version: v3.0.0 (模块化架构)

提供即时搜索AI处理结果的MongoDB持久化实现。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.instant_processed_result import (
    InstantProcessedResult,
    InstantProcessedStatus
)
from src.infrastructure.persistence.interfaces import IInstantProcessedResultRepository
from src.infrastructure.persistence.exceptions import RepositoryException
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoInstantProcessedResultRepository(IInstantProcessedResultRepository):
    """InstantProcessedResult MongoDB Repository 实现

    集合名称: instant_processed_results

    核心功能：
    - AI处理结果的生命周期管理
    - 状态流转（pending → processing → completed/failed）
    - 按任务和类型查询（支持即时和智能搜索）
    - 用户操作管理（留存、删除、评分、备注）
    - 统计分析和失败重试
    """

    COLLECTION_NAME = "instant_processed_results"

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """初始化Repository

        Args:
            db: MongoDB数据库实例，如果为None则自动获取
        """
        self._db = db
        self.collection_name = self.COLLECTION_NAME

    async def _get_collection(self):
        """获取集合"""
        if self._db is None:
            from src.infrastructure.database.connection import get_mongodb_database
            self._db = await get_mongodb_database()
        return self._db[self.collection_name]

    # ==================== 创建和初始化 ====================

    async def create_pending_result(
        self,
        raw_result_id: str,
        task_id: str,
        search_type: str = "instant"
    ) -> InstantProcessedResult:
        """创建待处理的结果记录"""
        try:
            result = InstantProcessedResult.create_pending(
                raw_result_id=raw_result_id,
                task_id=task_id,
                search_type=search_type
            )

            doc = result.to_dict()
            doc["_id"] = doc["id"]

            await (await self._get_collection()).insert_one(doc)

            logger.info(
                f"创建待处理结果: result_id={result.id}, "
                f"task_id={task_id}, search_type={search_type}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ 创建待处理结果失败: {str(e)}")
            raise RepositoryException(f"创建待处理结果失败: {e}")

    async def bulk_create_pending_results(
        self,
        raw_result_ids: List[str],
        task_id: str,
        search_type: str = "instant"
    ) -> List[InstantProcessedResult]:
        """批量创建待处理结果"""
        if not raw_result_ids:
            logger.warning("批量创建待处理结果: raw_result_ids为空")
            return []

        try:
            results = []
            documents = []

            for raw_result_id in raw_result_ids:
                result = InstantProcessedResult.create_pending(
                    raw_result_id=raw_result_id,
                    task_id=task_id,
                    search_type=search_type
                )
                results.append(result)

                doc = result.to_dict()
                doc["_id"] = doc["id"]
                documents.append(doc)

            await (await self._get_collection()).insert_many(documents)

            logger.info(
                f"批量创建待处理结果成功: task_id={task_id}, "
                f"数量={len(results)}, search_type={search_type}"
            )
            return results

        except Exception as e:
            logger.error(f"❌ 批量创建待处理结果失败: {str(e)}")
            raise RepositoryException(f"批量创建待处理结果失败: {e}")

    # ==================== 状态管理 ====================

    async def update_processing_status(
        self,
        result_id: str,
        status: InstantProcessedStatus,
        **kwargs
    ) -> bool:
        """更新处理状态"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }

            # 自动设置processed_at
            if status == InstantProcessedStatus.COMPLETED:
                update_data["processed_at"] = datetime.utcnow()

            # 添加其他字段
            for key, value in kwargs.items():
                if value is not None:
                    update_data[key] = value

            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"更新处理状态: result_id={result_id}, status={status.value}")

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新处理状态失败: {result_id}, 错误: {e}")
            raise RepositoryException(f"更新处理状态失败: {e}")

    async def save_ai_result(
        self,
        result_id: str,
        translated_title: Optional[str] = None,
        translated_content: Optional[str] = None,
        summary: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        sentiment: Optional[str] = None,
        categories: Optional[List[str]] = None,
        ai_model: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        ai_confidence_score: Optional[float] = None
    ) -> bool:
        """保存AI处理结果"""
        try:
            update_data = {
                "status": InstantProcessedStatus.COMPLETED.value,
                "processed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # 只更新非None的字段
            if translated_title is not None:
                update_data["translated_title"] = translated_title
            if translated_content is not None:
                update_data["translated_content"] = translated_content
            if summary is not None:
                update_data["summary"] = summary
            if key_points is not None:
                update_data["key_points"] = key_points
            if sentiment is not None:
                update_data["sentiment"] = sentiment
            if categories is not None:
                update_data["categories"] = categories
            if ai_model is not None:
                update_data["ai_model"] = ai_model
            if processing_time_ms is not None:
                update_data["processing_time_ms"] = processing_time_ms
            if ai_confidence_score is not None:
                update_data["ai_confidence_score"] = ai_confidence_score

            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"保存AI结果: result_id={result_id}")

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 保存AI结果失败: {result_id}, 错误: {e}")
            raise RepositoryException(f"保存AI结果失败: {e}")

    # ==================== 查询方法 ====================

    async def get_by_id(self, result_id: str) -> Optional[InstantProcessedResult]:
        """根据ID获取处理结果"""
        try:
            doc = await (await self._get_collection()).find_one({"_id": result_id})
            return InstantProcessedResult.from_dict(doc) if doc else None

        except Exception as e:
            logger.error(f"❌ 获取处理结果失败: {result_id}, 错误: {e}")
            raise RepositoryException(f"获取处理结果失败: {e}")

    async def get_by_raw_result_id(self, raw_result_id: str) -> Optional[InstantProcessedResult]:
        """根据原始结果ID获取处理结果"""
        try:
            doc = await (await self._get_collection()).find_one({"raw_result_id": raw_result_id})
            return InstantProcessedResult.from_dict(doc) if doc else None

        except Exception as e:
            logger.error(f"❌ 根据原始结果ID获取失败: {raw_result_id}, 错误: {e}")
            raise RepositoryException(f"根据原始结果ID获取失败: {e}")

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[InstantProcessedStatus] = None,
        search_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InstantProcessedResult], int]:
        """获取任务的处理结果（支持状态筛选和分页）"""
        try:
            query = {"task_id": task_id}

            if status is not None:
                query["status"] = status.value

            if search_type is not None:
                query["search_type"] = search_type

            collection = await self._get_collection()

            # 总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(query).sort(
                "created_at", -1
            ).skip(skip).limit(page_size)

            results = []
            async for doc in cursor:
                results.append(InstantProcessedResult.from_dict(doc))

            return results, total

        except Exception as e:
            logger.error(f"❌ 获取任务处理结果失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"获取任务处理结果失败: {e}")

    async def get_by_task_and_type(
        self,
        task_id: str,
        search_type: str,
        status: Optional[InstantProcessedStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InstantProcessedResult], int]:
        """根据任务ID和搜索类型获取处理结果（v2.1.0 统一架构专用）"""
        return await self.get_by_task(
            task_id=task_id,
            status=status,
            search_type=search_type,
            page=page,
            page_size=page_size
        )

    # ==================== 用户操作 ====================

    async def update_user_action(
        self,
        result_id: str,
        status: Optional[InstantProcessedStatus] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """更新用户操作（留存、删除、评分、备注）"""
        try:
            # 验证user_rating
            if user_rating is not None and not (1 <= user_rating <= 5):
                raise ValueError("user_rating must be between 1 and 5")

            update_data = {"updated_at": datetime.utcnow()}

            if status is not None:
                update_data["status"] = status.value
            if user_rating is not None:
                update_data["user_rating"] = user_rating
            if user_notes is not None:
                update_data["user_notes"] = user_notes

            result = await (await self._get_collection()).update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"更新用户操作: result_id={result_id}")

            return result.modified_count > 0

        except ValueError as e:
            logger.error(f"❌ 用户操作验证失败: {str(e)}")
            raise RepositoryException(f"用户操作验证失败: {e}")
        except Exception as e:
            logger.error(f"❌ 更新用户操作失败: {result_id}, 错误: {e}")
            raise RepositoryException(f"更新用户操作失败: {e}")

    # ==================== 统计和分析 ====================

    async def get_status_statistics(
        self,
        task_id: str,
        search_type: Optional[str] = None
    ) -> Dict[str, int]:
        """获取任务的状态统计"""
        try:
            query = {"task_id": task_id}
            if search_type is not None:
                query["search_type"] = search_type

            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]

            # 初始化所有状态为0
            status_counts = {status.value: 0 for status in InstantProcessedStatus}

            async for doc in (await self._get_collection()).aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]

            return status_counts

        except Exception as e:
            logger.error(f"❌ 获取状态统计失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"获取状态统计失败: {e}")

    async def get_failed_results(self, max_retry: int = 3) -> List[InstantProcessedResult]:
        """获取失败的结果（用于重试）"""
        try:
            query = {
                "status": InstantProcessedStatus.FAILED.value,
                "retry_count": {"$lt": max_retry}
            }

            cursor = (await self._get_collection()).find(query).sort("updated_at", 1)

            results = []
            async for doc in cursor:
                results.append(InstantProcessedResult.from_dict(doc))

            return results

        except Exception as e:
            logger.error(f"❌ 获取失败结果失败: 错误: {e}")
            raise RepositoryException(f"获取失败结果失败: {e}")

    # ==================== 批量操作 ====================

    async def delete_by_task(self, task_id: str) -> int:
        """删除任务的所有处理结果"""
        try:
            result = await (await self._get_collection()).delete_many(
                {"task_id": task_id}
            )

            logger.info(
                f"删除任务处理结果: task_id={task_id}, "
                f"删除数量={result.deleted_count}"
            )
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务处理结果失败: {task_id}, 错误: {e}")
            raise RepositoryException(f"删除任务处理结果失败: {e}")
