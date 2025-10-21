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

    # 关闭Redis连接
    try:
        from src.infrastructure.cache import redis_client
        await redis_client.close()
    except Exception as e:
        logger.warning(f"Redis关闭失败: {e}")


# 数据库启动和关闭事件
async def init_database():
    """初始化数据库连接"""
    try:
        # 初始化MongoDB连接
        await get_mongodb_database()

        # 创建必要的索引
        await create_indexes()

        # 初始化Redis连接（可选）
        try:
            from src.infrastructure.cache import redis_client
            await redis_client.connect()
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}. 将使用无缓存模式")

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

        # 定时搜索任务索引
        search_tasks = db.search_tasks
        await search_tasks.create_index("created_by")
        await search_tasks.create_index("status")
        await search_tasks.create_index("is_active")
        await search_tasks.create_index("schedule_interval")
        await search_tasks.create_index("next_run_time")
        await search_tasks.create_index("created_at")

        # 定时搜索结果索引
        search_results = db.search_results
        await search_results.create_index("task_id")
        await search_results.create_index("execution_time")
        await search_results.create_index([("task_id", 1), ("execution_time", -1)])

        # ==================== v1.3.0 即时搜索索引 ====================

        # 即时搜索任务索引
        instant_search_tasks = db.instant_search_tasks
        await instant_search_tasks.create_index("created_by")
        await instant_search_tasks.create_index("status")
        await instant_search_tasks.create_index("search_execution_id")
        await instant_search_tasks.create_index("created_at")
        logger.info("✅ 即时搜索任务索引创建完成")

        # 即时搜索结果索引（v1.3.0核心）
        instant_search_results = db.instant_search_results
        await instant_search_results.create_index("content_hash", unique=True)  # 去重键（唯一）
        await instant_search_results.create_index("task_id")
        await instant_search_results.create_index("url_normalized")
        await instant_search_results.create_index("first_found_at")
        await instant_search_results.create_index("last_found_at")
        logger.info("✅ 即时搜索结果索引创建完成（含content_hash唯一索引）")

        # 即时搜索映射索引（v1.3.0核心）
        instant_search_mappings = db.instant_search_result_mappings
        # 最常用：按搜索执行ID查询结果，按排名排序
        await instant_search_mappings.create_index([("search_execution_id", 1), ("search_position", 1)])
        # 反向查询：查询哪些搜索发现了该结果
        await instant_search_mappings.create_index("result_id")
        # 按任务查询所有映射
        await instant_search_mappings.create_index("task_id")
        # 唯一约束：同一搜索不能重复关联同一结果
        await instant_search_mappings.create_index(
            [("search_execution_id", 1), ("result_id", 1)],
            unique=True
        )
        logger.info("✅ 即时搜索映射索引创建完成（含唯一约束）")

        logger.info("✅ 数据库索引创建完成（含v1.3.0即时搜索索引）")

        # ==================== 智能总结报告系统索引 ====================

        # 1. summary_reports - 总结报告主表
        summary_reports = db.summary_reports
        # 基础索引
        await summary_reports.create_index("report_id", unique=True, name="idx_report_id")
        await summary_reports.create_index("created_by", name="idx_created_by")
        await summary_reports.create_index("status", name="idx_status")
        await summary_reports.create_index("created_at", name="idx_created_at")
        await summary_reports.create_index("updated_at", name="idx_updated_at")
        # 复合索引（常用查询组合）
        await summary_reports.create_index(
            [("created_by", 1), ("status", 1), ("created_at", -1)],
            name="idx_created_status_time"
        )
        logger.info("✅ 总结报告主表索引创建完成")

        # 2. summary_report_tasks - 报告任务关联表
        summary_report_tasks = db.summary_report_tasks
        # 基础索引
        await summary_report_tasks.create_index("association_id", unique=True, name="idx_association_id")
        await summary_report_tasks.create_index("report_id", name="idx_report_id")
        await summary_report_tasks.create_index("task_id", name="idx_task_id")
        # 复合索引（联表查询核心优化）
        await summary_report_tasks.create_index(
            [("report_id", 1), ("task_type", 1), ("task_id", 1)],
            name="idx_report_task_lookup"
        )
        # 优先级排序索引
        await summary_report_tasks.create_index(
            [("report_id", 1), ("is_active", 1), ("priority", -1)],
            name="idx_report_active_priority"
        )
        # 唯一约束：同一报告不能重复关联同一任务
        await summary_report_tasks.create_index(
            [("report_id", 1), ("task_id", 1), ("task_type", 1)],
            unique=True,
            name="idx_unique_report_task"
        )
        # 部分索引：只为活跃任务创建
        await summary_report_tasks.create_index(
            [("report_id", 1), ("task_id", 1)],
            partialFilterExpression={"is_active": True},
            name="idx_active_tasks_only"
        )
        logger.info("✅ 报告任务关联表索引创建完成（含性能优化索引）")

        # 3. summary_report_data_items - 报告数据项表
        summary_report_data_items = db.summary_report_data_items
        # 基础索引
        await summary_report_data_items.create_index("item_id", unique=True, name="idx_item_id")
        await summary_report_data_items.create_index("report_id", name="idx_report_id")
        await summary_report_data_items.create_index("source_task_id", name="idx_source_task")
        # 复合索引（常用查询）
        await summary_report_data_items.create_index(
            [("report_id", 1), ("is_visible", 1), ("display_order", 1)],
            name="idx_report_visible_order"
        )
        # 覆盖索引（只返回基础字段的查询）
        await summary_report_data_items.create_index(
            [("report_id", 1), ("item_id", 1), ("title", 1), ("source_task_id", 1)],
            name="idx_report_item_covered"
        )
        # 部分索引：只为可见数据项创建
        await summary_report_data_items.create_index(
            [("report_id", 1), ("added_at", -1)],
            partialFilterExpression={"is_visible": True},
            name="idx_visible_items_only"
        )
        # 全文搜索索引（带权重优化）
        await summary_report_data_items.create_index(
            [("title", "text"), ("content", "text"), ("tags", "text")],
            weights={"title": 10, "tags": 5, "content": 1},
            name="idx_fulltext_weighted"
        )
        logger.info("✅ 报告数据项表索引创建完成（含全文搜索优化索引）")

        # 4. summary_report_versions - 报告版本历史表
        summary_report_versions = db.summary_report_versions
        # 基础索引
        await summary_report_versions.create_index("version_id", unique=True, name="idx_version_id")
        # 复合索引（版本查询）
        await summary_report_versions.create_index(
            [("report_id", 1), ("version_number", -1)],
            name="idx_report_version"
        )
        logger.info("✅ 报告版本历史表索引创建完成")

        # 5. search_results 和 instant_search_results 的联表查询索引优化
        # 为联表查询优化外键索引
        search_results_extra = db.search_results
        await search_results_extra.create_index(
            [("task_id", 1), ("created_at", -1)],
            name="idx_task_created",
            background=True  # 后台创建，不阻塞
        )

        instant_search_results_extra = db.instant_search_results
        await instant_search_results_extra.create_index(
            [("execution_id", 1), ("created_at", -1)],
            name="idx_execution_created",
            background=True  # 后台创建，不阻塞
        )
        logger.info("✅ 联表查询外键索引优化完成")

        logger.info("✅ 智能总结报告系统所有索引创建完成")

    except Exception as e:
        logger.warning(f"创建索引失败: {e}")