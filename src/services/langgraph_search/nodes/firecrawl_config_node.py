"""Firecrawl 配置生成节点 (v4.14.0)

Step 2: 使用 Claude LLM 根据关键词生成 Firecrawl API 搜索配置。

职责：
1. 读取 keyword_generation 中的分层关键词 (tiered_keywords)
2. 读取目标语言列表 (target_languages)
3. 使用 Claude 智能生成 Firecrawl 搜索配置列表
4. 设置时间范围、结果数量等参数

输入：keyword_generation 字段
输出：firecrawl_search_config 字段

v4.14.0 更新：
- 简化配置：移除 location 和 purpose 字段
- 只保留 query, limit, tier 核心字段

v4.12.0 更新：
- 使用 Claude LLM 替代规则化处理
- 更智能的关键词组合和语言选择
"""

import json
import logging
from typing import Dict, Any, List, Optional

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from ..state import SearchState
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


# ============================================================================
# 配置常量
# ============================================================================

# 最大搜索配置数量（防止过多 API 调用）
MAX_CONFIGS = 10  # v4.17.0: 将使用配置中的 max_search_configs


# ============================================================================
# LLM Prompt - Firecrawl 配置生成
# ============================================================================

FIRECRAWL_CONFIG_PROMPT = """Generate Firecrawl search configurations as a JSON array.

User Query: {query}

Tiered Keywords: {tiered_keywords}

Target Languages: {target_languages}

Time Range: {time_range}

Rules:
1. Use keywords directly from tiered_keywords
2. Set limit based on tier: tier_1=20, tier_2=15, tier_3=10
3. Generate ONE config for EACH keyword (tier_1 first, then tier_2, then tier_3)
4. Maximum total configs: {max_configs}

Output format (JSON array only, no markdown):
[
  {{
    "query": "exact keyword from tiered_keywords",
    "limit": 20 or 15 or 10,
    "tier": "tier_1" or "tier_2" or "tier_3"
  }}
]"""


# ============================================================================
# FirecrawlConfigNode
# ============================================================================

class FirecrawlConfigNode:
    """Firecrawl 配置生成节点 (v4.14.0)

    Step 2: 使用 Claude LLM 根据关键词生成 Firecrawl 搜索配置。

    输入：keyword_generation 字段（来自 KeywordGeneratorNode）
    输出：firecrawl_search_config 列表 (query, limit, tier)
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Any] = None,
    ):
        """初始化配置生成节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()

        if anthropic_client:
            self.client = anthropic_client
        elif HAS_ANTHROPIC:
            api_key = self.config.claude_api_key
            base_url = self.config.claude_base_url

            if not api_key:
                logger.warning("Anthropic API key not configured, FirecrawlConfigNode will use fallback")
                self.client = None
            else:
                if base_url and base_url != "https://api.anthropic.com":
                    self.client = Anthropic(api_key=api_key, base_url=base_url)
                    logger.info(f"FirecrawlConfigNode using custom base_url: {base_url}")
                else:
                    self.client = Anthropic(api_key=api_key)
        else:
            self.client = None
            logger.warning("Anthropic client not available, FirecrawlConfigNode will use fallback")

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """生成 Firecrawl 搜索配置

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典，包含 firecrawl_search_config 字段
        """
        user_id = state.get("user_id", "")
        query = state.get("query", "")

        # 获取关键词生成结果
        keyword_generation = state.get("keyword_generation", {})

        if not keyword_generation:
            logger.warning(f"[user:{user_id}] No keyword_generation found, using fallback")
            return self._get_fallback_config(query)

        try:
            logger.info(f"[user:{user_id}] FirecrawlConfigNode: generating search configs with Claude...")
            # v4.17.0: 添加日志刷新
            logger.handlers[0].flush() if logger.handlers else None
            logger.info(f"[user:{user_id}] keyword_generation keys: {list(keyword_generation.keys())}")
            logger.handlers[0].flush() if logger.handlers else None
            tiered_keywords = keyword_generation.get("tiered_keywords", {})
            logger.info(f"[user:{user_id}] tiered_keywords tier_1 count: {len(tiered_keywords.get('tier_1', []))}")
            logger.info(f"[user:{user_id}] tiered_keywords tier_2 count: {len(tiered_keywords.get('tier_2', []))}")
            logger.info(f"[user:{user_id}] tiered_keywords tier_3 count: {len(tiered_keywords.get('tier_3', []))}")

            # 使用 LLM 生成配置
            if self.client:
                configs = self._generate_with_llm(query, keyword_generation, user_id)
            else:
                logger.warning(f"[user:{user_id}] LLM client not available, using fallback")
                configs = self._generate_fallback_configs(keyword_generation, query)

            # 添加 scrapeOptions
            # v4.17.0: 添加日志查看 configs
            logger.info(f"[user:{user_id}] Before scrapeOptions: configs={configs}, type={type(configs)}")
            for cfg in configs:
                cfg["scrapeOptions"] = {
                    "formats": ["markdown", "html"],
                    "onlyMainContent": True,
                    "blockAds": True,
                }

            logger.info(
                f"[user:{user_id}] FirecrawlConfigNode: generated {len(configs)} configs"
            )

            return {
                "firecrawl_search_config": configs,
                "status": "running",
            }

        except Exception as e:
            logger.error(f"[user:{user_id}] FirecrawlConfigNode failed: {e}")
            return self._get_fallback_config(query)

    def _generate_with_llm(
        self,
        query: str,
        keyword_generation: Dict[str, Any],
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """使用 Claude LLM 生成配置

        Args:
            query: 原始查询
            keyword_generation: 关键词生成结果
            user_id: 用户ID

        Returns:
            Firecrawl 配置列表
        """
        # 提取信息
        tiered_keywords = keyword_generation.get("tiered_keywords", {})
        target_languages = keyword_generation.get("target_languages", ["en"])
        time_range = keyword_generation.get("time_range", {})
        search_directions = keyword_generation.get("search_directions", [])

        # 构建 prompt
        prompt = FIRECRAWL_CONFIG_PROMPT.format(
            query=query,
            tiered_keywords=json.dumps(tiered_keywords, ensure_ascii=False, indent=2),
            target_languages=json.dumps(target_languages, ensure_ascii=False),
            time_range=json.dumps(time_range, ensure_ascii=False, indent=2),
            search_directions=json.dumps(search_directions, ensure_ascii=False, indent=2),
            max_configs=getattr(self.config, "max_search_configs", 20),
        )

        try:
            response = self.client.messages.create(
                model=getattr(self.config, "claude_model", "claude-sonnet-4-20250514"),
                max_tokens=getattr(self.config, "claude_max_tokens", 2000),
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # 清理可能的 markdown 标记
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # v4.17.0: 添加调试日志 - JSON 解析前
            logger.info(f"[user:{user_id}] LLM response cleaned (first 800 chars): {response_text[:800]}")

            # 解析 JSON
            configs = json.loads(response_text)

            # 验证和清理配置
            valid_configs = []
            for cfg in configs:
                if isinstance(cfg, dict) and cfg.get("query"):
                    # v4.14.0: 简化配置，只保留 query, limit, tier
                    # v4.17.0: 使用 tier 对应的配置限制，而非硬编码 20
                    tier = cfg.get("tier", "tier_1")
                    tier_limits = getattr(self.config, "tier_results_limit", {"tier_1": 20, "tier_2": 15, "tier_3": 10})
                    max_limit_for_tier = tier_limits.get(tier, 20)
                    valid_config = {
                        "query": cfg["query"],
                        "limit": min(cfg.get("limit", 10), max_limit_for_tier),
                        "tier": tier,
                    }
                    valid_configs.append(valid_config)

            # 添加时间范围
            # v4.17.1: 暂时禁用 tbs 参数以避免 Firecrawl API 日期格式错误
            # tbs = time_range.get("tbs", "")
            # if tbs:
            #     for cfg in valid_configs:
            #         cfg["tbs"] = tbs

            logger.info(
                f"[user:{user_id}] LLM generated {len(valid_configs)} valid configs"
            )

            # v4.17.0: 使用配置中的 max_search_configs 替代硬编码的 MAX_CONFIGS
            max_configs = getattr(self.config, "max_search_configs", 20)
            return valid_configs[:max_configs]

        except json.JSONDecodeError as e:
            logger.warning(f"[user:{user_id}] JSON parse failed: {e}")
            # 尝试提取 JSON 数组
            import re
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                try:
                    # v4.17.0: 使��配置中的 max_search_configs
                    max_configs = getattr(self.config, "max_search_configs", 20)
                    return json.loads(json_match.group())[:max_configs]
                except:
                    pass
            return self._generate_fallback_configs(keyword_generation, query)

        except Exception as e:
            # v4.17.0: 添加详细的错误日志
            import traceback
            logger.error(f"[user:{user_id}] LLM call failed: {type(e).__name__}: {e}")
            logger.error(f"[user:{user_id}] Response text (first 200 chars): {response_text[:200] if 'response_text' in locals() else 'N/A'}")
            logger.debug(f"[user:{user_id}] Traceback: {traceback.format_exc()}")
            return self._generate_fallback_configs(keyword_generation, query)

    def _generate_fallback_configs(
        self,
        keyword_generation: Dict[str, Any],
        query: str,
    ) -> List[Dict[str, Any]]:
        """生成降级配置（规则化处理）

        Args:
            keyword_generation: 关键词生成结果
            query: 原始查询

        Returns:
            Firecrawl 配置列表
        """
        configs = []
        tiered_keywords = keyword_generation.get("tiered_keywords", {})
        target_languages = keyword_generation.get("target_languages", ["en"])
        time_range = keyword_generation.get("time_range", {})
        tbs = time_range.get("tbs", "")

        # 简单规则：直接使用关键词
        # v4.17.0: 使用配置中的 tier_results_limit，更新默认值为 20/15/10
        tier_limits = getattr(self.config, "tier_results_limit", {"tier_1": 20, "tier_2": 15, "tier_3": 10})
        max_configs = getattr(self.config, "max_search_configs", 20)

        for tier, limit in tier_limits.items():
            keywords = tiered_keywords.get(tier, [])
            # v4.17.0: 使用 tier 限制作为关键词数量上限
            # tier_1 取前 20 个，tier_2 取前 15 个，tier_3 取前 10 个
            max_keywords_for_tier = min(len(keywords), limit)
            for keyword in keywords[:max_keywords_for_tier]:
                # v4.14.0: 简化配置，只保留 query, limit, tier
                # v4.14.0: 简化配置，只保留 query, limit, tier
                cfg = {
                    "query": keyword,
                    "limit": limit,
                    "tier": tier,
                }
                # v4.17.1: 暂时禁用 tbs 参数
                # if tbs:
                #     cfg["tbs"] = tbs
                configs.append(cfg)

        return configs[:max_configs]

    def _detect_language(self, text: str, target_languages: List[str]) -> str:
        """简单的语言检测

        Args:
            text: 文本
            target_languages: 目标语言列表

        Returns:
            语言代码
        """
        # 检测中文字符
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_chars > len(text) * 0.3:
            return "zh"

        # 检测印地语字符
        hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097f')
        if hindi_chars > len(text) * 0.3:
            return "hi"

        # 默认英文
        return target_languages[0] if target_languages else "en"

    def _get_fallback_config(self, query: str) -> Dict[str, Any]:
        """获取降级配置

        Args:
            query: 原始查询

        Returns:
            状态更新字典
        """
        return {
            "firecrawl_search_config": [
                {
                    "query": query,
                    "limit": 20,
                    "tier": "fallback",
                    "scrapeOptions": {
                        "formats": ["markdown", "html"],
                        "onlyMainContent": True,
                    }
                }
            ],
            "status": "running",
        }


# ============================================================================
# 工厂函数
# ============================================================================

def create_firecrawl_config_node(
    config: Optional[LangGraphSearchConfig] = None,
    anthropic_client: Optional[Any] = None,
) -> FirecrawlConfigNode:
    """创建 Firecrawl 配置生成节点的工厂函数

    Args:
        config: LangGraph 搜索配置
        anthropic_client: Anthropic 客户端

    Returns:
        FirecrawlConfigNode 实例
    """
    return FirecrawlConfigNode(
        config=config,
        anthropic_client=anthropic_client,
    )
