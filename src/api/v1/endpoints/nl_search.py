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
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import re

from src.api.dependencies.auth import require_permissions, get_current_active_user
from src.core.domain.entities.auth import User

# 导入服务层
from src.services.nl_search.nl_search_service import nl_search_service
from src.services.nl_search.mongo_archive_service import mongo_archive_service  # 使用 MongoDB 版本
from src.services.nl_search.config import nl_search_config
from src.services.nl_search.multilang_search_service import get_multilang_search_service

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


# ==================== RAG内容访问数据模型 ====================

class RAGContentResponse(BaseModel):
    """RAG内容详情响应"""
    mongo_id: str = Field(..., description="MongoDB news_results表的_id")
    url: str = Field(..., description="原始网页URL")
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容")
    title: str = Field(..., description="新闻标题")
    source: str = Field(..., description="来源网站")

    class Config:
        json_schema_extra = {
            "example": {
                "mongo_id": "249832360786370562",
                "url": "https://chineseyouthstandfortibet.substack.com/p/abc",
                "markdown_content": "# 标题\n\n正文内容...",
                "title": "本会编辑留学生张雅笛回国探亲遭文字狱",
                "source": "chineseyouthstandfortibet.substack.com"
            }
        }


# ==================== 档案管理数据模型 ====================

class ArchiveItemRequest(BaseModel):
    """档案条目请求

    v2.5.0: 支持双数据源 ID 格式
    - ObjectId (24位十六进制): file_uploads 集合 (用户上传文档)
    - 雪花ID (17-20位数字): search_results 集合 (新闻搜索结果)
    """
    news_result_id: str = Field(
        ...,
        description="结果ID（ObjectId 或 雪花ID）",
        min_length=17,
        max_length=24
    )
    edited_title: Optional[str] = Field(None, description="编辑后的标题", max_length=500)
    edited_summary: Optional[str] = Field(None, description="编辑后的摘要", max_length=5000)
    user_notes: Optional[str] = Field(None, description="用户备注", max_length=2000)
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分 1-5")

    @classmethod
    def validate_news_result_id(cls, v: str) -> str:
        """验证 news_result_id 格式

        支持两种格式:
        1. ObjectId: 24位十六进制 (file_uploads)
        2. 雪花ID: 17-20位纯数字 (search_results)
        """
        import re
        # ObjectId 格式: 24位十六进制
        if re.match(r'^[a-fA-F0-9]{24}$', v):
            return v
        # 雪花ID 格式: 17-20位纯数字
        if v.isdigit() and 17 <= len(v) <= 20:
            return v
        raise ValueError(
            f"无效的 ID 格式: '{v}'. "
            "支持 ObjectId (24位十六进制) 或 雪花ID (17-20位数字)"
        )

    def __init__(self, **data):
        super().__init__(**data)
        # 在实例化时验证 ID 格式
        self.validate_news_result_id(self.news_result_id)


class CreateArchiveRequest(BaseModel):
    """创建档案请求

    安全性增强 (v2.4.0):
    - items 最大限制 100 条，防止资源耗尽
    - 自动去重 news_result_id，防止重复条目
    - archive_name 和 description 自动清理危险字符

    v2.6.0: 新增 search_task_id 支持定时任务关联
    v2.7.0: 移除 user_id 参数，强制从 Token 获取用户身份（安全增强）
    """
    # v2.7.0: user_id 已移除，从 Token 认证中获取
    archive_name: str = Field(..., description="档案名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="档案描述", max_length=2000)
    tags: Optional[List[str]] = Field(None, description="档案标签列表", max_length=20)
    search_log_id: Optional[str] = Field(None, description="关联的搜索记录ID（雪花算法ID字符串，来自自然语言搜索）")
    search_task_id: Optional[str] = Field(None, description="关联的定时任务ID（雪花算法ID字符串，来自定时搜索任务）")
    items: List[ArchiveItemRequest] = Field(
        ...,
        description="档案条目列表（最多100条，自动去重）",
        min_length=1,
        max_length=100
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1001,
                "archive_name": "2024年AI技术突破汇总",
                "description": "整理2024年重要的AI技术突破新闻",
                "tags": ["AI", "技术", "2024"],
                "search_log_id": "248728141926559744",
                "search_task_id": "248728141926559745",
                "items": [
                    {
                        "news_result_id": "507f1f77bcf86cd799439011",
                        "edited_title": "用户上传文档标题",
                        "edited_summary": "来自用户上传的文档...",
                        "user_rating": 5
                    },
                    {
                        "news_result_id": "248728141926559744",
                        "edited_title": "新闻搜索结果标题",
                        "edited_summary": "来自新闻搜索的结果...",
                        "user_rating": 4
                    }
                ]
            }
        }


class UpdateArchiveRequest(BaseModel):
    """更新档案请求

    v2.5.3: 新增 user_summary 字段，用于存储用户上传的内容总结
    v2.5.9: 新增 generated_report 字段，用于存储AI生成的摘要报告
    """
    archive_name: Optional[str] = Field(None, description="新的档案名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="新的描述", max_length=2000)
    tags: Optional[List[str]] = Field(None, description="新的标签列表")
    user_summary: Optional[str] = Field(None, description="用户上传的内容总结（用于总结items列表内容）", max_length=50000)
    generated_report: Optional[str] = Field(None, description="AI生成的摘要报告", max_length=100000)


class ArchiveItemResponse(BaseModel):
    """档案条目响应

    v2.5.1: category 字段支持两种格式:
    - 字符串: file_uploads 数据源的分类 (如 "document", "other")
    - 字典: news_results 数据源的分类信息 (如 {"type": "news", "topic": "科技"})
    """
    id: int = Field(..., description="条目ID")
    news_result_id: str = Field(..., description="新闻结果ID")
    title: str = Field(..., description="显示标题（优先显示编辑标题）")
    content: Optional[str] = Field(None, description="显示内容（优先显示编辑摘要）")
    edited_title: Optional[str] = Field(None, description="用户编辑的标题")
    edited_summary: Optional[str] = Field(None, description="用户编辑的摘要")
    user_notes: Optional[str] = Field(None, description="用户备注")
    user_rating: Optional[int] = Field(None, description="用户评分")
    category: Optional[Any] = Field(None, description="分类信息（字符串或字典格式）")
    source: Optional[str] = Field(None, description="新闻来源")
    url: Optional[str] = Field(None, description="原文链接URL")
    created_at: Optional[str] = Field(None, description="添加时间")


class ArchiveResponse(BaseModel):
    """档案响应

    v2.5.2: 新增 generated_report 字段，返回 AI 生成的档案摘要报告
    v2.5.3: 新增 user_summary 字段，返回用户上传的内容总结
    v2.6.0: 新增 search_task_id 字段，支持定时任务关联
    v2.7.0: 新增审核相关字段 (status, reviewer_id, reviewer_name, reviewed_at, rejection_feedback, submission_count)
    """
    archive_id: str = Field(..., description="档案ID（MongoDB ObjectId）")
    user_id: int = Field(..., description="用户ID")
    archive_name: str = Field(..., description="档案名称")
    description: Optional[str] = Field(None, description="档案描述")
    tags: List[str] = Field(..., description="档案标签")
    search_log_id: Optional[str] = Field(None, description="关联的搜索记录ID（雪花算法ID字符串，来自自然语言搜索）")
    search_task_id: Optional[str] = Field(None, description="关联的定时任务ID（雪花算法ID字符串，来自定时搜索任务）")
    items_count: int = Field(..., description="档案条目数量")
    items: Optional[List[ArchiveItemResponse]] = Field(None, description="档案条目列表（仅详情接口返回）")
    generated_report: Optional[str] = Field(None, description="AI生成的档案摘要报告（Markdown格式）")
    user_summary: Optional[str] = Field(None, description="用户上传的内容总结（用于总结items列表内容）")
    # v2.7.0: 审核相关字段
    status: str = Field("pending", description="审核状态: pending(待审核)/approved(已审核)/rejected(已驳回)")
    reviewer_id: Optional[int] = Field(None, description="审核人ID")
    reviewer_name: Optional[str] = Field(None, description="审核人姓名")
    reviewed_at: Optional[str] = Field(None, description="审核时间")
    rejection_feedback: Optional[str] = Field(None, description="驳回原因/改进建议")
    submission_count: int = Field(1, description="提交次数")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class ArchiveListResponse(BaseModel):
    """档案列表响应"""
    total: int = Field(..., description="总记录数")
    items: List[ArchiveResponse] = Field(..., description="档案列表")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


# ==================== v2.7.0: 审核流程数据模型 ====================

class ArchiveReviewRequest(BaseModel):
    """档案审核请求

    v2.7.0: 新增

    用于审核员审核档案（通过或驳回）。
    """
    action: str = Field(
        ...,
        description="审核操作: approve(通过) 或 reject(驳回)",
        pattern="^(approve|reject)$"
    )
    feedback: Optional[str] = Field(
        None,
        description="驳回原因/改进建议（驳回时必填）",
        max_length=2000
    )

    class Config:
        json_schema_extra = {
            "example": {
                "action": "reject",
                "feedback": "内容质量不符合标准，请补充更多来源"
            }
        }


class ArchiveReviewResponse(BaseModel):
    """档案审核响应

    v2.7.0: 新增
    """
    archive_id: str = Field(..., description="档案ID")
    action: str = Field(..., description="审核操作")
    new_status: str = Field(..., description="审核后的状态")
    reviewer_id: int = Field(..., description="审核人ID")
    reviewer_name: str = Field(..., description="审核人姓名")
    reviewed_at: str = Field(..., description="审核时间")
    feedback: Optional[str] = Field(None, description="驳回原因")
    message: str = Field(..., description="响应消息")


class ArchiveResubmitResponse(BaseModel):
    """档案重新提交响应

    v2.7.0: 新增
    """
    archive_id: str = Field(..., description="档案ID")
    new_status: str = Field(..., description="重新提交后的状态")
    submission_count: int = Field(..., description="提交次数")
    message: str = Field(..., description="响应消息")


class ArchiveStatsResponse(BaseModel):
    """档案统计响应

    v2.7.0: 新增
    """
    pending: int = Field(..., description="待审核档案数量")
    approved: int = Field(..., description="已审核档案数量")
    rejected: int = Field(..., description="已驳回档案数量")
    total: int = Field(..., description="档案总数")


class ArchiveResponseWithStatus(ArchiveResponse):
    """带审核状态的档案响应

    v2.7.0: 扩展 ArchiveResponse，添加审核相关字段
    """
    status: str = Field("pending", description="审核状态: pending/approved/rejected")
    reviewer_id: Optional[int] = Field(None, description="审核人ID")
    reviewer_name: Optional[str] = Field(None, description="审核人姓名")
    reviewed_at: Optional[str] = Field(None, description="审核时间")
    rejection_feedback: Optional[str] = Field(None, description="驳回原因")
    submission_count: int = Field(1, description="提交次数")


# ==================== API端点 ====================
# 🔧 v2.3.1: 路由顺序修复 - 具体路径必须在动态参数路径之前
# 正确顺序: /status → /archives → /rag-content/{id} → /{log_id} → /{log_id}/xxx

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



# ==================== RAG内容访问API ====================

@router.get(
    "/rag-content/{mongo_id}",
    response_model=RAGContentResponse,
    summary="获取RAG结果的内容和URL",
    description="根据RAG返回的mongo_id获取news_results表中的markdown_content和url字段"
)
async def get_rag_content(mongo_id: str):
    """
    获取RAG结果的内容和URL

    **功能**: 🆕 新增

    **用途**:
    - 前端点击RAG结果时，获取完整的markdown内容用于展示
    - 获取原始URL用于跳转到来源网页

    **性能优化**:
    - 仅返回需要的字段（markdown_content, url, title, source）
    - 不返回完整的news_results文档
    - MongoDB字段投影优化：50KB → 5KB (90%减少)

    Args:
        mongo_id (str): news_results表的_id (RAG返回的mongo_id)

    Returns:
        RAGContentResponse: 包含markdown_content和url的响应

    Raises:
        HTTPException:
            - 404: mongo_id对应的记录不存在
            - 500: 数据库查询失败

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/249832360786370562"
        ```
    """
    try:
        logger.info(f"获取RAG内容: mongo_id={mongo_id}")

        from src.infrastructure.database.connection import get_mongodb_database

        db = await get_mongodb_database()

        # 性能优化: 只查询需要的字段 (field projection)
        result = await db["news_results"].find_one(
            {"_id": mongo_id},
            {
                "_id": 1,
                "url": 1,
                "markdown_content": 1,
                "title": 1,
                "source": 1
            }
        )

        if not result:
            logger.warning(f"RAG内容不存在: mongo_id={mongo_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "内容不存在",
                    "message": f"未找到对应的news_results记录: mongo_id={mongo_id}",
                    "hint": "请检查mongo_id是否正确，或该记录可能已被删除"
                }
            )

        # 构建响应
        response = RAGContentResponse(
            mongo_id=str(result["_id"]),
            url=result.get("url", ""),
            markdown_content=result.get("markdown_content"),
            title=result.get("title", ""),
            source=result.get("source", "")
        )

        logger.info(
            f"RAG内容获取成功: mongo_id={mongo_id}, "
            f"has_markdown={bool(response.markdown_content)}, "
            f"url_length={len(response.url)}"
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取RAG内容失败: mongo_id={mongo_id}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取内容失败，请稍后重试",
                "mongo_id": mongo_id
            }
        )

# ==================== 档案管理API ====================

@router.post(
    "/user-archives",
    response_model=ArchiveResponse,
    summary="创建档案",
    description="从搜索结果创建用户档案（需要认证）"
)
async def create_archive(
    request: CreateArchiveRequest,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """
    创建档案

    **功能**: ✅ 完整实现 (v2.4.0 增强)

    **流程**:
    1. 验证输入数据
    2. 去重处理（基于 news_result_id）
    3. 为每个条目创建快照（从MongoDB news_results）
    4. 批量创建档案条目
    5. 返回档案信息（包含去重统计）

    **v2.4.0 安全增强**:
    - 自动去重：相同 news_result_id 只保留第一条
    - 输入清理：移除潜在危险字符
    - 条目限制：最多 100 条

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
        curl -X POST "http://localhost:8000/api/v1/nl-search/user-archives" \\
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
        # v2.4.0: 去重处理 - 基于 news_result_id 去重，保留第一条
        seen_ids = set()
        unique_items = []
        duplicate_count = 0

        for item in request.items:
            if item.news_result_id not in seen_ids:
                seen_ids.add(item.news_result_id)
                unique_items.append(item)
            else:
                duplicate_count += 1

        if duplicate_count > 0:
            logger.warning(
                f"创建档案时检测到重复条目: user={request.user_id}, "
                f"原始数量={len(request.items)}, 去重后={len(unique_items)}, "
                f"重复数量={duplicate_count}"
            )

        # v2.4.0: 输入清理 - 移除潜在危险字符
        def sanitize_text(text: str) -> str:
            if not text:
                return text
            # 移除 HTML 标签和脚本注入风险
            return re.sub(r'<[^>]+>', '', text).strip()

        archive_name = sanitize_text(request.archive_name)
        description = sanitize_text(request.description) if request.description else None

        logger.info(
            f"创建档案请求: user={request.user_id}, name='{archive_name}', "
            f"items={len(unique_items)} (原始={len(request.items)}, 去重={duplicate_count})"
        )

        # 准备条目数据（使用去重后的列表）
        items_data = [
            {
                "news_result_id": item.news_result_id,
                "edited_title": sanitize_text(item.edited_title) if item.edited_title else None,
                "edited_summary": sanitize_text(item.edited_summary) if item.edited_summary else None,
                "user_notes": sanitize_text(item.user_notes) if item.user_notes else None,
                "user_rating": item.user_rating
            }
            for item in unique_items
        ]

        # 调用服务层创建档案（使用清理后的值）
        # v2.6.0: 新增 search_task_id 支持定时任务关联
        # v2.7.0: 从 Token 获取用户身份，不再从请求参数获取
        result = await mongo_archive_service.create_archive(
            user_id=current_user.id,  # v2.7.0: 从 Token 获取
            archive_name=archive_name,  # v2.4.0: 使用清理后的名称
            items=items_data,
            description=description,  # v2.4.0: 使用清理后的描述
            tags=request.tags,
            search_log_id=request.search_log_id,
            search_task_id=request.search_task_id  # v2.6.0: 定时任务关联
        )

        logger.info(f"档案创建成功: archive_id={result['archive_id']}")

        # 返回档案信息 (v2.7.0: 添加审核状态字段，从 Token 获取用户身份)
        return ArchiveResponse(
            archive_id=result["archive_id"],
            user_id=current_user.id,  # v2.7.0: 从 Token 获取
            archive_name=result["archive_name"],
            description=request.description,
            tags=request.tags or [],
            search_log_id=request.search_log_id,
            search_task_id=request.search_task_id,  # v2.6.0: 定时任务关联
            items_count=result["items_count"],
            items=None,  # 创建接口不返回条目详情
            created_at=result["created_at"],
            updated_at=None,
            # v2.7.0: 审核状态字段（新创建的档案默认为待审核）
            status="pending",
            reviewer_id=None,
            reviewer_name=None,
            reviewed_at=None,
            rejection_feedback=None,
            submission_count=1
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
    "/user-archives",
    response_model=ArchiveListResponse,
    summary="查询档案列表",
    description="分页查询用户的档案列表（v2.7.0: 支持按状态筛选，强制用户隔离）"
)
async def list_archives(
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected)$", description="审核状态筛选（v2.7.0新增）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """
    查询档案列表

    **功能**: ✅ 完整实现 (v2.7.0: 支持按状态筛选，强制用户隔离)

    **功能**:
    - 分页查询档案列表
    - v2.7.0: 强制用户隔离，普通用户只能查看自己的档案，admin 可查看所有
    - v2.7.0: 支持按审核状态筛选 (pending/approved/rejected)
    - 返回档案基本信息（不含条目详情）
    - 按创建时间倒序排列

    Args:
        status (Optional[str]): 审核状态筛选（v2.7.0新增）
        limit (int): 返回数量限制 (1-100)
        offset (int): 分页偏移量

    Returns:
        ArchiveListResponse: 档案列表

    Raises:
        HTTPException: 500 - 服务错误

    Example:
        ```bash
        # v2.7.0: 查询档案（需要 Token 认证，自动根据用户角色过滤）
        curl -X GET "http://localhost:8000/api/v1/nl-search/user-archives?limit=10&offset=0" \
            -H "Authorization: Bearer <token>"

        # v2.7.0: 查询待审核的档案
        curl -X GET "http://localhost:8000/api/v1/nl-search/user-archives?status=pending&limit=10&offset=0" \
            -H "Authorization: Bearer <token>"
        ```
    """
    try:
        # v2.7.0: 用户隔离逻辑
        # admin 角色可查看所有档案，普通用户只能查看自己的
        is_admin = "admin" in current_user.roles
        effective_user_id = None if is_admin else current_user.id

        logger.info(f"查询档案列表: user_id={current_user.id}, is_admin={is_admin}, effective_filter={effective_user_id}, status={status}, limit={limit}, offset={offset}")

        # v2.7.0: 使用支持状态筛选的服务方法
        archives = await mongo_archive_service.list_archives_by_status(
            user_id=effective_user_id,  # None 表示查询所有，否则只查询该用户的
            status=status,
            limit=limit,
            offset=offset
        )

        # 构建响应 (v2.5.2: 添加 generated_report, v2.5.3: 添加 user_summary, v2.6.0: 添加 search_task_id)
        # v2.7.0: 添加审核状态字段
        items = [
            ArchiveResponse(
                archive_id=archive["archive_id"],
                user_id=archive["user_id"],  # 使用档案中的user_id，而不是查询参数
                archive_name=archive["archive_name"],
                description=archive["description"],
                tags=archive["tags"],
                search_log_id=archive["search_log_id"],
                search_task_id=archive.get("search_task_id"),  # v2.6.0: 定时任务关联
                items_count=archive["items_count"],
                items=None,  # 列表接口不返回条目详情
                generated_report=archive.get("generated_report"),  # v2.5.2: AI生成的摘要报告
                user_summary=archive.get("user_summary"),  # v2.5.3: 用户上传的内容总结
                created_at=archive["created_at"],
                updated_at=archive["updated_at"],
                # v2.7.0: 审核状态字段
                status=archive.get("status", "pending"),
                reviewer_id=archive.get("reviewer_id"),
                reviewer_name=archive.get("reviewer_name"),
                reviewed_at=archive.get("reviewed_at"),
                rejection_feedback=archive.get("rejection_feedback"),
                submission_count=archive.get("submission_count", 1)
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
    "/user-archives/{archive_id}",
    response_model=ArchiveResponse,
    summary="获取档案详情",
    description="获取档案的完整信息（包含所有条目，v2.7.0: 强制用户隔离）"
)
async def get_archive(
    archive_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """
    获取档案详情

    **功能**: ✅ 完整实现 (v2.7.0: 强制用户隔离)

    **功能**:
    - 获取档案完整信息
    - 包含所有档案条目
    - v2.7.0: 强制 Token 认证，自动验证访问权限
    - v2.7.0: admin 可查看所有档案，普通用户只能查看自己的

    Args:
        archive_id (str): 档案ID

    Returns:
        ArchiveResponse: 档案详情（包含条目）

    Raises:
        HTTPException:
            - 401: 未认证
            - 403: 无权访问（非自己的档案且非 admin）
            - 404: 档案不存在
            - 500: 服务错误

    Example:
        ```bash
        # v2.7.0: 需要 Token 认证
        curl -X GET "http://localhost:8000/api/v1/nl-search/user-archives/abc123" \
            -H "Authorization: Bearer <token>"
        ```
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        logger.info(f"获取档案详情: archive_id={archive_id}, user_id={current_user.id}, is_admin={is_admin}")

        # 先获取档案（不带 user_id 过滤，用于检查归属）
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=None  # 先不过滤，获取后再检查权限
        )

        if not archive:
            logger.warning(f"档案不存在: archive_id={archive_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "档案不存在",
                    "message": f"未找到档案: archive_id={archive_id}"
                }
            )

        # v2.7.0: 权限检查 - 非 admin 只能访问自己的档案
        archive_owner_id = archive.get("user_id")
        if not is_admin and str(archive_owner_id) != str(current_user.id):
            logger.warning(f"无权访问档案: archive_id={archive_id}, owner={archive_owner_id}, requester={current_user.id}")
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AUTH_005",
                    "message": "权限不足，您只能查看自己创建的档案"
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
                url=item.get("url"),  # ✅ 添加URL字段
                created_at=item["created_at"]
            )
            for item in archive["items"]
        ]

        # v2.5.2: 添加 generated_report 字段
        # v2.5.3: 添加 user_summary 字段
        # v2.6.0: 添加 search_task_id 字段
        # v2.7.0: 添加审核状态字段
        return ArchiveResponse(
            archive_id=archive["archive_id"],
            user_id=archive["user_id"],
            archive_name=archive["archive_name"],
            description=archive["description"],
            tags=archive["tags"],
            search_log_id=archive["search_log_id"],
            search_task_id=archive.get("search_task_id"),  # v2.6.0: 定时任务关联
            items_count=archive["items_count"],
            items=items,
            generated_report=archive.get("generated_report"),  # v2.5.2: AI生成的摘要报告
            user_summary=archive.get("user_summary"),  # v2.5.3: 用户上传的内容总结
            created_at=archive["created_at"],
            updated_at=archive["updated_at"],
            # v2.7.0: 审核状态字段
            status=archive.get("status", "pending"),
            reviewer_id=archive.get("reviewer_id"),
            reviewer_name=archive.get("reviewer_name"),
            reviewed_at=archive.get("reviewed_at"),
            rejection_feedback=archive.get("rejection_feedback"),
            submission_count=archive.get("submission_count", 1)
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
    "/user-archives/{archive_id}",
    response_model=ArchiveResponse,
    summary="更新档案",
    description="更新档案的基本信息（v2.7.0: 强制用户隔离，仅所有者或 admin 可更新）"
)
async def update_archive(
    archive_id: str,
    request: UpdateArchiveRequest = None,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """
    更新档案

    **功能**: ✅ 完整实现 (v2.7.0: 强制用户隔离)

    **功能**:
    - 更新档案名称、描述、标签
    - 自动更新 updated_at 字段
    - v2.7.0: 强制 Token 认证，仅所有者或 admin 可更新

    Args:
        archive_id (str): 档案ID
        request (UpdateArchiveRequest): 更新内容

    Returns:
        ArchiveResponse: 更新后的档案信息

    Raises:
        HTTPException:
            - 401: 未认证
            - 403: 无权更新（非所有者且非 admin）
            - 404: 档案不存在
            - 500: 服务错误

    Example:
        ```bash
        # v2.7.0: 需要 Token 认证
        curl -X PUT "http://localhost:8000/api/v1/nl-search/user-archives/{archive_id}" \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer <token>" \
          -d '{
            "archive_name": "新档案名称",
            "description": "更新的描述",
            "tags": ["更新", "标签"]
          }'
        ```
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        logger.info(f"更新档案: archive_id={archive_id}, user_id={current_user.id}, is_admin={is_admin}")

        # 先获取档案检查权限
        existing_archive = await mongo_archive_service.get_archive(archive_id=archive_id, user_id=None)
        if not existing_archive:
            raise HTTPException(
                status_code=404,
                detail={"error": "档案不存在", "message": f"未找到档案: archive_id={archive_id}"}
            )

        # v2.7.0: 权限检查 - 非 admin 只能更新自己的档案
        archive_owner_id = existing_archive.get("user_id")
        if not is_admin and str(archive_owner_id) != str(current_user.id):
            logger.warning(f"无权更新档案: archive_id={archive_id}, owner={archive_owner_id}, requester={current_user.id}")
            raise HTTPException(
                status_code=403,
                detail={"code": "AUTH_005", "message": "权限不足，您只能更新自己创建的档案"}
            )

        # 调用服务层更新 (v2.5.9: 支持 generated_report 字段)
        success = await mongo_archive_service.update_archive(
            archive_id=archive_id,
            archive_name=request.archive_name if request else None,
            description=request.description if request else None,
            tags=request.tags if request else None,
            user_summary=request.user_summary if request else None,
            generated_report=request.generated_report if request else None
        )

        if not success:
            logger.warning(f"档案不存在: archive_id={archive_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "档案不存在",
                    "message": "未找到指定的档案"
                }
            )

        # 获取更新后的档案
        archive = await mongo_archive_service.get_archive(
            archive_id=archive_id,
            user_id=None
        )

        # v2.6.0: 添加 search_task_id 字段
        return ArchiveResponse(
            archive_id=archive["archive_id"],
            user_id=archive["user_id"],
            archive_name=archive["archive_name"],
            description=archive["description"],
            tags=archive["tags"],
            search_log_id=archive["search_log_id"],
            search_task_id=archive.get("search_task_id"),  # v2.6.0: 定时任务关联
            items_count=archive["items_count"],
            items=None,  # 更新接口不返回条目详情
            generated_report=archive.get("generated_report"),  # v2.5.2
            user_summary=archive.get("user_summary"),  # v2.5.3
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
    "/user-archives/{archive_id}",
    summary="删除档案",
    description="删除档案及其所有条目（v2.7.0: 强制用户隔离，仅所有者或 admin 可删除）"
)
async def delete_archive(
    archive_id: str,
    current_user: User = Depends(get_current_active_user)  # v2.7.0: 强制 Token 认证
):
    """
    删除档案

    **功能**: ✅ 完整实现 (v2.7.0: 强制用户隔离)

    **功能**:
    - 删除档案及所有条目（级联删除）
    - v2.7.0: 强制 Token 认证，仅所有者或 admin 可删除

    Args:
        archive_id (str): 档案ID (ObjectId字符串)

    Returns:
        dict: 删除结果

    Raises:
        HTTPException:
            - 401: 未认证
            - 403: 无权删除（非所有者且非 admin）
            - 404: 档案不存在
            - 500: 服务错误

    Example:
        ```bash
        # v2.7.0: 需要 Token 认证
        curl -X DELETE "http://localhost:8000/api/v1/nl-search/user-archives/692825cfab7ab1dc61932133" \
            -H "Authorization: Bearer <token>"
        ```
    """
    try:
        # v2.7.0: 用户隔离逻辑
        is_admin = "admin" in current_user.roles
        logger.info(f"删除档案: archive_id={archive_id}, user_id={current_user.id}, is_admin={is_admin}")

        # 先获取档案检查权限
        existing_archive = await mongo_archive_service.get_archive(archive_id=archive_id, user_id=None)
        if not existing_archive:
            raise HTTPException(
                status_code=404,
                detail={"error": "档案不存在", "message": f"未找到档案: archive_id={archive_id}"}
            )

        # v2.7.0: 权限检查 - 非 admin 只能删除自己的档案
        archive_owner_id = existing_archive.get("user_id")
        if not is_admin and str(archive_owner_id) != str(current_user.id):
            logger.warning(f"无权删除档案: archive_id={archive_id}, owner={archive_owner_id}, requester={current_user.id}")
            raise HTTPException(
                status_code=403,
                detail={"code": "AUTH_005", "message": "权限不足，您只能删除自己创建的档案"}
            )

        # 调用服务层删除
        success = await mongo_archive_service.delete_archive(
            archive_id=archive_id
        )

        if not success:
            logger.warning(f"档案删除失败: archive_id={archive_id}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "删除失败",
                    "message": "档案删除失败，请稍后重试"
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


# ==================== v2.7.0: 审核流程 API ====================

@router.get(
    "/user-archives/stats",
    response_model=ArchiveStatsResponse,
    summary="获取档案统计信息",
    description="获取各状态的档案数量统计（v2.7.0新增）"
)
async def get_archive_stats(
    user_id: Optional[int] = Query(None, gt=0, description="用户ID（可选，不传则统计所有档案）")
):
    """
    获取档案统计信息

    **功能**: v2.7.0 新增

    获取各审核状态的档案数量统计。

    Args:
        user_id (Optional[int]): 用户ID（可选）

    Returns:
        ArchiveStatsResponse: 各状态的档案数量

    Example:
        ```bash
        # 获取所有档案统计
        curl -X GET "http://localhost:8000/api/v1/nl-search/user-archives/stats"

        # 获取指定用户的档案统计
        curl -X GET "http://localhost:8000/api/v1/nl-search/user-archives/stats?user_id=1001"
        ```
    """
    try:
        logger.info(f"获取档案统计: user_id={user_id}")

        stats = await mongo_archive_service.get_archive_stats(user_id=user_id)

        return ArchiveStatsResponse(
            pending=stats["pending"],
            approved=stats["approved"],
            rejected=stats["rejected"],
            total=stats["total"]
        )

    except Exception as e:
        logger.error(f"获取档案统计失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取档案统计失败，请稍后重试"
            }
        )


@router.post(
    "/user-archives/{archive_id}/review",
    response_model=ArchiveReviewResponse,
    summary="审核档案",
    description="审核员审核档案（通过或驳回）（v2.7.0新增）",
    dependencies=[Depends(require_permissions("archive:review"))]
)
async def review_archive(
    archive_id: str,
    request: ArchiveReviewRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    审核档案

    **功能**: v2.7.0 新增

    审核员可以通过或驳回待审核状态的档案。

    **权限要求**: archive:review

    **状态流转**:
    - pending → approved (审核通过)
    - pending → rejected (审核驳回)

    Args:
        archive_id (str): 档案ID
        request (ArchiveReviewRequest): 审核请求（包含action和feedback）

    Returns:
        ArchiveReviewResponse: 审核结果

    Raises:
        HTTPException:
            - 400: 输入验证失败（如驳回时未提供原因）
            - 403: 权限不足
            - 404: 档案不存在
            - 500: 服务错误

    Example:
        ```bash
        # 审核通过
        curl -X POST "http://localhost:8000/api/v1/nl-search/user-archives/{archive_id}/review" \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{"action": "approve"}'

        # 审核驳回
        curl -X POST "http://localhost:8000/api/v1/nl-search/user-archives/{archive_id}/review" \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{"action": "reject", "feedback": "内容质量不符合标准"}'
        ```
    """
    try:
        logger.info(
            f"审核档案: archive_id={archive_id}, action={request.action}, "
            f"reviewer={current_user.username}"
        )

        # 获取审核人信息
        reviewer_id = current_user.id
        reviewer_name = current_user.full_name or current_user.username

        if request.action == "approve":
            # 审核通过
            success = await mongo_archive_service.approve_archive(
                archive_id=archive_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name
            )
            new_status = "approved"
            message = "档案审核通过"

        else:  # reject
            # 验证驳回原因
            if not request.feedback or not request.feedback.strip():
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "输入验证失败",
                        "message": "驳回档案时必须提供驳回原因"
                    }
                )

            # 审核驳回
            success = await mongo_archive_service.reject_archive(
                archive_id=archive_id,
                reviewer_id=reviewer_id,
                reviewer_name=reviewer_name,
                feedback=request.feedback
            )
            new_status = "rejected"
            message = "档案已驳回"

        if not success:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "审核失败",
                    "message": "档案审核操作失败"
                }
            )

        return ArchiveReviewResponse(
            archive_id=archive_id,
            action=request.action,
            new_status=new_status,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            reviewed_at=datetime.utcnow().isoformat(),
            feedback=request.feedback if request.action == "reject" else None,
            message=message
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"档案审核验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"档案审核失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "档案审核失败，请稍后重试"
            }
        )


@router.post(
    "/user-archives/{archive_id}/resubmit",
    response_model=ArchiveResubmitResponse,
    summary="重新提交档案",
    description="将已驳回的档案重新提交审核（v2.7.0新增）",
    dependencies=[Depends(require_permissions("archive:update"))]
)
async def resubmit_archive(
    archive_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    重新提交档案

    **功能**: v2.7.0 新增

    将已驳回的档案重新提交审核。

    **权限要求**: archive:update

    **状态流转**:
    - rejected → pending (重新提交)

    Args:
        archive_id (str): 档案ID

    Returns:
        ArchiveResubmitResponse: 重新提交结果

    Raises:
        HTTPException:
            - 400: 档案状态不是已驳回
            - 403: 权限不足
            - 404: 档案不存在
            - 500: 服务错误

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search/user-archives/{archive_id}/resubmit" \\
          -H "Authorization: Bearer <token>"
        ```
    """
    try:
        logger.info(
            f"重新提交档案: archive_id={archive_id}, user={current_user.username}"
        )

        # 重新提交
        success = await mongo_archive_service.resubmit_archive(archive_id=archive_id)

        if not success:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "重新提交失败",
                    "message": "档案重新提交操作失败"
                }
            )

        # 获取更新后的档案信息
        archive = await mongo_archive_service.get_archive(archive_id=archive_id)

        return ArchiveResubmitResponse(
            archive_id=archive_id,
            new_status="pending",
            submission_count=archive.get("submission_count", 2) if archive else 2,
            message="档案已重新提交审核"
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"档案重新提交验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "输入验证失败",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"档案重新提交失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "档案重新提交失败，请稍后重试"
            }
        )


# ==================== 多语言搜索 API (Claude + Firecrawl) ====================

class MultilangSearchRequest(BaseModel):
    """多语言搜索请求

    基于 Claude + Firecrawl Search 的多语言 OSINT 搜索
    默认支持中文、英语、日语、韩语四种语言
    """
    query_text: str = Field(
        ...,
        description="用户输入的查询文本",
        min_length=1,
        max_length=1000,
        examples=["从日本2025防卫白书看东亚安全趋势", "AI技术最新突破"]
    )
    languages: Optional[List[str]] = Field(
        default=["zh", "en", "ja", "ko"],
        description="搜索语言列表 (zh=中文, en=英语, ja=日语, ko=韩语)"
    )
    include_summary: bool = Field(
        default=True,
        description="是否生成 Claude 汇总分析"
    )
    results_per_language: int = Field(
        default=5,
        ge=1,
        le=20,
        description="每种语言的搜索结果数"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "从日本2025防卫白书看东亚安全趋势",
                "languages": ["zh", "en", "ja", "ko"],
                "include_summary": True,
                "results_per_language": 5
            }
        }


class MultilangSearchResponse(BaseModel):
    """多语言搜索响应"""
    query: str = Field(..., description="原始查询")
    timestamp: str = Field(..., description="搜索时间戳")
    multilang_queries: Dict[str, str] = Field(..., description="多语言查询映射")
    result_counts: Dict[str, int] = Field(..., description="各语言结果数量")
    results: Dict[str, List[Dict[str, Any]]] = Field(..., description="各语言搜索结果")
    summary: Optional[str] = Field(None, description="Claude 汇总分析 (Markdown格式)")
    execution_time_ms: int = Field(..., description="总耗时(毫秒)")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "从日本2025防卫白书看东亚安全趋势",
                "timestamp": "2025-12-23T18:00:00",
                "multilang_queries": {
                    "zh": "日本2025防卫白书 东亚安全",
                    "en": "Japan Defense White Paper 2025",
                    "ja": "2025年防衛白書",
                    "ko": "일본 2025 방위백서"
                },
                "result_counts": {"zh": 5, "en": 5, "ja": 5, "ko": 5},
                "results": {},
                "summary": "# 综合分析\n\n...",
                "execution_time_ms": 70000
            }
        }


class MultilangServiceStatus(BaseModel):
    """多语言搜索服务状态"""
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="版本号")
    claude_configured: bool = Field(..., description="Claude API 是否配置")
    firecrawl_configured: bool = Field(..., description="Firecrawl API 是否配置")
    supported_languages: List[str] = Field(..., description="支持的语言列表")
    results_per_language: int = Field(..., description="每语言结果数")
    enabled: bool = Field(..., description="功能是否启用")


@router.get(
    "/multilang/status",
    response_model=MultilangServiceStatus,
    summary="多语言搜索服务状态",
    description="检查 Claude + Firecrawl 多语言搜索服务状态"
)
async def get_multilang_status():
    """
    检查多语言搜索服务状态

    **功能**: 检查 Claude API 和 Firecrawl API 配置状态

    Returns:
        MultilangServiceStatus: 服务状态信息
    """
    try:
        service = get_multilang_search_service()
        status = await service.get_service_status()

        return MultilangServiceStatus(
            service=status["service"],
            version=status["version"],
            claude_configured=status["claude_configured"],
            firecrawl_configured=status["firecrawl_configured"],
            supported_languages=status["supported_languages"],
            results_per_language=status["results_per_language"],
            enabled=status["claude_configured"] and status["firecrawl_configured"]
        )

    except Exception as e:
        logger.error(f"获取多语言搜索状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "服务错误", "message": str(e)}
        )


@router.post(
    "/multilang",
    response_model=MultilangSearchResponse,
    summary="多语言 OSINT 搜索",
    description="基于 Claude + Firecrawl 的多语言搜索，默认支持中/英/日/韩四种语言"
)
async def create_multilang_search(request: MultilangSearchRequest):
    """
    多语言 OSINT 搜索

    **功能**: ✅ 完整实现

    **流程**:
    1. Claude 生成多语言搜索查询
    2. Firecrawl 并行搜索多种语言
    3. Claude 汇总分析多语言结果

    **默认语言**: 中文(zh)、英语(en)、日语(ja)、韩语(ko)

    Args:
        request (MultilangSearchRequest): 搜索请求

    Returns:
        MultilangSearchResponse: 多语言搜索结果

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/nl-search/multilang" \\
          -H "Content-Type: application/json" \\
          -d '{
            "query_text": "从日本2025防卫白书看东亚安全趋势",
            "languages": ["zh", "en", "ja", "ko"],
            "include_summary": true,
            "results_per_language": 5
          }'
        ```
    """
    try:
        logger.info(
            f"多语言搜索请求: query='{request.query_text[:50]}...', "
            f"languages={request.languages}, summary={request.include_summary}"
        )

        # 获取服务实例
        service = get_multilang_search_service()

        # 检查服务配置
        status = await service.get_service_status()
        if not status["claude_configured"]:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "服务未配置",
                    "message": "Claude API 未配置，请设置 ANTHROPIC_AUTH_TOKEN 环境变量"
                }
            )

        if not status["firecrawl_configured"]:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "服务未配置",
                    "message": "Firecrawl API 未配置，请设置 FIRECRAWL_API_KEY 环境变量"
                }
            )

        # 执行多语言搜索
        result = await service.search(
            query=request.query_text,
            languages=request.languages,
            include_summary=request.include_summary
        )

        logger.info(
            f"多语言搜索完成: languages={len(result['multilang_queries'])}, "
            f"total_results={sum(result['result_counts'].values())}, "
            f"time={result['execution_time_ms']}ms"
        )

        return MultilangSearchResponse(
            query=result["query"],
            timestamp=result["timestamp"],
            multilang_queries=result["multilang_queries"],
            result_counts=result["result_counts"],
            results=result["results"],
            summary=result.get("summary"),
            execution_time_ms=result["execution_time_ms"]
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"多语言搜索输入验证失败: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "输入验证失败", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"多语言搜索失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "搜索失败", "message": "服务暂时不可用，请稍后重试"}
        )


@router.post(
    "/multilang/analyze",
    summary="分析查询意图",
    description="使用 Claude 分析用户查询意图"
)
async def analyze_query(
    query_text: str = Query(..., min_length=1, max_length=1000, description="查询文本")
):
    """
    分析查询意图

    使用 Claude 解析用户查询的意图、关键词、实体等信息

    Args:
        query_text: 用户查询文本

    Returns:
        查询分析结果
    """
    try:
        service = get_multilang_search_service()
        analysis = await service.analyze_query(query_text)

        return {
            "query": query_text,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"查询分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "分析失败", "message": str(e)}
        )
