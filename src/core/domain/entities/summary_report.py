"""智能总结报告实体模型

用于整合定时任务和即时搜索任务，调用LLM/AI生成报告和总结
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

# 导入安全ID生成器
from src.infrastructure.id_generator import generate_string_id


class ReportType(Enum):
    """报告类型枚举"""
    COMPREHENSIVE = "comprehensive"  # 综合报告
    SUMMARY = "summary"              # 摘要报告
    ANALYSIS = "analysis"            # 分析报告
    CUSTOM = "custom"                # 自定义报告


class ReportStatus(Enum):
    """报告状态枚举"""
    DRAFT = "draft"                  # 草稿
    GENERATING = "generating"        # 生成中
    COMPLETED = "completed"          # 已完成
    FAILED = "failed"                # 生成失败
    ARCHIVED = "archived"            # 已归档


class TaskType(Enum):
    """任务类型枚举"""
    SCHEDULED = "scheduled"          # 定时任务 (SearchTask)
    INSTANT = "instant"              # 即时任务 (InstantSearchTask)


def _generate_secure_id() -> str:
    """生成安全的雪花算法ID"""
    return generate_string_id()


class SummaryReport(BaseModel):
    """
    总结报告主实体

    用于存储用户创建的总结数据库，包含多个搜索任务和定时任务
    """
    report_id: str = Field(default_factory=_generate_secure_id, description="报告唯一标识")
    title: str = Field(default="", description="报告标题")
    description: Optional[str] = Field(default=None, description="报告描述")
    report_type: str = Field(default="comprehensive", description="报告类型: comprehensive/summary/analysis/custom")
    status: str = Field(default="draft", description="报告状态: draft/generating/completed/failed/archived")

    # 报告内容（富文本 - Markdown或HTML格式）
    content: Dict[str, Any] = Field(
        default_factory=lambda: {
            "format": "markdown",     # markdown 或 html
            "text": "",               # 文本内容
            "manual_edits": False     # 是否经过手动编辑
        },
        description="报告内容（富文本）"
    )

    # LLM/AI 生成配置（预留字段）
    generation_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "llm_model": None,        # 使用的LLM模型
            "ai_analysis_type": None, # AI分析类型
            "generation_params": {}   # 生成参数
        },
        description="LLM/AI生成配置（预留接口）"
    )

    # 版本管理
    version: int = Field(default=1, description="当前版本号")
    auto_version: bool = Field(default=True, description="是否自动版本管理")

    # 元数据
    created_by: str = Field(default="", description="创建者")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")
    last_generated_at: Optional[datetime] = Field(default=None, description="最后生成时间")

    # 统计信息
    task_count: int = Field(default=0, description="关联任务数量")
    data_item_count: int = Field(default=0, description="数据项数量")
    view_count: int = Field(default=0, description="查看次数")

    def update_content(self, content_text: str, content_format: str = "markdown", is_manual: bool = False) -> None:
        """
        更新报告内容

        Args:
            content_text: 内容文本
            content_format: 内容格式 (markdown 或 html)
            is_manual: 是否手动编辑
        """
        self.content = {
            "format": content_format,
            "text": content_text,
            "manual_edits": is_manual
        }
        self.updated_at = datetime.utcnow()

        # 自动版本管理
        if self.auto_version and is_manual:
            self.version += 1

    def update_status(self, new_status: str) -> None:
        """更新报告状态"""
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if new_status == "completed":
            self.last_generated_at = datetime.utcnow()

    def increment_view_count(self) -> None:
        """增加查看次数"""
        self.view_count += 1


class SummaryReportTask(BaseModel):
    """
    报告-任务关联实体

    用于存储报告与搜索任务/定时任务的多对多关系
    """
    association_id: str = Field(default_factory=_generate_secure_id, description="关联唯一标识")
    report_id: str = Field(default="", description="报告ID")
    task_id: str = Field(default="", description="任务ID")
    task_type: str = Field(default="scheduled", description="任务类型: scheduled/instant")
    task_name: str = Field(default="", description="任务名称（冗余字段，便于展示）")

    # 配置信息
    is_active: bool = Field(default=True, description="是否启用（用于暂时排除某些任务）")
    priority: int = Field(default=0, description="优先级（用于排序）")

    # 元数据
    added_at: datetime = Field(default_factory=datetime.utcnow, description="添加时间")
    added_by: str = Field(default="", description="添加者")


class SummaryReportDataItem(BaseModel):
    """
    报告数据项实体

    用户手动选择加入总结的数据项
    """
    item_id: str = Field(default_factory=_generate_secure_id, description="数据项唯一标识")
    report_id: str = Field(default="", description="所属报告ID")

    # 数据来源
    source_type: str = Field(default="", description="来源类型: search_result/instant_search_result/custom")
    source_id: Optional[str] = Field(default=None, description="来源ID（如果来自搜索结果）")
    task_id: Optional[str] = Field(default=None, description="关联任务ID")
    task_type: Optional[str] = Field(default=None, description="任务类型: scheduled/instant")

    # 数据内容
    title: str = Field(default="", description="标题")
    content: str = Field(default="", description="内容")
    url: Optional[str] = Field(default=None, description="链接")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元数据")

    # 用户标注
    tags: List[str] = Field(default_factory=list, description="标签")
    notes: Optional[str] = Field(default=None, description="用户备注")
    importance: int = Field(default=0, description="重要性 (0-5)")

    # 排序和展示
    display_order: int = Field(default=0, description="显示顺序")
    is_visible: bool = Field(default=True, description="是否可见")

    # 元数据
    added_at: datetime = Field(default_factory=datetime.utcnow, description="添加时间")
    added_by: str = Field(default="", description="添加者")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    def update_notes(self, notes: str) -> None:
        """更新用户备注"""
        self.notes = notes
        self.updated_at = datetime.utcnow()

    def set_importance(self, importance: int) -> None:
        """设置重要性（0-5）"""
        if 0 <= importance <= 5:
            self.importance = importance
            self.updated_at = datetime.utcnow()
        else:
            raise ValueError("importance must be between 0 and 5")


class SummaryReportVersion(BaseModel):
    """
    报告版本历史实体

    用于版本管理和回滚功能
    """
    version_id: str = Field(default_factory=_generate_secure_id, description="版本唯一标识")
    report_id: str = Field(default="", description="所属报告ID")
    version_number: int = Field(default=1, description="版本号")

    # 版本内容快照
    content_snapshot: Dict[str, Any] = Field(default_factory=dict, description="内容快照")

    # 变更信息
    change_description: Optional[str] = Field(default=None, description="变更描述")
    change_type: str = Field(default="manual", description="变更类型: manual/auto_generated/ai_generated")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    created_by: str = Field(default="", description="创建者")

    # 统计信息
    content_size: int = Field(default=0, description="内容大小（字符数）")
