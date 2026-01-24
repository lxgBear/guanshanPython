"""即时搜索结果仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 IInstantSearchResultRepository 接口，提供：
- 即时搜索结果的 CRUD 操作
- 基于 content_hash 的去重机制（v1.3.0核心）
- 发现统计信息维护
- 按任务ID和搜索类型查询

职责：
- 数据库操作：MongoDB 集合 instant_search_results
- 去重检测：content_hash 唯一性检查
- 统计更新：原子更新发现次数和唯一搜索数
- 实体转换：InstantSearchResult <-> Dict

去重机制（v1.3.0）：
1. 每个结果生成 content_hash（基于标题+URL+内容）
2. 新结果入库前先调用 find_by_content_hash() 检查
3. 命中则调用 update_discovery_stats() 更新统计
4. 未命中则调用 create() 创建新结果
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_instant_search_repository import (
    IInstantSearchResultRepository
)
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoInstantSearchResultRepository(IInstantSearchResultRepository):
    """即时搜索结果仓储 MongoDB 实现

    集合: instant_search_results

    索引建议:
    - _id (默认)
    - content_hash (唯一索引，去重核心)
    - task_id (查询优化)
    - search_type (v2.1.0 统一架构)
    - (task_id, search_type) 复合索引
    - v4.8.1: relevance_score (排序优化) - 已移除
    - created_at (排序优化)

    v2.1.0 统一架构：
    - 即时搜索和智能搜索共用此结果表
    - 通过 search_type 字段区分类型
    """

    def __init__(self):
        self.collection_name = "instant_search_results"

    async def _get_collection(self):
        """获取MongoDB集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: InstantSearchResult, search_type: str = "instant") -> Dict[str, Any]:
        """将结果实体转换为MongoDB文档

        Args:
            result: 结果实体
            search_type: 搜索类型 ("instant" | "smart") v2.1.0新增

        Returns:
            MongoDB文档字典
        """
        return {
            "_id": result.id,
            "task_id": result.task_id,
            "search_type": search_type,  # v2.1.0 统一架构
            "title": result.title,
            "url": result.url,
            # v2.1.1: 移除 'content' 字段（InstantSearchResult 已改用 markdown_content 和 html_content）
            "snippet": result.snippet,
            "content_hash": result.content_hash,  # v1.3.0 去重键
            "url_normalized": result.url_normalized,  # v1.3.0 规范化URL
            "markdown_content": result.markdown_content,
            "html_content": result.html_content,
            "source": result.source,
            "published_date": result.published_date,
            "author": result.author,
            "language": result.language,
            "metadata": result.metadata,
            # v4.8.1: 移除评分字段
            # v1.3.0 发现统计字段
            "first_found_at": result.first_found_at,
            "last_found_at": result.last_found_at,
            "found_count": result.found_count,
            "unique_searches": result.unique_searches,
            "created_at": result.created_at,
            "updated_at": result.updated_at
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> InstantSearchResult:
        """将MongoDB文档转换为结果实体

        Args:
            data: MongoDB文档字典

        Returns:
            结果实体
        """
        return InstantSearchResult(
            id=data["_id"],
            task_id=data["task_id"],
            title=data.get("title", ""),
            url=data.get("url", ""),
            # v2.1.1: 移除 content 参数（InstantSearchResult 构造函数不接受此参数）
            snippet=data.get("snippet"),
            content_hash=data.get("content_hash", ""),
            url_normalized=data.get("url_normalized", ""),
            markdown_content=data.get("markdown_content"),
            html_content=data.get("html_content"),
            source=data.get("source", "web"),
            published_date=data.get("published_date"),
            author=data.get("author"),
            language=data.get("language"),
            metadata=data.get("metadata", {}),
            # v4.8.1: 移除评分字段
            first_found_at=data.get("first_found_at", datetime.utcnow()),
            last_found_at=data.get("last_found_at", datetime.utcnow()),
            found_count=data.get("found_count", 1),
            unique_searches=data.get("unique_searches", 1),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow())
        )

    async def find_by_content_hash(self, content_hash: str) -> Optional[InstantSearchResult]:
        """根据content_hash查找结果（去重核心方法）

        Args:
            content_hash: 内容哈希值

        Returns:
            InstantSearchResult | None: 已存在的结果，或None

        用途：
        - 去重检测：新结果入库前必须调用此方法
        - 统计更新：命中时调用update_discovery_stats()
        - 映射创建：无论命中与否都创建映射记录

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"content_hash": content_hash})

            if data:
                logger.debug(f"🔍 去重命中: content_hash={content_hash}")
                return self._dict_to_result(data)

            return None

        except Exception as e:
            logger.error(f"❌ 查找content_hash失败: {e}")
            raise RepositoryException(f"查找content_hash失败: {e}", e)

    async def create(self, result: InstantSearchResult, search_type: str = "instant") -> str:
        """创建新结果

        Args:
            result: 结果实体
            search_type: 搜索类型 ("instant" | "smart") v2.1.0统一架构

        Returns:
            result_id: 创建的结果ID

        注意：
        - 调用前应先检查content_hash是否存在
        - search_type用于统一架构支持（即时搜索和智能搜索共用结果表）

        Raises:
            RepositoryException: 创建失败时抛出
        """
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(result, search_type=search_type)

            await collection.insert_one(result_dict)
            logger.info(
                f"✅ 创建即时搜索结果: {result.title[:50]}... "
                f"(ID: {result.id}, type={search_type})"
            )

            return str(result.id)

        except Exception as e:
            logger.error(f"❌ 创建即时搜索结果失败: {e}")
            raise RepositoryException(f"创建即时搜索结果失败: {e}", e)

    async def update_discovery_stats(self, result: InstantSearchResult) -> bool:
        """更新发现统计信息（去重命中时调用）

        Args:
            result: 已存在的结果实体（包含ID）

        Returns:
            是否更新成功

        原子更新操作：
        - last_found_at = now
        - found_count += 1
        - unique_searches += 1
        - updated_at = now

        使用场景：
        - 当find_by_content_hash()命中时调用
        - 表示该结果被再次发现

        Raises:
            EntityNotFoundException: 结果不存在
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()

            update_result = await collection.update_one(
                {"_id": result.id},
                {
                    "$set": {
                        "last_found_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$inc": {
                        "found_count": 1,
                        "unique_searches": 1
                    }
                }
            )

            if update_result.matched_count == 0:
                raise EntityNotFoundException(f"结果不存在: {result.id}")

            # 更新实体对象的统计信息
            result.last_found_at = datetime.utcnow()
            result.updated_at = datetime.utcnow()
            result.found_count += 1
            result.unique_searches += 1

            logger.debug(f"📊 更新发现统计: {result.id}, found_count={result.found_count}")
            return update_result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新发现统计失败: {e}")
            raise RepositoryException(f"更新发现统计失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[InstantSearchResult]:
        """根据ID获取结果

        Args:
            id: 结果ID

        Returns:
            结果实体或None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取即时搜索结果失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取即时搜索结果失败: {e}", e)

    async def update(self, entity: InstantSearchResult) -> bool:
        """更新结果

        Args:
            entity: 结果实体

        Returns:
            是否更新成功

        Raises:
            EntityNotFoundException: 结果不存在
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            result_dict = self._result_to_dict(entity)
            result_dict.pop("_id")  # 移除ID字段

            result = await collection.update_one(
                {"_id": entity.id},
                {"$set": result_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"即时搜索结果不存在: {entity.id}")

            logger.info(f"✅ 更新即时搜索结果: {entity.title[:50]}... (ID: {entity.id})")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新即时搜索结果失败: {e}")
            raise RepositoryException(f"更新即时搜索结果失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除结果

        Args:
            id: 结果ID

        Returns:
            是否删除成功

        Raises:
            RepositoryException: 删除失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.info(f"✅ 删除即时搜索结果: ID={id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 删除即时搜索结果失败 (ID: {id}): {e}")
            raise RepositoryException(f"删除即时搜索结果失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查结果是否存在

        Args:
            id: 结果ID

        Returns:
            是否存在

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            count = await collection.count_documents({"_id": id}, limit=1)
            return count > 0

        except Exception as e:
            logger.error(f"❌ 检查即时搜索结果是否存在失败 (ID: {id}): {e}")
            raise RepositoryException(f"检查结果是否存在失败: {e}", e)

    async def get_results_by_task_and_type(
        self,
        task_id: str,
        search_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[InstantSearchResult], int]:
        """根据任务ID和搜索类型查询结果（v2.1.0统一架构查询）

        Args:
            task_id: 任务ID
            search_type: 搜索类型筛选 ("instant" | "smart")，None表示不筛选
            skip: 跳过记录数（用于分页）
            limit: 返回最大记录数

        Returns:
            (results, total): 结果列表和总数

        v4.8.1 排序规则：
        1. created_at DESC（时间优先）

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()

            # 构建查询条件
            query = {"task_id": task_id}
            if search_type:
                query["search_type"] = search_type

            # 总数
            total = await collection.count_documents(query)

            # 查询
            cursor = collection.find(query).sort([
                ("created_at", -1)
            ]).skip(skip).limit(limit)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            logger.debug(
                f"📋 查询任务结果: task_id={task_id}, search_type={search_type}, "
                f"skip={skip}, limit={limit}, total={total}"
            )
            return results, total

        except Exception as e:
            logger.error(f"❌ 查询任务结果失败: {e}")
            raise RepositoryException(f"查询任务结果失败: {e}", e)
