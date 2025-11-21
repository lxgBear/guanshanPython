"""
自然语言搜索API (v1.0.0-beta)

**状态**: ✅ 功能完整（功能开关控制）
**设计文档**: docs/NL_SEARCH_IMPLEMENTATION_GUIDE.md

实现完成:
- ✅ API端点结构
- ✅ 功能状态检查
- ✅ 搜索创建（LLM + GPT5 Search集成）
- ✅ 记录查询（数据库持久化）
- ✅ 服务层编排

功能控制:
- 环境变量: NL_SEARCH_ENABLED (默认false)
- 测试模式: 无需API Key即可运行
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

# 导入服务层
from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.mongo_archive_service import mongo_archive_service  # 使用 MongoDB 版本
from src.services.nl_search.config import nl_search_config

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 数据模型 ====================

class NLSearchRequest(BaseModel):
    """自然语言搜索请求

    用户可以使用自然语言描述搜索需求，系统将通过LLM理解并执行搜索。
    """
    query_text: str = Field(
        ...,
        description="用户输入的自然语言查询",
        min_length=1,
        max_length=1000,
        examples=["最近有哪些AI技术突破", "2024年深度学习最新进展"]
    )
    user_id: Optional[str] = Field(
        None,
        description="用户ID（可选，用于个性化和历史记录）"
    )
    search_mode: str = Field(
        default="single",
        description="搜索模式: single=单次搜索(快速), multi=多问题分解搜索(深度)",
        pattern="^(single|multi)$"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "最近有哪些关于GPT-5的新闻",
                "user_id": "user_12345",
                "search_mode": "single"
            }
        }


class NLSearchResponse(BaseModel):
    """自然语言搜索响应（完整版）"""
    log_id: Optional[str] = Field(None, description="搜索记录ID（雪花算法ID字符串）")
    status: str = Field(..., description="搜索状态")
    message: str = Field(..., description="响应消息")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="搜索结果列表")
    analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    refined_query: Optional[str] = Field(None, description="精炼后的查询（single模式）")
    search_mode: Optional[str] = Field(None, description="搜索模式（single|multi）")
    sub_queries: Optional[List[str]] = Field(None, description="子问题列表（multi模式）")
    total_raw_results: Optional[int] = Field(None, description="原始结果总数（multi模式）")
    total_unique_results: Optional[int] = Field(None, description="去重后结果数（multi模式）")
    alternative_api: Optional[str] = Field(None, description="替代方案API")

    class Config:
        json_schema_extra = {
            "example": {
                "log_id": 12345,
                "status": "completed",
                "message": "搜索成功",
                "results": [
                    {"title": "AI技术突破", "url": "https://example.com/1", "snippet": "..."}
                ],
                "analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破"]
                },
                "refined_query": "AI技术突破 2024",
                "search_mode": "single"
            }
        }


class NLSearchLog(BaseModel):
    """自然语言搜索记录（完整版）"""
    id: str = Field(..., description="记录ID（雪花算法ID字符串）")
    query_text: str = Field(..., description="用户查询")
    created_at: str = Field(..., description="创建时间（ISO格式）")
    status: str = Field(..., description="搜索状态")
    analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123456,
                "query_text": "最近AI技术突破",
                "created_at": "2025-11-14T15:30:00",
                "status": "completed",
                "analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破"]
                }
            }
        }


class NLSearchStatus(BaseModel):
    """功能状态"""
    enabled: bool = Field(..., description="功能是否启用")
    version: str = Field(..., description="版本号")
    message: str = Field(..., description="状态说明")
    alternative_api: Optional[str] = Field(None, description="替代方案")
    documentation: Optional[str] = Field(None, description="设计文档链接")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": False,
                "version": "1.0.0-beta",
                "message": "自然语言搜索功能正在开发中，敬请期待",
                "alternative_api": "/api/v1/smart-search",
                "documentation": "docs/NL_SEARCH_IMPLEMENTATION_GUIDE.md"
            }
        }


class NLSearchListResponse(BaseModel):
    """搜索历史列表响应"""
    total: int = Field(..., description="总记录数")
    items: List[NLSearchLog] = Field(..., description="搜索记录列表")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class SearchResultItem(BaseModel):
    """搜索结果条目"""
    title: str = Field(..., description="结果标题")
    url: str = Field(..., description="结果URL")
    snippet: str = Field(..., description="结果摘要")
    position: int = Field(..., description="结果位置")
    score: float = Field(..., description="相关性评分")
    source: str = Field(..., description="来源（serpapi/web/cache）")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "GPT-5发布：AI技术新突破",
                "url": "https://example.com/gpt5",
                "snippet": "OpenAI发布最新GPT-5模型...",
                "position": 1,
                "score": 0.95,
                "source": "serpapi"
            }
        }


class SearchResultsResponse(BaseModel):
    """搜索结果响应"""
    log_id: str = Field(..., description="搜索记录ID（雪花算法ID字符串）")
    query_text: str = Field(..., description="用户查询")
    total_count: int = Field(..., description="结果总数")
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    llm_analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    status: str = Field(..., description="搜索状态")
    created_at: str = Field(..., description="创建时间（ISO格式）")

    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "248728141926559744",
                "query_text": "最近有哪些AI技术突破",
                "total_count": 10,
                "results": [
                    {
                        "title": "GPT-5发布",
                        "url": "https://example.com/gpt5",
                        "snippet": "OpenAI发布最新GPT-5模型...",
                        "position": 1,
                        "score": 0.95,
                        "source": "serpapi"
                    }
                ],
                "llm_analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破"]
                },
                "status": "completed",
                "created_at": "2025-11-17T08:00:00Z"
            }
        }


class UserSelectionRequest(BaseModel):
    """用户选择请求"""
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(..., description="操作类型（click/bookmark/archive）")
    user_id: Optional[str] = Field(None, description="用户ID（可选）")

    class Config:
        json_schema_extra = {
            "example": {
                "result_url": "https://example.com/gpt5",
                "action_type": "click",
                "user_id": "user_123"
            }
        }


class UserSelectionResponse(BaseModel):
    """用户选择响应"""
    event_id: str = Field(..., description="事件ID（雪花算法ID字符串）")
    log_id: str = Field(..., description="搜索记录ID")
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(..., description="操作类型")
    recorded_at: str = Field(..., description="记录时间（ISO格式）")
    message: str = Field(..., description="响应消息")

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "248728141926559745",
                "log_id": "248728141926559744",
                "result_url": "https://example.com/gpt5",
                "action_type": "click",
                "recorded_at": "2025-11-17T08:00:00Z",
                "message": "用户选择已记录"
            }
        }


# ==================== 档案管理数据模型 ====================

class ArchiveItemRequest(BaseModel):
    """档案条目请求"""
    news_result_id: str = Field(..., description="新闻结果ID（MongoDB ObjectId）")
    edited_title: Optional[str] = Field(None, description="编辑后的标题")
    edited_summary: Optional[str] = Field(None, description="编辑后的摘要")
    user_notes: Optional[str] = Field(None, description="用户备注")
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分 1-5")


class CreateArchiveRequest(BaseModel):
    """创建档案请求"""
    user_id: int = Field(..., description="用户ID", gt=0)
    archive_name: str = Field(..., description="档案名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="档案描述", max_length=2000)
    tags: Optional[List[str]] = Field(None, description="档案标签列表")
    search_log_id: Optional[str] = Field(None, description="关联的搜索记录ID（雪花算法ID字符串）")
    items: List[ArchiveItemRequest] = Field(..., description="档案条目列表", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1001,
                "archive_name": "2024年AI技术突破汇总",
                "description": "整理2024年重要的AI技术突破新闻",
                "tags": ["AI", "技术", "2024"],
                "search_log_id": 123456,
                "items": [
                    {
                        "news_result_id": "507f1f77bcf86cd799439011",
                        "edited_title": "GPT-5重磅发布",
                        "edited_summary": "OpenAI发布最新GPT-5模型...",
                        "user_rating": 5
                    }
                ]
            }
        }


class UpdateArchiveRequest(BaseModel):
    """更新档案请求"""
    archive_name: Optional[str] = Field(None, description="新的档案名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="新的描述", max_length=2000)
    tags: Optional[List[str]] = Field(None, description="新的标签列表")


class ArchiveItemResponse(BaseModel):
    """档案条目响应"""
    id: int = Field(..., description="条目ID")
    news_result_id: str = Field(..., description="新闻结果ID")
    title: str = Field(..., description="显示标题（优先显示编辑标题）")
    content: Optional[str] = Field(None, description="显示内容（优先显示编辑摘要）")
    edited_title: Optional[str] = Field(None, description="用户编辑的标题")
    edited_summary: Optional[str] = Field(None, description="用户编辑的摘要")
    user_notes: Optional[str] = Field(None, description="用户备注")
    user_rating: Optional[int] = Field(None, description="用户评分")
    category: Optional[Dict[str, str]] = Field(None, description="分类信息")
    source: Optional[str] = Field(None, description="新闻来源")
    created_at: Optional[str] = Field(None, description="添加时间")


class ArchiveResponse(BaseModel):
    """档案响应"""
    archive_id: str = Field(..., description="档案ID（MongoDB ObjectId）")
    user_id: int = Field(..., description="用户ID")
    archive_name: str = Field(..., description="档案名称")
    description: Optional[str] = Field(None, description="档案描述")
    tags: List[str] = Field(..., description="档案标签")
    search_log_id: Optional[str] = Field(None, description="关联的搜索记录ID（雪花算法ID字符串）")
    items_count: int = Field(..., description="档案条目数量")
    items: Optional[List[ArchiveItemResponse]] = Field(None, description="档案条目列表（仅详情接口返回）")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class ArchiveListResponse(BaseModel):
    """档案列表响应"""
    total: int = Field(..., description="总记录数")
    items: List[ArchiveResponse] = Field(..., description="档案列表")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


# ==================== API端点 ====================

@router.get(
    "/status",
    response_model=NLSearchStatus,
    summary="功能状态检查",
    description="检查自然语言搜索功能的当前状态和可用性"
)
async def get_nl_search_status():
    """
    检查自然语言搜索功能状态

    **当前状态**: 🚧 开发中 (MVP阶段)

    **开发进度**:
    - ✅ API结构设计
    - 🚧 LLM集成
    - 🚧 数据库实现
    - 🚧 前端集成

    **替代方案**:
    - 使用智能搜索API: `/api/v1/smart-search`
    - 该API支持LLM查询分解功能

    Returns:
        NLSearchStatus: 功能状态信息

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/status"
        ```
    """
    # 调用服务层获取状态
    service_status = await nl_search_service.get_service_status()

    return NLSearchStatus(
        enabled=service_status["enabled"],
        version=service_status["version"],
        message="自然语言搜索功能已就绪" if service_status["enabled"]
                else "功能已关闭，设置NL_SEARCH_ENABLED=true启用",
        alternative_api="/api/v1/smart-search" if not service_status["enabled"] else None,
        documentation="docs/NL_SEARCH_IMPLEMENTATION_GUIDE.md"
    )


@router.post(
    "/",
    response_model=NLSearchResponse,
    summary="创建自然语言搜索",
    description="使用自然语言创建搜索请求"
)
async def create_nl_search(request: NLSearchRequest):
    """
    创建自然语言搜索请求

    **功能**: ✅ 完整实现

    **流程**:
    1. 检查功能开关
    2. 接收用户的自然语言查询
    3. 使用LLM理解用户意图（关键词、实体、时间范围等）
    4. 调用GPT-5 Search执行搜索
    5. 返回结构化的搜索结果

    Args:
        request (NLSearchRequest): 搜索请求参数

    Returns:
        NLSearchResponse: 搜索响应，包含分析结果和搜索结果

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 400: 输入验证失败
            - 500: 内部错误

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search" \\
          -H "Content-Type: application/json" \\
          -d '{
            "query_text": "最近有哪些AI技术突破",
            "user_id": "user_123"
          }'
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        # 调用服务层
        logger.info(f"收到自然语言搜索请求: {request.query_text[:50]}... (mode={request.search_mode})")

        result = await nl_search_service.create_search(
            query_text=request.query_text,
            user_id=request.user_id,
            search_mode=request.search_mode
        )

        logger.info(f"搜索成功: log_id={result['log_id']}, mode={request.search_mode}")

        # 构建响应（根据搜索模式返回不同字段）
        response = NLSearchResponse(
            log_id=result["log_id"],
            status="completed",
            message="搜索成功",
            results=result["results"],
            analysis=result["analysis"],
            search_mode=result.get("search_mode", request.search_mode)
        )

        # Single模式：返回优化指标和精炼查询
        if request.search_mode == "single":
            response.refined_query = result.get("refined_query")  # 已废弃，保持兼容性
            response.total_raw_results = result.get("total_results")  # GPT返回总数
            response.total_unique_results = result.get("high_score_results")  # 分数过滤后爬取数

        # Multi模式：返回子问题和统计信息
        elif request.search_mode == "multi":
            response.sub_queries = result.get("sub_queries", [])
            response.total_raw_results = result.get("total_raw_results")
            response.total_unique_results = result.get("total_unique_results")

        return response

    except ValueError as e:
        # 输入验证错误
        logger.warning(f"输入验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )

    except Exception as e:
        # 内部错误
        logger.error(f"搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "搜索失败",
                "message": "服务暂时不可用，请稍后重试",
                "log_id": None
            }
        )


@router.get(
    "/{log_id}",
    response_model=NLSearchLog,
    summary="获取搜索记录",
    description="根据ID获取自然语言搜索记录"
)
async def get_nl_search_log(log_id: str):
    """
    获取自然语言搜索记录

    **功能**: ✅ 完整实现

    **功能**:
    - 根据log_id获取搜索记录
    - 包含LLM分析结果
    - 包含创建时间和状态

    Args:
        log_id (str): 搜索记录ID（雪花算法ID字符串）

    Returns:
        NLSearchLog: 搜索记录详情

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 404: 记录不存在
            - 500: 内部错误

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/123456"
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        logger.info(f"查询搜索记录: log_id={log_id}")

        # 调用服务层
        log = await nl_search_service.get_search_log(log_id)

        if not log:
            logger.warning(f"搜索记录不存在: log_id={log_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "记录不存在",
                    "message": f"未找到搜索记录: log_id={log_id}",
                    "log_id": log_id
                }
            )

        return NLSearchLog(
            id=log["log_id"],
            query_text=log["query_text"],
            created_at=log["created_at"],
            status="completed",
            analysis=log.get("analysis")
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取搜索记录失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取搜索记录失败，请稍后重试",
                "log_id": log_id
            }
        )


@router.get(
    "/",
    response_model=NLSearchListResponse,
    summary="查询搜索历史",
    description="分页查询自然语言搜索历史"
)
async def list_nl_search_logs(
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    user_id: Optional[str] = Query(None, description="过滤指定用户")
):
    """
    查询自然语言搜索历史

    **功能**: ✅ 完整实现

    **功能**:
    - 分页查询搜索历史
    - 支持按数量限制和偏移量分页
    - 返回记录总数和当前页信息

    Args:
        limit (int): 返回数量限制 (1-100)
        offset (int): 分页偏移量
        user_id (Optional[str]): 过滤指定用户的搜索记录（当前版本未使用）

    Returns:
        NLSearchListResponse: 搜索历史列表

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 500: 内部错误

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search?limit=10&offset=0"
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        logger.info(f"查询搜索历史: limit={limit}, offset={offset}, user_id={user_id}")

        # 调用服务层
        logs = await nl_search_service.list_search_logs(limit=limit, offset=offset)

        # 构建响应
        items = [
            NLSearchLog(
                id=log["log_id"],
                query_text=log["query_text"],
                created_at=log["created_at"],
                status="completed",
                analysis=log.get("analysis")
            )
            for log in logs
        ]

        return NLSearchListResponse(
            total=len(items),
            items=items,
            page=offset // limit + 1 if limit > 0 else 1,
            page_size=limit
        )

    except Exception as e:
        logger.error(f"查询搜索历史失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "查询搜索历史失败，请稍后重试"
            }
        )


# ==================== 附加功能（预留）====================

@router.post(
    "/{log_id}/select",
    response_model=UserSelectionResponse,
    summary="记录用户选择",
    description="记录用户对搜索结果的选择行为"
)
async def select_search_result(
    log_id: str,
    request: UserSelectionRequest
):
    """
    记录用户对搜索结果的选择

    **功能**: ✅ 完整实现

    **用途**:
    - 收集用户反馈和行为数据
    - 优化LLM理解和搜索质量
    - 支持个性化推荐
    - A/B测试和分析

    **支持的操作类型**:
    - click: 用户点击结果
    - bookmark: 用户收藏结果
    - archive: 用户归档结果

    Args:
        log_id (str): 搜索记录ID（雪花算法ID字符串）
        request (UserSelectionRequest): 用户选择请求

    Returns:
        UserSelectionResponse: 选择记录确认

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 400: 输入验证失败
            - 404: 搜索记录不存在
            - 500: 内部错误

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search/248728141926559744/select" \\
          -H "Content-Type: application/json" \\
          -d '{
            "result_url": "https://example.com/gpt5",
            "action_type": "click",
            "user_id": "user_123"
          }'
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        logger.info(
            f"记录用户选择: log_id={log_id}, "
            f"url={request.result_url}, action={request.action_type}"
        )

        # 验证操作类型
        valid_actions = ["click", "bookmark", "archive"]
        if request.action_type not in valid_actions:
            raise ValueError(
                f"无效的操作类型: {request.action_type}。"
                f"有效值: {', '.join(valid_actions)}"
            )

        # 调用服务层记录选择
        event_id = await nl_search_service.record_user_selection(
            log_id=log_id,
            result_url=request.result_url,
            action_type=request.action_type,
            user_id=request.user_id
        )

        logger.info(f"用户选择已记录: event_id={event_id}")

        return UserSelectionResponse(
            event_id=event_id,
            log_id=log_id,
            result_url=request.result_url,
            action_type=request.action_type,
            recorded_at=datetime.utcnow().isoformat(),
            message="用户选择已成功记录"
        )

    except ValueError as e:
        # 输入验证错误或搜索记录不存在
        logger.warning(f"验证失败: {e}")
        status_code = 404 if "不存在" in str(e) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": "验证失败" if status_code == 400 else "记录不存在",
                "message": str(e),
                "log_id": log_id
            }
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"记录用户选择失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "记录用户选择失败，请稍后重试",
                "log_id": log_id
            }
        )


@router.get(
    "/{log_id}/results",
    response_model=SearchResultsResponse,
    summary="获取自然语言搜索结果",
    description="""
获取自然语言搜索的所有结果（支持分页）

⚠️ **重要提示 - 系统区分**:
- 此端点用于 **自然语言搜索系统** (NL Search)
- 数据来源: `nl_search_logs` → `news_results`
- 如需访问通用搜索结果，请使用: `/api/v1/search-tasks/{task_id}/results`

**两个系统的区别**:
1. **自然语言搜索** (本端点):
   - 前缀: `/api/v1/nl-search/`
   - 数据表: `nl_search_logs` + `news_results`
   - 用途: LLM理解的自然语言查询

2. **通用搜索**:
   - 前缀: `/api/v1/search-tasks/`
   - 数据表: `search_tasks` + `search_results`
   - 用途: 传统关键词搜索
    """,
    responses={
        404: {
            "description": "搜索记录不存在",
            "content": {
                "application/json": {
                    "example": {
                        "error": "记录不存在",
                        "message": "未找到搜索记录: log_id=xxx",
                        "hint": "如果这是通用搜索任务，请使用 /api/v1/search-tasks/{task_id}/results"
                    }
                }
            }
        }
    }
)
async def get_search_results(
    log_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量")
):
    """
    获取自然语言搜索的所有结果

    **功能**: ✅ 完整实现

    **数据来源**: nl_search_logs → news_results (自然语言搜索系统)

    **功能**:
    - 返回LLM分析的结构化结果
    - 包含搜索来源和评分
    - 支持结果分页
    - 包含LLM分析结果

    Args:
        log_id (str): 搜索记录ID（雪花算法ID字符串，来自 nl_search_logs）
        limit (Optional[int]): 返回数量限制（1-100）
        offset (int): 分页偏移量

    Returns:
        SearchResultsResponse: 搜索结果列表

    Raises:
        HTTPException:
            - 503: 功能未启用
            - 404: 搜索记录不存在（提示: 检查是否使用了错误的端点）
            - 500: 内部错误

    Example:
        ```bash
        # 正确使用 (自然语言搜索)
        curl -X GET "http://localhost:8000/api/v1/nl-search/248728141926559744/results?limit=10&offset=0"

        # 如果是通用搜索，应使用:
        # curl -X GET "http://localhost:8000/api/v1/search-tasks/{task_id}/results"
        ```
    """
    # 检查功能开关
    if not nl_search_config.enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "功能未启用",
                "message": "自然语言搜索功能已关闭。设置环境变量 NL_SEARCH_ENABLED=true 启用此功能。",
                "alternative_endpoint": "/api/v1/smart-search",
                "status": "disabled"
            }
        )

    try:
        logger.info(f"获取搜索结果: log_id={log_id}, limit={limit}, offset={offset}")

        # 调用服务层获取搜索结果
        result = await nl_search_service.get_search_results(
            log_id=log_id,
            limit=limit,
            offset=offset
        )

        if not result:
            logger.warning(f"搜索记录不存在: log_id={log_id}")

            # ✨ 新增：检查是否为通用搜索任务ID（用户可能用错了端点）
            from src.infrastructure.database.connection import get_mongodb_database
            db = await get_mongodb_database()
            generic_task = await db['search_tasks'].find_one({'_id': log_id})

            if generic_task:
                # 用户使用了错误的端点 - 提供友好提示
                logger.info(f"检测到端点使用错误: ID {log_id} 属于通用搜索系统")
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "端点使用错误",
                        "message": f"ID {log_id} 属于通用搜索系统，不是自然语言搜索",
                        "correct_endpoint": f"/api/v1/search-tasks/{log_id}/results",
                        "current_endpoint": f"/api/v1/nl-search/{log_id}/results",
                        "hint": "自然语言搜索使用 /api/v1/nl-search/ 前缀，通用搜索使用 /api/v1/search-tasks/ 前缀",
                        "documentation": "查看 API 文档了解两个系统的区别: /api/docs"
                    }
                )

            # 确实不存在于任何系统
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "记录不存在",
                    "message": f"未找到搜索记录: log_id={log_id}",
                    "log_id": log_id,
                    "hint": "请检查 ID 是否正确，或该记录可能已被删除"
                }
            )

        # 构建搜索结果条目列表
        result_items = [
            SearchResultItem(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                position=item.get("position", 0),
                score=item.get("score", 0.0),
                source=item.get("source", "unknown")
            )
            for item in result["results"]
        ]

        return SearchResultsResponse(
            log_id=result["log_id"],
            query_text=result["query_text"],
            total_count=result["total_count"],
            results=result_items,
            llm_analysis=result.get("llm_analysis"),
            status=result.get("status", "completed"),
            created_at=result["created_at"]
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取搜索结果失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取搜索结果失败，请稍后重试",
                "log_id": log_id
            }
        )


# ==================== 档案管理API ====================

@router.post(
    "/archives",
    response_model=ArchiveResponse,
    summary="创建档案",
    description="从搜索结果创建用户档案"
)
async def create_archive(request: CreateArchiveRequest):
    """
    创建档案

    **功能**: ✅ 完整实现

    **流程**:
    1. 验证输入数据
    2. 为每个条目创建快照（从MongoDB news_results）
    3. 批量创建档案条目
    4. 返回档案信息

    Args:
        request (CreateArchiveRequest): 创建档案请求

    Returns:
        ArchiveResponse: 档案详情

    Raises:
        HTTPException:
            - 400: 输入验证失败
            - 500: 服务错误

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search/archives" \\
          -H "Content-Type: application/json" \\
          -d '{
            "user_id": 1001,
            "archive_name": "AI技术突破汇总",
            "description": "2024年重要AI技术突破",
            "tags": ["AI", "技术"],
            "items": [
              {
                "news_result_id": "507f1f77bcf86cd799439011",
                "edited_title": "GPT-5发布",
                "user_rating": 5
              }
            ]
          }'
        ```
    """
    try:
        logger.info(f"创建档案请求: user={request.user_id}, name='{request.archive_name}', items={len(request.items)}")

        # 准备条目数据
        items_data = [
            {
                "news_result_id": item.news_result_id,
                "edited_title": item.edited_title,
                "edited_summary": item.edited_summary,
                "user_notes": item.user_notes,
                "user_rating": item.user_rating
            }
            for item in request.items
        ]

        # 调用服务层创建档案
        result = await mongo_archive_service.create_archive(
            user_id=request.user_id,
            archive_name=request.archive_name,
            items=items_data,
            description=request.description,
            tags=request.tags,
            search_log_id=request.search_log_id
        )

        logger.info(f"档案创建成功: archive_id={result['archive_id']}")

        # 返回档案信息
        return ArchiveResponse(
            archive_id=result["archive_id"],
            user_id=request.user_id,
            archive_name=result["archive_name"],
            description=request.description,
            tags=request.tags or [],
            search_log_id=request.search_log_id,
            items_count=result["items_count"],
            items=None,  # 创建接口不返回条目详情
            created_at=result["created_at"],
            updated_at=None
        )

    except ValueError as e:
        logger.warning(f"档案创建验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"档案创建失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "创建档案失败，请稍后重试"
            }
        )


@router.get(
    "/archives",
    response_model=ArchiveListResponse,
    summary="查询档案列表",
    description="分页查询用户的档案列表"
)
async def list_archives(
    user_id: int = Query(..., gt=0, description="用户ID"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量")
):
    """
    查询档案列表

    **功能**: ✅ 完整实现

    **功能**:
    - 分页查询用户的档案
    - 返回档案基本信息（不含条目详情）
    - 按创建时间倒序排列

    Args:
        user_id (int): 用户ID
        limit (int): 返回数量限制 (1-100)
        offset (int): 分页偏移量

    Returns:
        ArchiveListResponse: 档案列表

    Raises:
        HTTPException: 500 - 服务错误

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/archives?user_id=1001&limit=10&offset=0"
        ```
    """
    try:
        logger.info(f"查询档案列表: user_id={user_id}, limit={limit}, offset={offset}")

        # 调用服务层查询
        archives = await mongo_archive_service.list_archives(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        # 构建响应
        items = [
            ArchiveResponse(
                archive_id=archive["archive_id"],
                user_id=user_id,
                archive_name=archive["archive_name"],
                description=archive["description"],
                tags=archive["tags"],
                search_log_id=archive["search_log_id"],
                items_count=archive["items_count"],
                items=None,  # 列表接口不返回条目详情
                created_at=archive["created_at"],
                updated_at=archive["updated_at"]
            )
            for archive in archives
        ]

        return ArchiveListResponse(
            total=len(items),
            items=items,
            page=offset // limit + 1 if limit > 0 else 1,
            page_size=limit
        )

    except Exception as e:
        logger.error(f"查询档案列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "查询档案列表失败，请稍后重试"
            }
        )


@router.get(
    "/archives/{archive_id}",
    response_model=ArchiveResponse,
    summary="获取档案详情",
    description="获取档案的完整信息（包含所有条目）"
)
async def get_archive(
    archive_id: str,
    user_id: Optional[int] = Query(None, description="用户ID（可选，用于权限验证）")
):
    """
    获取档案详情

    **功能**: ✅ 完整实现

    **功能**:
    - 获取档案完整信息
    - 包含所有档案条目
    - 支持权限验证

    Args:
        archive_id (int): 档案ID
        user_id (Optional[int]): 用户ID（可选，用于权限验证）

    Returns:
        ArchiveResponse: 档案详情（包含条目）

    Raises:
        HTTPException:
            - 404: 档案不存在或无权访问
            - 500: 服务错误

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/archives/1?user_id=1001"
        ```
    """
    try:
        logger.info(f"获取档案详情: archive_id={archive_id}, user_id={user_id}")

        # 调用服务层获取档案
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=user_id
        )

        if not archive:
            logger.warning(f"档案不存在或无权访问: archive_id={archive_id}, user_id={user_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "档案不存在",
                    "message": f"未找到档案或您无权访问: archive_id={archive_id}"
                }
            )

        # 构建条目响应
        items = [
            ArchiveItemResponse(
                id=item["id"],
                news_result_id=item["news_result_id"],
                title=item["title"],
                content=item["content"],
                edited_title=item["edited_title"],
                edited_summary=item["edited_summary"],
                user_notes=item["user_notes"],
                user_rating=item["user_rating"],
                category=item["category"],
                source=item["source"],
                created_at=item["created_at"]
            )
            for item in archive["items"]
        ]

        return ArchiveResponse(
            archive_id=archive["archive_id"],
            user_id=archive["user_id"],
            archive_name=archive["archive_name"],
            description=archive["description"],
            tags=archive["tags"],
            search_log_id=archive["search_log_id"],
            items_count=archive["items_count"],
            items=items,
            created_at=archive["created_at"],
            updated_at=archive["updated_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取档案详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取档案详情失败，请稍后重试"
            }
        )


@router.put(
    "/archives/{archive_id}",
    response_model=ArchiveResponse,
    summary="更新档案",
    description="更新档案的基本信息（名称、描述、标签）"
)
async def update_archive(
    archive_id: str,
    user_id: int = Query(..., gt=0, description="用户ID（用于权限验证）"),
    request: UpdateArchiveRequest = None
):
    """
    更新档案

    **功能**: ✅ 完整实现

    **功能**:
    - 更新档案名称、描述、标签
    - 权限验证（仅允许档案所有者修改）
    - 自动更新 updated_at 字段

    Args:
        archive_id (int): 档案ID
        user_id (int): 用户ID（权限验证）
        request (UpdateArchiveRequest): 更新内容

    Returns:
        ArchiveResponse: 更新后的档案信息

    Raises:
        HTTPException:
            - 400: 输入验证失败
            - 404: 档案不存在或无权修改
            - 500: 服务错误

    Example:
        ```bash
        curl -X PUT "http://localhost:8000/api/v1/nl-search/archives/1?user_id=1001" \\
          -H "Content-Type: application/json" \\
          -d '{
            "archive_name": "新档案名称",
            "description": "更新的描述",
            "tags": ["更新", "标签"]
          }'
        ```
    """
    try:
        logger.info(f"更新档案: archive_id={archive_id}, user_id={user_id}")

        # 调用服务层更新
        success = await mongo_archive_service.update_archive(
            archive_id=archive_id,
            user_id=user_id,
            archive_name=request.archive_name if request else None,
            description=request.description if request else None,
            tags=request.tags if request else None
        )

        if not success:
            logger.warning(f"档案更新失败: archive_id={archive_id}, user_id={user_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "档案不存在",
                    "message": f"未找到档案或您无权修改: archive_id={archive_id}"
                }
            )

        # 获取更新后的档案
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=user_id
        )

        return ArchiveResponse(
            archive_id=archive["archive_id"],
            user_id=archive["user_id"],
            archive_name=archive["archive_name"],
            description=archive["description"],
            tags=archive["tags"],
            search_log_id=archive["search_log_id"],
            items_count=archive["items_count"],
            items=None,  # 更新接口不返回条目详情
            created_at=archive["created_at"],
            updated_at=archive["updated_at"]
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"档案更新验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"档案更新失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "更新档案失败，请稍后重试"
            }
        )


@router.delete(
    "/archives/{archive_id}",
    summary="删除档案",
    description="删除档案及其所有条目"
)
async def delete_archive(
    archive_id: str,
    user_id: int = Query(..., gt=0, description="用户ID（用于权限验证）")
):
    """
    删除档案

    **功能**: ✅ 完整实现

    **功能**:
    - 删除档案及所有条目（级联删除）
    - 权限验证（仅允许档案所有者删除）

    Args:
        archive_id (int): 档案ID
        user_id (int): 用户ID（权限验证）

    Returns:
        dict: 删除结果

    Raises:
        HTTPException:
            - 404: 档案不存在或无权删除
            - 500: 服务错误

    Example:
        ```bash
        curl -X DELETE "http://localhost:8000/api/v1/nl-search/archives/1?user_id=1001"
        ```
    """
    try:
        logger.info(f"删除档案: archive_id={archive_id}, user_id={user_id}")

        # 调用服务层删除
        success = await mongo_archive_service.delete_archive(
            archive_id=archive_id,
            user_id=user_id
        )

        if not success:
            logger.warning(f"档案删除失败: archive_id={archive_id}, user_id={user_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "档案不存在",
                    "message": f"未找到档案或您无权删除: archive_id={archive_id}"
                }
            )

        logger.info(f"档案删除成功: archive_id={archive_id}")

        return {
            "success": True,
            "message": "档案删除成功",
            "archive_id": archive_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"档案删除失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "删除档案失败,请稍后重试"
            }
        )
