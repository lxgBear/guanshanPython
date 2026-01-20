"""搜索引擎适配器

提供统一的搜索接口，支持 NL Search 和 gs-ai-crawl 搜索引擎。

v4.19.0 - 集成 gs-ai-crawl
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchEngineConfig:
    """搜索引擎配置"""
    def __init__(self, engine: str = "gsac"):
        # 默认使用 gsac (gs-ai-crawl)
        self.engine = engine

    def __repr__(self):
        return f"SearchEngineConfig(engine={self.engine})"


class SearchEngineAdapter:
    """搜索引擎适配器

    提供统一接口，支持 NL Search 和 gs-ai-crawl 搜索引擎。

    v4.19.0 - 集成 gs-ai-crawl

    Usage:
        from src.services.search_engine_adapter import search_engine_adapter

        result = await search_engine_adapter.search(
            query="中美贸易谈判",
            user_id="12345",
        )
    """

    def __init__(self, config: Optional[SearchEngineConfig] = None):
        """初始化适配器

        Args:
            config: 搜索引擎配置，默认使用 gsac 引擎
        """
        self.config = config or SearchEngineConfig()
        self._gsac_engine = None
        self._nl_search_service = None
        logger.info(
            f"[ADAPTER_INIT] config={self.config}"
        )

    @property
    def gsac_engine(self):
        """懒加载 gs-ai-crawl 引擎"""
        if self._gsac_engine is None:
            from src.services.langgraph_search.gsac_engine import GSAICrawlEngine
            self._gsac_engine = GSAICrawlEngine(self.config.__dict__)
        return self._gsac_engine

    @property
    def nl_search_service(self):
        """懒加载 NL Search 服务"""
        if self._nl_search_service is None:
            from src.services.nl_search.nl_search_service import NLSearchService
            self._nl_search_service = NLSearchService()
        return self._nl_search_service

    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        search_mode: str = "single",
        **options
    ) -> Dict[str, Any]:
        """执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式 (single/multi)
            options: 其他配置选项 (传递给搜索引擎)

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
        logger.info(
            f"Search request: query='{query[:50]}...', "
            f"user_id={user_id}, search_mode={search_mode}, "
            f"engine={self.config.engine}"
        )

        # 根据配置选择引擎
        engine = self.config.engine or "gsac"

        if engine == "gsac":
            return await self._search_with_gsac(
                query=query,
                user_id=user_id,
                search_mode=search_mode,
                **options
            )
        else:
            return await self._search_with_nl_search(
                query=query,
                user_id=user_id,
                search_mode=search_mode,
            )

    async def _search_with_gsac(
        self,
        query: str,
        user_id: Optional[str],
        search_mode: str,
        **options
    ) -> Dict[str, Any]:
        """使用 gs-ai-crawl 执行搜索

        Args:
            query: 搜索查询
            user_id: 用户ID
            search_mode: 搜索模式
            options: 传递给 gsac 的配置选项

        Returns:
            搜索结果
        """
        try:
            return await self.gsac_engine.search(
                query=query,
                user_id=user_id,
                search_mode=search_mode,
                **options
            )
        except ImportError as e:
            logger.error(f"gsac 引擎不可用: {e}")
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": "gsac",
                "success": False,
                "error": f"gsac 引擎不可用: {e}",
                "created_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"gsac 搜索失败: {e}", exc_info=True)
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": "gsac",
                "success": False,
                "error": str(e),
                "created_at": datetime.now().isoformat(),
            }

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
                "engine_used": "nl_search",
                "success": True,
            }
        except Exception as e:
            logger.error(f"NL Search failed: {e}", exc_info=True)
            return {
                "log_id": None,
                "query_text": query,
                "search_mode": search_mode,
                "results": [],
                "engine_used": "nl_search",
                "success": False,
                "error": str(e),
                "created_at": datetime.now().isoformat(),
            }

    def get_engine_status(self) -> Dict[str, Any]:
        """获取搜索引擎状态

        Returns:
            引擎状态信息
        """
        gsac_status = None
        if self._gsac_engine is not None:
            gsac_status = self._gsac_engine.get_status()
        
        return {
            "configured_engine": self.config.engine,
            "gsac_available": gsac_status.get("available", False) if gsac_status else None,
            "gsac_status": gsac_status,
            "nl_search_available": self._nl_search_service is not None,
        }


# 全局适配器实例
search_engine_adapter = SearchEngineAdapter()
