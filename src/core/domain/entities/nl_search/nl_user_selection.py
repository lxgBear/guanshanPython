"""
用户档案条目实体

存储档案中的具体新闻条目，包括用户编辑内容和原始数据快照。

设计说明:
- 快照存储机制防止原始数据被删除后无法查看
- 用户编辑内容优先于原始数据显示
- 支持用户评分、备注等个性化管理
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NLUserSelection(BaseModel):
    """用户档案条目实体

    档案中的具体新闻条目，包含用户编辑内容和原始数据快照。

    Attributes:
        id: 条目唯一ID (数据库自动生成)
        archive_id: 所属档案ID
        user_id: 用户ID（冗余存储，便于查询）
        news_result_id: 新闻结果ID（MongoDB中的ObjectId）
        edited_title: 用户编辑后的标题（可选）
        edited_summary: 用户编辑后的摘要（可选）
        user_notes: 用户备注（可选）
        user_rating: 用户评分（1-5，可选）
        snapshot_data: 原始新闻数据快照（完整JSON）
        display_order: 档案内显示顺序
        created_at: 添加到档案的时间

    Snapshot Data Structure:
        {
            "original_title": "新闻原始标题",
            "original_content": "新闻原始内容",
            "category": {"大类": "安全情报", "类别": "维稳", "地域": "东亚"},
            "published_at": "2023-10-23T12:00:00",
            "source": "example.com",
            "media_urls": ["https://example.com/image1.jpg"]
        }

    Example:
        >>> selection = NLUserSelection(
        ...     archive_id=1,
        ...     user_id=1001,
        ...     news_result_id="507f1f77bcf86cd799439011",
        ...     edited_title="GPT-5发布，AI能力再突破",
        ...     snapshot_data={
        ...         "original_title": "GPT-5 Released with Advanced Capabilities",
        ...         "original_content": "OpenAI announces GPT-5...",
        ...         "category": {"大类": "技术", "类别": "AI"},
        ...         "source": "openai.com"
        ...     }
        ... )
    """

    id: Optional[int] = Field(
        None,
        description="条目唯一ID (数据库自动生成)"
    )

    archive_id: int = Field(
        ...,
        description="所属档案ID",
        gt=0
    )

    user_id: int = Field(
        ...,
        description="用户ID（冗余存储）",
        gt=0
    )

    news_result_id: str = Field(
        ...,
        description="新闻结果ID（MongoDB ObjectId）",
        max_length=255
    )

    # 用户编辑字段
    edited_title: Optional[str] = Field(
        None,
        description="用户编辑后的标题",
        max_length=500
    )

    edited_summary: Optional[str] = Field(
        None,
        description="用户编辑后的摘要",
        max_length=5000
    )

    user_notes: Optional[str] = Field(
        None,
        description="用户备注",
        max_length=2000
    )

    user_rating: Optional[int] = Field(
        None,
        description="用户评分（1-5）",
        ge=1,
        le=5
    )

    # 快照存储
    snapshot_data: Dict[str, Any] = Field(
        ...,
        description="原始新闻数据快照（完整JSON）"
    )

    display_order: int = Field(
        0,
        description="档案内显示顺序",
        ge=0
    )

    created_at: Optional[datetime] = Field(
        None,
        description="添加到档案的时间"
    )

    class Config:
        """Pydantic 配置"""
        from_attributes = True  # SQLAlchemy ORM 支持
        json_schema_extra = {
            "example": {
                "id": 1,
                "archive_id": 1,
                "user_id": 1001,
                "news_result_id": "507f1f77bcf86cd799439011",
                "edited_title": "GPT-5发布，AI能力再突破",
                "edited_summary": "OpenAI发布最新GPT-5模型，在多个基准测试中表现优异",
                "user_notes": "重要技术突破，值得深入研究",
                "user_rating": 5,
                "snapshot_data": {
                    "original_title": "GPT-5 Released with Advanced Capabilities",
                    "original_content": "OpenAI announces GPT-5 with breakthrough improvements...",
                    "category": {"大类": "技术", "类别": "AI", "地域": "北美"},
                    "published_at": "2024-11-15T08:00:00",
                    "source": "openai.com",
                    "media_urls": ["https://openai.com/gpt5-banner.jpg"]
                },
                "display_order": 0,
                "created_at": "2024-11-17T10:00:00"
            }
        }

    def __repr__(self) -> str:
        """字符串表示"""
        title = self.edited_title or self.snapshot_data.get("original_title", "")
        return f"<NLUserSelection(id={self.id}, archive={self.archive_id}, title='{title[:30]}...')>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        title = self.display_title
        return f"档案条目 #{self.id}: {title}"

    @property
    def display_title(self) -> str:
        """显示标题（优先使用编辑标题）"""
        return self.edited_title or self.snapshot_data.get("original_title", "未知标题")

    @property
    def display_content(self) -> str:
        """显示内容（优先使用编辑摘要）"""
        return self.edited_summary or self.snapshot_data.get("original_content", "")

    @property
    def has_user_edits(self) -> bool:
        """是否有用户编辑内容"""
        return bool(self.edited_title or self.edited_summary)

    @property
    def original_title(self) -> Optional[str]:
        """获取原始标题"""
        return self.snapshot_data.get("original_title")

    @property
    def original_content(self) -> Optional[str]:
        """获取原始内容"""
        return self.snapshot_data.get("original_content")

    @property
    def category(self) -> Optional[Dict[str, str]]:
        """获取分类信息"""
        return self.snapshot_data.get("category")

    @property
    def source(self) -> Optional[str]:
        """获取新闻来源"""
        return self.snapshot_data.get("source")

    @property
    def media_urls(self) -> list:
        """获取媒体URL列表"""
        return self.snapshot_data.get("media_urls", [])

    @property
    def published_at(self) -> Optional[str]:
        """获取发布时间"""
        return self.snapshot_data.get("published_at")
