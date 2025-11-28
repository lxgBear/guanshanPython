"""
用户档案管理服务 (MongoDB 版本)

提供档案的创建、查询、更新功能,以及快照创建逻辑。

职责:
1. 档案的 CRUD 操作
2. 从 news_results 创建快照
3. 批量添加档案条目
4. 档案详情查询（包含所有条目）

版本: v2.0.0 (MongoDB)
日期: 2025-11-17
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.infrastructure.database.mongo_nl_user_archive_repository import MongoNLUserArchiveRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_id

logger = logging.getLogger(__name__)


class MongoArchiveService:
    """档案管理服务 (MongoDB版本)

    处理用户档案的创建、查询、更新等核心业务逻辑。
    所有数据存储在 MongoDB 的 user_archives 集合中。

    Example:
        >>> service = MongoArchiveService()
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
        self.archive_repo = MongoNLUserArchiveRepository()
        # 使用MongoDB database直接访问news_results集合
        self.db = None

        logger.info("MongoArchiveService 初始化完成")

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
                "archive_id": str,
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
            # 获取MongoDB数据库连接
            if self.db is None:
                self.db = await get_mongodb_database()

            # 为每个条目创建快照并准备数据
            archive_items = []
            for idx, item in enumerate(items):
                news_result_id = item.get("news_result_id")
                if not news_result_id:
                    logger.warning(f"条目 {idx} 缺少 news_result_id，跳过")
                    continue

                # 🆕 优先从 user_edited_results 读取完整快照
                edited_record = await self.db["user_edited_results"].find_one({
                    "news_result_id": news_result_id,
                    "user_id": user_id
                })

                snapshot = None
                edited_title = item.get("edited_title")
                edited_summary = item.get("edited_summary")

                if edited_record and "snapshot" in edited_record:
                    # 🆕 使用 user_edited_results 中的完整快照
                    user_snapshot = edited_record["snapshot"]

                    # 转换为档案快照格式
                    snapshot = {
                        "original_title": user_snapshot.get("title"),
                        "original_content": user_snapshot.get("preview"),
                        "category": user_snapshot.get("category"),
                        "published_at": user_snapshot.get("publish_time"),
                        "source": user_snapshot.get("source"),
                        "media_urls": [],
                        # 🆕 新增字段：保存url和markdown_content
                        "url": user_snapshot.get("url"),
                        "markdown_content": user_snapshot.get("markdown_content")
                    }

                    # 优先使用已保存的编辑内容
                    edited_title = edited_title or edited_record.get("edited_title")
                    edited_summary = edited_summary or edited_record.get("edited_summary")

                    logger.info(
                        f"从 user_edited_results 读取完整数据: "
                        f"news_result_id={news_result_id}, "
                        f"has_url={bool(snapshot.get('url'))}, "
                        f"has_markdown={bool(snapshot.get('markdown_content'))}"
                    )
                else:
                    # 降级: 从 news_results 创建快照
                    snapshot = await self._create_snapshot(news_result_id)

                    logger.info(
                        f"从 news_results 创建快照 (未找到编辑记录): "
                        f"news_result_id={news_result_id}"
                    )

                if not snapshot:
                    logger.warning(f"为 news_result_id={news_result_id} 创建快照失败，跳过")
                    continue

                # 准备条目数据
                archive_items.append({
                    "id": generate_id(),  # 生成唯一ID（雪花ID）
                    "news_result_id": news_result_id,
                    "edited_title": edited_title,
                    "edited_summary": edited_summary,
                    "user_notes": item.get("user_notes"),
                    "user_rating": item.get("user_rating"),
                    "snapshot_data": snapshot,
                    "display_order": idx,
                    "created_at": datetime.utcnow()
                })

            if not archive_items:
                raise ValueError("没有有效的档案条目可创建")

            # 创建档案（包含所有条目）
            archive_id = await self.archive_repo.create(
                user_id=user_id,
                archive_name=archive_name,
                items=archive_items,
                description=description,
                tags=tags,
                search_log_id=search_log_id
            )

            if not archive_id:
                raise Exception("创建档案失败")

            logger.info(f"档案创建成功: archive_id={archive_id}, items_count={len(archive_items)}")

            # 返回结果
            return {
                "archive_id": archive_id,
                "archive_name": archive_name,
                "items_count": len(archive_items),
                "created_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"创建档案失败: {e}", exc_info=True)
            raise

    async def get_archive(self, archive_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """获取档案详情（包含所有条目）

        Args:
            archive_id: 档案ID (ObjectId字符串)
            user_id: 用户ID（可选，用于权限验证）

        Returns:
            档案详情字典，不存在时返回 None:
            {
                "archive_id": str,
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
            >>> archive = await service.get_archive(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     user_id=1001
            ... )
            >>> print(archive["archive_name"])
        """
        logger.info(f"获取档案详情: archive_id={archive_id}, user_id={user_id}")

        try:
            # 获取档案
            archive = await self.archive_repo.get_by_id(archive_id)

            if not archive:
                logger.warning(f"档案不存在: archive_id={archive_id}")
                return None

            # 权限验证（如果提供了 user_id）
            if user_id is not None and archive.get("user_id") != user_id:
                logger.warning(f"用户 {user_id} 无权访问档案 {archive_id}")
                return None

            # 构建条目列表（添加显示字段）
            items = []
            for item in archive.get("items", []):
                snapshot = item.get("snapshot_data", {})

                # 获取显示标题和内容（优先使用编辑版本）
                display_title = item.get("edited_title") or snapshot.get("original_title", "未知标题")
                display_content = item.get("edited_summary") or snapshot.get("original_content", "")

                items.append({
                    "id": item.get("id"),
                    "news_result_id": item.get("news_result_id"),
                    "title": display_title,
                    "content": display_content,
                    "edited_title": item.get("edited_title"),
                    "edited_summary": item.get("edited_summary"),
                    "user_notes": item.get("user_notes"),
                    "user_rating": item.get("user_rating"),
                    "category": snapshot.get("category"),
                    "source": snapshot.get("source"),
                    "url": snapshot.get("url"),  # ✅ 添加URL字段
                    "published_at": snapshot.get("published_at"),
                    "media_urls": snapshot.get("media_urls", []),
                    "display_order": item.get("display_order", 0),
                    "created_at": item.get("created_at").isoformat() if item.get("created_at") else None
                })

            # 返回完整档案信息
            return {
                "archive_id": archive.get("_id"),
                "user_id": archive.get("user_id"),
                "archive_name": archive.get("archive_name"),
                "description": archive.get("description"),
                "tags": archive.get("tags", []),
                "search_log_id": archive.get("search_log_id"),
                "items_count": archive.get("items_count", 0),
                "items": items,
                "created_at": archive.get("created_at").isoformat() if archive.get("created_at") else None,
                "updated_at": archive.get("updated_at").isoformat() if archive.get("updated_at") else None
            }

        except Exception as e:
            logger.error(f"获取档案详情失败: {e}", exc_info=True)
            raise

    async def list_archives(
        self,
        user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取档案列表

        Args:
            user_id: 用户ID（可选，不传则查询所有档案）
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            档案列表

        Example:
            >>> # 查询所有档案
            >>> archives = await service.list_archives(limit=10)
            >>> # 查询指定用户的档案
            >>> archives = await service.list_archives(user_id=1001, limit=10)
        """
        logger.info(f"查询档案列表: user_id={user_id}, limit={limit}, offset={offset}")

        try:
            archives = await self.archive_repo.get_by_user(
                user_id=user_id,
                limit=limit,
                offset=offset
            )

            results = [
                {
                    "archive_id": archive.get("_id"),
                    "user_id": archive.get("user_id"),
                    "archive_name": archive.get("archive_name"),
                    "description": archive.get("description"),
                    "tags": archive.get("tags", []),
                    "search_log_id": archive.get("search_log_id"),
                    "items_count": archive.get("items_count", 0),
                    "created_at": archive.get("created_at").isoformat() if archive.get("created_at") else None,
                    "updated_at": archive.get("updated_at").isoformat() if archive.get("updated_at") else None
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
        archive_id: str,
        archive_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID (ObjectId字符串)
            archive_name: 新的档案名称
            description: 新的描述
            tags: 新的标签列表

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await service.update_archive(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     archive_name="新档案名称"
            ... )
        """
        logger.info(f"更新档案: archive_id={archive_id}")

        try:
            # 检查档案是否存在
            archive = await self.archive_repo.get_by_id(archive_id)
            if not archive:
                logger.info(f"档案不存在: archive_id={archive_id}")
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

    async def delete_archive(self, archive_id: str) -> bool:
        """删除档案（包括所有条目）

        Args:
            archive_id: 档案ID (ObjectId字符串)

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await service.delete_archive(
            ...     archive_id="507f1f77bcf86cd799439011"
            ... )
        """
        logger.info(f"删除档案: archive_id={archive_id}")

        try:
            # 检查档案是否存在
            archive = await self.archive_repo.get_by_id(archive_id)
            if not archive:
                logger.info(f"档案不存在: archive_id={archive_id}")
                return False

            # 执行删除
            success = await self.archive_repo.delete(archive_id)

            return success

        except Exception as e:
            logger.error(f"删除档案失败: {e}", exc_info=True)
            raise

    async def _create_snapshot(self, news_result_id: str) -> Optional[Dict[str, Any]]:
        """创建新闻结果的快照

        从 MongoDB search_results 集合中获取完整数据并创建快照。

        Args:
            news_result_id: 新闻结果ID（雪花算法ID，在MongoDB中存储为字符串）

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
            if self.db is None:
                self.db = await get_mongodb_database()

            # ✅ v2.3.0: 从 search_results 集合查询（而不是 news_results）
            # 这是 NL Search 服务写入搜索结果的集合
            result = await self.db["search_results"].find_one({"_id": news_result_id})

            if not result:
                logger.warning(f"未找到搜索结果: news_result_id={news_result_id}")
                return None

            # ✅ v2.3.0: 从 search_results 扁平结构提取快照数据
            # search_results 是扁平结构，不像 news_results 有嵌套字段
            snapshot = {
                "original_title": result.get("title"),
                # 优先使用 markdown_content，降级到 snippet
                "original_content": result.get("markdown_content") or result.get("snippet"),
                "category": None,  # search_results 没有 category 字段
                "published_at": result.get("article_published_time"),
                "source": result.get("source"),
                "media_urls": [],  # search_results 没有 media_urls 字段
                # ✅ 新增字段：保存 URL 和 markdown_content
                "url": result.get("url"),
                "markdown_content": result.get("markdown_content")
            }

            logger.debug(f"创建快照成功: news_result_id={news_result_id}, has_url={bool(snapshot.get('url'))}")
            return snapshot

        except Exception as e:
            logger.error(f"创建快照失败: news_result_id={news_result_id}, error={e}")
            return None


# 创建全局服务实例（单例模式）
mongo_archive_service = MongoArchiveService()
