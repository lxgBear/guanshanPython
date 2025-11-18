"""
用户档案管理服务

提供档案的创建、查询、更新功能,以及快照创建逻辑。

职责:
1. 档案的 CRUD 操作
2. 从 news_results 创建快照
3. 批量添加档案条目
4. 档案详情查询（包含所有条目）

版本: v1.0.0
日期: 2025-11-17
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.infrastructure.database.nl_user_archive_repository import NLUserArchiveRepository
from src.infrastructure.database.nl_user_selection_repository import NLUserSelectionRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.core.domain.entities.nl_search import NLUserArchive, NLUserSelection

logger = logging.getLogger(__name__)


class ArchiveService:
    """档案管理服务

    处理用户档案的创建、查询、更新等核心业务逻辑。

    Example:
        >>> service = ArchiveService()
        >>> archive_id = await service.create_archive(
        ...     user_id=1001,
        ...     archive_name="AI技术突破汇总",
        ...     items=[
        ...         {
        ...             "news_result_id": "507f1f77bcf86cd799439011",
        ...             "edited_title": "GPT-5发布"
        ...         }
        ...     ]
        ... )
    """

    def __init__(self):
        """初始化服务"""
        self.archive_repo = NLUserArchiveRepository()
        self.selection_repo = NLUserSelectionRepository()
        # 使用MongoDB database直接访问news_results集合
        self.db = None

        logger.info("ArchiveService 初始化完成")

    async def create_archive(
        self,
        user_id: int,
        archive_name: str,
        items: List[Dict[str, Any]],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_log_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """创建档案

        Args:
            user_id: 用户ID
            archive_name: 档案名称
            items: 档案条目列表，每个字典包含:
                - news_result_id: 新闻结果ID (必填)
                - edited_title: 编辑后的标题 (可选)
                - edited_summary: 编辑后的摘要 (可选)
                - user_notes: 用户备注 (可选)
                - user_rating: 用户评分 1-5 (可选)
            description: 档案描述
            tags: 档案标签列表
            search_log_id: 关联的搜索记录ID

        Returns:
            包含档案信息的字典:
            {
                "archive_id": int,
                "archive_name": str,
                "items_count": int,
                "created_at": str
            }

        Raises:
            ValueError: 输入验证失败
            Exception: 创建过程中的其他错误

        Example:
            >>> archive = await service.create_archive(
            ...     user_id=1001,
            ...     archive_name="AI技术突破",
            ...     items=[
            ...         {
            ...             "news_result_id": "507f1f77bcf86cd799439011",
            ...             "edited_title": "GPT-5发布"
            ...         }
            ...     ]
            ... )
        """
        # 验证输入
        if not archive_name or not archive_name.strip():
            raise ValueError("档案名称不能为空")

        if not items or len(items) == 0:
            raise ValueError("档案条目不能为空")

        archive_name = archive_name.strip()
        logger.info(f"开始创建档案: user={user_id}, name='{archive_name}', items={len(items)}")

        try:
            # 1. 创建档案主记录
            archive_id = await self.archive_repo.create(
                user_id=user_id,
                archive_name=archive_name,
                description=description,
                tags=tags,
                search_log_id=search_log_id
            )

            if not archive_id:
                raise Exception("创建档案失败")

            logger.info(f"档案创建成功: archive_id={archive_id}")

            # 2. 为每个条目创建快照并添加到档案
            selection_items = []
            for idx, item in enumerate(items):
                news_result_id = item.get("news_result_id")
                if not news_result_id:
                    logger.warning(f"条目 {idx} 缺少 news_result_id，跳过")
                    continue

                # 创建快照
                snapshot = await self._create_snapshot(news_result_id)
                if not snapshot:
                    logger.warning(f"为 news_result_id={news_result_id} 创建快照失败，跳过")
                    continue

                # 准备条目数据
                selection_items.append({
                    "archive_id": archive_id,
                    "user_id": user_id,
                    "news_result_id": news_result_id,
                    "snapshot_data": snapshot,
                    "edited_title": item.get("edited_title"),
                    "edited_summary": item.get("edited_summary"),
                    "user_notes": item.get("user_notes"),
                    "user_rating": item.get("user_rating"),
                    "display_order": idx
                })

            # 3. 批量创建档案条目
            if selection_items:
                created_ids = await self.selection_repo.create_batch(selection_items)
                logger.info(f"批量创建档案条目成功: {len(created_ids)} 条")
            else:
                logger.warning("没有有效的档案条目可创建")

            # 4. 返回结果
            return {
                "archive_id": archive_id,
                "archive_name": archive_name,
                "items_count": len(selection_items),
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"创建档案失败: {e}", exc_info=True)
            raise

    async def get_archive(self, archive_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """获取档案详情（包含所有条目）

        Args:
            archive_id: 档案ID
            user_id: 用户ID（可选，用于权限验证）

        Returns:
            档案详情字典，不存在时返回 None:
            {
                "archive_id": int,
                "user_id": int,
                "archive_name": str,
                "description": str,
                "tags": List[str],
                "search_log_id": int,
                "items_count": int,
                "items": List[Dict],
                "created_at": str,
                "updated_at": str
            }

        Example:
            >>> archive = await service.get_archive(archive_id=1, user_id=1001)
            >>> print(archive["archive_name"])
        """
        logger.info(f"获取档案详情: archive_id={archive_id}, user_id={user_id}")

        try:
            # 获取档案主信息
            archive = await self.archive_repo.get_by_id(archive_id)

            if not archive:
                logger.warning(f"档案不存在: archive_id={archive_id}")
                return None

            # 权限验证（如果提供了 user_id）
            if user_id is not None and archive.user_id != user_id:
                logger.warning(f"用户 {user_id} 无权访问档案 {archive_id}")
                return None

            # 获取档案所有条目
            selections = await self.selection_repo.get_by_archive(archive_id)

            # 构建条目列表
            items = [
                {
                    "id": sel.id,
                    "news_result_id": sel.news_result_id,
                    "title": sel.display_title,
                    "content": sel.display_content,
                    "edited_title": sel.edited_title,
                    "edited_summary": sel.edited_summary,
                    "user_notes": sel.user_notes,
                    "user_rating": sel.user_rating,
                    "original_title": sel.original_title,
                    "original_content": sel.original_content,
                    "category": sel.category,
                    "source": sel.source,
                    "media_urls": sel.media_urls,
                    "published_at": sel.published_at,
                    "display_order": sel.display_order,
                    "created_at": sel.created_at.isoformat() if sel.created_at else None
                }
                for sel in selections
            ]

            # 返回完整档案信息
            return {
                "archive_id": archive.id,
                "user_id": archive.user_id,
                "archive_name": archive.archive_name,
                "description": archive.description,
                "tags": archive.tags or [],
                "search_log_id": archive.search_log_id,
                "items_count": archive.items_count,
                "items": items,
                "created_at": archive.created_at.isoformat() if archive.created_at else None,
                "updated_at": archive.updated_at.isoformat() if archive.updated_at else None
            }

        except Exception as e:
            logger.error(f"获取档案详情失败: {e}", exc_info=True)
            raise

    async def list_archives(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户的档案列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            档案列表

        Example:
            >>> archives = await service.list_archives(user_id=1001, limit=10)
        """
        logger.info(f"查询用户档案列表: user_id={user_id}, limit={limit}, offset={offset}")

        try:
            archives = await self.archive_repo.get_by_user(
                user_id=user_id,
                limit=limit,
                offset=offset
            )

            results = [
                {
                    "archive_id": archive.id,
                    "archive_name": archive.archive_name,
                    "description": archive.description,
                    "tags": archive.tags or [],
                    "search_log_id": archive.search_log_id,
                    "items_count": archive.items_count,
                    "created_at": archive.created_at.isoformat() if archive.created_at else None,
                    "updated_at": archive.updated_at.isoformat() if archive.updated_at else None
                }
                for archive in archives
            ]

            logger.info(f"返回 {len(results)} 个档案")
            return results

        except Exception as e:
            logger.error(f"查询档案列表失败: {e}", exc_info=True)
            raise

    async def update_archive(
        self,
        archive_id: int,
        user_id: int,
        archive_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID
            user_id: 用户ID（用于权限验证）
            archive_name: 新的档案名称
            description: 新的描述
            tags: 新的标签列表

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await service.update_archive(
            ...     archive_id=1,
            ...     user_id=1001,
            ...     archive_name="新档案名称"
            ... )
        """
        logger.info(f"更新档案: archive_id={archive_id}, user_id={user_id}")

        try:
            # 权限验证
            archive = await self.archive_repo.get_by_id(archive_id)
            if not archive or archive.user_id != user_id:
                logger.warning(f"用户 {user_id} 无权更新档案 {archive_id}")
                return False

            # 执行更新
            success = await self.archive_repo.update(
                archive_id=archive_id,
                archive_name=archive_name,
                description=description,
                tags=tags
            )

            return success

        except Exception as e:
            logger.error(f"更新档案失败: {e}", exc_info=True)
            raise

    async def delete_archive(self, archive_id: int, user_id: int) -> bool:
        """删除档案（级联删除所有条目）

        Args:
            archive_id: 档案ID
            user_id: 用户ID（用于权限验证）

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await service.delete_archive(archive_id=1, user_id=1001)
        """
        logger.info(f"删除档案: archive_id={archive_id}, user_id={user_id}")

        try:
            # 权限验证
            archive = await self.archive_repo.get_by_id(archive_id)
            if not archive or archive.user_id != user_id:
                logger.warning(f"用户 {user_id} 无权删除档案 {archive_id}")
                return False

            # 执行删除（外键级联删除档案条目）
            success = await self.archive_repo.delete(archive_id)

            return success

        except Exception as e:
            logger.error(f"删除档案失败: {e}", exc_info=True)
            raise

    async def _create_snapshot(self, news_result_id: str) -> Optional[Dict[str, Any]]:
        """创建新闻结果的快照

        从 MongoDB news_results 集合中获取完整数据并创建快照。

        Args:
            news_result_id: 新闻结果ID（MongoDB ObjectId）

        Returns:
            快照数据字典，失败时返回 None

        Snapshot Structure:
            {
                "original_title": str,
                "original_content": str,
                "category": Dict[str, str],
                "published_at": str,
                "source": str,
                "media_urls": List[str]
            }
        """
        try:
            # 获取MongoDB数据库连接
            if not self.db:
                self.db = await get_mongodb_database()

            # 从 MongoDB 获取处理后的新闻结果
            from bson import ObjectId
            result = await self.db["news_results"].find_one({"_id": ObjectId(news_result_id)})

            if not result:
                logger.warning(f"未找到新闻结果: news_result_id={news_result_id}")
                return None

            # 提取快照数据（从news_results嵌套字段）
            news = result.get("news_results", {})
            if not news:
                logger.warning(f"新闻结果缺少news_results字段: news_result_id={news_result_id}")
                return None

            snapshot = {
                "original_title": news.get("title"),
                "original_content": news.get("content"),
                "category": news.get("category"),
                "published_at": news.get("published_at").isoformat() if news.get("published_at") else None,
                "source": news.get("source"),
                "media_urls": news.get("media_urls", [])
            }

            logger.debug(f"创建快照成功: news_result_id={news_result_id}")
            return snapshot

        except Exception as e:
            logger.error(f"创建快照失败: news_result_id={news_result_id}, error={e}")
            return None


# 创建全局服务实例（单例模式）
archive_service = ArchiveService()
