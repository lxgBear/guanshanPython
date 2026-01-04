"""用户管理API端点 (MongoDB 版本)"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from src.api.dependencies.auth import (
    get_current_active_user,
    require_permissions
)
from src.services.auth import UserService
from src.services.auth.user_service import UserServiceException
from src.services.auth import AuthService, AuthException
from src.core.domain.entities.auth import (
    User, UserCreate, UserUpdate, PasswordReset, RoleAssign
)

router = APIRouter()


class UserListResponse(BaseModel):
    """用户列表响应"""
    items: List[User]
    total: int
    page: int
    size: int
    pages: int


class UserCreateResponse(BaseModel):
    """创建用户响应"""
    id: str  # MongoDB 使用字符串ID
    username: str
    message: str


class MessageResponse(BaseModel):
    """消息响应"""
    message: str


@router.get(
    "",
    response_model=UserListResponse,
    summary="获取用户列表",
    dependencies=[Depends(require_permissions("user:list"))]
)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[str] = Query(None, description="角色代码筛选"),
    is_active: Optional[bool] = Query(None, description="状态筛选")
):
    """
    获取用户列表

    - 支持关键词搜索（用户名、显示名、邮箱）
    - 支持按角色筛选
    - 支持按状态筛选
    """
    user_service = UserService()
    users, total = await user_service.list_users(
        page=page,
        size=size,
        keyword=keyword,
        role_code=role,
        is_active=is_active
    )

    pages = (total + size - 1) // size

    return UserListResponse(
        items=users,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
    dependencies=[Depends(require_permissions("user:create"))]
)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    创建新用户

    - **username**: 用户名（必填，3-50字符，以字母开头）
    - **password**: 密码（必填，8位以上，包含大小写和数字）
    - **email**: 邮箱（选填）
    - **display_name**: 显示名称（选填）
    - **phone**: 手机号（选填）
    - **department**: 部门（选填）
    - **role_codes**: 角色代码列表（选填，支持多角色）
    """
    user_service = UserService()

    try:
        user = await user_service.create_user(data, created_by=current_user.id)
        return UserCreateResponse(
            id=user.id,
            username=user.username,
            message="用户创建成功"
        )
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.get(
    "/{user_id}",
    response_model=User,
    summary="获取用户详情",
    dependencies=[Depends(require_permissions("user:read"))]
)
async def get_user(
    user_id: str  # MongoDB 使用字符串ID
):
    """获取指定用户的详细信息"""
    user_service = UserService()
    user = await user_service.get_user(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_003", "message": "用户不存在"}
        )

    return user


@router.put(
    "/{user_id}",
    response_model=User,
    summary="更新用户",
    dependencies=[Depends(require_permissions("user:update"))]
)
async def update_user(
    user_id: str,  # MongoDB 使用字符串ID
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    更新用户信息

    支持更新：邮箱、显示名称、手机号、部门、状态、角色
    """
    user_service = UserService()

    try:
        user = await user_service.update_user(
            user_id=user_id,
            data=data,
            operator_id=current_user.id
        )
        return user
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="删除用户",
    dependencies=[Depends(require_permissions("user:delete"))]
)
async def delete_user(
    user_id: str,  # MongoDB 使用字符串ID
    current_user: User = Depends(get_current_active_user)
):
    """删除用户"""
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_004", "message": "不能删除自己"}
        )

    user_service = UserService()
    result = await user_service.delete_user(user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_003", "message": "用户不存在"}
        )

    return {"message": "用户删除成功"}


@router.post(
    "/{user_id}/reset-password",
    response_model=MessageResponse,
    summary="重置用户密码",
    dependencies=[Depends(require_permissions("user:update"))]
)
async def reset_user_password(
    user_id: str,  # MongoDB 使用字符串ID
    data: PasswordReset,
    current_user: User = Depends(get_current_active_user)
):
    """
    重置用户密码（管理员操作）

    不需要旧密码，直接设置新密码
    """
    auth_service = AuthService()

    try:
        await auth_service.reset_password(
            user_id=user_id,
            new_password=data.new_password,
            operator_id=current_user.id
        )
        return {"message": "密码重置成功"}
    except AuthException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post(
    "/{user_id}/lock",
    response_model=User,
    summary="锁定用户",
    dependencies=[Depends(require_permissions("user:update"))]
)
async def lock_user(
    user_id: str,  # MongoDB 使用字符串ID
    reason: str = Query(..., description="锁定原因"),
    current_user: User = Depends(get_current_active_user)
):
    """锁定用户账户"""
    # 不能锁定自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "USER_004", "message": "不能锁定自己"}
        )

    user_service = UserService()
    user = await user_service.lock_user(user_id, reason)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_003", "message": "用户不存在"}
        )

    return user


@router.post(
    "/{user_id}/unlock",
    response_model=User,
    summary="解锁用户",
    dependencies=[Depends(require_permissions("user:update"))]
)
async def unlock_user(
    user_id: str  # MongoDB 使用字符串ID
):
    """解锁用户账户"""
    user_service = UserService()
    user = await user_service.unlock_user(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_003", "message": "用户不存在"}
        )

    return user


@router.put(
    "/{user_id}/roles",
    response_model=User,
    summary="分配用户角色",
    dependencies=[Depends(require_permissions("role:assign"))]
)
async def assign_user_roles(
    user_id: str,  # MongoDB 使用字符串ID
    data: RoleAssign,
    current_user: User = Depends(get_current_active_user)
):
    """
    分配角色给用户

    - 支持同时分配多个角色
    - 会替换用户现有的所有角色
    """
    user_service = UserService()

    try:
        user = await user_service.assign_roles(
            user_id=user_id,
            role_codes=data.role_codes,
            operator_id=current_user.id
        )
        return user
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post(
    "/{user_id}/roles/{role_code}",
    response_model=User,
    summary="给用户添加角色",
    dependencies=[Depends(require_permissions("role:assign"))]
)
async def add_user_role(
    user_id: str,  # MongoDB 使用字符串ID
    role_code: str,
    current_user: User = Depends(get_current_active_user)
):
    """给用户添加一个角色（不影响现有角色）"""
    user_service = UserService()

    try:
        user = await user_service.add_role(
            user_id=user_id,
            role_code=role_code,
            operator_id=current_user.id
        )
        return user
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.delete(
    "/{user_id}/roles/{role_code}",
    response_model=User,
    summary="移除用户角色",
    dependencies=[Depends(require_permissions("role:assign"))]
)
async def remove_user_role(
    user_id: str,  # MongoDB 使用字符串ID
    role_code: str
):
    """移除用户的一个角色"""
    user_service = UserService()

    try:
        user = await user_service.remove_role(user_id, role_code)
        return user
    except UserServiceException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )
