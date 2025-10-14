"""
FastAPI应用主入口
关山智能系统API服务
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.utils.logger import get_logger
from src.api.v1.router import api_router
from src.infrastructure.database.connection import init_database, close_database_connections
from src.services.task_scheduler import start_scheduler, stop_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用生命周期管理
    处理启动和关闭时的初始化和清理工作
    """
    # 启动时初始化
    logger.info("🚀 启动关山智能系统...")
    
    try:
        # 初始化数据库连接（允许失败）
        await init_database()
        logger.info("✅ 数据库连接初始化成功")

        # 启动定时任务调度器
        try:
            await start_scheduler()
            logger.info("✅ 定时任务调度器启动成功")
        except Exception as e:
            logger.warning(f"⚠️ 定时任务调度器启动失败: {e}")

        # TODO: 初始化缓存
        # await init_redis()

        # TODO: 初始化消息队列
        # await init_rabbitmq()

        logger.info("✅ 系统启动成功")

    except Exception as e:
        logger.warning(f"⚠️ 部分组件初始化失败: {str(e)}")
        logger.info("✅ 系统启动成功（降级模式）")
    
    yield
    
    # 关闭时清理
    logger.info("🛑 正在关闭系统...")
    
    try:
        # 停止定时任务调度器
        try:
            await stop_scheduler()
            logger.info("✅ 定时任务调度器已停止")
        except Exception as e:
            logger.warning(f"⚠️ 停止调度器时出错: {e}")

        # 关闭数据库连接
        await close_database_connections()
        logger.info("✅ 数据库连接已关闭")

        # TODO: 关闭缓存连接
        # await close_redis()

        # TODO: 关闭消息队列
        # await close_rabbitmq()

        logger.info("✅ 系统已安全关闭")

    except Exception as e:
        logger.error(f"⚠️ 关闭时出现错误: {str(e)}")


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例
    
    Returns:
        FastAPI: 配置好的应用实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="基于Firecrawl + LLM + RAG Pipeline的智能信息采集与处理平台",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
    )
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(api_router, prefix="/api/v1")
    
    # 健康检查端点
    @app.get("/health")
    async def health_check():
        """健康检查端点"""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG
        }
    
    # 根路径
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "message": f"欢迎使用{settings.APP_NAME}",
            "version": settings.VERSION,
            "docs": "/api/docs" if settings.DEBUG else "文档已禁用"
        }
    
    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """全局异常处理器"""
        logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "服务器内部错误",
                "message": str(exc) if settings.DEBUG else "请联系管理员"
            }
        )
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    """
    直接运行时启动开发服务器
    生产环境应使用: uvicorn src.main:app
    """
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=1 if settings.DEBUG else settings.WORKERS,
    )