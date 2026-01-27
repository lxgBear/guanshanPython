"""信息条目实体模型

v1.0.0 初始版本：
- 支持从多个数据源（定时任务、智能搜索、文档上传）选择数据合并创建条目
- 统一字段名，兼容各数据源的内容格式
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from src.infrastructure.id_generator import generate_string_id


class EntryStatus(Enum):
    """条目状态枚举"""
    DRAFT = "draft"           # 草稿
    PUBLISHED = "published"   # 已发布
    ARCHIVED = "archived"     # 已归档


class DataSourceType(Enum):
    """数据来源类型枚举"""
    SCHEDULED = "scheduled"         # 定时任务 (search_results)
    SMART_SEARCH = "smart-search"   # 智能搜索 (instant_search_results)
    CHAT_SEARCH = "chat-search"     # Chat搜索 (langgraph_search_results)
    UPLOAD = "upload"               # 文档上传 (file_uploads)
    MANUAL = "manual"               # 手动录入 (search_results with source=translated)


@dataclass
class RawDataRef:
    """原始数据引用

    统一各数据源的字段名，存储原始数据的快照和翻译内容
    """
    # 标识信息
    ref_id: str = field(default_factory=generate_string_id)
    data_id: str = ""                          # 原始数据ID
    data_type: str = ""                        # 数据类型: scheduled/smart-search/chat-search/upload/manual
    source_collection: str = ""                # 来源集合名

    # 基础信息（统一字段名）
    title: str = ""
    url: str = ""
    origin_site: str = ""                      # 来源网站/来源标识
    published_date: Optional[datetime] = None

    # 原始内容
    markdown_content: str = ""                 # 原始 Markdown 内容
    html_content: str = ""                     # 原始 HTML 内容
    snippet: str = ""                          # 摘要

    # 翻译内容（统一字段名）
    translated_title: str = ""                 # 翻译后标题
    translated_content: str = ""               # 翻译后内容
    translated_at: Optional[datetime] = None   # 翻译时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "ref_id": self.ref_id,
            "data_id": self.data_id,
            "data_type": self.data_type,
            "source_collection": self.source_collection,
            "title": self.title,
            "url": self.url,
            "origin_site": self.origin_site,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "markdown_content": self.markdown_content,
            "html_content": self.html_content,
            "snippet": self.snippet,
            "translated_title": self.translated_title,
            "translated_content": self.translated_content,
            "translated_at": self.translated_at.isoformat() if self.translated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawDataRef":
        """从字典创建"""
        return cls(
            ref_id=data.get("ref_id", generate_string_id()),
            data_id=data.get("data_id", ""),
            data_type=data.get("data_type", ""),
            source_collection=data.get("source_collection", ""),
            title=data.get("title", ""),
            url=data.get("url", ""),
            origin_site=data.get("origin_site", ""),
            published_date=datetime.fromisoformat(data["published_date"]) if data.get("published_date") else None,
            markdown_content=data.get("markdown_content", ""),
            html_content=data.get("html_content", ""),
            snippet=data.get("snippet", ""),
            translated_title=data.get("translated_title", ""),
            translated_content=data.get("translated_content", ""),
            translated_at=datetime.fromisoformat(data["translated_at"]) if data.get("translated_at") else None,
        )


@dataclass
class InfoEntry:
    """信息条目实体

    用于存储从多个数据源合并创建的条目
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 基础信息
    title: str = ""
    description: str = ""
    summary: str = ""
    combined_content: str = ""        # 合并后的内容（TipTap JSON 格式）

    # 分类与标签
    tags: List[str] = field(default_factory=list)
    primary_category: str = ""        # 大类
    secondary_category: str = ""      # 类别
    tertiary_category: str = ""       # 地域

    # 状态
    status: EntryStatus = EntryStatus.DRAFT

    # 原始数据引用
    raw_data_refs: List[RawDataRef] = field(default_factory=list)
    raw_data_count: int = 0           # 引用的原始数据数量

    # 用户与时间
    user_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """初始化后处理"""
        self.raw_data_count = len(self.raw_data_refs)

    def add_raw_data_ref(self, ref: RawDataRef) -> None:
        """添加原始数据引用"""
        self.raw_data_refs.append(ref)
        self.raw_data_count = len(self.raw_data_refs)
        self.updated_at = datetime.utcnow()

    def update_combined_content(self, content: str) -> None:
        """更新合并内容"""
        self.combined_content = content
        self.updated_at = datetime.utcnow()

    def mark_as_published(self) -> None:
        """标记为已发布"""
        self.status = EntryStatus.PUBLISHED
        self.updated_at = datetime.utcnow()

    def mark_as_archived(self) -> None:
        """标记为已归档"""
        self.status = EntryStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "summary": self.summary,
            "combined_content": self.combined_content,
            "tags": self.tags,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "tertiary_category": self.tertiary_category,
            "status": self.status.value,
            "raw_data_refs": [ref.to_dict() for ref in self.raw_data_refs],
            "raw_data_count": self.raw_data_count,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def info_entry_to_mongo_doc(entry: InfoEntry) -> Dict[str, Any]:
    """将 InfoEntry 转换为 MongoDB 文档"""
    return {
        "_id": entry.id,
        "title": entry.title,
        "description": entry.description,
        "summary": entry.summary,
        "combined_content": entry.combined_content,
        "tags": entry.tags,
        "primary_category": entry.primary_category,
        "secondary_category": entry.secondary_category,
        "tertiary_category": entry.tertiary_category,
        "status": entry.status.value,
        "raw_data_refs": [ref.to_dict() for ref in entry.raw_data_refs],
        "raw_data_count": entry.raw_data_count,
        "user_id": entry.user_id,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def mongo_doc_to_info_entry(doc: Dict[str, Any]) -> InfoEntry:
    """将 MongoDB 文档转换为 InfoEntry"""
    raw_data_refs = [
        RawDataRef.from_dict(ref) for ref in doc.get("raw_data_refs", [])
    ]

    return InfoEntry(
        id=str(doc.get("_id", "")),
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        summary=doc.get("summary", ""),
        combined_content=doc.get("combined_content", ""),
        tags=doc.get("tags", []),
        primary_category=doc.get("primary_category", ""),
        secondary_category=doc.get("secondary_category", ""),
        tertiary_category=doc.get("tertiary_category", ""),
        status=EntryStatus(doc.get("status", "draft")),
        raw_data_refs=raw_data_refs,
        raw_data_count=doc.get("raw_data_count", len(raw_data_refs)),
        user_id=doc.get("user_id", ""),
        created_at=doc.get("created_at") or datetime.utcnow(),
        updated_at=doc.get("updated_at") or datetime.utcnow(),
    )
