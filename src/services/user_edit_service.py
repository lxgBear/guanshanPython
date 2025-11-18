"""
用户编辑服务

提供批量编辑功能的业务逻辑层

版本: v1.0.0
日期: 2025-11-17
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.core.domain.entities.processed_result import ProcessedResult
from src.infrastructure.database.user_edit_repository import user_edit_repository
from src.infrastructure.database.connection import get_mongodb_database

logger = logging.getLogger(__name__)


class UserEditService:
    """用户编辑服务"""

    # 可编辑字段白名单
    EDITABLE_FIELDS = {
        # 核心内容字段
        "title",
        "content_zh",
        "title_generated",

        # 标签与分类
        "article_tag",
        "cls_results",

        # 元数据字段
        "author",
        "published_date",
        "language",

        # 质量评估
        "user_rating",
        "user_notes",

        # 嵌套对象字段
        "news_results",  # 整个对象
    }

    # news_results 内的可编辑字段
    NEWS_RESULTS_EDITABLE_FIELDS = {
        "title",
        "content",
        "category",
        "source",
        "published_at",
        "media_urls"
    }

    def __init__(self):
        self.repository = user_edit_repository

    # ========== 验证方法 ==========

    def validate_editable_fields(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证可编辑字段

        Args:
            updates: 待更新的字段字典

        Returns:
            Dict: 验证后的字段字典

        Raises:
            ValueError: 字段验证失败
        """
        validated = {}
        errors = []

        for field, value in updates.items():
            # 跳过系统字段
            if field in ["editor_id", "edited_at", "edit_count"]:
                continue

            # 检查字段是否可编辑
            if field not in self.EDITABLE_FIELDS:
                errors.append(f"字段 '{field}' 不允许编辑")
                continue

            # 特殊验证
            if field == "user_rating":
                if value is not None and (not isinstance(value, int) or value < 1 or value > 5):
                    errors.append("user_rating 必须是 1-5 之间的整数")
                    continue

            if field == "news_results" and value is not None:
                # 验证 news_results 嵌套字段
                if not isinstance(value, dict):
                    errors.append("news_results 必须是字典类型")
                    continue

                for sub_field in value.keys():
                    if sub_field not in self.NEWS_RESULTS_EDITABLE_FIELDS:
                        errors.append(f"news_results.{sub_field} 不允许编辑")

                # 验证 category 结构
                if "category" in value and value["category"] is not None:
                    category = value["category"]
                    if not isinstance(category, dict):
                        errors.append("news_results.category 必须是字典类型")
                    else:
                        required_keys = ["大类", "类别", "地域"]
                        for key in required_keys:
                            if key not in category:
                                errors.append(f"news_results.category 缺少必填字段: {key}")

            if field == "article_tag" and value is not None:
                if not isinstance(value, list):
                    errors.append("article_tag 必须是数组类型")
                    continue
                if len(value) > 20:
                    errors.append("article_tag 最多支持20个标签")
                    continue

            validated[field] = value

        if errors:
            raise ValueError("; ".join(errors))

        return validated

    # ========== 批量操作 ==========

    async def batch_update(
        self,
        updates: List[Dict[str, Any]],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        批量更新（灵活模式）

        Args:
            updates: 更新列表，每项包含 {"id": "...", ...其他字段}
            editor_id: 编辑人ID

        Returns:
            Dict: 批量更新结果

        Raises:
            ValueError: 参数验证失败
        """
        if not updates:
            raise ValueError("更新列表不能为空")

        if len(updates) > 100:
            raise ValueError("批量更新最多支持100条记录")

        if not editor_id:
            raise ValueError("editor_id 不能为空")

        logger.info(f"批量更新开始: count={len(updates)}, editor={editor_id}")

        # 验证每条记录的字段
        validated_updates = []
        validation_errors = []

        for idx, item in enumerate(updates):
            try:
                record_id = item.get("id")
                if not record_id:
                    validation_errors.append({
                        "index": idx,
                        "error": "缺少记录ID"
                    })
                    continue

                # 提取更新字段
                update_fields = {k: v for k, v in item.items() if k != "id"}

                # 验证字段
                validated_fields = self.validate_editable_fields(update_fields)
                validated_fields["id"] = record_id

                validated_updates.append(validated_fields)

            except ValueError as e:
                validation_errors.append({
                    "index": idx,
                    "id": item.get("id"),
                    "error": str(e)
                })

        # 如果有验证错误，返回错误信息
        if validation_errors:
            logger.warning(f"批量更新验证失败: {len(validation_errors)}条记录")
            return {
                "success": False,
                "total": len(updates),
                "updated": 0,
                "failed": len(validation_errors),
                "validation_errors": validation_errors
            }

        # 执行批量更新
        result = await self.repository.batch_update(validated_updates, editor_id)

        logger.info(
            f"批量更新完成: updated={result['updated']}, "
            f"failed={result['failed']}"
        )

        return {
            "success": result["updated"] > 0,
            **result
        }

    async def batch_update_fields(
        self,
        record_ids: List[str],
        updates: Dict[str, Any],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        批量更新（统一字段模式）

        Args:
            record_ids: 记录ID列表
            updates: 要更新的字段字典
            editor_id: 编辑人ID

        Returns:
            Dict: 批量更新结果

        Raises:
            ValueError: 参数验证失败
        """
        if not record_ids:
            raise ValueError("记录ID列表不能为空")

        if len(record_ids) > 100:
            raise ValueError("批量更新最多支持100条记录")

        if not updates:
            raise ValueError("更新字段不能为空")

        if not editor_id:
            raise ValueError("editor_id 不能为空")

        logger.info(
            f"批量统一更新开始: count={len(record_ids)}, "
            f"fields={list(updates.keys())}, editor={editor_id}"
        )

        # 验证字段
        validated_updates = self.validate_editable_fields(updates)

        # 执行批量更新
        result = await self.repository.batch_update_fields(
            record_ids,
            validated_updates,
            editor_id
        )

        logger.info(
            f"批量统一更新完成: updated={result['updated']}, "
            f"failed={result['failed']}"
        )

        return {
            "success": result["updated"] > 0,
            **result
        }

    # ========== 单条操作 ==========

    async def update_one(
        self,
        record_id: str,
        updates: Dict[str, Any],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        更新单条记录

        Args:
            record_id: 记录ID
            updates: 要更新的字段字典
            editor_id: 编辑人ID

        Returns:
            Dict: 更新结果

        Raises:
            ValueError: 参数验证失败
        """
        if not record_id:
            raise ValueError("record_id 不能为空")

        if not updates:
            raise ValueError("更新字段不能为空")

        if not editor_id:
            raise ValueError("editor_id 不能为空")

        logger.info(f"更新单条记录: id={record_id}, editor={editor_id}")

        # 验证字段
        validated_updates = self.validate_editable_fields(updates)

        # 执行更新
        success = await self.repository.update_one(
            record_id,
            validated_updates,
            editor_id
        )

        if not success:
            raise ValueError(f"记录不存在或更新失败: {record_id}")

        # 获取更新后的记录
        updated_record = await self.repository.get_by_id(record_id)

        return {
            "success": True,
            "id": record_id,
            "updated_fields": list(validated_updates.keys()),
            "record": updated_record.dict() if updated_record else None
        }

    async def get_by_id(self, record_id: str) -> Optional[ProcessedResult]:
        """
        获取记录详情

        Args:
            record_id: 记录ID

        Returns:
            Optional[ProcessedResult]: 记录实体
        """
        return await self.repository.get_by_id(record_id)

    # ========== 查询操作 ==========

    async def get_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取任务的编辑记录列表

        Args:
            task_id: 任务ID
            page: 页码
            page_size: 每页数量

        Returns:
            Dict: 分页结果
        """
        results, total = await self.repository.get_by_task(task_id, page, page_size)

        return {
            "results": [r.dict() for r in results],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def get_by_editor(
        self,
        editor_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取编辑人的编辑记录列表

        Args:
            editor_id: 编辑人ID
            page: 页码
            page_size: 每页数量

        Returns:
            Dict: 分页结果
        """
        results, total = await self.repository.get_by_editor(editor_id, page, page_size)

        return {
            "results": [r.dict() for r in results],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    # ========== 复制操作 ==========

    async def copy_from_original(
        self,
        source_ids: List[str],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        从原始结果表(news_results)复制记录用于编辑

        Args:
            source_ids: 原始记录ID列表
            editor_id: 编辑人ID

        Returns:
            Dict: 复制结果

        Raises:
            ValueError: 参数验证失败
        """
        if not source_ids:
            raise ValueError("source_ids 不能为空")

        if len(source_ids) > 100:
            raise ValueError("批量复制最多支持100条记录")

        if not editor_id:
            raise ValueError("editor_id 不能为空")

        logger.info(f"批量复制记录开始: count={len(source_ids)}, editor={editor_id}")

        # 从 news_results 表获取原始记录
        db = await get_mongodb_database()
        news_collection = db["news_results"]

        original_results = []
        not_found = []

        for source_id in source_ids:
            doc = await news_collection.find_one({"_id": source_id})
            if doc:
                # 转换为 ProcessedResult 实体
                doc["id"] = doc.pop("_id")
                original = ProcessedResult(**doc)
                original_results.append(original)
            else:
                not_found.append(source_id)
                logger.warning(f"原始记录不存在: {source_id}")

        # 批量复制
        if original_results:
            new_ids = await self.repository.batch_copy_from_original(
                original_results,
                editor_id
            )
        else:
            new_ids = []

        logger.info(
            f"批量复制完成: copied={len(new_ids)}, "
            f"not_found={len(not_found)}"
        )

        return {
            "success": len(new_ids) > 0,
            "total": len(source_ids),
            "copied": len(new_ids),
            "failed": len(not_found),
            "new_ids": new_ids,
            "not_found_ids": not_found
        }


# 创建全局服务实例
user_edit_service = UserEditService()
