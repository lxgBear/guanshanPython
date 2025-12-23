"""
用户档案管理服务 (MongoDB 版本)

提供档案的创建、查询、更新功能,以及快照创建逻辑。

职责:
1. 档案的 CRUD 操作
2. 从 news_results 或 file_uploads 创建快照
3. 批量添加档案条目
4. 档案详情查询（包含所有条目）

版本: v2.5.4 (自动生成 user_summary)
日期: 2025-12-11

v2.5.4 更新:
- 新增 _generate_user_summary() 方法，自动生成档案条目汇总
- create_archive() 创建档案时自动生成 Markdown 格式的 user_summary
- 格式: # 档案标题 → ## 条目标题 + 来源 + 内容 + 分隔线

v2.5.1 更新:
- 修复 file_uploads 快照字段缺失问题
- 新增完整字段投影: file_size, mime_type, file_extension, uploaded_by 等
- 统一快照构建方法 _build_file_upload_snapshot()

v2.5.0 更新:
- 支持双数据源: file_uploads (用户上传) + news_results/search_results (新闻搜索)
- 自动检测ID类型: ObjectId格式 → file_uploads, 雪花ID → search_results
- 批量查询分离: 分别查询两个数据源以优化性能
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from bson import ObjectId

from src.infrastructure.database.mongo_nl_user_archive_repository import MongoNLUserArchiveRepository
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_id

logger = logging.getLogger(__name__)


# ==================== 数据源类型常量 ====================
SOURCE_TYPE_FILE_UPLOAD = "file_upload"
SOURCE_TYPE_NEWS = "news"
SOURCE_TYPE_UNKNOWN = "unknown"


def detect_source_type(item_id: str) -> str:
    """检测数据源类型

    根据ID格式自动判断数据来源:
    - ObjectId格式 (24位十六进制): file_uploads 集合
    - 雪花ID格式 (18-19位数字): search_results/news_results 集合

    Args:
        item_id: 条目ID字符串

    Returns:
        str: 数据源类型 (file_upload|news|unknown)

    Example:
        >>> detect_source_type("507f1f77bcf86cd799439011")  # ObjectId
        'file_upload'
        >>> detect_source_type("248728141926559744")  # 雪花ID
        'news'
    """
    if not item_id:
        return SOURCE_TYPE_UNKNOWN

    # ObjectId格式: 24位十六进制字符
    if re.match(r'^[a-fA-F0-9]{24}$', item_id):
        return SOURCE_TYPE_FILE_UPLOAD

    # 雪花ID格式: 18-19位纯数字
    if item_id.isdigit() and 17 <= len(item_id) <= 20:
        return SOURCE_TYPE_NEWS

    return SOURCE_TYPE_UNKNOWN


def classify_items_by_source(items: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """将条目按数据源分类

    Args:
        items: 条目列表，每个条目需包含 news_result_id 字段

    Returns:
        Tuple[List[str], List[str]]: (file_upload_ids, news_ids)

    Example:
        >>> items = [
        ...     {"news_result_id": "507f1f77bcf86cd799439011"},  # file_upload
        ...     {"news_result_id": "248728141926559744"}         # news
        ... ]
        >>> file_ids, news_ids = classify_items_by_source(items)
    """
    file_upload_ids = []
    news_ids = []

    for item in items:
        item_id = item.get("news_result_id")
        if not item_id:
            continue

        source_type = detect_source_type(item_id)
        if source_type == SOURCE_TYPE_FILE_UPLOAD:
            file_upload_ids.append(item_id)
        elif source_type == SOURCE_TYPE_NEWS:
            news_ids.append(item_id)
        else:
            # 未知类型默认归入 news（保持向后兼容）
            news_ids.append(item_id)
            logger.warning(f"无法识别ID类型: {item_id}，默认作为 news 处理")

    return file_upload_ids, news_ids


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

    def _generate_user_summary(
        self,
        archive_name: str,
        archive_items: List[Dict[str, Any]]
    ) -> str:
        """生成档案的 user_summary 字段 (v2.5.7)

        根据档案名称和条目列表自动生成格式化的 Markdown 总结。

        Args:
            archive_name: 档案名称
            archive_items: 档案条目列表，每个条目包含:
                - edited_title: 编辑后的标题
                - edited_summary: 编辑后的摘要
                - snapshot_data: 快照数据 (original_title, original_content, original_url)

        Returns:
            str: 格式化的 Markdown 总结

        格式:
            # 档案标题

            ## 1. 条目标题
            来源: https://xxx.com/article (仅当URL存在时显示)
            条目内容

            ---

            ## 2. 条目标题
            条目内容 (无URL时不显示来源行)

            ---
        """
        lines = [f"# {archive_name}", ""]

        for idx, item in enumerate(archive_items, start=1):
            snapshot = item.get("snapshot_data", {})

            # 获取标题：优先使用编辑版本，否则使用快照原始标题
            title = item.get("edited_title") or snapshot.get("original_title", "未知标题")

            # 获取URL：优先 original_url，回退到 url (v2.5.8 兼容不同数据源)
            url = snapshot.get("original_url") or snapshot.get("url")

            # 获取内容：优先使用编辑摘要，否则使用快照原始内容
            content = item.get("edited_summary") or snapshot.get("original_content", "")
            # 限制内容长度，避免过长
            if content and len(content) > 2000:
                content = content[:2000] + "..."

            # 构建条目
            lines.append(f"## {idx}. {title}")
            # 仅当URL存在时显示来源行
            if url:
                lines.append(f"来源: {url}")
            if content:
                lines.append(content)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

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

            # v2.5.0: 双数据源支持 - 分离 file_upload 和 news IDs
            all_item_ids = [item.get("news_result_id") for item in items if item.get("news_result_id")]

            if not all_item_ids:
                raise ValueError("没有有效的 news_result_id")

            # 按数据源分类 ID
            file_upload_ids, news_ids = classify_items_by_source(items)

            logger.info(
                f"数据源分类: file_uploads={len(file_upload_ids)}, "
                f"news={len(news_ids)}, total={len(all_item_ids)}"
            )

            # ==================== 批量查询 file_uploads ====================
            file_uploads_map = {}
            if file_upload_ids:
                file_uploads_map = await self._batch_fetch_file_uploads(file_upload_ids)

            # ==================== 批量查询 news 相关数据 ====================
            # 批量查询 user_edited_results（仅对 news IDs）
            edited_records_map = {}
            if news_ids:
                edited_records_cursor = self.db["user_edited_results"].find({
                    "news_result_id": {"$in": news_ids},
                    "user_id": user_id
                })
                edited_records_map = {
                    doc["news_result_id"]: doc
                    async for doc in edited_records_cursor
                }

            # 找出需要从 search_results 获取的 ID（未在 user_edited_results 中找到的）
            missing_news_ids = [nid for nid in news_ids if nid not in edited_records_map]

            # 批量查询 search_results
            search_results_map = {}
            if missing_news_ids:
                search_cursor = self.db["search_results"].find({
                    "_id": {"$in": missing_news_ids}
                })
                search_results_map = {
                    doc["_id"]: doc
                    async for doc in search_cursor
                }

            logger.info(
                f"批量查询完成: file_uploads={len(file_uploads_map)}, "
                f"edited_records={len(edited_records_map)}, "
                f"search_results={len(search_results_map)}, "
                f"total_items={len(items)}"
            )

            # 为每个条目创建快照并准备数据
            archive_items = []
            for idx, item in enumerate(items):
                news_result_id = item.get("news_result_id")
                if not news_result_id:
                    logger.warning(f"条目 {idx} 缺少 news_result_id，跳过")
                    continue

                snapshot = None
                edited_title = item.get("edited_title")
                edited_summary = item.get("edited_summary")

                # v2.5.0: 根据数据源类型选择快照来源
                source_type = detect_source_type(news_result_id)

                if source_type == SOURCE_TYPE_FILE_UPLOAD:
                    # ==================== 处理 file_uploads 数据源 ====================
                    snapshot = file_uploads_map.get(news_result_id)
                    if snapshot:
                        logger.debug(
                            f"从 file_uploads 获取快照: id={news_result_id}, "
                            f"title={snapshot.get('original_title', '')[:30]}"
                        )
                    else:
                        logger.warning(f"未找到 file_upload: id={news_result_id}")

                else:
                    # ==================== 处理 news 数据源 ====================
                    # 优先从 user_edited_results 获取
                    edited_record = edited_records_map.get(news_result_id)

                    if edited_record and "snapshot" in edited_record:
                        # 使用 user_edited_results 中的完整快照
                        user_snapshot = edited_record["snapshot"]

                        # 转换为档案快照格式
                        snapshot = {
                            "original_title": user_snapshot.get("title"),
                            "original_content": user_snapshot.get("preview"),
                            "category": user_snapshot.get("category"),
                            "published_at": user_snapshot.get("publish_time"),
                            "source": user_snapshot.get("source"),
                            "source_type": SOURCE_TYPE_NEWS,
                            "media_urls": [],
                            "url": user_snapshot.get("url"),
                            "markdown_content": user_snapshot.get("markdown_content")
                        }

                        # 优先使用已保存的编辑内容
                        edited_title = edited_title or edited_record.get("edited_title")
                        edited_summary = edited_summary or edited_record.get("edited_summary")

                        logger.debug(
                            f"从 user_edited_results 获取快照: id={news_result_id}"
                        )
                    else:
                        # 降级: 从 search_results 创建快照
                        search_result = search_results_map.get(news_result_id)
                        if search_result:
                            snapshot = {
                                "original_title": search_result.get("title"),
                                "original_content": search_result.get("markdown_content") or search_result.get("snippet"),
                                "category": None,
                                "published_at": search_result.get("article_published_time"),
                                "source": search_result.get("source"),
                                "source_type": SOURCE_TYPE_NEWS,
                                "media_urls": [],
                                "url": search_result.get("url"),
                                "markdown_content": search_result.get("markdown_content")
                            }
                            logger.debug(
                                f"从 search_results 获取快照: id={news_result_id}"
                            )
                        else:
                            logger.warning(
                                f"未找到 news_result: id={news_result_id}"
                            )

                if not snapshot:
                    logger.warning(f"为 id={news_result_id} 创建快照失败（source_type={source_type}），跳过")
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
                    "source_type": source_type,  # v2.5.0: 记录数据源类型
                    "display_order": idx,
                    "created_at": datetime.utcnow()
                })

            if not archive_items:
                raise ValueError("没有有效的档案条目可创建")

            # v2.5.4: 自动生成 user_summary
            user_summary = self._generate_user_summary(archive_name, archive_items)
            logger.info(f"生成 user_summary: length={len(user_summary)} chars")

            # 创建档案（包含所有条目）
            archive_id = await self.archive_repo.create(
                user_id=user_id,
                archive_name=archive_name,
                items=archive_items,
                description=description,
                tags=tags,
                search_log_id=search_log_id,
                user_summary=user_summary  # v2.5.4: 传入自动生成的总结
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
            # v2.5.2: 添加 generated_report 字段，处理空值和不存在情况
            generated_report = archive.get("generated_report")
            # 确保空字符串也被视为 None
            if generated_report is not None and isinstance(generated_report, str) and not generated_report.strip():
                generated_report = None

            # v2.5.3: 添加 user_summary 字段，用户上传的内容总结
            user_summary = archive.get("user_summary")
            if user_summary is not None and isinstance(user_summary, str) and not user_summary.strip():
                user_summary = None

            return {
                "archive_id": archive.get("_id"),
                "user_id": archive.get("user_id"),
                "archive_name": archive.get("archive_name"),
                "description": archive.get("description"),
                "tags": archive.get("tags", []),
                "search_log_id": archive.get("search_log_id"),
                "items_count": archive.get("items_count", 0),
                "items": items,
                "generated_report": generated_report,  # v2.5.2: AI生成的摘要报告
                "user_summary": user_summary,  # v2.5.3: 用户上传的内容总结
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

            # v2.5.2: 添加 generated_report 字段
            # v2.5.3: 添加 user_summary 字段
            results = []
            for archive in archives:
                # 处理 generated_report 空值
                generated_report = archive.get("generated_report")
                if generated_report is not None and isinstance(generated_report, str) and not generated_report.strip():
                    generated_report = None

                # v2.5.3: 处理 user_summary 空值
                user_summary = archive.get("user_summary")
                if user_summary is not None and isinstance(user_summary, str) and not user_summary.strip():
                    user_summary = None

                results.append({
                    "archive_id": archive.get("_id"),
                    "user_id": archive.get("user_id"),
                    "archive_name": archive.get("archive_name"),
                    "description": archive.get("description"),
                    "tags": archive.get("tags", []),
                    "search_log_id": archive.get("search_log_id"),
                    "items_count": archive.get("items_count", 0),
                    "generated_report": generated_report,  # v2.5.2: AI生成的摘要报告
                    "user_summary": user_summary,  # v2.5.3: 用户上传的内容总结
                    "created_at": archive.get("created_at").isoformat() if archive.get("created_at") else None,
                    "updated_at": archive.get("updated_at").isoformat() if archive.get("updated_at") else None
                })

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
        tags: Optional[List[str]] = None,
        user_summary: Optional[str] = None,
        generated_report: Optional[str] = None
    ) -> bool:
        """更新档案信息

        Args:
            archive_id: 档案ID (ObjectId字符串)
            archive_name: 新的档案名称
            description: 新的描述
            tags: 新的标签列表
            user_summary: 用户上传的内容总结 (v2.5.3新增)
            generated_report: AI生成的摘要报告 (v2.5.9新增)

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await service.update_archive(
            ...     archive_id="507f1f77bcf86cd799439011",
            ...     archive_name="新档案名称",
            ...     user_summary="用户自定义的档案内容总结...",
            ...     generated_report="AI生成的摘要报告..."
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
                tags=tags,
                user_summary=user_summary,
                generated_report=generated_report
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

    async def _create_file_upload_snapshot(self, file_id: str) -> Optional[Dict[str, Any]]:
        """创建用户上传文件的快照

        v2.5.0: 新增方法，从 MongoDB file_uploads 集合获取数据并创建快照。
        v2.5.1: 修复 - 添加完整字段查询，与 _batch_fetch_file_uploads 保持一致。

        Args:
            file_id: 文件ID（ObjectId格式的24位十六进制字符串）

        Returns:
            快照数据字典，失败时返回 None
        """
        try:
            # 获取MongoDB数据库连接
            if self.db is None:
                self.db = await get_mongodb_database()

            # v2.5.1: 完整的字段投影
            projection = {
                "file_id": 1,
                "title": 1,
                "content": 1,
                "original_filename": 1,
                "display_name": 1,
                "storage_url": 1,
                "storage_path": 1,
                "created_at": 1,
                "updated_at": 1,
                "tags": 1,
                "file_size": 1,
                "mime_type": 1,
                "file_extension": 1,
                "uploaded_by": 1,
                "category": 1,
                "status": 1,
                "_id": 0
            }

            # 尝试使用 file_id 字段查询
            result = await self.db["file_uploads"].find_one(
                {"file_id": file_id},
                projection
            )

            # 如果 file_id 查询失败，尝试使用 ObjectId 查询
            if not result:
                try:
                    projection_with_id = {**projection, "_id": 1}
                    del projection_with_id["_id"]  # 移除 _id: 0
                    result = await self.db["file_uploads"].find_one(
                        {"_id": ObjectId(file_id)},
                        projection
                    )
                except Exception:
                    pass  # ObjectId 转换失败，保持 result 为 None

            if not result:
                logger.warning(f"未找到文件上传记录: file_id={file_id}")
                return None

            # v2.5.1: 使用统一的快照构建方法
            snapshot = self._build_file_upload_snapshot(result, file_id)

            logger.debug(
                f"创建文件快照成功: file_id={file_id}, "
                f"title={snapshot.get('original_title', '')[:30]}..., "
                f"content_length={snapshot.get('full_content_length')}"
            )
            return snapshot

        except Exception as e:
            logger.error(f"创建文件快照失败: file_id={file_id}, error={e}")
            return None

    async def _batch_fetch_file_uploads(self, file_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取 file_uploads 数据

        v2.5.0: 新增方法，批量查询 file_uploads 集合。
        v2.5.1: 修复 - 添加完整字段查询，确保快照包含所有必要信息。

        Args:
            file_ids: 文件ID列表

        Returns:
            Dict[file_id, snapshot_data]: ID到快照的映射
        """
        if not file_ids:
            return {}

        try:
            if self.db is None:
                self.db = await get_mongodb_database()

            result_map = {}

            # v2.5.1: 完整的字段投影 - 包含所有必要的文件元数据
            projection = {
                "file_id": 1,
                "title": 1,
                "content": 1,
                "original_filename": 1,
                "display_name": 1,
                "storage_url": 1,
                "storage_path": 1,
                "created_at": 1,
                "updated_at": 1,
                "tags": 1,
                # v2.5.1: 新增字段
                "file_size": 1,
                "mime_type": 1,
                "file_extension": 1,
                "uploaded_by": 1,
                "category": 1,
                "status": 1
            }

            # 方式1: 使用 file_id 字段批量查询
            cursor = self.db["file_uploads"].find(
                {"file_id": {"$in": file_ids}},
                projection
            )

            async for doc in cursor:
                fid = doc.get("file_id")
                if fid:
                    result_map[fid] = self._build_file_upload_snapshot(doc, fid)

            # 方式2: 对于未找到的ID，尝试使用 ObjectId 查询
            missing_ids = [fid for fid in file_ids if fid not in result_map]
            if missing_ids:
                object_ids = []
                for fid in missing_ids:
                    try:
                        object_ids.append(ObjectId(fid))
                    except Exception:
                        pass

                if object_ids:
                    # 使用 _id 查询时需要包含 _id 字段
                    projection_with_id = {**projection, "_id": 1}
                    cursor2 = self.db["file_uploads"].find(
                        {"_id": {"$in": object_ids}},
                        projection_with_id
                    )

                    async for doc in cursor2:
                        fid = str(doc.get("_id"))
                        result_map[fid] = self._build_file_upload_snapshot(doc, fid)

            logger.info(f"批量获取 file_uploads: 请求={len(file_ids)}, 获取={len(result_map)}")
            return result_map

        except Exception as e:
            logger.error(f"批量获取 file_uploads 失败: {e}")
            return {}

    def _build_file_upload_snapshot(self, doc: Dict[str, Any], file_id: str) -> Dict[str, Any]:
        """构建 file_upload 快照数据

        v2.5.1: 新增方法，统一快照构建逻辑，确保字段完整性。

        Args:
            doc: MongoDB 文档
            file_id: 文件ID

        Returns:
            完整的快照数据字典
        """
        content = doc.get("content", "")

        return {
            # === 基础快照字段 (与 news 快照兼容) ===
            "original_title": doc.get("title") or doc.get("display_name") or doc.get("original_filename", ""),
            "original_content": content[:2000] if content else "",
            "category": doc.get("category"),
            "published_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "source": "用户上传",
            "source_type": SOURCE_TYPE_FILE_UPLOAD,
            "media_urls": [],
            "url": doc.get("storage_url"),
            "tags": doc.get("tags", []),
            "full_content_length": len(content) if content else 0,

            # === v2.5.1: file_uploads 特有字段 ===
            "file_id": file_id,
            "original_filename": doc.get("original_filename", ""),
            "display_name": doc.get("display_name"),
            "file_size": doc.get("file_size", 0),
            "mime_type": doc.get("mime_type", ""),
            "file_extension": doc.get("file_extension", ""),
            "uploaded_by": doc.get("uploaded_by", ""),
            "storage_path": doc.get("storage_path", ""),
            "file_status": doc.get("status", ""),
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None
        }


# 创建全局服务实例（单例模式）
mongo_archive_service = MongoArchiveService()
