"""
文档实体定义
核心领域模型 - 不依赖任何外部框架
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum


class DocumentStatus(str, Enum):
    """文档状态枚举"""
    PENDING = "pending"         # 待处理
    PROCESSING = "processing"   # 处理中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"          # 失败
    ARCHIVED = "archived"      # 已归档


class DocumentType(str, Enum):
    """文档类型枚举"""
    WEB_PAGE = "web_page"      # 网页
    PDF = "pdf"                # PDF文档
    MARKDOWN = "markdown"      # Markdown文档
    PLAIN_TEXT = "plain_text"  # 纯文本
    JSON = "json"              # JSON数据


@dataclass
class DocumentMetadata:
    """文档元数据值对象"""
    title: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    language: str = "zh"  # 默认中文
    source_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """文档实体 - 核心业务实体"""
    
    # 身份标识
    id: UUID = field(default_factory=uuid4)
    
    # 基本属性
    url: str = ""
    content: str = ""
    markdown_content: Optional[str] = None
    html_content: Optional[str] = None
    
    # 分类信息
    type: DocumentType = DocumentType.WEB_PAGE
    status: DocumentStatus = DocumentStatus.PENDING
    
    # 元数据
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    
    # 向量嵌入（用于RAG）
    embeddings: Optional[List[float]] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 版本控制
    version: int = 1
    
    def __post_init__(self):
        """初始化后验证"""
        if not self.url and not self.content:
            raise ValueError("文档必须有URL或内容")
    
    def mark_as_processing(self) -> None:
        """标记为处理中"""
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.utcnow()
    
    def mark_as_completed(self) -> None:
        """标记为已完成"""
        self.status = DocumentStatus.COMPLETED
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_as_failed(self, error_message: str) -> None:
        """标记为失败"""
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
    
    def update_content(self, content: str, markdown: Optional[str] = None) -> None:
        """更新内容"""
        self.content = content
        if markdown:
            self.markdown_content = markdown
        self.updated_at = datetime.utcnow()
        self.version += 1
    
    def is_processable(self) -> bool:
        """检查是否可处理"""
        return self.status in [DocumentStatus.PENDING, DocumentStatus.FAILED]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": str(self.id),
            "url": self.url,
            "content": self.content,
            "markdown_content": self.markdown_content,
            "html_content": self.html_content,
            "type": self.type.value,
            "status": self.status.value,
            "metadata": {
                "title": self.metadata.title,
                "author": self.metadata.author,
                "published_at": self.metadata.published_at.isoformat() if self.metadata.published_at else None,
                "tags": self.metadata.tags,
                "language": self.metadata.language,
                "source_url": self.metadata.source_url,
                "extra": self.metadata.extra
            },
            "embeddings": self.embeddings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error_message": self.error_message,
            "version": self.version
        }