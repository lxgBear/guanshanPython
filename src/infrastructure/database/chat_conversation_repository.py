"""
Chat Conversation MongoDB Repository

存储 QA Chat 的对话会话和消息历史。

设计说明:
- 使用 MongoDB Motor 异步驱动
- 使用雪花算法 ID 保持一致性
- 内嵌存储 messages 数组（单文档事务性）
- 支持用户隔离和分页查询

集合名称: chat_conversations

文档结构:
{
    "_id": "snowflake_id",           # 会话ID
    "title": "关于西藏问题的讨论",     # 会话标题（自动从首条消息生成）
    "user_id": "optional_user",       # 用户ID（隔离用）
    "messages": [                     # 消息数组
        {
            "id": "msg_snowflake_id",
            "role": "user",           # user | assistant
            "content": "请介绍西藏问题",
            "timestamp": "2025-12-26T10:00:00.000Z",
            "sources": []             # AI回复时的来源引用
        },
        {
            "id": "msg_snowflake_id",
            "role": "assistant",
            "content": "西藏问题是...",
            "timestamp": "2025-12-26T10:00:05.000Z",
            "sources": [{"id": "...", "title": "..."}]
        }
    ],
    "message_count": 2,
    "last_message_at": ISODate,
    "metadata": {
        "search_mode": "single",
        "model": "gpt-4",
        "total_tokens": 1500
    },
    "created_at": ISODate,
    "updated_at": ISODate
}

版本: v1.0.0
日期: 2025-12-29
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class ChatConversationRepository:
    """Chat Conversation MongoDB 仓库

    存储和查询 QA Chat 的对话会话。

    Example:
        >>> repo = ChatConversationRepository()
        >>> conv_id = await repo.create_conversation(
        ...     user_id="user_123",
        ...     title="关于西藏问题的讨论"
        ... )
        >>> await repo.add_message(conv_id, "user", "请介绍西藏问题")
        >>> conversation = await repo.get_by_id(conv_id)
    """

    def __init__(self):
        """初始化仓库"""
        self.db = None
        self.collection_name = "chat_conversations"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create_conversation(
        self,
        user_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建新对话会话

        Args:
            user_id: 用户ID（可选，用于隔离）
            title: 会话标题（可选，会从首条消息自动生成）
            metadata: 元数据（可选）

        Returns:
            str: 创建的会话ID（雪花算法ID字符串）

        Example:
            >>> conv_id = await repo.create_conversation(
            ...     user_id="user_123",
            ...     title="关于西藏问题的讨论"
            ... )
        """
        collection = await self._get_collection()

        conversation_id = generate_string_id()
        now = datetime.utcnow()

        document = {
            "_id": conversation_id,
            "title": title or "新对话",
            "user_id": user_id,
            "messages": [],
            "message_count": 0,
            "last_message_at": now,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now
        }

        await collection.insert_one(document)

        logger.info(
            f"创建对话会话成功: ID={conversation_id}, "
            f"user_id={user_id}, title='{title}'"
        )
        return conversation_id

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """添加消息到对话

        Args:
            conversation_id: 会话ID
            role: 消息角色 ("user" | "assistant")
            content: 消息内容
            sources: AI回复时的来源引用（可选）
            metadata: 消息元数据（可选）

        Returns:
            Optional[str]: 消息ID，会话不存在时返回 None

        Example:
            >>> msg_id = await repo.add_message(
            ...     conv_id, "user", "请介绍西藏问题"
            ... )
        """
        collection = await self._get_collection()

        message_id = generate_string_id()
        now = datetime.utcnow()

        message = {
            "id": message_id,
            "role": role,
            "content": content,
            "timestamp": now.isoformat(),
            "sources": sources or [],
            "metadata": metadata or {}
        }

        # 更新会话：添加消息 + 更新统计
        result = await collection.update_one(
            {"_id": conversation_id},
            {
                "$push": {"messages": message},
                "$inc": {"message_count": 1},
                "$set": {
                    "last_message_at": now,
                    "updated_at": now
                }
            }
        )

        if result.matched_count == 0:
            logger.warning(f"对话会话不存在: ID={conversation_id}")
            return None

        # 如果是第一条用户消息，自动更新标题
        conversation = await self.get_by_id(conversation_id)
        if conversation and conversation.get("message_count") == 1 and role == "user":
            # 用首条消息的前30个字符作为标题
            auto_title = content[:30] + ("..." if len(content) > 30 else "")
            await collection.update_one(
                {"_id": conversation_id},
                {"$set": {"title": auto_title}}
            )
            logger.info(f"自动更新对话标题: '{auto_title}'")

        logger.debug(f"添加消息成功: conv_id={conversation_id}, msg_id={message_id}, role={role}")
        return message_id

    async def get_by_id(
        self,
        conversation_id: str,
        include_messages: bool = True
    ) -> Optional[Dict[str, Any]]:
        """根据 ID 获取对话会话

        Args:
            conversation_id: 会话ID
            include_messages: 是否包含消息列表

        Returns:
            Optional[Dict]: 会话数据，不存在时返回 None

        Example:
            >>> conversation = await repo.get_by_id("248728141926559744")
            >>> if conversation:
            ...     print(conversation["title"], len(conversation["messages"]))
        """
        collection = await self._get_collection()

        projection = None
        if not include_messages:
            projection = {"messages": 0}

        document = await collection.find_one(
            {"_id": conversation_id},
            projection
        )

        if not document:
            logger.debug(f"对话会话不存在: ID={conversation_id}")
            return None

        return document

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before_message_id: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """获取会话的消息列表

        Args:
            conversation_id: 会话ID
            limit: 返回数量限制（从最新开始）
            before_message_id: 获取此消息之前的消息（分页用）

        Returns:
            Optional[List[Dict]]: 消息列表，不存在时返回 None

        Example:
            >>> messages = await repo.get_messages("248728141926559744", limit=20)
            >>> for msg in messages:
            ...     print(msg["role"], msg["content"][:50])
        """
        collection = await self._get_collection()

        # 使用聚合管道来支持分页
        pipeline = [
            {"$match": {"_id": conversation_id}},
            {"$project": {"messages": 1, "_id": 0}}
        ]

        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            return None

        messages = result[0].get("messages", [])

        # 如果需要分页（获取某消息之前的消息）
        if before_message_id:
            index = next(
                (i for i, m in enumerate(messages) if m["id"] == before_message_id),
                None
            )
            if index is not None:
                messages = messages[:index]

        # 如果需要限制数量，从最新的开始取
        if limit and len(messages) > limit:
            messages = messages[-limit:]

        return messages

    async def get_recent_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取最近的对话会话列表

        Args:
            user_id: 用户ID过滤（可选）
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[Dict]: 会话列表（不包含完整消息，只有摘要）

        Example:
            >>> conversations = await repo.get_recent_conversations(
            ...     user_id="user_123", limit=10
            ... )
        """
        collection = await self._get_collection()

        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id

        # 投影：不返回完整消息列表，只返回最后一条消息
        cursor = collection.find(
            filter_query,
            {
                "messages": {"$slice": -1},  # 只取最后一条消息
                "title": 1,
                "user_id": 1,
                "message_count": 1,
                "last_message_at": 1,
                "created_at": 1,
                "metadata": 1
            }
        ).sort("last_message_at", -1).skip(offset).limit(limit)

        conversations = await cursor.to_list(length=limit)

        # 转换最后一条消息为 last_message 字段
        for conv in conversations:
            messages = conv.pop("messages", [])
            conv["last_message"] = messages[0] if messages else None

        return conversations

    async def update_title(
        self,
        conversation_id: str,
        title: str
    ) -> bool:
        """更新会话标题

        Args:
            conversation_id: 会话ID
            title: 新标题

        Returns:
            bool: 更新是否成功

        Example:
            >>> success = await repo.update_title(conv_id, "新标题")
        """
        collection = await self._get_collection()

        result = await collection.update_one(
            {"_id": conversation_id},
            {
                "$set": {
                    "title": title,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        success = result.matched_count > 0
        if success:
            logger.info(f"更新对话标题成功: ID={conversation_id}, title='{title}'")

        return success

    async def update_metadata(
        self,
        conversation_id: str,
        metadata: Dict[str, Any],
        merge: bool = True
    ) -> bool:
        """更新会话元数据

        Args:
            conversation_id: 会话ID
            metadata: 元数据
            merge: 是否合并（True=合并，False=替换）

        Returns:
            bool: 更新是否成功
        """
        collection = await self._get_collection()

        if merge:
            # 合并模式：使用 $set 更新单个字段
            update_fields = {f"metadata.{k}": v for k, v in metadata.items()}
            update_fields["updated_at"] = datetime.utcnow()
            update_op = {"$set": update_fields}
        else:
            # 替换模式
            update_op = {
                "$set": {
                    "metadata": metadata,
                    "updated_at": datetime.utcnow()
                }
            }

        result = await collection.update_one(
            {"_id": conversation_id},
            update_op
        )

        return result.matched_count > 0

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话会话

        Args:
            conversation_id: 会话ID

        Returns:
            bool: 删除是否成功

        Example:
            >>> success = await repo.delete_conversation("248728141926559744")
        """
        collection = await self._get_collection()

        result = await collection.delete_one({"_id": conversation_id})

        success = result.deleted_count > 0
        if success:
            logger.info(f"删除对话会话成功: ID={conversation_id}")

        return success

    async def delete_old_conversations(self, days: int = 90) -> int:
        """删除旧对话会话

        Args:
            days: 保留天数，删除超过此天数的会话

        Returns:
            int: 删除的会话数

        Example:
            >>> deleted = await repo.delete_old_conversations(days=90)
        """
        collection = await self._get_collection()

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        result = await collection.delete_many({
            "last_message_at": {"$lt": cutoff_date}
        })

        deleted_count = result.deleted_count
        logger.info(f"删除 {deleted_count} 个旧的对话会话 (>{days}天)")

        return deleted_count

    async def count_conversations(self, user_id: Optional[str] = None) -> int:
        """统计会话数量

        Args:
            user_id: 用户ID过滤（可选）

        Returns:
            int: 会话数量
        """
        collection = await self._get_collection()

        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id

        return await collection.count_documents(filter_query)

    async def search_conversations(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """搜索对话会话

        Args:
            query: 搜索关键词
            user_id: 用户ID过滤（可选）
            limit: 返回数量限制

        Returns:
            List[Dict]: 匹配的会话列表
        """
        collection = await self._get_collection()

        filter_query = {
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"messages.content": {"$regex": query, "$options": "i"}}
            ]
        }

        if user_id:
            filter_query["user_id"] = user_id

        cursor = collection.find(
            filter_query,
            {
                "messages": {"$slice": -1},
                "title": 1,
                "user_id": 1,
                "message_count": 1,
                "last_message_at": 1,
                "created_at": 1
            }
        ).sort("last_message_at", -1).limit(limit)

        conversations = await cursor.to_list(length=limit)

        for conv in conversations:
            messages = conv.pop("messages", [])
            conv["last_message"] = messages[0] if messages else None

        return conversations

    async def create_indexes(self):
        """创建索引以优化查询性能

        创建的索引：
        1. user_id + last_message_at - 优化用户会话列表查询
        2. last_message_at (倒序) - 优化最近会话查询
        3. title (文本索引) - 优化标题搜索
        4. messages.content (文本索引) - 优化消息内容搜索

        Example:
            >>> await repo.create_indexes()
        """
        collection = await self._get_collection()

        # 1. 用户 + 最后消息时间复合索引
        await collection.create_index(
            [("user_id", 1), ("last_message_at", -1)],
            name="user_last_message_idx"
        )

        # 2. 最后消息时间索引（倒序）
        await collection.create_index(
            [("last_message_at", -1)],
            name="last_message_at_desc"
        )

        # 3. 标题文本索引
        await collection.create_index(
            [("title", "text"), ("messages.content", "text")],
            name="search_text_idx",
            default_language="none"  # 支持中文
        )

        # 4. 创建时间索引
        await collection.create_index(
            [("created_at", -1)],
            name="created_at_desc"
        )

        logger.info("对话会话索引创建完成")


# 全局实例
chat_conversation_repository = ChatConversationRepository()
