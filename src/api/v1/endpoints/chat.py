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
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator, List, Dict, Any
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.config import nl_search_config
from src.infrastructure.database.connection import get_mongodb_database
from bson import ObjectId

logger = logging.getLogger(__name__)

# AI服务配置
REMOTE_AI_SERVICE_URL = "http://192.168.0.5:8035/chat"
REMOTE_AI_SERVICE_TIMEOUT = 120.0

router = APIRouter()


# ==================== 数据模型 ====================

class ChatRequest(BaseModel):
    """Chat请求模型（兼容前端）"""
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

    class Config:
        json_schema_extra = {
            "example": {
                "question": "请介绍关于西藏的新闻"
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
    description="调用本地NL Search服务，自动保存到MongoDB并返回完整内容",
    response_model=ChatSyncResponse
)
async def chat_sync_endpoint(request: ChatRequest):
    """
    Chat接口 - 同步返回完整结果（含完整内容）

    **功能** (v2.5.0 - news_results集成):
    1. 调用本地 NL Search 服务执行搜索（sonar-pro + firecrawl + 入库）
    2. 自动保存搜索记录到 MongoDB nl_search_logs 集合
    3. 调用远程 AI 服务 (http://192.168.0.5:8035/chat) 进行智能处理
    4. 提取 AI 返回的 sources 中的 mongo_id
    5. 查询 MongoDB news_results 获取完整内容（包含中文翻译字段）
    6. 返回 AI 增强的响应（含完整内容和中文翻译）

    **数据流**:
    - 用户问题 → NLSearchService.create_search() → 保存到 MongoDB
    - 搜索结果 → 远程 AI 服务 → AI 生成答案 + 智能排序来源
    - sources[].mongo_id → news_results 查询 → 完整内容（嵌套结构 + 中文翻译）
    - 合并数据 → 返回前端

    Args:
        request (ChatRequest): Chat请求

    Returns:
        ChatSyncResponse: 包含完整内容的响应

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/chat/sync" \\
          -H "Content-Type: application/json" \\
          -d '{"question": "请介绍关于西藏的新闻"}'
        ```
    """
    try:
        logger.info(f"Chat同步请求: question='{request.question[:50]}...'")

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
                # 使用 stream 方法处理 SSE 响应
                async with client.stream(
                    "POST",
                    REMOTE_AI_SERVICE_URL,
                    json={
                        "question": request.question,
                        "search_results": result.get("results", []),
                        "user_id": request.user_id,
                        "log_id": log_id
                    }
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

        # 5. 构建响应
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
