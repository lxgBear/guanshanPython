"""智能总结报告仓储层

Version: v3.0.0 (模块化架构)
提供向后兼容的 Repository 实现。

注意：新代码应使用 src.infrastructure.persistence.repositories.mongo 模块中的实现。
本模块保留用于向后兼容，逐步迁移后将被弃用。
"""

# v3.0.0: 导入新的 Repository 实现
from src.infrastructure.persistence.repositories.mongo import (
    MongoSummaryReportRepository as _MongoSummaryReportRepository,
    MongoSummaryReportVersionRepository as _MongoSummaryReportVersionRepository
)


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoSummaryReportRepository
class SummaryReportRepository(_MongoSummaryReportRepository):
    """
    总结报告仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoSummaryReportRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoSummaryReportRepository

    注意：此类的所有功能已由父类 MongoSummaryReportRepository 实现。

    核心功能：
    - 报告的CRUD操作
    - 多维度过滤查询（创建者、状态、类型）
    - 内容更新（支持手动编辑、自动版本）
    - 状态管理（draft → in_progress → completed）
    - 查看次数统计
    """
    pass


# v3.0.0: 向后兼容别名
# 新代码应直接使用 MongoSummaryReportVersionRepository
class SummaryReportVersionRepository(_MongoSummaryReportVersionRepository):
    """
    报告版本历史仓储 (向后兼容层)

    v3.0.0: 此类继承自 MongoSummaryReportVersionRepository，提供向后兼容。
    新代码应使用: from src.infrastructure.persistence.repositories.mongo import MongoSummaryReportVersionRepository

    注意：此类的所有功能已由父类 MongoSummaryReportVersionRepository 实现。

    核心功能：
    - 版本记录的创建和查询
    - 按报告ID查询版本历史
    - 按版本号查询特定版本
    - 获取最新版本
    - 版本统计
    """
    pass
