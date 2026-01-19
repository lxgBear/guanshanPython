"""意图筛选节点 (v4.16.1)

在保存到数据库前进行意图匹配过滤。

处理流程：
1. URL 去重（先执行）
2. Claude LLM 意图匹配分析（分批处理，每批 10 个）
3. 计算 intent_score 分数（用于排序）
4. 结果分类：保留 / 降级 / 丢弃

判断逻辑（3步法）：
- Step 1: 回顾原始意图（从 keyword_generation 中获取）
- Step 2: 核心要素匹配（地点、事件、时间、来源）
- Step 3: 做出判断（✅ 保留 / ⚠️ 降级 / ❌ 丢弃）

intent_score 计算：
- keep: 0.8 + (匹配要素数/4) * 0.2 = 0.8~1.0
- downgrade: 0.4 + (匹配要素数/4) * 0.2 = 0.4~0.6
- 无 LLM 时: 默认 0.7

v4.16.1: 分批处理，避免 LLM 响应截断
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from ..state import SearchState
from ..config import LangGraphSearchConfig

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Prompt - 意图筛选
# ============================================================================

INTENT_FILTER_PROMPT = """你是一个专业的搜索结果筛选专家。

请根据用户的原始查询意图，对搜索结果进行相关性判断。

## 原始查询
{query}

## 意图分析（来自关键词生成）
{intent_summary}

## 待筛选结果
{results_json}

## 判断流程（3步法）

### Step 1: 回顾原始意图
从意图分析中提取核心需求：
- 目标信息源类型是什么？
- 需要什么内容深度？
- 有什么时间/地点/事件约束？

### Step 2: 核心要素匹配
对每个结果检查：
- **地点匹配**: 结果涉及的地点是否与查询相关？
- **事件匹配**: 结果描述的事件是否与查询相关？
- **时间匹配**: 结果的时间范围是否符合要求？
- **来源匹配**: 结果来源是否符合目标信息源类型？

### Step 3: 做出判断
根据匹配程度决定：
- ✅ **保留 (keep)**: 核心要素完全匹配或高度相关
- ⚠️ **降级 (downgrade)**: 部分匹配，有参考价值但不是核心结果
- ❌ **丢弃 (discard)**: 完全无关或严重偏离意图

## 偏离类型说明
- **地点偏离**: 查询某地事件，结果是其他地方的
- **事件偏离**: 查询某事件，结果是不相关事件
- **时间偏离**: 查询特定时间，结果是其他时间的
- **来源偏离**: 查询特定来源，结果是其他类型来源

## 输出格式

请以 JSON 格式返回（不要使用 markdown 代码块）:
{{
  "analysis_summary": "整体分析概述",
  "results": [
    {{
      "url": "结果URL",
      "decision": "keep|downgrade|discard",
      "confidence": 0.95,
      "matching": {{
        "location": true,
        "event": true,
        "time": true,
        "source": true
      }},
      "reason": "判断理由（简短）"
    }}
  ],
  "statistics": {{
    "total": 10,
    "keep": 5,
    "downgrade": 3,
    "discard": 2
  }}
}}

只返回 JSON，不要其他内容。"""


# ============================================================================
# IntentFilterNode
# ============================================================================

class IntentFilterNode:
    """意图筛选节点 (v4.16.0)

    处理流程：
    1. URL 去重（先执行）
    2. Claude LLM 意图匹配分析（后执行）
    3. 计算 intent_score 并添加到每个结果
    4. 过滤掉 discard 的结果

    输入字段：
    - aggregated_results: List[Dict] - 搜索结果
    - query: str - 原始查询
    - keyword_generation: Dict - 关键词生成结果（含意图分析）

    输出字段：
    - aggregated_results: List[Dict] - 过滤后的结果，每个结果包含：
        - intent_score: float (0.0-1.0) 用于排序
        - intent_match: str (keep/downgrade)
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Any] = None,
    ):
        """初始化意图筛选节点

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
                logger.warning("Anthropic API key not configured, IntentFilterNode will skip LLM filtering")
                self.client = None
            else:
                if base_url and base_url != "https://api.anthropic.com":
                    self.client = Anthropic(api_key=api_key, base_url=base_url)
                    logger.info(f"IntentFilter using custom base_url: {base_url}")
                else:
                    self.client = Anthropic(api_key=api_key)
        else:
            self.client = None
            logger.warning("Anthropic client not available, IntentFilterNode will skip LLM filtering")

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行意图筛选

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        user_id = state.get("user_id", "")
        query = state.get("query", "")
        results = state.get("aggregated_results", [])
        keyword_generation = state.get("keyword_generation", {})

        logger.info(
            f"[user:{user_id}] IntentFilter starting: "
            f"{len(results)} results to process"
        )

        # Step 1: URL 去重（先执行）
        deduplicated_results, dedup_stats = self._deduplicate_by_url(results, user_id)

        logger.info(
            f"[user:{user_id}] URL deduplication: "
            f"{len(results)} → {len(deduplicated_results)} "
            f"(removed {dedup_stats['duplicates_removed']})"
        )

        # Step 2: Claude LLM 意图匹配（后执行）
        if self.client and deduplicated_results:
            filtered_results, filter_stats = self._filter_with_llm(
                deduplicated_results,
                query,
                keyword_generation,
                user_id,
            )
        else:
            # 无 LLM 时跳过筛选，给所有结果添加默认分数
            filtered_results = []
            for result in deduplicated_results:
                result["intent_score"] = 0.7  # 默认分数
                result["intent_match"] = "keep"
                filtered_results.append(result)
            filter_stats = {
                "total": len(deduplicated_results),
                "keep": len(deduplicated_results),
                "downgrade": 0,
                "discard": 0,
            }
            logger.info(f"[user:{user_id}] LLM not available, using default intent_score=0.7")

        logger.info(
            f"[user:{user_id}] IntentFilter complete: "
            f"keep={filter_stats.get('keep', 0)}, "
            f"downgrade={filter_stats.get('downgrade', 0)}, "
            f"discard={filter_stats.get('discard', 0)}"
        )

        return {
            # 更新结果列表（供 OutputNode 使用）
            # 每个结果包含 intent_score 字段用于排序
            "aggregated_results": filtered_results,
            # v4.17.1: 保留统计信息
            "statistics": {
                **state.get("statistics", {}),
                "intent_filter": filter_stats,
            },
            "status": "running",
        }

    def _deduplicate_by_url(
        self,
        results: List[Dict[str, Any]],
        user_id: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """URL 去重

        保留第一个出现的结果，移除后续重复项。

        Args:
            results: 原始结果列表
            user_id: 用户ID

        Returns:
            (去重后的结果列表, 统计信息)
        """
        seen_urls = set()
        unique_results = []
        duplicates = []

        for result in results:
            url = result.get("url", "")
            if not url:
                # 无 URL 的结果保留
                unique_results.append(result)
                continue

            # 标准化 URL（移除尾部斜杠和查询参数用于比较）
            normalized_url = self._normalize_url(url)

            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_results.append(result)
            else:
                duplicates.append({
                    "url": url,
                    "title": result.get("title", ""),
                })

        stats = {
            "original_count": len(results),
            "unique_count": len(unique_results),
            "duplicates_removed": len(duplicates),
            "duplicate_urls": duplicates[:10],  # 只记录前10个
        }

        return unique_results, stats

    def _normalize_url(self, url: str) -> str:
        """标准化 URL 用于去重比较（v4.17.0 改进）

        保留重要查询参数（如 article_id），移除跟踪参数。

        Args:
            url: 原始 URL

        Returns:
            标准化后的 URL
        """
        if not url:
            return ""

        # 移除协议前缀
        url = url.lower()
        for prefix in ["https://", "http://", "www."]:
            if url.startswith(prefix):
                url = url[len(prefix):]

        # 移除尾部斜杠
        url = url.rstrip("/")

        # v4.17.0: 改进参数处理
        if "?" in url:
            base, params = url.split("?", 1)
            # 分离查询参数
            param_list = params.split("&")
            # 保留重要的参数（如 id, article, p 等）
            important_params = ["id", "article", "p", "page", "story", "post"]
            filtered_params = []
            for param in param_list:
                if "=" in param:
                    key, _ = param.split("=", 1)
                    key = key.lower()
                    if any(important in key for important in important_params):
                        filtered_params.append(param)

            if filtered_params:
                url = base + "?" + "&".join(filtered_params)
            else:
                url = base
        else:
            # 移除常见的跟踪路径
            for tracking_path in ["/ref", "/track", "/click", "/share", "?utm_", "?fbclid=", "?gclid="]:
                if tracking_path in url:
                    url = url.split(tracking_path)[0]
                    break

        return url

    def _filter_with_llm(
        self,
        results: List[Dict[str, Any]],
        query: str,
        keyword_generation: Dict[str, Any],
        user_id: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """使用 Claude LLM 进行意图匹配筛选（分批处理）

        Args:
            results: 去重后的结果列表
            query: 原始查询
            keyword_generation: 关键词生成结果
            user_id: 用户ID

        Returns:
            (筛选后的结果列表, 统计信息)
        """
        # 构建意图摘要
        intent_summary = self._build_intent_summary(keyword_generation)

        # v4.17.0: 使用配置化的批次大小
        BATCH_SIZE = 20  # 使用配置中的 intent_filter_batch_size
        all_decisions = {}
        total_batches = (len(results) + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"[user:{user_id}] Processing {len(results)} results in {total_batches} batches")

        for batch_idx in range(total_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(results))
            batch_results = results[start_idx:end_idx]

            # 准备批次数据（精简版，减少 token）
            results_for_llm = []
            for r in batch_results:
                results_for_llm.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", "")[:200] if r.get("description") else "",
                    "source": r.get("source", ""),
                })

            # 构建 prompt
            prompt = INTENT_FILTER_PROMPT.format(
                query=query,
                intent_summary=intent_summary,
                results_json=json.dumps(results_for_llm, ensure_ascii=False, indent=2),
            )

            try:
                response = self.client.messages.create(
                    model=getattr(self.config, "claude_model", "claude-sonnet-4-20250514"),
                    max_tokens=2000,  # 每批只需要较少 token
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

                # 解析 LLM 响应
                llm_result = json.loads(response_text)

                # 收集该批次的决策
                for item in llm_result.get("results", []):
                    url = item.get("url", "")
                    if url:
                        all_decisions[url] = {
                            "decision": item.get("decision", "keep"),
                            "confidence": item.get("confidence", 0.5),
                            "matching": item.get("matching", {}),
                        }

                logger.debug(f"[user:{user_id}] Batch {batch_idx+1}/{total_batches} processed: {len(batch_results)} results")

            except json.JSONDecodeError as e:
                logger.warning(f"[user:{user_id}] Batch {batch_idx+1} JSON parse failed: {e}")
                # 该批次降级：默认保留
                for r in batch_results:
                    url = r.get("url", "")
                    if url and url not in all_decisions:
                        all_decisions[url] = {"decision": "keep", "matching": {}}
            except Exception as e:
                logger.error(f"[user:{user_id}] Batch {batch_idx+1} LLM call failed: {e}")
                # 该批次降级：默认保留
                for r in batch_results:
                    url = r.get("url", "")
                    if url and url not in all_decisions:
                        all_decisions[url] = {"decision": "keep", "matching": {}}

        # 应用所有决策
        return self._apply_filter_decisions_from_map(results, all_decisions, user_id)

    def _build_intent_summary(self, keyword_generation: Dict[str, Any]) -> str:
        """构建意图摘要

        Args:
            keyword_generation: 关键词生成结果

        Returns:
            意图摘要字符串
        """
        if not keyword_generation:
            return "无意图分析数据"

        parts = []

        # 意图
        intent = keyword_generation.get("intent", {})
        if intent:
            parts.append(f"信息源类型: {intent.get('source_type', '未知')}")
            parts.append(f"内容深度: {intent.get('content_depth', '未知')}")
            parts.append(f"时间要求: {intent.get('time_requirement', '未知')}")

        # 事件
        event = keyword_generation.get("event", {})
        if event:
            parts.append(f"事件类型: {event.get('type', '未知')}")
            parts.append(f"事件时间: {event.get('time', '未知')}")
            parts.append(f"事件地点: {event.get('location', '未知')}")
            if event.get("parties"):
                parts.append(f"涉及方: {', '.join(event.get('parties', []))}")

        # 时间范围
        time_range = keyword_generation.get("time_range", {})
        if time_range:
            parts.append(f"搜索时间范围: {time_range.get('type', '未知')}")

        return "\n".join(parts) if parts else "无意图分析数据"

    def _apply_filter_decisions_from_map(
        self,
        results: List[Dict[str, Any]],
        decisions: Dict[str, Dict[str, Any]],
        user_id: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """应用 LLM 的筛选决策（从决策映射）

        Args:
            results: 原始结果列表
            decisions: URL → 决策映射
            user_id: 用户ID

        Returns:
            (筛选后的结果列表, 统计信息)
        """
        # 应用决策
        filtered_results = []
        stats = {
            "total": len(results),
            "keep": 0,
            "downgrade": 0,
            "discard": 0,
        }

        for result in results:
            url = result.get("url", "")
            decision_info = decisions.get(url, {"decision": "keep", "matching": {}})
            decision = decision_info.get("decision", "keep")
            matching = decision_info.get("matching", {})

            # 计算匹配要素数量 (location, event, time, source)
            matched_count = sum([
                1 if matching.get("location") else 0,
                1 if matching.get("event") else 0,
                1 if matching.get("time") else 0,
                1 if matching.get("source") else 0,
            ])

            if decision == "discard":
                # v4.17.0: 使用配置化的丢弃阈值
                # 如果意图分数高于配置阈值，则保留而不是丢弃
                current_score = 0.4 + (matched_count / 4) * 0.2
                discard_threshold = getattr(self.config, "intent_filter_discard_threshold", 0.3)
                if current_score >= discard_threshold:
                    # 分数足够高，改为降级而不是丢弃
                    decision = "downgrade"
                else:
                    # 丢弃
                    stats["discard"] += 1
                    logger.debug(f"[user:{user_id}] Discarded: {url[:50]}...")
            if decision == "downgrade":
                # v4.17.0: 降级：使用配置化的降级阈值
                downgrade_threshold = getattr(self.config, "intent_filter_downgrade_threshold", 0.5)
                intent_score = 0.4 + (matched_count / 4) * 0.2
                result["intent_score"] = round(intent_score, 3)
                result["intent_match"] = "downgrade"
                filtered_results.append(result)
                stats["downgrade"] += 1
            else:
                # 保留：intent_score = 0.8 + (matched_count/4) * 0.2
                intent_score = 0.8 + (matched_count / 4) * 0.2
                result["intent_score"] = round(intent_score, 3)
                result["intent_match"] = "keep"
                filtered_results.append(result)
                stats["keep"] += 1

        return filtered_results, stats


# ============================================================================
# 工厂函数
# ============================================================================

def create_intent_filter_node(
    config: Optional[LangGraphSearchConfig] = None,
    anthropic_client: Optional[Any] = None,
) -> IntentFilterNode:
    """创建意图筛选节点的工厂函数

    Args:
        config: LangGraph 搜索配置
        anthropic_client: Anthropic 客户端

    Returns:
        IntentFilterNode 实例
    """
    return IntentFilterNode(
        config=config,
        anthropic_client=anthropic_client,
    )
