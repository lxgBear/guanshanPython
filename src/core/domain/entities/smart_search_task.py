"""智能搜索任务实体模型

v2.0.0 智能搜索系统核心实体：
- 支持LLM查询分解
- 用户确认机制
- 并发子搜索执行
- 结果聚合统计
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional

from src.infrastructure.id_generator import generate_string_id
from src.core.domain.entities.query_decomposition import DecomposedQuery


class SmartSearchStatus(str, Enum):
    """智能搜索状态枚举"""
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # 等待用户确认
    SEARCHING = "searching"                          # 搜索中
    COMPLETED = "completed"                          # 全部成功
    PARTIAL_SUCCESS = "partial_success"              # 部分成功
    FAILED = "failed"                                # 全部失败
    EXPIRED = "expired"                              # 确认超时


@dataclass
class SubSearchResult:
    """子搜索结果摘要"""
    query: str  # 子查询
    task_id: str  # InstantSearchTask ID
    status: str  # completed | failed
    result_count: int = 0  # 结果数量
    credits_used: int = 0  # 消耗积分
    execution_time_ms: int = 0  # 执行时间（毫秒）
    error: Optional[str] = None  # 错误信息
    retryable: bool = False  # 是否可重试


@dataclass
class SmartSearchTask:
    """
    智能搜索任务实体

    核心功能：
    - LLM查询分解：将复杂查询分解为多个子查询
    - 用户确认：展示分解结果供用户审核和修改
    - 并发搜索：异步执行多个子查询
    - 结果聚合：跨查询去重和智能评分
    """

    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 基本信息
    name: str = ""  # 任务名称
    description: str = "智能搜索任务"  # 任务描述
    original_query: str = ""  # 原始查询
    search_config: Dict[str, Any] = field(default_factory=dict)  # 搜索配置

    # 分解阶段（LLM输出）
    decomposed_queries: List[DecomposedQuery] = field(default_factory=list)  # 分解的子查询
    llm_model: str = "gpt-4"  # 使用的LLM模型
    llm_reasoning: str = ""  # LLM分解推理过程
    decomposition_tokens_used: int = 0  # 分解消耗的token数

    # 确认阶段（用户修改）
    user_confirmed_queries: List[str] = field(default_factory=list)  # 用户确认的查询列表
    user_modifications: Dict[str, List[str]] = field(default_factory=dict)  # 用户修改记录

    # 执行阶段（子搜索任务）
    sub_search_task_ids: List[str] = field(default_factory=list)  # 子搜索任务ID列表
    sub_search_results: Dict[str, SubSearchResult] = field(default_factory=dict)  # 子搜索结果摘要

    # 聚合统计
    aggregated_stats: Dict[str, Any] = field(default_factory=dict)  # 聚合统计信息

    # 状态管理
    status: SmartSearchStatus = SmartSearchStatus.AWAITING_CONFIRMATION
    created_by: str = "system"  # 创建者
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None  # 用户确认时间
    started_at: Optional[datetime] = None  # 开始搜索时间
    completed_at: Optional[datetime] = None  # 完成时间

    # 元数据
    execution_time_ms: int = 0  # 总执行时间（毫秒）
    error_message: Optional[str] = None  # 错误信息

    def mark_as_awaiting_confirmation(self) -> None:
        """标记为等待确认"""
        self.status = SmartSearchStatus.AWAITING_CONFIRMATION
        self.updated_at = datetime.utcnow()

    def mark_as_searching(self) -> None:
        """标记为搜索中"""
        self.status = SmartSearchStatus.SEARCHING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_completed(self, stats: Dict[str, Any]) -> None:
        """
        标记为完成（全部子搜索成功）

        Args:
            stats: 聚合统计信息
        """
        self.status = SmartSearchStatus.COMPLETED
        self.aggregated_stats = stats
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_partial_success(self, stats: Dict[str, Any]) -> None:
        """
        标记为部分成功（部分子搜索失败）

        Args:
            stats: 聚合统计信息
        """
        self.status = SmartSearchStatus.PARTIAL_SUCCESS
        self.aggregated_stats = stats
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self, error_message: str) -> None:
        """标记为失败"""
        self.status = SmartSearchStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_expired(self) -> None:
        """标记为过期（确认超时）"""
        self.status = SmartSearchStatus.EXPIRED
        self.error_message = "用户确认超时（24小时）"
        self.updated_at = datetime.utcnow()

    def add_sub_search_result(self, task_id: str, result: SubSearchResult) -> None:
        """
        添加子搜索结果

        Args:
            task_id: InstantSearchTask ID
            result: 子搜索结果摘要
        """
        self.sub_search_results[task_id] = result
        self.updated_at = datetime.utcnow()

    def calculate_execution_time(self) -> int:
        """
        计算总执行时间（毫秒）

        Returns:
            执行时间（毫秒）
        """
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return 0

    def get_success_rate(self) -> float:
        """
        获取成功率

        Returns:
            成功率（0.0-1.0）
        """
        if not self.sub_search_results:
            return 0.0

        total = len(self.sub_search_results)
        successful = sum(
            1 for r in self.sub_search_results.values()
            if r.status == "completed"
        )

        return successful / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应和数据库存储）"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "original_query": self.original_query,
            "search_config": self.search_config,

            # 分解阶段
            "decomposed_queries": [
                {
                    "query": q.query,
                    "reasoning": q.reasoning,
                    "focus": q.focus
                }
                for q in self.decomposed_queries
            ],
            "llm_model": self.llm_model,
            "llm_reasoning": self.llm_reasoning,
            "decomposition_tokens_used": self.decomposition_tokens_used,

            # 确认阶段
            "user_confirmed_queries": self.user_confirmed_queries,
            "user_modifications": self.user_modifications,

            # 执行阶段
            "sub_search_task_ids": self.sub_search_task_ids,
            "sub_search_results": {
                task_id: {
                    "query": r.query,
                    "task_id": r.task_id,
                    "status": r.status,
                    "result_count": r.result_count,
                    "credits_used": r.credits_used,
                    "execution_time_ms": r.execution_time_ms,
                    "error": r.error,
                    "retryable": r.retryable
                }
                for task_id, r in self.sub_search_results.items()
            },

            # 聚合统计
            "aggregated_stats": self.aggregated_stats,

            # 状态管理
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,

            # 元数据
            "execution_time_ms": self.execution_time_ms or self.calculate_execution_time(),
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SmartSearchTask":
        """从字典创建实例（用于数据库查询）"""
        # 转换时间字段
        def parse_datetime(dt_str):
            if dt_str:
                return datetime.fromisoformat(dt_str) if isinstance(dt_str, str) else dt_str
            return None

        # 转换DecomposedQuery对象
        decomposed_queries = [
            DecomposedQuery(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in data.get("decomposed_queries", [])
        ]

        # 转换SubSearchResult对象
        sub_search_results = {
            task_id: SubSearchResult(
                query=r["query"],
                task_id=r["task_id"],
                status=r["status"],
                result_count=r.get("result_count", 0),
                credits_used=r.get("credits_used", 0),
                execution_time_ms=r.get("execution_time_ms", 0),
                error=r.get("error"),
                retryable=r.get("retryable", False)
            )
            for task_id, r in data.get("sub_search_results", {}).items()
        }

        return cls(
            id=data.get("id", generate_string_id()),
            name=data.get("name", ""),
            description=data.get("description", "智能搜索任务"),
            original_query=data.get("original_query", ""),
            search_config=data.get("search_config", {}),

            decomposed_queries=decomposed_queries,
            llm_model=data.get("llm_model", "gpt-4"),
            llm_reasoning=data.get("llm_reasoning", ""),
            decomposition_tokens_used=data.get("decomposition_tokens_used", 0),

            user_confirmed_queries=data.get("user_confirmed_queries", []),
            user_modifications=data.get("user_modifications", {}),

            sub_search_task_ids=data.get("sub_search_task_ids", []),
            sub_search_results=sub_search_results,

            aggregated_stats=data.get("aggregated_stats", {}),

            status=SmartSearchStatus(data.get("status", "awaiting_confirmation")),
            created_by=data.get("created_by", "system"),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            confirmed_at=parse_datetime(data.get("confirmed_at")),
            started_at=parse_datetime(data.get("started_at")),
            completed_at=parse_datetime(data.get("completed_at")),

            execution_time_ms=data.get("execution_time_ms", 0),
            error_message=data.get("error_message")
        )
