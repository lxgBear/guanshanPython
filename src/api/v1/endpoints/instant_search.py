"""即时搜索API端点

v1.3.0 功能：
- POST /instant-search-tasks - 创建并执行即时搜索
- GET /instant-search-tasks/{task_id} - 获取任务详情
- GET /instant-search-tasks/{task_id}/results - 获取搜索结果（通过映射表）
- GET /instant-search-tasks - 任务列表
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.instant_search_service import InstantSearchService
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/instant-search-tasks", tags=["即时搜索"])


# ==================== Request Models ====================

class CreateInstantSearchRequest(BaseModel):
    """创建即时搜索请求"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=100)
    query: Optional[str] = Field(None, description="搜索关键词（Search模式）")
    crawl_url: Optional[str] = Field(None, description="爬取URL（Crawl模式，优先于query）")
    search_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="搜索配置（JSON）"
    )
    created_by: str = Field(default="system", description="创建者")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "缅甸新闻搜索",
                "query": "Myanmar economy",
                "search_config": {
                    "limit": 10,
                    "include_domains": ["www.gnlm.com.mm"]
                },
                "created_by": "admin"
            }
        }


# ==================== Response Models ====================

class InstantSearchTaskResponse(BaseModel):
    """即时搜索任务响应"""
    id: str
    name: str
    description: Optional[str]
    query: Optional[str]
    crawl_url: Optional[str]
    target_website: Optional[str]
    search_config: Dict[str, Any]
    search_execution_id: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_results: int
    new_results: int
    shared_results: int
    credits_used: int
    execution_time_ms: int
    error_message: Optional[str]
    search_mode: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "1849365782347890688",
                "name": "缅甸新闻搜索",
                "query": "Myanmar economy",
                "target_website": "www.gnlm.com.mm",
                "search_execution_id": "exec_1849365782347890689",
                "status": "completed",
                "created_by": "admin",
                "total_results": 10,
                "new_results": 7,
                "shared_results": 3,
                "credits_used": 1,
                "execution_time_ms": 2500,
                "search_mode": "search"
            }
        }


class SearchResultWithMappingResponse(BaseModel):
    """带映射信息的搜索结果响应"""
    result: Dict[str, Any] = Field(..., description="搜索结果数据")
    mapping_info: Dict[str, Any] = Field(..., description="映射元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "result": {
                    "id": "1849365782347890690",
                    "title": "Myanmar Economic Report 2024",
                    "url": "https://www.gnlm.com.mm/economy-report",
                    "content": "...",
                    "found_count": 3,
                    "unique_searches": 2
                },
                "mapping_info": {
                    "found_at": "2025-10-15T10:30:00Z",
                    "search_position": 1,
                    "relevance_score": 0.95,
                    "is_first_discovery": False
                }
            }
        }


class PaginatedResultsResponse(BaseModel):
    """分页结果响应"""
    results: List[SearchResultWithMappingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[InstantSearchTaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== API Endpoints ====================

@router.post("", response_model=InstantSearchTaskResponse, status_code=201)
async def create_instant_search(request: CreateInstantSearchRequest):
    """
    创建并执行即时搜索

    v1.3.0 核心流程：
    1. 验证参数（必须提供query或crawl_url）
    2. 创建任务
    3. 执行搜索（Search API 或 Scrape API）
    4. 对每个结果进行去重检查
    5. 创建映射记录
    6. 返回任务统计（总结果、新结果、共享结果）

    参数：
    - name: 任务名称
    - query: 搜索关键词（可选，Search模式）
    - crawl_url: 爬取URL（可选，Crawl模式，优先级高于query）
    - search_config: 搜索配置（可选）
    - created_by: 创建者（可选，默认system）

    返回：
    - InstantSearchTask对象（含完整统计信息）

    示例：
    ```json
    {
        "name": "缅甸新闻搜索",
        "query": "Myanmar economy",
        "search_config": {
            "limit": 10,
            "include_domains": ["www.gnlm.com.mm"]
        }
    }
    ```
    """
    # 验证参数
    if not request.query and not request.crawl_url:
        raise HTTPException(
            status_code=400,
            detail="必须提供query（搜索关键词）或crawl_url（爬取URL）参数"
        )

    try:
        service = InstantSearchService()

        # 创建并执行搜索
        task = await service.create_and_execute_search(
            name=request.name,
            query=request.query,
            crawl_url=request.crawl_url,
            search_config=request.search_config,
            created_by=request.created_by
        )

        # 转换为响应模型
        return InstantSearchTaskResponse(**task.to_dict())

    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"创建即时搜索失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/{task_id}", response_model=InstantSearchTaskResponse)
async def get_instant_search_task(task_id: str):
    """
    获取即时搜索任务详情

    参数：
    - task_id: 任务ID

    返回：
    - InstantSearchTask对象
    """
    try:
        service = InstantSearchService()
        task = await service.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        return InstantSearchTaskResponse(**task.to_dict())

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/{task_id}/results", response_model=PaginatedResultsResponse)
async def get_instant_search_results(
    task_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取即时搜索结果（通过映射表JOIN）

    v1.3.0 核心查询：
    - 通过search_execution_id查询映射表
    - JOIN instant_search_results表
    - 按search_position排序
    - 返回结果 + 映射元数据

    参数：
    - task_id: 任务ID
    - page: 页码（默认1）
    - page_size: 每页数量（默认20，最大100）

    返回：
    - results: 搜索结果列表（含映射元数据）
    - total: 总结果数
    - pagination: 分页信息
    """
    try:
        service = InstantSearchService()

        # 获取结果
        results, total = await service.get_task_results(
            task_id=task_id,
            page=page,
            page_size=page_size
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        # 转换为响应模型
        result_responses = [
            SearchResultWithMappingResponse(**item)
            for item in results
        ]

        return PaginatedResultsResponse(
            results=result_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"获取搜索结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("", response_model=TaskListResponse)
async def list_instant_search_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态过滤（pending, running, completed, failed）")
):
    """
    获取即时搜索任务列表

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
        service = InstantSearchService()

        # 获取任务列表
        tasks, total = await service.list_tasks(
            page=page,
            page_size=page_size,
            status=status
        )

        # 计算总页数
        total_pages = (total + page_size - 1) // page_size

        # 转换为响应模型
        task_responses = [
            InstantSearchTaskResponse(**task.to_dict())
            for task in tasks
        ]

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
