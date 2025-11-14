"""即时搜索结果映射仓储 MongoDB 实现

Version: v3.0.0 (模块化架构)

实现 IInstantSearchResultMappingRepository 接口，提供：
- 搜索执行与结果的多对多关系管理（v1.3.0核心）
- 搜索发现历史完整追踪
- 正向查询（某次搜索发现了哪些结果）
- 反向查询（某个结果被哪些搜索发现）
- 批量创建映射记录（v2.1.2重复键容错）

职责：
- 数据库操作：MongoDB 集合 instant_search_result_mappings
- 映射管理：记录 search_execution_id <-> result_id 关系
- JOIN查询：聚合管道实现映射表与结果表的关联
- 批量操作：高效的批量插入和容错处理

映射表设计：
- search_execution_id: 搜索执行ID（每次搜索生成唯一ID）
- result_id: 结果ID（指向instant_search_results）
- task_id: 任务ID（冗余字段，方便查询）
- search_position: 搜索结果排名位置
- relevance_score: 相关性评分
- is_first_discovery: 是否首次发现该结果
- found_at: 发现时间

唯一索引：
- (search_execution_id, result_id) 联合唯一
- 保证同一次搜索中同一个结果只记录一次
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.core.domain.entities.instant_search_result_mapping import InstantSearchResultMapping
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.persistence.interfaces.i_instant_search_repository import (
    IInstantSearchResultMappingRepository
)
from src.infrastructure.persistence.interfaces.i_repository import (
    RepositoryException,
    EntityNotFoundException
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoInstantSearchResultMappingRepository(IInstantSearchResultMappingRepository):
    """即时搜索结果映射仓储 MongoDB 实现

    集合: instant_search_result_mappings

    索引建议:
    - _id (默认)
    - (search_execution_id, result_id) 联合唯一索引
    - search_execution_id (正向查询优化)
    - result_id (反向查询优化)
    - task_id (任务级别查询优化)
    - search_position (排序优化)
    - found_at (时间范围查询优化)

    v1.3.0 核心功能：
    - 多对多关系管理
    - 发现历史追踪
    - 去重机制支持
    """

    def __init__(self):
        self.collection_name = "instant_search_result_mappings"

    async def _get_collection(self):
        """获取MongoDB集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _mapping_to_dict(self, mapping: InstantSearchResultMapping) -> Dict[str, Any]:
        """将映射实体转换为MongoDB文档

        Args:
            mapping: 映射实体

        Returns:
            MongoDB文档字典
        """
        return {
            "_id": mapping.id,
            "search_execution_id": mapping.search_execution_id,
            "result_id": mapping.result_id,
            "task_id": mapping.task_id,
            "found_at": mapping.found_at,
            "search_position": mapping.search_position,
            "relevance_score": mapping.relevance_score,
            "is_first_discovery": mapping.is_first_discovery,
            "created_at": mapping.created_at
        }

    def _dict_to_mapping(self, data: Dict[str, Any]) -> InstantSearchResultMapping:
        """将MongoDB文档转换为映射实体

        Args:
            data: MongoDB文档字典

        Returns:
            映射实体
        """
        return InstantSearchResultMapping(
            id=data["_id"],
            search_execution_id=data["search_execution_id"],
            result_id=data["result_id"],
            task_id=data["task_id"],
            found_at=data.get("found_at", datetime.utcnow()),
            search_position=data.get("search_position", 0),
            relevance_score=data.get("relevance_score", 0.0),
            is_first_discovery=data.get("is_first_discovery", False),
            created_at=data.get("created_at", datetime.utcnow())
        )

    async def create(self, entity: InstantSearchResultMapping) -> str:
        """创建映射记录

        Args:
            entity: 映射实体

        Returns:
            mapping_id: 创建的映射ID

        Raises:
            RepositoryException: 创建失败时抛出
        """
        try:
            collection = await self._get_collection()
            mapping_dict = self._mapping_to_dict(entity)

            await collection.insert_one(mapping_dict)
            logger.debug(
                f"✅ 创建结果映射: search={entity.search_execution_id}, "
                f"result={entity.result_id}"
            )

            return str(entity.id)

        except Exception as e:
            logger.error(f"❌ 创建结果映射失败: {e}")
            raise RepositoryException(f"创建结果映射失败: {e}", e)

    async def batch_create(self, mappings: List[InstantSearchResultMapping]) -> None:
        """批量创建映射记录（v2.1.2重复键容错）

        Args:
            mappings: 映射记录列表

        容错策略 (v2.1.2)：
        - 使用 ordered=False 允许部分插入成功
        - 捕获重复键异常，只记录警告而不抛出错误
        - 返回void，通过日志记录成功/跳过数量

        使用场景：
        - 一次搜索发现多个结果时批量创建映射
        - 性能优化：减少数据库往返次数

        Raises:
            RepositoryException: 非重复键错误时抛出
        """
        if not mappings:
            return

        try:
            collection = await self._get_collection()
            mapping_dicts = [self._mapping_to_dict(m) for m in mappings]

            # v2.1.2: 使用 ordered=False 允许跳过重复键继续插入
            result = await collection.insert_many(mapping_dicts, ordered=False)

            inserted_count = len(result.inserted_ids)
            total_count = len(mappings)

            if inserted_count == total_count:
                logger.info(f"✅ 批量创建结果映射成功: {inserted_count}条")
            else:
                skipped = total_count - inserted_count
                logger.warning(
                    f"⚠️ 批量创建结果映射部分成功: 成功{inserted_count}条, "
                    f"跳过{skipped}条（重复键）, 总计{total_count}条"
                )

        except Exception as e:
            # v2.1.2: 捕获 BulkWriteError（包含重复键错误）
            from pymongo.errors import BulkWriteError

            if isinstance(e, BulkWriteError):
                # 提取成功插入的数量
                inserted_count = e.details.get('nInserted', 0)
                total_count = len(mappings)

                # 提取重复键错误数量
                write_errors = e.details.get('writeErrors', [])
                duplicate_count = sum(1 for err in write_errors if err.get('code') == 11000)

                logger.warning(
                    f"⚠️ 批量创建结果映射部分成功: 成功{inserted_count}条, "
                    f"重复键跳过{duplicate_count}条, 总计{total_count}条"
                )

                # v2.1.2: 重复键不视为致命错误，不抛出异常
                # 这是正常的去重行为：同一次搜索中同一个结果只保留一条映射
            else:
                # 其他错误仍然抛出
                logger.error(f"❌ 批量创建结果映射失败: {e}")
                raise RepositoryException(f"批量创建结果映射失败: {e}", e)

    async def get_results_by_search_execution(
        self,
        search_execution_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取某次搜索执行的所有结果（JOIN查询）

        Args:
            search_execution_id: 搜索执行ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            (results_with_mapping, total)
            每个元素包含：
            {
                "mapping": InstantSearchResultMapping,  # 映射元数据
                "result": InstantSearchResult            # 完整结果
            }

        查询逻辑：
        1. 筛选该次搜索的映射记录
        2. JOIN instant_search_results表获取完整结果
        3. 按search_position排序（保持搜索排名）
        4. 分页返回

        使用场景：
        - 前端展示某次搜索的结果列表
        - 追踪搜索结果的原始排名

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()

            # 使用MongoDB聚合管道实现JOIN查询
            skip = (page - 1) * page_size

            pipeline = [
                # 1. 筛选该次搜索执行的映射
                {"$match": {"search_execution_id": search_execution_id}},

                # 2. JOIN结果表
                {
                    "$lookup": {
                        "from": "instant_search_results",
                        "localField": "result_id",
                        "foreignField": "_id",
                        "as": "result"
                    }
                },

                # 3. 展开结果数组
                {"$unwind": "$result"},

                # 4. 按搜索排名排序
                {"$sort": {"search_position": 1}},

                # 5. 分页
                {"$skip": skip},
                {"$limit": page_size}
            ]

            # 执行查询
            cursor = collection.aggregate(pipeline)
            results_with_mapping = []

            # 动态导入 InstantSearchResultRepository 避免循环依赖
            from .instant_search_result_repository import MongoInstantSearchResultRepository
            result_repo = MongoInstantSearchResultRepository()

            async for doc in cursor:
                results_with_mapping.append({
                    "mapping": self._dict_to_mapping(doc),
                    "result": result_repo._dict_to_result(doc["result"])
                })

            # 计算总数
            total = await collection.count_documents({"search_execution_id": search_execution_id})

            logger.debug(
                f"📋 查询搜索结果: search_execution_id={search_execution_id}, "
                f"page={page}, size={page_size}, total={total}"
            )
            return results_with_mapping, total

        except Exception as e:
            logger.error(f"❌ 查询搜索结果失败: {e}")
            raise RepositoryException(f"查询搜索结果失败: {e}", e)

    async def get_mappings_by_result(self, result_id: str) -> List[InstantSearchResultMapping]:
        """查询哪些搜索发现了该结果（反向查询）

        Args:
            result_id: 结果ID

        Returns:
            映射记录列表（按found_at倒序）

        使用场景：
        - 追溯结果的发现历史
        - 分析结果的复现频率
        - 验证去重机制的有效性

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            cursor = collection.find({"result_id": result_id}).sort("found_at", -1)

            mappings = []
            async for data in cursor:
                mappings.append(self._dict_to_mapping(data))

            logger.debug(f"🔍 查询结果映射: result_id={result_id}, count={len(mappings)}")
            return mappings

        except Exception as e:
            logger.error(f"❌ 查询结果映射失败: {e}")
            raise RepositoryException(f"查询结果映射失败: {e}", e)

    async def get_by_id(self, id: str) -> Optional[InstantSearchResultMapping]:
        """根据ID获取映射

        Args:
            id: 映射ID

        Returns:
            映射实体或None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": id})

            if data:
                return self._dict_to_mapping(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取结果映射失败 (ID: {id}): {e}")
            raise RepositoryException(f"获取结果映射失败: {e}", e)

    async def update(self, entity: InstantSearchResultMapping) -> bool:
        """更新映射

        Args:
            entity: 映射实体

        Returns:
            是否更新成功

        Raises:
            EntityNotFoundException: 映射不存在
            RepositoryException: 更新失败时抛出
        """
        try:
            collection = await self._get_collection()
            mapping_dict = self._mapping_to_dict(entity)
            mapping_dict.pop("_id")  # 移除ID字段

            result = await collection.update_one(
                {"_id": entity.id},
                {"$set": mapping_dict}
            )

            if result.matched_count == 0:
                raise EntityNotFoundException(f"结果映射不存在: {entity.id}")

            logger.debug(f"✅ 更新结果映射: ID={entity.id}")
            return result.modified_count > 0

        except EntityNotFoundException:
            raise
        except Exception as e:
            logger.error(f"❌ 更新结果映射失败: {e}")
            raise RepositoryException(f"更新结果映射失败: {e}", e)

    async def delete(self, id: str) -> bool:
        """删除映射

        Args:
            id: 映射ID

        Returns:
            是否删除成功

        Raises:
            RepositoryException: 删除失败时抛出
        """
        try:
            collection = await self._get_collection()
            result = await collection.delete_one({"_id": id})

            if result.deleted_count > 0:
                logger.debug(f"✅ 删除结果映射: ID={id}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ 删除结果映射失败 (ID: {id}): {e}")
            raise RepositoryException(f"删除结果映射失败: {e}", e)

    async def exists(self, id: str) -> bool:
        """检查映射是否存在

        Args:
            id: 映射ID

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
            logger.error(f"❌ 检查结果映射是否存在失败 (ID: {id}): {e}")
            raise RepositoryException(f"检查映射是否存在失败: {e}", e)
