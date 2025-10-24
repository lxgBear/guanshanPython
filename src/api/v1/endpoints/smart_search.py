"""智能搜索API端点

v2.0.0 功能：
- POST /smart-search-tasks - 创建任务并调用LLM分解查询
- POST /smart-search-tasks/{task_id}/confirm - 确认子查询并执行搜索
- GET /smart-search-tasks/{task_id}/results - 获取聚合搜索结果
- GET /smart-search-tasks/{task_id} - 获取任务详情
- GET /smart-search-tasks - 任务列表
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.smart_search_service import SmartSearchService
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/smart-search-tasks", tags=["🧠 智能搜索（LLM分解）"])


# ==================== Request Models ====================

class CreateSmartSearchRequest(BaseModel):
    """创建智能搜索请求"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=100)
    query: str = Field(..., description="原始复杂查询", min_length=1)
    search_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="搜索配置（JSON）"
    )
    created_by: str = Field(default="system", description="创建者")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "缅甸经济分析",
                "query": "缅甸2024年经济发展情况",
                "search_config": {
                    "limit": 5,
                    "language": "zh",
                    "include_domains": ["www.gnlm.com.mm"]
                },
                "created_by": "admin"
            }
        }


class ConfirmQueriesRequest(BaseModel):
    """确认子查询请求"""
    confirmed_queries: List[str] = Field(
        ...,
        description="用户确认的子查询列表（可以编辑LLM建议）",
        min_items=1
    )

    class Config:
        json_schema_extra = {
            "example": {
                "confirmed_queries": [
                    "缅甸2024年GDP增长数据",
                    "缅甸2024年外国投资情况",
                    "缅甸2024年贸易数据"
                ]
            }
        }


# ==================== Response Models ====================

class DecomposedQueryResponse(BaseModel):
    """分解的子查询响应"""
    query: str = Field(..., description="子查询文本")
    reasoning: str = Field(..., description="为什么需要这个子查询")
    focus: str = Field(..., description="关注的信息维度")


class SmartSearchTaskResponse(BaseModel):
    """智能搜索任务响应"""
    id: str
    name: str
    description: str
    original_query: str
    search_config: Dict[str, Any]

    # 分解阶段
    decomposed_queries: List[DecomposedQueryResponse]
    llm_model: str
    llm_reasoning: str
    decomposition_tokens_used: int

    # 确认阶段
    user_confirmed_queries: List[str]
    user_modifications: Dict[str, List[str]]

    # 执行阶段
    sub_search_task_ids: List[str]
    sub_search_results: Dict[str, Any]

    # 聚合统计
    aggregated_stats: Dict[str, Any]

    # 状态管理
    status: str
    created_by: str
    created_at: str
    updated_at: str
    confirmed_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]

    execution_time_ms: int
    error_message: Optional[str]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "smart_1849365782347890688",
                "name": "缅甸经济分析",
                "original_query": "缅甸2024年经济发展情况",
                "decomposed_queries": [
                    {
                        "query": "缅甸2024年GDP增长数据",
                        "reasoning": "了解经济总体增长趋势",
                        "focus": "宏观经济指标"
                    }
                ],
                "llm_model": "gpt-4",
                "llm_reasoning": "分解策略：按经济维度拆分",
                "decomposition_tokens_used": 800,
                "status": "awaiting_confirmation",
                "created_by": "admin",
                "aggregated_stats": {},
                "execution_time_ms": 0
            }
        }


class AggregatedResultItemResponse(BaseModel):
    """聚合结果项响应"""
    result: Dict[str, Any] = Field(..., description="搜索结果数据")
    composite_score: float = Field(..., description="综合评分")
    sources: List[Dict[str, Any]] = Field(..., description="来源信息")
    multi_source_bonus: bool = Field(..., description="是否有多源奖励")
    source_count: int = Field(..., description="出现在多少个查询中")


class AggregatedResultsResponse(BaseModel):
    """聚合结果响应"""
    statistics: Dict[str, Any] = Field(..., description="统计信息")
    results: List[AggregatedResultItemResponse] = Field(..., description="结果列表")
    pagination: Dict[str, int] = Field(..., description="分页信息")

    class Config:
        json_schema_extra = {
            "example": {
                "statistics": {
                    "total_searches": 3,
                    "successful_searches": 3,
                    "failed_searches": 0,
                    "total_results_raw": 15,
                    "total_results_deduplicated": 12,
                    "duplication_rate": 0.2,
                    "total_credits_used": 3
                },
                "results": [
                    {
                        "result": {
                            "title": "Myanmar GDP Report 2024",
                            "url": "https://example.com/report",
                            "content": "..."
                        },
                        "composite_score": 0.85,
                        "sources": [
                            {
                                "query": "缅甸2024年GDP增长数据",
                                "task_id": "task1",
                                "position": 1,
                                "relevance_score": 0.95
                            }
                        ],
                        "multi_source_bonus": True,
                        "source_count": 2
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total": 12,
                    "total_pages": 1
                }
            }
        }


class ByQueryResultsResponse(BaseModel):
    """按查询分组结果响应"""
    results_by_query: List[Dict[str, Any]] = Field(..., description="按查询分组的结果")

    class Config:
        json_schema_extra = {
            "example": {
                "results_by_query": [
                    {
                        "query": "缅甸2024年GDP增长数据",
                        "task_id": "task1",
                        "status": "completed",
                        "count": 5,
                        "credits_used": 1,
                        "execution_time_ms": 2500,
                        "results": [
                            {
                                "title": "GDP Report 2024",
                                "url": "https://example.com",
                                "search_position": 1,
                                "relevance_score": 0.95
                            }
                        ]
                    }
                ]
            }
        }


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[SmartSearchTaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== API Endpoints ====================

@router.post("", response_model=SmartSearchTaskResponse, status_code=201)
async def create_smart_search(request: CreateSmartSearchRequest):
    """
    创建智能搜索任务并调用LLM分解查询

    v2.0.0 阶段1流程：
    1. 创建SmartSearchTask
    2. 检查缓存（降低成本）
    3. 调用LLM分解查询（GPT-4）
    4. 保存分解结果
    5. 返回待确认的任务

    参数：
    - name: 任务名称
    - query: 原始复杂查询
    - search_config: 搜索配置（可选）
    - created_by: 创建者（可选，默认system）

    返回：
    - SmartSearchTask对象（status=awaiting_confirmation）
    - 包含LLM分解的子查询和推理说明

    示例：
    ```json
    {
        "name": "缅甸经济分析",
        "query": "缅甸2024年经济发展情况",
        "search_config": {
            "limit": 5,
            "language": "zh"
        }
    }
    ```
    """
    try:
        service = SmartSearchService()

        # 创建并分解查询
        task = await service.create_and_decompose(
            name=request.name,
            query=request.query,
            search_config=request.search_config,
            created_by=request.created_by
        )

        # 转换为响应模型
        task_dict = task.to_dict()

        # 转换decomposed_queries为响应模型
        task_dict["decomposed_queries"] = [
            DecomposedQueryResponse(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in task_dict.get("decomposed_queries", [])
        ]

        return SmartSearchTaskResponse(**task_dict)

    except Exception as e:
        logger.error(f"创建智能搜索失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/{task_id}/confirm", response_model=SmartSearchTaskResponse)
async def confirm_and_execute(task_id: str, request: ConfirmQueriesRequest):
    """
    确认子查询并执行搜索

    v2.0.0 阶段2流程：
    1. 验证任务状态（必须是awaiting_confirmation）
    2. 更新用户确认的查询
    3. 并发执行子搜索（最大5个并发）
    4. 聚合结果
    5. 返回完成的任务

    参数：
    - task_id: 智能搜索任务ID
    - confirmed_queries: 用户确认的子查询列表（可以修改LLM建议）

    返回：
    - SmartSearchTask对象（status=completed/partial_success/failed）
    - 包含聚合统计信息

    示例：
    ```json
    {
        "confirmed_queries": [
            "缅甸2024年GDP增长数据",
            "缅甸2024年外国投资情况"
        ]
    }
    ```
    """
    try:
        service = SmartSearchService()

        # 确认并执行搜索
        task = await service.confirm_and_execute(
            task_id=task_id,
            confirmed_queries=request.confirmed_queries
        )

        # 转换为响应模型
        task_dict = task.to_dict()

        # 转换decomposed_queries为响应模型
        task_dict["decomposed_queries"] = [
            DecomposedQueryResponse(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in task_dict.get("decomposed_queries", [])
        ]

        return SmartSearchTaskResponse(**task_dict)

    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"确认并执行搜索失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/{task_id}/results", response_model=AggregatedResultsResponse | ByQueryResultsResponse)
async def get_aggregated_results(
    task_id: str,
    view_mode: str = Query("combined", description="视图模式（combined=综合去重, by_query=按查询分组）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取聚合搜索结果

    v2.0.0 阶段3功能：
    - combined视图：跨查询去重，综合评分排序
    - by_query视图：按查询分组，保留原始排序

    参数：
    - task_id: 智能搜索任务ID
    - view_mode: 视图模式（combined | by_query）
    - page: 页码（默认1）
    - page_size: 每页数量（默认20，最大100）

    返回：
    - combined模式：去重后的结果 + 综合评分 + 来源信息
    - by_query模式：按查询分组的结果 + 各查询统计

    综合评分公式：
    composite_score = 0.4 * multi_source_score + 0.4 * relevance_score + 0.2 * position_score
    """
    try:
        service = SmartSearchService()

        # 获取聚合结果
        results = await service.get_aggregated_results(
            task_id=task_id,
            view_mode=view_mode,
            page=page,
            page_size=page_size
        )

        if view_mode == "combined":
            # 转换为AggregatedResultsResponse
            return AggregatedResultsResponse(
                statistics=results["statistics"],
                results=[
                    AggregatedResultItemResponse(**item)
                    for item in results["results"]
                ],
                pagination=results["pagination"]
            )
        else:
            # by_query模式
            return ByQueryResultsResponse(
                results_by_query=results["results_by_query"]
            )

    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"获取聚合结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/{task_id}", response_model=SmartSearchTaskResponse)
async def get_smart_search_task(task_id: str):
    """
    获取智能搜索任务详情

    参数：
    - task_id: 任务ID

    返回：
    - SmartSearchTask对象（含完整分解、执行、聚合信息）
    """
    try:
        service = SmartSearchService()
        task = await service.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        # 转换为响应模型
        task_dict = task.to_dict()

        # 转换decomposed_queries为响应模型
        task_dict["decomposed_queries"] = [
            DecomposedQueryResponse(
                query=q["query"],
                reasoning=q["reasoning"],
                focus=q["focus"]
            )
            for q in task_dict.get("decomposed_queries", [])
        ]

        return SmartSearchTaskResponse(**task_dict)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("", response_model=TaskListResponse)
async def list_smart_search_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤（awaiting_confirmation, searching, completed, partial_success, failed, expired）")
):
    """
    获取智能搜索任务列表

    参数：
    - page: 页码（默认1）
    - page_size: 每页数量（默认20，最大100）
    - status: 状态过滤（可选）

    返回：
    - tasks: 任务列表
    - total: 总任务数
    - pagination: 分页信息
    """
    try:
        service = SmartSearchService()

        # 获取任务列表
        tasks, total = await service.list_tasks(
            page=page,
            page_size=page_size,
            status=status
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        # 转换为响应模型
        task_responses = []
        for task in tasks:
            task_dict = task.to_dict()

            # 转换decomposed_queries为响应模型
            task_dict["decomposed_queries"] = [
                DecomposedQueryResponse(
                    query=q["query"],
                    reasoning=q["reasoning"],
                    focus=q["focus"]
                )
                for q in task_dict.get("decomposed_queries", [])
            ]

            task_responses.append(SmartSearchTaskResponse(**task_dict))

        return TaskListResponse(
            tasks=task_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
