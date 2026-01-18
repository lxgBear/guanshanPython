"""
LangGraph 搜索结果管理 API

提供 LangGraph 搜索结果的查询、分页、批量转移、修改等功能

版本: v4.7.0
日期: 2026-01-16

API 端点汇总:
-----------
查询类:
  GET  /langgraph/tasks             - 获取有 LangGraph 结果的任务列表（聚合查询）
  GET  /langgraph/results           - 分页查询搜索结果（支持模糊搜索 title、层级筛选、分数筛选、状态筛选）
  GET  /langgraph/transfer-status/{task_id} - 获取任务的转移状态统计

修改类 (v4.7.0 新增):
  PATCH /langgraph/results/{result_id}  - 修改单条结果（标题、摘要、内容、状态、分类）
  PATCH /langgraph/results/batch        - 批量修改结果状态

转移类:
  POST /langgraph/results/{result_id}/transfer - 单条结果入库 (v4.7.0 新增)
  POST /langgraph/transfer-to-news  - 根据 ID 列表批量转移结果到 news_results
  POST /langgraph/transfer-by-task  - 根据任务 ID 批量转移结果到 news_results

权限说明:
--------
- langgraph:read / search:basic: 查询类接口
- langgraph:write: 修改类接口 (v4.7.0 新增)
- langgraph:transfer: 转移类接口

v4.5.4 更新:
- 新增 GET /results 端点，支持分页查询、模糊搜索(title)、层级筛选、分数筛选
- 首页返回统计信息（各层级数量、平均分数、来源分布）
- 支持 include_content 参数控制是否返回完整 markdown/html 内容

v4.5.5 更新:
- 新增 translator_status 筛选：按翻译状态筛选 (pending/processing/completed/failed)
- 新增 only_translated 筛选：仅返回 translator_status 有值的记录
- 新增 exclude_transferred 筛选：排除已转移到 news_results 的记录
- 响应模型新增 translator_status, translator_dict, transferred_to_news, transferred_at 字段

v4.5.6 更新:
- 新增 GET /tasks 端点，获取有 LangGraph 结果的任务列表（前端库外信息 Tab 使用）
- 支持按关键词搜索任务、分页查询
- 返回每个任务的结果数量、层级分布、平均分数等统计信息

v4.7.0 更新:
- 新增 PATCH /results/{result_id} 端点，支持修改单条结果的标题、摘要、内容、状态、分类
- 新增 PATCH /results/batch 端点，支持批量修改结果处理状态
- 新增 langgraph_status 字段：处理状态 (pending/transferred/discarded)
- GET /results 新增 langgraph_status 筛选参数，支持多选
- 响应模型新增 langgraph_status 字段
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from src.api.dependencies.auth import require_permissions
from src.services.langgraph_search.transfer_service import langgraph_transfer_service

router = APIRouter(
    prefix="/langgraph"
)


# ========== 请求模型 ==========

class TransferByIdsRequest(BaseModel):
    """根据 ID 列表转移请求"""
    result_ids: List[str] = Field(..., description="LangGraph 结果 ID 列表")
    user_id: str = Field(..., description="用户 ID")
    task_id: Optional[str] = Field(None, description="目标任务 ID（可选）")


class TransferByTaskRequest(BaseModel):
    """根据任务 ID 转移请求"""
    task_id: str = Field(..., description="LangGraph 任务 ID")
    user_id: str = Field(..., description="用户 ID")
    layer: Optional[int] = Field(None, ge=0, le=4, description="筛选特定层级（可选）")
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="最低分数筛选（可选）")
    limit: Optional[int] = Field(None, ge=1, le=500, description="最大转移数量（可选）")


# ========== v4.7.0: 修改请求模型 ==========

class UpdateResultRequest(BaseModel):
    """单条结果修改请求

    v4.7.0 新增：支持修改单条 LangGraph 搜索结果的部分字段
    """
    title: Optional[str] = Field(None, description="修改标题")
    snippet: Optional[str] = Field(None, description="修改摘要")
    markdown_content: Optional[str] = Field(None, description="修改 Markdown 内容")
    langgraph_status: Optional[str] = Field(
        None,
        description="处理状态: pending(未处理) / transferred(已入库) / discarded(已废弃)"
    )
    category: Optional[Dict[str, Any]] = Field(None, description="分类信息")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "修改后的标题",
                "langgraph_status": "discarded"
            }
        }


class BatchUpdateStatusRequest(BaseModel):
    """批量状态修改请求

    v4.7.0 新增：支持批量修改多条结果的处理状态
    """
    result_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="结果 ID 列表（1-100 条）"
    )
    langgraph_status: str = Field(
        ...,
        description="目标状态: pending(未处理) / transferred(已入库) / discarded(已废弃)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "result_ids": ["id1", "id2", "id3"],
                "langgraph_status": "transferred"
            }
        }


# ========== 响应模型 ==========

class TransferResponse(BaseModel):
    """转移响应"""
    success: bool = Field(..., description="是否成功")
    transferred: int = Field(..., description="成功转移数量")
    failed: int = Field(..., description="失败数量")
    total: int = Field(..., description="总数量")
    processed_ids: List[str] = Field(default_factory=list, description="转移后的 news_results ID 列表")
    failed_ids: List[str] = Field(default_factory=list, description="失败的 LangGraph 结果 ID 列表")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误详情")
    message: Optional[str] = Field(None, description="额外消息")


# ========== v4.7.0: 修改响应模型 ==========

class UpdateResultResponse(BaseModel):
    """单条结果修改响应

    v4.7.0 新增
    """
    success: bool = Field(..., description="是否成功")
    result_id: str = Field(..., description="结果 ID")
    updated_fields: List[str] = Field(default_factory=list, description="已更新的字段列表")
    message: Optional[str] = Field(None, description="额外消息")


class BatchUpdateStatusResponse(BaseModel):
    """批量状态修改响应

    v4.7.0 新增
    """
    success: bool = Field(..., description="是否成功（至少有一条更新成功）")
    updated: int = Field(..., description="成功更新数量")
    failed: int = Field(..., description="失败数量")
    total: int = Field(..., description="总请求数量")
    updated_ids: List[str] = Field(default_factory=list, description="成功更新的 ID 列表")
    failed_ids: List[str] = Field(default_factory=list, description="失败的 ID 列表")


# ========== v4.5.4: 查询响应模型 ==========

class LangGraphResultItem(BaseModel):
    """LangGraph 搜索结果项"""
    id: str = Field(..., description="结果 ID")
    task_id: str = Field(..., description="任务 ID")
    title: str = Field(..., description="标题")
    url: str = Field(..., description="URL")
    snippet: Optional[str] = Field(None, description="摘要")
    source: Optional[str] = Field(None, description="来源")
    language: Optional[str] = Field(None, description="语言")
    # LangGraph 特有字段
    layer: int = Field(0, description="搜索层级 (0-4)")
    layer_name: str = Field("", description="层级名称")
    source_tier: int = Field(1, description="来源可信度等级 (1-6)")
    # 评分
    relevance_score: float = Field(0.0, description="相关性分数")
    credibility_score: float = Field(0.0, description="可信度分数")
    final_score: float = Field(0.0, description="综合分数")
    # 内容
    has_markdown_content: bool = Field(False, description="是否有 Markdown 内容")
    has_html_content: bool = Field(False, description="是否有 HTML 内容")
    markdown_content: Optional[str] = Field(None, description="Markdown 内容")
    html_content: Optional[str] = Field(None, description="HTML 内容")
    # 时间
    created_at: Optional[datetime] = Field(None, description="创建时间")
    published_date: Optional[datetime] = Field(None, description="发布时间")
    # v4.5.5: AI 翻译状态
    translator_status: Optional[str] = Field(None, description="AI 翻译状态 (pending/processing/completed/failed)")
    translator_dict: Optional[Dict[str, Any]] = Field(None, description="AI 翻译总结内容")
    # v4.5.5: 数据转移状态
    transferred_to_news: bool = Field(False, description="是否已转移到 news_results")
    transferred_at: Optional[datetime] = Field(None, description="转移时间")
    # v4.7.0: 结果处理状态
    langgraph_status: str = Field("pending", description="处理状态: pending(未处理)/transferred(已入库)/discarded(已废弃)")

    class Config:
        from_attributes = True


class PaginationInfo(BaseModel):
    """分页信息"""
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total: int = Field(..., description="总数量")
    total_pages: int = Field(..., description="总页数")


class LangGraphResultsResponse(BaseModel):
    """LangGraph 搜索结果查询响应"""
    success: bool = Field(True, description="是否成功")
    data: List[LangGraphResultItem] = Field(default_factory=list, description="结果列表")
    pagination: PaginationInfo = Field(..., description="分页信息")
    statistics: Optional[Dict[str, Any]] = Field(None, description="统计信息")


# ========== v4.5.6: 任务列表响应模型 ==========

class LangGraphTaskSummary(BaseModel):
    """LangGraph 任务摘要"""
    task_id: str = Field(..., description="任务 ID")
    query: Optional[str] = Field(None, description="搜索关键词（从最新结果推断）")
    result_count: int = Field(0, description="结果数量")
    created_at: Optional[datetime] = Field(None, description="最早结果创建时间")
    updated_at: Optional[datetime] = Field(None, description="最新结果创建时间")
    statistics: Optional[Dict[str, Any]] = Field(None, description="统计信息")

    class Config:
        from_attributes = True


class LangGraphTasksResponse(BaseModel):
    """LangGraph 任务列表响应"""
    success: bool = Field(True, description="是否成功")
    data: List[LangGraphTaskSummary] = Field(default_factory=list, description="任务列表")
    pagination: PaginationInfo = Field(..., description="分页信息")


# ========== API 端点 ==========

# ========== v4.5.6: 任务列表端点 ==========

@router.get("/tasks", response_model=LangGraphTasksResponse)
async def get_langgraph_tasks(
    keyword: Optional[str] = Query(None, description="搜索关键词（搜索 task_id 或标题）"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量（最大 100）"),
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:read", "search:basic"]))
):
    """获取有 LangGraph 结果的任务列表

    v4.5.6 新增：用于前端"库外信息" Tab 展示任务选择器

    通过聚合查询返回所有有 LangGraph 搜索结果的任务，
    包含每个任务的结果数量、层级分布、平均分数等统计信息。

    权限: langgraph:read 或 search:basic

    Args:
        keyword: 搜索关键词（搜索 task_id 或结果标题）
        page: 页码
        page_size: 每页数量

    Returns:
        LangGraphTasksResponse: 任务列表
    """
    try:
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )

        repo = MongoLangGraphResultRepository()

        # 聚合查询
        tasks_data, total = await repo.get_distinct_tasks(
            keyword=keyword,
            page=page,
            page_size=page_size
        )

        # 转换为响应模型
        data = [
            LangGraphTaskSummary(
                task_id=t["task_id"],
                query=t.get("query"),
                result_count=t.get("result_count", 0),
                created_at=t.get("created_at"),
                updated_at=t.get("updated_at"),
                statistics=t.get("statistics"),
            )
            for t in tasks_data
        ]

        # 分页信息
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )

        return LangGraphTasksResponse(
            success=True,
            data=data,
            pagination=pagination
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.post("/results/{result_id}/transfer")
async def transfer_single_langgraph_result(
    result_id: str,
    current_user = Depends(require_permissions(["langgraph:transfer"]))
):
    """转移单条 LangGraph 结果到 news_results 表

    v4.7.0 新增: 便利端点，支持前端单条入库操作

    权限: langgraph:transfer

    Args:
        result_id: 结果 ID

    Returns:
        { success: bool, message: str }
    """
    try:
        result = await langgraph_transfer_service.transfer_by_ids(
            result_ids=[result_id],
            user_id=current_user.id,
            task_id=None
        )

        if result.get("success_count", 0) > 0:
            return {"success": True, "message": "入库成功"}
        else:
            return {"success": False, "message": result.get("message", "入库失败")}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")


@router.post("/transfer-to-news", response_model=TransferResponse)
async def transfer_langgraph_results_to_news(
    request: TransferByIdsRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:transfer"]))
):
    """批量转移 LangGraph 结果到 news_results 表

    将用户选择的 LangGraph 搜索结果转移到 news_results 表，
    供 AI 微服务进行翻译、分类等处理。

    权限: langgraph:transfer

    Args:
        request: 转移请求

    Returns:
        TransferResponse: 转移结果统计
    """
    try:
        result = await langgraph_transfer_service.transfer_by_ids(
            result_ids=request.result_ids,
            user_id=request.user_id,
            task_id=request.task_id
        )
        return TransferResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转移失败: {str(e)}")


@router.post("/transfer-by-task", response_model=TransferResponse)
async def transfer_langgraph_results_by_task(
    request: TransferByTaskRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:transfer"]))
):
    """根据任务 ID 批量转移 LangGraph 结果

    将指定任务的所有或筛选后的 LangGraph 搜索结果转移到 news_results 表。

    权限: langgraph:transfer

    Args:
        request: 转移请求

    Returns:
        TransferResponse: 转移结果统计
    """
    try:
        result = await langgraph_transfer_service.transfer_by_task(
            task_id=request.task_id,
            user_id=request.user_id,
            layer=request.layer,
            min_score=request.min_score,
            limit=request.limit
        )
        return TransferResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转移失败: {str(e)}")


@router.get("/transfer-status/{task_id}")
async def get_transfer_status(
    task_id: str,
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:read"]))
):
    """获取任务的转移状态

    查询指定任务的 LangGraph 结果转移情况。

    权限: langgraph:read

    Args:
        task_id: 任务 ID

    Returns:
        转移状态统计
    """
    try:
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )
        from src.infrastructure.persistence.repositories.mongo.processed_result_repository import (
            MongoProcessedResultRepository
        )

        langgraph_repo = MongoLangGraphResultRepository()
        processed_repo = MongoProcessedResultRepository()

        # 统计 LangGraph 结果数量
        lg_results = await langgraph_repo.find_by_task_id(task_id)
        lg_count = len(lg_results)

        # 统计已转移到 news_results 的数量
        # 通过 raw_result_id 关联查询
        db = await processed_repo._get_collection()
        transferred_count = await db.count_documents({
            "task_id": task_id,
            "metadata.langgraph.data_source_type": "langgraph"
        })

        return {
            "task_id": task_id,
            "langgraph_results_count": lg_count,
            "transferred_count": transferred_count,
            "pending_count": lg_count - transferred_count,
            "transfer_rate": round(transferred_count / lg_count * 100, 2) if lg_count > 0 else 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== v4.5.4: 查询端点 ==========

@router.get("/results", response_model=LangGraphResultsResponse)
async def get_langgraph_results(
    task_id: Optional[str] = Query(None, description="任务 ID（与 conversation_id 二选一）"),
    conversation_id: Optional[str] = Query(None, description="对话会话 ID（与 task_id 二选一，v4.6.0 新增）"),
    keyword: Optional[str] = Query(None, description="模糊搜索关键词（搜索 title）"),
    layer: Optional[int] = Query(None, ge=0, le=4, description="筛选层级 (0-4)"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="最低分数筛选"),
    translator_status: Optional[str] = Query(None, description="翻译状态筛选 (pending/processing/completed/failed)"),
    only_translated: bool = Query(False, description="仅返回 translator_status 有值的记录"),
    exclude_transferred: bool = Query(False, description="排除已转移到 news_results 的记录"),
    langgraph_status: Optional[str] = Query(None, description="处理状态筛选，多选用逗号分隔 (pending,transferred,discarded)"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量（最大 100）"),
    sort_by: str = Query("final_score", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    include_content: bool = Query(True, description="是否包含完整内容（markdown_content, html_content）"),
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:read", "search:basic"]))
):
    """分页查询 LangGraph 搜索结果

    v4.5.4 新增
    v4.5.5 更新: 新增 translator_status, only_translated, exclude_transferred 筛选参数
    v4.6.0 更新: 新增 conversation_id 参数，支持按对话会话查询
    v4.7.0 更新: 新增 langgraph_status 参数，支持按处理状态筛选

    支持按 task_id 或 conversation_id 查询，可选模糊搜索、层级筛选、分数筛选、翻译状态筛选、处理状态筛选。

    权限: langgraph:read 或 search:basic

    Args:
        task_id: 任务 ID（与 conversation_id 二选一）
        conversation_id: 对话会话 ID（与 task_id 二选一，用于前端查询历史会话的搜索结果）
        keyword: 模糊搜索关键词（搜索 title）
        layer: 筛选层级 (0-4)
        min_score: 最低分数筛选
        translator_status: 翻译状态筛选 (pending/processing/completed/failed)
        only_translated: 仅返回 translator_status 有值的记录
        exclude_transferred: 排除已转移到 news_results 的记录
        langgraph_status: 处理状态筛选，多选用逗号分隔 (pending/transferred/discarded)
        page: 页码
        page_size: 每页数量
        sort_by: 排序字段 (final_score, created_at, relevance_score, credibility_score, layer)
        sort_order: 排序方向 (asc/desc)
        include_content: 是否包含完整内容

    Returns:
        LangGraphResultsResponse: 分页查询结果

    Raises:
        HTTPException 400: 如果 task_id 和 conversation_id 都未提供
    """
    # v4.6.0: 验证至少有一个查询条件
    if not task_id and not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="task_id 和 conversation_id 必须至少提供一个"
        )

    try:
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )

        repo = MongoLangGraphResultRepository()

        # v4.7.0: 解析 langgraph_status 参数（支持逗号分隔的多选）
        langgraph_status_list = None
        if langgraph_status:
            langgraph_status_list = [s.strip() for s in langgraph_status.split(",") if s.strip()]

        # 分页查询（v4.6.0: 新增 conversation_id 参数, v4.7.0: 新增 langgraph_status 参数）
        results, total = await repo.find_with_pagination(
            task_id=task_id,
            conversation_id=conversation_id,
            keyword=keyword,
            layer=layer,
            min_score=min_score,
            translator_status=translator_status,
            only_translated=only_translated,
            exclude_transferred=exclude_transferred,
            langgraph_status=langgraph_status_list,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # 转换为响应模型（v4.5.5: 新增翻译状态和转移状态字段）
        data = []
        for r in results:
            item = LangGraphResultItem(
                id=str(r.id),
                task_id=str(r.task_id),
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                source=r.source,
                language=r.language,
                layer=r.layer,
                layer_name=r.layer_name,
                source_tier=r.source_tier,
                relevance_score=r.relevance_score,
                credibility_score=r.credibility_score,
                final_score=r.final_score,
                has_markdown_content=bool(r.markdown_content),
                has_html_content=bool(r.html_content),
                markdown_content=r.markdown_content if include_content else None,
                html_content=r.html_content if include_content else None,
                created_at=r.created_at,
                published_date=r.published_date,
                # v4.5.5: AI 翻译状态
                translator_status=r.translator_status,
                translator_dict=r.translator_dict,
                # v4.5.5: 数据转移状态
                transferred_to_news=r.transferred_to_news,
                transferred_at=r.transferred_at,
                # v4.7.0: 结果处理状态
                langgraph_status=r.langgraph_status,
            )
            data.append(item)

        # 分页信息
        total_pages = (total + page_size - 1) // page_size
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )

        # 统计信息（仅首页时返回）
        statistics = None
        if page == 1:
            statistics = await repo.get_task_statistics(task_id)

        return LangGraphResultsResponse(
            success=True,
            data=data,
            pagination=pagination,
            statistics=statistics
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== v4.7.0: 修改端点 ==========

@router.patch("/results/{result_id}", response_model=UpdateResultResponse)
async def update_langgraph_result(
    result_id: str,
    request: UpdateResultRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:write"]))
):
    """修改单条 LangGraph 搜索结果

    v4.7.0 新增：支持修改结果的标题、摘要、内容、处理状态、分类等字段

    权限: langgraph:write

    Args:
        result_id: 结果 ID
        request: 修改请求，包含要更新的字段

    Returns:
        UpdateResultResponse: 更新结果

    Raises:
        HTTPException 400: 如果请求体为空
        HTTPException 404: 如果结果不存在
        HTTPException 422: 如果状态值无效
    """
    # 构建更新字典（只包含非空字段）
    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.snippet is not None:
        updates["snippet"] = request.snippet
    if request.markdown_content is not None:
        updates["markdown_content"] = request.markdown_content
    if request.langgraph_status is not None:
        updates["langgraph_status"] = request.langgraph_status
    if request.category is not None:
        updates["category"] = request.category

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="请求体不能为空，至少需要提供一个要修改的字段"
        )

    try:
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )

        repo = MongoLangGraphResultRepository()

        # 先检查结果是否存在
        existing = await repo.get_by_id(result_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"未找到 ID 为 {result_id} 的结果"
            )

        # 执行部分更新
        success = await repo.update_partial(result_id, updates)

        return UpdateResultResponse(
            success=success,
            result_id=result_id,
            updated_fields=list(updates.keys()),
            message="更新成功" if success else "数据未变化"
        )

    except ValueError as e:
        # 参数验证错误（如无效的状态值）
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.patch("/results/batch", response_model=BatchUpdateStatusResponse)
async def batch_update_langgraph_results_status(
    request: BatchUpdateStatusRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["langgraph:write"]))
):
    """批量修改 LangGraph 搜索结果的处理状态

    v4.7.0 新增：支持批量修改多条结果的处理状态

    权限: langgraph:write

    Args:
        request: 批量修改请求，包含结果 ID 列表和目标状态

    Returns:
        BatchUpdateStatusResponse: 批量更新结果统计

    Raises:
        HTTPException 400: 如果 result_ids 为空
        HTTPException 422: 如果状态值无效或 ID 数量超过限制
    """
    try:
        from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
            MongoLangGraphResultRepository
        )

        repo = MongoLangGraphResultRepository()

        # 执行批量更新
        result = await repo.batch_update_status(
            result_ids=request.result_ids,
            langgraph_status=request.langgraph_status
        )

        return BatchUpdateStatusResponse(
            success=result["success"],
            updated=result["updated"],
            failed=result["failed"],
            total=result["total"],
            updated_ids=result["updated_ids"],
            failed_ids=result["failed_ids"]
        )

    except ValueError as e:
        # 参数验证错误
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")
