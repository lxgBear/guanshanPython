"""
Repository 接口层

定义统一的 Repository 接口层次结构，实现依赖倒置原则。
所有具体的 Repository 实现都应该实现这些接口。

Version: v3.0.0 (模块化架构)
"""

from .i_repository import (
    IBasicRepository,
    IQueryableRepository,
    IPaginatableRepository,
    IBulkOperationRepository
)

from .i_task_repository import ITaskRepository
from .i_result_repository import IResultRepository
from .i_processed_result_repository import IProcessedResultRepository
from .i_instant_search_repository import (
    IInstantSearchTaskRepository,
    IInstantSearchResultRepository,
    IInstantSearchResultMappingRepository
)
from .i_smart_search_repository import (
    ISmartSearchTaskRepository,
    ISmartSearchResultRepository,
    IQueryDecompositionCacheRepository
)
from .i_data_source_repository import IDataSourceRepository
from .i_archived_data_repository import IArchivedDataRepository
from .i_summary_report_repository import (
    ISummaryReportRepository,
    ISummaryReportVersionRepository
)
from .i_firecrawl_raw_repository import IFirecrawlRawResponseRepository
from .i_aggregated_search_result_repository import IAggregatedSearchResultRepository
from .i_instant_processed_result_repository import IInstantProcessedResultRepository

__all__ = [
    # 基础接口
    'IBasicRepository',
    'IQueryableRepository',
    'IPaginatableRepository',
    'IBulkOperationRepository',

    # 核心搜索接口
    'ITaskRepository',
    'IResultRepository',
    'IProcessedResultRepository',

    # 即时搜索接口
    'IInstantSearchTaskRepository',
    'IInstantSearchResultRepository',
    'IInstantSearchResultMappingRepository',

    # 智能搜索接口
    'ISmartSearchTaskRepository',
    'ISmartSearchResultRepository',
    'IQueryDecompositionCacheRepository',

    # 数据源和存档接口
    'IDataSourceRepository',
    'IArchivedDataRepository',

    # 报告接口
    'ISummaryReportRepository',
    'ISummaryReportVersionRepository',

    # 临时仓储接口
    'IFirecrawlRawResponseRepository',

    # 聚合和AI处理接口
    'IAggregatedSearchResultRepository',
    'IInstantProcessedResultRepository',
]
