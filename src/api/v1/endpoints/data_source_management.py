"""数据源管理API端点

提供数据源的完整生命周期管理接口：
- 数据源CRUD操作
- 原始数据引用管理
- 状态管理（确定/恢复草稿）
- 内容编辑
- 批量操作
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from src.infrastructure.database.connection import get_mongodb_database
from src.services.data_curation_service import DataCurationService
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/data-sources")


# ==========================================
# Pydantic模型定义
# ==========================================

class CreateDataSourceRequest(BaseModel):
    """创建数据源请求"""
    title: str = Field(..., description="数据源标题", min_length=1, max_length=200)
    description: str = Field("", description="数据源描述", max_length=1000)
    created_by: str = Field(..., description="创建者", min_length=1)
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    metadata: Optional[dict] = Field(default=None, description="扩展元数据")
    # 分类字段
    primary_category: Optional[str] = Field(default=None, description="第一级分类：大类")
    secondary_category: Optional[str] = Field(default=None, description="第二级分类：子目录")
    tertiary_category: Optional[str] = Field(default=None, description="第三级分类：具体分类")
    custom_tags: Optional[List[str]] = Field(default=None, description="自定义标签数组")


class UpdateDataSourceInfoRequest(BaseModel):
    """更新数据源基础信息请求"""
    title: Optional[str] = Field(None, description="新标题", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="新描述", max_length=1000)
    tags: Optional[List[str]] = Field(None, description="新标签列表")
    # 分类字段
    primary_category: Optional[str] = Field(None, description="第一级分类：大类")
    secondary_category: Optional[str] = Field(None, description="第二级分类：子目录")
    tertiary_category: Optional[str] = Field(None, description="第三级分类：具体分类")
    custom_tags: Optional[List[str]] = Field(None, description="自定义标签数组")
    updated_by: str = Field(..., description="更新者", min_length=1)


class UpdateDataSourceContentRequest(BaseModel):
    """更新数据源内容请求"""
    edited_content: str = Field(..., description="编辑内容（Markdown格式）")
    updated_by: str = Field(..., description="更新者", min_length=1)


class AddRawDataRequest(BaseModel):
    """添加原始数据请求"""
    data_id: str = Field(..., description="原始数据ID")
    data_type: str = Field(..., description="数据类型（scheduled或instant）", pattern="^(scheduled|instant)$")
    source_task_id: Optional[str] = Field(None, description="来源任务ID（可选，用于追溯数据来源）")
    added_by: str = Field(..., description="添加者", min_length=1)


class RemoveRawDataRequest(BaseModel):
    """移除原始数据请求"""
    data_id: str = Field(..., description="原始数据ID")
    data_type: str = Field(..., description="数据类型（scheduled或instant）", pattern="^(scheduled|instant)$")
    source_task_id: Optional[str] = Field(None, description="来源任务ID（可选，用于追溯数据来源）")
    removed_by: str = Field(..., description="移除者", min_length=1)


class ConfirmDataSourceRequest(BaseModel):
    """确定数据源请求"""
    confirmed_by: str = Field(..., description="确定者", min_length=1)


class RevertDataSourceRequest(BaseModel):
    """恢复草稿请求"""
    reverted_by: str = Field(..., description="操作者", min_length=1)


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    data_ids: List[str] = Field(..., description="原始数据ID列表", min_items=1)
    data_type: str = Field(..., description="数据类型（scheduled或instant）", pattern="^(scheduled|instant)$")
    operator: str = Field(..., description="操作者", min_length=1)


# ==========================================
# 依赖注入
# ==========================================

async def get_data_curation_service():
    """获取数据整编服务实例"""
    db = await get_mongodb_database()
    return DataCurationService(db)


# ==========================================
# 数据源基础操作端点
# ==========================================

@router.post("/", status_code=201, summary="创建数据源")
async def create_data_source(
    request: CreateDataSourceRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """创建新的数据源（草稿状态）

    **功能说明：**
    - 创建草稿状态的数据源
    - 初始状态：DRAFT
    - 初始数据量：0

    **请求示例：**
    ```json
    {
      "title": "Python Web开发最佳实践",
      "description": "收集Python Web开发相关的优质资源",
      "created_by": "user123",
      "tags": ["Python", "Web开发", "最佳实践"]
    }
    ```
    """
    try:
        data_source = await service.create_data_source(
            title=request.title,
            description=request.description,
            created_by=request.created_by,
            tags=request.tags,
            metadata=request.metadata,
            primary_category=request.primary_category,
            secondary_category=request.secondary_category,
            tertiary_category=request.tertiary_category,
            custom_tags=request.custom_tags
        )

        return {
            "success": True,
            "message": "数据源创建成功",
            "data": data_source.to_dict()
        }

    except Exception as e:
        logger.error(f"创建数据源失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建数据源失败: {str(e)}")


@router.get("/{data_source_id}", summary="获取数据源详情")
async def get_data_source(
    data_source_id: str,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """获取数据源详细信息

    **返回数据包含：**
    - 基础信息（标题、描述、标签）
    - 状态信息（draft/confirmed）
    - 原始数据引用列表
    - 编辑内容
    - 统计信息
    - 时间戳
    """
    data_source = await service.get_data_source(data_source_id)

    if not data_source:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return {
        "success": True,
        "data": data_source.to_dict()
    }


@router.get("/", summary="列出数据源")
async def list_data_sources(
    created_by: Optional[str] = Query(None, description="创建者过滤"),
    status: Optional[str] = Query(None, description="状态过滤（draft/confirmed）"),
    source_type: Optional[str] = Query(None, description="数据源类型过滤（scheduled/instant/mixed）"),
    start_date: Optional[datetime] = Query(None, description="开始日期过滤"),
    end_date: Optional[datetime] = Query(None, description="结束日期过滤"),
    # 分类过滤参数
    primary_category: Optional[str] = Query(None, description="第一级分类过滤"),
    secondary_category: Optional[str] = Query(None, description="第二级分类过滤"),
    tertiary_category: Optional[str] = Query(None, description="第三级分类过滤"),
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    service: DataCurationService = Depends(get_data_curation_service)
):
    """列出所有数据源（支持过滤和分页）

    **过滤条件：**
    - created_by: 按创建者过滤
    - status: 按状态过滤（draft/confirmed）
    - source_type: 按数据源类型过滤（scheduled/instant/mixed）
    - start_date: 创建时间起始日期
    - end_date: 创建时间结束日期

    **分页参数：**
    - limit: 每页数量（1-100，默认50）
    - skip: 跳过数量（默认0）
    """
    try:
        data_sources, total = await service.list_data_sources(
            created_by=created_by,
            status=status,
            source_type=source_type,
            start_date=start_date,
            end_date=end_date,
            primary_category=primary_category,
            secondary_category=secondary_category,
            tertiary_category=tertiary_category,
            limit=limit,
            skip=skip
        )

        return {
            "success": True,
            "data": {
                "items": [ds.to_summary() for ds in data_sources],
                "total": total,
                "limit": limit,
                "skip": skip
            }
        }

    except Exception as e:
        logger.error(f"列出数据源失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出数据源失败: {str(e)}")


@router.put("/{data_source_id}/info", summary="更新数据源基础信息")
async def update_data_source_info(
    data_source_id: str,
    request: UpdateDataSourceInfoRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """更新数据源基础信息（仅草稿状态可编辑）

    **可更新字段：**
    - title: 标题
    - description: 描述
    - tags: 标签列表

    **限制条件：**
    - 仅草稿状态（DRAFT）可编辑
    - 已确定状态（CONFIRMED）不可编辑
    """
    try:
        success = await service.update_data_source_info(
            data_source_id=data_source_id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            primary_category=request.primary_category,
            secondary_category=request.secondary_category,
            tertiary_category=request.tertiary_category,
            custom_tags=request.custom_tags,
            updated_by=request.updated_by
        )

        if success:
            return {
                "success": True,
                "message": "数据源信息更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="数据源信息更新失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新数据源信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新数据源信息失败: {str(e)}")


@router.put("/{data_source_id}/content", summary="更新数据源内容")
async def update_data_source_content(
    data_source_id: str,
    request: UpdateDataSourceContentRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """更新数据源编辑内容（仅草稿状态可编辑）

    **功能说明：**
    - 更新富文本编辑内容
    - 自动增加版本号
    - 仅草稿状态可编辑

    **内容格式：**
    - 支持Markdown格式
    - 最大长度：无限制
    """
    try:
        success = await service.update_data_source_content(
            data_source_id=data_source_id,
            edited_content=request.edited_content,
            updated_by=request.updated_by
        )

        if success:
            return {
                "success": True,
                "message": "数据源内容更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="数据源内容更新失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新数据源内容失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新数据源内容失败: {str(e)}")


@router.delete("/{data_source_id}", summary="删除数据源")
async def delete_data_source(
    data_source_id: str,
    deleted_by: str = Query(..., description="删除者"),
    service: DataCurationService = Depends(get_data_curation_service)
):
    """删除数据源

    **状态同步规则：**
    - 草稿状态：原始数据 processing → archived
    - 已确定状态：原始数据保持 completed（不变）

    **操作说明：**
    - 草稿状态删除：释放原始数据引用，数据状态恢复为archived
    - 已确定状态删除：保留原始数据completed状态（数据已被使用）
    """
    try:
        success = await service.delete_data_source(
            data_source_id=data_source_id,
            deleted_by=deleted_by
        )

        if success:
            return {
                "success": True,
                "message": "数据源删除成功"
            }
        else:
            raise HTTPException(status_code=400, detail="数据源删除失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除数据源失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除数据源失败: {str(e)}")


# ==========================================
# 原始数据管理端点
# ==========================================

@router.post("/{data_source_id}/raw-data", summary="添加原始数据到数据源")
async def add_raw_data_to_source(
    data_source_id: str,
    request: AddRawDataRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """添加原始数据到数据源

    **状态同步（MongoDB事务）：**
    - 原始数据状态：pending/archived → processing
    - 数据源引用列表：添加新引用
    - 统计信息：自动更新

    **前置条件：**
    - 数据源必须为草稿状态（DRAFT）
    - 原始数据必须存在
    - 原始数据状态必须为pending或archived

    **请求示例：**
    ```json
    {
      "data_id": "1234567890123456789",
      "data_type": "instant",
      "added_by": "user123"
    }
    ```
    """
    try:
        success = await service.add_raw_data_to_source(
            data_source_id=data_source_id,
            data_id=request.data_id,
            data_type=request.data_type,
            added_by=request.added_by
        )

        if success:
            return {
                "success": True,
                "message": "原始数据添加成功"
            }
        else:
            raise HTTPException(status_code=400, detail="原始数据添加失败")

    except ValueError as e:
        logger.warning(f"添加原始数据业务逻辑错误: {str(e)} (data_source_id={data_source_id}, data_id={request.data_id}, data_type={request.data_type})")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"添加原始数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"添加原始数据失败: {str(e)}")


@router.delete("/{data_source_id}/raw-data", summary="从数据源移除原始数据")
async def remove_raw_data_from_source(
    data_source_id: str,
    request: RemoveRawDataRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """从数据源移除原始数据

    **状态同步（MongoDB事务）：**
    - 原始数据状态：processing → archived
    - 数据源引用列表：移除引用
    - 统计信息：自动更新

    **前置条件：**
    - 数据源必须为草稿状态（DRAFT）
    - 原始数据必须在数据源中
    """
    try:
        success = await service.remove_raw_data_from_source(
            data_source_id=data_source_id,
            data_id=request.data_id,
            data_type=request.data_type,
            removed_by=request.removed_by
        )

        if success:
            return {
                "success": True,
                "message": "原始数据移除成功"
            }
        else:
            raise HTTPException(status_code=400, detail="原始数据移除失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"移除原始数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"移除原始数据失败: {str(e)}")


# ==========================================
# 状态管理端点
# ==========================================

@router.post("/{data_source_id}/confirm", summary="确定数据源")
async def confirm_data_source(
    data_source_id: str,
    request: ConfirmDataSourceRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """确定数据源

    **状态转换：**
    - 数据源：DRAFT → CONFIRMED

    **状态同步（MongoDB事务）：**
    - 所有关联的原始数据：processing → completed
    - 批量更新所有关联数据（如果有）

    **前置条件：**
    - 数据源必须为草稿状态（DRAFT）
    - 允许确定空数据源（不包含任何原始数据）

    **操作说明：**
    - 确定后数据源变为只读
    - 无法添加/移除原始数据
    - 无法编辑内容
    - 可以恢复为草稿（revert）
    """
    try:
        success = await service.confirm_data_source(
            data_source_id=data_source_id,
            confirmed_by=request.confirmed_by
        )

        if success:
            return {
                "success": True,
                "message": "数据源确定成功"
            }
        else:
            raise HTTPException(status_code=400, detail="数据源确定失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"确定数据源失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"确定数据源失败: {str(e)}")


@router.post("/{data_source_id}/revert", summary="恢复数据源为草稿")
async def revert_data_source_to_draft(
    data_source_id: str,
    request: RevertDataSourceRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """恢复数据源为草稿

    **状态转换：**
    - 数据源：CONFIRMED → DRAFT

    **状态同步（MongoDB事务）：**
    - 所有原始数据：completed → processing
    - 批量更新所有关联数据

    **前置条件：**
    - 数据源必须为已确定状态（CONFIRMED）

    **操作说明：**
    - 恢复后可以继续编辑
    - 可以添加/移除原始数据
    - 可以再次确定
    """
    try:
        success = await service.revert_data_source_to_draft(
            data_source_id=data_source_id,
            reverted_by=request.reverted_by
        )

        if success:
            return {
                "success": True,
                "message": "数据源已恢复为草稿"
            }
        else:
            raise HTTPException(status_code=400, detail="恢复草稿失败")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"恢复草稿失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"恢复草稿失败: {str(e)}")


# ==========================================
# 批量操作端点
# ==========================================

@router.post("/batch/archive", summary="批量留存原始数据")
async def batch_archive_raw_data(
    request: BatchOperationRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """批量留存原始数据

    **状态更新：**
    - 任意状态 → archived

    **使用场景：**
    - 将重要数据标记为已留存
    - 避免被删除或覆盖
    - 方便后续查找和使用

    **请求示例：**
    ```json
    {
      "data_ids": ["id1", "id2", "id3"],
      "data_type": "instant",
      "operator": "user123"
    }
    ```
    """
    try:
        result = await service.batch_archive_raw_data(
            data_ids=request.data_ids,
            data_type=request.data_type,
            updated_by=request.operator
        )

        return {
            "success": True,
            "message": "批量留存操作完成",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批量留存失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量留存失败: {str(e)}")


@router.post("/batch/delete", summary="批量删除原始数据")
async def batch_delete_raw_data(
    request: BatchOperationRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """批量软删除原始数据

    **状态更新：**
    - 任意状态 → deleted

    **使用场景：**
    - 清理无用数据
    - 软删除（可恢复）
    - 不真实删除数据库记录

    **请求示例：**
    ```json
    {
      "data_ids": ["id1", "id2", "id3"],
      "data_type": "scheduled",
      "operator": "user123"
    }
    ```
    """
    try:
        result = await service.batch_delete_raw_data(
            data_ids=request.data_ids,
            data_type=request.data_type,
            deleted_by=request.operator
        )

        return {
            "success": True,
            "message": "批量删除操作完成",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"批量删除失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")


# ==========================================
# 存档数据查询端点
# ==========================================

@router.get("/{data_source_id}/archived-data", summary="获取数据源的存档数据")
async def get_archived_data(
    data_source_id: str,
    page: int = Query(1, ge=1, description="页码（从1开始）"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    service: DataCurationService = Depends(get_data_curation_service)
):
    """获取数据源的存档数据（分页）

    **功能说明：**
    - 查询数据源确认时自动存档的原始数据
    - 存档数据保存完整content字段（非200字符截断）
    - 支持分页查询
    - 按创建时间倒序排列（最新的在前）

    **数据来源：**
    - scheduled类型：定时搜索结果
    - instant类型：即时搜索结果

    **分页参数：**
    - page: 页码（从1开始，默认1）
    - page_size: 每页数量（1-100，默认50）

    **返回数据包含：**
    - id: 存档数据ID（雪花算法）
    - data_source_id: 所属数据源ID
    - original_data_id: 原始数据ID
    - data_type: 数据类型（scheduled/instant）
    - title, url, content: 完整内容快照
    - archived_at: 存档时间
    - archived_by: 存档操作者
    - archived_reason: 存档原因（confirm/manual）
    - type_specific_fields: 类型特定字段
    """
    try:
        # 验证数据源是否存在
        data_source = await service.get_data_source(data_source_id)
        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在")

        # 查询存档数据
        archived_list, total = await service.get_archived_data(
            data_source_id=data_source_id,
            page=page,
            page_size=page_size
        )

        # 计算分页信息
        total_pages = (total + page_size - 1) // page_size

        return {
            "success": True,
            "data": {
                "items": [item.to_dict() for item in archived_list],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取存档数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取存档数据失败: {str(e)}")


@router.get("/{data_source_id}/archived-data/stats", summary="获取存档数据统计信息")
async def get_archived_data_statistics(
    data_source_id: str,
    service: DataCurationService = Depends(get_data_curation_service)
):
    """获取数据源的存档统计信息

    **功能说明：**
    - 统计数据源的存档数据量
    - 按数据类型分组统计
    - 计算总内容大小

    **返回数据包含：**
    - data_source_id: 数据源ID
    - total_count: 总存档数量
    - scheduled_count: scheduled类型数量
    - instant_count: instant类型数量
    - total_content_size: 总内容大小（字符数）
    - by_type: 按类型详细统计
      - count: 该类型数量
      - content_size: 该类型内容大小

    **使用场景：**
    - 了解数据源存档情况
    - 监控存储空间使用
    - 统计数据来源分布
    """
    try:
        # 验证数据源是否存在
        data_source = await service.get_data_source(data_source_id)
        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在")

        # 获取统计信息
        stats = await service.get_archived_data_statistics(data_source_id)

        return {
            "success": True,
            "data": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取存档统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取存档统计失败: {str(e)}")
