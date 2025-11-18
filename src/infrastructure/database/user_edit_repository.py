"""
用户编辑结果Repository

用于批量编辑功能的数据访问层
表: user_edited_results
字段: 复用ProcessedResult + 编辑追踪字段

版本: v1.0.0
日期: 2025-11-17
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.processed_result import ProcessedResult
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class UserEditRepository:
    """用户编辑结果Repository"""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self.db = db
        self.collection_name = "user_edited_results"

    async def _get_collection(self):
        """获取MongoDB集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    # ========== 基础CRUD操作 ==========

    async def create(self, entity: ProcessedResult, editor_id: str) -> str:
        """
        创建编辑记录

        Args:
            entity: ProcessedResult实体
            editor_id: 编辑人ID

        Returns:
            str: 新创建的记录ID
        """
        collection = await self._get_collection()

        if not entity.id:
            entity.id = generate_string_id()

        # 添加编辑追踪字段
        document = entity.dict(by_alias=True)
        document["editor_id"] = editor_id
        document["edited_at"] = datetime.utcnow()
        document["edit_count"] = 1
        document["_id"] = entity.id

        await collection.insert_one(document)
        logger.info(f"创建用户编辑记录: id={entity.id}, editor={editor_id}")
        return entity.id

    async def get_by_id(self, id: str) -> Optional[ProcessedResult]:
        """
        根据ID获取记录

        Args:
            id: 记录ID

        Returns:
            Optional[ProcessedResult]: 记录实体，不存在返回None
        """
        collection = await self._get_collection()

        document = await collection.find_one({"_id": id})
        if not document:
            return None

        # 移除额外字段，转换为ProcessedResult
        document.pop("editor_id", None)
        document.pop("edited_at", None)
        document.pop("edit_count", None)
        document.pop("source_result_id", None)

        return ProcessedResult(**document)

    async def update_one(
        self,
        id: str,
        updates: Dict[str, Any],
        editor_id: str
    ) -> bool:
        """
        更新单条记录

        Args:
            id: 记录ID
            updates: 要更新的字段字典
            editor_id: 编辑人ID

        Returns:
            bool: 更新成功返回True，记录不存在返回False
        """
        collection = await self._get_collection()

        # 添加编辑追踪
        updates["editor_id"] = editor_id
        updates["edited_at"] = datetime.utcnow()
        updates["updated_at"] = datetime.utcnow()

        result = await collection.update_one(
            {"_id": id},
            {
                "$set": updates,
                "$inc": {"edit_count": 1}  # 编辑次数+1
            }
        )

        success = result.modified_count > 0
        if success:
            logger.info(f"更新用户编辑记录: id={id}, editor={editor_id}, fields={list(updates.keys())}")
        else:
            logger.warning(f"更新失败，记录不存在: id={id}")

        return success

    async def delete(self, id: str) -> bool:
        """
        删除记录

        Args:
            id: 记录ID

        Returns:
            bool: 删除成功返回True
        """
        collection = await self._get_collection()

        result = await collection.delete_one({"_id": id})
        success = result.deleted_count > 0

        if success:
            logger.info(f"删除用户编辑记录: id={id}")
        else:
            logger.warning(f"删除失败，记录不存在: id={id}")

        return success

    # ========== 批量操作 ==========

    async def batch_update(
        self,
        updates: List[Dict[str, Any]],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        批量更新（灵活模式）- 每条记录可以更新不同字段

        Args:
            updates: 更新列表，每项包含 {"id": "...", ...其他字段}
            editor_id: 编辑人ID

        Returns:
            Dict: {
                "total": 总数,
                "updated": 成功更新数,
                "failed": 失败数,
                "results": [详细结果列表]
            }
        """
        collection = await self._get_collection()

        total = len(updates)
        results = []
        updated_count = 0
        failed_count = 0

        for item in updates:
            record_id = item.pop("id", None)
            if not record_id:
                results.append({
                    "id": None,
                    "success": False,
                    "error": "缺少记录ID"
                })
                failed_count += 1
                continue

            try:
                # 准备更新数据
                update_data = {**item}
                update_data["editor_id"] = editor_id
                update_data["edited_at"] = datetime.utcnow()
                update_data["updated_at"] = datetime.utcnow()

                # 执行更新
                result = await collection.update_one(
                    {"_id": record_id},
                    {
                        "$set": update_data,
                        "$inc": {"edit_count": 1}
                    }
                )

                if result.modified_count > 0:
                    results.append({
                        "id": record_id,
                        "success": True,
                        "updated_fields": list(item.keys())
                    })
                    updated_count += 1
                    logger.debug(f"批量更新成功: id={record_id}")
                else:
                    results.append({
                        "id": record_id,
                        "success": False,
                        "error": "记录不存在或无变更"
                    })
                    failed_count += 1

            except Exception as e:
                logger.error(f"批量更新失败: id={record_id}, error={e}")
                results.append({
                    "id": record_id,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1

        logger.info(
            f"批量更新完成: total={total}, updated={updated_count}, "
            f"failed={failed_count}, editor={editor_id}"
        )

        return {
            "total": total,
            "updated": updated_count,
            "failed": failed_count,
            "results": results
        }

    async def batch_update_fields(
        self,
        record_ids: List[str],
        updates: Dict[str, Any],
        editor_id: str
    ) -> Dict[str, Any]:
        """
        批量更新（统一字段模式）- 多条记录更新相同字段为相同值

        Args:
            record_ids: 记录ID列表
            updates: 要更新的字段字典（所有记录使用相同值）
            editor_id: 编辑人ID

        Returns:
            Dict: {
                "total": 总数,
                "updated": 成功更新数,
                "failed": 失败数,
                "updated_fields": 更新的字段列表
            }
        """
        collection = await self._get_collection()

        total = len(record_ids)

        # 准备更新数据
        update_data = {**updates}
        update_data["editor_id"] = editor_id
        update_data["edited_at"] = datetime.utcnow()
        update_data["updated_at"] = datetime.utcnow()

        try:
            # 批量更新
            result = await collection.update_many(
                {"_id": {"$in": record_ids}},
                {
                    "$set": update_data,
                    "$inc": {"edit_count": 1}
                }
            )

            updated_count = result.modified_count
            failed_count = total - updated_count

            logger.info(
                f"批量统一更新完成: total={total}, updated={updated_count}, "
                f"failed={failed_count}, fields={list(updates.keys())}, editor={editor_id}"
            )

            return {
                "total": total,
                "updated": updated_count,
                "failed": failed_count,
                "updated_fields": list(updates.keys())
            }

        except Exception as e:
            logger.error(f"批量统一更新失败: error={e}")
            raise

    # ========== 查询操作 ==========

    async def get_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[ProcessedResult], int]:
        """
        根据任务ID获取编辑记录（分页）

        Args:
            task_id: 任务ID
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            Tuple[List[ProcessedResult], int]: (记录列表, 总数)
        """
        collection = await self._get_collection()

        query = {"task_id": task_id}

        # 获取总数
        total = await collection.count_documents(query)

        # 分页查询
        cursor = collection.find(query)\
            .sort("edited_at", -1)\
            .skip((page - 1) * page_size)\
            .limit(page_size)

        results = []
        async for doc in cursor:
            # 移除额外字段
            doc.pop("editor_id", None)
            doc.pop("edited_at", None)
            doc.pop("edit_count", None)
            doc.pop("source_result_id", None)
            results.append(ProcessedResult(**doc))

        return results, total

    async def get_by_editor(
        self,
        editor_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[ProcessedResult], int]:
        """
        根据编辑人ID获取编辑记录（分页）

        Args:
            editor_id: 编辑人ID
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[ProcessedResult], int]: (记录列表, 总数)
        """
        collection = await self._get_collection()

        query = {"editor_id": editor_id}

        total = await collection.count_documents(query)

        cursor = collection.find(query)\
            .sort("edited_at", -1)\
            .skip((page - 1) * page_size)\
            .limit(page_size)

        results = []
        async for doc in cursor:
            doc.pop("editor_id", None)
            doc.pop("edited_at", None)
            doc.pop("edit_count", None)
            doc.pop("source_result_id", None)
            results.append(ProcessedResult(**doc))

        return results, total

    async def count_by_task(self, task_id: str) -> int:
        """
        统计任务的编辑记录数

        Args:
            task_id: 任务ID

        Returns:
            int: 记录数量
        """
        collection = await self._get_collection()
        return await collection.count_documents({"task_id": task_id})

    # ========== 复制操作 ==========

    async def copy_from_original(
        self,
        original_result: ProcessedResult,
        editor_id: str
    ) -> str:
        """
        从原始结果复制记录用于编辑

        Args:
            original_result: 原始ProcessedResult实体
            editor_id: 编辑人ID

        Returns:
            str: 新创建的记录ID
        """
        collection = await self._get_collection()

        # 创建新ID
        new_id = generate_string_id()

        # 准备文档
        document = original_result.dict(by_alias=True)
        document["_id"] = new_id
        document["source_result_id"] = original_result.id  # 保存原始记录ID
        document["editor_id"] = editor_id
        document["edited_at"] = datetime.utcnow()
        document["edit_count"] = 0  # 复制后尚未编辑
        document["created_at"] = datetime.utcnow()
        document["updated_at"] = datetime.utcnow()

        await collection.insert_one(document)
        logger.info(f"复制记录用于编辑: new_id={new_id}, source_id={original_result.id}")

        return new_id

    async def batch_copy_from_original(
        self,
        original_results: List[ProcessedResult],
        editor_id: str
    ) -> List[str]:
        """
        批量复制原始结果用于编辑

        Args:
            original_results: 原始ProcessedResult实体列表
            editor_id: 编辑人ID

        Returns:
            List[str]: 新创建的记录ID列表
        """
        if not original_results:
            return []

        collection = await self._get_collection()

        documents = []
        new_ids = []

        for original in original_results:
            new_id = generate_string_id()
            new_ids.append(new_id)

            document = original.dict(by_alias=True)
            document["_id"] = new_id
            document["source_result_id"] = original.id
            document["editor_id"] = editor_id
            document["edited_at"] = datetime.utcnow()
            document["edit_count"] = 0
            document["created_at"] = datetime.utcnow()
            document["updated_at"] = datetime.utcnow()

            documents.append(document)

        # 批量插入
        await collection.insert_many(documents)
        logger.info(f"批量复制{len(new_ids)}条记录用于编辑, editor={editor_id}")

        return new_ids

    # ========== 索引管理 ==========

    async def create_indexes(self):
        """创建MongoDB索引"""
        collection = await self._get_collection()

        logger.info("开始创建 user_edited_results 集合索引...")

        # 1. 编辑人+时间索引
        await collection.create_index(
            [("editor_id", 1), ("edited_at", -1)],
            name="editor_time_idx",
            background=True
        )
        logger.info("✅ 创建索引: editor_time_idx")

        # 2. 来源记录索引
        await collection.create_index(
            [("source_result_id", 1)],
            name="source_ref_idx",
            background=True
        )
        logger.info("✅ 创建索引: source_ref_idx")

        # 3. 任务+编辑时间索引
        await collection.create_index(
            [("task_id", 1), ("edited_at", -1)],
            name="task_edited_idx",
            background=True
        )
        logger.info("✅ 创建索引: task_edited_idx")

        # 4. 创建时间索引
        await collection.create_index(
            [("created_at", -1)],
            name="created_desc_idx",
            background=True
        )
        logger.info("✅ 创建索引: created_desc_idx")

        # 5. 全文搜索索引
        await collection.create_index(
            [("title", "text"), ("content_zh", "text")],
            name="fulltext_idx",
            background=True
        )
        logger.info("✅ 创建索引: fulltext_idx")

        logger.info("user_edited_results 集合索引创建完成！")


# 创建全局实例
user_edit_repository = UserEditRepository()
