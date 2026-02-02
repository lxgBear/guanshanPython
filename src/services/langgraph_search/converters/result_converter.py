"""搜索结果转换器

将 LangGraph 内部 SearchResult 转换为数据库实体格式。
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from ..state import SearchResult as LangGraphSearchResult
from src.core.domain.entities.search_result import SearchResult as DBSearchResult
from src.infrastructure.id_generator import generate_string_id


class ResultConverter:
    """搜索结果转换器

    提供 LangGraph SearchResult 与数据库 SearchResult 之间的双向转换。

    多用户隔离说明:
    - 转换时会将 user_id 写入结果的 metadata 字段
    - 等待 SearchResult 实体添加 user_id 字段后可直接映射

    Example:
        >>> lg_result = LangGraphSearchResult(url="...", title="...")
        >>> db_result = ResultConverter.to_db_entity(
        ...     lg_result,
        ...     task_id="123",
        ...     user_id="456"
        ... )
    """

    @staticmethod
    def to_db_entity(
        langgraph_result: LangGraphSearchResult,
        task_id: str,
        user_id: str,
        generate_id: bool = True,
    ) -> DBSearchResult:
        """将 LangGraph 结果转换为数据库实体

        Args:
            langgraph_result: LangGraph 搜索结果
            task_id: 关联的任务ID
            user_id: 用户ID (用于多用户隔离)
            generate_id: 是否生成新ID

        Returns:
            数据库 SearchResult 实体
        """
        # 解析发布日期
        published_date = None
        if langgraph_result.published_date:
            try:
                published_date = datetime.fromisoformat(
                    langgraph_result.published_date.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # 构建 metadata，包含 LangGraph 特有字段
        metadata = {
            # 分层搜索信息
            "layer": langgraph_result.layer,
            "layer_name": langgraph_result.layer_name,
            "source_tier": langgraph_result.source_tier,
            # 评分信息
            "relevance_score": langgraph_result.relevance_score,
            "credibility_score": langgraph_result.credibility_score,
            "final_score": langgraph_result.final_score,
        }

        # 创建数据库实体
        db_result = DBSearchResult(
            id=generate_string_id() if generate_id else "",
            task_id=task_id,
            # v2.0.0: 多用户数据隔离
            user_id=user_id,
            created_by=user_id,
            # 核心字段
            title=langgraph_result.title,
            url=langgraph_result.url,
            snippet=langgraph_result.snippet,
            source=langgraph_result.source_domain or "web",
            published_date=published_date,
            language=langgraph_result.language,
            markdown_content=langgraph_result.markdown_content,
            # v4.9.2: 移除 html_content 字段
            metadata=metadata,
            relevance_score=langgraph_result.relevance_score,
            quality_score=langgraph_result.credibility_score,
            created_at=langgraph_result.fetched_at or datetime.utcnow(),
        )

        # 生成内容哈希用于去重
        db_result.ensure_content_hash()

        return db_result

    @staticmethod
    def from_db_entity(
        db_result: DBSearchResult,
    ) -> LangGraphSearchResult:
        """将数据库实体转换为 LangGraph 结果

        Args:
            db_result: 数据库 SearchResult 实体

        Returns:
            LangGraph SearchResult
        """
        metadata = db_result.metadata or {}

        return LangGraphSearchResult(
            url=db_result.url,
            title=db_result.title,
            snippet=db_result.snippet or "",
            source_domain=db_result.source,
            layer=metadata.get("layer", 0),
            layer_name=metadata.get("layer_name", "未知"),
            source_tier=metadata.get("source_tier", 4),
            relevance_score=db_result.relevance_score,
            credibility_score=db_result.quality_score,
            final_score=metadata.get("final_score", 0.0),
            markdown_content=db_result.markdown_content,
            # v4.9.2: 移除 html_content 字段
            language=db_result.language or "en",
            published_date=(
                db_result.published_date.isoformat()
                if db_result.published_date
                else None
            ),
            fetched_at=db_result.created_at,
        )

    @staticmethod
    def to_db_entities_batch(
        langgraph_results: List[LangGraphSearchResult],
        task_id: str,
        user_id: str,
    ) -> List[DBSearchResult]:
        """批量转换 LangGraph 结果为数据库实体

        Args:
            langgraph_results: LangGraph 结果列表
            task_id: 关联的任务ID
            user_id: 用户ID

        Returns:
            数据库 SearchResult 实体列表
        """
        return [
            ResultConverter.to_db_entity(result, task_id, user_id)
            for result in langgraph_results
        ]

    @staticmethod
    def to_api_response(
        db_result: DBSearchResult,
        include_content: bool = False,
    ) -> Dict[str, Any]:
        """将数据库实体转换为 API 响应格式

        Args:
            db_result: 数据库实体
            include_content: 是否包含完整内容

        Returns:
            API 响应字典
        """
        metadata = db_result.metadata or {}

        response = {
            "id": db_result.id,
            "task_id": db_result.task_id,
            "title": db_result.title,
            "url": db_result.url,
            "snippet": db_result.snippet,
            "source": db_result.source,
            "language": db_result.language,
            "published_date": (
                db_result.published_date.isoformat()
                if db_result.published_date
                else None
            ),
            # 分层信息
            "layer": metadata.get("layer"),
            "layer_name": metadata.get("layer_name"),
            "source_tier": metadata.get("source_tier"),
            # 评分
            "relevance_score": db_result.relevance_score,
            "quality_score": db_result.quality_score,
            "final_score": metadata.get("final_score"),
            # 时间
            "created_at": db_result.created_at.isoformat(),
        }

        if include_content:
            response["markdown_content"] = db_result.markdown_content
            # v4.9.2: 移除 html_content 字段

        return response

    @staticmethod
    def extract_user_id(db_result: DBSearchResult) -> Optional[str]:
        """从数据库实体中提取用户ID

        Args:
            db_result: 数据库实体

        Returns:
            用户ID，如果不存在则返回 None
        """
        # v2.0.0: 优先使用新的 user_id 字段
        if db_result.user_id:
            return db_result.user_id
        # 兼容旧数据: 从 metadata 中读取
        if db_result.metadata:
            return db_result.metadata.get("user_id")
        return None
