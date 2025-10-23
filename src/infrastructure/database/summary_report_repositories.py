"""智能总结报告仓储层"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.summary_report import (
    SummaryReport,
    SummaryReportVersion
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryReportRepository:
    """总结报告仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.summary_reports

    async def create(self, report: SummaryReport) -> SummaryReport:
        """创建总结报告"""
        result = await self.collection.insert_one(report.model_dump())
        logger.info(f"✅ 创建总结报告: {report.report_id} - {report.title}")
        return report

    async def find_by_id(self, report_id: str) -> Optional[SummaryReport]:
        """根据ID查询报告"""
        doc = await self.collection.find_one({"report_id": report_id})
        return SummaryReport(**doc) if doc else None

    async def find_all(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[SummaryReport]:
        """查询所有报告（支持过滤）"""
        query = {}
        if created_by:
            query["created_by"] = created_by
        if status:
            query["status"] = status
        if report_type:
            query["report_type"] = report_type

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [SummaryReport(**doc) for doc in docs]

    async def update(self, report_id: str, update_data: Dict[str, Any]) -> bool:
        """更新报告"""
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.update_one(
            {"report_id": report_id},
            {"$set": update_data}
        )
        if result.modified_count > 0:
            logger.info(f"📝 更新报告: {report_id}")
        return result.modified_count > 0

    async def update_content(
        self,
        report_id: str,
        content_text: str,
        content_format: str = "markdown",
        is_manual: bool = False
    ) -> bool:
        """更新报告内容"""
        content_obj = {
            "format": content_format,
            "text": content_text,
            "manual_edits": is_manual
        }

        # 如果是手动编辑，增加版本号
        update_fields = {
            "content": content_obj,
            "updated_at": datetime.utcnow()
        }

        # 获取当前报告以检查auto_version设置
        report = await self.find_by_id(report_id)
        if report and report.auto_version and is_manual:
            update_fields["$inc"] = {"version": 1}

        result = await self.collection.update_one(
            {"report_id": report_id},
            {"$set": update_fields}
        )
        return result.modified_count > 0

    async def update_status(self, report_id: str, status: str) -> bool:
        """更新报告状态"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }

        if status == "completed":
            update_data["last_generated_at"] = datetime.utcnow()

        result = await self.collection.update_one(
            {"report_id": report_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def increment_view_count(self, report_id: str) -> bool:
        """增加查看次数"""
        result = await self.collection.update_one(
            {"report_id": report_id},
            {"$inc": {"view_count": 1}}
        )
        return result.modified_count > 0

    async def delete(self, report_id: str) -> bool:
        """删除报告"""
        result = await self.collection.delete_one({"report_id": report_id})
        logger.info(f"🗑️  删除报告: {report_id}")
        return result.deleted_count > 0


class SummaryReportVersionRepository:
    """报告版本历史仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.summary_report_versions

    async def create(self, version: SummaryReportVersion) -> SummaryReportVersion:
        """创建版本记录"""
        await self.collection.insert_one(version.model_dump())
        logger.info(f"✅ 创建版本记录: {version.report_id} v{version.version_number}")
        return version

    async def find_by_report(
        self,
        report_id: str,
        limit: int = 20
    ) -> List[SummaryReportVersion]:
        """查询报告的版本历史"""
        cursor = self.collection.find({
            "report_id": report_id
        }).sort("version_number", -1).limit(limit)

        docs = await cursor.to_list(length=limit)
        return [SummaryReportVersion(**doc) for doc in docs]

    async def find_by_version_number(
        self,
        report_id: str,
        version_number: int
    ) -> Optional[SummaryReportVersion]:
        """根据版本号查询"""
        doc = await self.collection.find_one({
            "report_id": report_id,
            "version_number": version_number
        })
        return SummaryReportVersion(**doc) if doc else None

    async def get_latest_version(
        self,
        report_id: str
    ) -> Optional[SummaryReportVersion]:
        """获取最新版本"""
        doc = await self.collection.find_one(
            {"report_id": report_id},
            sort=[("version_number", -1)]
        )
        return SummaryReportVersion(**doc) if doc else None

    async def delete_by_report(self, report_id: str) -> int:
        """删除报告的所有版本记录"""
        result = await self.collection.delete_many({"report_id": report_id})
        return result.deleted_count

    async def count_by_report(self, report_id: str) -> int:
        """统计报告的版本数量"""
        return await self.collection.count_documents({"report_id": report_id})
