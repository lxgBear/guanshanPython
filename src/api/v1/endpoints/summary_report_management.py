"""智能总结报告管理 API 端点

模块化组织：
1. 报告管理（CRUD）
2. 内容编辑与版本管理
3. LLM/AI生成（预留）
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from src.services.summary_report_service import summary_report_service
from src.core.domain.entities.summary_report import (
    SummaryReport,
    SummaryReportVersion
)
from src.utils.cursor_pagination import cursor_paginator

router = APIRouter(prefix="/summary-reports")


# ==========================================
# 请求/响应模型
# ==========================================

# 报告管理相关
class CreateReportRequest(BaseModel):
    """创建报告请求"""
    title: str = Field(..., description="报告标题")
    description: Optional[str] = Field(None, description="报告描述")
    report_type: str = Field(default="comprehensive", description="报告类型")
    created_by: str = Field(..., description="创建者ID")


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
    创建总结报告

    创建一个新的智能总结报告
    """
    try:
        report = await summary_report_service.create_report(
            title=request.title,
            description=request.description,
            report_type=request.report_type,
            created_by=request.created_by
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
async def get_report(report_id: str):
    """
    获取报告详情

    获取指定报告的详细信息，包括内容、统计等
    """
    try:
        report = await summary_report_service.get_report(report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"报告不存在: {report_id}"
            )
        return report
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
