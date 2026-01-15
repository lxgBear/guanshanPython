"""交叉验证节点

对聚合结果进行交叉验证，提高结果可信度。
"""

import logging
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict

from ..state import SearchState, SearchResult
from ..config import LangGraphSearchConfig
from ..utils.url_utils import extract_domain, get_root_domain

logger = logging.getLogger(__name__)


# 用户意图词列表 - 这些词决定搜索哪些媒体，但不应作为搜索关键词
# 用于在验证时过滤掉与主题不相关的结果
INTENT_WORDS_TO_FILTER = {
    "zh": [
        "西方媒体", "西方主流媒体", "欧美媒体", "西方新闻", "国际媒体", "海外媒体",
        "西方国家", "美英", "欧美", "西方世界", "西方国家报道", "欧美新闻",
        "亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体", "亚洲国家", "邻国媒体",
        "亚洲视角", "东亚报道", "当地媒体", "国内媒体", "中国媒体", "中文媒体",
        "本地媒体", "欧洲媒体", "欧盟媒体", "欧洲新闻", "欧洲报道", "中东媒体",
        "阿拉伯媒体", "中东新闻", "拉美媒体", "拉丁美洲媒体", "西班牙语媒体",
        "葡萄牙语媒体", "报道", "反应", "整理", "检索", "搜索", "查找", "收集", "汇总", "筛选",
    ],
    "en": [
        "western media", "western news", "international media", "overseas media",
        "western countries", "us european", "western world", "asian media", "asia news",
        "east asian media", "asian perspective", "domestic media", "chinese media",
        "local media", "european media", "eu media", "europe news", "middle east media",
        "arab media", "middle east news", "latin american media", "hispanic media",
        "report", "coverage", "reaction", "response", "collect", "search", "find",
    ],
}

# 常见停用词 - 这些词在关键词验证时应该被过滤掉
STOP_WORDS = {
    "zh": [
        # 时间相关
        "年", "月", "日", "时", "分", "秒",
        # 数字
        "��", "二", "三", "四", "五", "六", "七", "八", "九", "十",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        "2025", "2024", "2023", "2022", "2021", "2020",
        "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
        # 量词
        "个", "位", "次", "种", "类", "批", "群",
        # 连词
        "和", "与", "或", "及", "以及", "还有", "包括",
        # 助词
        "的", "了", "是", "在", "对", "这", "那", "些",
        # 虚词
        "请", "关于", "有关", "有关", "相关", "进行",
    ],
    "en": [
        "year", "month", "day", "hour", "minute", "second",
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        "2025", "2024", "2023", "2022", "2021", "2020",
        "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
        "and", "or", "for", "with", "from", "about", "related", "please",
    ],
}


class ValidatorNode:
    """交叉验证节点

    验证策略:
    1. 相关性验证: 结果内容是否与搜索主题相关（v4.6.0新增）
    2. 多源验证: 相同事实被多个独立来源报道
    3. 权威验证: 官方来源确认
    4. 时间验证: 发布时间合理性
    5. 内容一致性: 关键信息是否一致
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

            # v4.6.0: 提取搜索主题关键词用于相关性验证
            query = state.get("query", "")
            analysis = state.get("analysis", {})
            event_keywords = self._extract_event_keywords(query, analysis)

            logger.info(
                f"[user:{user_id}] Relevance validation with event keywords: {event_keywords[:3] if event_keywords else []}"
            )

            # v4.6.0: 相关性验证 - 过滤与主题不相关的结果
            relevance_filtered_results = self._filter_by_relevance(
                results,
                event_keywords,
                user_id
            )

            logger.info(
                f"[user:{user_id}] Relevance filter: {len(results)} -> {len(relevance_filtered_results)} results"
            )

            # 执行验证（使用过滤后的结果）
            validation_scores = self._validate_results(relevance_filtered_results)

            # 更新结果分数
            updated_results = self._apply_validation_scores(relevance_filtered_results, validation_scores)

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
                "filtered_count": len(results) - len(relevance_filtered_results),  # v4.6.0: 记录过滤数量
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

        # 重新排���
        results.sort(key=lambda x: x.final_score, reverse=True)

        return results

    def _extract_event_keywords(self, query: str, analysis: Dict[str, Any]) -> Set[str]:
        """提取事件核心关键词 (v4.6.0)

        从查询和分析结果中提取事件相关的关键词，排除用户意图词。
        这些关键词用于验证搜索结果是否与主题相关。

        Args:
            query: 原始查询
            analysis: Claude 分析结果

        Returns:
            事件关键词集合
        """
        keywords = set()

        # 1. 从 analysis 中提取关键词
        analysis_keywords = analysis.get("keywords", [])
        analysis_keywords_en = analysis.get("keywords_en", [])

        # 添加分析的关键词
        keywords.update(analysis_keywords)
        keywords.update(analysis_keywords_en)

        # 2. 从 keyword_combinations 中提取关键词
        keyword_combinations = analysis.get("keyword_combinations", [])
        for combo in keyword_combinations:
            query_text = combo.get("query", "")
            # 简单的词提取（按空格分割）
            words = query_text.split()
            for word in words:
                word = word.lower()
                # 过滤掉意图词
                if self._is_intent_word(word):
                    continue
                # 过滤掉常见停用词
                if word in ["the", "a", "an", "of", "in", "on", "at", "by", "for", "with", "from"]:
                    continue
                keywords.add(word)

        # 3. 从查询中提取（过滤意图词和停用词后）
        # v4.6.0: 使用 STOP_WORDS 来过滤掉所有停用词和意图词
        filtered_query = self._filter_intent_words(query)

        # 从 analysis 中提取关键词（优先级最高）
        keywords = set()
        analysis_keywords = analysis.get("keywords", [])
        analysis_keywords_en = analysis.get("keywords_en", [])
        keywords.update(analysis_keywords)
        keywords.update(analysis_keywords_en)

        # 4. 检查是否包含任何事件关键词，如果没有，使用降级逻辑
        if not keywords:
            # 使用 STOP_WORDS 过滤后的查询分词
            words = []
            for word in filtered_query.split():
                word_lower = word.lower()
                # 过滤停用词（包括中英文）
                stop_words = STOP_WORDS.get("zh", []) + STOP_WORDS.get("en", [])
                if word_lower in stop_words or len(word) < 2:
                    continue
                keywords.add(word)
        else:
            # 从 keyword_combinations 中提取关键词
            keyword_combinations = analysis.get("keyword_combinations", [])
            for combo in keyword_combinations:
                query_text = combo.get("query", "")
                if query_text:
                    # 分割并过滤停用词
                    words = []
                    for word in query_text.split():
                        word_lower = word.lower()
                        stop_words = STOP_WORDS.get("zh", []) + STOP_WORDS.get("en", [])
                        if word_lower in stop_words or len(word) < 2:
                            continue
                        keywords.add(word)

        return keywords

    def _is_intent_word(self, word: str) -> bool:
        """检查是否是意图词

        Args:
            word: 要检查的词

        Returns:
            如果是意图词返回 True
        """
        word_lower = word.lower()

        # 检查中文意图词
        for zh_intent in INTENT_WORDS_TO_FILTER["zh"]:
            if zh_intent in word_lower or word_lower in zh_intent:
                return True

        # 检查英文意图词
        for en_intent in INTENT_WORDS_TO_FILTER["en"]:
            if word_lower == en_intent.lower():
                return True

        return False

    def _filter_intent_words(self, text: str) -> str:
        """过滤掉文本中的意图词

        Args:
            text: 原始文本

        Returns:
            过滤后的文本
        """
        result = text
        for intent_word in INTENT_WORDS_TO_FILTER["zh"]:
            result = result.replace(intent_word, " ")
        for intent_word in INTENT_WORDS_TO_FILTER["en"]:
            result = result.replace(intent_word, " ")

        # 移除常见虚词
        for particle in ["对", "的", "关于", "有关", "搜索", "查找", "检索", "整理", "反应"]:
            result = result.replace(particle, " ")

        return result

    def _filter_by_relevance(
        self,
        results: List[SearchResult],
        event_keywords: Set[str],
        user_id: str,
    ) -> List[SearchResult]:
        """按相关性过滤结果 (v4.6.0)

        过滤掉与搜索主题不相关的结果。
        相关性判断标准：
        1. 标题或内容中包含至少一个事件关键词
        2. 标题长度合理（不是单字符或过短）
        3. 不包含大量无关内容

        Args:
            results: 搜索结果列表
            event_keywords: 事件关键词集合
            user_id: 用户ID（用于日志）

        Returns:
            过滤后的结果列表
        """
        if not event_keywords:
            logger.warning(f"[user:{user_id}] No event keywords, skipping relevance filter")
            return results

        filtered_results = []
        removed_count = 0

        for result in results:
            title = result.title or ""
            snippet = result.snippet or ""
            content = result.markdown_content or ""

            # 组合所有文本用于检查
            combined_text = f"{title} {snippet} {content}".lower()

            # 检查标题长度 - 过滤过短或过长的标题
            if len(title) < 5:
                logger.debug(f"[user:{user_id}] Filtered: title too short: {title[:50]}")
                removed_count += 1
                continue

            # 检查是否包含任何事件关键词
            has_keyword = any(
                keyword.lower() in combined_text
                for keyword in event_keywords
            )

            if not has_keyword:
                logger.debug(
                    f"[user:{user_id}] Filtered: no keyword match. "
                    f"title={title[:50]}, keywords={list(event_keywords)[:3]}"
                )
                removed_count += 1
                continue

            # 检查是否只包含意图词（完全没有事件关键词）
            # 如果标题只包含意图词但没有实际事件描述，过滤掉
            title_lower = title.lower()

            # 收集所有意图词用于检查
            all_intent_words = INTENT_WORDS_TO_FILTER["zh"] + INTENT_WORDS_TO_FILTER["en"]

            # 检查是否有非意图词的实质内容
            words = [w for w in title_lower.split() if w not in all_intent_words and len(w) > 1]

            intent_only = not words or len(" ".join(words)) <= 2

            if intent_only:
                logger.debug(
                    f"[user:{user_id}] Filtered: title contains only intent words: {title[:50]}"
                )
                removed_count += 1
                continue

            filtered_results.append(result)

        logger.info(
            f"[user:{user_id}] Relevance filter: {len(results)} -> {len(filtered_results)} "
            f"(removed {removed_count})"
        )

        return filtered_results
