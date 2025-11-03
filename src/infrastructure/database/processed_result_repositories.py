"""AI处理结果数据仓储

v2.0.0 职责分离架构：
- 管理 processed_results 集合的所有数据访问操作
- 支持状态管理和用户操作
- 提供AI服务所需的查询和更新接口

v2.0.1 字段扩展：
- 支持原始字段（title, url, content等）
- 支持AI服务新增字段（content_zh, cls_results等）
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessedResultRepository:
    """AI处理结果仓储（v2.0.0 新增）"""

    def __init__(self):
        self.collection_name = "processed_results"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: ProcessedResult) -> Dict[str, Any]:
        """将ProcessedResult实体转换为字典（v2.0.1 扩展）"""
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
            # AI处理数据
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
            # AI元数据
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
            "retry_count": result.retry_count
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> ProcessedResult:
        """将字典转换为ProcessedResult实体（v2.0.1 扩展）"""
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
            # AI处理数据
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
            # AI元数据
            ai_model=data.get("ai_model"),
            ai_processing_time_ms=data.get("ai_processing_time_ms", 0),
            ai_confidence_score=data.get("ai_confidence_score", 0.0),
            ai_metadata=data.get("ai_metadata", {}),
            processing_status=data.get("processing_status", "pending"),
            http_status_code=data.get("http_status_code"),
            is_test_data=data.get("is_test_data", False),
            # 用户操作
            status=ProcessedStatus(data.get("status", "pending")),
            user_rating=data.get("user_rating"),
            user_notes=data.get("user_notes"),
            # 时间戳
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            updated_at=data.get("updated_at", datetime.utcnow()),
            # 错误处理
            processing_error=data.get("processing_error"),
            retry_count=data.get("retry_count", 0)
        )

    # ==================== 创建和初始化 ====================

    async def create_pending_result(self, raw_result_id: str, task_id: str) -> ProcessedResult:
        """
        创建待处理的结果记录（v2.0.1 复制原始字段）

        从 search_results 获取原始数据并复制到 processed_results，
        避免前端查询时需要 JOIN 操作。

        Args:
            raw_result_id: 原始结果ID（来自search_results）
            task_id: 任务ID

        Returns:
            创建的ProcessedResult实体
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
            raise

    # ==================== 状态管理 ====================

    async def update_processing_status(
        self,
        result_id: str,
        status: ProcessedStatus,
        **kwargs
    ) -> bool:
        """
        更新处理状态

        Args:
            result_id: 结果ID
            status: 新状态
            **kwargs: 其他更新字段（如 processing_error, ai_model 等）

        Returns:
            是否更新成功
        """
        try:
            collection = await self._get_collection()

            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }

            # 合并额外字段
            update_data.update(kwargs)

            # 特殊处理：COMPLETED状态设置处理完成时间
            if status == ProcessedStatus.COMPLETED and "processed_at" not in kwargs:
                update_data["processed_at"] = datetime.utcnow()

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 更新处理状态: {result_id} -> {status.value}")
                return True

            logger.warning(f"⚠️ 处理状态未更新（记录不存在或无变化）: {result_id}")
            return False

        except Exception as e:
            logger.error(f"❌ 更新处理状态失败: {e}")
            raise

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
        """
        保存AI处理结果

        Args:
            result_id: 结果ID
            translated_title: 翻译后的标题
            translated_content: 翻译后的内容
            summary: AI摘要
            key_points: 关键点列表
            sentiment: 情感分析
            categories: 分类标签
            ai_model: AI模型名称
            processing_time_ms: 处理耗时
            ai_confidence_score: 置信度分数

        Returns:
            是否保存成功
        """
        try:
            collection = await self._get_collection()

            update_data = {
                "status": ProcessedStatus.COMPLETED.value,
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
                update_data["ai_processing_time_ms"] = processing_time_ms
            if ai_confidence_score is not None:
                update_data["ai_confidence_score"] = ai_confidence_score

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 保存AI处理结果: {result_id}")
                return True

            logger.warning(f"⚠️ AI结果未保存（记录不存在）: {result_id}")
            return False

        except Exception as e:
            logger.error(f"❌ 保存AI处理结果失败: {e}")
            raise

    # ==================== 查询方法 ====================

    async def get_by_id(self, result_id: str) -> Optional[ProcessedResult]:
        """根据ID获取处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取处理结果失败: {e}")
            raise

    async def get_by_raw_result_id(self, raw_result_id: str) -> Optional[ProcessedResult]:
        """根据原始结果ID获取处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"raw_result_id": raw_result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 根据原始结果ID获取处理结果失败: {e}")
            raise

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[ProcessedStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[ProcessedResult], int]:
        """
        获取任务的处理结果（支持状态筛选和分页）

        Args:
            task_id: 任务ID
            status: 状态筛选（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            (结果列表, 总数)
        """
        try:
            collection = await self._get_collection()

            # 构建查询条件
            query = {"task_id": task_id}
            if status is not None:
                query["status"] = status.value

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
            raise

    # ==================== 用户操作 ====================

    async def update_user_action(
        self,
        result_id: str,
        status: Optional[ProcessedStatus] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """
        更新用户操作（留存、删除、评分、备注）

        Args:
            result_id: 结果ID
            status: 新状态（ARCHIVED或DELETED）
            user_rating: 用户评分（1-5）
            user_notes: 用户备注

        Returns:
            是否更新成功
        """
        try:
            collection = await self._get_collection()

            update_data = {"updated_at": datetime.utcnow()}

            if status is not None:
                update_data["status"] = status.value
            if user_rating is not None:
                if not 1 <= user_rating <= 5:
                    raise ValueError("用户评分必须在1-5之间")
                update_data["user_rating"] = user_rating
            if user_notes is not None:
                update_data["user_notes"] = user_notes

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"✅ 更新用户操作: {result_id}")
                return True

            logger.warning(f"⚠️ 用户操作未更新（记录不存在）: {result_id}")
            return False

        except ValueError as e:
            logger.error(f"❌ 用户操作参数错误: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 更新用户操作失败: {e}")
            raise

    # ==================== 统计和分析 ====================

    async def get_status_statistics(self, task_id: str) -> Dict[str, int]:
        """
        获取任务的状态统计

        Args:
            task_id: 任务ID

        Returns:
            状态计数字典 {"pending": 10, "completed": 5, ...}
        """
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
            raise

    async def get_failed_results(self, max_retry: int = 3) -> List[ProcessedResult]:
        """
        获取失败的结果（用于重试）

        Args:
            max_retry: 最大重试次数

        Returns:
            失败的结果列表（retry_count < max_retry）
        """
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
            raise

    # ==================== 批量操作 ====================

    async def bulk_create_pending_results(
        self,
        raw_result_ids: List[str],
        task_id: str
    ) -> List[ProcessedResult]:
        """
        批量创建待处理结果（v2.0.1 复制原始字段）

        从 search_results 获取原始数据并复制到 processed_results，
        避免前端查询时需要 JOIN 操作。

        Args:
            raw_result_ids: 原始结果ID列表
            task_id: 任务ID

        Returns:
            创建的ProcessedResult列表
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
            raise

    async def delete_by_task(self, task_id: str) -> int:
        """
        删除任务的所有处理结果

        Args:
            task_id: 任务ID

        Returns:
            删除的记录数
        """
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})

            logger.info(f"🗑️ 删除任务处理结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务处理结果失败: {e}")
            raise
