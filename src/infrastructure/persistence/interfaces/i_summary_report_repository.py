"""总结报告仓储接口

Version: v3.0.0 (模块化架构)

总结报告仓储提供智能总结报告的持久化操作，包括：
- 基础CRUD操作
- 状态过滤查询（created_by, status, report_type）
- 内容更新（支持手动编辑和自动版本管理）
- 查看次数统计
- 版本历史管理
"""

from abc import abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.domain.entities.summary_report import SummaryReport, SummaryReportVersion
from .i_repository import IBasicRepository


class ISummaryReportRepository(IBasicRepository[SummaryReport]):
    """总结报告仓储接口

    职责：
    - 报告的CRUD操作
    - 多维度过滤查询（创建者、状态、类型）
    - 内容更新（支持手动编辑、自动版本）
    - 状态管理（draft → in_progress → completed）
    - 查看次数统计
    """

    @abstractmethod
    async def create(self, entity: SummaryReport) -> SummaryReport:
        """创建总结报告

        Args:
            entity: 报告实体

        Returns:
            创建的报告实体
        """
        pass

    @abstractmethod
    async def find_by_id(self, report_id: str) -> Optional[SummaryReport]:
        """根据ID查询报告

        Args:
            report_id: 报告ID

        Returns:
            报告实体或None
        """
        pass

    @abstractmethod
    async def find_all(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[SummaryReport]:
        """查询所有报告（支持过滤和分页）

        Args:
            created_by: 创建者过滤
            status: 状态过滤（draft, in_progress, completed）
            report_type: 报告类型过滤
            limit: 每页数量
            skip: 跳过数量

        Returns:
            报告实体列表

        排序：
        - 按创建时间倒序
        """
        pass

    @abstractmethod
    async def update(self, report_id: str, update_data: Dict[str, Any]) -> bool:
        """更新报告

        Args:
            report_id: 报告ID
            update_data: 更新数据字典

        Returns:
            是否更新成功

        注意：
        - 自动更新 updated_at 字段
        """
        pass

    @abstractmethod
    async def update_content(
        self,
        report_id: str,
        content_text: str,
        content_format: str = "markdown",
        is_manual: bool = False
    ) -> bool:
        """更新报告内容

        Args:
            report_id: 报告ID
            content_text: 内容文本
            content_format: 内容格式（markdown, html等）
            is_manual: 是否手动编辑

        Returns:
            是否更新成功

        业务逻辑：
        - 如果是手动编辑且启用auto_version，自动增加版本号
        - 更新content对象的format、text、manual_edits字段
        """
        pass

    @abstractmethod
    async def update_status(self, report_id: str, status: str) -> bool:
        """更新报告状态

        Args:
            report_id: 报告ID
            status: 新状态

        Returns:
            是否更新成功

        业务逻辑：
        - 如果状态为completed，更新last_generated_at字段
        """
        pass

    @abstractmethod
    async def increment_view_count(self, report_id: str) -> bool:
        """增加查看次数

        Args:
            report_id: 报告ID

        Returns:
            是否更新成功

        业务逻辑：
        - 使用$inc原子操作增加view_count
        """
        pass

    @abstractmethod
    async def delete(self, report_id: str) -> bool:
        """删除报告

        Args:
            report_id: 报告ID

        Returns:
            是否删除成功
        """
        pass


class ISummaryReportVersionRepository(IBasicRepository[SummaryReportVersion]):
    """报告版本历史仓储接口

    职责：
    - 版本记录的创建和查询
    - 按报告ID查询版本历史
    - 按版本号查询特定版本
    - 获取最新版本
    - 版本统计
    """

    @abstractmethod
    async def create(self, entity: SummaryReportVersion) -> SummaryReportVersion:
        """创建版本记录

        Args:
            entity: 版本实体

        Returns:
            创建的版本实体
        """
        pass

    @abstractmethod
    async def find_by_report(
        self,
        report_id: str,
        limit: int = 20
    ) -> List[SummaryReportVersion]:
        """查询报告的版本历史

        Args:
            report_id: 报告ID
            limit: 返回数量限制

        Returns:
            版本实体列表

        排序：
        - 按版本号倒序
        """
        pass

    @abstractmethod
    async def find_by_version_number(
        self,
        report_id: str,
        version_number: int
    ) -> Optional[SummaryReportVersion]:
        """根据版本号查询

        Args:
            report_id: 报告ID
            version_number: 版本号

        Returns:
            版本实体或None
        """
        pass

    @abstractmethod
    async def get_latest_version(
        self,
        report_id: str
    ) -> Optional[SummaryReportVersion]:
        """获取最新版本

        Args:
            report_id: 报告ID

        Returns:
            最新版本实体或None

        业务逻辑：
        - 按version_number倒序排列，取第一条
        """
        pass

    @abstractmethod
    async def delete_by_report(self, report_id: str) -> int:
        """删除报告的所有版本记录

        Args:
            report_id: 报告ID

        Returns:
            删除的记录数量

        业务逻辑：
        - 级联删除，通常在删除报告时调用
        """
        pass

    @abstractmethod
    async def count_by_report(self, report_id: str) -> int:
        """统计报告的版本数量

        Args:
            report_id: 报告ID

        Returns:
            版本数量
        """
        pass
