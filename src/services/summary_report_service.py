"""智能总结报告业务逻辑服务"""
from typing import List, Optional, Dict, Any

from src.core.domain.entities.summary_report import (
    SummaryReport,
    SummaryReportVersion
)
from src.infrastructure.database.summary_report_repositories import (
    SummaryReportRepository,
    SummaryReportVersionRepository
)
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Redis缓存是可选的
try:
    from src.infrastructure.cache import redis_client, cache_key_gen
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_client = None
    cache_key_gen = None
    logger.warning("Redis模块未安装，缓存功能将被禁用")


class SummaryReportService:
    """智能总结报告管理服务"""

    def __init__(self):
        self.db = None
        self.report_repo = None
        self.version_repo = None

    async def _init_repos(self):
        """初始化仓储"""
        if not self.db:
            self.db = await get_mongodb_database()
            self.report_repo = SummaryReportRepository(self.db)
            self.version_repo = SummaryReportVersionRepository(self.db)

    # ==========================================
    # 报告管理
    # ==========================================

    async def create_report(
        self,
        title: str,
        description: Optional[str],
        report_type: str,
        created_by: str,
        **kwargs
    ) -> SummaryReport:
        """创建总结报告"""
        await self._init_repos()

        report = SummaryReport(
            title=title,
            description=description,
            report_type=report_type,
            created_by=created_by,
            **kwargs
        )

        return await self.report_repo.create(report)

    async def get_report(self, report_id: str) -> Optional[SummaryReport]:
        """获取报告详情"""
        await self._init_repos()
        report = await self.report_repo.find_by_id(report_id)

        if report:
            # 增加查看次数
            await self.report_repo.increment_view_count(report_id)

        return report

    async def list_reports(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[SummaryReport]:
        """列出报告"""
        await self._init_repos()
        return await self.report_repo.find_all(
            created_by=created_by,
            status=status,
            report_type=report_type,
            limit=limit,
            skip=skip
        )

    async def update_report(
        self,
        report_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """更新报告"""
        await self._init_repos()
        return await self.report_repo.update(report_id, update_data)

    async def delete_report(self, report_id: str) -> bool:
        """删除报告（级联删除关联数据）"""
        await self._init_repos()

        # 删除版本历史
        await self.version_repo.delete_by_report(report_id)

        # 删除报告
        return await self.report_repo.delete(report_id)

    # ==========================================
    # 内容编辑和版本管理
    # ==========================================

    async def update_report_content(
        self,
        report_id: str,
        content_text: str,
        content_format: str = "markdown",
        is_manual: bool = False,
        updated_by: str = "",
        change_description: Optional[str] = None
    ) -> bool:
        """更新报告内容（支持富文本编辑）"""
        await self._init_repos()

        # 获取当前报告
        report = await self.report_repo.find_by_id(report_id)
        if not report:
            return False

        # 如果启用自动版本管理，创建版本快照
        if report.auto_version and is_manual:
            version = SummaryReportVersion(
                report_id=report_id,
                version_number=report.version + 1,
                content_snapshot=report.content.copy(),
                change_description=change_description or "Manual content update",
                change_type="manual" if is_manual else "auto_generated",
                created_by=updated_by,
                content_size=len(content_text)
            )
            await self.version_repo.create(version)

        # 更新内容
        return await self.report_repo.update_content(
            report_id,
            content_text,
            content_format,
            is_manual
        )

    async def get_report_versions(
        self,
        report_id: str,
        limit: int = 20
    ) -> List[SummaryReportVersion]:
        """获取报告版本历史"""
        await self._init_repos()
        return await self.version_repo.find_by_report(report_id, limit)

    async def rollback_to_version(
        self,
        report_id: str,
        version_number: int,
        updated_by: str
    ) -> bool:
        """回滚到指定版本"""
        await self._init_repos()

        # 获取目标版本
        version = await self.version_repo.find_by_version_number(report_id, version_number)
        if not version:
            return False

        # 恢复内容
        content_snapshot = version.content_snapshot
        content_text = content_snapshot.get("text", "")
        content_format = content_snapshot.get("format", "markdown")

        return await self.update_report_content(
            report_id,
            content_text,
            content_format,
            is_manual=True,
            updated_by=updated_by,
            change_description=f"Rollback to version {version_number}"
        )

    # ==========================================
    # LLM/AI 生成功能（预留接口）
    # ==========================================

    async def generate_report_with_llm(
        self,
        report_id: str,
        generation_mode: str = "comprehensive",
        llm_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用LLM生成报告内容（预留接口）

        待实现：将从数据源表获取数据，调用独立LLM服务生成报告

        Args:
            report_id: 报告ID
            generation_mode: 生成模式
            llm_config: LLM配置参数

        Returns:
            生成结果
        """
        # TODO: V2.0 - 从 report_data_sources 获取数据，调用独立LLM服务
        logger.warning("⚠️  LLM生成功能待V2.0实现")
        return {
            "success": False,
            "error": "LLM module not yet implemented in V2.0",
            "message": "此功能将在V2.0中重新实现，使用数据源表和独立LLM服务"
        }

    async def analyze_report_data_with_ai(
        self,
        report_id: str,
        analysis_type: str = "trend"
    ) -> Dict[str, Any]:
        """
        使用AI分析报告数据（预留接口）

        待实现：将从数据源表获取数据，调用独立AI服务进行分析

        Args:
            report_id: 报告ID
            analysis_type: 分析类型

        Returns:
            分析结果
        """
        # TODO: V2.0 - 从 report_data_sources 获取数据，调用独立AI服务
        logger.warning("⚠️  AI分析功能待V2.0实现")
        return {
            "success": False,
            "error": "AI analysis module not yet implemented in V2.0",
            "message": "此功能将在V2.0中重新实现，使用数据源表和独立AI服务"
        }

# 全局服务实例
summary_report_service = SummaryReportService()
