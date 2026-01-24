"""数据整编服务

提供数据源管理的核心业务逻辑，包括：
- 数据源CRUD操作
- 状态同步管理（MongoDB事务）
- 原始数据引用管理
- 批量操作支持

v1.5.1: 事务兼容性改进
- 支持standalone MongoDB（开发环境）
- 支持replica set MongoDB（生产环境）
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.data_source import (
    DataSource,
    DataSourceStatus,
    RawDataReference
)
from src.core.domain.entities.search_result import SearchResult, ResultStatus
from src.core.domain.entities.instant_search_result import InstantSearchResult, InstantSearchResultStatus
from src.core.domain.entities.archived_data import ArchivedData
from src.infrastructure.database.data_source_repositories import DataSourceRepository
from src.infrastructure.database.archived_data_repositories import ArchivedDataRepository
from src.infrastructure.database.connection import is_mongodb_replica_set
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataCurationService:
    """数据整编服务

    核心功能：
    - 数据源生命周期管理
    - 状态同步（使用MongoDB事务）
    - 原始数据引用管理
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """初始化服务

        Args:
            db: MongoDB数据库实例
        """
        self.db = db
        self.data_source_repo = DataSourceRepository(db)
        self.archived_data_repo = ArchivedDataRepository(db)  # 【新增】存档数据仓储
        self.search_results_collection = db.search_results
        self.instant_search_results_collection = db.instant_search_results
        self._supports_transactions = None  # 缓存事务支持检测结果

    @asynccontextmanager
    async def _transaction_context(self):
        """事务上下文管理器（兼容standalone和replica set）

        v1.5.1: 自动检测MongoDB是否支持事务
        - Replica set/mongos: 使用事务保证ACID
        - Standalone: 直接操作（无事务但仍保证单文档原子性）

        Yields:
            session: MongoDB session对象（如果支持事务），否则为None
        """
        # 缓存检测结果，避免重复检测
        if self._supports_transactions is None:
            self._supports_transactions = await is_mongodb_replica_set()

        if self._supports_transactions:
            # 使用事务
            async with await self.db.client.start_session() as session:
                async with session.start_transaction():
                    yield session
        else:
            # Standalone模式：不使用事务
            # 注意：这里yield None，repository方法需要能够处理session=None
            logger.debug("⚠️  MongoDB standalone模式，操作不使用事务")
            yield None

    # ==========================================
    # 数据源基础操作
    # ==========================================

    async def create_data_source(
        self,
        title: str,
        description: str,
        created_by: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        custom_tags: Optional[List[str]] = None
    ) -> DataSource:
        """创建数据源（草稿状态）

        Args:
            title: 数据源标题
            description: 数据源描述
            created_by: 创建者
            tags: 标签列表（可选）
            metadata: 扩展元数据（可选）
            primary_category: 第一级分类（可选）
            secondary_category: 第二级分类（可选）
            tertiary_category: 第三级分类（可选）
            custom_tags: 自定义标签（可选）

        Returns:
            创建的数据源实体
        """
        data_source = DataSource(
            title=title,
            description=description,
            created_by=created_by,
            updated_by=created_by,
            tags=tags or [],
            metadata=metadata or {},
            primary_category=primary_category,
            secondary_category=secondary_category,
            tertiary_category=tertiary_category,
            custom_tags=custom_tags or []
        )

        await self.data_source_repo.create(data_source)
        logger.info(f"✅ 创建数据源: {data_source.id} - {title}")

        return data_source

    async def get_data_source(self, data_source_id: str) -> Optional[DataSource]:
        """获取数据源详情

        Args:
            data_source_id: 数据源ID

        Returns:
            数据源实体，如果不存在则返回None
        """
        return await self.data_source_repo.find_by_id(data_source_id)

    async def list_data_sources(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> tuple[List[DataSource], int]:
        """列出数据源（支持过滤和分页）

        Args:
            created_by: 创建者过滤
            status: 状态过滤
            source_type: 数据源类型过滤
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            primary_category: 第一级分类过滤
            secondary_category: 第二级分类过滤
            tertiary_category: 第三级分类过滤
            limit: 每页数量
            skip: 跳过数量

        Returns:
            (数据源列表, 总数)
        """
        data_sources = await self.data_source_repo.find_all(
            created_by=created_by,
            status=status,
            source_type=source_type,
            start_date=start_date,
            end_date=end_date,
            primary_category=primary_category,
            secondary_category=secondary_category,
            tertiary_category=tertiary_category,
            limit=limit,
            skip=skip
        )

        total = await self.data_source_repo.count(
            created_by=created_by,
            status=status,
            source_type=source_type,
            start_date=start_date,
            end_date=end_date,
            primary_category=primary_category,
            secondary_category=secondary_category,
            tertiary_category=tertiary_category
        )

        return data_sources, total

    async def update_data_source_info(
        self,
        data_source_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        primary_category: Optional[str] = None,
        secondary_category: Optional[str] = None,
        tertiary_category: Optional[str] = None,
        custom_tags: Optional[List[str]] = None,
        updated_by: str = ""
    ) -> bool:
        """更新数据源基础信息（仅草稿状态可编辑）

        Args:
            data_source_id: 数据源ID
            title: 新标题（可选）
            description: 新描述（可选）
            tags: 新标签列表（可选）
            primary_category: 第一级分类（可选）
            secondary_category: 第二级分类（可选）
            tertiary_category: 第三级分类（可选）
            custom_tags: 自定义标签数组（可选）
            updated_by: 更新者

        Returns:
            是否更新成功

        Raises:
            ValueError: 如果数据源不存在或不可编辑
        """
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_edit():
            raise ValueError(
                f"Cannot edit data source in status '{data_source.status.value}'"
            )

        update_data = {"updated_by": updated_by}

        if title is not None:
            update_data["title"] = title

        if description is not None:
            update_data["description"] = description

        if tags is not None:
            update_data["tags"] = tags

        if primary_category is not None:
            update_data["primary_category"] = primary_category

        if secondary_category is not None:
            update_data["secondary_category"] = secondary_category

        if tertiary_category is not None:
            update_data["tertiary_category"] = tertiary_category

        if custom_tags is not None:
            update_data["custom_tags"] = custom_tags

        return await self.data_source_repo.update(data_source_id, update_data)

    async def update_data_source_content(
        self,
        data_source_id: str,
        edited_content: str,
        updated_by: str
    ) -> bool:
        """更新数据源编辑内容（仅草稿状态可编辑）

        Args:
            data_source_id: 数据源ID
            edited_content: 编辑内容（Markdown格式）
            updated_by: 更新者

        Returns:
            是否更新成功

        Raises:
            ValueError: 如果数据源不存在或不可编辑
        """
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_edit():
            raise ValueError(
                f"Cannot edit data source in status '{data_source.status.value}'"
            )

        update_data = {
            "edited_content": edited_content,
            "content_version": data_source.content_version + 1,
            "updated_by": updated_by
        }

        return await self.data_source_repo.update(data_source_id, update_data)

    # ==========================================
    # 原始数据管理（带状态同步）
    # ==========================================

    async def add_raw_data_to_source(
        self,
        data_source_id: str,
        data_id: str,
        data_type: str,
        added_by: str
    ) -> bool:
        """添加原始数据到数据源

        v1.5.2: 不再自动修改数据状态，状态由用户手动控制

        Args:
            data_source_id: 数据源ID
            data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）
            added_by: 添加者

        Returns:
            是否添加成功

        Raises:
            ValueError: 如果数据源不存在、不可编辑或原始数据不存在
        """
        # 验证数据源
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_edit():
            raise ValueError(
                f"Cannot add data to data source in status '{data_source.status.value}'"
            )

        # v1.5.0: 统一雪花ID后，data_type直接决定集合
        # v2.0.2: 支持从 news_results 查找AI处理后的数据
        if data_type == "scheduled":
            collection = self.search_results_collection
            # 首先在原始数据集合中查找
            raw_data_doc = await collection.find_one({"_id": data_id})
            # 如果未找到，尝试在AI处理结果集合中查找
            if not raw_data_doc:
                news_collection = self.db.news_results
                raw_data_doc = await news_collection.find_one({"_id": data_id})
                if raw_data_doc:
                    logger.info(f"📰 在news_results中找到AI处理后的数据: {data_id}")
        elif data_type == "instant":
            collection = self.instant_search_results_collection
            raw_data_doc = await collection.find_one({"_id": data_id})
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        if not raw_data_doc:
            # v1.5.0+: 智能错误提示 - 检测UUID格式并提供帮助信息
            is_uuid_format = "-" in data_id
            if is_uuid_format:
                # UUID格式的ID可能是旧数据或前端缓存
                logger.warning(
                    f"⚠️  检测到UUID格式ID: {data_id}, "
                    f"v1.5.0后系统已统一使用雪花ID格式。"
                    f"请刷新页面获取最新数据。"
                )
                raise ValueError(
                    f"数据 '{data_id}' 不存在。"
                    f"检测到旧的UUID格式ID，系统已于v1.5.0统一为雪花ID格式。"
                    f"可能原因：①前端缓存的旧数据 ②数据已被删除。建议刷新页面重新加载数据。"
                )
            else:
                raise ValueError(f"Raw data '{data_id}' not found in {data_type} collection")

        # v1.5.2: 移除状态限制，允许任何状态的数据添加到数据源
        current_status = raw_data_doc.get("status", "pending")

        # v1.5.1: 使用兼容的事务上下文（支持standalone和replica set）
        async with self._transaction_context() as session:
            try:
                # v1.5.2: 不再修改原始数据状态
                # 1. 添加到数据源引用列表
                ref = RawDataReference(
                    data_id=data_id,
                    data_type=data_type,
                    title=raw_data_doc.get("title", ""),
                    url=raw_data_doc.get("url", ""),
                    snippet=raw_data_doc.get("snippet", "") or raw_data_doc.get("content", "")[:200],
                    added_by=added_by
                )

                await self.data_source_repo.add_raw_data_ref(
                    data_source_id,
                    ref,
                    session=session
                )

                # 3. 更新统计信息
                data_source.add_raw_data(
                    data_id=data_id,
                    data_type=data_type,
                    title=ref.title,
                    url=ref.url,
                    snippet=ref.snippet,
                    added_by=added_by
                )

                await self.data_source_repo.update_statistics(
                    data_source_id,
                    data_source.total_raw_data_count,
                    data_source.scheduled_data_count,
                    data_source.instant_data_count,
                    session=session
                )

                logger.info(
                    f"✅ 添加原始数据到数据源: {data_id} ({data_type}) → {data_source_id} "
                    f"(当前状态: {current_status})"
                )

                return True

            except Exception as e:
                logger.error(f"❌ 添加原始数据失败（事务回滚）: {str(e)}")
                raise

    async def remove_raw_data_from_source(
        self,
        data_source_id: str,
        data_id: str,
        data_type: str,
        removed_by: str
    ) -> bool:
        """从数据源移除原始数据

        v1.5.2: 不再自动修改数据状态，状态由用户手动控制

        Args:
            data_source_id: 数据源ID
            data_id: 原始数据ID
            data_type: 数据类型（scheduled或instant）
            removed_by: 移除者

        Returns:
            是否移除成功

        Raises:
            ValueError: 如果数据源不存在或不可编辑
        """
        # 验证数据源
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_edit():
            raise ValueError(
                f"Cannot remove data from data source in status '{data_source.status.value}'"
            )

        # v1.5.0: 统一雪花ID后，data_type直接决定集合
        if data_type == "scheduled":
            collection = self.search_results_collection
        elif data_type == "instant":
            collection = self.instant_search_results_collection
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        # 获取当前状态（用于日志）
        raw_data_doc = await collection.find_one({"_id": data_id})
        current_status = raw_data_doc.get("status", "pending") if raw_data_doc else "unknown"

        # v1.5.1: 使用兼容的事务上下文（支持standalone和replica set）
        async with self._transaction_context() as session:
            try:
                # v1.5.2: 不再修改原始数据状态
                # 1. 从数据源引用列表移除
                await self.data_source_repo.remove_raw_data_ref(
                    data_source_id,
                    data_id,
                    session=session
                )

                # 2. 更新统计信息
                data_source.remove_raw_data(data_id, removed_by)

                await self.data_source_repo.update_statistics(
                    data_source_id,
                    data_source.total_raw_data_count,
                    data_source.scheduled_data_count,
                    data_source.instant_data_count,
                    session=session
                )

                logger.info(
                    f"✅ 从数据源移除原始数据: {data_id} ({data_type}) ← {data_source_id} "
                    f"(当前状态: {current_status})"
                )

                return True

            except Exception as e:
                logger.error(f"❌ 移除原始数据失败（事务回滚）: {str(e)}")
                raise

    # ==========================================
    # 数据源状态管理（带事务）
    # ==========================================

    async def confirm_data_source(
        self,
        data_source_id: str,
        confirmed_by: str
    ) -> bool:
        """确定数据源

        状态转换：DRAFT → CONFIRMED
        v1.5.2: 不再自动修改原始数据状态，状态由用户手动控制

        Args:
            data_source_id: 数据源ID
            confirmed_by: 确定者

        Returns:
            是否确定成功

        Raises:
            ValueError: 如果数据源不存在或不可确定
        """
        # 验证数据源
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_confirm():
            raise ValueError(
                f"Cannot confirm data source in status '{data_source.status.value}' "
                f"or with no raw data (count: {data_source.total_raw_data_count})"
            )

        # v1.5.1: 使用兼容的事务上下文（支持standalone和replica set）
        async with self._transaction_context() as session:
            try:
                # 1. 更新数据源状态 → CONFIRMED
                data_source.confirm(confirmed_by)

                await self.data_source_repo.update(
                    data_source_id,
                    {
                        "status": data_source.status.value,
                        "confirmed_by": data_source.confirmed_by,
                        "confirmed_at": data_source.confirmed_at,
                        "updated_by": data_source.updated_by
                    },
                    session=session
                )

                # v1.5.2: 不再修改原始数据状态
                # 2. 获取原始数据ID列表（用于存档）
                scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                instant_ids = data_source.get_raw_data_ids_by_type("instant")

                # 3. 【存档】存档原始数据到独立表
                archived_count = 0

                # 3.1 存档scheduled类型数据
                for data_id in scheduled_ids:
                    try:
                        raw_doc = await self.search_results_collection.find_one(
                            {"_id": data_id},
                            session=session
                        )

                        if raw_doc:
                            search_result = self._doc_to_search_result(raw_doc)
                            archived_data = ArchivedData.from_search_result(
                                search_result=search_result,
                                data_source_id=data_source_id,
                                archived_by=confirmed_by,
                                archived_reason="confirm"
                            )
                            await self.archived_data_repo.create(archived_data, session=session)
                            archived_count += 1
                        else:
                            logger.warning(f"⚠️  原始数据不存在，跳过存档: {data_id} (scheduled)")

                    except Exception as e:
                        logger.error(f"❌ 存档scheduled数据失败: {data_id}, 错误: {str(e)}")
                        # 继续处理其他数据，不中断整个流程

                # 3.2 存档instant类型数据
                for data_id in instant_ids:
                    try:
                        raw_doc = await self.instant_search_results_collection.find_one(
                            {"_id": data_id},
                            session=session
                        )

                        if raw_doc:
                            instant_result = self._doc_to_instant_search_result(raw_doc)
                            archived_data = ArchivedData.from_instant_search_result(
                                instant_result=instant_result,
                                data_source_id=data_source_id,
                                archived_by=confirmed_by,
                                archived_reason="confirm"
                            )
                            await self.archived_data_repo.create(archived_data, session=session)
                            archived_count += 1
                        else:
                            logger.warning(f"⚠️  原始数据不存在，跳过存档: {data_id} (instant)")

                    except Exception as e:
                        logger.error(f"❌ 存档instant数据失败: {data_id}, 错误: {str(e)}")
                        # 继续处理其他数据，不中断整个流程

                logger.info(
                    f"✅ 确定数据源: {data_source_id} "
                    f"(存档了 {archived_count} 条数据: "
                    f"{len(scheduled_ids)} 条scheduled + {len(instant_ids)} 条instant)"
                )

                return True

            except Exception as e:
                logger.error(f"❌ 确定数据源失败（事务回滚）: {str(e)}")
                raise

    async def revert_data_source_to_draft(
        self,
        data_source_id: str,
        reverted_by: str
    ) -> bool:
        """恢复数据源为草稿

        状态转换：CONFIRMED → DRAFT
        v1.5.2: 不再自动修改原始数据状态，状态由用户手动控制

        Args:
            data_source_id: 数据源ID
            reverted_by: 操作者

        Returns:
            是否恢复成功

        Raises:
            ValueError: 如果数据源不存在或不可恢复
        """
        # 验证数据源
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        if not data_source.can_revert_to_draft():
            raise ValueError(
                f"Cannot revert data source in status '{data_source.status.value}' to draft"
            )

        # v1.5.1: 使用兼容的事务上下文（支持standalone和replica set）
        async with self._transaction_context() as session:
            try:
                # 1. 更新数据源状态 → DRAFT
                data_source.revert_to_draft(reverted_by)

                await self.data_source_repo.update(
                    data_source_id,
                    {
                        "status": data_source.status.value,
                        "confirmed_by": None,
                        "confirmed_at": None,
                        "updated_by": data_source.updated_by
                    },
                    session=session
                )

                # v1.5.2: 不再修改原始数据状态
                # 2. 获取数据统计（用于日志）
                scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                instant_ids = data_source.get_raw_data_ids_by_type("instant")

                logger.info(
                    f"✅ 恢复数据源为草稿: {data_source_id} "
                    f"(包含 {len(scheduled_ids)} 条scheduled数据, "
                    f"{len(instant_ids)} 条instant数据)"
                )

                return True

            except Exception as e:
                logger.error(f"❌ 恢复数据源失败（事务回滚）: {str(e)}")
                raise

    async def delete_data_source(
        self,
        data_source_id: str,
        deleted_by: str
    ) -> bool:
        """删除数据源

        v1.5.2: 不再自动修改原始数据状态，状态由用户手动控制

        Args:
            data_source_id: 数据源ID
            deleted_by: 删除者

        Returns:
            是否删除成功

        Raises:
            ValueError: 如果数据源不存在
        """
        # 验证数据源
        data_source = await self.get_data_source(data_source_id)
        if not data_source:
            raise ValueError(f"Data source '{data_source_id}' not found")

        # v1.5.1: 使用兼容的事务上下文（支持standalone和replica set）
        async with self._transaction_context() as session:
            try:
                # v1.5.2: 不再修改原始数据状态
                # 获取数据统计（用于日志）
                scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                instant_ids = data_source.get_raw_data_ids_by_type("instant")

                # 删除数据源
                await self.data_source_repo.delete(data_source_id, session=session)

                logger.info(
                    f"✅ 删除数据源: {data_source_id} "
                    f"(状态: {data_source.status.value}, "
                    f"包含 {len(scheduled_ids)} 条scheduled + {len(instant_ids)} 条instant数据)"
                )

                return True

            except Exception as e:
                logger.error(f"❌ 删除数据源失败（事务回滚）: {str(e)}")
                raise

    # ==========================================
    # 批量操作
    # ==========================================

    async def batch_archive_raw_data(
        self,
        data_ids: List[str],
        data_type: str,
        updated_by: str
    ) -> Dict[str, Any]:
        """批量留存原始数据

        状态更新：任意状态 → archived

        Args:
            data_ids: 原始数据ID列表
            data_type: 数据类型（scheduled或instant）
            updated_by: 更新者

        Returns:
            操作结果统计
        """
        if data_type == "scheduled":
            collection = self.search_results_collection
        elif data_type == "instant":
            collection = self.instant_search_results_collection
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        result = await collection.update_many(
            {"_id": {"$in": data_ids}},
            {
                "$set": {
                    "status": "archived",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(
            f"✅ 批量留存原始数据: {result.modified_count}/{len(data_ids)} 条 ({data_type})"
        )

        return {
            "total": len(data_ids),
            "updated": result.modified_count,
            "status": "archived"
        }

    async def batch_delete_raw_data(
        self,
        data_ids: List[str],
        data_type: str,
        deleted_by: str
    ) -> Dict[str, Any]:
        """批量软删除原始数据

        状态更新：任意状态 → deleted

        Args:
            data_ids: 原始数据ID列表
            data_type: 数据类型（scheduled或instant）
            deleted_by: 删除者

        Returns:
            操作结果统计
        """
        if data_type == "scheduled":
            collection = self.search_results_collection
        elif data_type == "instant":
            collection = self.instant_search_results_collection
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        result = await collection.update_many(
            {"_id": {"$in": data_ids}},
            {
                "$set": {
                    "status": "deleted",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(
            f"✅ 批量删除原始数据: {result.modified_count}/{len(data_ids)} 条 ({data_type})"
        )

        return {
            "total": len(data_ids),
            "updated": result.modified_count,
            "status": "deleted"
        }

    # ==========================================
    # 存档数据查询
    # ==========================================

    async def get_archived_data(
        self,
        data_source_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[ArchivedData], int]:
        """获取数据源的存档数据（分页）

        Args:
            data_source_id: 数据源ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            (存档数据列表, 总数) 元组
        """
        archived_list, total = await self.archived_data_repo.find_with_pagination(
            data_source_id=data_source_id,
            page=page,
            page_size=page_size
        )

        logger.info(
            f"📊 查询存档数据: 数据源={data_source_id}, "
            f"页码={page}/{((total + page_size - 1) // page_size)}, "
            f"返回={len(archived_list)}条, 总数={total}条"
        )

        return archived_list, total

    async def get_archived_data_statistics(
        self,
        data_source_id: str
    ) -> Dict[str, Any]:
        """获取数据源的存档统计信息

        Args:
            data_source_id: 数据源ID

        Returns:
            统计信息字典
        """
        stats = await self.archived_data_repo.get_statistics(data_source_id)

        logger.info(
            f"📊 查询存档统计: 数据源={data_source_id}, "
            f"总数={stats.get('total_count', 0)}条, "
            f"scheduled={stats.get('scheduled_count', 0)}条, "
            f"instant={stats.get('instant_count', 0)}条"
        )

        return stats

    # ==========================================
    # 内部辅助方法
    # ==========================================

    def _doc_to_search_result(self, doc: Dict[str, Any]) -> SearchResult:
        """将MongoDB文档转换为SearchResult实体

        v1.5.0: 统一雪花ID处理

        Args:
            doc: MongoDB文档（来自search_results集合）

        Returns:
            SearchResult实体
        """
        # v1.5.0: 所有ID都是雪花格式（字符串）
        doc_id = doc.get("id", "")
        task_id = doc.get("task_id", "")

        # 转换日期字段
        published_date = doc.get("published_date")
        if isinstance(published_date, str):
            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))

        created_at = doc.get("created_at", datetime.utcnow())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        processed_at = doc.get("processed_at")
        if isinstance(processed_at, str):
            processed_at = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))

        # 转换状态枚举
        status_value = doc.get("status", "pending")
        try:
            status = ResultStatus(status_value)
        except ValueError:
            status = ResultStatus.PENDING

        return SearchResult(
            id=doc_id,  # v1.5.0: 直接使用雪花ID（字符串）
            task_id=task_id,  # v1.5.0: 直接使用雪花ID（字符串）
            # 核心字段
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),
            # 元数据
            source=doc.get("source", "web"),
            published_date=published_date,
            author=doc.get("author"),
            language=doc.get("language"),
            # Firecrawl字段
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            article_tag=doc.get("article_tag"),
            article_published_time=doc.get("article_published_time"),
            source_url=doc.get("source_url"),
            http_status_code=doc.get("http_status_code"),
            search_position=doc.get("search_position"),
            metadata=doc.get("metadata", {}),
            # 状态
            status=status,
            created_at=created_at,
            processed_at=processed_at,
            # 测试标记
            is_test_data=doc.get("is_test_data", False)
        )

    def _doc_to_instant_search_result(self, doc: Dict[str, Any]) -> InstantSearchResult:
        """将MongoDB文档转换为InstantSearchResult实体

        Args:
            doc: MongoDB文档（来自instant_search_results集合）

        Returns:
            InstantSearchResult实体
        """
        # 转换日期字段
        published_date = doc.get("published_date")
        if isinstance(published_date, str):
            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))

        first_found_at = doc.get("first_found_at", datetime.utcnow())
        if isinstance(first_found_at, str):
            first_found_at = datetime.fromisoformat(first_found_at.replace('Z', '+00:00'))

        last_found_at = doc.get("last_found_at", datetime.utcnow())
        if isinstance(last_found_at, str):
            last_found_at = datetime.fromisoformat(last_found_at.replace('Z', '+00:00'))

        created_at = doc.get("created_at", datetime.utcnow())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        updated_at = doc.get("updated_at", datetime.utcnow())
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))

        # 转换状态枚举
        status_value = doc.get("status", "pending")
        try:
            status = InstantSearchResultStatus(status_value)
        except ValueError:
            status = InstantSearchResultStatus.PENDING

        return InstantSearchResult(
            id=doc.get("id", ""),
            task_id=doc.get("task_id", ""),
            # 核心字段
            title=doc.get("title", ""),
            url=doc.get("url", ""),
            content=doc.get("content", ""),
            snippet=doc.get("snippet"),
            # 去重和规范化
            content_hash=doc.get("content_hash", ""),
            url_normalized=doc.get("url_normalized", ""),
            # Firecrawl字段
            markdown_content=doc.get("markdown_content"),
            html_content=doc.get("html_content"),
            # 元数据
            source=doc.get("source", "web"),
            published_date=published_date,
            author=doc.get("author"),
            language=doc.get("language"),
            metadata=doc.get("metadata", {}),
            # 状态
            status=status,
            # 发现统计
            first_found_at=first_found_at,
            last_found_at=last_found_at,
            found_count=doc.get("found_count", 1),
            unique_searches=doc.get("unique_searches", 1),
            # 时间戳
            created_at=created_at,
            updated_at=updated_at
        )
