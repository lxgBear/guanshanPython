"""Chat 搜索服务

封装要素提取和确认流程，提供两阶段搜索功能。

v4.20.0 - 添加 gsac 搜索要素确认功能

使用流程:
1. extract_elements() - 提取搜索要素，返回待确认任务
2. confirm_and_execute() - 确认要素并执行搜索
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from src.core.domain.entities.chat_search_elements import ChatSearchElements
from src.infrastructure.database.chat_task_repository import (
    ChatTaskRepository,
    chat_task_repository,
)
from src.services.query_analyzer import get_unified_analyzer, UnifiedQueryAnalyzer
from src.core.interfaces.layer import LayerContext, LayerStatus
from src.services.layers import SearchEngineLayer

logger = logging.getLogger(__name__)


class ChatSearchService:
    """Chat 搜索服务

    封装要素提取和确认流程，提供统一的搜索接口。

    Example:
        service = ChatSearchService()

        # 阶段1: 提取要素
        task_id, elements = await service.extract_elements(
            question="请检索西方主流媒体关于四川阿坝红旗大桥垮塌的报道",
            user_id=123
        )

        # 阶段2: 确认并执行
        result = await service.confirm_and_execute(
            task_id=task_id,
            confirmed_elements=elements,
            user_id=123
        )
    """

    def __init__(
        self,
        task_repo: Optional[ChatTaskRepository] = None,
        analyzer: Optional[UnifiedQueryAnalyzer] = None,
        search_layer: Optional[SearchEngineLayer] = None,
    ):
        """初始化服务

        Args:
            task_repo: 任务仓库实例
            analyzer: 查询分析器实例
            search_layer: 搜索层实例
        """
        self.task_repo = task_repo or chat_task_repository
        self._analyzer = analyzer
        self._search_layer = search_layer

    @property
    def analyzer(self) -> UnifiedQueryAnalyzer:
        """延迟加载查询分析器"""
        if self._analyzer is None:
            self._analyzer = get_unified_analyzer()
        return self._analyzer

    @property
    def search_layer(self) -> SearchEngineLayer:
        """延迟加载搜索层"""
        if self._search_layer is None:
            self._search_layer = SearchEngineLayer()
        return self._search_layer

    async def extract_elements(
        self,
        question: str,
        user_id: int,
        search_mode: str = "single",
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, ChatSearchElements]:
        """提取搜索要素

        调用 LLM 分析用户问题，提取搜索要素，创建待确认任务。

        Args:
            question: 用户问题
            user_id: 用户ID
            search_mode: 搜索模式 (single/multi)
            conversation_id: 对话会话ID
            metadata: 额外元数据

        Returns:
            (task_id, elements): 任务ID和提取的要素

        Raises:
            Exception: LLM 调用失败时抛出异常
        """
        logger.info(f"[ChatSearchService] 开始提取要素: user_id={user_id}, question={question[:50]}...")

        # 1. 创建任务 (status = awaiting_confirmation)
        task_id = await self.task_repo.create_task_with_confirmation(
            user_id=user_id,
            question=question,
            search_mode=search_mode,
            conversation_id=conversation_id,
            metadata=metadata or {},
        )
        logger.info(f"[ChatSearchService] 创建任务: task_id={task_id}")

        try:
            # 2. 调用 UnifiedQueryAnalyzer 分析
            decomposition = await self.analyzer.analyze(question)
            logger.info(f"[ChatSearchService] LLM 分析完成: keywords={decomposition.keywords}")

            # 3. 转换为 ChatSearchElements
            elements = ChatSearchElements.from_enhanced_decomposition(
                decomp=decomposition,
                original_query=question,
            )

            # 4. 保存到任务
            await self.task_repo.update_extracted_elements(
                task_id=task_id,
                elements=elements.to_dict(),
            )

            logger.info(
                f"[ChatSearchService] 要素提取完成: task_id={task_id}, "
                f"keywords={len(elements.keywords)}, time_range={elements.time_range}"
            )

            return task_id, elements

        except Exception as e:
            # 提取失败，标记任务失败
            logger.error(f"[ChatSearchService] 要素提取失败: {e}", exc_info=True)
            await self.task_repo.fail_task(
                task_id=task_id,
                error_message=f"要素提取失败: {str(e)}",
                error_details={"stage": "extract_elements"},
            )
            raise

    async def confirm_and_execute(
        self,
        task_id: str,
        confirmed_elements: ChatSearchElements,
        user_id: int,
    ) -> Dict[str, Any]:
        """确认要素并执行搜索（同步版本）

        验证任务状态，保存确认要素，执行 gsac 搜索。

        Args:
            task_id: 任务ID
            confirmed_elements: 用户确认的要素
            user_id: 用户ID

        Returns:
            搜索结果

        Raises:
            ValueError: 任务不存在或状态不正确
            Exception: 搜索执行失败
        """
        logger.info(f"[ChatSearchService] 开始确认执行: task_id={task_id}")

        # 1. 验证任务状态
        task = await self.task_repo.get_task_by_user(task_id, user_id)
        if not task:
            raise ValueError(f"任务不存在或无权访问: {task_id}")

        if task["status"] != ChatTaskRepository.STATUS_AWAITING_CONFIRMATION:
            raise ValueError(
                f"任务状态不是 awaiting_confirmation: {task['status']}"
            )

        # 2. 保存确认要素
        await self.task_repo.update_confirmed_elements(
            task_id=task_id,
            elements=confirmed_elements.to_dict(),
        )

        # 3. 更新状态为 searching
        await self.task_repo.update_status(
            task_id=task_id,
            status=ChatTaskRepository.STATUS_SEARCHING,
            progress_message="正在执行搜索...",
            progress_percentage=20,
        )

        try:
            # 4. 执行搜索
            result = await self._execute_search(task, confirmed_elements)

            # 5. 完成任务
            await self.task_repo.complete_task(
                task_id=task_id,
                result=result,
            )

            logger.info(
                f"[ChatSearchService] 搜索完成: task_id={task_id}, "
                f"results={result.get('result_count', 0)}"
            )

            return result

        except Exception as e:
            logger.error(f"[ChatSearchService] 搜索执行失败: {e}", exc_info=True)
            await self.task_repo.fail_task(
                task_id=task_id,
                error_message=f"搜索执行失败: {str(e)}",
                error_details={"stage": "confirm_and_execute"},
            )
            raise

    async def prepare_for_async_execution(
        self,
        task_id: str,
        confirmed_elements: ChatSearchElements,
        user_id: int,
    ) -> Dict[str, Any]:
        """准备异步执行（v4.21.0）

        验证任务状态，保存确认要素，更新状态为 searching。
        此方法用于异步执行前的准备工作，不执行实际搜索。

        Args:
            task_id: 任务ID
            confirmed_elements: 用户确认的要素
            user_id: 用户ID

        Returns:
            任务信息

        Raises:
            ValueError: 任务不存在或状态不正确
        """
        logger.info(f"[ChatSearchService] 准备异步执行: task_id={task_id}")

        # 1. 验证任务状态
        task = await self.task_repo.get_task_by_user(task_id, user_id)
        if not task:
            raise ValueError(f"任务不存在或无权访问: {task_id}")

        if task["status"] != ChatTaskRepository.STATUS_AWAITING_CONFIRMATION:
            raise ValueError(
                f"任务状态不是 awaiting_confirmation: {task['status']}"
            )

        # 2. 保存确认要素
        await self.task_repo.update_confirmed_elements(
            task_id=task_id,
            elements=confirmed_elements.to_dict(),
        )

        # 3. 更新状态为 searching
        await self.task_repo.update_status(
            task_id=task_id,
            status=ChatTaskRepository.STATUS_SEARCHING,
            progress_message="搜索任务已启动，正在后台执行...",
            progress_percentage=10,
        )

        logger.info(f"[ChatSearchService] 异步执行准备完成: task_id={task_id}")
        return task

    async def execute_search_only(
        self,
        task_id: str,
        confirmed_elements: ChatSearchElements,
        user_id: int,
    ) -> Dict[str, Any]:
        """仅执行搜索（v4.21.0）

        用于异步后台执行搜索，不做状态验证（已在 prepare_for_async_execution 中完成）。

        Args:
            task_id: 任务ID
            confirmed_elements: 用户确认的要素
            user_id: 用户ID

        Returns:
            搜索结果
        """
        logger.info(f"[ChatSearchService] 开始后台搜索: task_id={task_id}")

        try:
            # 获取任务信息
            task = await self.task_repo.get_task_by_user(task_id, user_id)
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            # 执行搜索
            result = await self._execute_search(task, confirmed_elements)

            # 完成任务
            await self.task_repo.complete_task(
                task_id=task_id,
                result=result,
            )

            logger.info(
                f"[ChatSearchService] 后台搜索完成: task_id={task_id}, "
                f"results={result.get('result_count', 0)}"
            )

            return result

        except Exception as e:
            logger.error(f"[ChatSearchService] 后台搜索失败: {e}", exc_info=True)
            await self.task_repo.fail_task(
                task_id=task_id,
                error_message=f"搜索执行失败: {str(e)}",
                error_details={"stage": "execute_search_only"},
            )
            raise

    async def _execute_search(
        self,
        task: Dict[str, Any],
        elements: ChatSearchElements,
    ) -> Dict[str, Any]:
        """执行搜索

        使用 SearchEngineLayer 执行 gsac 搜索。

        Args:
            task: 任务文档
            elements: 确认的搜索要素

        Returns:
            搜索结果
        """
        # 初始化搜索层
        await self.search_layer.initialize()

        # 构建搜索查询
        query = elements.build_search_query()
        if not query:
            query = task["question"]

        # 构建搜索上下文
        context = LayerContext(
            task_id=task["_id"],
            user_id=str(task["user_id"]),
            query=query,
            options={
                "confirmed_elements": elements.to_dict(),
                "conversation_id": task.get("conversation_id"),
                **elements.to_gsac_options(),
            },
        )

        # 执行搜索
        search_result = await self.search_layer.execute(context)

        if search_result.status == LayerStatus.FAILED:
            raise Exception(search_result.error or "搜索失败")

        # 构建返回结果
        return {
            "task_id": task["_id"],
            "status": "completed",
            "result_count": search_result.result_count,
            "results": [r.to_dict() if hasattr(r, "to_dict") else r for r in search_result.results],
            "statistics": search_result.statistics.to_dict() if search_result.statistics else {},
            "search_elements": elements.to_dict(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def get_task_with_elements(
        self,
        task_id: str,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """获取任务详情（包含要素）

        Args:
            task_id: 任务ID
            user_id: 用户ID

        Returns:
            任务详情字典，包含 extracted_elements 和 confirmed_elements
        """
        task = await self.task_repo.get_task_by_user(task_id, user_id)
        if not task:
            return None

        # 转换要素为实体对象（如果存在）
        if task.get("extracted_elements"):
            task["extracted_elements_obj"] = ChatSearchElements.from_dict(
                task["extracted_elements"]
            )
        if task.get("confirmed_elements"):
            task["confirmed_elements_obj"] = ChatSearchElements.from_dict(
                task["confirmed_elements"]
            )

        return task


# 单例工厂函数
_service_instance: Optional[ChatSearchService] = None


def get_chat_search_service() -> ChatSearchService:
    """获取 ChatSearchService 单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ChatSearchService()
    return _service_instance
