"""查询分解实体模型

用于智能搜索系统的LLM查询分解功能
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DecomposedQuery:
    """分解的子查询"""
    query: str  # 子查询文本
    reasoning: str  # 为什么需要这个子查询的解释
    focus: str  # 关注的信息维度


@dataclass
class QueryDecomposition:
    """
    查询分解结果实体

    由LLM Service调用GPT-4生成，包含分解的子查询列表和整体策略说明
    """
    # 分解的子查询列表
    decomposed_queries: List[DecomposedQuery] = field(default_factory=list)

    # 整体分解策略说明
    overall_strategy: str = ""

    # LLM元数据
    tokens_used: int = 0  # 消耗的token数
    model: str = "gpt-4"  # 使用的模型

    def to_dict(self):
        """转换为字典"""
        return {
            "decomposed_queries": [
                {
                    "query": q.query,
                    "reasoning": q.reasoning,
                    "focus": q.focus
                }
                for q in self.decomposed_queries
            ],
            "overall_strategy": self.overall_strategy,
            "tokens_used": self.tokens_used,
            "model": self.model
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueryDecomposition":
        """从字典创建实例"""
        return cls(
            decomposed_queries=[
                DecomposedQuery(
                    query=q["query"],
                    reasoning=q["reasoning"],
                    focus=q["focus"]
                )
                for q in data.get("decomposed_queries", [])
            ],
            overall_strategy=data.get("overall_strategy", ""),
            tokens_used=data.get("tokens_used", 0),
            model=data.get("model", "gpt-4")
        )
