"""
自然语言搜索记录实体 (简化版)

设计说明:
- 简化版实体，适合 MVP 阶段
- llm_analysis 使用 JSON 字段存储 LLM 解析结果
- 支持 SQLAlchemy ORM 映射
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NLSearchLog(BaseModel):
    """自然语言搜索记录 (简化版)

    存储用户的自然语言查询及 LLM 分析结果。

    Attributes:
        id: 主键ID (数据库自动生成)
        query_text: 原始用户输入的自然语言查询
        llm_analysis: LLM 解析结构，包含关键词、实体、时间范围等
        created_at: 创建时间

    Example:
        >>> log = NLSearchLog(
        ...     query_text="最近有哪些AI技术突破",
        ...     llm_analysis={
        ...         "intent": "technology_news",
        ...         "keywords": ["AI", "技术突破", "2024"],
        ...         "confidence": 0.95
        ...     }
        ... )
    """

    id: Optional[int] = Field(
        None,
        description="主键ID (数据库自动生成)"
    )

    query_text: str = Field(
        ...,
        description="原始用户输入",
        max_length=1000,
        min_length=1
    )

    llm_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="大模型解析结构（关键词、实体、时间范围等）"
    )

    created_at: Optional[datetime] = Field(
        None,
        description="创建时间"
    )

    class Config:
        """Pydantic 配置"""
        from_attributes = True  # SQLAlchemy ORM 支持
        json_schema_extra = {
            "example": {
                "id": 123456,
                "query_text": "最近有哪些AI技术突破",
                "llm_analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破", "2024"],
                    "entities": [
                        {"type": "technology", "value": "AI"}
                    ],
                    "time_range": {
                        "type": "recent",
                        "from": "2024-01-01",
                        "to": "2024-12-31"
                    },
                    "confidence": 0.95
                },
                "created_at": "2024-11-14T10:00:00"
            }
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<NLSearchLog(id={self.id}, query='{self.query_text[:30]}...')>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"NL Search #{self.id}: {self.query_text}"

    @property
    def has_llm_analysis(self) -> bool:
        """是否已完成 LLM 分析"""
        return self.llm_analysis is not None and len(self.llm_analysis) > 0

    @property
    def keywords(self) -> list:
        """提取关键词列表"""
        if not self.has_llm_analysis:
            return []
        return self.llm_analysis.get("keywords", [])

    @property
    def intent(self) -> Optional[str]:
        """提取意图"""
        if not self.has_llm_analysis:
            return None
        return self.llm_analysis.get("intent")

    @property
    def confidence(self) -> float:
        """提取置信度"""
        if not self.has_llm_analysis:
            return 0.0
        return self.llm_analysis.get("confidence", 0.0)
