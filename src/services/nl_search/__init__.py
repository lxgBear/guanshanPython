"""
自然语言搜索服务模块

v2.0.0 (清理后)
状态: ✅ 完成代码清理 + Claude Search Agent v2.1

模块结构:
- config.py: 配置管理 ✅
- prompts.py: Prompt 模板 ✅
- llm_processor.py: LLM 处理器 ✅
- gpt5_search_adapter.py: GPT-5 搜索适配器 ✅
- nl_search_service.py: 核心服务 ✅
- multilang_search_service.py: 多语言搜索服务 (Claude + Firecrawl) ✅
- claude_search_agent_v2_1.py: 智能搜索 Agent (来源分层 + 可信度评分) ✅
- mongo_archive_service.py: MongoDB 档案服务 (v2.5.4) ✅
- firecrawl_search_adapter.py: Firecrawl 搜索适配器 ✅

已删除的过时文件 (v2.0.0 清理):
- claude_search_agent.py (v1) → 已被 v2.1 取代
- claude_search_agent_v2.py (v2) → 已被 v2.1 取代
- search_strategy.py → 仅被 v1 使用
- archive_service.py → 已被 mongo_archive_service.py 取代
"""
from .config import nl_search_config, NLSearchConfig
from .llm_processor import LLMProcessor
from .gpt5_search_adapter import GPT5SearchAdapter, SearchResult
from .nl_search_service import NLSearchService, nl_search_service
from .multilang_search_service import (
    MultilangSearchService,
    MultilangSearchConfig,
    create_multilang_search_service,
    get_multilang_search_service,
)
from .claude_search_agent_v2_1 import (
    ClaudeSearchAgentV21,
    EnhancedSearchResult,
)
from .mongo_archive_service import (
    MongoArchiveService,
    mongo_archive_service,
)

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
    # 多语言搜索 (Claude + Firecrawl)
    "MultilangSearchService",
    "MultilangSearchConfig",
    "create_multilang_search_service",
    "get_multilang_search_service",
    # Claude Search Agent v2.1
    "ClaudeSearchAgentV21",
    "EnhancedSearchResult",
    # MongoDB 档案服务
    "MongoArchiveService",
    "mongo_archive_service",
]
