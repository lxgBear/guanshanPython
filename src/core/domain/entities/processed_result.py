"""AI处理后的搜索结果实体模型

v2.0.0 职责分离架构：
- processed_results 表存储AI处理、翻译、总结后的增强数据
- 作为前端主查询数据源
- 支持用户操作（留存、删除、评分、备注）
- 与 search_results（原始数据表）职责分离

v2.0.1 字段扩展：
- 添加原始字段（title, url, content等）以支持前端直接查询
- 添加AI服务新增字段（content_zh, cls_results等）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from src.infrastructure.id_generator import generate_string_id


class ProcessedStatus(Enum):
    """处理结果状态枚举"""
    PENDING = "pending"         # 待AI处理
    PROCESSING = "processing"   # AI处理中
    COMPLETED = "completed"     # AI处理完成
    FAILED = "failed"           # AI处理失败
    ARCHIVED = "archived"       # 用户留存
    DELETED = "deleted"         # 用户删除（软删除）


@dataclass
class ProcessedResult:
    """AI处理结果实体（v2.0.1 扩展）

    职责：
    1. 存储原始搜索结果数据（避免JOIN查询）
    2. 存储AI分析、翻译、总结后的增强数据
    3. 管理用户操作状态（留存、删除）
    4. 记录AI处理元数据
    """
    # ==================== 主键和关联 ====================
    id: str = field(default_factory=generate_string_id)
    raw_result_id: str = ""  # 关联 search_results 的 ID
    task_id: str = ""        # 关联的搜索任务ID

    # ==================== 原始字段（v2.0.1 新增）====================
    # 核心内容
    title: str = ""                                    # 原始标题
    url: str = ""                                      # 原始URL
    source_url: str = ""                               # 来源URL
    content: str = ""                                  # 原始内容
    snippet: Optional[str] = None                      # 内容摘要

    # 格式化内容
    markdown_content: Optional[str] = None             # Markdown格式
    html_content: Optional[str] = None                 # HTML格式

    # 元数据
    author: Optional[str] = None                       # 作者
    published_date: Optional[datetime] = None          # 发布日期
    language: Optional[str] = None                     # 语言
    source: str = "web"                                # 来源类型
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据

    # 质量指标
    quality_score: float = 0.0                         # 质量分数
    relevance_score: float = 0.0                       # 相关性分数
    search_position: int = 0                           # 搜索位置

    # ==================== AI处理字段 ====================
    # AI翻译和生成
    content_zh: Optional[str] = None                   # AI翻译的中文内容
    title_generated: Optional[str] = None              # AI生成的标题
    translated_title: Optional[str] = None             # 翻译后的标题（保留兼容）
    translated_content: Optional[str] = None           # 翻译后的内容（保留兼容）
    summary: Optional[str] = None                      # AI生成的摘要
    key_points: List[str] = field(default_factory=list)  # 关键要点

    # AI分类和分析
    cls_results: Optional[Dict[str, Any]] = None       # 分类结果（大类、子目录）
    sentiment: Optional[str] = None                    # 情感分析
    categories: List[str] = field(default_factory=list)  # 分类标签（保留兼容）

    # AI处理的HTML
    html_ctx_llm: Optional[str] = None                 # LLM处理后的HTML
    html_ctx_regex: Optional[str] = None               # Regex处理后的HTML

    # AI提取的元数据
    article_published_time: Optional[str] = None       # 文章发布时间
    article_tag: Optional[str] = None                  # 文章标签

    # ==================== AI处理元数据 ====================
    ai_model: Optional[str] = None                     # 使用的AI模型
    ai_processing_time_ms: int = 0                     # AI处理耗时（毫秒）
    ai_confidence_score: float = 0.0                   # AI置信度分数
    ai_metadata: Dict[str, Any] = field(default_factory=dict)  # AI额外元数据

    # 处理状态
    processing_status: str = "pending"                 # 处理状态（success/failed/pending）
    http_status_code: Optional[int] = None             # HTTP状态码
    is_test_data: bool = False                         # 是否测试数据

    # ==================== 用户操作状态 ====================
    status: ProcessedStatus = ProcessedStatus.PENDING  # 用户操作状态
    user_rating: Optional[int] = None                  # 用户评分（1-5）
    user_notes: Optional[str] = None                   # 用户备注

    # ==================== 时间戳 ====================
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ==================== 错误处理 ====================
    processing_error: Optional[str] = None
    retry_count: int = 0

    def mark_as_processing(self) -> None:
        """标记为AI处理中"""
        self.status = ProcessedStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_as_completed(self, ai_model: str, processing_time_ms: int) -> None:
        """标记为AI处理完成"""
        self.status = ProcessedStatus.COMPLETED
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.ai_model = ai_model
        self.ai_processing_time_ms = processing_time_ms

    def mark_as_failed(self, error_message: str) -> None:
        """标记为AI处理失败"""
        self.status = ProcessedStatus.FAILED
        self.processing_error = error_message
        self.retry_count += 1
        self.updated_at = datetime.utcnow()

    def mark_as_archived(self) -> None:
        """用户标记为留存"""
        self.status = ProcessedStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """用户标记为删除（软删除）"""
        self.status = ProcessedStatus.DELETED
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
            self.status == ProcessedStatus.FAILED and
            self.retry_count < max_retries
        )

    def is_ready_for_display(self) -> bool:
        """检查是否可以展示给前端"""
        return self.status in [
            ProcessedStatus.COMPLETED,
            ProcessedStatus.ARCHIVED
        ]
