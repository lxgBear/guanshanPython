"""
API v1 路由配置

前端API：只包含前端需要的接口，暴露在API文档中
内部API：系统管理接口，隐藏在API文档中
"""
from fastapi import APIRouter
from src.api.v1.endpoints import crawl
from src.api.v1.endpoints import search_tasks_frontend, search_results_frontend, internal_api, scheduler_management
from src.api.v1.endpoints import instant_search
from src.api.v1.endpoints import summary_report_management

# 创建主路由器
api_router = APIRouter()

# ==========================================
# 前端API - 暴露在API文档中
# ==========================================

# 爬取服务（保留原有功能）
api_router.include_router(
    crawl.router,
    prefix="/crawl",
    tags=["🌐 网页爬取服务"]
)

# 搜索任务管理（前端优化版）
api_router.include_router(
    search_tasks_frontend.router,
    tags=["🔍 搜索任务管理"]
)

# 搜索结果查询（前端优化版，作为任务子资源）
api_router.include_router(
    search_results_frontend.router,
    tags=["📊 搜索结果查询"]
)

# 调度器管理
api_router.include_router(
    scheduler_management.router,
    tags=["📊 调度器管理"]
)

# 即时搜索（v1.3.0新增）
api_router.include_router(
    instant_search.router,
    tags=["⚡ 即时搜索"]
)

# 智能总结报告系统
api_router.include_router(
    summary_report_management.router,
    tags=["📝 智能总结报告"]
)

# ==========================================
# 内部API - 隐藏在API文档中
# ==========================================

# 系统内部接口（手动执行、系统状态等）
api_router.include_router(
    internal_api.router,
    tags=["🔧 系统内部接口"]
)