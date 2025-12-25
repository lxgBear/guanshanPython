"""认证API端点"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.api.dependencies.auth import get_db_session, get_current_active_user
from src.services.auth import AuthService, AuthException
from src.core.domain.entities.auth import (
    User, UserLogin, TokenResponse, TokenRefresh, PasswordChange
)

router = APIRouter()


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


class RefreshResponse(BaseModel):
    """刷新Token响应"""
    access_token: str
    expires_in: int


class MessageResponse(BaseModel):
    """消息响应"""
    message: str


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(
    data: UserLogin,
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """
    用户登录

    - **username**: 用户名
    - **password**: 密码
    - **remember_me**: 是否记住登录状态
    """
    # 获取客户端信息
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    auth_service = AuthService(session)

    try:
        result = await auth_service.login(
            username=data.username,
            password=data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return result
    except AuthException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": e.message}
        )


@router.post("/logout", response_model=MessageResponse, summary="用户登出")
async def logout(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    用户登出

    需要认证
    """
    # 这里可以扩展为将 Token 加入黑名单
    return {"message": "登出成功"}


@router.post("/refresh", response_model=RefreshResponse, summary="刷新Token")
async def refresh_token(
    data: TokenRefresh,
    session: AsyncSession = Depends(get_db_session)
):
    """
    刷新访问令牌

    使用 refresh_token 获取新的 access_token
    """
    auth_service = AuthService(session)

    try:
        access_token, expires_in = await auth_service.refresh_token(data.refresh_token)
        return {"access_token": access_token, "expires_in": expires_in}
    except AuthException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": e.code, "message": e.message}
        )


@router.get("/me", response_model=User, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取当前登录用户的详细信息

    需要认证
    """
    return current_user


@router.post("/change-password", response_model=MessageResponse, summary="修改密码")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    修改当前用户密码

    需要认证，需要提供旧密码
    """
    auth_service = AuthService(session)

    try:
        await auth_service.change_password(
            user_id=current_user.id,
            old_password=data.old_password,
            new_password=data.new_password
        )
        return {"message": "密码修改成功"}
    except AuthException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )
