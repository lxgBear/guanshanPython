"""重试搜索节点 (v4.17.0)

当结果数量低于阈值时，生成补充搜索配置并继续搜索。

v4.17.0 更新：
- 检查结果数量是否低于阈值
- 利用 supplementary_notes 中的 search_tips 和 alternative_spellings
- 生成补充搜索配置
- 最多重试 2 次
"""

import json
import logging
from typing import Dict, Any, List, Optional

from ..state import SearchState
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


# ============================================================================
# 常量
# ============================================================================

# 最小结果阈值 - 低于此值时触发重试
MIN_RESULTS_THRESHOLD = 30

# 最大重试次数
MAX_RETRY_COUNT = 2


# ============================================================================
# RetrySearchNode
# ============================================================================

class RetrySearchNode:
    """重试搜索节点 (v4.17.0)

    当搜索结果数量低于阈值时，生成补充搜索配置。

    输入字段：
    - aggregated_results: List[Dict] - 当前搜索结果
    - keyword_generation: Dict - 关键词生成结果
    - search_retry_count: int - 当前重试次数
    - firecrawl_search_config: List[Dict] - 当前搜索配置

    输出字段：
    - firecrawl_search_config: List[Dict] - 扩展后的搜索配置列表
    - search_retry_count: int - 更新后的重试次数
    - should_retry: bool - 是否需要重试
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
    ):
        """初始化重试搜索节点

        Args:
            config: LangGraph 搜索配置
        """
        self.config = config or LangGraphSearchConfig()

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """检查是否需要重试并生成补充搜索配置

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        results = state.get("aggregated_results", [])
        retry_count = state.get("search_retry_count", 0)
        current_configs = state.get("firecrawl_search_config", [])
        keyword_generation = state.get("keyword_generation", {})

        logger.info(
            f"[user:{user_id}] RetrySearch: "
            f"results={len(results)}, retry_count={retry_count}"
        )

        # 检查是否需要重试
        should_retry = (
            len(results) < MIN_RESULTS_THRESHOLD and
            retry_count < MAX_RETRY_COUNT
        )

        if should_retry:
            logger.info(
                f"[user:{user_id}] Result count {len(results)} < {MIN_RESULTS_THRESHOLD}, "
                f"generating retry search configs (attempt {retry_count + 1})"
            )

            # 生成补充搜索配置
            new_configs = self._generate_retry_configs(
                keyword_generation,
                retry_count,
                user_id,
            )

            # 合并到现有配置列表
            merged_configs = current_configs + new_configs

            # 限制最大配置数量
            max_configs = getattr(self.config, "max_search_configs", 20)
            if len(merged_configs) > max_configs:
                merged_configs = merged_configs[:max_configs]
                logger.info(
                    f"[user:{user_id}] Limiting configs to {max_configs}"
                )

            return {
                "firecrawl_search_config": merged_configs,
                "search_retry_count": retry_count + 1,
                "should_retry": True,
                "status": "running",
            }
        else:
            # 不需要重试
            if len(results) < MIN_RESULTS_THRESHOLD:
                logger.warning(
                    f"[user:{user_id}] Reached max retries ({MAX_RETRY_COUNT}) "
                    f"but still only have {len(results)} results"
                )
            else:
                logger.info(
                    f"[user:{user_id}] Sufficient results ({len(results)}), "
                    f"no retry needed"
                )

            return {
                "should_retry": False,
                "status": "running",
            }

    def _generate_retry_configs(
        self,
        keyword_generation: Dict[str, Any],
        retry_count: int,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """生成重试搜索配置

        利用 supplementary_notes 中的 search_tips 和 alternative_spellings。

        Args:
            keyword_generation: 关键词生成结果
            retry_count: 当前重试次数
            user_id: 用户ID

        Returns:
            新增的搜索配置列表
        """
        new_configs = []

        # 提取 supplementary_notes
        supplementary_notes = keyword_generation.get("supplementary_notes", {})

        # 1. 使用 search_tips 生成补充搜索
        search_tips = supplementary_notes.get("search_tips", [])
        if search_tips:
            for tip in search_tips[:3]:
                # 限制每批 3 个建议
                new_configs.append({
                    "query": tip,
                    "limit": 15,
                    "tier": "retry_search_tip",
                })
            logger.debug(
                f"[user:{user_id}] Generated {len(search_tips[:3])} configs from search_tips"
            )

        # 2. 使用 alternative_spellings 生成补充搜索
        alternative_spellings = supplementary_notes.get("alternative_spellings", {})
        if alternative_spellings:
            # 将拼写变体作为搜索查询
            for word, variants in alternative_spellings.items():
                if isinstance(variants, list):
                    for variant in variants[:2]:  # 每个变体最多 2 个
                        new_configs.append({
                            "query": variant,
                            "limit": 15,
                            "tier": "retry_alternative_spelling",
                        })
            logger.debug(
                f"[user:{user_id}] Generated {len(new_configs)} configs from alternative_spellings"
            )

        # 3. 如果没有补充信息，基于 tier_3 关键词生成重试
        if not new_configs:
            tiered_keywords = keyword_generation.get("tiered_keywords", {})
            tier_3_keywords = tiered_keywords.get("tier_3", [])

            if tier_3_keywords:
                for keyword in tier_3_keywords[:5]:
                    new_configs.append({
                        "query": keyword,
                        "limit": 15,
                        "tier": "retry_tier_3",
                    })
                logger.debug(
                    f"[user:{user_id}] Generated {len(tier_3_keywords[:5])} configs from tier_3"
                )

        # 限制重试配置数量，避免过多 API 调用
        max_retry_configs = 5
        return new_configs[:max_retry_configs]


# ============================================================================
# 工厂函数
# ============================================================================

def create_retry_search_node(
    config: Optional[LangGraphSearchConfig] = None,
) -> RetrySearchNode:
    """创建重试搜索节点的工厂函数

    Args:
        config: LangGraph 搜索配置

    Returns:
        RetrySearchNode 实例
    """
    return RetrySearchNode(
        config=config,
    )
