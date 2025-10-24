"""数据源实体模型

数据源管理系统的核心实体，用于整编和管理搜索结果数据。

设计要点：
- 只有2个状态：DRAFT（草稿）⇄ CONFIRMED（已确定）
- 通过MongoDB事务同步更新原始数据状态
- 支持混合数据源（scheduled + instant search）
- 提供富文本编辑和版本追踪能力
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

# 导入雪花算法ID生成器
from src.infrastructure.id_generator import generate_string_id


class DataSourceStatus(Enum):
    """数据源状态枚举（仅2个状态）"""
    DRAFT = "draft"           # 草稿：可编辑、可添加删除数据
    CONFIRMED = "confirmed"   # 已确定：只读、数据已锁定


class DataSourceType(Enum):
    """数据源类型枚举"""
    SCHEDULED = "scheduled"         # 来自定时任务
    INSTANT = "instant"            # 来自即时搜索
    MIXED = "mixed"                # 混合数据源


@dataclass
class RawDataReference:
    """原始数据引用

    存储对SearchResult或InstantSearchResult的引用
    """
    # 数据ID
    data_id: str

    # 数据类型（scheduled或instant）
    data_type: str  # "scheduled" | "instant"

    # 数据快照（关键字段，用于展示）
    title: str = ""
    url: str = ""
    snippet: str = ""

    # 添加时间
    added_at: datetime = field(default_factory=datetime.utcnow)

    # 添加者
    added_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        # Handle added_at: could be datetime or string from MongoDB
        added_at_str = None
        if self.added_at:
            if isinstance(self.added_at, datetime):
                added_at_str = self.added_at.isoformat()
            elif isinstance(self.added_at, str):
                added_at_str = self.added_at

        return {
            "data_id": self.data_id,
            "data_type": self.data_type,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "added_at": added_at_str,
            "added_by": self.added_by
        }


@dataclass
class DataSource:
    """数据源实体

    核心功能：
    - 整编和管理搜索结果数据
    - 状态管理：草稿 ⇄ 已确定
    - 富文本编辑和版本追踪
    - 混合数据源支持
    """
    # 主键（雪花算法ID，全局唯一）
    id: str = field(default_factory=generate_string_id)

    # 基础信息
    title: str = ""                          # 数据源标题
    description: str = ""                    # 数据源描述
    source_type: DataSourceType = DataSourceType.MIXED  # 数据源类型

    # 状态管理（仅2个状态）
    status: DataSourceStatus = DataSourceStatus.DRAFT

    # 原始数据引用列表
    raw_data_refs: List[RawDataReference] = field(default_factory=list)

    # 编辑内容（富文本）
    edited_content: str = ""                 # 用户编辑的内容（Markdown格式）
    content_version: int = 1                 # 内容版本号

    # 统计信息
    total_raw_data_count: int = 0           # 原始数据总数
    scheduled_data_count: int = 0           # 定时任务数据数量
    instant_data_count: int = 0             # 即时搜索数据数量

    # 创建和确定信息
    created_by: str = ""                     # 创建者
    created_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_by: Optional[str] = None       # 确定者
    confirmed_at: Optional[datetime] = None  # 确定时间

    # 更新信息
    updated_by: str = ""                     # 最后更新者
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # 元数据
    tags: List[str] = field(default_factory=list)  # 标签
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据

    def __post_init__(self):
        """初始化后自动更新统计信息"""
        self._update_statistics()

    def _update_statistics(self) -> None:
        """更新统计信息"""
        self.total_raw_data_count = len(self.raw_data_refs)
        self.scheduled_data_count = sum(
            1 for ref in self.raw_data_refs if ref.data_type == "scheduled"
        )
        self.instant_data_count = sum(
            1 for ref in self.raw_data_refs if ref.data_type == "instant"
        )

        # 自动判断数据源类型
        if self.scheduled_data_count > 0 and self.instant_data_count > 0:
            self.source_type = DataSourceType.MIXED
        elif self.scheduled_data_count > 0:
            self.source_type = DataSourceType.SCHEDULED
        elif self.instant_data_count > 0:
            self.source_type = DataSourceType.INSTANT

    # ==========================================
    # 状态验证方法
    # ==========================================

    def can_edit(self) -> bool:
        """是否可以编辑"""
        return self.status == DataSourceStatus.DRAFT

    def can_confirm(self) -> bool:
        """是否可以确定"""
        return (
            self.status == DataSourceStatus.DRAFT and
            self.total_raw_data_count > 0  # 必须有数据才能确定
        )

    def can_revert_to_draft(self) -> bool:
        """是否可以恢复为草稿"""
        return self.status == DataSourceStatus.CONFIRMED

    # ==========================================
    # 状态转换方法
    # ==========================================

    def confirm(self, confirmed_by: str) -> None:
        """确定数据源

        状态转换：DRAFT → CONFIRMED
        触发：原始数据 processing → completed

        Args:
            confirmed_by: 确定者

        Raises:
            ValueError: 如果当前状态不允许确定
        """
        if not self.can_confirm():
            raise ValueError(
                f"Cannot confirm data source in status '{self.status.value}' "
                f"or with no raw data (count: {self.total_raw_data_count})"
            )

        self.status = DataSourceStatus.CONFIRMED
        self.confirmed_by = confirmed_by
        self.confirmed_at = datetime.utcnow()
        self.updated_by = confirmed_by
        self.updated_at = datetime.utcnow()

    def revert_to_draft(self, reverted_by: str) -> None:
        """恢复为草稿

        状态转换：CONFIRMED → DRAFT
        触发：原始数据 completed → processing

        Args:
            reverted_by: 操作者

        Raises:
            ValueError: 如果当前状态不允许恢复
        """
        if not self.can_revert_to_draft():
            raise ValueError(
                f"Cannot revert data source in status '{self.status.value}' to draft"
            )

        self.status = DataSourceStatus.DRAFT
        self.confirmed_by = None
        self.confirmed_at = None
        self.updated_by = reverted_by
        self.updated_at = datetime.utcnow()

    # ==========================================
    # 数据管理方法
    # ==========================================

    def add_raw_data(
        self,
        data_id: str,
        data_type: str,
        title: str,
        url: str,
        snippet: str,
        added_by: str
    ) -> None:
        """添加原始数据引用

        Args:
            data_id: 数据ID
            data_type: 数据类型（scheduled或instant）
            title: 标题
            url: URL
            snippet: 摘要
            added_by: 添加者

        Raises:
            ValueError: 如果数据源不可编辑或数据已存在
        """
        if not self.can_edit():
            raise ValueError(
                f"Cannot add raw data to data source in status '{self.status.value}'"
            )

        # 检查是否已存在
        if any(ref.data_id == data_id for ref in self.raw_data_refs):
            raise ValueError(f"Raw data '{data_id}' already exists in data source")

        # 添加引用
        ref = RawDataReference(
            data_id=data_id,
            data_type=data_type,
            title=title,
            url=url,
            snippet=snippet,
            added_at=datetime.utcnow(),
            added_by=added_by
        )
        self.raw_data_refs.append(ref)

        # 更新统计
        self._update_statistics()
        self.updated_by = added_by
        self.updated_at = datetime.utcnow()

    def remove_raw_data(self, data_id: str, removed_by: str) -> None:
        """移除原始数据引用

        Args:
            data_id: 数据ID
            removed_by: 移除者

        Raises:
            ValueError: 如果数据源不可编辑或数据不存在
        """
        if not self.can_edit():
            raise ValueError(
                f"Cannot remove raw data from data source in status '{self.status.value}'"
            )

        # 查找并移除
        original_count = len(self.raw_data_refs)
        self.raw_data_refs = [
            ref for ref in self.raw_data_refs if ref.data_id != data_id
        ]

        if len(self.raw_data_refs) == original_count:
            raise ValueError(f"Raw data '{data_id}' not found in data source")

        # 更新统计
        self._update_statistics()
        self.updated_by = removed_by
        self.updated_at = datetime.utcnow()

    def update_content(
        self,
        edited_content: str,
        updated_by: str
    ) -> None:
        """更新编辑内容

        Args:
            edited_content: 编辑内容（Markdown格式）
            updated_by: 更新者

        Raises:
            ValueError: 如果数据源不可编辑
        """
        if not self.can_edit():
            raise ValueError(
                f"Cannot update content of data source in status '{self.status.value}'"
            )

        self.edited_content = edited_content
        self.content_version += 1
        self.updated_by = updated_by
        self.updated_at = datetime.utcnow()

    def get_raw_data_ids_by_type(self, data_type: str) -> List[str]:
        """获取指定类型的原始数据ID列表

        Args:
            data_type: 数据类型（scheduled或instant）

        Returns:
            数据ID列表
        """
        return [
            ref.data_id
            for ref in self.raw_data_refs
            if ref.data_type == data_type
        ]

    # ==========================================
    # 序列化方法
    # ==========================================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "raw_data_refs": [ref.to_dict() for ref in self.raw_data_refs],
            "edited_content": self.edited_content,
            "content_version": self.content_version,
            "total_raw_data_count": self.total_raw_data_count,
            "scheduled_data_count": self.scheduled_data_count,
            "instant_data_count": self.instant_data_count,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": self.tags,
            "metadata": self.metadata
        }

    def to_summary(self) -> Dict[str, Any]:
        """返回摘要信息（轻量级响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "total_raw_data_count": self.total_raw_data_count,
            "scheduled_data_count": self.scheduled_data_count,
            "instant_data_count": self.instant_data_count,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "tags": self.tags
        }
