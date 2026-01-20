"""
Chat Task Repository - 聊天任务数据访问层

v3.0.0 新增：支持后台任务执行模式
v4.20.0 新增：支持要素确认流程 (awaiting_confirmation 状态)

MongoDB Collection: chat_tasks
- 存储所有聊天任务的状态和结果
- 支持同步等待和异步轮询两种模式
- 支持要素提取和确认流程
- 任务完成后关联到 search_history
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_id

logger = logging.getLogger(__name__)


class ChatTaskRepository:
    """聊天任务仓库"""

    COLLECTION_NAME = "chat_tasks"

    # 任务状态常量
    STATUS_PENDING = "pending"           # 等待执行
    STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待用户确认要素
    STATUS_SEARCHING = "searching"       # 正在搜索
    STATUS_PROCESSING = "processing"     # AI处理中
    STATUS_COMPLETED = "completed"       # 已完成
    STATUS_FAILED = "failed"             # 失败
    STATUS_EXPIRED = "expired"           # 确认超时

    async def create_task(
        self,
        user_id: int,
        question: str,
        search_mode: str = "single",
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建新任务

        Args:
            user_id: 用户ID
            question: 用户问题
            search_mode: 搜索模式 (single/multi)
            conversation_id: 可选的对话ID
            metadata: 额外元数据

        Returns:
            task_id: 任务ID（雪花算法）
        """
        db = await get_mongodb_database()

        task_id = generate_id()
        now = datetime.utcnow()

        task_doc = {
            "_id": str(task_id),
            "user_id": user_id,
            "question": question,
            "search_mode": search_mode,
            "conversation_id": conversation_id,

            # 状态管理
            "status": self.STATUS_PENDING,
            "progress": {
                "current_step": "pending",
                "message": "任务已创建，等待执行",
                "percentage": 0
            },

            # 结果存储（完成后填充）
            "result": None,
            "error": None,

            # 关联ID
            "history_id": None,  # 完成后关联到 search_history

            # 元数据
            "metadata": metadata or {},

            # 时间戳
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now
        }

        await db[self.COLLECTION_NAME].insert_one(task_doc)
        logger.info(f"创建聊天任务: task_id={task_id}, user_id={user_id}")

        return str(task_id)

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情

        Args:
            task_id: 任务ID

        Returns:
            任务文档，不存在返回 None
        """
        db = await get_mongodb_database()
        return await db[self.COLLECTION_NAME].find_one({"_id": task_id})

    async def get_task_by_user(
        self,
        task_id: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取指定用户的任务（安全查询）

        Args:
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            任务文档，不存在或不属于该用户返回 None
        """
        db = await get_mongodb_database()
        return await db[self.COLLECTION_NAME].find_one({
            "_id": task_id,
            "user_id": user_id
        })

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress_message: Optional[str] = None,
        progress_percentage: Optional[int] = None
    ) -> bool:
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            progress_message: 进度消息
            progress_percentage: 进度百分比

        Returns:
            是否更新成功
        """
        db = await get_mongodb_database()

        update_doc = {
            "status": status,
            "updated_at": datetime.utcnow()
        }

        # 更新进度信息
        if progress_message is not None:
            update_doc["progress.message"] = progress_message
            update_doc["progress.current_step"] = status
        if progress_percentage is not None:
            update_doc["progress.percentage"] = progress_percentage

        # 记录开始时间
        if status == self.STATUS_SEARCHING:
            update_doc["started_at"] = datetime.utcnow()

        result = await db[self.COLLECTION_NAME].update_one(
            {"_id": task_id},
            {"$set": update_doc}
        )

        if result.modified_count > 0:
            logger.debug(f"更新任务状态: task_id={task_id}, status={status}")
            return True
        return False

    async def complete_task(
        self,
        task_id: str,
        result: Dict[str, Any],
        history_id: Optional[str] = None
    ) -> bool:
        """完成任务

        Args:
            task_id: 任务ID
            result: 任务结果
            history_id: 关联的历史记录ID

        Returns:
            是否更新成功
        """
        db = await get_mongodb_database()

        now = datetime.utcnow()
        update_doc = {
            "status": self.STATUS_COMPLETED,
            "result": result,
            "history_id": history_id,
            "progress": {
                "current_step": "completed",
                "message": "任务完成",
                "percentage": 100
            },
            "completed_at": now,
            "updated_at": now
        }

        result_update = await db[self.COLLECTION_NAME].update_one(
            {"_id": task_id},
            {"$set": update_doc}
        )

        if result_update.modified_count > 0:
            logger.info(f"任务完成: task_id={task_id}, history_id={history_id}")
            return True
        return False

    async def fail_task(
        self,
        task_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """标记任务失败

        Args:
            task_id: 任务ID
            error_message: 错误消息
            error_details: 错误详情

        Returns:
            是否更新成功
        """
        db = await get_mongodb_database()

        now = datetime.utcnow()
        update_doc = {
            "status": self.STATUS_FAILED,
            "error": {
                "message": error_message,
                "details": error_details,
                "failed_at": now
            },
            "progress": {
                "current_step": "failed",
                "message": error_message,
                "percentage": 0
            },
            "completed_at": now,
            "updated_at": now
        }

        result = await db[self.COLLECTION_NAME].update_one(
            {"_id": task_id},
            {"$set": update_doc}
        )

        if result.modified_count > 0:
            logger.error(f"任务失败: task_id={task_id}, error={error_message}")
            return True
        return False

    async def get_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取用户的任务列表

        Args:
            user_id: 用户ID
            status: 可选的状态过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        db = await get_mongodb_database()

        query = {"user_id": user_id}
        if status:
            query["status"] = status

        cursor = db[self.COLLECTION_NAME].find(query).sort(
            "created_at", -1
        ).skip(offset).limit(limit)

        return await cursor.to_list(length=limit)

    async def get_pending_tasks(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户待处理的任务

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            待处理任务列表
        """
        db = await get_mongodb_database()

        cursor = db[self.COLLECTION_NAME].find({
            "user_id": user_id,
            "status": {"$in": [
                self.STATUS_PENDING,
                self.STATUS_SEARCHING,
                self.STATUS_PROCESSING
            ]}
        }).sort("created_at", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def count_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None
    ) -> int:
        """统计用户任务数量

        Args:
            user_id: 用户ID
            status: 可选的状态过滤

        Returns:
            任务数量
        """
        db = await get_mongodb_database()

        query = {"user_id": user_id}
        if status:
            query["status"] = status

        return await db[self.COLLECTION_NAME].count_documents(query)

    async def list_tasks(
        self,
        query: Dict[str, Any],
        skip: int = 0,
        limit: int = 20,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """通用任务列表查询 (v4.21.0)

        Args:
            query: 查询条件
            skip: 跳过数量
            limit: 返回数量
            sort: 排序规则，如 [("created_at", -1)]

        Returns:
            任务列表
        """
        db = await get_mongodb_database()

        cursor = db[self.COLLECTION_NAME].find(query)

        if sort:
            cursor = cursor.sort(sort)

        cursor = cursor.skip(skip).limit(limit)

        return await cursor.to_list(length=limit)

    async def count_tasks(self, query: Dict[str, Any]) -> int:
        """通用任务计数 (v4.21.0)

        Args:
            query: 查询条件

        Returns:
            任务数量
        """
        db = await get_mongodb_database()
        return await db[self.COLLECTION_NAME].count_documents(query)

    async def delete_task(self, task_id: str, user_id: int) -> bool:
        """删除任务（仅限用户自己的任务）

        Args:
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        db = await get_mongodb_database()

        result = await db[self.COLLECTION_NAME].delete_one({
            "_id": task_id,
            "user_id": user_id
        })

        if result.deleted_count > 0:
            logger.info(f"删除任务: task_id={task_id}, user_id={user_id}")
            return True
        return False

    # ==================== 要素确认相关方法 ====================

    async def create_task_with_confirmation(
        self,
        user_id: int,
        question: str,
        search_mode: str = "single",
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建需要要素确认的任务

        Args:
            user_id: 用户ID
            question: 用户问题
            search_mode: 搜索模式 (single/multi)
            conversation_id: 可选的对话ID
            metadata: 额外元数据

        Returns:
            task_id: 任务ID（雪花算法）
        """
        db = await get_mongodb_database()

        task_id = generate_id()
        now = datetime.utcnow()

        task_doc = {
            "_id": str(task_id),
            "user_id": user_id,
            "question": question,
            "search_mode": search_mode,
            "conversation_id": conversation_id,

            # 状态管理 - 初始为等待确认
            "status": self.STATUS_AWAITING_CONFIRMATION,
            "progress": {
                "current_step": "awaiting_confirmation",
                "message": "等待用户确认搜索要素",
                "percentage": 5
            },

            # 要素存储
            "extracted_elements": None,  # LLM 提取的要素
            "confirmed_elements": None,  # 用户确认的要素
            "confirmed_at": None,

            # 结果存储（完成后填充）
            "result": None,
            "error": None,

            # 关联ID
            "history_id": None,

            # 元数据
            "metadata": metadata or {},

            # 时间戳
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now
        }

        await db[self.COLLECTION_NAME].insert_one(task_doc)
        logger.info(f"创建要素确认任务: task_id={task_id}, user_id={user_id}")

        return str(task_id)

    async def update_extracted_elements(
        self,
        task_id: str,
        elements: Dict[str, Any]
    ) -> bool:
        """保存 LLM 提取的要素

        Args:
            task_id: 任务ID
            elements: 提取的要素字典

        Returns:
            是否更新成功
        """
        db = await get_mongodb_database()

        update_doc = {
            "extracted_elements": elements,
            "progress.message": "搜索要素已提取，等待用户确认",
            "progress.percentage": 10,
            "updated_at": datetime.utcnow()
        }

        result = await db[self.COLLECTION_NAME].update_one(
            {"_id": task_id},
            {"$set": update_doc}
        )

        if result.modified_count > 0:
            logger.info(f"保存提取要素: task_id={task_id}")
            return True
        return False

    async def update_confirmed_elements(
        self,
        task_id: str,
        elements: Dict[str, Any]
    ) -> bool:
        """保存用户确认的要素

        Args:
            task_id: 任务ID
            elements: 确认的要素字典

        Returns:
            是否更新成功
        """
        db = await get_mongodb_database()

        now = datetime.utcnow()
        update_doc = {
            "confirmed_elements": elements,
            "confirmed_at": now,
            "progress.message": "用户已确认搜索要素",
            "progress.percentage": 15,
            "updated_at": now
        }

        result = await db[self.COLLECTION_NAME].update_one(
            {"_id": task_id},
            {"$set": update_doc}
        )

        if result.modified_count > 0:
            logger.info(f"保存确认要素: task_id={task_id}")
            return True
        return False

    async def expire_stale_tasks(self, timeout_hours: int = 24) -> int:
        """将超时未确认的任务标记为过期

        Args:
            timeout_hours: 超时小时数，默认24小时

        Returns:
            过期任务数量
        """
        db = await get_mongodb_database()

        cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)
        now = datetime.utcnow()

        result = await db[self.COLLECTION_NAME].update_many(
            {
                "status": self.STATUS_AWAITING_CONFIRMATION,
                "created_at": {"$lt": cutoff_time}
            },
            {
                "$set": {
                    "status": self.STATUS_EXPIRED,
                    "error": {
                        "message": f"确认超时（{timeout_hours}小时）",
                        "details": {"timeout_hours": timeout_hours},
                        "failed_at": now
                    },
                    "progress": {
                        "current_step": "expired",
                        "message": f"任务超时，未在 {timeout_hours} 小时内确认",
                        "percentage": 0
                    },
                    "completed_at": now,
                    "updated_at": now
                }
            }
        )

        expired_count = result.modified_count
        if expired_count > 0:
            logger.info(f"过期任务数量: {expired_count}")
        return expired_count

    async def get_awaiting_confirmation_tasks(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取用户等待确认的任务

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            等待确认的任务列表
        """
        db = await get_mongodb_database()

        cursor = db[self.COLLECTION_NAME].find({
            "user_id": user_id,
            "status": self.STATUS_AWAITING_CONFIRMATION
        }).sort("created_at", -1).limit(limit)

        return await cursor.to_list(length=limit)


# 单例实例
chat_task_repository = ChatTaskRepository()
