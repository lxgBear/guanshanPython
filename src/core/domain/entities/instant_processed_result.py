"""即时搜索AI处理结果实体模型

v2.1.0 即时+智能搜索统一架构：
- instant_processed_results 表存储AI处理、翻译、总结后的增强数据
- 支持 search_type 字段区分即时搜索和智能搜索
- 作为前端主查询数据源
- 支持用户操作（留存、删除、评分、备注）
- 与 instant_search_results（原始数据表）职责分离
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from src.infrastructure.id_generator import generate_string_id


class InstantProcessedStatus(Enum):
    """即时搜索处理结果状态枚举"""
    PENDING = "pending"         # 待AI处理
    PROCESSING = "processing"   # AI处理中
    COMPLETED = "completed"     # AI处理完成
    FAILED = "failed"           # AI处理失败
    ARCHIVED = "archived"       # 用户留存
    DELETED = "deleted"         # 用户删除（软删除）


@dataclass
class InstantProcessedResult:
    """即时搜索AI处理结果实体（v2.1.0 新增）

    职责：
    1. 存储AI分析、翻译、总结后的数据
    2. 管理用户操作状态（留存、删除）
    3. 记录AI处理元数据
    4. 支持即时搜索和智能搜索统一查询
    """
    # 主键
    id: str = field(default_factory=generate_string_id)

    # 关联原始结果
    raw_result_id: str = ""  # 关联 instant_search_results 的 ID
    task_id: str = ""        # 关联的搜索任务ID

    # v2.1.0 统一架构字段
    search_type: str = "instant"  # 搜索类型：instant（即时） | smart（智能）

    # AI处理后的数据
    translated_title: Optional[str] = None  # 翻译后的标题
    translated_content: Optional[str] = None  # 翻译后的内容
    summary: Optional[str] = None  # AI生成的摘要
    key_points: List[str] = field(default_factory=list)  # 关键要点
    sentiment: Optional[str] = None  # 情感分析（positive/neutral/negative）
    categories: List[str] = field(default_factory=list)  # AI分类标签

    # AI处理元数据
    ai_model: Optional[str] = None  # 使用的AI模型（如：gpt-4）
    ai_processing_time_ms: int = 0  # AI处理耗时（毫秒）
    ai_confidence_score: float = 0.0  # AI置信度分数（0-1）
    ai_metadata: Dict[str, Any] = field(default_factory=dict)  # AI额外元数据

    # 用户操作状态
    status: InstantProcessedStatus = InstantProcessedStatus.PENDING
    user_rating: Optional[int] = None  # 用户评分（1-5）
    user_notes: Optional[str] = None  # 用户备注

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)  # 创建时间（原始结果时间）
    processed_at: Optional[datetime] = None  # AI处理完成时间
    updated_at: datetime = field(default_factory=datetime.utcnow)  # 最后更新时间

    # 错误处理
    processing_error: Optional[str] = None  # AI处理错误信息
    retry_count: int = 0  # 重试次数

    def mark_as_processing(self) -> None:
        """标记为AI处理中"""
        self.status = InstantProcessedStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_as_completed(self, ai_model: str, processing_time_ms: int) -> None:
        """标记为AI处理完成"""
        self.status = InstantProcessedStatus.COMPLETED
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.ai_model = ai_model
        self.ai_processing_time_ms = processing_time_ms

    def mark_as_failed(self, error_message: str) -> None:
        """标记为AI处理失败"""
        self.status = InstantProcessedStatus.FAILED
        self.processing_error = error_message
        self.retry_count += 1
        self.updated_at = datetime.utcnow()

    def mark_as_archived(self) -> None:
        """用户标记为留存"""
        self.status = InstantProcessedStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """用户标记为删除（软删除）"""
        self.status = InstantProcessedStatus.DELETED
        self.updated_at = datetime.utcnow()

    def update_user_rating(self, rating: int) -> None:
        """更新用户评分（1-5星）"""
        if not 1 <= rating <= 5:
            raise ValueError("评分必须在1-5之间")
        self.user_rating = rating
        self.updated_at = datetime.utcnow()

    def update_user_notes(self, notes: str) -> None:
        """更新用户备注"""
        self.user_notes = notes
        self.updated_at = datetime.utcnow()

    def can_retry(self, max_retries: int = 3) -> bool:
        """检查是否可以重试AI处理"""
        return (
            self.status == InstantProcessedStatus.FAILED and
            self.retry_count < max_retries
        )

    def is_ready_for_display(self) -> bool:
        """检查是否可以展示给前端"""
        return self.status in [
            InstantProcessedStatus.COMPLETED,
            InstantProcessedStatus.ARCHIVED
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "raw_result_id": self.raw_result_id,
            "task_id": self.task_id,
            "search_type": self.search_type,
            # AI处理数据
            "translated_title": self.translated_title,
            "translated_content": self.translated_content,
            "summary": self.summary,
            "key_points": self.key_points,
            "sentiment": self.sentiment,
            "categories": self.categories,
            # AI元数据
            "ai_model": self.ai_model,
            "ai_processing_time_ms": self.ai_processing_time_ms,
            "ai_confidence_score": self.ai_confidence_score,
            "ai_metadata": self.ai_metadata,
            # 用户操作
            "status": self.status.value,
            "user_rating": self.user_rating,
            "user_notes": self.user_notes,
            # 时间戳
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # 错误处理
            "processing_error": self.processing_error,
            "retry_count": self.retry_count
        }
