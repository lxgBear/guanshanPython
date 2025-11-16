"""
自然语言搜索服务模块

v1.0.0-beta
状态: ✅ Phase 1-5 完成

模块结构:
- config.py: 配置管理 ✅
- prompts.py: Prompt 模板 ✅
- llm_processor.py: LLM 处理器 ✅
- gpt5_search_adapter.py: GPT-5 搜索适配器 ✅
- nl_search_service.py: 核心服务 ✅
- content_enricher.py: 内容增强器 (Phase 4 待实现)
"""
from .config import nl_search_config, NLSearchConfig
from .llm_processor import LLMProcessor
from .gpt5_search_adapter import GPT5SearchAdapter, SearchResult
from .nl_search_service import NLSearchService, nl_search_service

__all__ = [
    # 配置
    "nl_search_config",
    "NLSearchConfig",
    # 处理器
    "LLMProcessor",
    # 适配器
    "GPT5SearchAdapter",
    "SearchResult",
    # 服务
    "NLSearchService",
    "nl_search_service",
]
