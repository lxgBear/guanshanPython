"""搜索引擎适配器

提供统一的搜索接口，支持在 NL Search 和 LangGraph 搜索引擎之间切换。

**v4.0.0 新增**:
- 支持 LangGraph 搜索引擎
- 配置化引擎选择
- 自动回退机制

Usage:
    from src.services.search_engine_adapter import search_engine_adapter

    result = await search_engine_adapter.search(
        query="中美贸易谈判",
        user_id="12345",
        search_mode="single"
    )
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

# 确保环境变量被加载（防止导入顺序问题）
from dotenv import load_dotenv
load_dotenv(override=True)

# Firecrawl 客户端导入
try:
    from firecrawl import Firecrawl
    HAS_FIRECRAWL = True
except ImportError:
    Firecrawl = None
    HAS_FIRECRAWL = False

logger = logging.getLogger(__name__)


class SearchEngine(str, Enum):
    """搜索引擎类型"""
    NL_SEARCH = "nl_search"      # 原有 NL Search 服务
    LANGGRAPH = "langgraph"      # 新 LangGraph 搜索服务


class SearchEngineConfig:
    """搜索引擎配置"""

    def __init__(self):
        # 从环境变量读取配置，默认使用 langgraph (v4.1.0)
        self.engine = SearchEngine(
            os.getenv("SEARCH_ENGINE", "langgraph")
        )
        # 是否启用自动回退（LangGraph 失败时回退到 nl_search）
        self.enable_fallback = os.getenv(
            "SEARCH_ENGINE_FALLBACK", "true"
        ).lower() == "true"
        # LangGraph 特定配置
        self.langgraph_enable_checkpointing = os.getenv(
            "LANGGRAPH_ENABLE_CHECKPOINTING", "false"
        ).lower() == "true"

    def __repr__(self):
        return (
            f"SearchEngineConfig(engine={self.engine}, "
            f"fallback={self.enable_fallback})"
        )


# 全局配置实例
search_engine_config = SearchEngineConfig()


class SearchEngineAdapter:
    """搜索引擎适配器

    提供统一接口，支持多种搜索引擎后端。

    Features:
    - 统一的搜索接口
    - 自动引擎选择
    - 失败回退机制
    - 结果格式标准化
    """

    def __init__(self, config: Optional[SearchEngineConfig] = None):
        """初始化适配器

        Args:
            config: 搜索引擎配置，默认使用全局配置
        """
        self.config = config or search_engine_config
        self._nl_search_service = None
        self._langgraph_service = None

        logger.info(
            f"[ADAPTER_INIT] config={self.config}, "
            f"firecrawl_sdk_available={HAS_FIRECRAWL}"
        )

    @property
    def nl_search_service(self):
        """懒加载 NL Search 服务"""
        if self._nl_search_service is None:
            from src.services.nl_search.nl_search_service import nl_search_service
            self._nl_search_service = nl_search_service
        return self._nl_search_service

    @property
    def langgraph_service(self):
        """懒加载 LangGraph 服务"""
        if self._langgraph_service is None:
            try:
                from src.services.langgraph_search import LangGraphSearchService

                # 创建 Firecrawl 客户端
                firecrawl_client = None
                if HAS_FIRECRAWL and Firecrawl is not None:
                    api_key = os.getenv("FIRECRAWL_API_KEY")
                    if api_key:
                        firecrawl_client = Firecrawl(api_key=api_key)
                        logger.info("Firecrawl client created for LangGraph")
                    else:
                        logger.warning("FIRECRAWL_API_KEY not configured")
                else:
                    logger.warning("Firecrawl SDK not installed")

                self._langgraph_service = LangGraphSearchService(
                    firecrawl_client=firecrawl_client,
                )
                logger.info(
                    f"[LANGGRAPH_INIT] success=True, "
                    f"firecrawl_client_available={firecrawl_client is not None}"
                )
            except ImportError as e:
                logger.warning(f"LangGraph not available: {e}")
                self._langgraph_service = None
            except Exception as e:
                logger.error(f"Failed to initialize LangGraphSearchService: {e}")
                self._langgraph_service = None
        return self._langgraph_service

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        search_mode: str = "single",
        force_engine: Optional[SearchEngine] = None,
        task_id: Optional[str] = None,  # v4.5.2: 传递 task_id 用于数据库存储
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式 (single/multi)
            force_engine: 强制使用指定引擎（覆盖配置）
            task_id: 任务ID（v4.5.2: 用于关联数据库记录）

        Returns:
            标准化的搜索结果:
            {
                "log_id": str,
                "query_text": str,
                "search_mode": str,
                "results": list,
                "engine_used": str,
                "created_at": str,
                ...
            }
        """
        engine = force_engine or self.config.engine

        logger.info(
            f"Search request: query='{query[:50]}...', "
            f"user_id={user_id}, engine={engine}, task_id={task_id}"
        )

        # 根据配置选择搜索引擎
        if engine == SearchEngine.LANGGRAPH:
            result = await self._search_with_langgraph(
                query=query,
                user_id=user_id,
                search_mode=search_mode,
                task_id=task_id,  # v4.5.2: 传递 task_id
            )

            # 检查是否需要回退
            if not result.get("success", True) and self.config.enable_fallback:
                logger.warning(
                    f"LangGraph search failed, falling back to nl_search: "
                    f"{result.get('error')}"
                )
                result = await self._search_with_nl_search(
                    query=query,
                    user_id=user_id,
                    search_mode=search_mode,
                )
                result["fallback_used"] = True

            return result

        else:
            # 默认使用 NL Search
            return await self._search_with_nl_search(
                query=query,
                user_id=user_id,
                search_mode=search_mode,
            )

    async def _search_with_nl_search(
        self,
        query: str,
        user_id: Optional[str],
        search_mode: str,
    ) -> Dict[str, Any]:
        """使用 NL Search 执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式

        Returns:
            搜索结果
        """
        try:
            result = await self.nl_search_service.create_search(
                query_text=query,
                user_id=user_id,
                search_mode=search_mode,
            )

            # 标准化结果格式
            return {
                **result,
                "engine_used": SearchEngine.NL_SEARCH.value,
                "success": True,
            }

        except Exception as e:
            logger.error(f"NL Search failed: {e}", exc_info=True)
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": SearchEngine.NL_SEARCH.value,
                "success": False,
                "error": str(e),
                "created_at": datetime.now().isoformat(),
            }

    async def _search_with_langgraph(
        self,
        query: str,
        user_id: Optional[str],
        search_mode: str,
        task_id: Optional[str] = None,  # v4.5.2: 传递 task_id
    ) -> Dict[str, Any]:
        """使用 LangGraph 执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式
            task_id: 任务ID（v4.5.2: 用于关联数据库记录）

        Returns:
            搜索结果（转换为标准格式）
        """
        # 检查 LangGraph 服务是否可用
        if self.langgraph_service is None:
            logger.warning("LangGraph service not available")
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": SearchEngine.LANGGRAPH.value,
                "success": False,
                "error": "LangGraph service not available",
                "created_at": datetime.now().isoformat(),
            }

        # 确保 user_id 存在（LangGraph 必需）
        if not user_id:
            user_id = "anonymous"
            logger.warning("No user_id provided, using 'anonymous'")

        try:
            # 构建 LangGraph 搜索选项
            options = {
                "search_mode": search_mode,
                "task_id": task_id,  # v4.5.2: 传递 task_id 用于数据库存储
            }

            # v4.4.0: 移除硬编码的多语言检测，改由 QueryAnalyzer (LLM) 智能判断
            # 语言检测和关键词翻译现在由 Claude 在 QueryAnalyzer 节点中完成
            # 每个搜索层级可以有独立的语言和关键词配置 (layer_search_config)

            # 执行 LangGraph 搜索
            lg_result = await self.langgraph_service.execute_search(
                query=query,
                user_id=user_id,
                options=options,
            )

            # 转换为标准格式
            converted = self._convert_langgraph_result(lg_result, query, search_mode)
            logger.info(
                f"[LANGGRAPH_RESULT] query='{query[:50]}...', "
                f"results_count={len(converted.get('results', []))}, "
                f"success={converted.get('success')}, "
                f"status={lg_result.get('status')}"
            )
            return converted

        except Exception as e:
            logger.error(f"LangGraph search failed: {e}", exc_info=True)
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": SearchEngine.LANGGRAPH.value,
                "success": False,
                "error": str(e),
                "created_at": datetime.now().isoformat(),
            }

    def _convert_langgraph_result(
        self,
        lg_result: Dict[str, Any],
        query: str,
        search_mode: str,
    ) -> Dict[str, Any]:
        """转换 LangGraph 结果为标准格式

        LangGraph 返回格式:
        {
            "success": bool,
            "thread_id": str,
            "user_id": str,
            "query": str,
            "status": str,
            "results": list,
            "statistics": dict,
            ...
        }

        标准格式:
        {
            "log_id": str,
            "query_text": str,
            "search_mode": str,
            "results": list,
            "analysis": dict,
            ...
        }
        """
        # 转换结果列表格式
        converted_results = []
        for result in lg_result.get("results", []):
            # LangGraph SearchResult 转换为 NL Search 格式
            converted_results.append({
                "id": result.get("id") or result.get("url", ""),
                "mongo_id": result.get("mongo_id", ""),
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "source": result.get("source_domain", ""),
                "score": result.get("final_score", 0.0),
                "layer": result.get("layer", 0),
                "layer_name": result.get("layer_name", ""),
                "publish_time": result.get("publish_date", ""),
                "category": {
                    "大类": result.get("category", "未分类"),
                    "类别": result.get("subcategory", "未分类"),
                    "地域": result.get("region", "未知"),
                },
                "preview": (result.get("snippet") or "")[:200],
            })

        return {
            "log_id": lg_result.get("thread_id"),
            "query_text": query,
            "search_mode": search_mode,
            "results": converted_results,
            "analysis": lg_result.get("statistics", {}),
            "engine_used": SearchEngine.LANGGRAPH.value,
            "success": lg_result.get("success", False),
            "error": lg_result.get("error_message"),
            "created_at": lg_result.get("started_at") or datetime.now().isoformat(),
            # 保留 LangGraph 特有字段
            "langgraph_status": lg_result.get("status"),
            "langgraph_statistics": lg_result.get("statistics"),
            "needs_review": lg_result.get("needs_review", False),
        }

    def _detect_multilingual_intent(self, query: str) -> Optional[List[str]]:
        """自动检测查询的多语言意图

        .. deprecated:: v4.4.0
            此方法已废弃。语言检测现在由 QueryAnalyzer 节点中的 Claude LLM 智能判断。
            每个搜索层级有独立的语言和关键词配置 (layer_search_config)。
            保留此方法仅用于向后兼容。

        当查询包含"西方媒体"、"国际媒体"、"欧洲媒体"等关键词时，
        自动返回对应的目标语言列表。

        Args:
            query: 搜索查询

        Returns:
            检测到的语言代码列表，如果没有检测到则返回 None
        """
        from src.services.langgraph_search.languages import (
            get_european_languages, get_asian_languages,
            get_media_domains, get_south_asian_languages,
            get_eastern_european_languages,
        )

        query_lower = query.lower()

        # 西方媒体关键词 → 欧洲语言
        western_keywords = ["西方媒体", "西方主流媒体", "欧美媒体", "西方新闻",
                           "国际媒体", "海外媒体", "西方国家", "欧美", "西方世界"]
        if any(kw in query for kw in western_keywords):
            logger.info(f"Detected 'western media' intent, using European languages")
            return get_european_languages()

        # 欧洲媒体关键词
        european_keywords = ["欧洲媒体", "欧盟媒体", "欧洲新闻", "欧洲报道"]
        if any(kw in query for kw in european_keywords):
            logger.info(f"Detected 'european media' intent, using European languages")
            return get_european_languages()

        # 亚洲媒体关键词
        asian_keywords = ["亚洲媒体", "亚洲新闻", "东亚媒体", "东南亚媒体"]
        if any(kw in query for kw in asian_keywords):
            logger.info(f"Detected 'asian media' intent, using Asian languages")
            return get_asian_languages()

        # 东欧媒体关键词
        eastern_european_keywords = ["东欧媒体", "俄语媒体"]
        if any(kw in query for kw in eastern_european_keywords):
            logger.info(f"Detected 'eastern european' intent, using Eastern European languages")
            return get_eastern_european_languages()

        # 南亚媒体关键词
        south_asian_keywords = ["南亚媒体", "印度媒体"]
        if any(kw in query for kw in south_asian_keywords):
            logger.info(f"Detected 'south asian' intent, using South Asian languages")
            return get_south_asian_languages()

        # 中东媒体关键词
        middle_east_keywords = ["中东媒体", "阿拉伯媒体", "中东新闻"]
        if any(kw in query for kw in middle_east_keywords):
            logger.info(f"Detected 'middle east' intent, using Arabic/Turkish/Hebrew")
            return ["ar", "tr", "he"]

        return None

    def get_engine_status(self) -> Dict[str, Any]:
        """获取搜索引擎状态

        Returns:
            引擎状态信息
        """
        return {
            "configured_engine": self.config.engine.value,
            "fallback_enabled": self.config.enable_fallback,
            "nl_search_available": self._nl_search_service is not None or True,
            "langgraph_available": self.langgraph_service is not None,
        }


# 全局适配器实例
search_engine_adapter = SearchEngineAdapter()
