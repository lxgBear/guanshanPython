"""
用户档案仓储层

提供档案的 CRUD 操作和查询功能。

设计说明:
- 使用 SQLAlchemy 异步 ORM
- 实现档案的创建、查询、更新、删除
- 支持用户维度的档案列表查询
"""
from typing import List, Optional
from datetime import datetime
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.entities.nl_search import NLUserArchive
from src.infrastructure.database.connection import get_mariadb_session
from src.utils.logger import get_logger

logger = get_logger(__name__)


class NLUserArchiveRepository:
    """用户档案仓储

    提供档案数据的 CRUD 操作和查询功能。

    Example:
        >>> repo = NLUserArchiveRepository()
        >>> archive_id = await repo.create(
        ...     user_id=1001,
        ...     archive_name="AI技术突破汇总",
        ...     description="2024年重要AI技术突破",
        ...     tags=["AI", "技术"]
        ... )
        >>> archive = await repo.get_by_id(archive_id)
        >>> print(archive.archive_name)
        AI技术突破汇总
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
        user_id: int,
        archive_name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_log_id: Optional[int] = None
    ) -> Optional[int]:
        """创建档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            description: 档案描述（可选）
            tags: 标签列表（可选）
            search_log_id: 关联的搜索记录ID（可选）

        Returns:
            Optional[int]: 创建的档案ID，失败时返回 None

        Example:
            >>> archive_id = await repo.create(
            ...     user_id=1001,
            ...     archive_name="AI技术突破",
            ...     tags=["AI", "技术"]
            ... )
        """
        try:
            session = await self._get_session()

            # 准备 JSON 数据
            tags_json = json.dumps(tags) if tags else None

            # 插入档案记录
            query = text("""
                INSERT INTO nl_user_archives
                (user_id, archive_name, description, tags, search_log_id, items_count, created_at, updated_at)
                VALUES (:user_id, :archive_name, :description, :tags, :search_log_id, 0, NOW(), NOW())
            """)

            result = await session.execute(
                query,
                {
                    "user_id": user_id,
                    "archive_name": archive_name,
                    "description": description,
                    "tags": tags_json,
                    "search_log_id": search_log_id
                }
            )
            await session.commit()

            archive_id = result.lastrowid
            logger.info(f"创建用户档案成功: ID={archive_id}, user={user_id}, name='{archive_name}'")
            return archive_id

        except Exception as e:
            logger.error(f"创建用户档案失败: {e}")
            await session.rollback()
            return None

    async def get_by_id(self, archive_id: int) -> Optional[NLUserArchive]:
        """根据ID获取档案

        Args:
            archive_id: 档案ID

        Returns:
            Optional[NLUserArchive]: 档案实体，不存在时返回 None

        Example:
            >>> archive = await repo.get_by_id(1)
            >>> if archive:
            ...     print(archive.archive_name)
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT id, user_id, archive_name, description, tags, search_log_id,
                       items_count, created_at, updated_at
                FROM nl_user_archives
                WHERE id = :archive_id
            """)

            result = await session.execute(query, {"archive_id": archive_id})
            row = result.fetchone()

            if not row:
                return None

            # 解析 JSON 字段
            tags = json.loads(row.tags) if row.tags else None

            return NLUserArchive(
                id=row.id,
                user_id=row.user_id,
                archive_name=row.archive_name,
                description=row.description,
                tags=tags,
                search_log_id=row.search_log_id,
                items_count=row.items_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )

        except Exception as e:
            logger.error(f"查询档案失败: {e}")
            raise

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[NLUserArchive]:
        """获取用户的档案列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[NLUserArchive]: 档案列表

        Example:
            >>> archives = await repo.get_by_user(user_id=1001, limit=10)
            >>> for archive in archives:
            ...     print(archive.archive_name)
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT id, user_id, archive_name, description, tags, search_log_id,
                       items_count, created_at, updated_at
                FROM nl_user_archives
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            result = await session.execute(
                query,
                {"user_id": user_id, "limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            archives = []
            for row in rows:
                tags = json.loads(row.tags) if row.tags else None
                archives.append(NLUserArchive(
                    id=row.id,
                    user_id=row.user_id,
                    archive_name=row.archive_name,
                    description=row.description,
                    tags=tags,
                    search_log_id=row.search_log_id,
                    items_count=row.items_count,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                ))

            return archives

        except Exception as e:
            logger.error(f"查询用户档案列表失败: {e}")
            raise

    async def update(
        self,
        archive_id: int,
        archive_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID
            archive_name: 新的档案名称（可选）
            description: 新的描述（可选）
            tags: 新的标签列表（可选）

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update(
            ...     archive_id=1,
            ...     archive_name="新档案名称",
            ...     description="新描述"
            ... )
        """
        try:
            session = await self._get_session()

            # 构建动态更新语句
            update_fields = []
            params = {"archive_id": archive_id}

            if archive_name is not None:
                update_fields.append("archive_name = :archive_name")
                params["archive_name"] = archive_name

            if description is not None:
                update_fields.append("description = :description")
                params["description"] = description

            if tags is not None:
                update_fields.append("tags = :tags")
                params["tags"] = json.dumps(tags)

            if not update_fields:
                logger.warning("更新档案时未提供任何字段")
                return False

            # 添加 updated_at 字段
            update_fields.append("updated_at = NOW()")

            query = text(f"""
                UPDATE nl_user_archives
                SET {', '.join(update_fields)}
                WHERE id = :archive_id
            """)

            result = await session.execute(query, params)
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"更新档案成功: ID={archive_id}")
            return success

        except Exception as e:
            logger.error(f"更新档案失败: {e}")
            await session.rollback()
            return False

    async def delete(self, archive_id: int) -> bool:
        """删除档案（级联删除档案条目）

        Args:
            archive_id: 档案ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete(archive_id=1)
        """
        session = await self._get_session()

        try:
            query = text("DELETE FROM nl_user_archives WHERE id = :archive_id")
            result = await session.execute(query, {"archive_id": archive_id})
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"删除档案成功: ID={archive_id}")
            return success

        except Exception as e:
            await session.rollback()
            logger.error(f"删除档案失败: {e}")
            raise

    async def count_by_user(self, user_id: int) -> int:
        """统计用户的档案总数

        Args:
            user_id: 用户ID

        Returns:
            int: 档案总数

        Example:
            >>> total = await repo.count_by_user(user_id=1001)
            >>> print(f"用户共有 {total} 个档案")
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT COUNT(*) as total
                FROM nl_user_archives
                WHERE user_id = :user_id
            """)
            result = await session.execute(query, {"user_id": user_id})
            row = result.fetchone()
            return row.total if row else 0

        except Exception as e:
            logger.error(f"统计用户档案数失败: {e}")
            raise
