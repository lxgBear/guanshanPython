"""
用户档案实体

存储用户创建的档案元数据。

设计说明:
- 档案是用户基于AI筛选结果创建的知识管理单元
- 支持标签、描述等元数据
- 关联搜索记录，提供内容溯源
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class NLUserArchive(BaseModel):
    """用户档案实体

    用户基于AI筛选的新闻结果创建的档案，用于知识管理和内容归档。

    Attributes:
        id: 档案唯一ID (数据库自动生成)
        user_id: 用户ID
        archive_name: 档案名称（用户命名）
        description: 档案描述（可选）
        tags: 档案标签列表（可选）
        search_log_id: 关联的搜索记录ID（可选，用于溯源）
        items_count: 档案中的条目数量
        created_at: 创建时间
        updated_at: 最后更新时间

    Example:
        >>> archive = NLUserArchive(
        ...     user_id=1001,
        ...     archive_name="2024年AI技术突破汇总",
        ...     description="整理2024年重要的AI技术突破新闻",
        ...     tags=["AI", "技术", "2024"],
        ...     search_log_id=123456
        ... )
    """

    id: Optional[int] = Field(
        None,
        description="档案唯一ID (数据库自动生成)"
    )

    user_id: int = Field(
        ...,
        description="用户ID",
        gt=0
    )

    archive_name: str = Field(
        ...,
        description="档案名称",
        max_length=255,
        min_length=1
    )

    description: Optional[str] = Field(
        None,
        description="档案描述（可选）",
        max_length=2000
    )

    tags: Optional[List[str]] = Field(
        None,
        description="档案标签列表（可选）"
    )

    search_log_id: Optional[int] = Field(
        None,
        description="关联的搜索记录ID（用于溯源）"
    )

    items_count: int = Field(
        0,
        description="档案中的条目数量",
        ge=0
    )

    created_at: Optional[datetime] = Field(
        None,
        description="创建时间"
    )

    updated_at: Optional[datetime] = Field(
        None,
        description="最后更新时间"
    )

    class Config:
        """Pydantic 配置"""
        from_attributes = True  # SQLAlchemy ORM 支持
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 1001,
                "archive_name": "2024年AI技术突破汇总",
                "description": "整理2024年重要的AI技术突破新闻",
                "tags": ["AI", "技术", "2024"],
                "search_log_id": 123456,
                "items_count": 5,
                "created_at": "2024-11-17T10:00:00",
                "updated_at": "2024-11-17T10:30:00"
            }
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<NLUserArchive(id={self.id}, name='{self.archive_name}', items={self.items_count})>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"档案 #{self.id}: {self.archive_name} ({self.items_count}条)"

    @property
    def has_tags(self) -> bool:
        """是否有标签"""
        return self.tags is not None and len(self.tags) > 0

    @property
    def has_description(self) -> bool:
        """是否有描述"""
        return self.description is not None and len(self.description) > 0

    @property
    def is_linked_to_search(self) -> bool:
        """是否关联搜索记录"""
        return self.search_log_id is not None
