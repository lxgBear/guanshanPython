"""
API v1 路由配置
"""
from fastapi import APIRouter
from src.api.v1.endpoints import crawl

# 创建主路由器
api_router = APIRouter()

# 注册各个模块的路由
api_router.include_router(
    crawl.router,
    prefix="/crawl",
    tags=["爬取服务"]
)