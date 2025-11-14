"""
MongoDB AI处理结果 Repository 实现

基于 MongoDB 的 AI 处理结果数据访问实现，实现 IProcessedResultRepository 接口。

Version: v3.0.0 (模块化架构)
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.infrastructure.persistence.interfaces import IProcessedResultRepository
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoProcessedResultRepository(IProcessedResultRepository):
    """
    MongoDB AI处理结果 Repository 实现

    使用 MongoDB 作为数据存储，实现 IProcessedResultRepository 接口。
    集合名: news_results
    """

    def __init__(self):
        self.collection_name = "news_results"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: ProcessedResult) -> Dict[str, Any]:
        """将 ProcessedResult 实体转换为 MongoDB 文档（v2.0.1 扩展）"""
        return {
            "_id": str(result.id),
            "raw_result_id": str(result.raw_result_id),
            "task_id": str(result.task_id),
            # 原始字段（v2.0.1 新增）
            "title": result.title,
            "url": result.url,
            "source_url": result.source_url,
            "content": result.content,
            "snippet": result.snippet,
            "markdown_content": result.markdown_content,
            "html_content": result.html_content,
            "author": result.author,
            "published_date": result.published_date,
            "language": result.language,
            "source": result.source,
            "metadata": result.metadata,
            "quality_score": result.quality_score,
            "relevance_score": result.relevance_score,
            "search_position": result.search_position,
            # AI 处理数据
            "content_zh": result.content_zh,
            "title_generated": result.title_generated,
            "translated_title": result.translated_title,
            "translated_content": result.translated_content,
            "summary": result.summary,
            "key_points": result.key_points,
            "cls_results": result.cls_results,
            "sentiment": result.sentiment,
            "categories": result.categories,
            "html_ctx_llm": result.html_ctx_llm,
            "html_ctx_regex": result.html_ctx_regex,
            "article_published_time": result.article_published_time,
            "article_tag": result.article_tag,
            # AI 元数据
            "ai_model": result.ai_model,
            "ai_processing_time_ms": result.ai_processing_time_ms,
            "ai_confidence_score": result.ai_confidence_score,
            "ai_metadata": result.ai_metadata,
            "processing_status": result.processing_status,
            "http_status_code": result.http_status_code,
            "is_test_data": result.is_test_data,
            # 用户操作
            "status": result.status.value,
            "user_rating": result.user_rating,
            "user_notes": result.user_notes,
            # 时间戳
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "updated_at": result.updated_at,
            # 错误处理
            "processing_error": result.processing_error,
            "retry_count": result.retry_count,
            # news_results 嵌套字段（v2.0.2）
            "news_results": result.news_results,
            # 内容清理字段（v2.0.2）
            "content_cleaned": result.content_cleaned
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> ProcessedResult:
        """将 MongoDB 文档转换为 ProcessedResult 实体（v2.0.1 扩展）"""
        # 安全地解析 status 字段，防止数据损坏导致的错误
        status_value = data.get("status", "pending")
        try:
            status = ProcessedStatus(status_value)
        except ValueError:
            # 如果 status 值无效，记录错误并使用默认值
            logger.error(
                f"⚠️  数据损坏：无效的 status 值 '{status_value}' (文档ID: {data.get('_id')}), "
                f"已重置为 'pending'"
            )
            status = ProcessedStatus.PENDING

        return ProcessedResult(
            id=str(data.get("_id", "")),
            raw_result_id=str(data.get("raw_result_id", "")),
            task_id=str(data.get("task_id", "")),
            # 原始字段（v2.0.1 新增）
            title=data.get("title", ""),
            url=data.get("url", ""),
            source_url=data.get("source_url", ""),
            content=data.get("content", ""),
            snippet=data.get("snippet"),
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            author=data.get("author"),
            published_date=data.get("published_date"),
            language=data.get("language"),
            source=data.get("source", "web"),
            metadata=data.get("metadata", {}),
            quality_score=data.get("quality_score", 0.0),
            relevance_score=data.get("relevance_score", 0.0),
            search_position=data.get("search_position", 0),
            # AI 处理数据
            content_zh=data.get("content_zh"),
            title_generated=data.get("title_generated"),
            translated_title=data.get("translated_title"),
            translated_content=data.get("translated_content"),
            summary=data.get("summary"),
            key_points=data.get("key_points", []),
            cls_results=data.get("cls_results"),
            sentiment=data.get("sentiment"),
            categories=data.get("categories", []),
            html_ctx_llm=data.get("html_ctx_llm"),
            html_ctx_regex=data.get("html_ctx_regex"),
            article_published_time=data.get("article_published_time"),
            article_tag=data.get("article_tag"),
            # AI 元数据
            ai_model=data.get("ai_model"),
            ai_processing_time_ms=data.get("ai_processing_time_ms", 0),
            ai_confidence_score=data.get("ai_confidence_score", 0.0),
            ai_metadata=data.get("ai_metadata", {}),
            processing_status=data.get("processing_status", "pending"),
            http_status_code=data.get("http_status_code"),
            is_test_data=data.get("is_test_data", False),
            # 用户操作
            status=status,
            user_rating=data.get("user_rating"),
            user_notes=data.get("user_notes"),
            # 时间戳
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            updated_at=data.get("updated_at", datetime.utcnow()),
            # 错误处理
            processing_error=data.get("processing_error"),
            retry_count=data.get("retry_count", 0),
            # news_results 嵌套字段（v2.0.2）
            news_results=data.get("news_results"),
            # 内容清理字段（v2.0.2）
            content_cleaned=data.get("content_cleaned")
        )

    # ==================== IBasicRepository 实现 ====================

    async def create(self, entity: ProcessedResult) -> str:
        """创建 AI 处理结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)

            await collection.insert_one(result_dict)
            logger.info(f"✅ 创建 AI 处理结果: {entity.title[:50]} (ID: {entity.id})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建 AI 处理结果失败: {e}")
            raise RepositoryException(f"创建 AI 处理结果失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[ProcessedResult]:
        """根据 ID 获取 AI 处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取 AI 处理结果失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取 AI 处理结果失败: {e}", e)

    async def update(self, entity: ProcessedResult) -> bool:
        """更新 AI 处理结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)
            result_dict.pop("_id")  # 移除 ID 字段

            result = await collection.update_one(
                {"_id": str(entity.id)},
                {"$set": result_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"AI 处理结果不存在: {entity.id}")

            logger.info(f"✅ 更新 AI 处理结果: {entity.title[:50]} (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新 AI 处理结果失败: {e}")
            raise RepositoryException(f"更新 AI 处理结果失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除 AI 处理结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除 AI 处理结果: {id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 删除 AI 处理结果失败: {e}")
            raise RepositoryException(f"删除 AI 处理结果失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查 AI 处理结果是否存在"""
        try:
            collection = await self._get_collection()
            count = await collection.count_documents({"_id": id}, limit=1)
            return count > 0

        except Exception as e:
            logger.error(f"❌ 检查 AI 处理结果存在性失败: {e}")
            raise RepositoryException(f"检查 AI 处理结果存在性失败: {e}", e)

    # ==================== IQueryableRepository 实现 ====================

    async def find_all(self, limit: Optional[int] = None) -> List[ProcessedResult]:
        """获取所有 AI 处理结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({}).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 获取所有 AI 处理结果失败: {e}")
            raise RepositoryException(f"获取所有 AI 处理结果失败: {e}", e)

    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[ProcessedResult]:
        """根据条件查询 AI 处理结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 条件查询 AI 处理结果失败: {e}")
            raise RepositoryException(f"条件查询 AI 处理结果失败: {e}", e)

    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """统计 AI 处理结果数量"""
        try:
            collection = await self._get_collection()
            query = criteria if criteria else {}
            return await collection.count_documents(query)

        except Exception as e:
            logger.error(f"❌ 统计 AI 处理结果数量失败: {e}")
            raise RepositoryException(f"统计 AI 处理结果数量失败: {e}", e)

    # ==================== IPaginatableRepository 实现 ====================

    async def find_with_pagination(
        self,
        page: int,
        page_size: int,
        criteria: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> Tuple[List[ProcessedResult], int]:
        """分页查询 AI 处理结果"""
        if page < 1:
            raise ValueError("页码必须大于等于1")
        if page_size < 1:
            raise ValueError("页大小必须大于等于1")

        try:
            collection = await self._get_collection()
            query = criteria if criteria else {}

            # 统计总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            sort_field = sort_by if sort_by else "created_at"
            sort_direction = -1 if sort_order == "desc" else 1

            cursor = collection.find(query).sort(sort_field, sort_direction).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results, total

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ 分页查询 AI 处理结果失败: {e}")
            raise RepositoryException(f"分页查询 AI 处理结果失败: {e}", e)

    # ==================== IBulkOperationRepository 实现 ====================

    async def bulk_create(self, entities: List[ProcessedResult]) -> List[str]:
        """批量创建 AI 处理结果"""
        if not entities:
            return []

        try:
            collection = await self._get_collection()
            result_dicts = [self._result_to_dict(entity) for entity in entities]

            result = await collection.insert_many(result_dicts)
            logger.info(f"✅ 批量创建 AI 处理结果: {len(result.inserted_ids)} 条")

            return [str(id) for id in result.inserted_ids]

        except Exception as e:
            logger.error(f"❌ 批量创建 AI 处理结果失败: {e}")
            raise RepositoryException(f"批量创建 AI 处理结果失败: {e}", e)

    async def bulk_update(self, entities: List[ProcessedResult]) -> int:
        """批量更新 AI 处理结果"""
        if not entities:
            return 0

        try:
            collection = await self._get_collection()
            updated_count = 0

            for entity in entities:
                result_dict = self._result_to_dict(entity)
                result_dict.pop("_id")

                result = await collection.update_one(
                    {"_id": str(entity.id)},
                    {"$set": result_dict}
                )
                updated_count += result.modified_count

            logger.info(f"✅ 批量更新 AI 处理结果: {updated_count} 条")
            return updated_count

        except Exception as e:
            logger.error(f"❌ 批量更新 AI 处理结果失败: {e}")
            raise RepositoryException(f"批量更新 AI 处理结果失败: {e}", e)

    async def bulk_delete(self, ids: List[str]) -> int:
        """批量删除 AI 处理结果"""
        if not ids:
            return 0

        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"_id": {"$in": ids}})

            logger.info(f"✅ 批量删除 AI 处理结果: {result.deleted_count} 条")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 批量删除 AI 处理结果失败: {e}")
            raise RepositoryException(f"批量删除 AI 处理结果失败: {e}", e)

    # ==================== IProcessedResultRepository 特定方法 ====================

    async def find_by_task_id(
        self,
        task_id: str,
        status: Optional[ProcessedStatus] = None,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """根据任务 ID 查询 AI 处理结果"""
        try:
            criteria = {"task_id": task_id}
            if status is not None:
                criteria["status"] = status.value

            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按任务 ID 查询 AI 处理结果失败: {e}")
            raise RepositoryException(f"按任务 ID 查询 AI 处理结果失败: {e}", e)

    async def find_by_raw_result_id(
        self,
        raw_result_id: str
    ) -> Optional[ProcessedResult]:
        """根据原始结果 ID 查询 AI 处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"raw_result_id": raw_result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 根据原始结果 ID 获取 AI 处理结果失败: {e}")
            raise RepositoryException(f"根据原始结果 ID 获取 AI 处理结果失败: {e}", e)

    async def find_by_status(
        self,
        status: ProcessedStatus,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """根据状态查询 AI 处理结果"""
        try:
            criteria = {"status": status.value}
            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按状态查询 AI 处理结果失败: {e}")
            raise RepositoryException(f"按状态查询 AI 处理结果失败: {e}", e)

    async def find_pending_results(
        self,
        limit: Optional[int] = None
    ) -> List[ProcessedResult]:
        """查询待处理的结果"""
        try:
            return await self.find_by_status(ProcessedStatus.PENDING, limit)

        except Exception as e:
            logger.error(f"❌ 查询待处理结果失败: {e}")
            raise RepositoryException(f"查询待处理结果失败: {e}", e)

    async def update_processing_status(
        self,
        result_id: str,
        status: ProcessedStatus,
        **kwargs
    ) -> bool:
        """更新处理状态"""
        try:
            collection = await self._get_collection()

            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }

            # 合并额外字段
            update_data.update(kwargs)

            # 特殊处理：COMPLETED 状态设置处理完成时间
            if status == ProcessedStatus.COMPLETED and "processed_at" not in kwargs:
                update_data["processed_at"] = datetime.utcnow()

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                logger.warning(f"⚠️  处理状态未更新（记录不存在）: {result_id}")
                return False

            logger.info(f"✅ 更新处理状态: {result_id} -> {status.value}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新处理状态失败: {e}")
            raise RepositoryException(f"更新处理状态失败: {e}", e)

    async def save_ai_result(
        self,
        result_id: str,
        ai_data: Dict[str, Any]
    ) -> bool:
        """保存 AI 处理结果"""
        try:
            collection = await self._get_collection()

            update_data = {
                "status": ProcessedStatus.COMPLETED.value,
                "processed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # 合并 AI 数据
            update_data.update(ai_data)

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                logger.warning(f"⚠️  AI 结果未保存（记录不存在）: {result_id}")
                return False

            logger.info(f"✅ 保存 AI 处理结果: {result_id}")
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 保存 AI 处理结果失败: {e}")
            raise RepositoryException(f"保存 AI 处理结果失败: {e}", e)

    async def update_user_action(
        self,
        result_id: str,
        status: Optional[ProcessedStatus] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """更新用户操作"""
        try:
            collection = await self._get_collection()

            update_data = {"updated_at": datetime.utcnow()}

            if status is not None:
                update_data["status"] = status.value
            if user_rating is not None:
                if not 1 <= user_rating <= 5:
                    raise ValueError("用户评分必须在 1-5 之间")
                update_data["user_rating"] = user_rating
            if user_notes is not None:
                update_data["user_notes"] = user_notes

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                logger.warning(f"⚠️  用户操作未更新（记录不存在）: {result_id}")
                return False

            logger.info(f"✅ 更新用户操作: {result_id}")
            return result.modified_count > 0

        except ValueError as e:
            logger.error(f"❌ 用户操作参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 更新用户操作失败: {e}")
            raise RepositoryException(f"更新用户操作失败: {e}", e)

    async def get_processing_statistics(
        self,
        task_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取处理统计信息"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            match_criteria = {}
            if task_id:
                match_criteria["task_id"] = task_id
            if start_date:
                match_criteria["created_at"] = {"$gte": start_date}
            if end_date:
                if "created_at" in match_criteria:
                    match_criteria["created_at"]["$lte"] = end_date
                else:
                    match_criteria["created_at"] = {"$lte": end_date}

            # 聚合统计
            pipeline = [
                {"$match": match_criteria},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_processing_time": {"$avg": "$ai_processing_time_ms"}
                }}
            ]

            status_stats = {status.value: 0 for status in ProcessedStatus}
            total = 0
            total_processing_time = 0

            async for doc in collection.aggregate(pipeline):
                status_stats[doc["_id"]] = doc["count"]
                total += doc["count"]
                if doc.get("avg_processing_time"):
                    total_processing_time += doc["avg_processing_time"]

            # 计算成功率
            completed = status_stats.get(ProcessedStatus.COMPLETED.value, 0)
            failed = status_stats.get(ProcessedStatus.FAILED.value, 0)
            success_rate = (completed / (completed + failed)) * 100 if (completed + failed) > 0 else 0.0

            return {
                "total": total,
                "pending": status_stats.get(ProcessedStatus.PENDING.value, 0),
                "processing": status_stats.get(ProcessedStatus.PROCESSING.value, 0),
                "completed": completed,
                "failed": failed,
                "archived": status_stats.get(ProcessedStatus.ARCHIVED.value, 0),
                "deleted": status_stats.get(ProcessedStatus.DELETED.value, 0),
                "avg_processing_time_ms": total_processing_time / len([s for s in status_stats.values() if s > 0]) if total > 0 else 0,
                "success_rate": round(success_rate, 2)
            }

        except Exception as e:
            logger.error(f"❌ 获取处理统计信息失败: {e}")
            raise RepositoryException(f"获取处理统计信息失败: {e}", e)

    async def find_with_pagination_and_filters(
        self,
        task_id: Optional[str] = None,
        status: Optional[ProcessedStatus] = None,
        categories: Optional[List[str]] = None,
        min_rating: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[ProcessedResult], int]:
        """分页查询 AI 处理结果（带多维度过滤）"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            criteria = {}

            if task_id:
                criteria["task_id"] = task_id
            if status:
                criteria["status"] = status.value
            if categories:
                criteria["categories"] = {"$in": categories}
            if min_rating:
                criteria["user_rating"] = {"$gte": min_rating}
            if start_date:
                criteria["created_at"] = {"$gte": start_date}
            if end_date:
                if "created_at" in criteria:
                    criteria["created_at"]["$lte"] = end_date
                else:
                    criteria["created_at"] = {"$lte": end_date}

            # 使用分页查询方法
            return await self.find_with_pagination(
                page=page,
                page_size=page_size,
                criteria=criteria,
                sort_by=sort_by,
                sort_order=sort_order
            )

        except Exception as e:
            logger.error(f"❌ 分页查询 AI 处理结果（带过滤）失败: {e}")
            raise RepositoryException(f"分页查询 AI 处理结果（带过滤）失败: {e}", e)

    # ==================== 额外的业务方法 (向后兼容) ====================

    async def create_pending_result(self, raw_result_id: str, task_id: str) -> ProcessedResult:
        """
        创建待处理的结果记录（v2.0.1 复制原始字段）

        从 search_results 获取原始数据并复制到 processed_results，
        避免前端查询时需要 JOIN 操作。
        """
        try:
            collection = await self._get_collection()

            # 1. 从 search_results 查询原始数据
            db = await get_mongodb_database()
            search_results_collection = db['search_results']
            raw_data = await search_results_collection.find_one({"_id": raw_result_id})

            # 2. 创建待处理结果实体，复制原始字段
            if raw_data:
                result = ProcessedResult(
                    raw_result_id=raw_result_id,
                    task_id=task_id,
                    status=ProcessedStatus.PENDING,
                    # 复制原始字段（v2.0.1）
                    title=raw_data.get("title", ""),
                    url=raw_data.get("url", ""),
                    source_url=raw_data.get("source_url", ""),
                    content=raw_data.get("content", ""),
                    snippet=raw_data.get("snippet"),
                    markdown_content=raw_data.get("markdown_content"),
                    html_content=raw_data.get("html_content"),
                    author=raw_data.get("author"),
                    published_date=raw_data.get("published_date"),
                    language=raw_data.get("language"),
                    source=raw_data.get("source", "web"),
                    metadata=raw_data.get("metadata", {}),
                    quality_score=raw_data.get("quality_score", 0.0),
                    relevance_score=raw_data.get("relevance_score", 0.0),
                    search_position=raw_data.get("search_position", 0)
                )
            else:
                # 如果找不到原始数据，创建最小记录
                logger.warning(f"⚠️ 未找到原始结果数据: {raw_result_id}")
                result = ProcessedResult(
                    raw_result_id=raw_result_id,
                    task_id=task_id,
                    status=ProcessedStatus.PENDING
                )

            # 3. 保存到数据库
            result_dict = self._result_to_dict(result)
            await collection.insert_one(result_dict)

            logger.info(f"✅ 创建待处理结果: raw_result_id={raw_result_id}, processed_id={result.id}")
            return result

        except Exception as e:
            logger.error(f"❌ 创建待处理结果失败: {e}")
            raise RepositoryException(f"创建待处理结果失败: {e}", e)

    async def bulk_create_pending_results(
        self,
        raw_result_ids: List[str],
        task_id: str
    ) -> List[ProcessedResult]:
        """
        批量创建待处理结果（v2.0.1 复制原始字段）
        """
        try:
            collection = await self._get_collection()

            # 1. 从 search_results 查询原始数据
            db = await get_mongodb_database()
            search_results_collection = db['search_results']

            # 批量查询原始结果
            search_results_cursor = search_results_collection.find({
                "_id": {"$in": raw_result_ids}
            })

            # 构建 ID -> 原始结果的映射
            search_results_map = {}
            async for raw_data in search_results_cursor:
                search_results_map[str(raw_data["_id"])] = raw_data

            # 2. 创建所有待处理结果实体，复制原始字段
            results = []
            for raw_id in raw_result_ids:
                raw_data = search_results_map.get(raw_id)

                if raw_data:
                    # 复制原始字段到 ProcessedResult
                    result = ProcessedResult(
                        raw_result_id=raw_id,
                        task_id=task_id,
                        status=ProcessedStatus.PENDING,
                        # 复制原始字段（v2.0.1）
                        title=raw_data.get("title", ""),
                        url=raw_data.get("url", ""),
                        source_url=raw_data.get("source_url", ""),
                        content=raw_data.get("content", ""),
                        snippet=raw_data.get("snippet"),
                        markdown_content=raw_data.get("markdown_content"),
                        html_content=raw_data.get("html_content"),
                        author=raw_data.get("author"),
                        published_date=raw_data.get("published_date"),
                        language=raw_data.get("language"),
                        source=raw_data.get("source", "web"),
                        metadata=raw_data.get("metadata", {}),
                        quality_score=raw_data.get("quality_score", 0.0),
                        relevance_score=raw_data.get("relevance_score", 0.0),
                        search_position=raw_data.get("search_position", 0)
                    )
                else:
                    # 如果找不到原始数据，创建最小记录
                    logger.warning(f"⚠️ 未找到原始结果数据: {raw_id}")
                    result = ProcessedResult(
                        raw_result_id=raw_id,
                        task_id=task_id,
                        status=ProcessedStatus.PENDING
                    )

                results.append(result)

            # 3. 批量插入
            if results:
                result_dicts = [self._result_to_dict(r) for r in results]
                await collection.insert_many(result_dicts)
                logger.info(f"✅ 批量创建待处理结果: {len(results)}条（已复制原始字段）")

            return results

        except Exception as e:
            logger.error(f"❌ 批量创建待处理结果失败: {e}")
            raise RepositoryException(f"批量创建待处理结果失败: {e}", e)

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[ProcessedStatus] = None,
        processing_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[ProcessedResult], int]:
        """获取任务的处理结果（支持状态筛选和分页）"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            query = {"task_id": task_id}
            if status is not None:
                query["status"] = status.value
            if processing_status is not None:
                query["processing_status"] = processing_status

            # 总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results, total

        except Exception as e:
            logger.error(f"❌ 获取任务处理结果失败: {e}")
            raise RepositoryException(f"获取任务处理结果失败: {e}", e)

    async def get_status_statistics(self, task_id: str) -> Dict[str, int]:
        """获取任务的状态统计"""
        try:
            collection = await self._get_collection()

            pipeline = [
                {"$match": {"task_id": task_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]

            status_counts = {status.value: 0 for status in ProcessedStatus}

            async for doc in collection.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]

            return status_counts

        except Exception as e:
            logger.error(f"❌ 获取状态统计失败: {e}")
            raise RepositoryException(f"获取状态统计失败: {e}", e)

    async def get_failed_results(self, max_retry: int = 3) -> List[ProcessedResult]:
        """获取失败的结果（用于重试）"""
        try:
            collection = await self._get_collection()

            cursor = collection.find({
                "status": ProcessedStatus.FAILED.value,
                "retry_count": {"$lt": max_retry}
            }).sort("updated_at", 1)  # 按更新时间升序（优先重试旧的）

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            if results:
                logger.info(f"📋 找到{len(results)}个可重试的失败结果")

            return results

        except Exception as e:
            logger.error(f"❌ 获取失败结果失败: {e}")
            raise RepositoryException(f"获取失败结果失败: {e}", e)

    async def delete_by_task(self, task_id: str) -> int:
        """删除任务的所有处理结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})

            logger.info(f"🗑️ 删除任务处理结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务处理结果失败: {e}")
            raise RepositoryException(f"删除任务处理结果失败: {e}", e)
