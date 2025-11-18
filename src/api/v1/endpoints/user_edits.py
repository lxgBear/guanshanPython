"""
用户批量编辑API

提供批量编辑功能的RESTful API端点

版本: v1.0.0
日期: 2025-11-17
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.user_edit_service import user_edit_service

router = APIRouter(
    prefix="/user-edits"
    # tags 由 router.py 统一管理: ["✏️ 用户批量编辑"]
)


# ========== 请求模型 ==========

class BatchUpdateRequest(BaseModel):
    """批量更新请求（灵活模式）"""

    class UpdateItem(BaseModel):
        """单条更新项"""
        id: str = Field(..., description="记录ID")
        # 以下字段都是可选的，根据需要编辑
        title: Optional[str] = Field(None, description="标题")
        content_zh: Optional[str] = Field(None, description="中文内容")
        title_generated: Optional[str] = Field(None, description="AI生成的标题")
        article_tag: Optional[List[str]] = Field(None, description="文章标签")
        cls_results: Optional[str] = Field(None, description="分类结果")
        author: Optional[str] = Field(None, description="作者")
        published_date: Optional[str] = Field(None, description="发布日期")
        language: Optional[str] = Field(None, description="语言")
        user_rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分")
        user_notes: Optional[str] = Field(None, description="用户备注")
        news_results: Optional[Dict[str, Any]] = Field(None, description="News结果对象")

        class Config:
            extra = "allow"  # 允许额外字段

    updates: List[UpdateItem] = Field(..., description="更新列表")
    editor_id: str = Field(..., description="编辑人ID")


class BatchUpdateFieldsRequest(BaseModel):
    """批量更新请求（统一字段模式）"""
    record_ids: List[str] = Field(..., description="记录ID列表")
    updates: Dict[str, Any] = Field(..., description="要更新的字段")
    editor_id: str = Field(..., description="编辑人ID")


class SingleUpdateRequest(BaseModel):
    """单条更新请求"""
    title: Optional[str] = None
    content_zh: Optional[str] = None
    title_generated: Optional[str] = None
    article_tag: Optional[List[str]] = None
    cls_results: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    language: Optional[str] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    user_notes: Optional[str] = None
    news_results: Optional[Dict[str, Any]] = None
    editor_id: str = Field(..., description="编辑人ID")

    class Config:
        extra = "allow"


class CopyFromOriginalRequest(BaseModel):
    """从原表复制请求"""
    source_ids: List[str] = Field(..., description="原始记录ID列表")
    editor_id: str = Field(..., description="编辑人ID")


# ========== 响应模型 ==========

class BatchUpdateResponse(BaseModel):
    """批量更新响应"""
    success: bool = Field(..., description="是否成功")
    total: int = Field(..., description="总数")
    updated: int = Field(..., description="成功更新数")
    failed: int = Field(..., description="失败数")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="详细结果")
    validation_errors: Optional[List[Dict[str, Any]]] = Field(None, description="验证错误")


class BatchUpdateFieldsResponse(BaseModel):
    """批量统一更新响应"""
    success: bool = Field(..., description="是否成功")
    total: int = Field(..., description="总数")
    updated: int = Field(..., description="成功更新数")
    failed: int = Field(..., description="失败数")
    updated_fields: List[str] = Field(..., description="更新的字段列表")
    message: str = Field(..., description="提示信息")


class SingleUpdateResponse(BaseModel):
    """单条更新响应"""
    success: bool = Field(..., description="是否成功")
    id: str = Field(..., description="记录ID")
    updated_fields: List[str] = Field(..., description="更新的字段列表")
    message: str = Field(..., description="提示信息")


class CopyFromOriginalResponse(BaseModel):
    """复制响应"""
    success: bool = Field(..., description="是否成功")
    total: int = Field(..., description="总数")
    copied: int = Field(..., description="成功复制数")
    failed: int = Field(..., description="失败数")
    new_ids: List[str] = Field(..., description="新创建的记录ID列表")
    not_found_ids: Optional[List[str]] = Field(None, description="未找到的原始记录ID")


# ========== API端点 ==========

@router.post(
    "/batch",
    response_model=BatchUpdateResponse,
    summary="批量更新（灵活模式）",
    description="批量更新多条记录，每条可以更新不同字段"
)
async def batch_update(request: BatchUpdateRequest):
    """
    批量更新（灵活模式）

    **使用场景**:
    - 用户勾选多条记录
    - 进入批量编辑模式（类似Excel）
    - 为每条记录单独编辑不同字段
    - 点击"批量保存"

    **示例**:
    ```json
    {
      "updates": [
        {
          "id": "record_id_1",
          "title": "新标题1",
          "content_zh": "新内容1"
        },
        {
          "id": "record_id_2",
          "title": "新标题2",
          "article_tag": ["GPT-5", "AI"]
        }
      ],
      "editor_id": "user_123"
    }
    ```
    """
    try:
        # 转换为字典列表
        updates_list = [item.dict(exclude_none=True) for item in request.updates]

        # 执行批量更新
        result = await user_edit_service.batch_update(
            updates=updates_list,
            editor_id=request.editor_id
        )

        return BatchUpdateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.post(
    "/batch-fields",
    response_model=BatchUpdateFieldsResponse,
    summary="批量更新（统一字段）",
    description="批量更新多条记录的相同字段为相同值"
)
async def batch_update_fields(request: BatchUpdateFieldsRequest):
    """
    批量更新（统一字段模式）

    **使用场景**:
    - 用户勾选多条记录
    - 点击"批量设置分类"
    - 选择统一的分类、标签等
    - 应用到所有选中记录

    **示例**:
    ```json
    {
      "record_ids": ["id1", "id2", "id3"],
      "updates": {
        "news_results": {
          "category": {
            "大类": "科技",
            "类别": "人工智能",
            "地域": "美国"
          }
        },
        "article_tag": ["GPT-5", "AI"],
        "user_rating": 5
      },
      "editor_id": "user_123"
    }
    ```
    """
    try:
        result = await user_edit_service.batch_update_fields(
            record_ids=request.record_ids,
            updates=request.updates,
            editor_id=request.editor_id
        )

        return BatchUpdateFieldsResponse(
            success=result["success"],
            total=result["total"],
            updated=result["updated"],
            failed=result["failed"],
            updated_fields=result["updated_fields"],
            message=f"成功更新{result['updated']}条记录"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量更新失败: {str(e)}")


@router.patch(
    "/{record_id}",
    response_model=SingleUpdateResponse,
    summary="更新单条记录",
    description="更新单条记录的多个字段"
)
async def update_one(record_id: str, request: SingleUpdateRequest):
    """
    更新单条记录

    **使用场景**:
    - 点击某条记录的"编辑"按钮
    - 进入编辑表单页面
    - 修改多个字段
    - 点击"保存"

    **示例**:
    ```json
    {
      "title": "修正后的标题",
      "content_zh": "修正后的内容",
      "news_results": {
        "category": {
          "大类": "科技",
          "类别": "AI",
          "地域": "美国"
        }
      },
      "user_rating": 5,
      "editor_id": "user_123"
    }
    ```
    """
    try:
        # 提取更新字段
        updates = request.dict(exclude={"editor_id"}, exclude_none=True)

        # 执行更新
        result = await user_edit_service.update_one(
            record_id=record_id,
            updates=updates,
            editor_id=request.editor_id
        )

        return SingleUpdateResponse(
            success=result["success"],
            id=result["id"],
            updated_fields=result["updated_fields"],
            message="更新成功"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.get(
    "/{record_id}",
    summary="获取记录详情",
    description="获取单条编辑记录的详细信息"
)
async def get_record(record_id: str):
    """
    获取记录详情

    **使用场景**:
    - 进入编辑页面时获取当前值
    - 查看编辑记录详情

    **返回**: ProcessedResult实体的完整数据
    """
    try:
        record = await user_edit_service.get_by_id(record_id)

        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        return record.dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记录失败: {str(e)}")


@router.get(
    "/tasks/{task_id}",
    summary="获取任务的编辑记录列表",
    description="分页获取任务的编辑记录"
)
async def get_by_task(
    task_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取任务的编辑记录列表

    **使用场景**:
    - 查看某个任务下用户编辑的所有记录
    - 分页浏览编辑历史

    **返回**: 分页的编辑记录列表
    """
    try:
        result = await user_edit_service.get_by_task(
            task_id=task_id,
            page=page,
            page_size=page_size
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记录列表失败: {str(e)}")


@router.get(
    "/editors/{editor_id}",
    summary="获取编辑人的记录列表",
    description="分页获取某个编辑人的所有编辑记录"
)
async def get_by_editor(
    editor_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取编辑人的记录列表

    **使用场景**:
    - 查看某个用户编辑的所有记录
    - 审计用户编辑历史

    **返回**: 分页的编辑记录列表
    """
    try:
        result = await user_edit_service.get_by_editor(
            editor_id=editor_id,
            page=page,
            page_size=page_size
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记录列表失败: {str(e)}")


@router.post(
    "/copy",
    response_model=CopyFromOriginalResponse,
    summary="从原表复制记录",
    description="从processed_results表复制记录到user_edited_results用于编辑"
)
async def copy_from_original(request: CopyFromOriginalRequest):
    """
    从原表复制记录

    **使用场景**:
    - 从AI处理结果表中选择记录
    - 复制到用户编辑表进行编辑
    - 避免直接修改原始数据

    **示例**:
    ```json
    {
      "source_ids": ["original_id_1", "original_id_2"],
      "editor_id": "user_123"
    }
    ```

    **返回**: 新创建的记录ID列表
    """
    try:
        result = await user_edit_service.copy_from_original(
            source_ids=request.source_ids,
            editor_id=request.editor_id
        )

        return CopyFromOriginalResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"复制记录失败: {str(e)}")


@router.delete(
    "/{record_id}",
    summary="删除编辑记录",
    description="删除单条用户编辑记录"
)
async def delete_record(record_id: str):
    """
    删除编辑记录

    **使用场景**:
    - 删除不需要的编辑记录
    - 清理测试数据

    **注意**: 这是物理删除，不可恢复
    """
    try:
        success = await user_edit_service.repository.delete(record_id)

        if not success:
            raise HTTPException(status_code=404, detail="记录不存在")

        return {
            "success": True,
            "id": record_id,
            "message": "删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
