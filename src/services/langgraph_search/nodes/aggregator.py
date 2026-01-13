"""结果聚合节点

聚合各层搜索结果，进行去重和排序。
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..state import SearchState, SearchResult, LayerSearchResult
from ..config import LangGraphSearchConfig
from ..utils.url_utils import normalize_url, extract_domain, get_root_domain

logger = logging.getLogger(__name__)


class AggregatorNode:
    """结果聚合节点

    功能:
    - URL 去重（规范化后比较）
    - 多层结果合并
    - 综合评分计算
    - 结果排序
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
    ):
        """初始化聚合节点

        Args:
            config: LangGraph 搜索配置
        """
        self.config = config or LangGraphSearchConfig()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行结果聚合

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        layer_results = state.get("layer_results", {})

        try:
            # 记录每层的结果数量
            layer_counts = {
                layer: len(data.get("results", [])) if isinstance(data, dict) else 0
                for layer, data in layer_results.items()
            }
            logger.info(
                f"[AGGREGATOR_START] user_id={user_id}, "
                f"layers_count={len(layer_results)}, "
                f"per_layer_counts={layer_counts}"
            )

            # 收集所有结果
            all_results = self._collect_results(layer_results)

            if not all_results:
                logger.warning(
                    f"[AGGREGATOR_EMPTY] user_id={user_id}, "
                    f"层结果数量={layer_counts}, "
                    f"原因: 所有层搜索都未返回结果"
                )
                return {
                    "aggregated_results": [],
                }

            # URL 去重
            url_deduplicated = self._deduplicate_by_url(all_results)

            # 计算综合评分
            scored = self._calculate_composite_scores(url_deduplicated)

            # 排序
            sorted_results = sorted(
                scored,
                key=lambda x: x.final_score,
                reverse=True,
            )

            # 内容相似度去重 (在排序后进行，保留高分结果)
            content_deduplicated = self._deduplicate_by_content(sorted_results)

            # 转换为字典格式
            aggregated_results = [r.to_dict() for r in content_deduplicated]

            logger.info(
                f"[AGGREGATOR_COMPLETE] user_id={user_id}, "
                f"total={len(all_results)} → url_dedup={len(url_deduplicated)} → "
                f"content_dedup={len(aggregated_results)}"
            )

            return {
                "aggregated_results": aggregated_results,
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] Aggregation failed: {e}")
            return {
                "aggregated_results": [],
                "error_message": f"聚合失败: {str(e)}",
            }

    def _collect_results(
        self,
        layer_results: Dict[int, Dict],
    ) -> List[SearchResult]:
        """从各层收集结果

        Args:
            layer_results: 层级结果映射

        Returns:
            所有结果列表
        """
        all_results = []

        for layer, layer_data in layer_results.items():
            if not isinstance(layer_data, dict):
                logger.warning(f"[AGGREGATOR] Layer {layer} data is not a dict: {type(layer_data)}")
                continue

            results_data = layer_data.get("results", [])
            if not results_data:
                continue

            for result_data in results_data:
                if result_data is None:
                    logger.warning(f"[AGGREGATOR] Skipping None result_data in layer {layer}")
                    continue

                try:
                    if isinstance(result_data, dict):
                        result = SearchResult.from_dict(result_data)
                        all_results.append(result)
                    elif isinstance(result_data, SearchResult):
                        all_results.append(result_data)
                    else:
                        logger.warning(f"[AGGREGATOR] Unknown result type: {type(result_data)}")
                except Exception as e:
                    logger.warning(f"[AGGREGATOR] Failed to parse result in layer {layer}: {e}")
                    continue

        return all_results

    def _deduplicate_by_url(
        self,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """按 URL 去重

        保留分数最高的结果，并累加多源信息。

        Args:
            results: 原始结果列表

        Returns:
            去重后的结果列表
        """
        url_map: Dict[str, Dict[str, Any]] = {}

        for result in results:
            normalized_url = normalize_url(result.url)

            if normalized_url not in url_map:
                url_map[normalized_url] = {
                    "result": result,
                    "source_count": 1,
                    "layers": [result.layer],
                    "total_relevance": result.relevance_score,
                    "total_credibility": result.credibility_score,
                }
            else:
                entry = url_map[normalized_url]
                entry["source_count"] += 1
                entry["layers"].append(result.layer)
                entry["total_relevance"] += result.relevance_score
                entry["total_credibility"] += result.credibility_score

                # 如果新结果分数更高，替换
                if result.final_score > entry["result"].final_score:
                    entry["result"] = result

        # 构建去重结果
        deduplicated = []
        for normalized_url, entry in url_map.items():
            result = entry["result"]

            # 计算平均分数
            source_count = entry["source_count"]
            result.relevance_score = entry["total_relevance"] / source_count
            result.credibility_score = entry["total_credibility"] / source_count

            deduplicated.append(result)

        return deduplicated

    def _calculate_composite_scores(
        self,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """计算综合评分

        综合评分公式:
        final_score = (relevance * 0.35 + credibility * 0.35 + layer_weight * 0.15 + recency * 0.15) * multi_source_bonus

        Args:
            results: 结果列表

        Returns:
            更新评分后的结果列表
        """
        # 构建标题相似度分组，用于多源验证
        title_groups = self._group_similar_titles(results)

        for result in results:
            # 获取层级权重
            layer_weight = self.config.get_layer_weight(result.layer)

            # 计算时效性评分
            recency_score = self._calculate_recency_score(result)

            # 计算真实的多源奖励
            title_key = self._normalize_title(result.title)
            similar_group = title_groups.get(title_key, [result])
            unique_domains = len(set(
                get_root_domain(extract_domain(r.url)) for r in similar_group
            ))
            # 每多一个独立来源，增加 10% 奖励，最高 30%
            multi_source_bonus = min(1.3, 1.0 + (unique_domains - 1) * 0.1)

            # 基础分数 (调整权重以包含时效性)
            base_score = (
                result.relevance_score * 0.35 +
                result.credibility_score * 0.35 +
                layer_weight * 0.15 +
                recency_score * 0.15
            )

            result.final_score = base_score * multi_source_bonus

        return results

    def _group_similar_titles(
        self,
        results: List[SearchResult],
    ) -> Dict[str, List[SearchResult]]:
        """按标题相似度分组

        用于多源验证，将报道相同事件的结果归为一组。

        Args:
            results: 结果列表

        Returns:
            标题键到结果列表的映射
        """
        groups: Dict[str, List[SearchResult]] = defaultdict(list)
        for result in results:
            title_key = self._normalize_title(result.title)
            groups[title_key].append(result)
        return dict(groups)

    def _normalize_title(self, title: str) -> str:
        """规范化标题用于比较

        移除标点、转小写、截断，使相似标题能够匹配。

        Args:
            title: 原始标题

        Returns:
            规范化后的标题键
        """
        import re
        if not title:
            return ""
        normalized = title.lower()
        # 移除标点符号
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # 合并空白
        normalized = re.sub(r'\s+', ' ', normalized)
        # 取前50字符作为键
        return normalized.strip()[:50]

    def _calculate_recency_score(self, result: SearchResult) -> float:
        """计算时效性评分

        根据发布日期计算时效性分数，越新的内容分数越高。

        Args:
            result: 搜索结果

        Returns:
            时效性评分 (0.0-1.0)
        """
        from datetime import datetime, timezone

        # 如果没有发布日期，返回中等分数
        if not result.published_date:
            return 0.5

        try:
            # 解析 ISO 格式日期
            pub_date_str = result.published_date.replace('Z', '+00:00')
            pub_date = datetime.fromisoformat(pub_date_str)

            # 确保 pub_date 有时区信息
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)

            # 计算距今天数
            now = datetime.now(timezone.utc)
            days_ago = (now - pub_date).days

            # 根据时间距离返回评分
            if days_ago <= 1:
                return 1.0    # 24小时内
            elif days_ago <= 7:
                return 0.8    # 1周内
            elif days_ago <= 30:
                return 0.5    # 1月内
            elif days_ago <= 90:
                return 0.3    # 3月内
            else:
                return 0.2    # 更早
        except (ValueError, TypeError):
            return 0.5

    def _deduplicate_by_content(
        self,
        results: List[SearchResult],
        similarity_threshold: float = 0.8,
    ) -> List[SearchResult]:
        """基于内容相似度去重

        使用标题和摘要的文本相似度来识别重复内容。
        由于输入已按分数排序，先出现的结果会被保留。

        Args:
            results: 按分数排序的结果列表
            similarity_threshold: 相似度阈值，超过此值视为重复 (默认 0.8)

        Returns:
            去重后的结果列表
        """
        from difflib import SequenceMatcher

        if not results:
            return []

        deduplicated: List[SearchResult] = []

        for result in results:
            is_duplicate = False
            content = f"{result.title or ''} {result.snippet or ''}"

            # 只与已保留的结果比较（限制比较数量以提高性能）
            for existing in deduplicated[-50:]:  # 只比较最近的50个
                existing_content = f"{existing.title or ''} {existing.snippet or ''}"

                # 快速预检：如果长度差异过大，跳过详细比较
                len_ratio = len(content) / max(len(existing_content), 1)
                if len_ratio < 0.5 or len_ratio > 2.0:
                    continue

                # 计算相似度
                similarity = SequenceMatcher(
                    None, content, existing_content
                ).ratio()

                if similarity > similarity_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"Content duplicate found: '{(result.title or '')[:30]}...' "
                        f"similar to '{(existing.title or '')[:30]}...' (similarity={similarity:.2f})"
                    )
                    break

            if not is_duplicate:
                deduplicated.append(result)

        return deduplicated

    def _calculate_statistics(
        self,
        aggregated_results: List[SearchResult],
        layer_results: Dict[int, Dict],
    ) -> Dict[str, Any]:
        """计算统计信息

        Args:
            aggregated_results: 聚合后的结果
            layer_results: 层级结果

        Returns:
            统计信息字典
        """
        # 按层级统计
        layer_stats = {}
        for layer, layer_data in layer_results.items():
            layer_stats[str(layer)] = {
                "name": layer_data.get("layer_name", f"Layer {layer}"),
                "result_count": len(layer_data.get("results", [])),
                "execution_time_ms": layer_data.get("execution_time_ms", 0),
                "error": layer_data.get("error"),
            }

        # 按域名统计
        domain_counts = defaultdict(int)
        for result in aggregated_results:
            domain = extract_domain(result.url)
            domain_counts[domain] += 1

        # 按层级分布统计
        tier_distribution = defaultdict(int)
        for result in aggregated_results:
            tier_distribution[result.source_tier] += 1

        return {
            "total_results": len(aggregated_results),
            "layer_stats": layer_stats,
            "top_domains": dict(
                sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "tier_distribution": dict(tier_distribution),
            "avg_relevance_score": (
                sum(r.relevance_score for r in aggregated_results) / len(aggregated_results)
                if aggregated_results else 0
            ),
            "avg_credibility_score": (
                sum(r.credibility_score for r in aggregated_results) / len(aggregated_results)
                if aggregated_results else 0
            ),
        }
