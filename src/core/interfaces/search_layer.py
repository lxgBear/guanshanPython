"""搜索层接口定义

定义搜索引擎层的专用接口和数据模型。
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .layer import ILayer, LayerContext, LayerResult, LayerStatus


@dataclass
class SearchResultItem:
    """搜索结果项

    Attributes:
        url: 结果URL
        title: 标题
        snippet: 摘要
        content: 完整内容（可选）
        layer: 搜索层级 (0-4)
        layer_name: 层级名称
        score: 综合评分
        relevance_score: 相关性评分
        credibility_score: 可信度评分
        source_domain: 来源域名
        source_tier: 来源等级
        language: 语言
        published_date: 发布日期
        metadata: 额外元数据
    """
    url: str
    title: str
    snippet: str
    content: Optional[str] = None
    layer: int = 0
    layer_name: str = ""
    score: float = 0.0
    relevance_score: float = 0.0
    credibility_score: float = 0.0
    source_domain: str = ""
    source_tier: int = 1
    language: str = "zh"
    published_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "content": self.content,
            "layer": self.layer,
            "layer_name": self.layer_name,
            "score": self.score,
            "relevance_score": self.relevance_score,
            "credibility_score": self.credibility_score,
            "source_domain": self.source_domain,
            "source_tier": self.source_tier,
            "language": self.language,
            "published_date": self.published_date,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResultItem":
        """从字典创建"""
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            snippet=data.get("snippet", ""),
            content=data.get("content") or data.get("markdown_content"),
            layer=data.get("layer", 0),
            layer_name=data.get("layer_name", ""),
            score=data.get("score") or data.get("final_score", 0.0),
            relevance_score=data.get("relevance_score", 0.0),
            credibility_score=data.get("credibility_score", 0.0),
            source_domain=data.get("source_domain", ""),
            source_tier=data.get("source_tier", 1),
            language=data.get("language", "zh"),
            published_date=data.get("published_date"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SearchStatistics:
    """搜索统计信息"""
    total_results: int = 0
    unique_domains: int = 0
    layer_distribution: Dict[int, int] = field(default_factory=dict)
    tier_distribution: Dict[int, int] = field(default_factory=dict)
    language_distribution: Dict[str, int] = field(default_factory=dict)
    execution_time_ms: int = 0
    search_engine: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_results": self.total_results,
            "unique_domains": self.unique_domains,
            "layer_distribution": self.layer_distribution,
            "tier_distribution": self.tier_distribution,
            "language_distribution": self.language_distribution,
            "execution_time_ms": self.execution_time_ms,
            "search_engine": self.search_engine,
        }


@dataclass
class SearchLayerResult(LayerResult):
    """搜索层结果

    继承自 LayerResult，添加搜索特有的字段。
    """
    results: List[SearchResultItem] = field(default_factory=list)
    statistics: Optional[SearchStatistics] = None
    task_id: str = ""

    @property
    def result_count(self) -> int:
        """结果数量"""
        return len(self.results)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        base = super().to_dict()
        base.update({
            "results": [r.to_dict() for r in self.results],
            "statistics": self.statistics.to_dict() if self.statistics else None,
            "task_id": self.task_id,
            "result_count": self.result_count,
        })
        return base


class ISearchLayer(ILayer):
    """搜索层接口

    搜索层负责:
    1. 执行搜索查询（LangGraph 或 NL Search）
    2. 将结果保存到 langgraph_search_results 集合
    3. 发送搜索完成事件

    搜索层不负责:
    - 调用 AI 服务
    - 处理对话历史
    - 推送到前端
    """

    @property
    def layer_type(self) -> str:
        return "search"

    @abstractmethod
    async def execute(self, context: LayerContext) -> SearchLayerResult:
        """执行搜索

        Args:
            context: 层执行上下文

        Returns:
            SearchLayerResult: 搜索结果，包含结果列表和统计信息
        """
        pass

    @abstractmethod
    async def get_search_status(self, task_id: str) -> str:
        """获取搜索状态

        Args:
            task_id: 任务ID

        Returns:
            str: 状态字符串 (pending | running | completed | failed)
        """
        pass

    @abstractmethod
    async def get_search_results(
        self,
        task_id: str,
    ) -> Optional[SearchLayerResult]:
        """获取搜索结果

        Args:
            task_id: 任务ID

        Returns:
            搜索结果，如果不存在则返回 None
        """
        pass
