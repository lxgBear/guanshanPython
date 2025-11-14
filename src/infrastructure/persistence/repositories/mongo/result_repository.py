"""
MongoDB 搜索结果 Repository 实现

基于 MongoDB 的搜索结果数据访问实现，实现 IResultRepository 接口。

Version: v3.0.0 (模块化架构)
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from src.core.domain.entities.search_result import SearchResult, SearchResultBatch, ResultStatus
from src.infrastructure.persistence.interfaces import IResultRepository
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoResultRepository(IResultRepository):
    """
    MongoDB 搜索结果 Repository 实现

    使用 MongoDB 作为数据存储，实现 IResultRepository 接口。
    """

    def __init__(self):
        self.collection_name = "search_results"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        """将结果实体转换为 MongoDB 文档 (v2.1.0: 优化后的模型，移除 metadata 存储)"""
        return {
            "_id": str(result.id),
            "task_id": str(result.task_id),
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            # 优化后的字段
            "markdown_content": result.markdown_content,  # Markdown 格式内容
            "html_content": result.html_content,  # HTML 格式内容
            "article_tag": result.article_tag,
            "article_published_time": result.article_published_time,
            "source_url": result.source_url,
            "http_status_code": result.http_status_code,
            "search_position": result.search_position,
            # v2.1.1: 去重字段
            "content_hash": result.content_hash,
            # v2.1.0: 不再存储 metadata 字段以减少数据量（2-5KB/记录）
            # 所有有用字段已提取为独立字段：author, language, article_tag, http_status_code 等
            # "metadata": result.metadata,  # 已废弃 - 不再存储
            # 已移除字段: raw_data, content (使用 markdown_content 替代)
            "relevance_score": result.relevance_score,
            "quality_score": result.quality_score,
            "status": result.status.value,
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "is_test_data": result.is_test_data
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> SearchResult:
        """将 MongoDB 文档转换为结果实体

        v1.5.0: 修复 ID 类型 - 使用 id 字段（雪花 ID）而非 _id 字段（MongoDB 主键）
        """
        # v1.5.0: 优先使用 id 字段（迁移后的雪花 ID），fallback 到 _id（向后兼容）
        result_id = str(data.get("id") or data.get("_id", ""))
        task_id = str(data.get("task_id", ""))

        # 处理 article_tag：数据库中可能存储为列表
        article_tag_raw = data.get("article_tag")
        if isinstance(article_tag_raw, list):
            # 如果是列表，用逗号连接成字符串
            article_tag = ', '.join(str(tag) for tag in article_tag_raw) if article_tag_raw else None
        else:
            article_tag = article_tag_raw

        # v1.5.2: 处理旧状态值的向后兼容
        status_value = data.get("status", "pending")
        try:
            status = ResultStatus(status_value)
        except ValueError:
            # 处理旧状态值: processing/completed → pending (回归到待处理)
            logger.warning(f"⚠️  检测到已废弃的状态值 '{status_value}'，将转换为 'pending' (ID: {result_id})")
            status = ResultStatus.PENDING

        return SearchResult(
            id=result_id,
            task_id=task_id,
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            # 优化后的字段
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            article_tag=article_tag,
            article_published_time=data.get("article_published_time"),
            source_url=data.get("source_url"),
            http_status_code=data.get("http_status_code"),
            search_position=data.get("search_position"),
            # v2.1.1: 去重字段
            content_hash=data.get("content_hash"),
            metadata=data.get("metadata", {}),
            # 已移除字段: raw_data, content (不再从数据库读取)
            relevance_score=data.get("relevance_score", 0.0),
            quality_score=data.get("quality_score", 0.0),
            status=status,
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            is_test_data=data.get("is_test_data", False)
        )

    # ==================== IBasicRepository 实现 ====================

    async def create(self, entity: SearchResult) -> str:
        """创建搜索结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)

            await collection.insert_one(result_dict)
            logger.info(f"✅ 创建搜索结果: {entity.title[:50]} (ID: {entity.id})")

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建搜索结果失败: {e}")
            raise RepositoryException(f"创建搜索结果失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[SearchResult]:
        """根据 ID 获取搜索结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取搜索结果失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取搜索结果失败: {e}", e)

    async def update(self, entity: SearchResult) -> bool:
        """更新搜索结果"""
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)
            result_dict.pop("_id")  # 移除 ID 字段

            result = await collection.update_one(
                {"_id": str(entity.id)},
                {"$set": result_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"搜索结果不存在: {entity.id}")

            logger.info(f"✅ 更新搜索结果: {entity.title[:50]} (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新搜索结果失败: {e}")
            raise RepositoryException(f"更新搜索结果失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除搜索结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除搜索结果: {id}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 删除搜索结果失败: {e}")
            raise RepositoryException(f"删除搜索结果失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查搜索结果是否存在"""
        try:
            collection = await self._get_collection()
            count = await collection.count_documents({"_id": id}, limit=1)
            return count > 0

        except Exception as e:
            logger.error(f"❌ 检查搜索结果存在性失败: {e}")
            raise RepositoryException(f"检查搜索结果存在性失败: {e}", e)

    # ==================== IQueryableRepository 实现 ====================

    async def find_all(self, limit: Optional[int] = None) -> List[SearchResult]:
        """获取所有搜索结果"""
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
            logger.error(f"❌ 获取所有搜索结果失败: {e}")
            raise RepositoryException(f"获取所有搜索结果失败: {e}", e)

    async def find_by_criteria(self, criteria: Dict[str, Any]) -> List[SearchResult]:
        """根据条件查询搜索结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 条件查询搜索结果失败: {e}")
            raise RepositoryException(f"条件查询搜索结果失败: {e}", e)

    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """统计搜索结果数量"""
        try:
            collection = await self._get_collection()
            query = criteria if criteria else {}
            return await collection.count_documents(query)

        except Exception as e:
            logger.error(f"❌ 统计搜索结果数量失败: {e}")
            raise RepositoryException(f"统计搜索结果数量失败: {e}", e)

    # ==================== IBulkOperationRepository 实现 ====================

    async def bulk_create(self, entities: List[SearchResult]) -> List[str]:
        """批量创建搜索结果"""
        if not entities:
            return []

        try:
            collection = await self._get_collection()
            result_dicts = [self._result_to_dict(entity) for entity in entities]

            result = await collection.insert_many(result_dicts)
            logger.info(f"✅ 批量创建搜索结果: {len(result.inserted_ids)} 条")

            return [str(id) for id in result.inserted_ids]

        except Exception as e:
            logger.error(f"❌ 批量创建搜索结果失败: {e}")
            raise RepositoryException(f"批量创建搜索结果失败: {e}", e)

    async def bulk_update(self, entities: List[SearchResult]) -> int:
        """批量更新搜索结果"""
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

            logger.info(f"✅ 批量更新搜索结果: {updated_count} 条")
            return updated_count

        except Exception as e:
            logger.error(f"❌ 批量更新搜索结果失败: {e}")
            raise RepositoryException(f"批量更新搜索结果失败: {e}", e)

    async def bulk_delete(self, ids: List[str]) -> int:
        """批量删除搜索结果"""
        if not ids:
            return 0

        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"_id": {"$in": ids}})

            logger.info(f"✅ 批量删除搜索结果: {result.deleted_count} 条")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 批量删除搜索结果失败: {e}")
            raise RepositoryException(f"批量删除搜索结果失败: {e}", e)

    async def bulk_update_fields(
        self,
        criteria: Dict[str, Any],
        updates: Dict[str, Any]
    ) -> int:
        """批量更新字段

        根据条件批量更新指定字段，不需要加载完整实体。

        Args:
            criteria: 更新条件
            updates: 要更新的字段和值

        Returns:
            int: 成功更新的数量

        Raises:
            RepositoryException: 批量更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.update_many(
                criteria,
                {"$set": updates}
            )

            logger.info(f"✅ 批量更新字段: {result.modified_count} 条")
            return result.modified_count

        except Exception as e:
            logger.error(f"❌ 批量更新字段失败: {e}")
            raise RepositoryException(f"批量更新字段失败: {e}", e)

    # ==================== IResultRepository 特定方法 ====================

    async def find_by_task_id(
        self,
        task_id: str,
        limit: Optional[int] = None
    ) -> List[SearchResult]:
        """根据任务 ID 查询搜索结果"""
        try:
            criteria = {"task_id": task_id}
            collection = await self._get_collection()
            cursor = collection.find(criteria).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"❌ 按任务 ID 查询搜索结果失败: {e}")
            raise RepositoryException(f"按任务 ID 查询搜索结果失败: {e}", e)

    async def find_by_url(self, url: str) -> Optional[SearchResult]:
        """根据 URL 查询搜索结果（去重检查）"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"url": url})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 按 URL 查询搜索结果失败: {e}")
            raise RepositoryException(f"按 URL 查询搜索结果失败: {e}", e)

    async def find_by_status(
        self,
        status: ResultStatus,
        limit: Optional[int] = None
    ) -> List[SearchResult]:
        """根据状态查询搜索结果"""
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
            logger.error(f"❌ 按状态查询搜索结果失败: {e}")
            raise RepositoryException(f"按状态查询搜索结果失败: {e}", e)

    async def save_batch(self, batch: SearchResultBatch) -> List[str]:
        """批量保存搜索结果批次

        这是一个便捷方法，内部调用 bulk_create
        """
        try:
            if not batch.results:
                logger.warning(f"⚠️  批次为空: {batch.batch_id}")
                return []

            # 调用批量创建方法
            result_ids = await self.bulk_create(batch.results)

            logger.info(f"✅ 保存批次成功: {batch.batch_id}, {len(result_ids)} 条结果")
            return result_ids

        except Exception as e:
            logger.error(f"❌ 保存批次失败: {e}")
            raise RepositoryException(f"保存批次失败: {e}", e)

    async def get_task_results_count(self, task_id: str) -> int:
        """统计任务的搜索结果数量"""
        try:
            criteria = {"task_id": task_id}
            return await self.count(criteria)

        except Exception as e:
            logger.error(f"❌ 统计任务搜索结果数量失败: {e}")
            raise RepositoryException(f"统计任务搜索结果数量失败: {e}", e)

    async def delete_by_task_id(self, task_id: str) -> int:
        """删除任务的所有搜索结果"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})

            logger.info(f"✅ 删除任务搜索结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"❌ 删除任务搜索结果失败: {e}")
            raise RepositoryException(f"删除任务搜索结果失败: {e}", e)

    # ==================== 额外的业务方法 (向后兼容) ====================

    async def save_results(
        self,
        results: List[SearchResult],
        enable_dedup: bool = True
    ) -> Dict[str, int]:
        """批量保存搜索结果（v2.1.1: 支持去重）

        Args:
            results: 搜索结果列表
            enable_dedup: 是否启用去重（默认 True）

        Returns:
            保存统计信息: {"saved": 10, "duplicates": 2, "total": 12}
        """
        if not results:
            return {"saved": 0, "duplicates": 0, "total": 0}

        try:
            collection = await self._get_collection()

            # 如果不启用去重，直接批量插入
            if not enable_dedup:
                result_dicts = [self._result_to_dict(result) for result in results]
                await collection.insert_many(result_dicts)
                logger.info(f"保存搜索结果成功（未去重）: {len(results)}条")
                return {"saved": len(results), "duplicates": 0, "total": len(results)}

            # 启用去重逻辑
            # 1. 确保所有结果都有 content_hash
            for result in results:
                result.ensure_content_hash()

            # 2. 获取所有 content_hash
            content_hashes = [result.content_hash for result in results]

            # 3. 查询数据库中已存在的 content_hash
            existing_hashes = set()
            async for doc in collection.find(
                {"content_hash": {"$in": content_hashes}},
                {"content_hash": 1}
            ):
                existing_hashes.add(doc.get("content_hash"))

            # 4. 过滤出新结果
            new_results = []
            duplicate_count = 0

            for result in results:
                if result.content_hash not in existing_hashes:
                    new_results.append(result)
                else:
                    duplicate_count += 1
                    logger.debug(f"跳过重复内容: {result.url} (hash: {result.content_hash})")

            # 5. 保存新结果
            if new_results:
                result_dicts = [self._result_to_dict(result) for result in new_results]
                await collection.insert_many(result_dicts)
                logger.info(f"保存搜索结果成功: 新增{len(new_results)}条, 跳过重复{duplicate_count}条")
            else:
                logger.info(f"无新结果保存: 全部{duplicate_count}条均为重复")

            return {
                "saved": len(new_results),
                "duplicates": duplicate_count,
                "total": len(results)
            }

        except Exception as e:
            logger.error(f"保存搜索结果失败: {e}")
            raise RepositoryException(f"保存搜索结果失败: {e}", e)

    async def check_existing_urls(self, task_id: str, urls: List[str]) -> set:
        """检查哪些 URL 已存在于数据库（v2.1.1: URL 去重辅助方法）

        Args:
            task_id: 任务 ID
            urls: URL 列表

        Returns:
            已存在的 URL 集合
        """
        try:
            collection = await self._get_collection()

            existing_urls = set()
            async for doc in collection.find(
                {"task_id": task_id, "url": {"$in": urls}},
                {"url": 1}
            ):
                existing_urls.add(doc.get("url"))

            if existing_urls:
                logger.debug(f"发现{len(existing_urls)}个已存在的 URL (任务: {task_id})")

            return existing_urls

        except Exception as e:
            logger.error(f"检查已存在 URL 失败: {e}")
            raise RepositoryException(f"检查已存在 URL 失败: {e}", e)

    async def get_results_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20,
        execution_time: Optional[datetime] = None
    ) -> tuple[List[SearchResult], int]:
        """获取任务的搜索结果（分页）"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            filter_dict = {"task_id": task_id}
            if execution_time:
                filter_dict["execution_time"] = execution_time

            # 计算总数
            total = await collection.count_documents(filter_dict)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results, total

        except Exception as e:
            logger.error(f"获取任务结果失败: {e}")
            raise RepositoryException(f"获取任务结果失败: {e}", e)

    async def get_latest_results(
        self,
        task_id: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """获取任务的最新结果"""
        try:
            collection = await self._get_collection()
            cursor = collection.find({"task_id": task_id}).sort("created_at", -1).limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"获取最新结果失败: {e}")
            raise RepositoryException(f"获取最新结果失败: {e}", e)

    async def delete_results_by_task(self, task_id: str) -> int:
        """删除任务的所有结果（别名方法，调用 delete_by_task_id）"""
        return await self.delete_by_task_id(task_id)

    # ==================== 状态管理方法 (v2.1.0 新增) ====================

    async def get_results_by_status(
        self,
        task_id: str,
        status: ResultStatus,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[SearchResult], int]:
        """按状态筛选搜索结果

        Args:
            task_id: 任务 ID
            status: 结果状态
            page: 页码
            page_size: 每页数量

        Returns:
            (结果列表, 总数)
        """
        try:
            collection = await self._get_collection()

            query = {
                "task_id": task_id,
                "status": status.value
            }

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
            logger.error(f"按状态获取结果失败: {e}")
            raise RepositoryException(f"按状态获取结果失败: {e}", e)

    async def count_by_status(self, task_id: str) -> Dict[str, int]:
        """统计各状态结果数量

        Args:
            task_id: 任务 ID

        Returns:
            状态计数字典 {"pending": 10, "archived": 5, ...}
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

            status_counts = {status.value: 0 for status in ResultStatus}

            async for doc in collection.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]

            return status_counts

        except Exception as e:
            logger.error(f"统计状态失败: {e}")
            raise RepositoryException(f"统计状态失败: {e}", e)

    async def update_result_status(
        self,
        result_id: str,
        new_status: ResultStatus
    ) -> bool:
        """更新单个结果状态

        Args:
            result_id: 结果 ID
            new_status: 新状态

        Returns:
            是否更新成功
        """
        try:
            collection = await self._get_collection()

            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"更新结果状态: {result_id} -> {new_status.value}")
                return True

            return False

        except Exception as e:
            logger.error(f"更新结果状态失败: {e}")
            raise RepositoryException(f"更新结果状态失败: {e}", e)

    async def bulk_update_status(
        self,
        result_ids: List[str],
        new_status: ResultStatus
    ) -> int:
        """批量更新结果状态

        Args:
            result_ids: 结果 ID 列表
            new_status: 新状态

        Returns:
            更新的记录数
        """
        try:
            collection = await self._get_collection()

            update_data = {
                "status": new_status.value,
                "processed_at": datetime.utcnow()
            }

            result = await collection.update_many(
                {"_id": {"$in": result_ids}},
                {"$set": update_data}
            )

            logger.info(f"批量更新状态: {result.modified_count}条 -> {new_status.value}")
            return result.modified_count

        except Exception as e:
            logger.error(f"批量更新状态失败: {e}")
            raise RepositoryException(f"批量更新状态失败: {e}", e)

    async def get_status_distribution(self, task_id: str) -> Dict[str, Any]:
        """获取状态分布统计

        Args:
            task_id: 任务 ID

        Returns:
            状态分布统计信息
        """
        try:
            # 获取各状态计数
            status_counts = await self.count_by_status(task_id)
            total = sum(status_counts.values())

            # 计算百分比
            distribution = {}
            for status, count in status_counts.items():
                percentage = (count / total * 100) if total > 0 else 0
                distribution[status] = {
                    "count": count,
                    "percentage": round(percentage, 2)
                }

            return {
                "total": total,
                "distribution": distribution
            }

        except Exception as e:
            logger.error(f"获取状态分布失败: {e}")
            raise RepositoryException(f"获取状态分布失败: {e}", e)
