"""
用户选择事件仓储
记录用户对搜索结果的选择行为

版本: v1.0.0
日期: 2025-11-17
作者: Claude Code Backend Engineer
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.id_generator import generate_string_id

logger = logging.getLogger(__name__)


class UserSelectionEventRepository:
    """
    用户选择事件仓储

    用于记录和查询用户对 NL Search 搜索结果的选择行为。

    集合: user_selection_events

    文档结构:
    {
        "_id": "event_123456789",
        "log_id": "248728141926559744",
        "result_url": "https://example.com/article",
        "action_type": "click",
        "user_id": "user_123",
        "selected_at": ISODate(...),
        "user_agent": "Mozilla/5.0...",
        "ip_address": "192.168.1.1"
    }

    Example:
        >>> repo = UserSelectionEventRepository()
        >>> event_id = await repo.create(
        ...     log_id="248728141926559744",
        ...     result_url="https://example.com",
        ...     action_type="click"
        ... )
    """

    def __init__(self):
        """初始化仓储"""
        self.db = None
        self.collection_name = "user_selection_events"

    async def _get_collection(self):
        """获取 MongoDB 集合"""
        if self.db is None:
            self.db = await get_mongodb_database()
        return self.db[self.collection_name]

    async def create(
        self,
        log_id: str,
        result_url: str,
        action_type: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        创建用户选择事件

        Args:
            log_id: 搜索记录ID（雪花算法ID字符串）
            result_url: 选中的结果URL
            action_type: 操作类型 (click, bookmark, archive)
            user_id: 用户ID（可选）
            user_agent: 用户代理字符串（可选）
            ip_address: 客户端IP地址（可选）

        Returns:
            str: 创建的事件ID（雪花算法ID字符串）

        Example:
            >>> event_id = await repo.create(
            ...     log_id="248728141926559744",
            ...     result_url="https://example.com/gpt5",
            ...     action_type="click",
            ...     user_id="user_123"
            ... )
        """
        collection = await self._get_collection()

        # 生成事件ID
        event_id = generate_string_id()

        # 准备文档
        document = {
            "_id": event_id,
            "log_id": log_id,
            "result_url": result_url,
            "action_type": action_type,
            "user_id": user_id,
            "selected_at": datetime.utcnow(),
            "user_agent": user_agent,
            "ip_address": ip_address
        }

        # 插入文档
        await collection.insert_one(document)

        logger.info(
            f"创建用户选择事件: event_id={event_id}, "
            f"log_id={log_id}, action={action_type}"
        )

        return event_id

    async def get_by_log_id(
        self,
        log_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取某次搜索的所有用户选择事件

        Args:
            log_id: 搜索记录ID
            limit: 返回数量限制

        Returns:
            List[Dict]: 事件列表，按时间倒序排列

        Example:
            >>> events = await repo.get_by_log_id("248728141926559744")
            >>> for event in events:
            ...     print(event["result_url"], event["action_type"])
        """
        collection = await self._get_collection()

        # 查询事件（按时间倒序）
        cursor = collection.find(
            {"log_id": log_id}
        ).sort("selected_at", -1).limit(limit)

        events = await cursor.to_list(length=limit)
        return events

    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取某用户的所有选择事件

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            List[Dict]: 事件列表

        Example:
            >>> events = await repo.get_by_user_id("user_123", limit=20)
        """
        collection = await self._get_collection()

        # 查询事件
        cursor = collection.find(
            {"user_id": user_id}
        ).sort("selected_at", -1).skip(offset).limit(limit)

        events = await cursor.to_list(length=limit)
        return events

    async def count_by_log_id(self, log_id: str) -> int:
        """
        统计某次搜索的选择次数

        Args:
            log_id: 搜索记录ID

        Returns:
            int: 选择次数

        Example:
            >>> count = await repo.count_by_log_id("248728141926559744")
            >>> print(f"该搜索被选择了 {count} 次")
        """
        collection = await self._get_collection()
        return await collection.count_documents({"log_id": log_id})

    async def create_indexes(self):
        """
        创建索引以优化查询性能

        索引列表:
        1. log_id + selected_at (倒序) - 查询某次搜索的选择历史
        2. user_id + selected_at (倒序) - 查询某用户的选择历史
        3. selected_at (倒序) - 全局时间排序

        Example:
            >>> await repo.create_indexes()
        """
        collection = await self._get_collection()

        # 1. log_id + 时间索引
        await collection.create_index(
            [("log_id", 1), ("selected_at", -1)],
            name="log_time_idx"
        )

        # 2. user_id + 时间索引
        await collection.create_index(
            [("user_id", 1), ("selected_at", -1)],
            name="user_time_idx"
        )

        # 3. 时间索引
        await collection.create_index(
            [("selected_at", -1)],
            name="time_idx"
        )

        logger.info("✅ 用户选择事件索引创建完成")


# 全局实例
user_selection_repository = UserSelectionEventRepository()
