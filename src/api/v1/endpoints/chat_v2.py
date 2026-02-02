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
from typing import Optional, List, Dict, Any, Union
import logging
import asyncio
from datetime import datetime

from src.core.interfaces.layer import LayerContext, LayerStatus
from src.core.interfaces.orchestrator import ExecutionMode
from src.services.layers import SearchEngineLayer, AIProcessingLayer
from src.services.orchestrators import ChatOrchestrator, ChatOrchestratorConfig
from src.infrastructure.database.chat_task_repository import chat_task_repository
from src.infrastructure.database.chat_conversation_repository import chat_conversation_repository
from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
    mongo_langgraph_result_repository,
)
from src.core.domain.entities.auth.user import User
from src.api.dependencies.auth import get_current_active_user
from src.services.chat_search_service import get_chat_search_service
from src.core.domain.entities.chat_search_elements import ChatSearchElements

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


# ==================== 要素确认相关模型 (v4.20.0) ====================

class ChatSearchElementsModel(BaseModel):
    """搜索要素模型 - 用于要素确认流程"""
    keywords: List[str] = Field(default_factory=list, description="中文关键词列表")
    keywords_en: List[str] = Field(default_factory=list, description="英文关键词列表")
    time_range: Optional[str] = Field(None, description="时间范围 (qdr:d, qdr:w, qdr:m, qdr:y)")
    source_preferences: List[str] = Field(default_factory=list, description="来源偏好列表")
    languages: List[str] = Field(default_factory=lambda: ["zh", "en"], description="搜索语言")
    search_strategy: Dict[str, Any] = Field(default_factory=dict, description="搜索策略配置")
    summary: str = Field(default="", description="事件简要描述")
    event_type: str = Field(default="", description="事件类型")
    llm_reasoning: str = Field(default="", description="LLM 分析理由")
    original_query: str = Field(default="", description="原始查询")


class ChatTaskWithElementsResponse(BaseModel):
    """带要素的任务响应 - 要素确认流程第一阶段"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态 (awaiting_confirmation)")
    extracted_elements: Optional[ChatSearchElementsModel] = Field(None, description="LLM 提取的搜索要素")
    message: str = Field(default="", description="提示消息")
    created_at: Optional[str] = Field(None, description="创建时间")


class ConfirmElementsRequest(BaseModel):
    """确认要素请求"""
    confirmed_elements: ChatSearchElementsModel = Field(..., description="用户确认/修改后的搜索要素")


class ConfirmAsyncResponse(BaseModel):
    """异步确认响应 - v4.21.0 新增"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(default="searching", description="任务状态")
    message: str = Field(default="搜索任务已开始，请稍后在库外信息中查看结果", description="提示消息")
    estimated_time_seconds: int = Field(default=60, description="预估完成时间（秒）")


# ==================== API 端点 ====================

@router.post(
    "/sync",
    response_model=None,  # 根据参数返回不同类型：ChatV2Response, TaskCreatedResponse 或 ChatTaskWithElementsResponse
    summary="同步搜索（V2 层分离架构）",
    description="v4.20.0: 支持要素确认模式。require_confirmation=true时返回提取的要素供用户确认。",
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
                        },
                        "confirmation": {
                            "summary": "要素确认模式 (require_confirmation=true)",
                            "value": {
                                "task_id": "123456",
                                "status": "awaiting_confirmation",
                                "extracted_elements": {
                                    "keywords": ["关键词1", "关键词2"],
                                    "keywords_en": ["keyword1", "keyword2"],
                                    "time_range": "qdr:m",
                                    "source_preferences": ["mainstream"],
                                    "languages": ["zh", "en"]
                                },
                                "message": "请确认或修改搜索要素",
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
    require_confirmation: bool = Query(True, description="是否需要要素确认。true=返回提取的要素供用户确认(默认)，false=直接执行搜索"),
    current_user: User = Depends(get_current_active_user),
):
    """
    基于层分离架构的同步搜索

    **执行流程**:
    1. 如果 require_confirmation=true，提取搜索要素并返回供用户确认
    2. 如果 wait=false，立即返回任务ID，后台并行执行
    3. 如果 wait=true，等待执行完成后返回结果

    **要素确认流程 (v4.20.0)**:
    1. POST /chat/v2/sync?require_confirmation=true → 获取提取的要素 (status=awaiting_confirmation)
    2. POST /chat/v2/tasks/{task_id}/confirm → 确认要素并执行搜索 (status=completed)

    **架构优势**:
    - 搜索层和AI层职责分离，易于维护和扩展
    - 支持真正的并行执行
    - 事件驱动的层间通信
    """
    try:
        logger.info(
            f"[ChatV2] Request: question='{request.question[:50]}...', "
            f"wait={wait}, require_confirmation={require_confirmation}, user_id={current_user.id}"
        )

        # v4.20.0: 要素确认模式 - 提取要素后返回供用户确认
        if require_confirmation:
            logger.info(f"[ChatV2] 要素确认模式: 开始提取搜索要素")
            chat_search_service = get_chat_search_service()

            try:
                task_id, elements = await chat_search_service.extract_elements(
                    question=request.question,
                    user_id=current_user.id,
                    search_mode=request.search_mode,
                    conversation_id=request.conversation_id,
                    metadata={"source": "chat_v2_sync", "require_confirmation": True}
                )

                # 转换为响应模型
                elements_model = ChatSearchElementsModel(
                    keywords=elements.keywords,
                    keywords_en=elements.keywords_en,
                    time_range=elements.time_range,
                    source_preferences=elements.source_preferences,
                    languages=elements.languages,
                    search_strategy=elements.search_strategy,
                    summary=elements.summary,
                    event_type=elements.event_type,
                    llm_reasoning=elements.llm_reasoning,
                    original_query=elements.original_query,
                )

                logger.info(f"[ChatV2] 要素提取完成: task_id={task_id}, keywords={elements.keywords}")

                return ChatTaskWithElementsResponse(
                    task_id=task_id,
                    status="awaiting_confirmation",
                    extracted_elements=elements_model,
                    message="请确认或修改搜索要素，然后调用 POST /chat/v2/tasks/{task_id}/confirm 执行搜索",
                    created_at=datetime.now().isoformat()
                )

            except Exception as e:
                logger.error(f"[ChatV2] 要素提取失败: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"要素提取失败: {str(e)}")

        # 非要素确认模式：直接执行搜索
        orchestrator = await get_orchestrator()

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

            # v4.22.0: 保存消息到 chat_conversations (search_only 模式)
            if request.conversation_id:
                try:
                    # 保存用户消息
                    await chat_conversation_repository.add_message(
                        conversation_id=request.conversation_id,
                        role="user",
                        content=request.question
                    )
                    # 保存搜索结果（无AI回答）
                    sources_for_save = [
                        {"mongo_id": s.mongo_id, "title": s.title, "source": s.source}
                        for s in sources[:5]
                    ]
                    await chat_conversation_repository.add_message(
                        conversation_id=request.conversation_id,
                        role="assistant",
                        content="[仅搜索模式 - 无AI总结]",
                        sources=sources_for_save
                    )
                    logger.info(f"[ChatV2] search_only 消息已保存: conversation_id={request.conversation_id}")
                except Exception as e:
                    logger.warning(f"[ChatV2] search_only 保存消息失败: {e}")

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

        # v4.22.0: 保存消息到 chat_conversations
        if request.conversation_id:
            try:
                # 保存用户消息
                await chat_conversation_repository.add_message(
                    conversation_id=request.conversation_id,
                    role="user",
                    content=request.question
                )
                # 保存AI回复（包含来源摘要）
                sources_for_save = [
                    {"mongo_id": s.mongo_id, "title": s.title, "source": s.source}
                    for s in sources[:5]  # 只保存前5个来源
                ]
                await chat_conversation_repository.add_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=ai_result.result.answer,
                    sources=sources_for_save
                )
                logger.info(f"[ChatV2] 消息已保存到对话: conversation_id={request.conversation_id}")
            except Exception as e:
                logger.warning(f"[ChatV2] 保存消息失败: {e}")

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


# ==================== 任务查询端点 (v4.21.0) ====================

class ChatTaskListResponse(BaseModel):
    """Chat 任务列表响应"""
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="任务列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=20, description="每页数量")


class ChatTaskDetailResponse(BaseModel):
    """Chat 任务详情响应"""
    task_id: str
    status: str
    question: str
    created_at: str
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    extracted_elements: Optional[Dict[str, Any]] = None
    confirmed_elements: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    progress_message: Optional[str] = None
    progress_percentage: Optional[int] = None


@router.get(
    "/tasks",
    response_model=ChatTaskListResponse,
    summary="获取用户的Chat搜索任务列表",
    description="v4.21.0 新增：获取当前用户的所有 Chat 搜索任务，按创建时间倒序排列"
)
async def get_chat_tasks(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(default=None, description="状态过滤 (searching/completed/failed)"),
    current_user: User = Depends(get_current_active_user)
):
    """
    获取用户的Chat搜索任务列表

    **v4.21.0 新增**

    返回当前用户的所有 Chat 搜索任务，支持分页和状态过滤。
    用于在"库外信息"页面展示用户的搜索任务。

    Args:
        page: 页码
        page_size: 每页数量
        status: 状态过滤

    Returns:
        ChatTaskListResponse: 任务列表
    """
    try:
        logger.info(f"[ChatV2] 获取任务列表: user_id={current_user.id}, page={page}, status={status}")

        # 构建查询条件
        query = {"user_id": current_user.id}
        if status:
            query["status"] = status

        # 查询任务
        skip = (page - 1) * page_size
        tasks = await chat_task_repository.list_tasks(
            query=query,
            skip=skip,
            limit=page_size,
            sort=[("created_at", -1)]  # 按创建时间倒序
        )

        # 获取总数
        total = await chat_task_repository.count_tasks(query)

        # 转换任务数据
        task_list = []
        for task in tasks:
            task_data = {
                "task_id": task["_id"],
                "status": task.get("status", "unknown"),
                "question": task.get("question", ""),
                "created_at": task.get("created_at", "").isoformat() if task.get("created_at") else "",
                "updated_at": task.get("updated_at", "").isoformat() if task.get("updated_at") else None,
                "completed_at": task.get("completed_at", "").isoformat() if task.get("completed_at") else None,
                "result_count": task.get("result", {}).get("result_count", 0) if task.get("result") else 0,
                "error_message": task.get("error", {}).get("message") if task.get("error") else None,
                "progress_message": task.get("progress", {}).get("message"),
                "progress_percentage": task.get("progress", {}).get("percentage"),
            }
            task_list.append(task_data)

        logger.info(f"[ChatV2] 任务列表获取成功: count={len(task_list)}, total={total}")

        return ChatTaskListResponse(
            tasks=task_list,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"[ChatV2] 获取任务列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tasks/{task_id}",
    response_model=ChatTaskDetailResponse,
    summary="获取Chat搜索任务详情",
    description="v4.21.0 新增：获取指定任务的详细信息和搜索结果"
)
async def get_chat_task_detail(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取Chat搜索任务详情

    **v4.21.0 新增**

    返回指定任务的详细信息，包括搜索要素、结果等。

    **v4.34.0 更新**:
    - 从 langgraph_search_results 表查询最新数据（包含翻译内容）
    - 将 translator_dict 中的翻译内容映射到结果中

    Args:
        task_id: 任务ID

    Returns:
        ChatTaskDetailResponse: 任务详情
    """
    try:
        logger.info(f"[ChatV2] 获取任务详情: task_id={task_id}, user_id={current_user.id}")

        task = await chat_task_repository.get_task_by_user(task_id, current_user.id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在或无权访问")

        # v4.34.0: 从 langgraph_search_results 表查询最新数据（包含翻译内容）
        result = task.get("result")
        if result and task.get("status") == "completed":
            try:
                langgraph_results = await mongo_langgraph_result_repository.find_by_task_id(task_id)
                if langgraph_results:
                    # 将 LangGraphSearchResult 实体转换为字典，并提取翻译内容
                    enriched_results = []
                    for lr in langgraph_results:
                        result_dict = {
                            "id": lr.id,
                            "url": lr.url,
                            "title": lr.title,
                            "snippet": lr.snippet,
                            "content": lr.markdown_content,
                            "markdown_content": lr.markdown_content,
                            "source": lr.source,
                            "published_date": lr.published_date.isoformat() if lr.published_date else None,
                            "layer": lr.layer,
                            "layer_name": lr.layer_name,
                            # v4.34.0: 从 translator_dict 提取翻译内容
                            "translated_title": (lr.translator_dict or {}).get("title_zh", ""),
                            "translated_content": (lr.translator_dict or {}).get("content_zh", ""),
                            "translator_status": lr.translator_status,
                        }
                        enriched_results.append(result_dict)

                    # 更新 result 中的 results 数组
                    result = {
                        **result,
                        "results": enriched_results,
                        "result_count": len(enriched_results),
                    }
                    logger.info(f"[ChatV2] 从 langgraph_search_results 加载了 {len(enriched_results)} 条结果")
            except Exception as e:
                logger.warning(f"[ChatV2] 从 langgraph_search_results 加载结果失败，使用原始数据: {e}")

        return ChatTaskDetailResponse(
            task_id=task["_id"],
            status=task.get("status", "unknown"),
            question=task.get("question", ""),
            created_at=task.get("created_at", "").isoformat() if task.get("created_at") else "",
            updated_at=task.get("updated_at", "").isoformat() if task.get("updated_at") else None,
            completed_at=task.get("completed_at", "").isoformat() if task.get("completed_at") else None,
            extracted_elements=task.get("extracted_elements"),
            confirmed_elements=task.get("confirmed_elements"),
            result=result,
            error_message=task.get("error_message"),
            progress_message=task.get("progress_message"),
            progress_percentage=task.get("progress_percentage"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatV2] 获取任务详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 要素确认端点 (v4.20.0) ====================

@router.post(
    "/tasks/{task_id}/confirm",
    response_model=Union[ChatV2Response, ConfirmAsyncResponse],
    summary="确认搜索要素并执行搜索",
    description="v4.20.0 新增：确认要素确认流程的第二阶段。v4.21.0: 支持异步执行(wait=false)"
)
async def confirm_search_elements_v2(
    task_id: str,
    request: ConfirmElementsRequest,
    wait: bool = Query(
        default=False,
        description="是否等待搜索完成。false=异步执行(立即返回)，true=同步等待结果"
    ),
    current_user: User = Depends(get_current_active_user)
):
    """
    确认搜索要素并执行搜索

    **v4.20.0 新增：要素确认流程第二阶段**
    **v4.21.0 改进：支持异步执行，解决超时问题**

    在调用 POST /chat/v2/sync?require_confirmation=true 获取提取的要素后，
    用户可以修改要素，然后调用此端点执行搜索。

    **流程**:
    1. POST /chat/v2/sync?require_confirmation=true → 获取提取的要素 (status=awaiting_confirmation)
    2. POST /chat/v2/tasks/{task_id}/confirm?wait=false → 启动搜索任务 (立即返回)
    3. 搜索在后台执行，用户可在"库外信息"中查看结果

    **参数**:
    - wait=false (默认): 异步执行，立即返回任务状态
    - wait=true: 同步等待，返回搜索结果（可能超时）

    Args:
        task_id: 任务ID（从阶段1返回）
        request: 确认的要素
        wait: 是否等待搜索完成

    Returns:
        - wait=false: ConfirmAsyncResponse (task_id, status="searching")
        - wait=true: ChatV2Response (完整搜索结果)
    """
    try:
        logger.info(f"[ChatV2] 确认搜索要素: task_id={task_id}, user_id={current_user.id}, wait={wait}")

        chat_search_service = get_chat_search_service()

        # 转换请求模型为领域实体
        confirmed_elements = ChatSearchElements(
            keywords=request.confirmed_elements.keywords,
            keywords_en=request.confirmed_elements.keywords_en,
            time_range=request.confirmed_elements.time_range,
            source_preferences=request.confirmed_elements.source_preferences,
            languages=request.confirmed_elements.languages,
            search_strategy=request.confirmed_elements.search_strategy,
            summary=request.confirmed_elements.summary,
            event_type=request.confirmed_elements.event_type,
            llm_reasoning=request.confirmed_elements.llm_reasoning,
            original_query=request.confirmed_elements.original_query,
        )

        if not wait:
            # v4.21.0: 异步执行 - 立即返回，后台执行搜索
            # 先验证任务状态和保存确认要素
            await chat_search_service.prepare_for_async_execution(
                task_id=task_id,
                confirmed_elements=confirmed_elements,
                user_id=current_user.id
            )

            # 启动后台任务
            asyncio.create_task(
                _execute_confirm_search_background(
                    task_id=task_id,
                    confirmed_elements=confirmed_elements,
                    user_id=current_user.id
                )
            )

            logger.info(f"[ChatV2] 异步搜索任务已启动: task_id={task_id}")

            return ConfirmAsyncResponse(
                task_id=task_id,
                status="searching",
                message="搜索任务已开始，请稍后在库外信息中查看结果",
                estimated_time_seconds=60
            )

        # wait=true: 同步执行（原有逻辑）
        result = await chat_search_service.confirm_and_execute(
            task_id=task_id,
            confirmed_elements=confirmed_elements,
            user_id=current_user.id
        )

        logger.info(f"[ChatV2] 搜索完成: task_id={task_id}, sources_count={result.get('sources_count', 0)}")

        # 转换来源数据
        sources = [
            _convert_source(s)
            for s in result.get("sources", [])
        ]

        # v4.22.0: 保存消息到 chat_conversations
        task = await chat_task_repository.get_task(task_id)
        if task and task.get("conversation_id"):
            conversation_id = task.get("conversation_id")
            try:
                # 保存用户消息
                await chat_conversation_repository.add_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=result.get("question", "")
                )
                # 保存AI回复（包含来源摘要）
                sources_for_save = [
                    {"mongo_id": s.mongo_id, "title": s.title, "source": s.source}
                    for s in sources[:5]  # 只保存前5个来源
                ]
                await chat_conversation_repository.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=result.get("answer", ""),
                    sources=sources_for_save
                )
                logger.info(f"[ChatV2] 确认搜索消息已保存: conversation_id={conversation_id}")
            except Exception as e:
                logger.warning(f"[ChatV2] 确认搜索保存消息失败: {e}")

        return ChatV2Response(
            question=result.get("question", ""),
            answer=result.get("answer", ""),
            sources=sources,
            sources_count=len(sources),
            status="success",
            task_id=task_id,
            history_id=result.get("history_id"),
            execution_mode="confirmation",
            execution_time_ms=result.get("execution_time_ms", 0),
        )

    except ValueError as e:
        logger.warning(f"[ChatV2] 确认搜索要素失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ChatV2] 确认搜索要素错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _execute_confirm_search_background(
    task_id: str,
    confirmed_elements: ChatSearchElements,
    user_id: int
):
    """后台执行确认搜索任务 (v4.21.0)"""
    try:
        logger.info(f"[ChatV2] 后台搜索开始: task_id={task_id}")

        chat_search_service = get_chat_search_service()
        result = await chat_search_service.execute_search_only(
            task_id=task_id,
            confirmed_elements=confirmed_elements,
            user_id=user_id
        )

        logger.info(f"[ChatV2] 后台搜索完成: task_id={task_id}, results={result.get('result_count', 0)}")

        # v4.22.0: 保存消息到 chat_conversations
        task = await chat_task_repository.get_task(task_id)
        if task and task.get("conversation_id"):
            conversation_id = task.get("conversation_id")
            try:
                # 保存用户消息
                await chat_conversation_repository.add_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=task.get("question", "")
                )
                # 保存AI回复（如果有的话）
                answer = result.get("answer", "")
                if answer:
                    sources_for_save = [
                        {"mongo_id": s.get("mongo_id"), "title": s.get("title"), "source": s.get("source")}
                        for s in result.get("sources", [])[:5]  # 只保存前5个来源
                    ]
                    await chat_conversation_repository.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        sources=sources_for_save
                    )
                logger.info(f"[ChatV2] 后台搜索消息已保存: conversation_id={conversation_id}")
            except Exception as save_e:
                logger.warning(f"[ChatV2] 后台搜索保存消息失败: {save_e}")

    except Exception as e:
        logger.error(f"[ChatV2] 后台搜索失败: task_id={task_id}, error={e}", exc_info=True)
        # 错误已在 service 层处理，这里只记录日志


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

            # v4.22.0: 保存消息到 chat_conversations
            conversation_id = context.options.get("conversation_id") if context.options else None
            if conversation_id:
                try:
                    # 保存用户消息
                    await chat_conversation_repository.add_message(
                        conversation_id=conversation_id,
                        role="user",
                        content=context.query
                    )
                    # 保存AI回复（包含来源摘要）
                    sources_for_save = [
                        {"mongo_id": s.get("mongo_id"), "title": s.get("title"), "source": s.get("source")}
                        for s in ai_result.result.sources[:5]  # 只保存前5个来源
                    ]
                    await chat_conversation_repository.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=ai_result.result.answer,
                        sources=sources_for_save
                    )
                    logger.info(f"[ChatV2] 后台任务消息已保存: conversation_id={conversation_id}")
                except Exception as e:
                    logger.warning(f"[ChatV2] 后台任务保存消息失败: {e}")
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
