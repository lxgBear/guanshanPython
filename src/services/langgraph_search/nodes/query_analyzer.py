"""查询分析节点 (v4.7.0)

OSINT 架构中的协调器节点，负责协调意图解析和关键词生成。
保留作为 QueryAnalyzer 的接口兼容性，内部委托给 IntentParserNode 和 KeywordGeneratorNode。
"""

import logging
from typing import Dict, Any, List, Optional

from anthropic import Anthropic

from ..state import SearchState
from ..config import LangGraphSearchConfig
from .intent_parser import IntentParserNode
from .keyword_generator import KeywordGeneratorNode

logger = logging.getLogger(__name__)


class QueryAnalyzerNode:
    """查询分析节点 (v4.7.0 - OSINT 架构重构）

    协调器模式：将原本的单节点分析拆分为两个独立节点：
    1. IntentParserNode: 解析用户意图（提取 investigation_target, source_type_constraint）
    2. KeywordGeneratorNode: 基于 investigation_target 生成分层关键词

    保留兼容性：仍作为 QueryAnalyzerNode 存在，但内部使用新架构。
    """

    def __init__(
        self,
        config: Optional[LangGraphSearchConfig] = None,
        anthropic_client: Optional[Anthropic] = None,
    ):
        """初始化查询分析节点

        Args:
            config: LangGraph 搜索配置
            anthropic_client: Anthropic 客户端（可选）
        """
        self.config = config or LangGraphSearchConfig()
        self.client = anthropic_client or Anthropic()

        # v4.7.0: 创建子节点
        self.intent_parser = IntentParserNode(self.config, self.client)
        self.keyword_generator = KeywordGeneratorNode(self.config, self.client)

    def __call__(self, state: SearchState) -> Dict[str, Any]:
        """执行查询分析（协调器模式）

        Args:
            state: 当前搜索状态

        Returns:
            状态更新字典
        """
        query = state.get("query", "")
        user_id = state.get("user_id", "")

        if not query:
            logger.warning(f"[user:{user_id}] Empty query received")
            return {
                "analysis": {},
                "parties": [],
                "keywords": [],
                "keywords_en": [],
                "time_range": "qdr:m",
                "status": "failed",
                "error_message": "查询为空",
            }

        # 检查是否使用 OSINT 架构（通过 feature flag）
        use_osint_architecture = self._should_use_osint_architecture(state)

        try:
            if use_osint_architecture:
                return self._execute_osint_architecture(state, query, user_id)
            else:
                return self._execute_legacy_architecture(state, query, user_id)

        except Exception as e:
            logger.error(f"[user:{user_id}] Query analysis failed: {e}")
            # 降级到旧架构的错误处理
            return {
                "analysis": {},
                "parties": [],
                "keywords": [],
                "keywords_en": [],
                "time_range": "qdr:m",
                "target_languages": state.get("target_languages", ["en", "zh"]),
                "layer_search_config": {},
                "enabled_layers": self.config.get_enabled_layers(),
                "status": "running",
                "error_message": f"查询分析失败: {str(e)}",
            }

    def _should_use_osint_architecture(self, state: SearchState) -> bool:
        """判断是否使用 OSINT 新架构

        Args:
            state: 当前搜索状态

        Returns:
            True 如果使用新架构
        """
        # 检查 feature flag
        search_options = state.get("search_options", {})
        if search_options.get("use_osint_architecture") is not None:
            return search_options["use_osint_architecture"]

        # 检查状态中是否有迁移版本标记
        osint_version = state.get("osint_migration_version")
        if osint_version:
            # 如果状态已经有 OSINT 版本标记，说明是新架构
            return True

        # 默认使用新架构（v4.7.0 开始）
        return True

    def _execute_osint_architecture(
        self,
        state: SearchState,
        query: str,
        user_id: str
    ) -> Dict[str, Any]:
        """执行 OSINT 新架构（两阶段：意图解析 + 关键词生成）

        Args:
            state: 当前搜索状态
            query: 搜索查询
            user_id: 用户 ID

        Returns:
            状态更新字典
        """
        logger.info(f"[user:{user_id}] Using OSINT architecture (v4.7.0)")

        # 阶段 1: 意图解析
        intent_result = self.intent_parser(state)

        # 阶段 2: 关键词生成（基于意图解析结果）
        # 注意：keyword_generator 需要 parsed_intent 存在于 state 中
        # 所以需要先更新 state，然后再调用 keyword_generator
        state_after_intent = {**state, **intent_result}
        keyword_result = self.keyword_generator(state_after_intent)

        # 合并结果
        result = {**intent_result, **keyword_result}

        # 生成兼容性的输出格式
        # 从 keyword_groups 提取 keywords 和 keywords_en
        keyword_groups = result.get("keyword_groups", [])
        keywords = []
        keywords_en = []

        for group in keyword_groups:
            if group.get("language") == "zh":
                keywords.extend(group.get("keywords", []))
            elif group.get("language") == "en":
                keywords_en.extend(group.get("keywords", []))

        # 去重
        keywords = list(dict.fromkeys(keywords))
        keywords_en = list(dict.fromkeys(keywords_en))

        # 生成 layer_search_config（兼容性）
        layer_search_config = {}
        for group in keyword_groups:
            layer = group.get("layer")
            layer_search_config[f"layer_{layer}"] = {
                "description": group.get("description", ""),
                "language": group.get("language", "en"),
                "keywords": group.get("keywords", []),
                "enabled": True,
            }

        logger.info(
            f"[user:{user_id}] OSINT architecture complete: "
            f"{len(keywords)} zh keywords, {len(keywords_en)} en keywords"
        )

        return {
            "analysis": {
                "investigation_target": state_after_intent.get("parsed_intent", {}).get("investigation_target", ""),
                "source_type_constraint": result.get("source_type_constraint"),
                "keyword_groups": keyword_groups,
            },
            "parties": [],  # 新架构暂时保留空列表
            "keywords": keywords,  # 兼容性字段
            "keywords_en": keywords_en,  # 兼容性字段
            "time_range": result.get("time_range", "qdr:m"),
            "target_languages": result.get("target_languages", ["en", "zh"]),
            "search_domains": result.get("search_domains", []),
            "layer_search_config": layer_search_config,
            "enabled_layers": self.config.get_enabled_layers(),
            # OSINT 新架构字段
            "parsed_intent": result.get("parsed_intent"),
            "keyword_groups": keyword_groups,
            "source_type_constraint": result.get("source_type_constraint"),
            "status": "running",
        }

    def _execute_legacy_architecture(
        self,
        state: SearchState,
        query: str,
        user_id: str
    ) -> Dict[str, Any]:
        """执行旧架构（单节点分析，用于降级）

        Args:
            state: 当前搜索状态
            query: 搜索查询
            user_id: 用户 ID

        Returns:
            状态更新字典
        """
        logger.info(f"[user:{user_id}] Using legacy architecture")

        # 保留 v4.6.0 的后处理逻辑
        # 这里可以调用旧的分析方法，但为了简化，
        # 我们在 OSINT 架构中已经实现，
        # 直接将 intent_parser 和 keyword_generator 结果合并即可

        return self._execute_osint_architecture(state, query, user_id)
