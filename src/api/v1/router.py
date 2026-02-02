"""
API v1 路由配置

混合权限架构:
- Layer 1: 路由级权限 - 在 include_router 中通过 dependencies 配置
- Layer 2: 端点级权限 - 在各 endpoint 文件中单独配置（用于更细粒度控制）

前端API：只包含前端需要的接口，暴露在API文档中
内部API：系统管理接口，隐藏在API文档中
"""
from fastapi import APIRouter, Depends
from src.api.v1.endpoints import crawl
from src.api.v1.endpoints import search_tasks_frontend, search_results_frontend, internal_api, scheduler_management
from src.api.v1.endpoints import instant_search
from src.api.v1.endpoints import smart_search
from src.api.v1.endpoints import summary_report_management
from src.api.v1.endpoints import data_source_management
from src.api.v1.endpoints import firecrawl_utils
from src.api.v1.endpoints import nl_search
from src.api.v1.endpoints import user_edits
from src.api.v1.endpoints import chat
from src.api.v1.endpoints import chat_v2  # V2 层分离架构
from src.api.v1.endpoints import upload
from src.api.v1.endpoints import review
from src.api.v1.endpoints import langgraph_transfer
from src.api.v1.endpoints import category_management
from src.api.v1.endpoints import search_results_manual  # v2.2.0 手动添加数据
from src.api.v1.endpoints import unified_results  # v4.24.0 统一聚合结果
from src.api.v1.endpoints import info_entries  # v4.25.0 信息条目管理
from src.api.v1.endpoints import review_entries  # v4.29.0 审核条目管理
from src.api.v1.endpoints import published_entries  # 发布条目管理
from src.api.v1.endpoints import review_flow  # v2.8.0 审批流程
from src.api.v1.endpoints import map_detail  # Map + Detail 详情页爬取
from src.api.v1.endpoints.auth import router as auth_router

# 权限依赖
from src.api.dependencies.auth import (
    get_current_active_user,
    require_permissions,
    require_roles
)

# 创建主路由器
api_router = APIRouter()

# ==========================================
# 认证与权限API (公开 + 已认证)
# ==========================================

# 用户认证与权限管理
# 注意：auth 模块内部有更细粒度的权限控制
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["🔐 认证与权限"]
)

# ==========================================
# 前端API - 需要权限控制
# ==========================================

# 爬取服务 - 需要 info:create 权限
api_router.include_router(
    crawl.router,
    prefix="/crawl",
    tags=["🌐 网页爬取服务"],
    dependencies=[Depends(require_permissions("info:create"))]
)

# 搜索任务管理 - 需要 search:basic 或 search:advanced 权限
api_router.include_router(
    search_tasks_frontend.router,
    tags=["🔍 搜索任务管理 (通用搜索)"],
    dependencies=[Depends(require_permissions("search:basic", "search:advanced"))]
)

# 搜索结果查询 - 需要 search:basic 或 search:advanced 权限
api_router.include_router(
    search_results_frontend.router,
    tags=["📊 搜索结果查询 (通用搜索)"],
    dependencies=[Depends(require_permissions("search:basic", "search:advanced"))]
)

# 手动添加数据 - 需要 info:create 权限 (v2.2.0)
api_router.include_router(
    search_results_manual.router,
    tags=["📝 手动添加数据"],
    dependencies=[Depends(require_permissions("info:create", "search:basic"))]
)

# 调度器管理 - 需要 system:config 权限
api_router.include_router(
    scheduler_management.router,
    tags=["📊 调度器管理"],
    dependencies=[Depends(require_permissions("system:config"))]
)

# 即时搜索 - 需要 search:basic 权限
api_router.include_router(
    instant_search.router,
    tags=["⚡ 即时搜索"],
    dependencies=[Depends(require_permissions("search:basic", "search:advanced"))]
)

# 智能搜索 - 需要 search:advanced 权限
api_router.include_router(
    smart_search.router,
    tags=["🧠 智能搜索（LLM分解）"],
    dependencies=[Depends(require_permissions("search:advanced"))]
)

# 智能总结报告 - 需要 search:advanced 或 info:read 权限
api_router.include_router(
    summary_report_management.router,
    tags=["📝 智能总结报告"],
    dependencies=[Depends(require_permissions("search:advanced", "info:read"))]
)

# 数据源管理 - 需要 info:create 或 info:update 权限
api_router.include_router(
    data_source_management.router,
    tags=["📦 数据源管理"],
    dependencies=[Depends(require_permissions("info:create", "info:update"))]
)

# Firecrawl 工具 - 公开接口（积分估算和定价信息）
api_router.include_router(
    firecrawl_utils.router,
    tags=["💰 Firecrawl 工具"]
    # 无 dependencies，公开访问
)

# 自然语言搜索 - 需要 search:multilang 权限
api_router.include_router(
    nl_search.router,
    prefix="/nl-search",
    tags=["🤖 自然语言搜索 (NL Search - Beta)"],
    dependencies=[Depends(require_permissions("search:multilang", "search:basic"))]
)

# 用户批量编辑 - 需要 info:update 权限
api_router.include_router(
    user_edits.router,
    tags=["✏️ 用户批量编辑"],
    dependencies=[Depends(require_permissions("info:update"))]
)

# Chat接口 - 需要 search:basic 或 search:multilang 权限
api_router.include_router(
    chat.router,
    tags=["💬 Chat接口"],
    dependencies=[Depends(require_permissions("search:basic", "search:multilang"))]
)

# Chat V2 接口（层分离架构） - 需要 search:basic 或 search:multilang 权限
api_router.include_router(
    chat_v2.router,
    prefix="/chat/v2",
    tags=["💬 Chat V2 (层分离架构)"],
    dependencies=[Depends(require_permissions("search:basic", "search:multilang"))]
)

# 文件上传管理 - 需要 info:create 权限
api_router.include_router(
    upload.router,
    tags=["📁 文件上传管理"],
    dependencies=[Depends(require_permissions("info:create"))]
)

# 档案审核管理 - 需要 archive:review 或 archive:update 权限
api_router.include_router(
    review.router,
    tags=["📋 档案审核管理"],
    dependencies=[Depends(require_permissions("archive:review", "archive:update", "search:basic"))]
)

# LangGraph 转移管理 - 需要 langgraph:transfer 权限
api_router.include_router(
    langgraph_transfer.router,
    tags=["🔄 LangGraph 转移管理"],
    dependencies=[Depends(require_permissions("langgraph:transfer", "info:create"))]
)

# 分类体系管理 - 需要 info:update 或 system:config 权限
api_router.include_router(
    category_management.router,
    tags=["📂 分类体系管理"],
    dependencies=[Depends(require_permissions("info:update", "system:config"))]
)

# 统一聚合结果 - 需要 search:basic 权限 (v4.24.0)
api_router.include_router(
    unified_results.router,
    tags=["📊 统一聚合结果"],
    dependencies=[Depends(require_permissions("search:basic", "search:advanced"))]
)

# 信息条目管理 - 需要 info:create 或 info:read 权限 (v4.25.0)
api_router.include_router(
    info_entries.router,
    tags=["📝 信息条目"],
    dependencies=[Depends(require_permissions("info:create", "info:read"))]
)

# 审核条目管理 - 需要 info:create 或 archive:review 权限 (v4.29.0)
api_router.include_router(
    review_entries.router,
    tags=["📋 审核条目"],
    dependencies=[Depends(require_permissions("info:create", "archive:review"))]
)

# 发布条目管理 - 需要 info:read 或 review:approve 权限
api_router.include_router(
    published_entries.router,
    tags=["📢 发布条目"],
    dependencies=[Depends(require_permissions("info:read", "review:approve"))]
)

# 审批流程管理 - 需要登录即可访问基本功能 (v2.8.0)
api_router.include_router(
    review_flow.router,
    tags=["🔄 审批流程"],
    dependencies=[Depends(get_current_active_user)]
)

# Map + Detail 详情页爬取 - 需要 info:create 权限
api_router.include_router(
    map_detail.router,
    tags=["🗺️ Map + Detail 详情页爬取"],
    dependencies=[Depends(require_permissions("info:create", "search:basic"))]
)

# ==========================================
# 内部API - 仅管理员可访问
# ==========================================

# 系统内部接口（手动执行、系统状态等）
api_router.include_router(
    internal_api.router,
    tags=["🔧 系统内部接口"],
    dependencies=[Depends(require_roles("admin"))]
)
