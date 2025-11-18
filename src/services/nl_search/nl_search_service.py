"""
NL Search 核心服务
用于编排整个自然语言搜索流程

版本: v2.0.0 (MongoDB)
日期: 2025-11-17
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.services.nl_search.config import nl_search_config
from src.services.nl_search.llm_processor import LLMProcessor
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter
from src.infrastructure.database.mongo_nl_search_repository import MongoNLSearchLogRepository
from src.infrastructure.database.user_selection_repository import user_selection_repository

logger = logging.getLogger(__name__)


class NLSearchService:
    """
    自然语言搜索核心服务

    职责:
    1. 编排整个搜索流程
    2. 调用LLM解析用户查询
    3. 调用搜索适配器执行搜索
    4. 保存搜索记录到数据库
    5. 返回完整的搜索结果

    使用示例:
        service = NLSearchService()
        result = await service.create_search(
            query_text="最近有哪些AI技术突破",
            user_id="user_123"
        )
    """

    def __init__(self):
        """初始化服务"""
        # 初始化各个组件
        self.llm_processor = LLMProcessor()
        self.gpt5_adapter = GPT5SearchAdapter(
            test_mode=not nl_search_config.enabled  # 功能关闭时使用测试模式
        )
        self.repository = MongoNLSearchLogRepository()
        self.selection_repository = user_selection_repository

        logger.info("NLSearchService 初始化完成 (MongoDB)")

    async def create_search(
        self,
        query_text: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建自然语言搜索

        流程:
        1. 验证输入
        2. 创建搜索记录
        3. LLM解析查询
        4. 更新分析结果
        5. 精炼查询
        6. 执行搜索
        7. 返回结果

        Args:
            query_text: 用户输入的自然语言查询
            user_id: 用户ID（可选）

        Returns:
            包含搜索结果的字典:
            {
                "log_id": int,
                "query_text": str,
                "analysis": dict,
                "refined_query": str,
                "results": list,
                "created_at": datetime
            }

        Raises:
            ValueError: 输入验证失败
            Exception: 搜索过程中的其他错误
        """
        # 1. 验证输入
        if not query_text or not query_text.strip():
            raise ValueError("查询文本不能为空")

        query_text = query_text.strip()
        logger.info(f"开始处理自然语言搜索: {query_text[:50]}...")

        try:
            # 2. 创建搜索记录
            log_id = await self.repository.create(
                query_text=query_text,
                llm_analysis=None
            )
            logger.info(f"创建搜索记录: log_id={log_id}")

            # 3. LLM解析查询
            logger.info("调用LLM解析查询...")
            analysis = await self.llm_processor.parse_query(query_text)
            logger.info(f"LLM解析完成: intent={analysis.get('intent')}, "
                       f"keywords={analysis.get('keywords')}")

            # 4. 更新分析结果
            await self.repository.update_llm_analysis(
                log_id=log_id,
                llm_analysis=analysis
            )
            logger.info("分析结果已保存")

            # 5. 精炼查询
            refined_query = await self.llm_processor.refine_query(query_text)
            logger.info(f"精炼后的查询: {refined_query}")

            # 6. 执行搜索
            logger.info("开始执行搜索...")
            search_results = await self.gpt5_adapter.search(
                query=refined_query,
                max_results=nl_search_config.max_results_per_query
            )
            logger.info(f"搜索完成: 获得{len(search_results)}个结果")

            # 🆕 7. 保存搜索结果到数据库
            results_dict = [r.to_dict() for r in search_results]
            await self.repository.update_search_results(
                log_id=log_id,
                search_results=results_dict,
                results_count=len(search_results)
            )
            logger.info(f"搜索结果已保存: log_id={log_id}")

            # 8. 构建返回结果
            result = {
                "log_id": log_id,
                "query_text": query_text,
                "analysis": analysis,
                "refined_query": refined_query,
                "results": results_dict,
                "created_at": datetime.now().isoformat()
            }

            logger.info(f"搜索流程完成: log_id={log_id}")
            return result

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            # 不重新抛出，让API层处理
            raise

    async def get_search_log(self, log_id: str) -> Optional[Dict[str, Any]]:
        """
        获取搜索记录

        Args:
            log_id: 搜索记录ID（雪花算法ID字符串）

        Returns:
            搜索记录字典，如果不存在返回None
        """
        logger.info(f"获取搜索记录: log_id={log_id}")

        try:
            log = await self.repository.get_by_id(log_id)

            if not log:
                logger.warning(f"搜索记录不存在: log_id={log_id}")
                return None

            return {
                "log_id": log["_id"],
                "query_text": log["query_text"],
                "analysis": log.get("llm_analysis"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }

        except Exception as e:
            logger.error(f"获取搜索记录失败: {e}", exc_info=True)
            raise

    async def list_search_logs(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出搜索历史

        Args:
            limit: 返回数量限制
            offset: 分页偏移量

        Returns:
            搜索记录列表
        """
        logger.info(f"查询搜索历史: limit={limit}, offset={offset}")

        try:
            logs = await self.repository.get_recent(limit=limit, offset=offset)

            results = [
                {
                    "log_id": log["_id"],
                    "query_text": log["query_text"],
                    "analysis": log.get("llm_analysis"),
                    "created_at": log["created_at"].isoformat() if log.get("created_at") else None
                }
                for log in logs
            ]

            logger.info(f"返回{len(results)}条搜索记录")
            return results

        except Exception as e:
            logger.error(f"查询搜索历史失败: {e}", exc_info=True)
            raise

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        根据关键词搜索历史记录

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            匹配的搜索记录列表
        """
        logger.info(f"根据关键词搜索: keyword={keyword}")

        try:
            logs = await self.repository.search_by_keyword(
                keyword=keyword,
                limit=limit
            )

            results = [
                {
                    "log_id": log["_id"],
                    "query_text": log["query_text"],
                    "analysis": log.get("llm_analysis"),
                    "created_at": log["created_at"].isoformat() if log.get("created_at") else None
                }
                for log in logs
            ]

            logger.info(f"找到{len(results)}条匹配记录")
            return results

        except Exception as e:
            logger.error(f"关键词搜索失败: {e}", exc_info=True)
            raise

    async def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态

        Returns:
            服务状态信息
        """
        return {
            "enabled": nl_search_config.enabled,
            "llm_configured": bool(self.llm_processor.client),
            "search_configured": bool(self.gpt5_adapter.api_key or self.gpt5_adapter.test_mode),
            "test_mode": self.gpt5_adapter.test_mode,
            "version": "1.0.0-beta"
        }

    async def get_search_results(
        self,
        log_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        获取搜索结果

        Args:
            log_id: 搜索记录ID（雪花算法ID字符串）
            limit: 返回数量限制（可选）
            offset: 分页偏移量（默认 0）

        Returns:
            Optional[Dict]: 搜索结果数据，不存在时返回 None

        Example:
            >>> result = await service.get_search_results("248728141926559744")
            >>> print(f"共 {result['total_count']} 条结果")
            >>> for item in result['results']:
            ...     print(item['title'])
        """
        logger.info(f"获取搜索结果: log_id={log_id}")

        try:
            # 1. 获取搜索记录（包含基本信息）
            log = await self.repository.get_by_id(log_id)
            if not log:
                logger.warning(f"搜索记录不存在: log_id={log_id}")
                return None

            # 2. 获取搜索结果
            search_results = await self.repository.get_search_results(log_id)
            if search_results is None:
                logger.warning(f"搜索结果不存在: log_id={log_id}")
                return None

            # 3. 分页处理
            total_count = len(search_results)
            if limit is not None:
                search_results = search_results[offset:offset + limit]

            # 4. 构建响应
            return {
                "log_id": log_id,
                "query_text": log["query_text"],
                "total_count": total_count,
                "results": search_results,
                "llm_analysis": log.get("llm_analysis"),
                "status": log.get("status", "completed"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None
            }

        except Exception as e:
            logger.error(f"获取搜索结果失败: {e}", exc_info=True)
            raise

    async def record_user_selection(
        self,
        log_id: str,
        result_url: str,
        action_type: str,
        user_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        记录用户选择事件

        Args:
            log_id: 搜索记录ID
            result_url: 选中的结果URL
            action_type: 操作类型（click, bookmark, archive）
            user_id: 用户ID（可选）
            user_agent: 用户代理字符串（可选）
            ip_address: 客户端IP地址（可选）

        Returns:
            str: 事件ID

        Raises:
            ValueError: 搜索记录不存在

        Example:
            >>> event_id = await service.record_user_selection(
            ...     log_id="248728141926559744",
            ...     result_url="https://example.com/gpt5",
            ...     action_type="click"
            ... )
        """
        logger.info(
            f"记录用户选择: log_id={log_id}, "
            f"url={result_url}, action={action_type}"
        )

        try:
            # 1. 验证搜索记录存在
            log = await self.repository.get_by_id(log_id)
            if not log:
                raise ValueError(f"搜索记录不存在: log_id={log_id}")

            # 2. 创建选择事件
            event_id = await self.selection_repository.create(
                log_id=log_id,
                result_url=result_url,
                action_type=action_type,
                user_id=user_id,
                user_agent=user_agent,
                ip_address=ip_address
            )

            logger.info(f"用户选择已记录: event_id={event_id}")
            return event_id

        except Exception as e:
            logger.error(f"记录用户选择失败: {e}", exc_info=True)
            raise

    async def get_selection_statistics(
        self,
        log_id: str
    ) -> Dict[str, Any]:
        """
        获取用户选择统计

        Args:
            log_id: 搜索记录ID

        Returns:
            Dict: 统计数据

        Example:
            >>> stats = await service.get_selection_statistics("248728141926559744")
            >>> print(f"总点击数: {stats['total_clicks']}")
        """
        logger.info(f"获取选择统计: log_id={log_id}")

        try:
            # 获取所有选择事件
            events = await self.selection_repository.get_by_log_id(log_id)

            # 统计数据
            total_count = len(events)
            click_count = sum(1 for e in events if e["action_type"] == "click")
            bookmark_count = sum(1 for e in events if e["action_type"] == "bookmark")
            archive_count = sum(1 for e in events if e["action_type"] == "archive")

            # 统计 URL 点击次数
            url_clicks = {}
            for event in events:
                url = event["result_url"]
                url_clicks[url] = url_clicks.get(url, 0) + 1

            return {
                "log_id": log_id,
                "total_count": total_count,
                "click_count": click_count,
                "bookmark_count": bookmark_count,
                "archive_count": archive_count,
                "top_urls": sorted(
                    url_clicks.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]  # 前5个最热门URL
            }

        except Exception as e:
            logger.error(f"获取选择统计失败: {e}", exc_info=True)
            raise


# 创建全局服务实例（单例模式）
nl_search_service = NLSearchService()
