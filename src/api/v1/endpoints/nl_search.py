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

    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "最近有哪些关于GPT-5的新闻",
                "user_id": "user_12345"
            }
        }


class NLSearchResponse(BaseModel):
    """自然语言搜索响应（完整版）"""
    log_id: Optional[int] = Field(None, description="搜索记录ID")
    status: str = Field(..., description="搜索状态")
    message: str = Field(..., description="响应消息")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="搜索结果列表")
    analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    refined_query: Optional[str] = Field(None, description="精炼后的查询")
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
                "refined_query": "AI技术突破 2024"
            }
        }


class NLSearchLog(BaseModel):
    """自然语言搜索记录（完整版）"""
    id: int = Field(..., description="记录ID")
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
        logger.info(f"收到自然语言搜索请求: {request.query_text[:50]}...")

        result = await nl_search_service.create_search(
            query_text=request.query_text,
            user_id=request.user_id
        )

        logger.info(f"搜索成功: log_id={result['log_id']}")

        return NLSearchResponse(
            log_id=result["log_id"],
            status="completed",
            message="搜索成功",
            results=result["results"],
            analysis=result["analysis"],
            refined_query=result["refined_query"]
        )

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
async def get_nl_search_log(log_id: int):
    """
    获取自然语言搜索记录

    **功能**: ✅ 完整实现

    **功能**:
    - 根据log_id获取搜索记录
    - 包含LLM分析结果
    - 包含创建时间和状态

    Args:
        log_id (int): 搜索记录ID

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
    summary="用户选择结果 (预留)",
    description="记录用户对搜索结果的选择（功能开发中）",
    status_code=503
)
async def select_search_result(
    log_id: int,
    result_id: int = Query(..., description="选中的结果ID")
):
    """
    记录用户对搜索结果的选择

    **状态**: 🚧 功能开发中

    **用途**:
    - 收集用户反馈
    - 优化LLM理解
    - 个性化推荐

    Args:
        log_id (int): 搜索记录ID
        result_id (int): 用户选择的结果ID

    Raises:
        HTTPException: 503 - 功能未启用
    """
    raise HTTPException(
        status_code=503,
        detail="功能开发中"
    )


@router.get(
    "/{log_id}/results",
    summary="获取搜索结果 (预留)",
    description="获取自然语言搜索的所有结果（功能开发中）",
    status_code=503
)
async def get_search_results(log_id: int):
    """
    获取自然语言搜索的所有结果

    **状态**: 🚧 功能开发中

    **计划功能**:
    - 返回LLM分析的结构化结果
    - 包含搜索来源
    - 包含抓取的内容
    - 支持结果排序和过滤

    Args:
        log_id (int): 搜索记录ID

    Raises:
        HTTPException: 503 - 功能未启用
    """
    raise HTTPException(
        status_code=503,
        detail="功能开发中"
    )
