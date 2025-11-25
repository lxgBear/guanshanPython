"""
API v1 路由配置

前端API：只包含前端需要的接口，暴露在API文档中
内部API：系统管理接口，隐藏在API文档中
"""
from fastapi import APIRouter
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

# 搜索任务管理（前端优化版 - 通用搜索系统）
api_router.include_router(
    search_tasks_frontend.router,
    tags=["🔍 搜索任务管理 (通用搜索)"]
)

# 搜索结果查询（前端优化版 - 通用搜索系统，数据源: search_tasks → search_results）
api_router.include_router(
    search_results_frontend.router,
    tags=["📊 搜索结果查询 (通用搜索)"]
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

# 智能搜索（v2.0.0新增 - LLM查询分解）
api_router.include_router(
    smart_search.router,
    tags=["🧠 智能搜索（LLM分解）"]
)

# 智能总结报告系统
api_router.include_router(
    summary_report_management.router,
    tags=["📝 智能总结报告"]
)

# 数据源管理系统（v1.4.0新增）
api_router.include_router(
    data_source_management.router,
    tags=["📦 数据源管理"]
)

# Firecrawl 工具（积分估算和定价信息）
api_router.include_router(
    firecrawl_utils.router,
    tags=["💰 Firecrawl 工具"]
)

# 自然语言搜索（v1.0.0-beta - 独立系统，数据源: nl_search_logs → news_results）
api_router.include_router(
    nl_search.router,
    prefix="/nl-search",
    tags=["🤖 自然语言搜索 (NL Search - Beta)"]
)

# 用户批量编辑（v1.0.0新增）
api_router.include_router(
    user_edits.router,
    tags=["✏️ 用户批量编辑"]
)

# Chat接口（v1.0.0新增 - 映射到NL Search）
api_router.include_router(
    chat.router,
    tags=["💬 Chat接口"]
)

# ==========================================
# 内部API - 隐藏在API文档中
# ==========================================

# 系统内部接口（手动执行、系统状态等）
api_router.include_router(
    internal_api.router,
    tags=["🔧 系统内部接口"]
)