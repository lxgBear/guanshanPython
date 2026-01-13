"""质量门控节点 (v3.7.2)

对搜索结果进行质量门控检查，未通过时触发重试或使用备选策略。

功能:
- 质量阈值检查（结果数量、内容质量）
- 自动重试机制（最多3次）
- 备选策略（调整查询词、扩大范围等）
"""

import logging
from typing import Dict, Any, List, Optional, Literal

from ..state import SearchState
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


class QualityGateNode:
    """质量门控节点

    验证搜索结果质量，决定是否需要重新��索。

    质量标准:
    1. 最小结果数量（默认3条）
    2. 内容质量分数
    3. 来源多样性
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
    ):
        """初始化质量门控节点

        Args:
            config: LangGraph 搜索配置
        """
        self.config = config or LangGraphSearchConfig()

        # 质量阈值配置
        self.min_results = self.config.min_results or 3
        self.min_quality_score = self.config.min_quality_score or 0.6
        self.max_retries = self.config.max_search_retries or 3

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行质量门控检查

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典，包含质量检查结果和重试决策
        """
        user_id = state.get("user_id", "")
        aggregated_results = state.get("aggregated_results", [])
        retry_count = state.get("search_retry_count", 0)

        # 如果禁用质量门控，直接通过
        if not self.config.enable_quality_gate:
            logger.info(f"[user:{user_id}] 质量门控已禁用，跳过检查")
            return {
                "quality_gate_passed": True,
                "quality_gate_reason": "disabled",
                "quality_check_done": True,
            }

        # 检查结果数量
        result_count = len(aggregated_results)

        # 计算质量分数
        quality_metrics = self._calculate_quality_metrics(aggregated_results)

        # 质量门控决策
        passed, reason = self._evaluate_quality(
            result_count,
            quality_metrics
        )

        logger.info(
            f"[user:{user_id}] 质量门控检查: "
            f"结果数={result_count}, "
            f"质量分数={quality_metrics.get('avg_score', 0):.2f}, "
            f"通过={passed}, "
            f"原因={reason}"
        )

        # 更新状态
        update = {
            "quality_metrics": quality_metrics,
            "quality_gate_passed": passed,
            "quality_gate_reason": reason,
            "quality_check_done": True,
        }

        # 如果未通过且未超过重试次数，触发重试
        if not passed and retry_count < self.max_retries:
            update["should_retry_search"] = True
            update["search_retry_count"] = retry_count + 1
            update["retry_strategy"] = self._get_retry_strategy(reason, retry_count)
            logger.info(
                f"[user:{user_id}] 质量门控未通过，触发第 {retry_count + 1} 次重试，"
                f"策略: {update['retry_strategy']}"
            )
        else:
            update["should_retry_search"] = False
            if not passed:
                logger.warning(
                    f"[user:{user_id}] 质量门控未通过且已达最大重试次数 ({self.max_retries})，"
                    f"使用当前结果"
                )

        return update

    def _calculate_quality_metrics(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算结果质量指标

        Args:
            results: 搜索结果列表

        Returns:
            质量指标字典
        """
        if not results:
            return {
                "result_count": 0,
                "avg_score": 0.0,
                "high_quality_count": 0,
                "source_diversity": 0,
                "content_length_avg": 0,
            }

        total_score = 0.0
        high_quality_count = 0
        sources = set()
        total_content_length = 0

        for result in results:
            if isinstance(result, dict):
                score = result.get("score", result.get("final_score", 0.0))
                content = result.get("markdown_content", result.get("html_content", ""))
                url = result.get("url", "")
            else:
                # SearchResult 对象
                score = getattr(result, "score", getattr(result, "final_score", 0.0))
                content = getattr(result, "markdown_content", getattr(result, "html_content", ""))
                url = getattr(result, "url", "")

            total_score += score
            if score >= self.min_quality_score:
                high_quality_count += 1

            # 统计来源多样性
            if url:
                from ..utils.url_utils import extract_domain
                sources.add(extract_domain(url))

            total_content_length += len(content) if content else 0

        result_count = len(results)
        return {
            "result_count": result_count,
            "avg_score": total_score / result_count if result_count > 0 else 0.0,
            "high_quality_count": high_quality_count,
            "source_diversity": len(sources),
            "content_length_avg": total_content_length / result_count if result_count > 0 else 0,
        }

    def _evaluate_quality(
        self,
        result_count: int,
        quality_metrics: Dict[str, Any]
    ) -> tuple[bool, str]:
        """评估结果质量

        Args:
            result_count: 结果数量
            quality_metrics: 质量指标

        Returns:
            (是否通过, 原因)
        """
        # 检查最小结果数量
        if result_count < self.min_results:
            return False, f"insufficient_results ({result_count} < {self.min_results})"

        # 检查平均质量分数
        avg_score = quality_metrics.get("avg_score", 0.0)
        if avg_score < self.min_quality_score * 0.7:
            return False, f"low_quality_score ({avg_score:.2f} < {self.min_quality_score * 0.7:.2f})"

        # 检查高质量结果数量
        high_quality_count = quality_metrics.get("high_quality_count", 0)
        if high_quality_count < max(1, self.min_results // 2):
            return False, f"insufficient_high_quality ({high_quality_count} < {max(1, self.min_results // 2)})"

        # 所有检查通过
        return True, "all_checks_passed"

    def _get_retry_strategy(
        self,
        fail_reason: str,
        retry_count: int
    ) -> str:
        """获取重试策略

        Args:
            fail_reason: 失败原因
            retry_count: 当前重试次数

        Returns:
            重试策略名称
        """
        strategies = {
            "insufficient_results": [
                "expand_query",      # 扩大查询范围
                "remove_filters",    # 移除部分过滤条件
                "fallback_sources",  # 使用备选来源
            ],
            "low_quality_score": [
                "adjust_keywords",   # 调整关键词
                "change_perspective", # 改变查询角度
                "use_synonyms",      # 使用同义词
            ],
            "insufficient_high_quality": [
                "prioritize_tier",   # 优先高层级来源
                "extend_time_range", # 扩大时间范围
                "add_synonyms",      # 添加同义词
            ],
        }

        # 根据失败原因获取策略列表
        strategy_list = strategies.get(fail_reason, ["expand_query"])

        # 根据重试次数选择策略
        index = min(retry_count, len(strategy_list) - 1)
        return strategy_list[index]


def should_retry_search(state: SearchState) -> Literal["retry", "output"]:
    """条件边函数：决定是否重试搜索

    Args:
        state: 当前搜索状态

    Returns:
        "retry" 或 "output"
    """
    should_retry = state.get("should_retry_search", False)
    return "retry" if should_retry else "output"
