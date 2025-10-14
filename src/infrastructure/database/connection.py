"""数据库连接管理"""

import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# MongoDB 连接
_mongodb_client: Optional[AsyncIOMotorClient] = None
_mongodb_database: Optional[AsyncIOMotorDatabase] = None

# MariaDB 连接
_mariadb_engine = None
_mariadb_session_factory: Optional[async_sessionmaker] = None


async def get_mongodb_database() -> AsyncIOMotorDatabase:
    """获取MongoDB数据库连接"""
    global _mongodb_client, _mongodb_database
    
    if _mongodb_database is None:
        try:
            _mongodb_client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=5000  # 5秒超时
            )
            _mongodb_database = _mongodb_client[settings.MONGODB_DB_NAME]
            
            # 测试连接（使用超时）
            await asyncio.wait_for(_mongodb_client.admin.command('ping'), timeout=5.0)
            logger.info(f"MongoDB连接成功: {settings.MONGODB_DB_NAME}")
            
        except asyncio.TimeoutError:
            logger.warning("MongoDB连接超时，可能服务未启动")
            raise ConnectionError("MongoDB连接超时")
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
    
    return _mongodb_database


async def get_mariadb_session() -> AsyncSession:
    """获取MariaDB会话"""
    global _mariadb_engine, _mariadb_session_factory
    
    if _mariadb_session_factory is None:
        try:
            _mariadb_engine = create_async_engine(
                settings.MARIADB_URL,
                pool_size=settings.MARIADB_POOL_SIZE,
                max_overflow=settings.MARIADB_MAX_OVERFLOW,
                pool_timeout=settings.MARIADB_POOL_TIMEOUT,
                echo=settings.DEBUG
            )
            _mariadb_session_factory = async_sessionmaker(
                _mariadb_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("MariaDB连接池创建成功")
            
        except Exception as e:
            logger.error(f"MariaDB连接失败: {e}")
            raise
    
    return _mariadb_session_factory()


async def get_database_connection():
    """根据配置获取数据库连接（默认使用MongoDB）"""
    return await get_mongodb_database()


async def close_database_connections():
    """关闭所有数据库连接"""
    global _mongodb_client, _mariadb_engine
    
    if _mongodb_client:
        _mongodb_client.close()
        logger.info("MongoDB连接已关闭")
    
    if _mariadb_engine:
        await _mariadb_engine.dispose()
        logger.info("MariaDB连接已关闭")


# 数据库启动和关闭事件
async def init_database():
    """初始化数据库连接"""
    try:
        # 初始化MongoDB连接
        await get_mongodb_database()
        
        # 创建必要的索引
        await create_indexes()
        
        logger.info("数据库初始化完成")
    except (ConnectionError, asyncio.TimeoutError):
        logger.warning("数据库连接失败，将使用内存存储模式（仅用于开发测试）")
        # 可以在这里设置一个全局标志来切换到内存模式
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        logger.warning("将继续使用内存存储模式")
        # 不抛出异常，让应用继续启动


async def create_indexes():
    """创建数据库索引"""
    try:
        db = await get_mongodb_database()
        
        # 搜索任务索引
        search_tasks = db.search_tasks
        await search_tasks.create_index("created_by")
        await search_tasks.create_index("status")
        await search_tasks.create_index("is_active")
        await search_tasks.create_index("schedule_interval")
        await search_tasks.create_index("next_run_time")
        await search_tasks.create_index("created_at")
        
        # 搜索结果索引
        search_results = db.search_results
        await search_results.create_index("task_id")
        await search_results.create_index("execution_time")
        await search_results.create_index([("task_id", 1), ("execution_time", -1)])
        
        logger.info("数据库索引创建完成")
        
    except Exception as e:
        logger.warning(f"创建索引失败: {e}")