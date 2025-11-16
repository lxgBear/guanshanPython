"""
NL Search 数据仓库 (简化版 - MariaDB)

设计说明:
- 使用 SQLAlchemy 异步 ORM
- JSON 字段存储 LLM 分析结果
- 支持分页查询和关键词搜索
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from sqlalchemy import text, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.entities.nl_search import NLSearchLog
from src.infrastructure.database.connection import get_mariadb_session
from src.utils.logger import get_logger

logger = get_logger(__name__)


class NLSearchLogRepository:
    """自然语言搜索记录仓库 (简化版)

    提供 NL Search 数据的 CRUD 操作和查询功能。

    Example:
        >>> repo = NLSearchLogRepository()
        >>> log_id = await repo.create(
        ...     query_text="最近有哪些AI技术突破",
        ...     llm_analysis={"intent": "tech_news", "keywords": ["AI"]}
        ... )
        >>> log = await repo.get_by_id(log_id)
        >>> print(log.query_text)
        最近有哪些AI技术突破
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """初始化仓库

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
        query_text: str,
        llm_analysis: Optional[Dict[str, Any]] = None
    ) -> int:
        """创建搜索记录

        Args:
            query_text: 用户输入的自然语言查询
            llm_analysis: LLM 分析结果 (可选)

        Returns:
            int: 创建的记录 ID

        Raises:
            Exception: 数据库操作失败

        Example:
            >>> log_id = await repo.create(
            ...     query_text="AI技术突破",
            ...     llm_analysis={"intent": "tech_news"}
            ... )
        """
        session = await self._get_session()

        try:
            # 准备 JSON 数据
            llm_analysis_json = json.dumps(llm_analysis) if llm_analysis else None

            # 插入记录
            query = text("""
                INSERT INTO nl_search_logs (query_text, llm_analysis, created_at)
                VALUES (:query_text, :llm_analysis, NOW())
            """)

            result = await session.execute(
                query,
                {
                    "query_text": query_text,
                    "llm_analysis": llm_analysis_json
                }
            )
            await session.commit()

            log_id = result.lastrowid
            logger.info(f"创建 NL 搜索记录成功: ID={log_id}, query='{query_text[:30]}...'")
            return log_id

        except Exception as e:
            await session.rollback()
            logger.error(f"创建 NL 搜索记录失败: {e}")
            raise

    async def get_by_id(self, log_id: int) -> Optional[NLSearchLog]:
        """根据 ID 获取搜索记录

        Args:
            log_id: 搜索记录 ID

        Returns:
            Optional[NLSearchLog]: 搜索记录，如果不存在则返回 None

        Example:
            >>> log = await repo.get_by_id(123456)
            >>> if log:
            ...     print(log.query_text)
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT id, query_text, llm_analysis, created_at
                FROM nl_search_logs
                WHERE id = :log_id
            """)

            result = await session.execute(query, {"log_id": log_id})
            row = result.fetchone()

            if not row:
                return None

            # 解析 JSON 字段
            llm_analysis = json.loads(row.llm_analysis) if row.llm_analysis else None

            return NLSearchLog(
                id=row.id,
                query_text=row.query_text,
                llm_analysis=llm_analysis,
                created_at=row.created_at
            )

        except Exception as e:
            logger.error(f"查询 NL 搜索记录失败: {e}")
            raise

    async def update_llm_analysis(
        self,
        log_id: int,
        llm_analysis: Dict[str, Any]
    ) -> bool:
        """更新 LLM 解析结果

        Args:
            log_id: 搜索记录 ID
            llm_analysis: 新的 LLM 分析结果

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update_llm_analysis(
            ...     log_id=123456,
            ...     llm_analysis={"intent": "updated", "confidence": 0.99}
            ... )
        """
        session = await self._get_session()

        try:
            query = text("""
                UPDATE nl_search_logs
                SET llm_analysis = :llm_analysis
                WHERE id = :log_id
            """)

            result = await session.execute(
                query,
                {
                    "log_id": log_id,
                    "llm_analysis": json.dumps(llm_analysis)
                }
            )
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"更新 NL 搜索记录 LLM 分析成功: ID={log_id}")
            return success

        except Exception as e:
            await session.rollback()
            logger.error(f"更新 NL 搜索记录失败: {e}")
            raise

    async def get_recent(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> List[NLSearchLog]:
        """获取最近的搜索记录

        Args:
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[NLSearchLog]: 搜索记录列表

        Example:
            >>> logs = await repo.get_recent(limit=10, offset=0)
            >>> for log in logs:
            ...     print(log.query_text)
        """
        session = await self._get_session()

        try:
            query = text("""
                SELECT id, query_text, llm_analysis, created_at
                FROM nl_search_logs
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            result = await session.execute(
                query,
                {"limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            logs = []
            for row in rows:
                llm_analysis = json.loads(row.llm_analysis) if row.llm_analysis else None
                logs.append(NLSearchLog(
                    id=row.id,
                    query_text=row.query_text,
                    llm_analysis=llm_analysis,
                    created_at=row.created_at
                ))

            return logs

        except Exception as e:
            logger.error(f"查询最近搜索记录失败: {e}")
            raise

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[NLSearchLog]:
        """根据关键词搜索 (MySQL JSON 查询)

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[NLSearchLog]: 匹配的搜索记录列表

        Example:
            >>> logs = await repo.search_by_keyword("AI", limit=10)
        """
        session = await self._get_session()

        try:
            # MySQL JSON_CONTAINS 查询
            query = text("""
                SELECT id, query_text, llm_analysis, created_at
                FROM nl_search_logs
                WHERE JSON_CONTAINS(
                    llm_analysis->'$.keywords',
                    JSON_QUOTE(:keyword)
                )
                OR query_text LIKE :query_pattern
                ORDER BY created_at DESC
                LIMIT :limit
            """)

            result = await session.execute(
                query,
                {
                    "keyword": keyword,
                    "query_pattern": f"%{keyword}%",
                    "limit": limit
                }
            )
            rows = result.fetchall()

            logs = []
            for row in rows:
                llm_analysis = json.loads(row.llm_analysis) if row.llm_analysis else None
                logs.append(NLSearchLog(
                    id=row.id,
                    query_text=row.query_text,
                    llm_analysis=llm_analysis,
                    created_at=row.created_at
                ))

            return logs

        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            raise

    async def count_total(self) -> int:
        """统计总记录数

        Returns:
            int: 总记录数

        Example:
            >>> total = await repo.count_total()
            >>> print(f"共有 {total} 条搜索记录")
        """
        session = await self._get_session()

        try:
            query = text("SELECT COUNT(*) as total FROM nl_search_logs")
            result = await session.execute(query)
            row = result.fetchone()
            return row.total if row else 0

        except Exception as e:
            logger.error(f"统计记录数失败: {e}")
            raise

    async def delete_old_records(self, days: int = 30) -> int:
        """删除旧记录

        Args:
            days: 保留天数，删除超过此天数的记录

        Returns:
            int: 删除的记录数

        Example:
            >>> deleted = await repo.delete_old_records(days=30)
            >>> print(f"删除了 {deleted} 条旧记录")
        """
        session = await self._get_session()

        try:
            query = text("""
                DELETE FROM nl_search_logs
                WHERE created_at < DATE_SUB(NOW(), INTERVAL :days DAY)
            """)

            result = await session.execute(query, {"days": days})
            await session.commit()

            deleted_count = result.rowcount
            logger.info(f"删除 {deleted_count} 条旧的 NL 搜索记录 (>{days}天)")
            return deleted_count

        except Exception as e:
            await session.rollback()
            logger.error(f"删除旧记录失败: {e}")
            raise

    async def delete_by_id(self, log_id: int) -> bool:
        """根据 ID 删除记录

        Args:
            log_id: 搜索记录 ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete_by_id(123456)
        """
        session = await self._get_session()

        try:
            query = text("DELETE FROM nl_search_logs WHERE id = :log_id")
            result = await session.execute(query, {"log_id": log_id})
            await session.commit()

            success = result.rowcount > 0
            if success:
                logger.info(f"删除 NL 搜索记录成功: ID={log_id}")
            return success

        except Exception as e:
            await session.rollback()
            logger.error(f"删除记录失败: {e}")
            raise
