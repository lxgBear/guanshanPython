"""
Chat API V2 端点 - 基于层分离架构

使用新的层分离架构重新实现 Chat 功能。

**核心改进**:
- 搜索层和AI层职责分离
- 支持并行执行 (wait=false)
- 事件驱动的层间通信
- 更清晰的代码结构

**架构**:
- SearchEngineLayer: 执行 LangGraph 搜索 → 存储到 langgraph_search_results
- AIProcessingLayer: 读取搜索结果 → 调用远程AI → 返回给前端
- ChatOrchestrator: 协调两个层的执行

**兼容性**:
- 完全兼容现有 /chat/sync API
- 新增 /chat/v2/sync 端点使用新架构
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from src.core.interfaces.layer import LayerContext, LayerStatus
from src.core.interfaces.orchestrator import ExecutionMode
from src.services.layers import SearchEngineLayer, AIProcessingLayer
from src.services.orchestrators import ChatOrchestrator, ChatOrchestratorConfig
from src.infrastructure.database.chat_task_repository import chat_task_repository
from src.core.domain.entities.auth.user import User
from src.api.dependencies.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局协调器实例（延迟初始化）
_orchestrator: Optional[ChatOrchestrator] = None


async def get_orchestrator() -> ChatOrchestrator:
    """获取协调器实例（单例）"""
    global _orchestrator
    if _orchestrator is None:
        config = ChatOrchestratorConfig(
            parallel_execution=True,
            search_timeout=300.0,
            ai_timeout=300.0,
        )
        _orchestrator = ChatOrchestrator(config=config)

        # 注册层
        search_layer = SearchEngineLayer()
        ai_layer = AIProcessingLayer()

        _orchestrator.register_layer(search_layer, priority=1)
        _orchestrator.register_layer(
            ai_layer,
            priority=2,
            dependencies=["search_engine"],
        )

        # 初始化
        await _orchestrator.initialize()

    return _orchestrator


# ==================== 数据模型 ====================

class HistoryMessage(BaseModel):
    """历史消息模型"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatV2Request(BaseModel):
    """Chat V2 请求模型"""
    question: str = Field(
        ...,
        description="用户提问（自然语言）",
        min_length=1,
        max_length=1000,
    )
    search_mode: str = Field(
        default="single",
        description="搜索模式: single=单次搜索, multi=多问题分解",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="对话会话ID（可选，用于多轮对话）",
    )
    history: Optional[List[HistoryMessage]] = Field(
        None,
        description="对话历史（可选）",
    )


class CategoryModel(BaseModel):
    """分类信息模型"""
    大类: str = "未分类"
    类别: str = "未分类"
    地域: str = "未知"


class SourceDetail(BaseModel):
    """来源详情模型"""
    id: str = ""
    mongo_id: str = ""
    title: str = ""
    source: str = ""
    score: float = 0.0
    category: CategoryModel = Field(default_factory=CategoryModel)
    publish_time: str = ""
    preview: str = ""
    url: Optional[str] = None
    title_zh: Optional[str] = None
    summary_zh: Optional[str] = None
    content_zh: Optional[str] = None


class ChatV2Response(BaseModel):
    """Chat V2 响应模型"""
    question: str
    answer: str
    sources: List[SourceDetail]
    sources_count: int
    status: str = "success"
    task_id: Optional[str] = None
    history_id: Optional[str] = None
    execution_mode: str = "parallel"
    execution_time_ms: int = 0


class TaskCreatedResponse(BaseModel):
    """任务创建响应"""
    task_id: str
    status: str = "pending"
    message: str = "任务已创建，正在后台处理"
    created_at: str


# ==================== API 端点 ====================

@router.post(
    "/sync",
    response_model=None,  # 根据 wait 参数返回不同类型：ChatV2Response 或 TaskCreatedResponse
    summary="同步搜索（V2 层分离架构）",
    responses={
        200: {
            "description": "成功响应",
            "content": {
                "application/json": {
                    "examples": {
                        "sync": {
                            "summary": "同步模式 (wait=true)",
                            "value": {
                                "question": "用户问题",
                                "answer": "AI回答",
                                "sources": [],
                                "sources_count": 0,
                                "status": "success",
                                "execution_mode": "sequential",
                                "execution_time_ms": 1000
                            }
                        },
                        "async": {
                            "summary": "异步模式 (wait=false)",
                            "value": {
                                "task_id": "123456",
                                "status": "pending",
                                "message": "任务已创建",
                                "created_at": "2026-01-14T00:00:00"
                            }
                        }
                    }
                }
            }
        }
    },
)
async def chat_sync_v2(
    request: ChatV2Request,
    background_tasks: BackgroundTasks,
    wait: bool = Query(True, description="是否等待完成"),
    skip_summary: bool = Query(False, description="是否跳过AI总结"),
    current_user: User = Depends(get_current_active_user),
):
    """
    基于层分离架构的同步搜索

    **执行流程**:
    1. 创建任务记录
    2. 如果 wait=false，立即返回任务ID，后台并行执行
    3. 如果 wait=true，等待执行完成后返回结果

    **架构优势**:
    - 搜索层和AI层职责分离，易于维护和扩展
    - 支持真正的并行执行
    - 事件驱动的层间通信
    """
    try:
        orchestrator = await get_orchestrator()

        logger.info(
            f"[ChatV2] Request: question='{request.question[:50]}...', "
            f"wait={wait}, user_id={current_user.id}"
        )

        # 创建任务记录
        task_id = await chat_task_repository.create_task(
            user_id=current_user.id,
            question=request.question,
            search_mode=request.search_mode,
            conversation_id=request.conversation_id,
        )
        logger.info(f"[ChatV2] Task created: task_id={task_id}")

        # 构建层执行上下文
        context = LayerContext(
            task_id=task_id,
            user_id=str(current_user.id),
            query=request.question,
            options={
                "search_mode": request.search_mode,
                "conversation_id": request.conversation_id,
                "history": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.history
                ] if request.history else None,
                "skip_summary": skip_summary,
            },
        )

        # 异步模式：立即返回，后台执行
        if not wait:
            background_tasks.add_task(
                _execute_in_background,
                orchestrator,
                context,
                task_id,
            )

            return TaskCreatedResponse(
                task_id=task_id,
                status="pending",
                message="任务已创建，正在后台处理。请通过 GET /chat/tasks/{task_id} 查询结果。",
                created_at=datetime.now().isoformat(),
            )

        # 同步模式：等待执行完成
        if skip_summary:
            # 仅搜索模式
            result = await orchestrator.execute_search_only(context)

            if result.status != LayerStatus.COMPLETED:
                raise HTTPException(
                    status_code=500,
                    detail=f"搜索失败: {result.error}",
                )

            # 更新任务状态
            await chat_task_repository.complete_task(
                task_id=task_id,
                result={
                    "question": request.question,
                    "sources_count": result.result_count,
                    "status": "search_only",
                },
            )

            # 转换来源数据
            sources = [
                _convert_source(s)
                for s in result.data.get("results", [])
            ]

            return ChatV2Response(
                question=request.question,
                answer="",
                sources=sources,
                sources_count=len(sources),
                status="search_only",
                task_id=task_id,
                execution_mode="search_only",
            )

        # 完整执行（搜索 + AI处理）
        mode = ExecutionMode.SEQUENTIAL  # 同步模式下使用串行执行

        result = await orchestrator.execute(context, mode=mode)

        if not result.is_success:
            error_msg = "; ".join(result.errors) if result.errors else "执行失败"
            raise HTTPException(status_code=500, detail=error_msg)

        # 获取AI层结果
        ai_result = result.get_layer_result("ai_processing")
        if not ai_result or not ai_result.result:
            raise HTTPException(status_code=500, detail="AI处理结果为空")

        # 更新任务状态
        await chat_task_repository.complete_task(
            task_id=task_id,
            result={
                "question": request.question,
                "answer": ai_result.result.answer,
                "sources_count": len(ai_result.result.sources),
                "status": "success",
            },
            history_id=ai_result.result.data.get("history_id"),
        )

        # 转换来源数据
        sources = [
            _convert_source(s)
            for s in ai_result.result.sources
        ]

        return ChatV2Response(
            question=request.question,
            answer=ai_result.result.answer,
            sources=sources,
            sources_count=len(sources),
            status="success",
            task_id=task_id,
            history_id=ai_result.result.data.get("history_id"),
            execution_mode=mode.value,
            execution_time_ms=result.total_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatV2] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/stream",
    summary="流式搜索（V2 层分离架构）",
)
async def chat_stream_v2(
    request: ChatV2Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    流式搜索 - 实时返回AI处理结果

    使用 Server-Sent Events (SSE) 实时返回：
    - 搜索进度
    - AI回答片段
    - 来源信息
    """
    try:
        orchestrator = await get_orchestrator()

        logger.info(
            f"[ChatV2] Stream request: question='{request.question[:50]}...', "
            f"user_id={current_user.id}"
        )

        # 创建任务记录
        task_id = await chat_task_repository.create_task(
            user_id=current_user.id,
            question=request.question,
            search_mode=request.search_mode,
            conversation_id=request.conversation_id,
        )

        # 构建层执行上下文
        context = LayerContext(
            task_id=task_id,
            user_id=str(current_user.id),
            query=request.question,
            options={
                "search_mode": request.search_mode,
                "conversation_id": request.conversation_id,
                "history": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.history
                ] if request.history else None,
            },
        )

        async def generate():
            """生成SSE流"""
            try:
                async for event in orchestrator.stream(
                    context,
                    mode=ExecutionMode.SEQUENTIAL,
                ):
                    yield event.to_sse_string()
            except Exception as e:
                from src.core.interfaces.ai_layer import SSEEvent
                yield SSEEvent.error(str(e), "stream_error").to_sse_string()
                yield SSEEvent.stream_end("error").to_sse_string()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        logger.error(f"[ChatV2] Stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/health",
    summary="健康检查",
)
async def health_check():
    """检查所有层的健康状态"""
    try:
        orchestrator = await get_orchestrator()
        health_status = await orchestrator.health_check()

        all_healthy = all(health_status.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "layers": health_status,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 辅助函数 ====================

async def _execute_in_background(
    orchestrator: ChatOrchestrator,
    context: LayerContext,
    task_id: str,
):
    """后台执行任务"""
    try:
        logger.info(f"[ChatV2] Background execution started: task_id={task_id}")

        # 使用并行模式执行
        result = await orchestrator.execute(context, mode=ExecutionMode.PARALLEL)

        # 获取AI层结果
        ai_result = result.get_layer_result("ai_processing")

        if result.is_success and ai_result and ai_result.result:
            await chat_task_repository.complete_task(
                task_id=task_id,
                result={
                    "question": context.query,
                    "answer": ai_result.result.answer,
                    "sources": ai_result.result.sources,  # 添加 sources 字段
                    "sources_count": len(ai_result.result.sources),
                    "status": "success",
                },
                history_id=ai_result.result.data.get("history_id"),
            )
            logger.info(f"[ChatV2] Background execution completed: task_id={task_id}")
        else:
            error_msg = "; ".join(result.errors) if result.errors else "执行失败"
            await chat_task_repository.fail_task(
                task_id=task_id,
                error_message=error_msg,
            )
            logger.error(f"[ChatV2] Background execution failed: task_id={task_id}, error={error_msg}")

    except Exception as e:
        logger.error(f"[ChatV2] Background execution error: task_id={task_id}, error={e}")
        await chat_task_repository.fail_task(
            task_id=task_id,
            error_message=str(e),
        )


def _convert_source(source: Dict[str, Any]) -> SourceDetail:
    """转换来源数据为响应模型"""
    category_data = source.get("category", {})
    if isinstance(category_data, dict):
        category = CategoryModel(
            大类=category_data.get("大类", "未分类"),
            类别=category_data.get("类别", "未分类"),
            地域=category_data.get("地域", "未知"),
        )
    else:
        category = CategoryModel()

    return SourceDetail(
        id=source.get("id", ""),
        mongo_id=source.get("mongo_id", ""),
        title=source.get("title", ""),
        source=source.get("source", ""),
        score=source.get("score", 0.0),
        category=category,
        publish_time=source.get("publish_time", ""),
        preview=source.get("preview", ""),
        url=source.get("url"),
        title_zh=source.get("title_zh"),
        summary_zh=source.get("summary_zh"),
        content_zh=source.get("content_zh"),
    )
