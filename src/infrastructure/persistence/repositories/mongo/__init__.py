"""
MongoDB Repository 实现

提供基于 MongoDB 的 Repository 具体实现。

Version: v3.0.0 (模块化架构)
"""

from .task_repository import MongoTaskRepository
from .result_repository import MongoResultRepository
from .processed_result_repository import MongoProcessedResultRepository
from .instant_search_task_repository import MongoInstantSearchTaskRepository
from .instant_search_result_repository import MongoInstantSearchResultRepository
from .instant_search_result_mapping_repository import MongoInstantSearchResultMappingRepository
from .smart_search_task_repository import MongoSmartSearchTaskRepository
from .smart_search_result_repository import MongoSmartSearchResultRepository
from .query_decomposition_cache_repository import MongoQueryDecompositionCacheRepository
from .data_source_repository import MongoDataSourceRepository
from .archived_data_repository import MongoArchivedDataRepository
from .summary_report_repository import (
    MongoSummaryReportRepository,
    MongoSummaryReportVersionRepository
)
from .firecrawl_raw_repository import MongoFirecrawlRawResponseRepository
from .aggregated_search_result_repository import MongoAggregatedSearchResultRepository
from .instant_processed_result_repository import MongoInstantProcessedResultRepository

__all__ = [
    'MongoTaskRepository',
    'MongoResultRepository',
    'MongoProcessedResultRepository',
    'MongoInstantSearchTaskRepository',
    'MongoInstantSearchResultRepository',
    'MongoInstantSearchResultMappingRepository',
    'MongoSmartSearchTaskRepository',
    'MongoSmartSearchResultRepository',
    'MongoQueryDecompositionCacheRepository',
    'MongoDataSourceRepository',
    'MongoArchivedDataRepository',
    'MongoSummaryReportRepository',
    'MongoSummaryReportVersionRepository',
    'MongoFirecrawlRawResponseRepository',
    'MongoAggregatedSearchResultRepository',
    'MongoInstantProcessedResultRepository',
]
