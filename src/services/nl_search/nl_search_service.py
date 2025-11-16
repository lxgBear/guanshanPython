"""
NL Search 核心服务
用于编排整个自然语言搜索流程

版本: v1.0.0-beta
日期: 2025-11-16
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.services.nl_search.config import nl_search_config
from src.services.nl_search.llm_processor import LLMProcessor
from src.services.nl_search.gpt5_search_adapter import GPT5SearchAdapter
from src.infrastructure.database.nl_search_repositories import NLSearchLogRepository
from src.core.domain.entities.nl_search import NLSearchLog

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
        self.repository = NLSearchLogRepository()

        logger.info("NLSearchService 初始化完成")

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

            # 7. 构建返回结果
            result = {
                "log_id": log_id,
                "query_text": query_text,
                "analysis": analysis,
                "refined_query": refined_query,
                "results": [r.to_dict() for r in search_results],
                "created_at": datetime.now().isoformat()
            }

            logger.info(f"搜索流程完成: log_id={log_id}")
            return result

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            # 不重新抛出，让API层处理
            raise

    async def get_search_log(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        获取搜索记录

        Args:
            log_id: 搜索记录ID

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
                "log_id": log.id,
                "query_text": log.query_text,
                "analysis": log.llm_analysis,
                "created_at": log.created_at.isoformat() if log.created_at else None
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
                    "log_id": log.id,
                    "query_text": log.query_text,
                    "analysis": log.llm_analysis,
                    "created_at": log.created_at.isoformat() if log.created_at else None
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
                    "log_id": log.id,
                    "query_text": log.query_text,
                    "analysis": log.llm_analysis,
                    "created_at": log.created_at.isoformat() if log.created_at else None
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
            "llm_configured": bool(self.llm_processor.llm_client),
            "search_configured": bool(self.gpt5_adapter.api_key or self.gpt5_adapter.test_mode),
            "test_mode": self.gpt5_adapter.test_mode,
            "version": "1.0.0-beta"
        }


# 创建全局服务实例（单例模式）
nl_search_service = NLSearchService()
