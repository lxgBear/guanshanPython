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

    # 统计信息 (V2.0更新)
    source_count: int = Field(default=0, description="关联的数据源数量")
    data_quality_score: float = Field(default=0.0, description="数据质量评分 (0.0-1.0)")
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
