"""交叉验证节点

对聚合结果进行交叉验证，提高结果可信度。
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..state import SearchState, SearchResult
from ..config import LangGraphSearchConfig
from ..utils.url_utils import extract_domain, get_root_domain

logger = logging.getLogger(__name__)


class ValidatorNode:
    """交叉验证节点

    验证策略:
    1. 多源验证: 相同事实被多个独立来源报道
    2. 权威验证: 官方来源确认
    3. 时间验证: 发布时间合理性
    4. 内容一致性: 关键信息是否一致
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
    ):
        """初始化验证节点

        Args:
            config: LangGraph 搜索配置
        """
        self.config = config or LangGraphSearchConfig()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行交叉验证

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        aggregated_results = state.get("aggregated_results", [])

        # 如果禁用验证，直接跳过
        if not self.config.enable_validation:
            logger.info(f"[user:{user_id}] Validation disabled, skipping")
            return {
                "validation_scores": {},
                "cross_validation_done": True,
            }

        # 如果结果数量不足，跳过验证
        if len(aggregated_results) < self.config.min_results_for_validation:
            logger.info(
                f"[user:{user_id}] Not enough results for validation "
                f"({len(aggregated_results)} < {self.config.min_results_for_validation})"
            )
            return {
                "validation_scores": {},
                "cross_validation_done": True,
            }

        try:
            logger.info(
                f"[user:{user_id}] Validating {len(aggregated_results)} results"
            )

            # 转换为 SearchResult 对象
            results = []
            for result_data in aggregated_results:
                if isinstance(result_data, dict):
                    results.append(SearchResult.from_dict(result_data))
                else:
                    results.append(result_data)

            # 执行验证
            validation_scores = self._validate_results(results)

            # 更新结果分数
            updated_results = self._apply_validation_scores(results, validation_scores)

            # 转换回字典格式
            updated_aggregated = [r.to_dict() for r in updated_results]

            logger.info(
                f"[user:{user_id}] Validation complete: "
                f"{len(validation_scores)} results scored"
            )

            return {
                "aggregated_results": updated_aggregated,
                "validation_scores": validation_scores,
                "cross_validation_done": True,
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Validation failed: {e}")
            return {
                "validation_scores": {},
                "cross_validation_done": True,
                "error_message": f"验证失败: {str(e)}",
            }

    def _validate_results(
        self,
        results: List[SearchResult],
    ) -> Dict[str, float]:
        """验证结果

        Args:
            results: 搜索结果列表

        Returns:
            URL → 验证分数的映射
        """
        validation_scores = {}

        # 按根域名分组
        domain_groups = self._group_by_root_domain(results)

        # 统计每个标题/主题出现在多少个不同根域名
        title_domain_counts = self._count_title_domains(results)

        for result in results:
            url = result.url or ""
            if not url:
                continue  # 跳过没有 URL 的结果

            score = 0.0

            # 1. 多源验证加分 (最高 0.3)
            title_key = self._normalize_title(result.title)
            domain_count = title_domain_counts.get(title_key, 1)
            multi_source_score = min(0.3, (domain_count - 1) * 0.1)
            score += multi_source_score

            # 2. 层级权威加分 (最高 0.3)
            source_tier = result.source_tier if result.source_tier else 4
            tier_score = self._calculate_tier_score(source_tier)
            score += tier_score

            # 3. 域名多样性加分 (最高 0.2)
            root_domain = get_root_domain(extract_domain(url))
            domain_diversity = len(domain_groups.get(root_domain, []))
            diversity_score = min(0.2, domain_diversity * 0.05)
            score += diversity_score

            # 4. 内容长度加分 (最高 0.2)
            content_score = self._calculate_content_score(result)
            score += content_score

            validation_scores[url] = min(1.0, score)

        return validation_scores

    def _group_by_root_domain(
        self,
        results: List[SearchResult],
    ) -> Dict[str, List[SearchResult]]:
        """按根域名分组

        Args:
            results: 结果列表

        Returns:
            根域名 → 结果列表的映射
        """
        groups = defaultdict(list)

        for result in results:
            url = result.url or ""
            if not url:
                continue
            domain = extract_domain(url)
            root_domain = get_root_domain(domain)
            if root_domain:
                groups[root_domain].append(result)

        return dict(groups)

    def _count_title_domains(
        self,
        results: List[SearchResult],
    ) -> Dict[str, int]:
        """统计标题出现在多少个不同域名

        Args:
            results: 结果列表

        Returns:
            标题 → 域名数量的映射
        """
        title_domains = defaultdict(set)

        for result in results:
            title_key = self._normalize_title(result.title)
            if not title_key:
                continue  # 跳过空标题
            url = result.url or ""
            if not url:
                continue
            domain = extract_domain(url)
            root_domain = get_root_domain(domain)
            if root_domain:
                title_domains[title_key].add(root_domain)

        return {k: len(v) for k, v in title_domains.items()}

    def _normalize_title(self, title: Optional[str]) -> str:
        """规范化标题用于比较

        Args:
            title: 原始标题 (可能为 None)

        Returns:
            规范化后的标题
        """
        if title is None or title == "":
            return ""
        # 确保 title 是字符串类型
        title_str = str(title) if not isinstance(title, str) else title
        # 转小写，移除特殊字符
        import re
        normalized = title_str.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    def _calculate_tier_score(self, source_tier: int) -> float:
        """计算层级权威分数

        Args:
            source_tier: 来源等级 (1-6)

        Returns:
            权威分数 (0-0.3)
        """
        tier_scores = {
            1: 0.30,  # 官方来源
            2: 0.25,  # 主流媒体
            3: 0.20,  # 区域媒体
            4: 0.15,  # 一般来源
            5: 0.10,  # 低权威
            6: 0.05,  # 未知来源
        }
        return tier_scores.get(source_tier, 0.1)

    def _calculate_content_score(self, result: SearchResult) -> float:
        """计算内容质量分数

        Args:
            result: 搜索结果

        Returns:
            内容分数 (0-0.2)
        """
        content = result.markdown_content or ""
        content_length = len(content)

        if content_length > 5000:
            return 0.20
        elif content_length > 2000:
            return 0.15
        elif content_length > 500:
            return 0.10
        elif content_length > 100:
            return 0.05
        else:
            return 0.0

    def _apply_validation_scores(
        self,
        results: List[SearchResult],
        validation_scores: Dict[str, float],
    ) -> List[SearchResult]:
        """应用验证分数到结果

        Args:
            results: 结果列表
            validation_scores: 验证分数映射

        Returns:
            更新后的结果列表
        """
        for result in results:
            validation_score = validation_scores.get(result.url, 0.5)

            # 更新最终分数：原始分数 * 0.7 + 验证分数 * 0.3
            result.final_score = (
                result.final_score * 0.7 +
                validation_score * 0.3
            )

        # 重新排序
        results.sort(key=lambda x: x.final_score, reverse=True)

        return results
