"""LangGraph 到 news_results 的批量转移服务

v4.5.3 新增：将用户选择的 LangGraph 搜索结果批量转移到 news_results 表
供 AI 微服务处理。

v4.5.5 更新：
- 转移成功后标记源记录 transferred_to_news=True
- 记录转移时间 transferred_at

功能：
- 从 langgraph_search_results 读取用户选择的数据
- 转换为 ProcessedResult 格式保存到 news_results
- 标记数据来源为 langgraph
- 保持 LangGraph 特有字段（layer, category, scores）
- 标记已转移的源记录避免重复转移
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from src.utils.logger import get_logger
from src.core.domain.entities.langgraph_search_result import LangGraphSearchResult
from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus, NewsResultsDict
from src.infrastructure.id_generator import generate_string_id

logger = get_logger(__name__)


class LangGraphTransferService:
    """LangGraph 到 news_results 的批量转移服务

    v4.5.3 新增

    职责：
    1. 从 langgraph_search_results 批量读取数据
    2. 转换为 ProcessedResult 实体
    3. 保存到 news_results 表供 AI 微服务处理
    4. 标记转移状态
    """

    def __init__(self):
        """初始化转移服务"""
        self.langgraph_repo = None
        self.processed_repo = None

    async def _get_repositories(self):
        """延迟加载仓储（避免循环导入）"""
        if self.langgraph_repo is None:
            from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
                MongoLangGraphResultRepository
            )
            from src.infrastructure.persistence.repositories.mongo.processed_result_repository import (
                MongoProcessedResultRepository
            )
            self.langgraph_repo = MongoLangGraphResultRepository()
            self.processed_repo = MongoProcessedResultRepository()

    async def transfer_by_ids(
        self,
        result_ids: List[str],
        user_id: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """根据 ID 列表批量转移 LangGraph 结果到 news_results

        Args:
            result_ids: LangGraph 结果 ID 列表
            user_id: 用户 ID
            task_id: 目标任务 ID（可选，用于组织转移后的数据）

        Returns:
            转移统计: {
                "success": true,
                "transferred": 10,
                "failed": 0,
                "total": 10,
                "processed_ids": ["id1", "id2", ...],
                "errors": []
            }
        """
        await self._get_repositories()

        if not result_ids:
            return {
                "success": True,
                "transferred": 0,
                "failed": 0,
                "total": 0,
                "processed_ids": [],
                "errors": []
            }

        logger.info(f"[user:{user_id}] 开始批量转移 {len(result_ids)} 条 LangGraph 结果")

        transferred = []
        failed = []
        errors = []

        for result_id in result_ids:
            try:
                # 1. 从 langgraph_search_results 读取数据
                langgraph_result = await self.langgraph_repo.get_by_id(result_id)

                if not langgraph_result:
                    logger.warning(f"LangGraph 结果不存在: {result_id}")
                    failed.append(result_id)
                    errors.append({"id": result_id, "error": "结果不存在"})
                    continue

                # 2. 转换为 ProcessedResult
                processed_result = self._to_processed_result(
                    langgraph_result,
                    user_id,
                    task_id or langgraph_result.task_id
                )

                # 3. 保存到 news_results
                processed_id = await self.processed_repo.create(processed_result)

                # 4. v4.5.5: 标记源记录已转移
                langgraph_result.transferred_to_news = True
                langgraph_result.transferred_at = datetime.utcnow()
                await self.langgraph_repo.update(langgraph_result)

                logger.info(
                    f"转移成功: {result_id} -> {processed_id} "
                    f"({langgraph_result.title[:50]})"
                )
                transferred.append(processed_id)

            except Exception as e:
                logger.error(f"转移失败: {result_id} - {e}")
                failed.append(result_id)
                errors.append({"id": result_id, "error": str(e)})

        logger.info(
            f"[user:{user_id}] 转移完成: "
            f"成功{len(transferred)}条, 失败{len(failed)}条"
        )

        return {
            "success": len(failed) == 0,
            "transferred": len(transferred),
            "failed": len(failed),
            "total": len(result_ids),
            "processed_ids": transferred,
            "failed_ids": failed,
            "errors": errors
        }

    async def transfer_by_task(
        self,
        task_id: str,
        user_id: str,
        layer: Optional[int] = None,
        min_score: Optional[float] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """根据任务 ID 批量转移 LangGraph 结果

        Args:
            task_id: LangGraph 任务 ID
            user_id: 用户 ID
            layer: 筛选特定层级（可选）
            min_score: 最低分数筛选（可选）
            limit: 最大转移数量（可选）

        Returns:
            转移统计
        """
        await self._get_repositories()

        # 查询符合条件的 LangGraph 结果
        if layer is not None:
            results = await self.langgraph_repo.find_by_task_and_layer(
                task_id, layer, limit
            )
        else:
            results = await self.langgraph_repo.find_by_task_id(task_id, limit)

        # 按分数筛选
        if min_score is not None:
            results = [r for r in results if r.final_score >= min_score]

        if not results:
            return {
                "success": True,
                "transferred": 0,
                "failed": 0,
                "total": 0,
                "message": "没有符合条件的结果"
            }

        # 批量转移
        result_ids = [str(r.id) for r in results]
        return await self.transfer_by_ids(result_ids, user_id, task_id)

    def _to_processed_result(
        self,
        langgraph_result: LangGraphSearchResult,
        user_id: str,
        task_id: str
    ) -> ProcessedResult:
        """将 LangGraphSearchResult 转换为 ProcessedResult

        Args:
            langgraph_result: LangGraph 搜索结果
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            ProcessedResult 实体
        """
        # 构建 NewsResultsDict（如果 LangGraph 有分类信息）
        news_results: Optional[NewsResultsDict] = None
        if langgraph_result.category:
            news_results = NewsResultsDict(
                title=langgraph_result.title,
                published_at=langgraph_result.article_published_time,
                source=langgraph_result.source,
                content=langgraph_result.markdown_content or langgraph_result.snippet or "",
                category=langgraph_result.category,
                media_urls=[]  # LangGraph 暂不提取媒体资源
            )

        # 将 LangGraph 特有字段存入 metadata
        metadata = {
            **(langgraph_result.metadata or {}),
            "langgraph": {
                "layer": langgraph_result.layer,
                "layer_name": langgraph_result.layer_name,
                "source_tier": langgraph_result.source_tier,
                "credibility_score": langgraph_result.credibility_score,
                "final_score": langgraph_result.final_score,
                "data_source_type": langgraph_result.data_source_type,
                "multi_source_bonus": langgraph_result.multi_source_bonus,
                "recency_bonus": langgraph_result.recency_bonus,
                "layer_weight": langgraph_result.layer_weight,
            }
        }

        # 创建 ProcessedResult
        processed_result = ProcessedResult(
            id=generate_string_id(),
            raw_result_id=str(langgraph_result.id),  # 关联原始 LangGraph 结果 ID
            task_id=task_id,

            # 原始字段（从 LangGraph 复制）
            title=langgraph_result.title,
            url=langgraph_result.url,
            source_url=langgraph_result.source_url or langgraph_result.url,
            content=langgraph_result.markdown_content or langgraph_result.snippet or "",
            snippet=langgraph_result.snippet,
            markdown_content=langgraph_result.markdown_content,
            html_content=langgraph_result.html_content,
            author=langgraph_result.author,
            published_date=langgraph_result.published_date,
            language=langgraph_result.language,
            source=langgraph_result.source,
            metadata=metadata,
            quality_score=langgraph_result.quality_score,
            relevance_score=langgraph_result.relevance_score,
            search_position=langgraph_result.search_position,

            # LangGraph 分类信息映射到 cls_results
            cls_results=langgraph_result.category,

            # news_results 嵌套字段
            news_results=news_results,

            # 处理状态（设为待 AI 处理）
            status=ProcessedStatus.PENDING,
            processing_status="pending",

            # 时间戳
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),

            # 从 LangGraph 继承的状态
            is_test_data=langgraph_result.is_test_data,
        )

        return processed_result


# 单例实例
langgraph_transfer_service = LangGraphTransferService()
