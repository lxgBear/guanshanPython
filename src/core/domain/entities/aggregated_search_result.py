"""聚合搜索结果实体

v1.5.2 新增实体：智能搜索聚合结果的专用存储结构

用途：
- 存储智能搜索系统的去重聚合结果
- 包含综合评分、多源信息等聚合字段
- 职责分离：区别于即时搜索的原始结果（instant_search_results）

集合映射：
- smart_search_results: 存储 AggregatedSearchResult
- instant_search_results: 存储 SearchResult（原始子查询结果）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.search_result import ResultStatus


@dataclass
class SourceInfo:
    """结果来源信息

    表示该结果出现在哪个子查询中的位置和评分
    """
    query: str = ""  # 子查询文本
    task_id: str = ""  # 子搜索任务ID
    position: int = 0  # 在该查询结果中的位置（1-based）
    relevance_score: float = 0.0  # 在该查询中的相关性评分


@dataclass
class AggregatedSearchResult:
    """聚合搜索结果实体

    v1.5.2: 智能搜索专用结果存储，包含跨查询聚合信息

    职责分离：
    - SearchResult: 单个子搜索的原始结果（存储在 instant_search_results）
    - AggregatedSearchResult: 跨查询去重聚合后的结果（存储在 smart_search_results）
    """

    # ========== 核心标识 ==========
    id: str = field(default_factory=generate_string_id)
    smart_task_id: str = ""  # 智能搜索任务ID

    # ========== 基础搜索结果字段 ==========
    # 继承自SearchResult的核心字段
    title: str = ""
    url: str = ""
    content: str = ""
    snippet: Optional[str] = None

    # ========== 聚合评分字段 ==========
    composite_score: float = 0.0  # 综合评分（多源加权计算）

    # 分项评分（用于透明度和调试）
    avg_relevance_score: float = 0.0  # 平均相关性评分
    avg_quality_score: float = 0.0  # 平均质量评分
    position_score: float = 0.0  # 位置评分（越靠前越高）
    multi_source_score: float = 0.0  # 多源评分（出现次数越多越高）

    # ========== 多源信息 ==========
    sources: List[SourceInfo] = field(default_factory=list)  # 所有来源列表
    source_count: int = 0  # 出现在多少个查询中
    multi_source_bonus: bool = False  # 是否获得多源奖励（source_count > 1）

    # ========== 元数据 ==========
    result_type: str = "web"  # 结果类型（web/pdf/video等）
    language: Optional[str] = None  # 内容语言
    published_date: Optional[datetime] = None  # 发布日期

    # ========== 状态管理 ==========
    status: ResultStatus = ResultStatus.PENDING  # 结果状态
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ========== 附加信息 ==========
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于MongoDB存储）

        v1.5.2: 支持雪花ID系统
        """
        return {
            "id": self.id,
            "smart_task_id": self.smart_task_id,

            # 基础字段
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,

            # 聚合评分
            "composite_score": self.composite_score,
            "avg_relevance_score": self.avg_relevance_score,
            "avg_quality_score": self.avg_quality_score,
            "position_score": self.position_score,
            "multi_source_score": self.multi_source_score,

            # 多源信息
            "sources": [
                {
                    "query": s.query,
                    "task_id": s.task_id,
                    "position": s.position,
                    "relevance_score": s.relevance_score
                }
                for s in self.sources
            ],
            "source_count": self.source_count,
            "multi_source_bonus": self.multi_source_bonus,

            # 元数据
            "result_type": self.result_type,
            "language": self.language,
            "published_date": self.published_date.isoformat() if self.published_date else None,

            # 状态
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),

            # 附加
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregatedSearchResult":
        """从字典创建实体（用于MongoDB读取）

        v1.5.2: 支持雪花ID系统，直接使用字符串ID
        """
        # 处理来源列表
        sources = [
            SourceInfo(
                query=s.get("query", ""),
                task_id=s.get("task_id", ""),
                position=s.get("position", 0),
                relevance_score=s.get("relevance_score", 0.0)
            )
            for s in data.get("sources", [])
        ]

        # 处理日期时间
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        published_date = data.get("published_date")
        if isinstance(published_date, str):
            published_date = datetime.fromisoformat(published_date)

        # 处理状态枚举
        status = data.get("status", "PENDING")
        if isinstance(status, str):
            status = ResultStatus[status]

        return cls(
            id=str(data.get("id", "")),
            smart_task_id=str(data.get("smart_task_id", "")),

            # 基础字段
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            snippet=data.get("snippet"),

            # 聚合评分
            composite_score=data.get("composite_score", 0.0),
            avg_relevance_score=data.get("avg_relevance_score", 0.0),
            avg_quality_score=data.get("avg_quality_score", 0.0),
            position_score=data.get("position_score", 0.0),
            multi_source_score=data.get("multi_source_score", 0.0),

            # 多源信息
            sources=sources,
            source_count=data.get("source_count", 0),
            multi_source_bonus=data.get("multi_source_bonus", False),

            # 元数据
            result_type=data.get("result_type", "web"),
            language=data.get("language"),
            published_date=published_date,

            # 状态
            status=status,
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow(),

            # 附加
            metadata=data.get("metadata", {})
        )

    def update_composite_score(self):
        """重新计算综合评分

        综合评分公式：
        composite_score = 0.4 * multi_source_score + 0.4 * avg_relevance_score + 0.2 * position_score

        权重说明：
        - multi_source_score (40%): 出现在多个查询中的结果更重要
        - avg_relevance_score (40%): 平均相关性评分
        - position_score (20%): 原始搜索结果中的位置
        """
        self.composite_score = (
            0.4 * self.multi_source_score +
            0.4 * self.avg_relevance_score +
            0.2 * self.position_score
        )

        # 更新时间戳
        self.updated_at = datetime.utcnow()
