"""SummaryReport MongoDB Repository 实现

Version: v3.0.0 (模块化架构)

提供总结报告和版本历史的MongoDB持久化实现。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.summary_report import SummaryReport, SummaryReportVersion
from src.infrastructure.persistence.interfaces import (
    ISummaryReportRepository,
    ISummaryReportVersionRepository
)
from src.infrastructure.persistence.exceptions import RepositoryException
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MongoSummaryReportRepository(ISummaryReportRepository):
    """SummaryReport MongoDB Repository 实现

    集合名称: summary_reports

    核心功能：
    - 报告的CRUD操作
    - 多维度过滤查询（创建者、状态、类型）
    - 内容更新（支持手动编辑、自动版本）
    - 状态管理
    - 查看次数统计
    """

    COLLECTION_NAME = "summary_reports"

    def __init__(self, db: AsyncIOMotorDatabase):
        """初始化Repository

        Args:
            db: MongoDB数据库实例
        """
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entity: SummaryReport) -> SummaryReport:
        """创建总结报告"""
        try:
            result = await self.collection.insert_one(entity.model_dump())
            logger.info(f"✅ 创建总结报告: {entity.report_id} - {entity.title}")
            return entity
        except Exception as e:
            logger.error(f"❌ 创建总结报告失败: {entity.report_id}, 错误: {e}")
            raise RepositoryException(f"创建总结报告失败: {e}")

    async def find_by_id(self, report_id: str) -> Optional[SummaryReport]:
        """根据ID查询报告"""
        try:
            doc = await self.collection.find_one({"report_id": report_id})
            return SummaryReport(**doc) if doc else None
        except Exception as e:
            logger.error(f"❌ 查询报告失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"查询报告失败: {e}")

    async def find_all(
        self,
        created_by: Optional[str] = None,
        status: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[SummaryReport]:
        """查询所有报告（支持过滤和分页）"""
        try:
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
        except Exception as e:
            logger.error(f"❌ 查询报告列表失败, 错误: {e}")
            raise RepositoryException(f"查询报告列表失败: {e}")

    async def update(self, report_id: str, update_data: Dict[str, Any]) -> bool:
        """更新报告"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = await self.collection.update_one(
                {"report_id": report_id},
                {"$set": update_data}
            )
            if result.modified_count > 0:
                logger.info(f"📝 更新报告: {report_id}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ 更新报告失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"更新报告失败: {e}")

    async def update_content(
        self,
        report_id: str,
        content_text: str,
        content_format: str = "markdown",
        is_manual: bool = False
    ) -> bool:
        """更新报告内容"""
        try:
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
        except Exception as e:
            logger.error(f"❌ 更新报告内容失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"更新报告内容失败: {e}")

    async def update_status(self, report_id: str, status: str) -> bool:
        """更新报告状态"""
        try:
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
        except Exception as e:
            logger.error(f"❌ 更新报告状态失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"更新报告状态失败: {e}")

    async def increment_view_count(self, report_id: str) -> bool:
        """增加查看次数"""
        try:
            result = await self.collection.update_one(
                {"report_id": report_id},
                {"$inc": {"view_count": 1}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"❌ 增加查看次数失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"增加查看次数失败: {e}")

    async def delete(self, report_id: str) -> bool:
        """删除报告"""
        try:
            result = await self.collection.delete_one({"report_id": report_id})
            logger.info(f"🗑️  删除报告: {report_id}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"❌ 删除报告失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"删除报告失败: {e}")

    # ==================== IBasicRepository 基础方法 ====================

    async def get_by_id(self, id: str) -> Optional[SummaryReport]:
        """根据ID获取报告（IBasicRepository要求的标准方法）

        Args:
            id: 报告ID

        Returns:
            Optional[SummaryReport]: 报告实体，不存在则返回None

        Raises:
            RepositoryException: 查询失败时抛出
        """
        # 调用已有的find_by_id方法
        return await self.find_by_id(id)

    async def exists(self, id: str) -> bool:
        """检查报告是否存在

        Args:
            id: 报告ID

        Returns:
            bool: 报告是否存在

        Raises:
            RepositoryException: 查询失败时抛出
        """
        try:
            count = await self.collection.count_documents({"report_id": id})
            return count > 0
        except Exception as e:
            logger.error(f"❌ 检查报告是否存在失败: {id}, 错误: {e}")
            raise RepositoryException(f"检查报告是否存在失败: {e}")


class MongoSummaryReportVersionRepository(ISummaryReportVersionRepository):
    """SummaryReportVersion MongoDB Repository 实现

    集合名称: summary_report_versions

    核心功能：
    - 版本记录的创建和查询
    - 按报告ID查询版本历史
    - 按版本号查询特定版本
    - 获取最新版本
    - 版本统计
    """

    COLLECTION_NAME = "summary_report_versions"

    def __init__(self, db: AsyncIOMotorDatabase):
        """初始化Repository

        Args:
            db: MongoDB数据库实例
        """
        self.collection = db[self.COLLECTION_NAME]

    async def create(self, entity: SummaryReportVersion) -> SummaryReportVersion:
        """创建版本记录"""
        try:
            await self.collection.insert_one(entity.model_dump())
            logger.info(f"✅ 创建版本记录: {entity.report_id} v{entity.version_number}")
            return entity
        except Exception as e:
            logger.error(f"❌ 创建版本记录失败: {entity.report_id}, 错误: {e}")
            raise RepositoryException(f"创建版本记录失败: {e}")

    async def find_by_report(
        self,
        report_id: str,
        limit: int = 20
    ) -> List[SummaryReportVersion]:
        """查询报告的版本历史"""
        try:
            cursor = self.collection.find({
                "report_id": report_id
            }).sort("version_number", -1).limit(limit)

            docs = await cursor.to_list(length=limit)
            return [SummaryReportVersion(**doc) for doc in docs]
        except Exception as e:
            logger.error(f"❌ 查询版本历史失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"查询版本历史失败: {e}")

    async def find_by_version_number(
        self,
        report_id: str,
        version_number: int
    ) -> Optional[SummaryReportVersion]:
        """根据版本号查询"""
        try:
            doc = await self.collection.find_one({
                "report_id": report_id,
                "version_number": version_number
            })
            return SummaryReportVersion(**doc) if doc else None
        except Exception as e:
            logger.error(f"❌ 查询版本失败: {report_id} v{version_number}, 错误: {e}")
            raise RepositoryException(f"查询版本失败: {e}")

    async def get_latest_version(
        self,
        report_id: str
    ) -> Optional[SummaryReportVersion]:
        """获取最新版本"""
        try:
            doc = await self.collection.find_one(
                {"report_id": report_id},
                sort=[("version_number", -1)]
            )
            return SummaryReportVersion(**doc) if doc else None
        except Exception as e:
            logger.error(f"❌ 获取最新版本失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"获取最新版本失败: {e}")

    async def delete_by_report(self, report_id: str) -> int:
        """删除报告的所有版本记录"""
        try:
            result = await self.collection.delete_many({"report_id": report_id})
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ 删除版本记录失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"删除版本记录失败: {e}")

    async def count_by_report(self, report_id: str) -> int:
        """统计报告的版本数量"""
        try:
            return await self.collection.count_documents({"report_id": report_id})
        except Exception as e:
            logger.error(f"❌ 统计版本数量失败: {report_id}, 错误: {e}")
            raise RepositoryException(f"统计版本数量失败: {e}")
