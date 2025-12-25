"""
权限配置模块 - 路由级权限映射

混合权限架构:
- Layer 1: 全局认证（JWT验证）
- Layer 2: 路由级权限（本文件配置）
- Layer 3: 端点级权限（在各endpoint文件中单独配置）
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class AccessLevel(str, Enum):
    """访问级别枚举"""
    PUBLIC = "public"           # 公开访问，无需认证
    AUTHENTICATED = "authenticated"  # 需要登录，无特定权限
    PERMISSION = "permission"   # 需要特定权限
    ROLE = "role"               # 需要特定角色


@dataclass
class RoutePermission:
    """路由权限配置"""
    access_level: AccessLevel
    permissions: List[str] = None  # 所需权限（任一满足即可）
    roles: List[str] = None        # 所需角色（任一满足即可）
    require_all: bool = False      # 是否需要满足所有权限
    description: str = ""          # 描述说明


# ==========================================
# 公开路由白名单（无需认证）
# ==========================================
PUBLIC_ROUTES = [
    # 认证相关
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",

    # API文档
    "/docs",
    "/redoc",
    "/openapi.json",

    # 健康检查
    "/health",
    "/",

    # Firecrawl 工具（定价信息等公开）
    "/api/v1/firecrawl",
]


# ==========================================
# 路由级权限配置
# ==========================================
ROUTE_PERMISSIONS: Dict[str, RoutePermission] = {
    # ------------------------------------------
    # 认证与权限管理 (已有完整端点级权限)
    # ------------------------------------------
    "/api/v1/auth": RoutePermission(
        access_level=AccessLevel.AUTHENTICATED,
        description="认证相关接口，需要登录"
    ),

    # ------------------------------------------
    # 网页爬取服务
    # ------------------------------------------
    "/api/v1/crawl": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:create"],
        description="网页爬取需要信息采集权限"
    ),

    # ------------------------------------------
    # 搜索任务管理（通用搜索）
    # ------------------------------------------
    "/api/v1/search-tasks": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:basic", "search:advanced"],
        description="搜索任务管理需要搜索权限"
    ),

    # ------------------------------------------
    # 搜索结果查询
    # ------------------------------------------
    "/api/v1/search-results": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:basic", "search:advanced"],
        description="搜索结果查询需要搜索权限"
    ),

    # ------------------------------------------
    # 调度器管理
    # ------------------------------------------
    "/api/v1/scheduler": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["system:config"],
        description="调度器管理需要系统配置权限"
    ),

    # ------------------------------------------
    # 即时搜索
    # ------------------------------------------
    "/api/v1/instant-search": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:basic"],
        description="即时搜索需要基础搜索权限"
    ),

    # ------------------------------------------
    # 智能搜索（LLM分解）
    # ------------------------------------------
    "/api/v1/smart-search": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:advanced"],
        description="智能搜索需要高级搜索权限"
    ),

    # ------------------------------------------
    # 智能总结报告
    # ------------------------------------------
    "/api/v1/summary-reports": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:advanced", "info:read"],
        description="总结报告需要高级搜索或信息读取权限"
    ),

    # ------------------------------------------
    # 数据源管理
    # ------------------------------------------
    "/api/v1/data-sources": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:create", "info:update"],
        description="数据源管理需要信息管理权限"
    ),

    # ------------------------------------------
    # 自然语言搜索 (NL Search)
    # ------------------------------------------
    "/api/v1/nl-search": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:multilang"],
        description="NL搜索需要多语言搜索权限"
    ),

    # ------------------------------------------
    # 用户批量编辑
    # ------------------------------------------
    "/api/v1/user-edits": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:update"],
        description="用户编辑需要信息更新权限"
    ),

    # ------------------------------------------
    # Chat接口
    # ------------------------------------------
    "/api/v1/chat": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["search:basic", "search:multilang"],
        description="Chat接口需要搜索权限"
    ),

    # ------------------------------------------
    # 文件上传管理
    # ------------------------------------------
    "/api/v1/upload": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:create"],
        description="文件上传需要信息创建权限"
    ),

    # ------------------------------------------
    # 系统内部接口
    # ------------------------------------------
    "/api/v1/internal": RoutePermission(
        access_level=AccessLevel.ROLE,
        roles=["admin"],
        description="内部接口仅管理员可访问"
    ),
}


# ==========================================
# 端点级权限覆盖配置
# 这些配置会覆盖路由级配置，用于需要更严格权限的端点
# ==========================================
ENDPOINT_PERMISSIONS: Dict[str, RoutePermission] = {
    # 搜索任务 - 删除操作需要更高权限
    "DELETE /api/v1/search-tasks/{task_id}": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:delete"],
        description="删除搜索任务需要删除权限"
    ),

    # 数据源 - 删除操作需要更高权限
    "DELETE /api/v1/data-sources/{source_id}": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["info:delete"],
        description="删除数据源需要删除权限"
    ),

    # 调度器 - 启动/停止需要执行权限
    "POST /api/v1/scheduler/start": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["system:config"],
        description="启动调度器需要系统配置权限"
    ),

    "POST /api/v1/scheduler/stop": RoutePermission(
        access_level=AccessLevel.PERMISSION,
        permissions=["system:config"],
        description="停止调度器需要系统配置权限"
    ),
}


def get_route_permission(path: str) -> Optional[RoutePermission]:
    """
    获取路由权限配置

    Args:
        path: 请求路径

    Returns:
        RoutePermission 或 None
    """
    # 精确匹配
    if path in ROUTE_PERMISSIONS:
        return ROUTE_PERMISSIONS[path]

    # 前缀匹配
    for route_prefix, permission in ROUTE_PERMISSIONS.items():
        if path.startswith(route_prefix):
            return permission

    return None


def is_public_route(path: str) -> bool:
    """
    检查是否为公开路由

    Args:
        path: 请求路径

    Returns:
        是否公开
    """
    for public_route in PUBLIC_ROUTES:
        if path == public_route or path.startswith(public_route):
            return True
    return False


def get_endpoint_permission(method: str, path: str) -> Optional[RoutePermission]:
    """
    获取端点级权限配置（用于覆盖路由级）

    Args:
        method: HTTP方法
        path: 请求路径

    Returns:
        RoutePermission 或 None
    """
    key = f"{method} {path}"
    return ENDPOINT_PERMISSIONS.get(key)
