"""输出适配器 (v4.7.0)

确保 OSINT 新架构的输出格式与旧 API 保持兼容。

## 适配原则

1. **向后兼容**: 新架构输出应包含旧架构的所有字段
2. **渐进增强**: 新架构可以添加额外字段，但不破坏现有字段
3. **字段映射**: 新架构字段到旧架构字段的映射关系清晰

## 字段映射表

### 新架构 → 旧架构

| 新架构字段 | 旧架构字段 | 说明 |
|-----------|-----------|------|
| parsed_intent.investigation_target | analysis.query | 调查目标 |
| keyword_groups | keywords + keywords_en | 关键词 |
| source_type_constraint | analysis.source_constraint | 媒体类型约束 |
| - | analysis.parties | 当事方（保留为空） |
| - | analysis.overall_strategy | 策略（保留为空） |

### 聚合结果映射

| 新架构字段 | 旧 API 字段 | 说明 |
|-----------|------------|------|
| layer | - | 新增字段 |
| layer_name | - | 新增字段 |
| source_tier | - | 新增字段 |
| credibility_score | quality_score | 可信度分数 |
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputAdapter:
    """输出适配器

    将 OSINT 新架构的输出转换为兼容旧 API 的格式。

    Example:
        >>> adapter = OutputAdapter()
        >>> compatible_state = adapter.adapt_state(osint_state)
        >>> api_response = adapter.to_api_response(compatible_state)
    """

    # 兼容性字段映射配置
    COMPATIBILITY_VERSION = "4.7.0"
    LEGACY_VERSION = "4.6.0"

    def __init__(self):
        """初始化适配器"""
        self._warnings: List[str] = []

    def adapt_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """适配 State 为兼容格式

        将新架构的 State 转换为包含旧架构所有字段的格式。

        Args:
            state: 新架构的 SearchState

        Returns:
            兼容旧架构的 State
        """
        adapted = {**state}
        self._warnings = []

        # 确保有 analysis 字段
        if "analysis" not in adapted or not adapted["analysis"]:
            adapted["analysis"] = self._create_analysis_from_new_fields(state)

        # 确保有 keywords 字段
        if "keywords" not in adapted or not adapted["keywords"]:
            adapted["keywords"] = self._extract_keywords_from_groups(state)

        # 确保有 keywords_en 字段
        if "keywords_en" not in adapted or not adapted["keywords_en"]:
            adapted["keywords_en"] = self._extract_keywords_en_from_groups(state)

        # 确保 layer_search_config 存在
        if "layer_search_config" not in adapted or not adapted["layer_search_config"]:
            adapted["layer_search_config"] = self._create_layer_config_from_groups(state)

        # 确保有 parties 字段（兼容性）
        if "parties" not in adapted:
            adapted["parties"] = []

        # 记录适配信息
        if self._warnings:
            logger.warning(f"[OutputAdapter] Adaptation warnings: {self._warnings}")

        return adapted

    def _create_analysis_from_new_fields(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """从新架构字段创建兼容的 analysis 对象

        Args:
            state: 新架构 State

        Returns:
            兼容旧架构的 analysis 字典
        """
        analysis = {}

        # 从 parsed_intent 提取信息
        parsed_intent = state.get("parsed_intent", {}) or {}
        if parsed_intent:
            analysis["query"] = parsed_intent.get("investigation_target", "")
            analysis["source_constraint"] = parsed_intent.get("source_type_constraint")
            analysis["investigation_type"] = parsed_intent.get("investigation_type", "event")

        # 保留兼容的空字段
        analysis["overall_strategy"] = ""
        analysis["summary"] = parsed_intent.get("investigation_target", "")

        return analysis

    def _extract_keywords_from_groups(
        self, state: Dict[str, Any]
    ) -> List[str]:
        """从 keyword_groups 提取中文关键词

        Args:
            state: 新架构 State

        Returns:
            中文关键词列表
        """
        keyword_groups = state.get("keyword_groups", []) or []
        keywords = []

        for group in keyword_groups:
            if isinstance(group, dict):
                if group.get("language") == "zh":
                    keywords.extend(group.get("keywords", []))

        # 去重
        return list(dict.fromkeys(keywords))

    def _extract_keywords_en_from_groups(
        self, state: Dict[str, Any]
    ) -> List[str]:
        """从 keyword_groups 提取英文关键词

        Args:
            state: 新架构 State

        Returns:
            英文关键词列表
        """
        keyword_groups = state.get("keyword_groups", []) or []
        keywords_en = []

        for group in keyword_groups:
            if isinstance(group, dict):
                if group.get("language") == "en":
                    keywords_en.extend(group.get("keywords", []))

        # 去重
        return list(dict.fromkeys(keywords_en))

    def _create_layer_config_from_groups(
        self, state: Dict[str, Any]
    ) -> Dict[str, Dict]:
        """从 keyword_groups 创建 layer_search_config

        Args:
            state: 新架构 State

        Returns:
            layer_search_config 字典
        """
        keyword_groups = state.get("keyword_groups", []) or []
        config = {}

        for group in keyword_groups:
            if isinstance(group, dict):
                layer = group.get("layer", 0)
                config[f"layer_{layer}"] = {
                    "description": group.get("description", ""),
                    "language": group.get("language", "en"),
                    "keywords": group.get("keywords", []),
                    "search_type": group.get("search_type", "news"),
                    "enabled": True,
                }

        return config

    def to_api_response(
        self,
        state: Dict[str, Any],
        thread_id: str,
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        """将 State 转换为 API 响应格式

        Args:
            state: 搜索状态
            thread_id: 线程ID
            include_metadata: 是否包含元数据

        Returns:
            API 响应字典
        """
        # 先适配 State
        adapted_state = self.adapt_state(state)

        # 构建响应
        response = {
            "success": adapted_state.get("status") == "completed",
            "thread_id": thread_id,
            "user_id": adapted_state.get("user_id", ""),
            "query": adapted_state.get("query", ""),
            "status": adapted_state.get("status", "unknown"),
            "results": adapted_state.get("final_results", []),
            "statistics": self._build_statistics(adapted_state),
            "error_message": adapted_state.get("error_message"),
            "needs_review": adapted_state.get("needs_review", False),
        }

        # 可选元数据
        if include_metadata:
            response["metadata"] = {
                "started_at": adapted_state.get("started_at"),
                "completed_at": adapted_state.get("completed_at"),
                "architecture_version": self.COMPATIBILITY_VERSION,
                "osint_migration_version": adapted_state.get("osint_migration_version"),
                "enabled_layers": adapted_state.get("enabled_layers", []),
            }

        return response

    def _build_statistics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """构建统计信息

        Args:
            state: 搜索状态

        Returns:
            统计信息字典
        """
        final_results = state.get("final_results", [])
        layer_results = state.get("layer_results", {}) or {}

        stats = {
            "total_results": len(final_results),
            "layer_distribution": {},
            "quality_metrics": state.get("quality_metrics", {}),
        }

        # 按层级统计结果
        for result in final_results:
            layer = result.get("layer", 0)
            layer_name = result.get("layer_name", f"Layer {layer}")
            if layer_name not in stats["layer_distribution"]:
                stats["layer_distribution"][layer_name] = 0
            stats["layer_distribution"][layer_name] += 1

        # 添加层级搜索执行统计
        for layer_id, layer_data in layer_results.items():
            if isinstance(layer_data, dict):
                layer_name = layer_data.get("layer_name", f"Layer {layer_id}")
                stats["layer_distribution"][f"{layer_name}_searched"] = (
                    stats["layer_distribution"].get(f"{layer_name}_searched", 0) +
                    len(layer_data.get("results", []))
                )

        return stats

    def adapt_result_item(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """适配单个结果项为兼容格式

        Args:
            result: 搜索结果项

        Returns:
            兼容格式的结果项
        """
        # 确保必要字段存在
        adapted = {
            "url": result.get("url", ""),
            "title": result.get("title", ""),
            "snippet": result.get("snippet", ""),
            "source": result.get("source_domain", result.get("source", "web")),
        }

        # 评分字段（新旧兼容）
        adapted["relevance_score"] = result.get("relevance_score", 0.0)
        adapted["quality_score"] = result.get(
            "credibility_score",
            result.get("quality_score", 0.0)
        )
        adapted["final_score"] = result.get("final_score", 0.0)

        # 新架构字段（保留）
        if "layer" in result:
            adapted["layer"] = result["layer"]
        if "layer_name" in result:
            adapted["layer_name"] = result["layer_name"]
        if "source_tier" in result:
            adapted["source_tier"] = result["source_tier"]

        # 内容字段
        if "markdown_content" in result:
            adapted["markdown_content"] = result["markdown_content"]
        if "html_content" in result:
            adapted["html_content"] = result["html_content"]
        if "published_date" in result:
            adapted["published_date"] = result["published_date"]
        if "language" in result:
            adapted["language"] = result["language"]

        return adapted

    def get_warnings(self) -> List[str]:
        """获取适配过程中的警告信息

        Returns:
            警告消息列表
        """
        return self._warnings.copy()


class LegacyOutputAdapter:
    """旧架构输出适配器

    用于 v4.6.0 及之前版本的输出格式适配。
    """

    COMPATIBILITY_VERSION = "4.6.0"

    def to_api_response(
        self,
        state: Dict[str, Any],
        thread_id: str,
    ) -> Dict[str, Any]:
        """将旧架构 State 转换为 API 响应

        Args:
            state: 搜索状态
            thread_id: 线程ID

        Returns:
            API 响应字典
        """
        return {
            "success": state.get("status") == "completed",
            "thread_id": thread_id,
            "user_id": state.get("user_id", ""),
            "query": state.get("query", ""),
            "status": state.get("status", "unknown"),
            "results": state.get("final_results", []),
            "statistics": {
                "total_results": len(state.get("final_results", [])),
                "quality_metrics": state.get("quality_metrics", {}),
            },
            "error_message": state.get("error_message"),
            "needs_review": state.get("needs_review", False),
        }


def create_output_adapter(use_osint: bool = True) -> Union[OutputAdapter, LegacyOutputAdapter]:
    """工厂函数：创建输出适配器

    Args:
        use_osint: 是否使用 OSINT 新架构

    Returns:
        相应的输出适配器实例
    """
    if use_osint:
        return OutputAdapter()
    return LegacyOutputAdapter()
