"""Chat 搜索要素实体

定义搜索要素的数据结构，用于要素确认流程。

v4.20.0 - 添加 gsac 搜索要素确认功能
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ChatSearchElements:
    """Chat 搜索要素实体

    封装从用户问题中提取的搜索要素，支持用户确认和修改。

    Attributes:
        keywords: 中文关键词列表
        keywords_en: 英文关键词列表
        time_range: 时间范围 (qdr:d, qdr:w, qdr:m, qdr:y)
        source_preferences: 来源偏好列表 (official, mainstream, regional)
        languages: 搜索语言列表
        search_strategy: 搜索策略配置
        summary: 事件简要描述
        event_type: 事件类型 (政治, 军事, 经济, 外交, 科技, 社会, 其他)
        llm_reasoning: LLM 分析理由
        original_query: 原始查询
    """

    keywords: List[str]
    keywords_en: List[str] = field(default_factory=list)
    time_range: Optional[str] = None
    source_preferences: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["zh", "en"])
    search_strategy: Dict[str, Any] = field(default_factory=dict)

    # 元信息
    summary: str = ""
    event_type: str = ""
    llm_reasoning: str = ""
    original_query: str = ""

    # 时间戳
    extracted_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "keywords": self.keywords,
            "keywords_en": self.keywords_en,
            "time_range": self.time_range,
            "source_preferences": self.source_preferences,
            "languages": self.languages,
            "search_strategy": self.search_strategy,
            "summary": self.summary,
            "event_type": self.event_type,
            "llm_reasoning": self.llm_reasoning,
            "original_query": self.original_query,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSearchElements":
        """从字典创建实例"""
        extracted_at = data.get("extracted_at")
        if isinstance(extracted_at, str):
            extracted_at = datetime.fromisoformat(extracted_at)

        return cls(
            keywords=data.get("keywords", []),
            keywords_en=data.get("keywords_en", []),
            time_range=data.get("time_range"),
            source_preferences=data.get("source_preferences", []),
            languages=data.get("languages", ["zh", "en"]),
            search_strategy=data.get("search_strategy", {}),
            summary=data.get("summary", ""),
            event_type=data.get("event_type", ""),
            llm_reasoning=data.get("llm_reasoning", ""),
            original_query=data.get("original_query", ""),
            extracted_at=extracted_at,
        )

    @classmethod
    def from_enhanced_decomposition(
        cls,
        decomp: Any,
        original_query: str = ""
    ) -> "ChatSearchElements":
        """从 EnhancedQueryDecomposition 转换

        Args:
            decomp: UnifiedQueryAnalyzer 返回的 EnhancedQueryDecomposition
            original_query: 原始查询文本

        Returns:
            ChatSearchElements 实例
        """
        # 提取来源偏好
        source_preferences = []
        if decomp.search_strategy:
            recommended_sources = decomp.search_strategy.get("recommended_sources", [])
            for src in recommended_sources:
                if "官方" in src or "政府" in src:
                    source_preferences.append("official")
                elif "主流" in src or "权威" in src:
                    source_preferences.append("mainstream")
                elif "智库" in src or "研究" in src:
                    source_preferences.append("think_tank")
                elif "地区" in src or "周边" in src:
                    source_preferences.append("regional")

        # 默认搜索策略
        # v4.22.0: enable_deep_scrape 改为默认 True，以获取完整 markdown_content
        default_strategy = {
            "max_keywords": 5,
            "max_results_per_keyword": 10,
            "enable_deep_scrape": True,
            "similarity_threshold": 0.8,
        }

        # 合并用户提供的策略
        search_strategy = {**default_strategy}
        if decomp.search_strategy:
            # 提取 gsac 相关配置
            if "primary_focus" in decomp.search_strategy:
                search_strategy["primary_focus"] = decomp.search_strategy["primary_focus"]
            if "secondary_topics" in decomp.search_strategy:
                search_strategy["secondary_topics"] = decomp.search_strategy["secondary_topics"]

        # 提取语言列表
        languages = list(decomp.query_variations.keys()) if decomp.query_variations else ["zh", "en"]

        # 构建 LLM 推理说明
        llm_reasoning = decomp.overall_strategy if hasattr(decomp, "overall_strategy") else ""
        if decomp.time_sensitivity == "high":
            llm_reasoning += " 时效性要求高，建议搜索最近的内容。"
        elif decomp.time_sensitivity == "low":
            llm_reasoning += " 时效性要求较低，可以搜索更长时间范围。"

        return cls(
            keywords=decomp.keywords if decomp.keywords else [],
            keywords_en=decomp.keywords_en if decomp.keywords_en else [],
            time_range=decomp.suggested_time_range,
            source_preferences=source_preferences if source_preferences else ["mainstream"],
            languages=languages,
            search_strategy=search_strategy,
            summary=decomp.summary if decomp.summary else "",
            event_type=decomp.event_type if decomp.event_type else "其他",
            llm_reasoning=llm_reasoning,
            original_query=original_query,
            extracted_at=datetime.utcnow(),
        )

    def to_gsac_options(self) -> Dict[str, Any]:
        """转换为 gsac 搜索选项

        Returns:
            适用于 GSAICrawlEngine.search() 的 options 参数
        """
        # v4.22.0: enable_deep_scrape 默认改为 True，以获取完整 markdown_content
        options = {
            "max_keywords": self.search_strategy.get("max_keywords", 5),
            "max_results_per_keyword": self.search_strategy.get("max_results_per_keyword", 10),
            "enable_deep_scrape": self.search_strategy.get("enable_deep_scrape", True),
            "similarity_threshold": self.search_strategy.get("similarity_threshold", 0.8),
            "enable_summary": self.search_strategy.get("enable_summary", True),
        }

        return options

    def build_search_query(self) -> str:
        """根据要素构建搜索查询

        Returns:
            组合后的搜索查询字符串
        """
        if self.original_query:
            return self.original_query

        # 使用关键词构建查询
        if self.keywords:
            return " ".join(self.keywords[:3])

        return ""

    def get_time_range_display(self) -> str:
        """获取时间范围的显示文本"""
        time_range_map = {
            "qdr:d": "过去24小时",
            "qdr:w": "过去一周",
            "qdr:m": "过去一个月",
            "qdr:y": "过去一年",
        }
        return time_range_map.get(self.time_range, "不限时间")

    def get_source_preferences_display(self) -> List[str]:
        """获取来源偏好的显示文本"""
        source_map = {
            "official": "官方来源",
            "mainstream": "主流媒体",
            "regional": "地区媒体",
            "think_tank": "智库机构",
            "international": "国际媒体",
        }
        return [source_map.get(s, s) for s in self.source_preferences]
