"""
Chat API 端点

提供与前端 /chat 接口兼容的适配器，映射到 NL Search 系统。

**功能**:
- 接收 question 字段，映射到 query_text
- 返回 SSE (Server-Sent Events) 流式响应
- 完全兼容现有 nl_search 系统

**映射关系**:
- /chat 的 question → nl_search_logs 的 query_text

版本: v1.0.0
日期: 2025-11-22

v2.7.0 更新:
- 添加 Token 认证，强制从 Token 获取用户身份
- 添加用户隔离逻辑（admin 查看所有，普通用户只能查看自己的）
- 新增 info_items 和 is_pinned 字段支持
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, AsyncGenerator, List, Dict, Any
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.config import nl_search_config
from src.services.nl_search.search_history_service import search_history_service
from src.infrastructure.database.connection import get_mongodb_database
from src.infrastructure.database.chat_conversation_repository import (
    chat_conversation_repository
)
from src.core.domain.entities.auth.user import User
from src.api.dependencies.auth import get_current_active_user
from bson import ObjectId

logger = logging.getLogger(__name__)

# AI服务配置
REMOTE_AI_SERVICE_URL = "http://192.168.0.5:8035/chat"
REMOTE_AI_SERVICE_TIMEOUT = 120.0

router = APIRouter()


# ==================== 工具函数 ====================

async def populate_info_items(info_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """填充 info_items 的完整数据 (v2.9.0)

    从原表查询完整信息，根据 source 字段路由到不同的集合:
    - "用户上传" → file_uploads 集合
    - 其他 → news_results 集合

    Args:
        info_items: 只包含 mongo_id + source 的引用列表

    Returns:
        填充了 title, score, preview 等完整信息的列表
    """
    if not info_items:
        return []

    db = await get_mongodb_database()
    populated_items = []

    for item in info_items:
        mongo_id = item.get("mongo_id") or item.get("id")
        source = item.get("source", "")

        if not mongo_id:
            populated_items.append(item)
            continue

        try:
            if source == "用户上传":
                # 从 file_uploads 集合查询
                result = await db["file_uploads"].find_one(
                    {"_id": ObjectId(mongo_id)},
                    {"title": 1, "content": 1, "_id": 0}
                )
                if result:
                    populated_items.append({
                        **item,
                        "title": result.get("title") or item.get("title", ""),
                        "preview": (result.get("content") or "")[:200],
                    })
                else:
                    populated_items.append(item)
            else:
                # 从 news_results 集合查询
                result = await db["news_results"].find_one(
                    {"_id": mongo_id},
                    {"news_results.title_zh": 1, "news_results.summary_zh": 1, "_id": 0}
                )
                if result:
                    nested = result.get("news_results", {})
                    populated_items.append({
                        **item,
                        "title": nested.get("title_zh") or item.get("title", ""),
                        "preview": (nested.get("summary_zh") or "")[:200],
                    })
                else:
                    populated_items.append(item)

        except Exception as e:
            logger.warning(f"填充 info_item 失败 (mongo_id={mongo_id}): {e}")
            populated_items.append(item)

    return populated_items


# ==================== 数据模型 ====================

class HistoryMessage(BaseModel):
    """历史消息模型"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Chat请求模型（兼容前端）

    v1.1.0: 新增 conversation_id 和 history 支持多轮对话
    """
    question: str = Field(
        ...,
        description="用户提问（自然语言）",
        min_length=1,
        max_length=1000,
        examples=["请介绍关于西藏的新闻"]
    )
    user_id: Optional[str] = Field(
        None,
        description="用户ID（可选）"
    )
    search_mode: str = Field(
        default="single",
        description="搜索模式: single=单次搜索, multi=多问题分解",
        pattern="^(single|multi)$"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="对话会话ID（可选，用于多轮对话）"
    )
    history: Optional[List[HistoryMessage]] = Field(
        None,
        description="对话历史（可选，如果提供了conversation_id会自动从服务器获取）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "请介绍关于西藏的新闻",
                "conversation_id": "248728141926559744",
                "history": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
                ]
            }
        }


class CategoryModel(BaseModel):
    """分类信息模型"""
    大类: str
    类别: str
    地域: str


class SourceDetail(BaseModel):
    """来源详情模型（增强版，统一格式）

    v2.7.1: 统一新闻来源和用户上传格式
    - 用户上传数据映射到相同字段结构
    - file_uploads.title → title_zh
    - file_uploads.content → content_zh
    - file_uploads.storage_url → url
    """
    id: str = Field(..., description="UUID")
    mongo_id: str = Field(..., description="MongoDB ID")
    title: str = Field(..., description="标题")
    source: str = Field(..., description="来源：新闻网站名称 或 '用户上传'")
    score: float = Field(..., description="相关性评分")
    category: CategoryModel = Field(..., description="分类信息")
    publish_time: str = Field(..., description="发布时间")
    preview: str = Field(..., description="内容预览")
    url: Optional[str] = Field(None, description="完整URL")
    markdown_content: Optional[str] = Field(None, description="完整Markdown内容")
    content_length: Optional[int] = Field(None, description="内容长度")
    title_zh: Optional[str] = Field(None, description="中文标题")
    summary_zh: Optional[str] = Field(None, description="中文摘要")
    content_zh: Optional[str] = Field(None, description="中文内容/正文")


class ChatSyncResponse(BaseModel):
    """Chat同步响应模型"""
    question: str = Field(..., description="用户问题")
    answer: str = Field(..., description="完整答案")
    sources: List[SourceDetail] = Field(..., description="数据来源列表（含完整内容）")
    sources_count: int = Field(..., description="来源数量")
    answer_length: int = Field(..., description="答案长度")
    status: str = Field(..., description="状态")


# ==================== API端点 ====================

@router.post(
    "/chat",
    summary="Chat接口（SSE流式响应）",
    description="接收question字段，返回流式搜索结果（映射到nl_search系统）"
)
async def chat_endpoint(request: ChatRequest):
    """
    Chat接口 - 流式返回搜索结果

    **功能**:
    - 接收 question 字段（自然语言查询）
    - 映射到 nl_search_logs.query_text
    - 返回 SSE 格式的流式响应

    **流式响应格式**:
    ```
    data: {"type": "status", "message": "正在搜索..."}
    data: {"type": "analysis", "data": {...}}
    data: {"type": "result", "index": 0, "data": {
        "id": "uuid",
        "mongo_id": "249832360786370562",
        "title": "标题",
        "url": "https://example.com",
        "preview": "预览内容",
        "source": "来源",
        "category": {"大类": "...", "类别": "...", "地域": "..."},
        "score": 0.95,
        "publish_time": "2025-01-01",
        "markdown_content": "完整Markdown内容（从news_results查询）",
        "title_zh": "中文标题",
        "summary_zh": "中文摘要",
        "content_zh": "中文总结"
    }}
    data: {"type": "done", "log_id": "123456", "total_results": 10}
    ```

    Args:
        request (ChatRequest): Chat请求

    Returns:
        StreamingResponse: SSE流式响应

    Raises:
        HTTPException:
            - 503: NL Search功能未启用
            - 400: 输入验证失败
            - 500: 内部错误

    Example:
        ```bash
        curl -N -X POST "http://192.168.0.5:8035/api/v1/chat" \\
          -H "Content-Type: application/json" \\
          -d '{"question": "请介绍关于西藏的新闻"}'
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "NL Search功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        logger.info(f"Chat请求: question='{request.question[:50]}...', mode={request.search_mode}")

        # 💾 准备保存 SSE 原始格式
        save_dir = Path("data/chat_sse")
        save_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        question_slug = request.question[:30].replace(" ", "_").replace("/", "_")
        sse_filename = f"{timestamp}_{question_slug}.sse.txt"
        sse_filepath = save_dir / sse_filename

        sse_lines = []  # 收集 SSE 原始行

        # 映射 question → query_text
        async def event_generator() -> AsyncGenerator[str, None]:
            """生成SSE事件流（集成远程AI服务）+ 保存SSE原始格式"""
            try:
                # 1. 发送状态：开始搜索
                status_line = f"data: {json.dumps({'type': 'status', 'message': '正在分析您的问题...'}, ensure_ascii=False)}\n\n"
                sse_lines.append(status_line)
                yield status_line

                # 2. 调用NL Search服务（sonar-pro + firecrawl + 入库）
                result = await nl_search_service.create_search(
                    query_text=request.question,
                    user_id=request.user_id,
                    search_mode=request.search_mode
                )

                log_id = result["log_id"]
                logger.info(f"搜索成功: log_id={log_id}, results_count={len(result.get('results', []))}")

                # 3. 调用远程 AI 服务进行处理
                try:
                    async with httpx.AsyncClient(timeout=REMOTE_AI_SERVICE_TIMEOUT) as client:
                        logger.info(f"正在调用远程 AI 服务: {REMOTE_AI_SERVICE_URL}")

                        async with client.stream(
                            "POST",
                            REMOTE_AI_SERVICE_URL,
                            json={
                                "question": request.question,
                                "user_id": request.user_id,
                                "search_mode": request.search_mode
                            }
                        ) as ai_response:
                            if ai_response.status_code != 200:
                                logger.error(f"远程 AI 服务返回错误: {ai_response.status_code}")
                                raise Exception(f"AI服务返回状态码: {ai_response.status_code}")

                            # 4. 实时处理 AI 服务的 SSE 流
                            db = await get_mongodb_database()

                            async for line in ai_response.aiter_lines():
                                if not line.strip():
                                    continue

                                if not line.startswith("data: "):
                                    continue

                                try:
                                    event_data = line[6:]  # 去除 "data: " 前缀
                                    event = json.loads(event_data)

                                    # 5. 检测 sources 事件，进行数据增强
                                    if event.get("type") == "sources":
                                        logger.info(f"收到 sources 事件，sources 数量: {len(event.get('data', []))}")
                                        enhanced_sources = []

                                        for source in event.get("data", []):
                                            mongo_id = source.get("mongo_id")

                                            if mongo_id:
                                                try:
                                                    # 6. ✅ v2.3.0: 从 search_results 集合查询（扁平结构）
                                                    search_result = await db["search_results"].find_one(
                                                        {"_id": mongo_id},
                                                        {
                                                            "url": 1,
                                                            "markdown_content": 1,
                                                            "title": 1,
                                                            "snippet": 1,
                                                            "_id": 0
                                                        }
                                                    )

                                                    # 7. 合并 AI 服务数据和 search_results 数据
                                                    if search_result:
                                                        enhanced_source = {
                                                            **source,  # AI 服务返回的基础字段
                                                            "url": search_result.get("url"),
                                                            "markdown_content": search_result.get("markdown_content"),
                                                            # v2.3.0: search_results 是扁平结构，无嵌套字段
                                                            "title": search_result.get("title") or source.get("title"),
                                                            "snippet": search_result.get("snippet")
                                                        }
                                                        enhanced_sources.append(enhanced_source)
                                                    else:
                                                        logger.warning(f"未找到 mongo_id={mongo_id} 的 search_results 记录")
                                                        enhanced_sources.append(source)

                                                except Exception as e:
                                                    logger.warning(f"查询 search_results 失败 (mongo_id={mongo_id}): {e}")
                                                    enhanced_sources.append(source)
                                            else:
                                                enhanced_sources.append(source)

                                        # 8. 返回增强后的 sources 事件
                                        enhanced_event = {
                                            "type": "sources",
                                            "data": enhanced_sources
                                        }
                                        sources_line = f"data: {json.dumps(enhanced_event, ensure_ascii=False)}\n\n"
                                        sse_lines.append(sources_line)
                                        yield sources_line
                                        logger.info(f"已发送增强后的 sources 事件，包含 {len(enhanced_sources)} 条记录")

                                    else:
                                        # 其他事件（answer_chunk, stream_end）直接转发
                                        event_line = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                                        sse_lines.append(event_line)
                                        yield event_line

                                except json.JSONDecodeError as e:
                                    logger.warning(f"解析 AI 服务响应失败: {e}, line={line}")
                                    continue

                except httpx.RequestError as e:
                    # AI 服务不可用，使用本地数据回退
                    logger.warning(f"远程 AI 服务不可用: {e}，使用本地数据回退")

                    # 回退策略：直接返回本地搜索结果
                    if result.get("analysis"):
                        analysis_line = f"data: {json.dumps({'type': 'analysis', 'data': result['analysis']}, ensure_ascii=False)}\n\n"
                        sse_lines.append(analysis_line)
                        yield analysis_line

                    db = await get_mongodb_database()
                    for idx, item in enumerate(result.get("results", [])):
                        mongo_id = item.get("mongo_id")
                        url = item.get("url")
                        markdown_content = None
                        title_zh = None
                        summary_zh = None
                        content_zh = None

                        if mongo_id:
                            try:
                                news_result = await db["news_results"].find_one(
                                    {"_id": mongo_id},
                                    {
                                        "url": 1,
                                        "markdown_content": 1,
                                        "news_results.title_zh": 1,
                                        "news_results.summary_zh": 1,
                                        "news_results.content_zh": 1,
                                        "_id": 0
                                    }
                                )

                                if news_result:
                                    url = news_result.get("url") or url
                                    markdown_content = news_result.get("markdown_content")
                                    nested = news_result.get("news_results", {})
                                    title_zh = nested.get("title_zh")
                                    summary_zh = nested.get("summary_zh")
                                    content_zh = nested.get("content_zh")
                            except Exception as e:
                                logger.warning(f"查询 news_results 失败 (mongo_id={mongo_id}): {e}")

                        result_data = {
                            "type": "result",
                            "index": idx,
                            "data": {
                                "id": item.get("id"),
                                "mongo_id": mongo_id,
                                "title": item.get("title"),
                                "url": url,
                                "preview": item.get("preview"),
                                "source": item.get("source"),
                                "category": item.get("category"),
                                "score": item.get("score", 0.0),
                                "publish_time": item.get("publish_time"),
                                "markdown_content": markdown_content,
                                "title_zh": title_zh,
                                "summary_zh": summary_zh,
                                "content_zh": content_zh
                            }
                        }
                        yield f"data: {json.dumps(result_data, ensure_ascii=False)}\n\n"

                    done_data = {
                        "type": "done",
                        "log_id": log_id,
                        "total_results": len(result.get("results", [])),
                        "search_mode": request.search_mode,
                        "fallback": True  # 标记使用了回退策略
                    }

                    if request.search_mode == "single":
                        done_data["total_raw_results"] = result.get("total_results")
                        done_data["high_score_results"] = result.get("high_score_results")

                    elif request.search_mode == "multi":
                        done_data["sub_queries"] = result.get("sub_queries", [])
                        done_data["total_unique_results"] = result.get("total_unique_results")

                    yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

            except ValueError as e:
                # 输入验证错误
                error_data = {
                    "type": "error",
                    "error": "输入验证失败",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

            except Exception as e:
                # 内部错误
                logger.error(f"Chat搜索失败: {e}", exc_info=True)
                error_data = {
                    "type": "error",
                    "error": "搜索失败",
                    "message": "服务暂时不可用，请稍后重试"
                }
                error_line = f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                sse_lines.append(error_line)
                yield error_line

            finally:
                # 💾 保存 SSE 原始格式到文件
                try:
                    with open(sse_filepath, 'w', encoding='utf-8') as f:
                        f.write(f"# SSE Stream for: {request.question}\n")
                        f.write(f"# Timestamp: {datetime.now().isoformat()}\n")
                        f.write(f"# User ID: {request.user_id}\n")
                        f.write(f"# Search Mode: {request.search_mode}\n")
                        f.write("#" + "="*80 + "\n\n")
                        f.writelines(sse_lines)

                    logger.info(f"💾 SSE 原始格式已保存: {sse_filepath} ({len(sse_lines)} 行)")
                except Exception as save_error:
                    logger.warning(f"⚠️ 保存 SSE 原始格式失败: {save_error}")

        # 返回SSE流式响应
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Chat端点异常: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "Chat服务暂时不可用，请稍后重试"
            }
        )


@router.post(
    "/chat/sync",
    summary="Chat接口（同步响应，含完整内容）",
    description="调用本地NL Search服务，自动保存到MongoDB并返回完整内容。支持多轮对话历史。",
    response_model=ChatSyncResponse
)
async def chat_sync_endpoint(request: ChatRequest):
    """
    Chat接口 - 同步返回完整结果（含完整内容）

    **功能** (v2.6.0 - 多轮对话支持):
    1. 调用本地 NL Search 服务执行搜索（sonar-pro + firecrawl + 入库）
    2. 自动保存搜索记录到 MongoDB nl_search_logs 集合
    3. 调用远程 AI 服务 (http://192.168.0.5:8035/chat) 进行智能处理
    4. 提取 AI 返回的 sources 中的 mongo_id
    5. 查询 MongoDB news_results 获取完整内容（包含中文翻译字段）
    6. 返回 AI 增强的响应（含完整内容和中文翻译）
    7. 【新增】支持多轮对话历史，可传入 conversation_id 或 history

    **数据流**:
    - 用户问题 → NLSearchService.create_search() → 保存到 MongoDB
    - 搜索结果 + 历史对话 → 远程 AI 服务 → AI 生成答案 + 智能排序来源
    - sources[].mongo_id → news_results 查询 → 完整内容（嵌套结构 + 中文翻译）
    - 合并数据 → 返回前端
    - 【新增】如提供 conversation_id，自动保存对话到 chat_conversations

    Args:
        request (ChatRequest): Chat请求（支持 conversation_id 和 history）

    Returns:
        ChatSyncResponse: 包含完整内容的响应

    Example:
        ```bash
        # 单次对话
        curl -X POST "http://localhost:8000/api/v1/chat/sync" \\
          -H "Content-Type: application/json" \\
          -d '{"question": "请介绍关于西藏的新闻"}'

        # 多轮对话
        curl -X POST "http://localhost:8000/api/v1/chat/sync" \\
          -H "Content-Type: application/json" \\
          -d '{"question": "继续介绍", "conversation_id": "248728141926559744"}'
        ```
    """
    try:
        logger.info(f"Chat同步请求: question='{request.question[:50]}...', conversation_id={request.conversation_id}")

        # 0. 处理对话历史
        conversation_history = []

        # 如果提供了 conversation_id，从数据库获取历史
        if request.conversation_id:
            try:
                messages = await chat_conversation_repository.get_messages(
                    request.conversation_id, limit=20  # 限制最近20条消息
                )
                if messages:
                    conversation_history = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in messages
                    ]
                    logger.info(f"从数据库加载对话历史: {len(conversation_history)} 条消息")
            except Exception as e:
                logger.warning(f"加载对话历史失败: {e}")

        # 如果请求中直接提供了 history，使用请求中的历史（覆盖数据库历史）
        if request.history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.history
            ]
            logger.info(f"使用请求中的对话历史: {len(conversation_history)} 条消息")

        # 1. 调用本地 NL Search 服务
        result = await nl_search_service.create_search(
            query_text=request.question,
            user_id=request.user_id,
            search_mode=request.search_mode
        )

        log_id = result["log_id"]
        logger.info(f"搜索成功: log_id={log_id}, results_count={len(result.get('results', []))}")

        # 2. 调用远程 AI 服务进行智能处理 (SSE 流解析)
        logger.info("开始调用远程 AI 服务...")

        try:
            async with httpx.AsyncClient(timeout=REMOTE_AI_SERVICE_TIMEOUT) as client:
                # 构建 AI 服务请求参数
                ai_request_data = {
                    "question": request.question,
                    "search_results": result.get("results", []),
                    "user_id": request.user_id,
                    "log_id": log_id
                }

                # 如果有对话历史，添加到请求中
                if conversation_history:
                    ai_request_data["history"] = conversation_history
                    logger.info(f"向 AI 服务传递 {len(conversation_history)} 条对话历史")

                # 使用 stream 方法处理 SSE 响应
                async with client.stream(
                    "POST",
                    REMOTE_AI_SERVICE_URL,
                    json=ai_request_data
                ) as ai_response:
                    if ai_response.status_code != 200:
                        error_text = await ai_response.aread()
                        error_msg = f"AI 服务返回错误状态码: {ai_response.status_code}, 响应: {error_text.decode()[:200]}"
                        logger.error(error_msg)
                        raise HTTPException(status_code=502, detail=error_msg)

                    # 解析 SSE 流
                    answer_chunks = []
                    ai_sources = []
                    stream_status = "unknown"

                    async for line in ai_response.aiter_lines():
                        # 跳过空行
                        if not line.strip():
                            continue

                        # 解析 SSE 格式: "data: {...}"
                        if line.startswith("data: "):
                            try:
                                event_data = json.loads(line[6:])  # 去除 "data: " 前缀
                                event_type = event_data.get("type")

                                if event_type == "answer_chunk":
                                    # 收集 answer 片段
                                    answer_chunks.append(event_data.get("data", ""))

                                elif event_type == "sources":
                                    # 提取 sources 数据
                                    ai_sources = event_data.get("data", [])
                                    logger.info(f"收到 sources 数据: {len(ai_sources)} 条")

                                elif event_type == "stream_end":
                                    # 流结束事件
                                    stream_status = event_data.get("data", {}).get("status", "success_ai")
                                    logger.info(f"SSE 流结束: {stream_status}")

                            except json.JSONDecodeError as e:
                                logger.warning(f"SSE 事件解析失败: {line[:100]}, 错误: {e}")
                                continue

                    # 组装完整 answer
                    ai_answer = "".join(answer_chunks)

                    # 验证必要字段
                    if not ai_answer:
                        error_msg = "AI 服务返回的 answer 为空"
                        logger.error(error_msg)
                        raise HTTPException(status_code=502, detail=error_msg)

                    if not ai_sources:
                        error_msg = "AI 服务返回的 sources 为空"
                        logger.error(error_msg)
                        raise HTTPException(status_code=502, detail=error_msg)

                    logger.info(f"✅ AI 服务调用成功: answer_length={len(ai_answer)}, sources_count={len(ai_sources)}")

                    # 💾 保存 AI 服务响应到 data 文件夹
                    try:
                        # 创建保存目录
                        save_dir = Path("data/ai_responses")
                        save_dir.mkdir(parents=True, exist_ok=True)

                        # 生成文件名：时间戳 + 查询主题
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        question_slug = request.question[:30].replace(" ", "_").replace("/", "_")
                        filename = f"{timestamp}_{question_slug}.json"
                        filepath = save_dir / filename

                        # 构建保存数据
                        response_data = {
                            "timestamp": datetime.now().isoformat(),
                            "request": {
                                "question": request.question,
                                "user_id": request.user_id,
                                "search_mode": request.search_mode,
                                "log_id": log_id
                            },
                            "response": {
                                "answer": ai_answer,
                                "sources_count": len(ai_sources),
                                "sources": ai_sources,
                                "stream_status": stream_status
                            }
                        }

                        # 保存到文件
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(response_data, f, ensure_ascii=False, indent=2)

                        logger.info(f"💾 AI 服务响应已保存: {filepath}")

                    except Exception as save_error:
                        logger.warning(f"⚠️ 保存 AI 响应失败: {save_error}")

        except httpx.TimeoutException as e:
            error_msg = f"AI 服务调用超时（{REMOTE_AI_SERVICE_TIMEOUT}秒）"
            logger.error(error_msg)
            raise HTTPException(status_code=504, detail=error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"AI 服务请求失败: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=502, detail=error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"AI 服务返回的 SSE 事件不是有效的 JSON"
            logger.error(error_msg)
            raise HTTPException(status_code=502, detail=error_msg) from e

        # 3. 使用 AI 服务结果
        full_answer = ai_answer
        sources_data = ai_sources

        logger.info(f"最终数据: answer_length={len(full_answer)}, sources_count={len(sources_data)}, status={stream_status}")

        # 4. 去重处理：按 mongo_id 去重，保留第一个出现的
        seen_mongo_ids = set()
        unique_sources = []
        duplicate_count = 0

        for source in sources_data:
            mongo_id = source.get('mongo_id')
            if mongo_id and mongo_id in seen_mongo_ids:
                duplicate_count += 1
                continue
            if mongo_id:
                seen_mongo_ids.add(mongo_id)
            unique_sources.append(source)

        if duplicate_count > 0:
            logger.info(f"去重处理: 原始={len(sources_data)}, 去重后={len(unique_sources)}, 重复={duplicate_count}")

        # 5. 查询 MongoDB 获取完整内容
        db = await get_mongodb_database()
        enhanced_sources = []

        for source in unique_sources:
            mongo_id = source.get('mongo_id')
            source_type = source.get('source', '')  # 来源类型

            if not mongo_id:
                logger.warning(f"来源缺少mongo_id: {source.get('id')}")
                continue

            # 处理 category 字段,如果为空则提供默认值
            category_data = source.get('category', {})
            if not category_data or not all(k in category_data for k in ['大类', '类别', '地域']):
                category_data = {
                    '大类': '未分类',
                    '类别': '未分类',
                    '地域': '未知'
                }

            # ✅ v2.7.2: 根据来源类型路由到不同数据集合，统一字段格式
            if source_type == "用户上传":
                # 从 file_uploads 集合查询（使用 _id ObjectId）
                try:
                    file_result = await db["file_uploads"].find_one(
                        {"_id": ObjectId(mongo_id)},
                        {
                            "title": 1,
                            "content": 1,
                            "original_filename": 1,
                            "storage_url": 1,
                            "_id": 0
                        }
                    )
                except Exception as e:
                    logger.warning(f"ObjectId 转换失败: {mongo_id}, 错误: {e}")
                    file_result = None

                if file_result:
                    logger.info(f"从 file_uploads 查询成功: file_id={mongo_id}")
                    # 映射到统一字段格式
                    file_title = file_result.get('title') or source.get('title', '')
                    file_content = file_result.get('content', '')

                    enhanced_source = SourceDetail(
                        id=source.get('id', ''),
                        mongo_id=mongo_id,
                        title=file_title,
                        source=source_type,
                        score=source.get('score', 0.0),
                        category=CategoryModel(**category_data),
                        publish_time=source.get('publish_time', '未知时间'),
                        preview=source.get('preview', '') or file_content[:200] if file_content else '',
                        url=file_result.get('storage_url'),
                        # 统一字段映射：file_uploads → news 格式
                        title_zh=file_title,           # title → title_zh
                        summary_zh=None,               # 用户上传无摘要
                        content_zh=file_content,       # content → content_zh
                        content_length=len(file_content) if file_content else None
                    )
                else:
                    logger.warning(f"未找到 file_id={mongo_id} 的 file_uploads 记录")
                    enhanced_source = SourceDetail(
                        id=source.get('id', ''),
                        mongo_id=mongo_id,
                        title=source.get('title', ''),
                        source=source_type,
                        score=source.get('score', 0.0),
                        category=CategoryModel(**category_data),
                        publish_time=source.get('publish_time', '未知时间'),
                        preview=source.get('preview', '')
                    )
            else:
                # 从 news_results 集合查询（原有逻辑）
                news_result = await db["news_results"].find_one(
                    {"_id": mongo_id},
                    {
                        "url": 1,
                        "news_results.title_zh": 1,
                        "news_results.summary_zh": 1,
                        "news_results.content_zh": 1,
                        "_id": 0
                    }
                )

                # 提取嵌套的 news_results 对象
                nested_news_results = news_result.get('news_results', {}) if news_result else {}

                enhanced_source = SourceDetail(
                    id=source.get('id', ''),
                    mongo_id=mongo_id,
                    title=source.get('title', ''),
                    source=source_type,
                    score=source.get('score', 0.0),
                    category=CategoryModel(**category_data),
                    publish_time=source.get('publish_time', '未知时间'),
                    preview=source.get('preview', ''),
                    url=news_result.get('url') if news_result else None,
                    title_zh=nested_news_results.get('title_zh'),
                    summary_zh=nested_news_results.get('summary_zh'),
                    content_zh=nested_news_results.get('content_zh')
                )

            enhanced_sources.append(enhanced_source)

        logger.info(f"MongoDB查询完成: {len(enhanced_sources)}/{len(unique_sources)} 条记录获取了完整内容")

        # 5. 保存对话到数据库（如果提供了 conversation_id）
        if request.conversation_id:
            try:
                # 保存用户消息
                await chat_conversation_repository.add_message(
                    conversation_id=request.conversation_id,
                    role="user",
                    content=request.question
                )

                # 保存 AI 回复
                sources_for_save = [
                    {
                        "id": s.id,
                        "mongo_id": s.mongo_id,
                        "title": s.title,
                        "source": s.source
                    }
                    for s in enhanced_sources[:5]  # 只保存前5个来源的摘要
                ]
                await chat_conversation_repository.add_message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=full_answer,
                    sources=sources_for_save
                )
                logger.info(f"对话已保存到会话: {request.conversation_id}")

            except Exception as e:
                logger.warning(f"保存对话失败: {e}")

        # 5.5 v2.8.0: 保存搜索历史
        if request.user_id:
            try:
                # 将 SourceDetail 对象转换为 dict
                sources_for_history = [
                    {
                        "mongo_id": s.mongo_id,
                        "source": s.source,
                        "title": s.title,
                        "score": s.score,
                        "category": {
                            "大类": s.category.大类,
                            "类别": s.category.类别,
                            "地域": s.category.地域
                        },
                        "publish_time": s.publish_time,
                        "preview": s.preview[:200] if s.preview else ""
                    }
                    for s in enhanced_sources
                ]

                history_id = await search_history_service.save_from_sync_response(
                    user_id=int(request.user_id),
                    question=request.question,
                    answer=full_answer,
                    sources=sources_for_history,
                    conversation_id=request.conversation_id,
                    search_mode=request.search_mode
                )
                logger.info(f"搜索历史已保存: history_id={history_id}, user_id={request.user_id}")

            except Exception as e:
                logger.warning(f"保存搜索历史失败: {e}")

        # 6. 构建响应
        response_data = ChatSyncResponse(
            question=request.question,
            answer=full_answer,
            sources=enhanced_sources,
            sources_count=len(enhanced_sources),
            answer_length=len(full_answer),
            status=stream_status
        )

        return response_data

    except ValueError as e:
        logger.error(f"输入验证失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )

    except Exception as e:
        logger.error(f"Chat同步搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "搜索失败",
                "message": "服务暂时不可用，请稍后重试"
            }
        )


# ==================== 对话历史 API ====================
# v1.1.0 新增：对话会话持久化
# chat_conversation_repository 已在文件顶部导入


class InfoItemModel(BaseModel):
    """信息条目存储模型 (v2.9.0 优化, v2.10.1 响应优化)

    只存储引用信息 (mongo_id + source)，查询时从原表填充完整数据。
    优化目的: 减少数据冗余，降低数据库存储压力，保证数据一致性。

    v2.10.1: 添加 exclude_none 配置，列表接口不返回 null 字段。
    前端需要完整数据时使用 POST /chat/messages/batch-sources 接口。
    """
    model_config = ConfigDict(
        # 不返回值为 None 的字段，让响应更干净
        exclude_none=True
    )

    id: str = Field(..., description="条目ID (同 mongo_id)")
    mongo_id: str = Field(..., description="MongoDB 数据库 ID")
    source: str = Field(..., description="来源类型 (新闻/用户上传)")
    # 以下字段为可选，用于兼容旧数据和查询时填充
    title: Optional[str] = Field(None, description="标题 (查询时填充)")
    score: Optional[float] = Field(None, description="相关性评分 (查询时填充)")
    preview: Optional[str] = Field(None, description="预览内容 (查询时填充)")


class ConversationCreateRequest(BaseModel):
    """创建对话会话请求

    v2.7.0: user_id 已移除，后端从 Token 自动获取用户身份
    """
    title: Optional[str] = Field(None, description="会话标题（可选，自动从首条消息生成）")
    is_pinned: Optional[bool] = Field(False, description="是否置顶")


class ConversationCreateResponse(BaseModel):
    """创建对话会话响应"""
    conversation_id: str
    title: str
    created_at: str


class MessageModel(BaseModel):
    """消息模型"""
    id: str
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    timestamp: str
    sources: List[Dict[str, Any]] = []
    info_items: List[InfoItemModel] = Field(default_factory=list, description="关联的信息条目")


class ConversationModel(BaseModel):
    """对话会话模型

    v2.7.0: 新增 is_pinned 和 info_items 字段
    """
    id: str = Field(..., alias="_id")
    title: str
    user_id: Optional[str]
    messages: List[MessageModel]
    message_count: int
    last_message_at: str
    created_at: str
    is_pinned: bool = Field(default=False, description="是否置顶")
    info_items: List[InfoItemModel] = Field(default_factory=list, description="对话关联的信息条目")

    class Config:
        populate_by_name = True


class ConversationListItem(BaseModel):
    """对话列表项"""
    id: str = Field(..., alias="_id")
    title: str
    user_id: Optional[str]
    message_count: int
    last_message_at: str
    last_message: Optional[MessageModel]
    created_at: str
    is_pinned: bool = Field(default=False, description="是否置顶")

    class Config:
        populate_by_name = True


class ConversationListResponse(BaseModel):
    """对话列表响应"""
    conversations: List[ConversationListItem]
    total: int
    has_more: bool


class AddMessageRequest(BaseModel):
    """添加消息请求"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    sources: Optional[List[Dict[str, Any]]] = None
    info_items: Optional[List[InfoItemModel]] = Field(None, description="关联的信息条目")


@router.post(
    "/chat/conversations",
    response_model=ConversationCreateResponse,
    summary="创建对话会话",
    description="创建新的对话会话，返回会话ID。v2.7.0: 需要 Token 认证"
)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """创建新对话会话

    v2.7.0: user_id 从 Token 自动获取，不再从请求参数传入
    """
    try:
        # v2.7.0: 从 Token 获取用户 ID
        user_id = str(current_user.id)

        conversation_id = await chat_conversation_repository.create_conversation(
            user_id=user_id,
            title=request.title,
            metadata={"is_pinned": request.is_pinned or False}
        )

        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        logger.info(f"创建对话会话成功: conv_id={conversation_id}, user_id={user_id}")

        return ConversationCreateResponse(
            conversation_id=conversation_id,
            title=conversation["title"],
            created_at=conversation["created_at"].isoformat()
        )

    except Exception as e:
        logger.error(f"创建对话会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建对话会话失败")


@router.get(
    "/chat/conversations",
    response_model=ConversationListResponse,
    summary="获取对话列表",
    description="获取用户的对话会话列表（分页）。v2.7.0: 需要 Token 认证，admin 可查看所有，普通用户只能查看自己的"
)
async def get_conversations(
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: int = 20,
    offset: int = 0
):
    """获取对话列表

    v2.7.0: 用户隔离
    - admin 角色可查看所有对话
    - 普通用户只能查看自己的对话
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else str(current_user.id)

        logger.info(f"获取对话列表: user_id={current_user.id}, is_admin={is_admin}, effective_filter={effective_user_id}")

        conversations = await chat_conversation_repository.get_recent_conversations(
            user_id=effective_user_id,
            limit=limit + 1,  # 多取一条判断是否有更多
            offset=offset
        )

        has_more = len(conversations) > limit
        if has_more:
            conversations = conversations[:limit]

        total = await chat_conversation_repository.count_conversations(user_id=effective_user_id)

        # 转换时间格式
        items = []
        for conv in conversations:
            last_msg = conv.get("last_message")
            metadata = conv.get("metadata", {})
            items.append(ConversationListItem(
                _id=conv["_id"],
                title=conv["title"],
                user_id=conv.get("user_id"),
                message_count=conv["message_count"],
                last_message_at=conv["last_message_at"].isoformat() if conv.get("last_message_at") else "",
                last_message=MessageModel(
                    id=last_msg["id"],
                    role=last_msg["role"],
                    content=last_msg["content"],
                    timestamp=last_msg["timestamp"],
                    sources=last_msg.get("sources", []),
                    info_items=last_msg.get("info_items", [])
                ) if last_msg else None,
                created_at=conv["created_at"].isoformat() if conv.get("created_at") else "",
                is_pinned=metadata.get("is_pinned", False)
            ))

        return ConversationListResponse(
            conversations=items,
            total=total,
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取对话列表失败")


@router.get(
    "/chat/conversations/{conversation_id}",
    summary="获取对话详情",
    description="获取指定对话会话的完整信息和消息历史。v2.7.0: 需要 Token 认证，非 admin 只能访问自己的对话"
)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """获取对话详情

    v2.7.0: 用户隔离 - 非 admin 只能访问自己的对话
    """
    try:
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=True
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查 - 非 admin 只能访问自己的对话
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能查看自己的对话"
                }
            )

        # 转换时间格式 + v2.9.0: 填充 info_items 完整数据
        messages = []
        for msg in conversation.get("messages", []):
            # v2.9.0: 填充消息中的 info_items
            msg_info_items = msg.get("info_items", [])
            if msg_info_items:
                msg_info_items = await populate_info_items(msg_info_items)

            messages.append({
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "sources": msg.get("sources", []),
                "info_items": msg_info_items
            })

        # v2.9.0: 填充对话级别的 info_items
        conv_info_items = conversation.get("info_items", [])
        if conv_info_items:
            conv_info_items = await populate_info_items(conv_info_items)

        metadata = conversation.get("metadata", {})
        return {
            "id": conversation["_id"],
            "title": conversation["title"],
            "user_id": conversation.get("user_id"),
            "messages": messages,
            "message_count": conversation["message_count"],
            "last_message_at": conversation["last_message_at"].isoformat() if conversation.get("last_message_at") else "",
            "created_at": conversation["created_at"].isoformat() if conversation.get("created_at") else "",
            "is_pinned": metadata.get("is_pinned", False),
            "info_items": conv_info_items
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取对话详情失败")


@router.post(
    "/chat/conversations/{conversation_id}/messages",
    summary="添加消息",
    description="向对话会话添加新消息。v2.7.0: 需要 Token 认证，非 admin 只能向自己的对话添加消息"
)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """添加消息到对话

    v2.7.0: 用户隔离 - 非 admin 只能向自己的对话添加消息
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能向自己的对话添加消息"
                }
            )

        # 转换 info_items 为字典格式
        info_items_dict = None
        if request.info_items:
            info_items_dict = [item.model_dump() for item in request.info_items]

        message_id = await chat_conversation_repository.add_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
            sources=request.sources,
            metadata={"info_items": info_items_dict} if info_items_dict else None
        )

        if not message_id:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "role": request.role,
            "content": request.content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="添加消息失败")


@router.get(
    "/chat/conversations/{conversation_id}/messages",
    summary="获取消息历史",
    description="获取对话会话的消息历史（支持分页）。v2.7.0: 需要 Token 认证，非 admin 只能获取自己的对话消息"
)
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: Optional[int] = None,
    before: Optional[str] = None
):
    """获取消息历史

    v2.7.0: 用户隔离 - 非 admin 只能获取自己的对话消息
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能获取自己的对话消息"
                }
            )

        messages = await chat_conversation_repository.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            before_message_id=before
        )

        if messages is None:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        return {
            "conversation_id": conversation_id,
            "messages": messages,
            "count": len(messages)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取消息历史失败")


class UpdateConversationRequest(BaseModel):
    """更新对话请求 - v2.7.0 扩展"""
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="会话标题")
    is_pinned: Optional[bool] = Field(None, description="是否置顶")


@router.patch(
    "/chat/conversations/{conversation_id}",
    summary="更新对话",
    description="更新对话会话的标题或置顶状态。v2.7.0: 需要 Token 认证，非 admin 只能更新自己的对话"
)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """更新对话

    v2.7.0: 用户隔离 - 非 admin 只能更新自己的对话
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能更新自己的对话"
                }
            )

        # 更新标题
        if request.title:
            await chat_conversation_repository.update_title(
                conversation_id=conversation_id,
                title=request.title
            )

        # 更新置顶状态
        if request.is_pinned is not None:
            await chat_conversation_repository.update_metadata(
                conversation_id=conversation_id,
                metadata={"is_pinned": request.is_pinned},
                merge=True
            )

        return {
            "success": True,
            "title": request.title,
            "is_pinned": request.is_pinned
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新对话失败")


@router.delete(
    "/chat/conversations/{conversation_id}",
    summary="删除对话",
    description="删除指定的对话会话。v2.7.0: 需要 Token 认证，非 admin 只能删除自己的对话"
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """删除对话会话

    v2.7.0: 用户隔离 - 非 admin 只能删除自己的对话
    """
    try:
        # v2.7.0: 先检查对话归属
        conversation = await chat_conversation_repository.get_by_id(
            conversation_id, include_messages=False
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        # v2.7.0: 权限检查
        is_admin = "admin" in current_user.roles
        conv_owner_id = conversation.get("user_id")
        if not is_admin and str(conv_owner_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能删除自己的对话"
                }
            )

        success = await chat_conversation_repository.delete_conversation(
            conversation_id=conversation_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="对话会话不存在")

        logger.info(f"删除对话会话成功: conv_id={conversation_id}, user_id={current_user.id}")

        return {"success": True, "deleted_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除对话会话失败")


@router.get(
    "/chat/conversations/search",
    summary="搜索对话",
    description="按关键词搜索对话会话。v2.7.0: 需要 Token 认证，admin 可搜索所有，普通用户只能搜索自己的"
)
async def search_conversations(
    q: str,
    current_user: User = Depends(get_current_active_user),  # v2.7.0: 强制 Token 认证
    limit: int = 20
):
    """搜索对话

    v2.7.0: 用户隔离
    - admin 角色可搜索所有对话
    - 普通用户只能搜索自己的对话
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else str(current_user.id)

        logger.info(f"搜索对话: user_id={current_user.id}, is_admin={is_admin}, query='{q[:20]}...'")

        conversations = await chat_conversation_repository.search_conversations(
            query=q,
            user_id=effective_user_id,
            limit=limit
        )

        items = []
        for conv in conversations:
            last_msg = conv.get("last_message")
            metadata = conv.get("metadata", {})
            items.append({
                "id": conv["_id"],
                "title": conv["title"],
                "user_id": conv.get("user_id"),
                "message_count": conv["message_count"],
                "last_message_at": conv["last_message_at"].isoformat() if conv.get("last_message_at") else "",
                "last_message": {
                    "id": last_msg["id"],
                    "role": last_msg["role"],
                    "content": last_msg["content"],
                    "timestamp": last_msg["timestamp"],
                    "sources": last_msg.get("sources", []),
                    "info_items": last_msg.get("info_items", [])
                } if last_msg else None,
                "created_at": conv["created_at"].isoformat() if conv.get("created_at") else "",
                "is_pinned": metadata.get("is_pinned", False)
            })

        return {
            "query": q,
            "results": items,
            "count": len(items)
        }

    except Exception as e:
        logger.error(f"搜索对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="搜索对话失败")


# ==================== 搜索历史 API (v2.8.0) ====================

class SearchHistoryResultModel(BaseModel):
    """搜索结果项模型"""
    mongo_id: str
    source: str
    title: str
    score: float
    category: Optional[Dict[str, str]] = None
    publish_time: Optional[str] = None
    preview: Optional[str] = None


class SearchHistoryItemModel(BaseModel):
    """搜索历史记录模型"""
    id: str = Field(..., alias="_id")
    user_id: int
    query: str
    answer: Optional[str] = None
    results: Optional[List[SearchHistoryResultModel]] = None
    results_count: int = 0
    conversation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    class Config:
        populate_by_name = True


class SearchHistoryListResponse(BaseModel):
    """搜索历史列表响应"""
    items: List[SearchHistoryItemModel]
    total: int
    limit: int
    offset: int


class SearchHistoryStatsResponse(BaseModel):
    """搜索统计响应"""
    total_searches: int
    total_results: int
    avg_results_per_search: float


@router.get(
    "/chat/search-history",
    summary="获取搜索历史列表",
    description="获取当前用户的搜索历史记录（分页）。v2.8.0 新增"
)
async def get_search_history(
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    offset: int = 0,
    source_filter: Optional[str] = None
):
    """获取用户搜索历史列表

    Args:
        limit: 返回数量限制
        offset: 偏移量
        source_filter: 按来源类型筛选 (可选)
    """
    try:
        result = await search_history_service.get_user_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            source_filter=source_filter
        )

        # 转换日期格式
        items = []
        for item in result["items"]:
            items.append({
                "_id": item["_id"],
                "user_id": item["user_id"],
                "query": item["query"],
                "answer": item.get("answer"),
                "results_count": item.get("results_count", 0),
                "conversation_id": item.get("conversation_id"),
                "metadata": item.get("metadata"),
                "created_at": item["created_at"].isoformat() if item.get("created_at") else None
            })

        return SearchHistoryListResponse(
            items=items,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"]
        )

    except Exception as e:
        logger.error(f"获取搜索历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取搜索历史失败")


@router.get(
    "/chat/search-history/{history_id}",
    summary="获取搜索历史详情",
    description="获取指定搜索历史的完整详情"
)
async def get_search_history_detail(
    history_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取搜索历史详情"""
    try:
        history = await search_history_service.get_history_detail(
            history_id=history_id,
            user_id=current_user.id
        )

        if not history:
            raise HTTPException(status_code=404, detail="历史记录不存在")

        return {
            "_id": history["_id"],
            "user_id": history["user_id"],
            "query": history["query"],
            "answer": history.get("answer"),
            "results": history.get("results", []),
            "results_count": history.get("results_count", 0),
            "conversation_id": history.get("conversation_id"),
            "metadata": history.get("metadata"),
            "created_at": history["created_at"].isoformat() if history.get("created_at") else None,
            "updated_at": history["updated_at"].isoformat() if history.get("updated_at") else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取搜索历史详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取搜索历史详情失败")


@router.get(
    "/chat/search-history/by-result/{mongo_id}",
    summary="按结果ID查询历史",
    description="查询引用了特定搜索结果的历史记录"
)
async def find_history_by_result(
    mongo_id: str,
    current_user: User = Depends(get_current_active_user),
    limit: int = 20
):
    """查询包含特定 mongo_id 的历史记录"""
    try:
        histories = await search_history_service.find_by_result_id(
            mongo_id=mongo_id,
            user_id=current_user.id,
            limit=limit
        )

        items = []
        for h in histories:
            items.append({
                "_id": h["_id"],
                "query": h["query"],
                "results_count": h.get("results_count", 0),
                "created_at": h["created_at"].isoformat() if h.get("created_at") else None
            })

        return {"items": items, "count": len(items)}

    except Exception as e:
        logger.error(f"按结果ID查询历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败")


@router.get(
    "/chat/search-history/by-source/{source}",
    summary="按来源类型查询历史",
    description="查询包含特定来源类型的历史记录"
)
async def find_history_by_source(
    source: str,
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    offset: int = 0
):
    """按来源类型查询历史记录"""
    try:
        histories = await search_history_service.find_by_source_type(
            source=source,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )

        items = []
        for h in histories:
            items.append({
                "_id": h["_id"],
                "query": h["query"],
                "results_count": h.get("results_count", 0),
                "created_at": h["created_at"].isoformat() if h.get("created_at") else None
            })

        return {"items": items, "count": len(items)}

    except Exception as e:
        logger.error(f"按来源类型查询历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败")


@router.get(
    "/chat/search-history/stats",
    response_model=SearchHistoryStatsResponse,
    summary="获取搜索统计",
    description="获取用户的搜索行为统计"
)
async def get_search_stats(
    current_user: User = Depends(get_current_active_user)
):
    """获取用户搜索统计"""
    try:
        stats = await search_history_service.get_user_statistics(current_user.id)
        return SearchHistoryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"获取搜索统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取统计失败")


@router.delete(
    "/chat/search-history/{history_id}",
    summary="删除搜索历史",
    description="删除指定的搜索历史记录"
)
async def delete_search_history(
    history_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除搜索历史记录"""
    try:
        success = await search_history_service.delete_history(
            history_id=history_id,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(status_code=404, detail="历史记录不存在或无权删除")

        return {"message": "删除成功", "history_id": history_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除搜索历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除失败")


# ==================== 批量查询 API (v2.10.0) ====================

class BatchSourcesRequest(BaseModel):
    """批量查询来源数据请求 (v2.10.0)"""
    message_ids: List[str] = Field(
        ...,
        description="消息ID列表 (雪花ID)",
        min_length=1,
        max_length=50  # 限制批量查询数量
    )


class PopulatedSourceItem(BaseModel):
    """填充后的来源数据项"""
    mongo_id: str = Field(..., description="MongoDB 数据库 ID")
    source: str = Field(..., description="来源类型")
    title: Optional[str] = Field(None, description="标题")
    preview: Optional[str] = Field(None, description="预览内容")
    url: Optional[str] = Field(None, description="原文链接")
    content_zh: Optional[str] = Field(None, description="中文内容")
    summary_zh: Optional[str] = Field(None, description="中文摘要")


class MessageSourcesResult(BaseModel):
    """单条消息的来源数据"""
    message_id: str = Field(..., description="消息ID")
    conversation_id: str = Field(..., description="对话ID")
    sources: List[PopulatedSourceItem] = Field(default_factory=list, description="填充后的来源数据")


class BatchSourcesResponse(BaseModel):
    """批量查询来源数据响应"""
    results: List[MessageSourcesResult] = Field(default_factory=list)
    found_count: int = Field(..., description="找到的消息数量")
    requested_count: int = Field(..., description="请求的消息数量")


async def populate_info_items_full(info_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """填充 info_items 的完整数据 (v2.10.0 增强版)

    从原表查询完整信息，包含 content_zh, summary_zh 等字段。

    Args:
        info_items: 只包含 mongo_id + source 的引用列表

    Returns:
        填充了完整信息的列表
    """
    if not info_items:
        return []

    db = await get_mongodb_database()
    populated_items = []

    for item in info_items:
        mongo_id = item.get("mongo_id") or item.get("id")
        source = item.get("source", "")

        if not mongo_id:
            populated_items.append(item)
            continue

        try:
            if source == "用户上传":
                # 从 file_uploads 集合查询
                result = await db["file_uploads"].find_one(
                    {"_id": ObjectId(mongo_id)},
                    {"title": 1, "content": 1, "storage_url": 1, "_id": 0}
                )
                if result:
                    content = result.get("content", "")
                    populated_items.append({
                        "mongo_id": mongo_id,
                        "source": source,
                        "title": result.get("title") or item.get("title", ""),
                        "preview": content[:200] if content else "",
                        "url": result.get("storage_url"),
                        "content_zh": content,
                        "summary_zh": None,
                    })
                else:
                    populated_items.append({
                        "mongo_id": mongo_id,
                        "source": source,
                        "title": item.get("title", ""),
                        "preview": item.get("preview", ""),
                    })
            else:
                # 从 news_results 集合查询
                result = await db["news_results"].find_one(
                    {"_id": mongo_id},
                    {
                        "url": 1,
                        "news_results.title_zh": 1,
                        "news_results.summary_zh": 1,
                        "news_results.content_zh": 1,
                        "_id": 0
                    }
                )
                if result:
                    nested = result.get("news_results", {})
                    content_zh = nested.get("content_zh", "")
                    populated_items.append({
                        "mongo_id": mongo_id,
                        "source": source,
                        "title": nested.get("title_zh") or item.get("title", ""),
                        "preview": content_zh[:200] if content_zh else "",
                        "url": result.get("url"),
                        "content_zh": content_zh,
                        "summary_zh": nested.get("summary_zh"),
                    })
                else:
                    populated_items.append({
                        "mongo_id": mongo_id,
                        "source": source,
                        "title": item.get("title", ""),
                        "preview": item.get("preview", ""),
                    })

        except Exception as e:
            logger.warning(f"填充 info_item 完整数据失败 (mongo_id={mongo_id}): {e}")
            populated_items.append({
                "mongo_id": mongo_id,
                "source": source,
                "title": item.get("title", ""),
                "preview": item.get("preview", ""),
            })

    return populated_items


@router.post(
    "/chat/messages/batch-sources",
    response_model=BatchSourcesResponse,
    summary="批量查询消息关联的来源数据 (v2.10.0)",
    description="根据消息ID (雪花ID) 批量查询消息关联的 info_items 中的 mongo_id 对应的完整数据"
)
async def batch_get_message_sources(
    request: BatchSourcesRequest,
    current_user: User = Depends(get_current_active_user)
):
    """批量查询消息关联的来源数据

    用于用户点击历史记录时，根据 message_id 查询该消息关联的所有来源数据。

    **数据流**:
    1. 根据 message_ids 从 chat_conversations 集合查询消息
    2. 提取每条消息的 info_items
    3. 根据 info_items 中的 mongo_id + source 从原表查询完整数据
    4. 返回填充后的完整来源数据

    Args:
        request: 包含 message_ids 的请求体

    Returns:
        BatchSourcesResponse: 每个 message_id 对应的完整来源数据

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/chat/messages/batch-sources" \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{"message_ids": ["msg_id_1", "msg_id_2"]}'
        ```
    """
    try:
        logger.info(f"批量查询消息来源: user_id={current_user.id}, count={len(request.message_ids)}")

        # 1. 批量查询消息
        # v2.10.0: 用户隔离 - 只能查询自己的消息（admin 可查所有）
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else str(current_user.id)

        messages = await chat_conversation_repository.get_messages_by_ids(
            message_ids=request.message_ids,
            user_id=effective_user_id
        )

        if not messages:
            return BatchSourcesResponse(
                results=[],
                found_count=0,
                requested_count=len(request.message_ids)
            )

        # 2. 对每条消息的 info_items 进行填充
        results = []
        for msg_id, msg_data in messages.items():
            info_items = msg_data.get("info_items", [])

            # 填充完整数据
            if info_items:
                populated_sources = await populate_info_items_full(info_items)
            else:
                populated_sources = []

            results.append(MessageSourcesResult(
                message_id=msg_id,
                conversation_id=msg_data.get("conversation_id", ""),
                sources=[
                    PopulatedSourceItem(**s) for s in populated_sources
                ]
            ))

        logger.info(f"批量查询完成: 请求={len(request.message_ids)}, 找到={len(results)}")

        return BatchSourcesResponse(
            results=results,
            found_count=len(results),
            requested_count=len(request.message_ids)
        )

    except Exception as e:
        logger.error(f"批量查询消息来源失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="批量查询失败")
