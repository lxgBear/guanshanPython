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

from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.config import nl_search_config
from src.infrastructure.database.connection import get_mongodb_database

logger = logging.getLogger(__name__)

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
    """来源详情模型（增强版，包含完整内容）"""
    id: str = Field(..., description="UUID")
    mongo_id: str = Field(..., description="MongoDB ID")
    title: str = Field(..., description="标题")
    source: str = Field(..., description="来源网站")
    score: float = Field(..., description="相关性评分")
    category: CategoryModel = Field(..., description="分类信息")
    publish_time: str = Field(..., description="发布时间")
    preview: str = Field(..., description="内容预览")
    url: Optional[str] = Field(None, description="完整URL（从news_results查询）")
    markdown_content: Optional[str] = Field(None, description="完整Markdown内容（从news_results查询）")
    content_length: Optional[int] = Field(None, description="内容长度")
    title_zh: Optional[str] = Field(None, description="中文标题（从news_results.news_results查询）")
    summary_zh: Optional[str] = Field(None, description="中文摘要/翻译内容（从news_results.news_results查询）")
    content_zh: Optional[str] = Field(None, description="中文总结（从news_results.news_results查询）")


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
    data: {"type": "result", "data": {...}}
    data: {"type": "done", "log_id": "123456"}
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

        # 映射 question → query_text
        async def event_generator() -> AsyncGenerator[str, None]:
            """生成SSE事件流"""
            try:
                # 1. 发送状态：开始搜索
                yield f"data: {json.dumps({'type': 'status', 'message': '正在分析您的问题...'}, ensure_ascii=False)}\n\n"

                # 2. 调用NL Search服务
                result = await nl_search_service.create_search(
                    query_text=request.question,
                    user_id=request.user_id,
                    search_mode=request.search_mode
                )

                log_id = result["log_id"]
                logger.info(f"搜索成功: log_id={log_id}, results_count={len(result.get('results', []))}")

                # 3. 发送分析结果
                if result.get("analysis"):
                    yield f"data: {json.dumps({'type': 'analysis', 'data': result['analysis']}, ensure_ascii=False)}\n\n"

                # 4. 逐条发送搜索结果
                for idx, item in enumerate(result.get("results", [])):
                    result_data = {
                        "type": "result",
                        "index": idx,
                        "data": {
                            "mongo_id": item.get("mongo_id"),
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "preview": item.get("preview"),
                            "source": item.get("source"),
                            "category": item.get("category"),
                            "score": item.get("score", 0.0)
                        }
                    }
                    yield f"data: {json.dumps(result_data, ensure_ascii=False)}\n\n"

                # 5. 发送完成状态
                done_data = {
                    "type": "done",
                    "log_id": log_id,
                    "total_results": len(result.get("results", [])),
                    "search_mode": request.search_mode
                }

                # Single模式：添加统计信息
                if request.search_mode == "single":
                    done_data["total_raw_results"] = result.get("total_results")
                    done_data["high_score_results"] = result.get("high_score_results")

                # Multi模式：添加子问题信息
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
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

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
    description="调用外部Chat API，查询MongoDB获取完整内容",
    response_model=ChatSyncResponse
)
async def chat_sync_endpoint(request: ChatRequest):
    """
    Chat接口 - 同步返回完整结果（含完整内容）

    **功能**:
    1. 调用外部 Chat API (http://192.168.0.5:8035/chat)
    2. 收集流式 SSE 响应
    3. 提取 sources 中的 mongo_id
    4. 查询 MongoDB news_results 获取完整内容（url, markdown_content）
    5. 返回增强的响应（含完整内容）

    **数据流**:
    - 用户问题 → 外部Chat API → SSE响应
    - sources[].mongo_id → MongoDB查询 → 完整内容
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

        # 1. 调用外部 Chat API
        external_chat_url = "http://192.168.0.5:8035/chat"
        full_answer = ""
        sources_data = []
        stream_status = "unknown"

        # 配置：禁用代理以访问本地网络
        proxies = {
            'http://': None,
            'https://': None
        }

        async with httpx.AsyncClient(proxies=proxies, timeout=60.0) as client:
            async with client.stream(
                'POST',
                external_chat_url,
                json={"question": request.question},
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()

                # 2. 解析 SSE 流式响应
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # SSE 格式: "data: {json}"
                    if line.startswith('data: '):
                        json_text = line[6:]  # 去掉 "data: " 前缀

                        try:
                            chunk_data = json.loads(json_text)
                            chunk_type = chunk_data.get('type', 'unknown')

                            # 收集答案块
                            if chunk_type == 'answer_chunk':
                                full_answer += chunk_data.get('data', '')

                            # 收集来源数据
                            elif chunk_type == 'sources':
                                sources_data = chunk_data.get('data', [])

                            # 记录流结束状态
                            elif chunk_type == 'stream_end':
                                stream_status = chunk_data.get('data', {}).get('status', 'success')

                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON解析失败: {json_text[:100]}... 错误: {e}")
                            continue

        logger.info(f"外部API响应: answer_length={len(full_answer)}, sources_count={len(sources_data)}, status={stream_status}")

        # 3. 查询 MongoDB 获取完整内容
        db = await get_mongodb_database()
        enhanced_sources = []

        for source in sources_data:
            mongo_id = source.get('mongo_id')
            if not mongo_id:
                logger.warning(f"来源缺少mongo_id: {source.get('id')}")
                continue

            # 查询 news_results 集合（包含嵌套的 news_results 字段）
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

            # 提取嵌套的 news_results 字段
            nested_news_results = news_result.get('news_results', {}) if news_result else {}

            # 构建增强的来源对象
            enhanced_source = SourceDetail(
                id=source.get('id', ''),
                mongo_id=mongo_id,
                title=source.get('title', ''),
                source=source.get('source', ''),
                score=source.get('score', 0.0),
                category=CategoryModel(**source.get('category', {})),
                publish_time=source.get('publish_time', '未知时间'),
                preview=source.get('preview', ''),
                url=news_result.get('url') if news_result else None,
                markdown_content=news_result.get('markdown_content') if news_result else None,
                content_length=len(news_result.get('markdown_content', '')) if news_result and news_result.get('markdown_content') else None,
                title_zh=nested_news_results.get('title_zh'),
                summary_zh=nested_news_results.get('summary_zh'),
                content_zh=nested_news_results.get('content_zh')
            )

            enhanced_sources.append(enhanced_source)

        logger.info(f"MongoDB查询完成: {len(enhanced_sources)}/{len(sources_data)} 条记录获取了完整内容")

        # 4. 构建响应
        response_data = ChatSyncResponse(
            question=request.question,
            answer=full_answer,
            sources=enhanced_sources,
            sources_count=len(enhanced_sources),
            answer_length=len(full_answer),
            status=stream_status
        )

        return response_data

    except httpx.HTTPError as e:
        logger.error(f"外部Chat API调用失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "外部API调用失败",
                "message": f"无法连接到Chat API: {str(e)}"
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
