"""
用户档案条目仓储层

提供档案条目的 CRUD 操作和查询功能。

设计说明:
- 使用 SQLAlchemy 异步 ORM
- 实现档案条目的创建、查询、更新、删除
- 支持批量创建（档案创建场景）
- 快照数据使用 JSON 字段存储
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.entities.nl_search import NLUserSelection
from src.infrastructure.database.connection import get_mariadb_session
from src.utils.logger import get_logger

logger = get_logger(__name__)


class NLUserSelectionRepository:
    """用户档案条目仓储

    提供档案条目数据的 CRUD 操作和查询功能。

    Example:
        >>> repo = NLUserSelectionRepository()
        >>> selection_id = await repo.create(
        ...     archive_id=1,
        ...     user_id=1001,
        ...     news_result_id="507f1f77bcf86cd799439011",
        ...     snapshot_data={"original_title": "GPT-5发布"},
        ...     edited_title="GPT-5重磅发布"
        ... )
        >>> selection = await repo.get_by_id(selection_id)
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """初始化仓储

        Args:
            session: 可选的数据库会话，如果不提供则自动创建
        """
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """获取数据库会话"""
        if self._session is None:
            return await get_mariadb_session()
        return self._session

    async def create(
        self,
        archive_id: int,
        user_id: int,
        news_result_id: str,
        snapshot_data: Dict[str, Any],
        edited_title: Optional[str] = None,
        edited_summary: Optional[str] = None,
        user_notes: Optional[str] = None,
        user_rating: Optional[int] = None,
        display_order: int = 0
    ) -> Optional[int]:
        """创建档案条目

        Args:
            archive_id: 所属档案ID
            user_id: 用户ID
            news_result_id: 新闻结果ID（MongoDB ObjectId）
            snapshot_data: 原始数据快照
            edited_title: 用户编辑后的标题（可选）
            edited_summary: 用户编辑后的摘要（可选）
            user_notes: 用户备注（可选）
            user_rating: 用户评分 1-5（可选）
            display_order: 显示顺序（可选）

        Returns:
            Optional[int]: 创建的条目ID，失败时返回 None

        Example:
            >>> selection_id = await repo.create(
            ...     archive_id=1,
            ...     user_id=1001,
            ...     news_result_id="507f1f77bcf86cd799439011",
            ...     snapshot_data={"original_title": "GPT-5发布"},
            ...     edited_title="GPT-5重磅发布"
            ... )
        """
        try:
            session = await self._get_session()

            # 插入条目记录
            query = text("""
                INSERT INTO nl_user_selections
                (archive_id, user_id, news_result_id, edited_title, edited_summary,
                 user_notes, user_rating, snapshot_data, display_order, created_at)
                VALUES (:archive_id, :user_id, :news_result_id, :edited_title, :edited_summary,
                        :user_notes, :user_rating, :snapshot_data, :display_order, NOW())
            """)

            result = await session.execute(
                query,
                {
                    "archive_id": archive_id,
                    "user_id": user_id,
                    "news_result_id": news_result_id,
                    "edited_title": edited_title,
                    "edited_summary": edited_summary,
                    "user_notes": user_notes,
                    "user_rating": user_rating,
                    "snapshot_data": json.dumps(snapshot_data),
                    "display_order": display_order
                }
            )
            await session.commit()

            selection_id = result.lastrowid
            logger.info(f"创建档案条目成功: ID={selection_id}, archive={archive_id}, news={news_result_id}")
            return selection_id

        except Exception as e:
            logger.error(f"创建档案条目失败: {e}")
            await session.rollback()
            return None

    async def create_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[int]:
        """批量创建档案条目

        Args:
            items: 条目数据列表，每个字典包含:
                - archive_id: 档案ID
                - user_id: 用户ID
                - news_result_id: 新闻结果ID
                - snapshot_data: 快照数据
                - edited_title: 编辑标题（可选）
                - edited_summary: 编辑摘要（可选）
                - user_notes: 用户备注（可选）
                - user_rating: 用户评分（可选）
                - display_order: 显示顺序（可选，默认0）

        Returns:
            List[int]: 创建的条目ID列表

        Example:
            >>> ids = await repo.create_batch([
            ...     {
            ...         "archive_id": 1,
            ...         "user_id": 1001,
            ...         "news_result_id": "507f1f77bcf86cd799439011",
            ...         "snapshot_data": {"original_title": "新闻1"},
            ...         "edited_title": "编辑标题1"
            ...     },
            ...     {
            ...         "archive_id": 1,
            ...         "user_id": 1001,
            ...         "news_result_id": "507f1f77bcf86cd799439012",
            ...         "snapshot_data": {"original_title": "新闻2"}
            ...     }
            ... ])
        """
        if not items:
            return []

        try:
            session = await self._get_session()
            created_ids = []

            # 逐个插入（为了获取每个ID）
            for item in items:
                query = text("""
                    INSERT INTO nl_user_selections
                    (archive_id, user_id, news_result_id, edited_title, edited_summary,
                     user_notes, user_rating, snapshot_data, display_order, created_at)
                    VALUES (:archive_id, :user_id, :news_result_id, :edited_title, :edited_summary,
                            :user_notes, :user_rating, :snapshot_data, :display_order, NOW())
                """)

                result = await session.execute(
                    query,
                    {
                        "archive_id": item["archive_id"],
                        "user_id": item["user_id"],
                        "news_result_id": item["news_result_id"],
                        "edited_title": item.get("edited_title"),
                        "edited_summary": item.get("edited_summary"),
                        "user_notes": item.get("user_notes"),
                        "user_rating": item.get("user_rating"),
                        "snapshot_data": json.dumps(item["snapshot_data"]),
                        "display_order": item.get("display_order", 0)
                    }
                )
                created_ids.append(result.lastrowid)

            await session.commit()
            logger.info(f"批量创建档案条目成功: {len(created_ids)} 条")
            return created_ids

        except Exception as e:
            logger.error(f"批量创建档案条目失败: {e}")
            await session.rollback()
            return []

    async def get_by_id(self, selection_id: int) -> Optional[NLUserSelection]:
        """根据ID获取档案条目

        Args:
            selection_id: 条目ID

        Returns:
            Optional[NLUserSelection]: 条目实体，不存在时返回 None

        Example:
            >>> selection = await repo.get_by_id(1)
            >>> if selection:
            ...     print(selection.display_title)
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT id, archive_id, user_id, news_result_id, edited_title, edited_summary,
                       user_notes, user_rating, snapshot_data, display_order, created_at
                FROM nl_user_selections
                WHERE id = :selection_id
            """)

            result = await session.execute(query, {"selection_id": selection_id})
            row = result.fetchone()

            if not row:
                return None

            # 解析 JSON 字段
            snapshot_data = json.loads(row.snapshot_data)

            return NLUserSelection(
                id=row.id,
                archive_id=row.archive_id,
                user_id=row.user_id,
                news_result_id=row.news_result_id,
                edited_title=row.edited_title,
                edited_summary=row.edited_summary,
                user_notes=row.user_notes,
                user_rating=row.user_rating,
                snapshot_data=snapshot_data,
                display_order=row.display_order,
                created_at=row.created_at
            )

        except Exception as e:
            logger.error(f"查询档案条目失败: {e}")
            raise

    async def get_by_archive(
        self,
        archive_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[NLUserSelection]:
        """获取档案的所有条目

        Args:
            archive_id: 档案ID
            limit: 返回数量限制（可选）
            offset: 分页偏移量

        Returns:
            List[NLUserSelection]: 条目列表（按 display_order 排序）

        Example:
            >>> selections = await repo.get_by_archive(archive_id=1)
            >>> for selection in selections:
            ...     print(selection.display_title)
        """
        session = await self._get_session()

        try:
            # 构建查询语句
            base_query = """
                SELECT id, archive_id, user_id, news_result_id, edited_title, edited_summary,
                       user_notes, user_rating, snapshot_data, display_order, created_at
                FROM nl_user_selections
                WHERE archive_id = :archive_id
                ORDER BY display_order ASC, created_at ASC
            """

            if limit is not None:
                base_query += " LIMIT :limit OFFSET :offset"
                params = {"archive_id": archive_id, "limit": limit, "offset": offset}
            else:
                params = {"archive_id": archive_id}

            query = text(base_query)
            result = await session.execute(query, params)
            rows = result.fetchall()

            selections = []
            for row in rows:
                snapshot_data = json.loads(row.snapshot_data)
                selections.append(NLUserSelection(
                    id=row.id,
                    archive_id=row.archive_id,
                    user_id=row.user_id,
                    news_result_id=row.news_result_id,
                    edited_title=row.edited_title,
                    edited_summary=row.edited_summary,
                    user_notes=row.user_notes,
                    user_rating=row.user_rating,
                    snapshot_data=snapshot_data,
                    display_order=row.display_order,
                    created_at=row.created_at
                ))

            return selections

        except Exception as e:
            logger.error(f"查询档案条目列表失败: {e}")
            raise

    async def update(
        self,
        selection_id: int,
        edited_title: Optional[str] = None,
        edited_summary: Optional[str] = None,
        user_notes: Optional[str] = None,
        user_rating: Optional[int] = None,
        display_order: Optional[int] = None
    ) -> bool:
        """更新档案条目

        Args:
            selection_id: 条目ID
            edited_title: 新的编辑标题（可选）
            edited_summary: 新的编辑摘要（可选）
            user_notes: 新的用户备注（可选）
            user_rating: 新的用户评分（可选）
            display_order: 新的显示顺序（可选）

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update(
            ...     selection_id=1,
            ...     edited_title="新标题",
            ...     user_rating=5
            ... )
        """
        try:
            session = await self._get_session()

            # 构建动态更新语句
            update_fields = []
            params = {"selection_id": selection_id}

            if edited_title is not None:
                update_fields.append("edited_title = :edited_title")
                params["edited_title"] = edited_title

            if edited_summary is not None:
                update_fields.append("edited_summary = :edited_summary")
                params["edited_summary"] = edited_summary

            if user_notes is not None:
                update_fields.append("user_notes = :user_notes")
                params["user_notes"] = user_notes

            if user_rating is not None:
                update_fields.append("user_rating = :user_rating")
                params["user_rating"] = user_rating

            if display_order is not None:
                update_fields.append("display_order = :display_order")
                params["display_order"] = display_order

            if not update_fields:
                logger.warning("更新档案条目时未提供任何字段")
                return False

            query = text(f"""
                UPDATE nl_user_selections
                SET {', '.join(update_fields)}
                WHERE id = :selection_id
            """)

            result = await session.execute(query, params)
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"更新档案条目成功: ID={selection_id}")
            return success

        except Exception as e:
            logger.error(f"更新档案条目失败: {e}")
            await session.rollback()
            return False

    async def delete(self, selection_id: int) -> bool:
        """删除档案条目

        Args:
            selection_id: 条目ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete(selection_id=1)
        """
        session = await self._get_session()

        try:
            query = text("DELETE FROM nl_user_selections WHERE id = :selection_id")
            result = await session.execute(query, {"selection_id": selection_id})
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"删除档案条目成功: ID={selection_id}")
            return success

        except Exception as e:
            await session.rollback()
            logger.error(f"删除档案条目失败: {e}")
            raise

    async def delete_by_archive(self, archive_id: int) -> int:
        """删除档案的所有条目

        Args:
            archive_id: 档案ID

        Returns:
            int: 删除的条目数量

        Example:
            >>> deleted_count = await repo.delete_by_archive(archive_id=1)
        """
        session = await self._get_session()

        try:
            query = text("DELETE FROM nl_user_selections WHERE archive_id = :archive_id")
            result = await session.execute(query, {"archive_id": archive_id})
            await session.commit()

            deleted_count = result.rowcount
            logger.info(f"删除档案所有条目成功: archive={archive_id}, count={deleted_count}")
            return deleted_count

        except Exception as e:
            await session.rollback()
            logger.error(f"删除档案所有条目失败: {e}")
            raise

    async def count_by_archive(self, archive_id: int) -> int:
        """统计档案的条目总数

        Args:
            archive_id: 档案ID

        Returns:
            int: 条目总数

        Example:
            >>> total = await repo.count_by_archive(archive_id=1)
            >>> print(f"档案共有 {total} 条")
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT COUNT(*) as total
                FROM nl_user_selections
                WHERE archive_id = :archive_id
            """)
            result = await session.execute(query, {"archive_id": archive_id})
            row = result.fetchone()
            return row.total if row else 0

        except Exception as e:
            logger.error(f"统计档案条目数失败: {e}")
            raise
