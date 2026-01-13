"""聚合搜索结果转换器

将 LangGraph 聚合结果转换为数据库实体格式。
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from ..state import SearchResult as LangGraphSearchResult
from src.core.domain.entities.aggregated_search_result import (
    AggregatedSearchResult,
    SourceInfo,
)
from src.infrastructure.id_generator import generate_string_id


class AggregatedResultConverter:
    """聚合搜索结果转换器

    将 LangGraph 去重聚合后的结果转换为 AggregatedSearchResult 实体。

    多用户隔离说明:
    - 转换时会将 user_id 写入结果的 metadata 字段
    - 等待 AggregatedSearchResult 实体添加 user_id 字段后可直接映射

    Example:
        >>> aggregated_results = [...]  # LangGraph 聚合结果
        >>> db_results = AggregatedResultConverter.to_db_entities(
        ...     aggregated_results,
        ...     smart_task_id="123",
        ...     user_id="456"
        ... )
    """

    @staticmethod
    def to_db_entity(
        langgraph_result: LangGraphSearchResult,
        smart_task_id: str,
        user_id: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        generate_id: bool = True,
    ) -> AggregatedSearchResult:
        """将 LangGraph 结果转换为聚合结果实体

        Args:
            langgraph_result: LangGraph 搜索结果
            smart_task_id: 智能搜索任务ID
            user_id: 用户ID (用于多用户隔离)
            sources: 结果来源信息列表
            generate_id: 是否生成新ID

        Returns:
            AggregatedSearchResult 实体
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

        # 转换来源信息
        source_infos = []
        if sources:
            for s in sources:
                source_infos.append(
                    SourceInfo(
                        query=s.get("query", ""),
                        task_id=s.get("task_id", ""),
                        position=s.get("position", 0),
                        relevance_score=s.get("relevance_score", 0.0),
                    )
                )

        source_count = len(source_infos)
        multi_source_bonus = source_count > 1

        # 计算多源评分
        multi_source_score = min(1.0, source_count * 0.25)  # 每个来源增加0.25，最高1.0

        # 计算位置评分 (基于来源中的最佳位置)
        if source_infos:
            best_position = min(s.position for s in source_infos)
            position_score = max(0.0, 1.0 - (best_position - 1) * 0.1)
        else:
            position_score = 0.5

        # 构建 metadata，包含 LangGraph 特有字段
        metadata = {
            # 分层搜索信息
            "layer": langgraph_result.layer,
            "layer_name": langgraph_result.layer_name,
            "source_tier": langgraph_result.source_tier,
            "source_domain": langgraph_result.source_domain,
            # 原始评分
            "credibility_score": langgraph_result.credibility_score,
            "final_score": langgraph_result.final_score,
        }

        # 创建聚合结果实体
        aggregated = AggregatedSearchResult(
            id=generate_string_id() if generate_id else "",
            smart_task_id=smart_task_id,
            # v2.0.0: 多用户数据隔离
            user_id=user_id,
            created_by=user_id,
            # 核心字段
            title=langgraph_result.title,
            url=langgraph_result.url,
            content=langgraph_result.markdown_content or "",
            snippet=langgraph_result.snippet,
            # 评分
            composite_score=langgraph_result.final_score,
            avg_relevance_score=langgraph_result.relevance_score,
            avg_quality_score=langgraph_result.credibility_score,
            position_score=position_score,
            multi_source_score=multi_source_score,
            # 多源信息
            sources=source_infos,
            source_count=source_count,
            multi_source_bonus=multi_source_bonus,
            # 元数据
            result_type="web",
            language=langgraph_result.language,
            published_date=published_date,
            # 附加
            metadata=metadata,
            created_at=langgraph_result.fetched_at or datetime.utcnow(),
        )

        # 更新综合评分
        aggregated.update_composite_score()

        return aggregated

    @staticmethod
    def from_db_entity(
        db_result: AggregatedSearchResult,
    ) -> LangGraphSearchResult:
        """将数据库实体转换为 LangGraph 结果

        Args:
            db_result: AggregatedSearchResult 实体

        Returns:
            LangGraph SearchResult
        """
        metadata = db_result.metadata or {}

        return LangGraphSearchResult(
            url=db_result.url,
            title=db_result.title,
            snippet=db_result.snippet or "",
            source_domain=metadata.get("source_domain", ""),
            layer=metadata.get("layer", 0),
            layer_name=metadata.get("layer_name", "未知"),
            source_tier=metadata.get("source_tier", 4),
            relevance_score=db_result.avg_relevance_score,
            credibility_score=db_result.avg_quality_score,
            final_score=db_result.composite_score,
            markdown_content=db_result.content,
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
        smart_task_id: str,
        user_id: str,
        sources_map: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> List[AggregatedSearchResult]:
        """批量转换 LangGraph 结果为聚合结果实体

        Args:
            langgraph_results: LangGraph 结果列表
            smart_task_id: 智能搜索任务ID
            user_id: 用户ID
            sources_map: URL → 来源信息列表的映射

        Returns:
            AggregatedSearchResult 实体列表
        """
        sources_map = sources_map or {}
        return [
            AggregatedResultConverter.to_db_entity(
                result,
                smart_task_id,
                user_id,
                sources=sources_map.get(result.url),
            )
            for result in langgraph_results
        ]

    @staticmethod
    def to_api_response(
        db_result: AggregatedSearchResult,
        include_content: bool = False,
        include_sources: bool = True,
    ) -> Dict[str, Any]:
        """将数据库实体转换为 API 响应格式

        Args:
            db_result: 数据库实体
            include_content: 是否包含完整内容
            include_sources: 是否包含来源详情

        Returns:
            API 响应字典
        """
        metadata = db_result.metadata or {}

        response = {
            "id": db_result.id,
            "smart_task_id": db_result.smart_task_id,
            "title": db_result.title,
            "url": db_result.url,
            "snippet": db_result.snippet,
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
            "source_domain": metadata.get("source_domain"),
            # 评分
            "composite_score": db_result.composite_score,
            "relevance_score": db_result.avg_relevance_score,
            "quality_score": db_result.avg_quality_score,
            "position_score": db_result.position_score,
            "multi_source_score": db_result.multi_source_score,
            # 多源信息
            "source_count": db_result.source_count,
            "multi_source_bonus": db_result.multi_source_bonus,
            # 时间
            "created_at": db_result.created_at.isoformat(),
        }

        if include_content:
            response["content"] = db_result.content

        if include_sources and db_result.sources:
            response["sources"] = [
                {
                    "query": s.query,
                    "task_id": s.task_id,
                    "position": s.position,
                    "relevance_score": s.relevance_score,
                }
                for s in db_result.sources
            ]

        return response

    @staticmethod
    def extract_user_id(db_result: AggregatedSearchResult) -> Optional[str]:
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

    @staticmethod
    def merge_results(
        results: List[LangGraphSearchResult],
        user_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """合并相同 URL 的结果，构建来源映射

        Args:
            results: LangGraph 结果列表
            user_id: 用户ID

        Returns:
            URL → 合并信息的映射，包含:
            - result: 最佳结果
            - sources: 来源列表
        """
        from ..utils.url_utils import normalize_url

        url_map: Dict[str, Dict[str, Any]] = {}

        for i, result in enumerate(results):
            normalized_url = normalize_url(result.url)

            if normalized_url not in url_map:
                url_map[normalized_url] = {
                    "result": result,
                    "sources": [],
                }

            # 添加来源信息
            url_map[normalized_url]["sources"].append({
                "query": "",  # 查询词由调用方设置
                "task_id": "",  # 任务ID由调用方设置
                "position": i + 1,
                "relevance_score": result.relevance_score,
            })

            # 如果新结果分数更高，替换主结果
            current_best = url_map[normalized_url]["result"]
            if result.final_score > current_best.final_score:
                url_map[normalized_url]["result"] = result

        return url_map
