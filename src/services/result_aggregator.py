"""结果聚合器

智能搜索系统的结果聚合组件，负责：
- 跨多个子搜索去重
- 计算综合相关性评分
- 支持多种聚合视图
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.core.domain.entities.instant_search_task import InstantSearchTask
from src.core.domain.entities.instant_search_result import InstantSearchResult
from src.infrastructure.database.instant_search_repositories import (
    InstantSearchResultRepository,
    InstantSearchResultMappingRepository
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResultAggregator:
    """
    结果聚合器

    核心算法：
    1. 收集所有子搜索的结果
    2. 基于content_hash去重
    3. 计算综合评分
    4. 排序和分页
    """

    def __init__(self):
        self.result_repo = InstantSearchResultRepository()
        self.mapping_repo = InstantSearchResultMappingRepository()

    async def aggregate(
        self,
        sub_search_tasks: List[InstantSearchTask]
    ) -> Dict[str, Any]:
        """
        聚合多个子搜索的结果

        算法：
        1. 收集所有结果
        2. 基于content_hash去重
        3. 计算综合评分
        4. 统计信息

        Args:
            sub_search_tasks: 子搜索任务列表

        Returns:
            聚合统计信息
        """
        logger.info(f"开始聚合 {len(sub_search_tasks)} 个子搜索的结果")

        # 收集所有结果
        all_results = []
        total_searches = len(sub_search_tasks)
        successful_searches = 0
        failed_searches = 0
        total_credits_used = 0

        for task in sub_search_tasks:
            if task.status.value == "completed":
                successful_searches += 1
                total_credits_used += task.credits_used

                # 获取该任务的所有结果
                results_with_mapping, _ = await self.mapping_repo.get_results_by_search_execution(
                    search_execution_id=task.search_execution_id,
                    page=1,
                    page_size=1000  # 获取所有结果
                )

                for item in results_with_mapping:
                    all_results.append({
                        "result": item["result"],
                        "mapping": item["mapping"],
                        "task_id": task.id,
                        "query": task.query or task.crawl_url
                    })
            else:
                failed_searches += 1

        # 去重和评分
        deduplicated_results = self.deduplicate_by_content_hash(all_results)

        # 计算综合评分
        scored_results = []
        for content_hash, result_items in deduplicated_results.items():
            # 取第一个结果作为代表
            representative = result_items[0]

            # 收集所有来源信息
            sources = [
                {
                    "query": item["query"],
                    "task_id": item["task_id"],
                    "position": item["mapping"].search_position,
                    "relevance_score": item["mapping"].relevance_score
                }
                for item in result_items
            ]

            # 计算综合评分
            positions = [item["mapping"].search_position for item in result_items]
            relevance_scores = [item["mapping"].relevance_score for item in result_items]

            composite_score = self.calculate_composite_score(
                source_count=len(sources),
                positions=positions,
                relevance_scores=relevance_scores,
                total_queries=total_searches
            )

            scored_results.append({
                "result": representative["result"],
                "composite_score": composite_score,
                "sources": sources,
                "multi_source": len(sources) > 1,
                "source_count": len(sources)
            })

        # 按综合评分排序
        scored_results.sort(key=lambda x: x["composite_score"], reverse=True)

        # 统计信息
        total_results_raw = len(all_results)
        total_results_deduplicated = len(deduplicated_results)
        duplication_rate = (total_results_raw - total_results_deduplicated) / total_results_raw if total_results_raw > 0 else 0.0

        stats = {
            "total_searches": total_searches,
            "successful_searches": successful_searches,
            "failed_searches": failed_searches,
            "total_results_raw": total_results_raw,
            "total_results_deduplicated": total_results_deduplicated,
            "duplication_rate": round(duplication_rate, 2),
            "total_credits_used": total_credits_used
        }

        logger.info(
            f"聚合完成: 原始结果={total_results_raw}, "
            f"去重后={total_results_deduplicated}, "
            f"去重率={duplication_rate:.1%}"
        )

        return {
            "stats": stats,
            "results": scored_results
        }

    def deduplicate_by_content_hash(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        按content_hash去重，返回hash到结果列表的映射

        Args:
            results: 结果列表（包含result和mapping）

        Returns:
            content_hash -> 结果列表的映射
        """
        hash_to_results = defaultdict(list)

        for item in results:
            result: InstantSearchResult = item["result"]
            content_hash = result.content_hash

            hash_to_results[content_hash].append(item)

        logger.debug(f"去重: {len(results)}条 -> {len(hash_to_results)}条唯一结果")
        return dict(hash_to_results)

    def calculate_composite_score(
        self,
        source_count: int,
        positions: List[int],
        relevance_scores: List[float],
        total_queries: int
    ) -> float:
        """
        计算综合评分

        评分公式：
        composite_score =
            0.4 * multi_source_score +  # 多源得分
            0.4 * relevance_score +      # 相关性得分
            0.2 * position_score         # 位置得分

        其中：
        - multi_source_score = (出现次数 / 总子查询数)
        - relevance_score = 平均相关性分数
        - position_score = 1 / (1 + avg_position)

        Args:
            source_count: 出现在多少个子查询中
            positions: 在各个子查询中的位置
            relevance_scores: 在各个子查询中的相关性分数
            total_queries: 总查询数

        Returns:
            综合评分（0.0-1.0）
        """
        # 多源得分：出现在越多查询中，得分越高
        multi_source_score = source_count / total_queries

        # 相关性得分：平均相关性
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

        # 位置得分：平均排名越靠前，得分越高
        avg_position = sum(positions) / len(positions) if positions else 1
        position_score = 1.0 / (1.0 + avg_position)

        # 综合评分
        composite_score = (
            0.4 * multi_source_score +
            0.4 * avg_relevance +
            0.2 * position_score
        )

        return round(composite_score, 4)

    async def get_combined_view(
        self,
        aggregated_data: Dict[str, Any],
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取综合去重视图

        Args:
            aggregated_data: 聚合数据
            page: 页码
            page_size: 每页数量

        Returns:
            分页后的综合视图
        """
        results = aggregated_data["results"]
        stats = aggregated_data["stats"]

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = results[start:end]

        # 格式化结果
        formatted_results = []
        for item in paginated_results:
            result: InstantSearchResult = item["result"]

            formatted_results.append({
                "result": result.to_dict(),
                "composite_score": item["composite_score"],
                "sources": item["sources"],
                "multi_source_bonus": item["multi_source"],
                "source_count": item["source_count"]
            })

        return {
            "statistics": stats,
            "results": formatted_results,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": len(results),
                "total_pages": (len(results) + page_size - 1) // page_size
            }
        }

    async def get_by_query_view(
        self,
        sub_search_tasks: List[InstantSearchTask],
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取按查询分组的视图

        Args:
            sub_search_tasks: 子搜索任务列表
            page: 页码（应用于每个查询的结果）
            page_size: 每页数量

        Returns:
            按查询分组的结果
        """
        results_by_query = []

        for task in sub_search_tasks:
            # 获取该任务的结果
            results_with_mapping, total = await self.mapping_repo.get_results_by_search_execution(
                search_execution_id=task.search_execution_id,
                page=page,
                page_size=page_size
            )

            # 格式化结果
            formatted_results = []
            for item in results_with_mapping:
                result: InstantSearchResult = item["result"]
                mapping = item["mapping"]

                formatted_results.append({
                    **result.to_dict(),
                    "search_position": mapping.search_position,
                    "relevance_score": mapping.relevance_score,
                    "is_first_discovery": mapping.is_first_discovery
                })

            results_by_query.append({
                "query": task.query or task.crawl_url,
                "task_id": task.id,
                "status": task.status.value,
                "count": total,
                "credits_used": task.credits_used,
                "execution_time_ms": task.execution_time_ms,
                "results": formatted_results,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            })

        return {
            "results_by_query": results_by_query
        }
