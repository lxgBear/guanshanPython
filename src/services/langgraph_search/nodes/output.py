"""输出节点

格式化最终搜索结果，生成统计信息。
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..state import SearchState, SearchResult
from ..config import LangGraphSearchConfig
from ..utils.url_utils import extract_domain

logger = logging.getLogger(__name__)


class OutputNode:
    """输出节点

    功能:
    - 格式化最终结果
    - 生成统计信息
    - 标记完成状态
    - 确定是否需要人工审核
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
    ):
        """初始化输出节点

        Args:
            config: LangGraph 搜索配置
        """
        self.config = config or LangGraphSearchConfig()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行输出格式化

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        aggregated_results = state.get("aggregated_results", [])
        layer_results = state.get("layer_results", {})
        validation_scores = state.get("validation_scores", {})

        try:
            logger.info(f"[user:{user_id}] Formatting {len(aggregated_results)} results")

            # 转换为 SearchResult 对象
            results = []
            for result_data in aggregated_results:
                if isinstance(result_data, dict):
                    results.append(SearchResult.from_dict(result_data))
                else:
                    results.append(result_data)

            # 格式化最终结果
            final_results = self._format_final_results(results)

            # 生成统计信息
            statistics = self._generate_statistics(
                results,
                layer_results,
                validation_scores,
            )

            # 判断是否需要人工审核
            needs_review = self._check_needs_review(results, statistics)

            logger.info(
                f"[user:{user_id}] Output complete: "
                f"{len(final_results)} results, needs_review={needs_review}"
            )

            return {
                "final_results": final_results,
                "statistics": statistics,
                "needs_review": needs_review,
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Output formatting failed: {e}")
            return {
                "final_results": [],
                "statistics": {},
                "status": "failed",
                "error_message": f"输出格式化失败: {str(e)}",
                "completed_at": datetime.utcnow().isoformat(),
            }

    def _format_final_results(
        self,
        results: List[SearchResult],
    ) -> List[Dict[str, Any]]:
        """格式化最终结果

        Args:
            results: 搜索结果列表

        Returns:
            格式化后的结果字典列表
        """
        final_results = []

        for i, result in enumerate(results):
            formatted = {
                "rank": i + 1,
                "url": result.url,
                "title": result.title,
                "snippet": result.snippet,
                "source_domain": result.source_domain,
                # 分层信息
                "layer": result.layer,
                "layer_name": result.layer_name,
                "source_tier": result.source_tier,
                # 评分
                "relevance_score": round(result.relevance_score, 4),
                "credibility_score": round(result.credibility_score, 4),
                "final_score": round(result.final_score, 4),
                # 内容
                "has_content": bool(result.markdown_content),
                "content_length": len(result.markdown_content or ""),
                # 元数据
                "language": result.language,
                "published_date": result.published_date,
                "fetched_at": (
                    result.fetched_at.isoformat()
                    if result.fetched_at
                    else None
                ),
            }
            final_results.append(formatted)

        return final_results

    def _generate_statistics(
        self,
        results: List[SearchResult],
        layer_results: Dict[int, Dict],
        validation_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """生成统计信息

        Args:
            results: 搜索结果列表
            layer_results: 层级结果
            validation_scores: 验证分数

        Returns:
            统计信息字典
        """
        if not results:
            return {
                "total_results": 0,
                "layer_stats": {},
                "domain_distribution": {},
                "tier_distribution": {},
                "score_stats": {},
            }

        # 按层级统计
        layer_stats = {}
        total_execution_time = 0

        for layer, layer_data in layer_results.items():
            if isinstance(layer_data, dict):
                layer_stats[str(layer)] = {
                    "name": layer_data.get("layer_name", f"Layer {layer}"),
                    "result_count": len(layer_data.get("results", [])),
                    "queries_executed": len(layer_data.get("queries_executed", [])),
                    "execution_time_ms": layer_data.get("execution_time_ms", 0),
                    "error": layer_data.get("error"),
                }
                total_execution_time += layer_data.get("execution_time_ms", 0)

        # 按域名统计
        domain_counts = defaultdict(int)
        for result in results:
            domain = extract_domain(result.url)
            domain_counts[domain] += 1

        domain_distribution = dict(
            sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        # 按层级等级统计
        tier_counts = defaultdict(int)
        for result in results:
            tier_counts[result.source_tier] += 1

        tier_distribution = {
            f"tier_{k}": v for k, v in sorted(tier_counts.items())
        }

        # 分数统计
        relevance_scores = [r.relevance_score for r in results]
        credibility_scores = [r.credibility_score for r in results]
        final_scores = [r.final_score for r in results]

        score_stats = {
            "relevance": {
                "min": round(min(relevance_scores), 4),
                "max": round(max(relevance_scores), 4),
                "avg": round(sum(relevance_scores) / len(relevance_scores), 4),
            },
            "credibility": {
                "min": round(min(credibility_scores), 4),
                "max": round(max(credibility_scores), 4),
                "avg": round(sum(credibility_scores) / len(credibility_scores), 4),
            },
            "final": {
                "min": round(min(final_scores), 4),
                "max": round(max(final_scores), 4),
                "avg": round(sum(final_scores) / len(final_scores), 4),
            },
        }

        # 验证统计
        validation_stats = {}
        if validation_scores:
            v_scores = list(validation_scores.values())
            validation_stats = {
                "validated_count": len(v_scores),
                "min": round(min(v_scores), 4),
                "max": round(max(v_scores), 4),
                "avg": round(sum(v_scores) / len(v_scores), 4),
            }

        # 语言统计
        language_counts = defaultdict(int)
        for result in results:
            language_counts[result.language or "unknown"] += 1

        return {
            "total_results": len(results),
            "unique_domains": len(domain_counts),
            "total_execution_time_ms": total_execution_time,
            "layer_stats": layer_stats,
            "domain_distribution": domain_distribution,
            "tier_distribution": tier_distribution,
            "language_distribution": dict(language_counts),
            "score_stats": score_stats,
            "validation_stats": validation_stats,
        }

    def _check_needs_review(
        self,
        results: List[SearchResult],
        statistics: Dict[str, Any],
    ) -> bool:
        """检查是否需要人工审核

        Args:
            results: 搜索结果列表
            statistics: 统计信息

        Returns:
            是否需要人工审核
        """
        # 如果禁用人工审核，返回 False
        if not self.config.enable_human_review:
            return False

        # 检查条件
        needs_review = False

        # 1. 结果数量不足
        if len(results) < 5:
            needs_review = True

        # 2. 平均分数过低
        score_stats = statistics.get("score_stats", {})
        avg_final = score_stats.get("final", {}).get("avg", 0)
        if avg_final < self.config.review_threshold:
            needs_review = True

        # 3. 高层级来源不足
        tier_distribution = statistics.get("tier_distribution", {})
        tier_1_count = tier_distribution.get("tier_1", 0)
        tier_2_count = tier_distribution.get("tier_2", 0)
        if tier_1_count + tier_2_count < 3:
            needs_review = True

        # 4. 验证分数过低
        validation_stats = statistics.get("validation_stats", {})
        avg_validation = validation_stats.get("avg", 1.0)
        if avg_validation < self.config.validation_threshold:
            needs_review = True

        return needs_review
