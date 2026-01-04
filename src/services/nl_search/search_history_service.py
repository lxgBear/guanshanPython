"""
Search History Service (v2.8.0)

搜索历史记录服务层，提供业务逻辑封装。

职责:
1. 从 /chat/sync 响应中提取并保存搜索历史
2. 提供历史记录查询接口
3. 支持按 mongo_id 和 source 查询关联历史
4. 统计用户搜索行为

版本: v2.8.0
日期: 2025-01-04
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.infrastructure.database.search_history_repository import search_history_repository

logger = logging.getLogger(__name__)


class SearchHistoryService:
    """搜索历史服务

    提供搜索历史的业务逻辑封装，包括:
    - 从 ChatSyncResponse 提取数据并保存
    - 历史记录的分页查询
    - 按 mongo_id/source 查询关联历史
    - 用户搜索统计

    Example:
        >>> service = SearchHistoryService()
        >>> # 保存搜索历史
        >>> history_id = await service.save_from_sync_response(
        ...     user_id=123,
        ...     question="关于西藏的新闻",
        ...     answer="根据搜索结果...",
        ...     sources=[{"mongo_id": "xxx", "source": "新闻", ...}],
        ...     conversation_id="conv_123"
        ... )
        >>> # 查询历史
        >>> histories = await service.get_user_history(user_id=123)
    """

    def __init__(self):
        """初始化服务"""
        self.repository = search_history_repository

    async def save_from_sync_response(
        self,
        user_id: int,
        question: str,
        answer: str,
        sources: List[Dict[str, Any]],
        conversation_id: Optional[str] = None,
        search_mode: str = "single",
        processing_time_ms: Optional[int] = None
    ) -> str:
        """从 /chat/sync 响应保存搜索历史

        从 ChatSyncResponse 中提取关键数据并存储。

        Args:
            user_id: 用户ID
            question: 用户问题
            answer: AI回答
            sources: 搜索结果来源列表 (SourceDetail 的 dict 格式)
            conversation_id: 关联的对话ID (可选)
            search_mode: 搜索模式 (single/multi)
            processing_time_ms: 处理时间 (毫秒)

        Returns:
            str: 新创建的历史记录ID

        Example:
            >>> sources = [
            ...     {"mongo_id": "xxx", "source": "新闻", "title": "标题", "score": 0.95, ...}
            ... ]
            >>> history_id = await service.save_from_sync_response(
            ...     user_id=123,
            ...     question="西藏新闻",
            ...     answer="AI回答内容",
            ...     sources=sources
            ... )
        """
        # 提取 results 数据 (保存关键字段)
        results = []
        for source in sources:
            result = {
                "mongo_id": source.get("mongo_id", ""),
                "source": source.get("source", "未知"),
                "title": source.get("title", ""),
                "score": source.get("score", 0.0),
                "category": source.get("category", {}),
                "publish_time": source.get("publish_time", ""),
                "preview": source.get("preview", "")[:200] if source.get("preview") else ""
            }
            results.append(result)

        # 构建元数据
        metadata = {
            "search_mode": search_mode,
            "answer_length": len(answer),
            "processing_time_ms": processing_time_ms
        }

        # 保存到仓库
        history_id = await self.repository.create(
            user_id=user_id,
            query=question,
            answer=answer,
            results=results,
            conversation_id=conversation_id,
            metadata=metadata
        )

        logger.info(
            f"Saved search history: id={history_id}, user={user_id}, "
            f"results={len(results)}, mode={search_mode}"
        )

        return history_id

    async def get_user_history(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        source_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取用户搜索历史列表

        Args:
            user_id: 用户ID
            limit: 返回数量限制
            offset: 偏移量
            source_filter: 按来源类型筛选 (可选)

        Returns:
            包含 items 和 total 的字典

        Example:
            >>> result = await service.get_user_history(user_id=123, limit=10)
            >>> print(result["items"])  # 历史记录列表
            >>> print(result["total"])  # 总数量
        """
        items = await self.repository.list_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
            source_filter=source_filter
        )

        total = await self.repository.count_by_user(user_id)

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    async def get_history_detail(
        self,
        history_id: str,
        user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """获取历史记录详情

        Args:
            history_id: 历史记录ID
            user_id: 用户ID (可选，用于权限验证)

        Returns:
            历史记录详情或 None
        """
        return await self.repository.get_by_id(history_id, user_id)

    async def find_by_result_id(
        self,
        mongo_id: str,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """查询引用了特定结果的历史记录

        当用户想知道某个搜索结果被哪些查询引用过时使用。

        Args:
            mongo_id: 原始数据的 MongoDB ID
            user_id: 用户ID (可选，用于权限过滤)
            limit: 返回数量限制

        Returns:
            包含该 mongo_id 的历史记录列表

        Example:
            >>> # 查找引用了某新闻的所有搜索历史
            >>> histories = await service.find_by_result_id("news_xxx")
        """
        return await self.repository.find_by_mongo_id(
            mongo_id=mongo_id,
            user_id=user_id,
            limit=limit
        )

    async def find_by_source_type(
        self,
        source: str,
        user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """按来源类型查询历史记录

        Args:
            source: 来源类型 (如 "新闻", "用户上传")
            user_id: 用户ID (可选)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            包含该来源类型的历史记录列表
        """
        return await self.repository.find_by_source(
            source=source,
            user_id=user_id,
            limit=limit,
            offset=offset
        )

    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """获取用户搜索统计

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        return await self.repository.get_statistics(user_id)

    async def delete_history(self, history_id: str, user_id: int) -> bool:
        """删除历史记录

        Args:
            history_id: 历史记录ID
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        return await self.repository.delete(history_id, user_id)

    async def ensure_indexes(self):
        """确保数据库索引存在"""
        await self.repository.ensure_indexes()


# 全局单例
search_history_service = SearchHistoryService()
