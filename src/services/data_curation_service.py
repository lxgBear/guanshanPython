"""数据整编服务

提供数据源管理的核心业务逻辑，包括：
- 数据源CRUD操作
- 状态同步管理（MongoDB事务）
- 原始数据引用管理
- 批量操作支持
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.data_source import (
    DataSource,
    DataSourceStatus,
    RawDataReference
)
from src.core.domain.entities.search_result import SearchResult
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.infrastructure.database.data_source_repositories import DataSourceRepository
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
        self.search_results_collection = db.search_results
        self.instant_search_results_collection = db.instant_search_results

    # ==========================================
    # 数据源基础操作
    # ==========================================

    async def create_data_source(
        self,
        title: str,
        description: str,
        created_by: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataSource:
        """创建数据源（草稿状态）

        Args:
            title: 数据源标题
            description: 数据源描述
            created_by: 创建者
            tags: 标签列表（可选）
            metadata: 扩展元数据（可选）

        Returns:
            创建的数据源实体
        """
        data_source = DataSource(
            title=title,
            description=description,
            created_by=created_by,
            updated_by=created_by,
            tags=tags or [],
            metadata=metadata or {}
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
            limit=limit,
            skip=skip
        )

        total = await self.data_source_repo.count(
            created_by=created_by,
            status=status,
            source_type=source_type,
            start_date=start_date,
            end_date=end_date
        )

        return data_sources, total

    async def update_data_source_info(
        self,
        data_source_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        updated_by: str = ""
    ) -> bool:
        """更新数据源基础信息（仅草稿状态可编辑）

        Args:
            data_source_id: 数据源ID
            title: 新标题（可选）
            description: 新描述（可选）
            tags: 新标签列表（可选）
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

        状态同步：原始数据 pending/archived → processing

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

        # 获取原始数据
        if data_type == "scheduled":
            collection = self.search_results_collection
        elif data_type == "instant":
            collection = self.instant_search_results_collection
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        raw_data_doc = await collection.find_one({"id": data_id})
        if not raw_data_doc:
            raise ValueError(f"Raw data '{data_id}' not found in {data_type} collection")

        # 检查当前状态
        current_status = raw_data_doc.get("status", "pending")
        if current_status not in ["pending", "archived"]:
            raise ValueError(
                f"Cannot add raw data with status '{current_status}' to data source. "
                f"Only 'pending' or 'archived' data can be added."
            )

        # 使用事务同步更新
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 1. 更新原始数据状态 → processing
                    await collection.update_one(
                        {"id": data_id},
                        {
                            "$set": {
                                "status": "processing",
                                "updated_at": datetime.utcnow()
                            }
                        },
                        session=session
                    )

                    # 2. 添加到数据源引用列表
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
                        f"(状态: {current_status} → processing)"
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

        状态同步：原始数据 processing → archived

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

        # 获取原始数据集合
        if data_type == "scheduled":
            collection = self.search_results_collection
        elif data_type == "instant":
            collection = self.instant_search_results_collection
        else:
            raise ValueError(f"Invalid data type: {data_type}")

        # 使用事务同步更新
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 1. 更新原始数据状态 → archived
                    await collection.update_one(
                        {"id": data_id},
                        {
                            "$set": {
                                "status": "archived",
                                "updated_at": datetime.utcnow()
                            }
                        },
                        session=session
                    )

                    # 2. 从数据源引用列表移除
                    await self.data_source_repo.remove_raw_data_ref(
                        data_source_id,
                        data_id,
                        session=session
                    )

                    # 3. 更新统计信息
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
                        f"(状态: processing → archived)"
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
        状态同步：原始数据 processing → completed

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

        # 使用事务同步更新
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
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

                    # 2. 批量更新原始数据状态 → completed
                    scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                    instant_ids = data_source.get_raw_data_ids_by_type("instant")

                    if scheduled_ids:
                        await self.search_results_collection.update_many(
                            {"id": {"$in": scheduled_ids}},
                            {
                                "$set": {
                                    "status": "completed",
                                    "processed_at": datetime.utcnow()
                                }
                            },
                            session=session
                        )

                    if instant_ids:
                        await self.instant_search_results_collection.update_many(
                            {"id": {"$in": instant_ids}},
                            {
                                "$set": {
                                    "status": "completed",
                                    "updated_at": datetime.utcnow()
                                }
                            },
                            session=session
                        )

                    logger.info(
                        f"✅ 确定数据源: {data_source_id} "
                        f"(更新了 {len(scheduled_ids)} 条scheduled数据, "
                        f"{len(instant_ids)} 条instant数据 → completed)"
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
        状态同步：原始数据 completed → processing

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

        # 使用事务同步更新
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
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

                    # 2. 批量更新原始数据状态 → processing
                    scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                    instant_ids = data_source.get_raw_data_ids_by_type("instant")

                    if scheduled_ids:
                        await self.search_results_collection.update_many(
                            {"id": {"$in": scheduled_ids}},
                            {
                                "$set": {
                                    "status": "processing",
                                    "processed_at": None
                                }
                            },
                            session=session
                        )

                    if instant_ids:
                        await self.instant_search_results_collection.update_many(
                            {"id": {"$in": instant_ids}},
                            {
                                "$set": {
                                    "status": "processing",
                                    "updated_at": datetime.utcnow()
                                }
                            },
                            session=session
                        )

                    logger.info(
                        f"✅ 恢复数据源为草稿: {data_source_id} "
                        f"(更新了 {len(scheduled_ids)} 条scheduled数据, "
                        f"{len(instant_ids)} 条instant数据 → processing)"
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

        状态同步：
        - 草稿状态：原始数据 processing → archived
        - 已确定状态：原始数据保持 completed（不变）

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

        # 判断是否需要更新原始数据状态
        need_status_sync = (data_source.status == DataSourceStatus.DRAFT)

        # 使用事务同步更新
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                try:
                    # 1. 如果是草稿状态，批量更新原始数据状态 → archived
                    if need_status_sync:
                        scheduled_ids = data_source.get_raw_data_ids_by_type("scheduled")
                        instant_ids = data_source.get_raw_data_ids_by_type("instant")

                        if scheduled_ids:
                            await self.search_results_collection.update_many(
                                {"id": {"$in": scheduled_ids}},
                                {
                                    "$set": {
                                        "status": "archived",
                                        "processed_at": datetime.utcnow()
                                    }
                                },
                                session=session
                            )

                        if instant_ids:
                            await self.instant_search_results_collection.update_many(
                                {"id": {"$in": instant_ids}},
                                {
                                    "$set": {
                                        "status": "archived",
                                        "updated_at": datetime.utcnow()
                                    }
                                },
                                session=session
                            )

                        logger.info(
                            f"📊 更新原始数据状态: {len(scheduled_ids)} 条scheduled数据, "
                            f"{len(instant_ids)} 条instant数据 → archived"
                        )

                    # 2. 删除数据源
                    await self.data_source_repo.delete(data_source_id, session=session)

                    logger.info(
                        f"✅ 删除数据源: {data_source_id} "
                        f"(状态: {data_source.status.value}, "
                        f"状态同步: {'是' if need_status_sync else '否'})"
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
            {"id": {"$in": data_ids}},
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
            {"id": {"$in": data_ids}},
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
