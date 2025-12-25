"""角色管理API端点"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.api.dependencies.auth import (
    get_db_session,
    get_current_active_user,
    require_permissions,
    require_roles
)
from src.services.auth import RoleService
from src.services.auth.role_service import RoleServiceException
from src.core.domain.entities.auth import (
    Role, RoleCreate, RoleUpdate, RolePermissionUpdate, Permission
)

router = APIRouter()


class RoleListResponse(BaseModel):
    """角色列表响应"""
    items: List[Role]


class PermissionListResponse(BaseModel):
    """权限列表响应"""
    items: List[Permission]
    modules: List[str]


class MessageResponse(BaseModel):
    """消息响应"""
    message: str


@router.get(
    "",
    response_model=RoleListResponse,
    summary="获取角色列表",
    dependencies=[Depends(require_permissions("role:read"))]
)
async def list_roles(
    is_active: Optional[bool] = Query(None, description="状态筛选"),
    include_system: bool = Query(True, description="是否包含系统角色"),
    session: AsyncSession = Depends(get_db_session)
):
    """获取所有角色列表"""
    role_service = RoleService(session)
    roles = await role_service.list_roles(
        is_active=is_active,
        include_system=include_system
    )
    return RoleListResponse(items=roles)


@router.post(
    "",
    response_model=Role,
    status_code=status.HTTP_201_CREATED,
    summary="创建角色",
    dependencies=[Depends(require_permissions("role:create"))]
)
async def create_role(
    data: RoleCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """
    创建新角色

    - **code**: 角色代码（必填，小写字母开头，只能包含小写字母、数字和下划线）
    - **name**: 角色名称（必填）
    - **level**: 权限级别（0-100，默认0）
    - **description**: 角色描述（选填）
    - **parent_role_code**: 父级角色代码（选填，用于权限继承）
    - **permission_codes**: 权限代码列表（选填）
    """
    role_service = RoleService(session)

    try:
        role = await role_service.create_role(data)
        return role
    except RoleServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.get(
    "/{role_id}",
    response_model=Role,
    summary="获取角色详情",
    dependencies=[Depends(require_permissions("role:read"))]
)
async def get_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """获取指定角色的详细信息"""
    role_service = RoleService(session)
    role = await role_service.get_role(role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_001", "message": "角色不存在"}
        )

    return role


@router.put(
    "/{role_id}",
    response_model=Role,
    summary="更新角色",
    dependencies=[Depends(require_permissions("role:update"))]
)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """
    更新角色信息

    注意：系统角色的某些字段（权限级别、父级角色）不可修改
    """
    role_service = RoleService(session)

    try:
        role = await role_service.update_role(role_id, data)
        return role
    except RoleServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.delete(
    "/{role_id}",
    response_model=MessageResponse,
    summary="删除角色",
    dependencies=[Depends(require_permissions("role:delete"))]
)
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_db_session)
):
    """
    删除角色

    注意：系统角色不可删除
    """
    role_service = RoleService(session)

    try:
        result = await role_service.delete_role(role_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ROLE_001", "message": "角色不存在"}
            )
        return {"message": "角色删除成功"}
    except RoleServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.put(
    "/{role_id}/permissions",
    response_model=Role,
    summary="更新角色权限",
    dependencies=[Depends(require_permissions("role:update"))]
)
async def update_role_permissions(
    role_id: int,
    data: RolePermissionUpdate,
    session: AsyncSession = Depends(get_db_session)
):
    """
    更新角色的权限配置

    会替换角色现有的所有权限
    """
    role_service = RoleService(session)

    try:
        role = await role_service.update_role_permissions(role_id, data.permission_codes)
        return role
    except RoleServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.get(
    "/code/{role_code}",
    response_model=Role,
    summary="根据代码获取角色",
    dependencies=[Depends(require_permissions("role:read"))]
)
async def get_role_by_code(
    role_code: str,
    session: AsyncSession = Depends(get_db_session)
):
    """根据角色代码获取角色详情"""
    role_service = RoleService(session)
    role = await role_service.get_role_by_code(role_code)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ROLE_001", "message": "角色不存在"}
        )

    return role


# ============ 权限管理 ============

@router.get(
    "/permissions/list",
    response_model=PermissionListResponse,
    summary="获取权限列表",
    dependencies=[Depends(require_permissions("role:read"))]
)
async def list_permissions(
    module: Optional[str] = Query(None, description="按模块筛选"),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取所有权限列表

    返回权限列表和模块列表
    """
    role_service = RoleService(session)
    permissions, modules = await role_service.list_permissions(module=module)
    return PermissionListResponse(items=permissions, modules=modules)
