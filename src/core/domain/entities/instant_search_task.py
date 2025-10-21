"""即时搜索任务实体模型

v1.3.0 架构说明：
- 即时搜索任务为一次性执行，不涉及调度
- 使用雪花算法ID确保高并发场景下的ID唯一性
- 每次搜索执行生成唯一的search_execution_id用于结果映射
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4

# 导入雪花算法ID生成器（复用定时搜索的ID生成器）
from src.infrastructure.id_generator import generate_string_id


class InstantSearchStatus(Enum):
    """即时搜索状态枚举"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class InstantSearchTask:
    """
    即时搜索任务实体

    设计特点：
    - 一次性执行，不涉及调度间隔
    - 支持关键词搜索和URL爬取两种模式
    - 每次执行生成唯一的search_execution_id
    - 使用雪花算法ID保证分布式环境下的唯一性

    v1.3.0 新增：
    - search_execution_id: 搜索执行ID，关联结果映射表
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 基本信息
    name: str = ""  # 任务名称
    description: Optional[str] = None  # 任务描述

    # 搜索参数（双模式）
    query: Optional[str] = None  # 搜索关键词（Search API模式）
    crawl_url: Optional[str] = None  # 爬取URL（Scrape API模式，优先级高于query）
    target_website: Optional[str] = None  # 目标网站（用于前端展示，例如：www.gnlm.com.mm）

    # 搜索配置
    search_config: Dict[str, Any] = field(default_factory=dict)  # Firecrawl搜索配置（JSON）

    # 执行信息（v1.3.0核心）
    search_execution_id: str = field(default_factory=lambda: f"exec_{generate_string_id()}")  # 搜索执行ID

    # 状态
    status: InstantSearchStatus = InstantSearchStatus.PENDING

    # 元数据
    created_by: str = "system"  # 创建者
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None  # 开始执行时间
    completed_at: Optional[datetime] = None  # 完成时间

    # 执行结果统计
    total_results: int = 0  # 总结果数
    new_results: int = 0  # 新结果数（首次发现）
    shared_results: int = 0  # 共享结果数（其他搜索已发现）
    credits_used: int = 0  # 消耗积分
    execution_time_ms: int = 0  # 执行时间（毫秒）

    # 错误信息
    error_message: Optional[str] = None

    def start_execution(self) -> None:
        """开始执行"""
        self.status = InstantSearchStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_completed(
        self,
        total: int,
        new: int,
        shared: int,
        credits: int,
        execution_time: int
    ) -> None:
        """标记为完成"""
        self.status = InstantSearchStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.total_results = total
        self.new_results = new
        self.shared_results = shared
        self.credits_used = credits
        self.execution_time_ms = execution_time

    def mark_as_failed(self, error_message: str) -> None:
        """标记为失败"""
        self.status = InstantSearchStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error_message = error_message

    def get_search_mode(self) -> str:
        """获取搜索模式"""
        if self.crawl_url:
            return "crawl"  # URL爬取模式
        elif self.query:
            return "search"  # 关键词搜索模式
        else:
            return "unknown"

    def extract_target_website(self) -> Optional[str]:
        """
        从 search_config 或 crawl_url 中提取目标网站

        Returns:
            目标网站域名
        """
        # 优先从crawl_url提取
        if self.crawl_url:
            from urllib.parse import urlparse
            parsed = urlparse(self.crawl_url)
            return parsed.netloc

        # 其次从search_config的include_domains提取
        include_domains = self.search_config.get('include_domains', [])
        if include_domains and len(include_domains) > 0:
            return include_domains[0]

        return None

    def sync_target_website(self) -> None:
        """
        同步 target_website 字段
        - 如果为空，自动提取
        - 如果不为空，保持用户自定义值
        """
        if not self.target_website:
            self.target_website = self.extract_target_website()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "query": self.query,
            "crawl_url": self.crawl_url,
            "target_website": self.target_website,
            "search_config": self.search_config,
            "search_execution_id": self.search_execution_id,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_results": self.total_results,
            "new_results": self.new_results,
            "shared_results": self.shared_results,
            "credits_used": self.credits_used,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "search_mode": self.get_search_mode()
        }
