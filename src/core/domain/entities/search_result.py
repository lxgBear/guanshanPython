"""搜索结果实体模型"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4


class ResultStatus(Enum):
    """结果状态枚举（数据源管理版）"""
    PENDING = "pending"         # 初始状态：刚采集
    ARCHIVED = "archived"       # 已留存：用户标记重要
    PROCESSING = "processing"   # 处理中：数据源正在整编
    COMPLETED = "completed"     # 已完成：数据源已确定
    DELETED = "deleted"         # 已删除：软删除


@dataclass
class SearchResult:
    """搜索结果实体"""
    id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)  # 关联的任务ID
    
    # 搜索结果核心数据
    title: str = ""
    url: str = ""
    content: str = ""  # 提取的主要内容
    snippet: Optional[str] = None  # 搜索结果摘要
    
    # 元数据
    source: str = "web"  # 来源：web, news, academic 等
    published_date: Optional[datetime] = None  # 发布日期
    author: Optional[str] = None  # 作者
    language: Optional[str] = None  # 语言
    
    # Firecrawl 特定字段 - 优化版
    markdown_content: Optional[str] = None  # Markdown 格式内容(最大5000字符)
    html_content: Optional[str] = None  # HTML格式内容(用于富文本显示和分析)
    article_tag: Optional[str] = None  # 文章标签 (article:tag)
    article_published_time: Optional[str] = None  # 文章发布时间 (article:published_time)

    # 精简的元数据(只保留有用字段)
    source_url: Optional[str] = None  # 原始URL(重定向场景)
    http_status_code: Optional[int] = None  # HTTP状态码
    search_position: Optional[int] = None  # 搜索结果排名

    # 保留原metadata字段以支持扩展元数据(但应过滤冗余字段)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 精简的扩展元数据

    # 注: 已移除以下字段以优化存储:
    # - raw_data: 原始响应数据(~850KB) → 已删除,通过独立字段替代
    
    # 质量指标
    relevance_score: float = 0.0  # 相关性分数
    quality_score: float = 0.0    # 质量分数
    
    # 状态与时间
    status: ResultStatus = ResultStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # 测试模式标记
    is_test_data: bool = False  # 是否为测试数据
    
    def mark_as_archived(self) -> None:
        """标记为已留存"""
        self.status = ResultStatus.ARCHIVED
        self.processed_at = datetime.utcnow()

    def mark_as_processing(self) -> None:
        """标记为处理中（数据源整编中）"""
        self.status = ResultStatus.PROCESSING
        self.processed_at = datetime.utcnow()

    def mark_as_completed(self) -> None:
        """标记为已完成（数据源已确定）"""
        self.status = ResultStatus.COMPLETED
        self.processed_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """标记为已删除（软删除）"""
        self.status = ResultStatus.DELETED
        self.processed_at = datetime.utcnow()
    
    def to_summary(self) -> Dict[str, Any]:
        """返回摘要信息"""
        return {
            "id": str(self.id),
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet or self.content[:200],
            "source": self.source,
            "relevance_score": self.relevance_score,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "is_test_data": self.is_test_data
        }


@dataclass 
class SearchResultBatch:
    """搜索结果批次"""
    id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    execution_id: str = ""  # 执行ID（用于跟踪）
    
    # 结果数据
    results: List[SearchResult] = field(default_factory=list)
    total_count: int = 0  # 总结果数
    returned_count: int = 0  # 返回结果数
    
    # 执行信息
    query: str = ""  # 执行的查询
    search_config: Dict[str, Any] = field(default_factory=dict)
    
    # 性能指标
    execution_time_ms: int = 0  # 执行时间（毫秒）
    credits_used: int = 0  # 消耗积分
    
    # 状态
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # 测试模式
    is_test_mode: bool = False
    test_limit_applied: bool = False
    
    def add_result(self, result: SearchResult) -> None:
        """添加结果"""
        self.results.append(result)
        self.returned_count = len(self.results)
    
    def set_error(self, error_message: str) -> None:
        """设置错误"""
        self.success = False
        self.error_message = error_message