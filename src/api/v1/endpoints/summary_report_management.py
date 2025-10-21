"""智能总结报告管理 API 端点

模块化组织：
1. 报告管理（CRUD）
2. 任务关联管理
3. 数据检索与搜索
4. 内容编辑与版本管理
5. LLM/AI生成（预留）
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from src.services.summary_report_service import summary_report_service
from src.core.domain.entities.summary_report import (
    SummaryReport,
    SummaryReportTask,
    SummaryReportDataItem,
    SummaryReportVersion
)
from src.utils.cursor_pagination import cursor_paginator

router = APIRouter(prefix="/summary-reports")


# ==========================================
# 请求/响应模型
# ==========================================

# 报告管理相关
class TaskAssociation(BaseModel):
    """任务关联信息"""
    task_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型: scheduled/instant")
    task_name: str = Field(..., description="任务名称")
    priority: int = Field(default=0, description="优先级")


class CreateReportRequest(BaseModel):
    """创建报告请求"""
    title: str = Field(..., description="报告标题")
    description: Optional[str] = Field(None, description="报告描述")
    report_type: str = Field(default="comprehensive", description="报告类型")
    created_by: str = Field(..., description="创建者ID")
    task_associations: List[TaskAssociation] = Field(
        default_factory=list,
        description="创建时直接关联的任务列表（可选）"
    )


class UpdateReportRequest(BaseModel):
    """更新报告请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    report_type: Optional[str] = None


class ReportListResponse(BaseModel):
    """报告列表响应"""
    total: int
    page: int
    limit: int
    reports: List[Dict[str, Any]]


# 任务关联相关
class AddTaskRequest(BaseModel):
    """添加任务到报告"""
    task_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型: scheduled/instant")
    task_name: str = Field(..., description="任务名称")
    added_by: str = Field(..., description="添加者ID")
    priority: int = Field(default=0, description="优先级")


# 数据项相关
class AddDataItemRequest(BaseModel):
    """添加数据项到报告"""
    source_type: str = Field(..., description="来源类型")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容")
    added_by: str = Field(..., description="添加者ID")
    url: Optional[str] = None
    source_id: Optional[str] = None
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    importance: int = Field(default=0)


# 内容编辑相关
class UpdateContentRequest(BaseModel):
    """更新报告内容"""
    content_text: str = Field(..., description="内容文本")
    content_format: str = Field(default="markdown", description="内容格式")
    is_manual: bool = Field(default=True, description="是否手动编辑")
    updated_by: str = Field(..., description="更新者ID")
    change_description: Optional[str] = None


# LLM生成相关（预留）
class GenerateReportRequest(BaseModel):
    """生成报告请求（预留）"""
    generation_mode: str = Field(default="comprehensive", description="生成模式")
    llm_config: Optional[Dict[str, Any]] = None


# ==========================================
# 模块1: 报告管理（CRUD）
# ==========================================

@router.post("/", response_model=SummaryReport, status_code=status.HTTP_201_CREATED)
async def create_report(request: CreateReportRequest):
    """
    创建总结报告（支持批量关联任务）

    创建一个新的智能总结报告，用于整合多个搜索任务的结果

    改进功能：
    - 支持在创建报告时直接关联多个任务，减少API调用次数
    - 任务关联失败不影响报告创建，会在响应中返回失败信息
    """
    try:
        # 创建报告
        report = await summary_report_service.create_report(
            title=request.title,
            description=request.description,
            report_type=request.report_type,
            created_by=request.created_by
        )

        # 如果提供了任务关联列表，批量添加任务
        if request.task_associations:
            failed_tasks = []
            for task_assoc in request.task_associations:
                try:
                    await summary_report_service.add_task_to_report(
                        report_id=report.report_id,
                        task_id=task_assoc.task_id,
                        task_type=task_assoc.task_type,
                        task_name=task_assoc.task_name,
                        added_by=request.created_by,
                        priority=task_assoc.priority
                    )
                except Exception as e:
                    failed_tasks.append({
                        "task_id": task_assoc.task_id,
                        "error": str(e)
                    })

            # 如果有任务添加失败，记录到报告的metadata中
            if failed_tasks:
                await summary_report_service.update_report(
                    report.report_id,
                    {"metadata.failed_task_associations": failed_tasks}
                )

        return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建报告失败: {str(e)}"
        )


@router.get("/")
async def list_reports(
    created_by: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    report_type: Optional[str] = None,
    cursor: Optional[str] = Query(None, description="分页游标"),
    limit: int = Query(20, ge=1, le=100),
    include_total: bool = Query(False, description="是否包含总数（影响性能）")
):
    """
    获取报告列表（游标分页）

    支持分页和筛选，使用游标分页提高大数据集性能

    响应格式:
    {
        "items": [...],  # 报告列表
        "meta": {
            "has_next": bool,         # 是否有下一页
            "next_cursor": str,       # 下一页游标
            "count": int,             # 当前页记录数
            "total_count": int | null # 总记录数（仅 include_total=true）
        }
    }
    """
    try:
        # 构建基础过滤条件
        base_filter = {}
        if created_by:
            base_filter["created_by"] = created_by
        if status_filter:
            base_filter["status"] = status_filter
        if report_type:
            base_filter["report_type"] = report_type

        # 使用游标分页
        result = await cursor_paginator.paginate(
            collection=summary_report_service.db.summary_reports,
            base_filter=base_filter,
            cursor=cursor,
            limit=limit,
            sort_field="created_at",
            direction=-1,  # 最新创建的在前
            include_total=include_total
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的游标: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询报告列表失败: {str(e)}"
        )


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    include_task_results: bool = Query(False, description="是否包含任务结果"),
    task_ids: Optional[str] = Query(None, description="指定任务ID（逗号分隔）"),
    cursor: Optional[str] = Query(None, description="任务结果分页游标"),
    limit: int = Query(50, ge=1, le=200, description="任务结果分页大小")
):
    """
    获取报告详情（支持返回任务结果）

    获取指定报告的详细信息，包括内容、统计等

    改进功能：
    - 支持include_task_results=true时返回关联任务的搜索结果
    - 支持task_ids参数指定要返回结果的任务（逗号分隔）
    - 支持cursor分页，适合大数据量场景
    - 如果不指定task_ids，则返回所有关联任务的结果

    响应格式:
    {
      "report": {...},  # 报告基本信息
      "task_results": {  # 仅当include_task_results=true时返回
        "items": [...],
        "meta": {
          "has_next": bool,
          "next_cursor": str,
          "count": int,
          "task_stats": {...}
        }
      }
    }
    """
    try:
        # 获取报告基本信息
        report = await summary_report_service.get_report(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"报告不存在: {report_id}"
            )

        # 构建响应
        response = {"report": report}

        # 如果需要包含任务结果
        if include_task_results:
            # 解析task_ids参数
            specified_task_ids = None
            if task_ids:
                specified_task_ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]

            # 获取任务结果
            task_results = await summary_report_service.get_task_results_for_report(
                report_id=report_id,
                task_ids=specified_task_ids,
                cursor=cursor,
                limit=limit
            )
            response["task_results"] = task_results

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取报告详情失败: {str(e)}"
        )


@router.put("/{report_id}", response_model=Dict[str, Any])
async def update_report(report_id: str, request: UpdateReportRequest):
    """
    更新报告基础信息

    更新报告的标题、描述等基础字段
    """
    try:
        update_data = request.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有提供更新数据"
            )

        success = await summary_report_service.update_report(report_id, update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"报告不存在: {report_id}"
            )

        return {"message": "更新成功", "report_id": report_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新报告失败: {str(e)}"
        )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str):
    """
    删除报告

    删除报告及其所有关联数据（任务关联、数据项、版本历史）
    """
    try:
        success = await summary_report_service.delete_report(report_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"报告不存在: {report_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除报告失败: {str(e)}"
        )


# ==========================================
# 模块2: 任务关联管理
# ==========================================

@router.post("/{report_id}/tasks", response_model=SummaryReportTask, status_code=status.HTTP_201_CREATED)
async def add_task_to_report(report_id: str, request: AddTaskRequest):
    """
    关联任务到报告

    将搜索任务或即时任务关联到报告，用于后续数据聚合
    """
    try:
        task_association = await summary_report_service.add_task_to_report(
            report_id=report_id,
            task_id=request.task_id,
            task_type=request.task_type,
            task_name=request.task_name,
            added_by=request.added_by,
            priority=request.priority
        )
        return task_association
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加任务失败: {str(e)}"
        )


@router.get("/{report_id}/tasks", response_model=List[SummaryReportTask])
async def get_report_tasks(
    report_id: str,
    is_active: Optional[bool] = None
):
    """
    获取报告的关联任务列表

    查询报告关联的所有任务
    """
    try:
        tasks = await summary_report_service.get_report_tasks(report_id, is_active)
        return tasks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务列表失败: {str(e)}"
        )


@router.delete("/{report_id}/tasks/{task_id}/{task_type}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task_from_report(
    report_id: str,
    task_id: str,
    task_type: str
):
    """
    从报告中移除任务

    解除任务与报告的关联关系
    """
    try:
        success = await summary_report_service.remove_task_from_report(
            report_id, task_id, task_type
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务关联不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除任务失败: {str(e)}"
        )


# ==========================================
# 模块3: 数据检索与搜索
# ==========================================

@router.get("/{report_id}/search")
async def search_report_data(
    report_id: str,
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    模糊搜索报告数据（联表查询）

    在报告关联的所有任务结果中进行全文搜索
    支持跨定时任务和即时任务的联表查询
    """
    try:
        # 使用联表查询搜索
        results = await summary_report_service.search_across_tasks(
            report_id=report_id,
            search_query=q,
            limit=limit
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


@router.get("/{report_id}/data")
async def get_report_data_items(
    report_id: str,
    is_visible: Optional[bool] = None,
    cursor: Optional[str] = Query(None, description="分页游标"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    获取报告的数据项列表（游标分页）

    获取用户手动添加到报告的数据项
    使用游标分页以提高大数据集的查询性能

    响应格式:
    {
        "items": [...],  # 数据项列表
        "meta": {
            "has_next": bool,      # 是否有下一页
            "next_cursor": str,    # 下一页游标
            "count": int           # 当前页记录数
        }
    }
    """
    try:
        # 构建基础过滤条件
        base_filter = {"report_id": report_id}
        if is_visible is not None:
            base_filter["is_visible"] = is_visible

        # 使用游标分页
        result = await cursor_paginator.paginate(
            collection=summary_report_service.db.summary_report_data_items,
            base_filter=base_filter,
            cursor=cursor,
            limit=limit,
            sort_field="added_at",
            direction=-1  # 最新添加的在前
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的游标: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询数据项失败: {str(e)}"
        )


@router.post("/{report_id}/data", response_model=SummaryReportDataItem, status_code=status.HTTP_201_CREATED)
async def add_data_item(report_id: str, request: AddDataItemRequest):
    """
    添加数据项到报告

    用户手动选择数据加入报告
    """
    try:
        item = await summary_report_service.add_data_item(
            report_id=report_id,
            source_type=request.source_type,
            title=request.title,
            content=request.content,
            added_by=request.added_by,
            url=request.url,
            source_id=request.source_id,
            task_id=request.task_id,
            task_type=request.task_type,
            tags=request.tags,
            importance=request.importance
        )
        return item
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加数据项失败: {str(e)}"
        )


# ==========================================
# 模块4: 内容编辑与版本管理
# ==========================================

@router.put("/{report_id}/content")
async def update_report_content(report_id: str, request: UpdateContentRequest):
    """
    更新报告内容（富文本编辑）

    支持Markdown/HTML格式的内容编辑
    自动版本管理
    """
    try:
        success = await summary_report_service.update_report_content(
            report_id=report_id,
            content_text=request.content_text,
            content_format=request.content_format,
            is_manual=request.is_manual,
            updated_by=request.updated_by,
            change_description=request.change_description
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"报告不存在: {report_id}"
            )

        return {"message": "内容更新成功", "report_id": report_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新内容失败: {str(e)}"
        )


@router.get("/{report_id}/versions")
async def get_report_versions(
    report_id: str,
    cursor: Optional[str] = Query(None, description="分页游标"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    获取报告版本历史（游标分页）

    查看报告的所有历史版本，使用游标分页

    响应格式:
    {
        "items": [...],  # 版本列表
        "meta": {
            "has_next": bool,      # 是否有下一页
            "next_cursor": str,    # 下一页游标
            "count": int           # 当前页记录数
        }
    }
    """
    try:
        # 使用游标分页
        result = await cursor_paginator.paginate(
            collection=summary_report_service.db.summary_report_versions,
            base_filter={"report_id": report_id},
            cursor=cursor,
            limit=limit,
            sort_field="created_at",
            direction=-1  # 最新版本在前
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的游标: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询版本历史失败: {str(e)}"
        )


@router.post("/{report_id}/versions/{version_number}/restore")
async def rollback_to_version(
    report_id: str,
    version_number: int,
    updated_by: str = Query(..., description="操作者")
):
    """
    回滚到历史版本

    将报告内容恢复到指定版本
    """
    try:
        success = await summary_report_service.rollback_to_version(
            report_id=report_id,
            version_number=version_number,
            updated_by=updated_by
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"版本不存在: {version_number}"
            )

        return {
            "message": "回滚成功",
            "report_id": report_id,
            "version_number": version_number
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回滚失败: {str(e)}"
        )


# ==========================================
# 模块5: LLM/AI生成（预留接口）
# ==========================================

@router.post("/{report_id}/generate")
async def generate_report_with_llm(
    report_id: str,
    request: GenerateReportRequest
):
    """
    使用LLM生成报告总结（预留接口）

    调用LLM服务生成报告内容
    待LLM模块开发完成后实现
    """
    try:
        result = await summary_report_service.generate_report_with_llm(
            report_id=report_id,
            generation_mode=request.generation_mode,
            llm_config=request.llm_config
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成报告失败: {str(e)}"
        )


@router.get("/{report_id}/analysis")
async def analyze_report_data_with_ai(
    report_id: str,
    analysis_type: str = Query(default="trend", description="分析类型")
):
    """
    使用AI分析报告数据（预留接口）

    调用AI服务进行数据分析
    待AI模块开发完成后实现
    """
    try:
        result = await summary_report_service.analyze_report_data_with_ai(
            report_id=report_id,
            analysis_type=analysis_type
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI分析失败: {str(e)}"
        )
