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
        # 检查是否配置了 MongoDB URL
        if not settings.MONGODB_URL:
            logger.warning("MONGODB_URL 未配置，使用内存存储模式")
            raise ConnectionError("MongoDB URL 未配置")

        try:
            # 检测远程MongoDB (hancens.top) 需要 TLS/SSL
            is_remote_db = 'hancens.top' in settings.MONGODB_URL

            # 构建连接参数
            connection_params = {
                'maxPoolSize': settings.MONGODB_MAX_POOL_SIZE,
                'minPoolSize': settings.MONGODB_MIN_POOL_SIZE,
                'serverSelectionTimeoutMS': 10000,  # 10秒超时（增加以适应远程网络延迟）
                'connectTimeoutMS': 10000,           # 10秒连接超时
                'socketTimeoutMS': 15000,            # 15秒查询超时（写操作可能较慢）
                'retryWrites': True,  # 启用重试
                'retryReads': True
            }

            # 远程MongoDB可能不需要SSL（Navicat的"SSL"只是UI显示）
            # 先尝试不启用SSL的直连模式
            if is_remote_db:
                # 直连模式（避免副本集自动发现导致的网络问题）
                connection_params['directConnection'] = True
                logger.info("检测到远程MongoDB，使用直连模式（无SSL）")

            _mongodb_client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                **connection_params
            )
            _mongodb_database = _mongodb_client[settings.MONGODB_DB_NAME]

            # 测试连接（使用超时）
            await asyncio.wait_for(_mongodb_client.admin.command('ping'), timeout=10.0)
            logger.info(f"MongoDB连接成功: {settings.MONGODB_DB_NAME}")

        except asyncio.TimeoutError:
            logger.warning("MongoDB连接超时，可能服务未启动")
            raise ConnectionError("MongoDB连接超时")
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise

    return _mongodb_database


async def is_mongodb_replica_set() -> bool:
    """检查MongoDB是否支持事务（replica set或mongos）

    Returns:
        bool: True表示支持事务，False表示standalone模式
    """
    try:
        client = _mongodb_client
        if client is None:
            await get_mongodb_database()
            client = _mongodb_client

        # 检查服务器信息
        server_info = await client.admin.command('isMaster')

        # replica set有setName字段，mongos有msg='isdbgrid'
        is_replica_set = 'setName' in server_info
        is_mongos = server_info.get('msg') == 'isdbgrid'

        if is_replica_set or is_mongos:
            logger.info(f"MongoDB支持事务 (replica_set={is_replica_set}, mongos={is_mongos})")
            return True
        else:
            logger.info("MongoDB standalone模式，事务功能已禁用")
            return False

    except Exception as e:
        logger.warning(f"检查MongoDB事务支持失败: {e}，默认禁用事务")
        return False


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


# 权限定义（用于同步到数据库）
PERMISSION_DEFINITIONS = {
    # 用户管理
    "user:create": {"name": "创建用户", "module": "user", "description": "创建新用户账户"},
    "user:read": {"name": "查看用户", "module": "user", "description": "查看用户信息"},
    "user:update": {"name": "更新用户", "module": "user", "description": "修改用户信息"},
    "user:delete": {"name": "删除用户", "module": "user", "description": "删除用户账户"},
    "user:list": {"name": "用户列表", "module": "user", "description": "查看用户列表"},

    # 角色管理
    "role:create": {"name": "创建角色", "module": "role", "description": "创建新角色"},
    "role:read": {"name": "查看角色", "module": "role", "description": "查看角色信息"},
    "role:update": {"name": "更新角色", "module": "role", "description": "修改角色信息"},
    "role:delete": {"name": "删除角色", "module": "role", "description": "删除角色"},
    "role:assign": {"name": "分配角色", "module": "role", "description": "为用户分配角色"},

    # 信息采集
    "info:create": {"name": "创建信息", "module": "info", "description": "创建信息条目"},
    "info:read": {"name": "查看信息", "module": "info", "description": "查看信息详情"},
    "info:update": {"name": "更新信息", "module": "info", "description": "修改信息条目"},
    "info:delete": {"name": "删除信息", "module": "info", "description": "删除信息条目"},

    # 校审管理
    "review:assign": {"name": "分配校审", "module": "review", "description": "分配校审任务"},
    "review:execute": {"name": "执行校审", "module": "review", "description": "执行校审操作"},
    "review:approve": {"name": "审批通过", "module": "review", "description": "审批通过校审"},
    "review:read": {"name": "查看校审", "module": "review", "description": "查看校审记录"},
    "review:approve_final": {"name": "终审权限", "module": "review", "description": "终审权限，可直接结束审批流程"},

    # NL搜索
    "search:basic": {"name": "基础搜索", "module": "search", "description": "使用基础搜索功能"},
    "search:advanced": {"name": "高级搜索", "module": "search", "description": "使用高级搜索功能"},
    "search:multilang": {"name": "多语言搜索", "module": "search", "description": "使用多语言搜索"},

    # 系统管理
    "system:config": {"name": "系统配置", "module": "system", "description": "修改系统配置"},
    "system:log": {"name": "系统日志", "module": "system", "description": "查看系统日志"},
    "system:api": {"name": "API管理", "module": "system", "description": "管理API配置"},

    # v2.7.0: 档案管理
    "archive:create": {"name": "创建档案", "module": "archive", "description": "创建新档案"},
    "archive:read": {"name": "读取档案", "module": "archive", "description": "读取自己的和已审核的档案"},
    "archive:update": {"name": "更新档案", "module": "archive", "description": "更新档案内容"},
    "archive:delete": {"name": "删除档案", "module": "archive", "description": "删除档案"},
    "archive:review": {"name": "审核档案", "module": "archive", "description": "审核档案（通过/驳回）"},
    "archive:read_all": {"name": "读取全部档案", "module": "archive", "description": "读取所有状态的档案（含待审核）"},

    # v2.8.0: 审批流程权限
    "workflow:create": {"name": "创建审批流程", "module": "workflow", "description": "创建新的审批流程"},
    "workflow:read": {"name": "查看审批流程", "module": "workflow", "description": "查看审批流程详情"},
    "workflow:update": {"name": "修改审批流程", "module": "workflow", "description": "修改审批流程配置"},
    "workflow:delete": {"name": "删除审批流程", "module": "workflow", "description": "删除审批流程"},

    # v2.8.0: 页面权限
    "page:dashboard": {"name": "工作台", "module": "page", "description": "访问工作台页面"},
    "page:collect": {"name": "信息采集", "module": "page", "description": "访问信息采集页面"},
    "page:compile": {"name": "整编页面", "module": "page", "description": "访问整编页面"},
    "page:generate": {"name": "信息生成", "module": "page", "description": "访问信息生成页面"},
    "page:review_pending": {"name": "待审批列表", "module": "page", "description": "访问待审批列表"},
    "page:review_history": {"name": "审批历史", "module": "page", "description": "访问审批历史页面"},
    "page:user_management": {"name": "用户管理", "module": "page", "description": "访问用户管理页面"},
    "page:role_permissions": {"name": "角色权限管理", "module": "page", "description": "访问角色权限管理页面"},
    "page:system_settings": {"name": "系统设置", "module": "page", "description": "访问系统设置页面"},
    "page:data_sources": {"name": "数据源管理", "module": "page", "description": "访问数据源管理页面"},
    "page:archives": {"name": "档案管理", "module": "page", "description": "访问档案管理页面"},

    # v2.8.0: 按钮权限
    "button:export": {"name": "导出", "module": "button", "description": "导出数据功能"},
    "button:batch_delete": {"name": "批量删除", "module": "button", "description": "批量删除数据"},
    "button:submit_review": {"name": "提交审核", "module": "button", "description": "提交内容进行审核"},
    "button:create_user": {"name": "创建用户按钮", "module": "button", "description": "创建用户按钮权限"},
    "button:reset_password": {"name": "重置密码", "module": "button", "description": "重置用户密码"},
    "button:lock_user": {"name": "锁定用户", "module": "button", "description": "锁定/解锁用户"},
    "button:assign_role": {"name": "分配角色按钮", "module": "button", "description": "分配角色按钮权限"},
}


async def sync_permissions_to_database():
    """
    同步权限定义到数据库 auth_permissions 集合
    确保所有 PermissionCode 枚举中的权限都存在于数据库中
    """
    try:
        from src.infrastructure.persistence.auth.mongodb.role_repository import MongoPermissionRepository

        permission_repo = MongoPermissionRepository()
        created_count = 0

        for code, info in PERMISSION_DEFINITIONS.items():
            # 检查权限是否已存在
            existing = await permission_repo.get_by_code(code)
            if not existing:
                # 创建新权限
                await permission_repo.create(
                    code=code,
                    name=info["name"],
                    module=info["module"],
                    description=info.get("description")
                )
                created_count += 1

        if created_count > 0:
            logger.info(f"✅ 权限同步完成，新增 {created_count} 个权限")
        else:
            logger.debug("权限数据已是最新")

    except Exception as e:
        logger.warning(f"⚠️ 权限同步失败: {e}")


# 同步默认角色权限到数据库
async def sync_default_role_permissions():
    """
    同步 DEFAULT_ROLE_PERMISSIONS 中定义的权限到数据库角色
    确保数据库中的角色拥有代码中定义的所有默认权限
    """
    try:
        from src.core.domain.entities.auth.permission import DEFAULT_ROLE_PERMISSIONS, PermissionCode
        from src.infrastructure.persistence.auth.mongodb.role_repository import MongoRoleRepository
        
        role_repo = MongoRoleRepository()
        
        for role_code, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
            # 获取数据库中的角色
            role = await role_repo.get_by_code(role_code)
            if not role:
                logger.debug(f"角色 {role_code} 不存在于数据库中，跳过权限同步")
                continue
            
            # 将 PermissionCode 枚举转换为字符串
            default_permissions = [p.value if isinstance(p, PermissionCode) else p for p in permission_codes]
            
            # 获取当前权限
            current_permissions = set(role.get("permissions", []))
            default_permissions_set = set(default_permissions)
            
            # 检查是否需要更新（只添加缺失的权限，不删除现有权限）
            missing_permissions = default_permissions_set - current_permissions
            
            if missing_permissions:
                # 合并权限：保留现有权限 + 添加缺失的默认权限
                merged_permissions = list(current_permissions | default_permissions_set)
                
                # 更新角色权限
                success = await role_repo.assign_permissions(role["_id"], merged_permissions)
                if success:
                    logger.info(f"✅ 角色 {role_code} 权限同步完成，新增 {len(missing_permissions)} 个权限")
                else:
                    logger.warning(f"⚠️ 角色 {role_code} 权限同步失败")
            else:
                logger.debug(f"角色 {role_code} 权限已是最新")
                
        logger.info("✅ 默认角色权限同步完成")
    except Exception as e:
        logger.warning(f"⚠️ 默认角色权限同步失败: {e}")
        # 不抛出异常，让应用继续启动


# 数据库启动和关闭事件
async def init_database():
    """初始化数据库连接"""
    try:
        # 初始化MongoDB连接
        await get_mongodb_database()

        # 创建必要的索引
        await create_indexes()

        # v2.8.0: 同步权限定义到数据库
        await sync_permissions_to_database()

        # 同步默认角色权限（v2.8.0）
        await sync_default_role_permissions()

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
        await search_results.create_index("status")  # v2.1.0: 状态查询优化
        # v2.1.1: 去重索引
        await search_results.create_index("content_hash")  # 内容去重查询
        await search_results.create_index([("task_id", 1), ("url", 1)])  # URL去重查询
        logger.info("✅ 定时搜索结果索引创建完成（含v2.1.1去重索引）")

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
        await instant_search_results.create_index("status")  # v2.1.0: 状态查询优化
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

        # ==================== v2.1.0 智能搜索结果索引 ====================

        # 智能搜索结果索引（基于SearchResult实体的状态管理）
        smart_search_results = db.smart_search_results
        await smart_search_results.create_index("task_id")
        await smart_search_results.create_index("status")  # v2.1.0: 状态查询优化
        await smart_search_results.create_index("created_at")
        await smart_search_results.create_index([("task_id", 1), ("status", 1)])  # 复合索引优化
        logger.info("✅ 智能搜索结果索引创建完成（含状态查询优化）")

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

        # ==================== 数据源存档系统索引 ====================

        # data_source_archived_data - 数据源存档表
        archived_data = db.data_source_archived_data

        # 基础索引
        await archived_data.create_index("data_source_id", name="idx_data_source_id")
        await archived_data.create_index("data_type", name="idx_data_type")
        await archived_data.create_index("archived_at", name="idx_archived_at")
        await archived_data.create_index("created_at", name="idx_created_at")

        # 复合索引（最常用：按数据源查询并按时间排序）
        await archived_data.create_index(
            [("data_source_id", 1), ("created_at", -1)],
            name="idx_datasource_created"
        )

        # 复合索引（按数据源和类型查询）
        await archived_data.create_index(
            [("data_source_id", 1), ("data_type", 1)],
            name="idx_datasource_type"
        )

        # 防重复存档索引（确保同一原始数据不被重复存档）
        await archived_data.create_index(
            [("original_data_id", 1), ("data_type", 1)],
            unique=True,
            name="idx_unique_original_data"
        )

        # 存档元信息索引（查询特定人员或原因的存档）
        await archived_data.create_index("archived_by", name="idx_archived_by")
        await archived_data.create_index("archived_reason", name="idx_archived_reason")

        logger.info("✅ 数据源存档系统索引创建完成（含防重复存档唯一索引）")

        # ==================== Claude Search Session 索引 (v2.1) ====================

        claude_search_sessions = db.claude_search_sessions

        # 基础索引
        await claude_search_sessions.create_index(
            [("created_at", -1)],
            name="idx_created_at_desc"
        )

        # 用户 + 创建时间复合索引（用户隔离查询优化）
        await claude_search_sessions.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_user_created"
        )

        # 查询文本索引
        await claude_search_sessions.create_index(
            [("query", "text")],
            name="idx_query_text"
        )

        # 版本索引
        await claude_search_sessions.create_index(
            [("version", 1)],
            name="idx_version"
        )

        # 来源层级索引（用于聚合查询）
        await claude_search_sessions.create_index(
            [("results.source_tier", 1)],
            name="idx_results_source_tier"
        )

        # 用户+查询复合索引（用于去重检查）
        await claude_search_sessions.create_index(
            [("user_id", 1), ("query", 1), ("created_at", -1)],
            name="idx_user_query_time"
        )

        logger.info("✅ Claude Search Session 索引创建完成（v2.1 数据库存储）")

        # ==================== LangGraph 搜索结果索引 (v4.5.2) ====================

        langgraph_search_results = db.langgraph_search_results

        # 基础索引
        await langgraph_search_results.create_index("task_id", name="idx_lg_task_id")
        await langgraph_search_results.create_index("user_id", name="idx_lg_user_id")
        await langgraph_search_results.create_index("created_by", name="idx_lg_created_by")
        await langgraph_search_results.create_index("created_at", name="idx_lg_created_at")
        await langgraph_search_results.create_index("status", name="idx_lg_status")
        # v4.6.0: conversation_id 索引（用于前端查询历史会话的搜索结果）
        await langgraph_search_results.create_index("conversation_id", name="idx_lg_conversation_id")

        # LangGraph 特定字段索引
        await langgraph_search_results.create_index("layer", name="idx_lg_layer")
        await langgraph_search_results.create_index("source_tier", name="idx_lg_source_tier")

        # v4.5.3: 数据来源分类和 AI 处理状态索引
        await langgraph_search_results.create_index("data_source_type", name="idx_lg_data_source_type")
        await langgraph_search_results.create_index("ai_processed", name="idx_lg_ai_processed")
        await langgraph_search_results.create_index("ai_processed_at", name="idx_lg_ai_processed_at")

        # 复合索引（常用查询组合）
        await langgraph_search_results.create_index(
            [("task_id", 1), ("layer", 1)],
            name="idx_lg_task_layer"
        )
        await langgraph_search_results.create_index(
            [("task_id", 1), ("created_at", -1)],
            name="idx_lg_task_created"
        )
        await langgraph_search_results.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="idx_lg_user_created"
        )

        # v4.5.3: AI 处理查询索引
        await langgraph_search_results.create_index(
            [("data_source_type", 1), ("ai_processed", 1)],
            name="idx_lg_source_ai_processed"
        )
        await langgraph_search_results.create_index(
            [("ai_processed", 1), ("created_at", -1)],
            name="idx_lg_ai_processed_created"
        )

        # 去重索引
        await langgraph_search_results.create_index(
            "content_hash",
            name="idx_lg_content_hash"
        )
        await langgraph_search_results.create_index(
            [("task_id", 1), ("url", 1)],
            name="idx_lg_task_url"
        )

        # v4.6.0: conversation_id 复合索引（用于历史会话查询）
        await langgraph_search_results.create_index(
            [("conversation_id", 1), ("created_at", -1)],
            name="idx_lg_conversation_created"
        )

        logger.info("✅ LangGraph 搜索结果索引创建完成（v4.5.2 数据隔离 + v4.5.3 AI处理状态 + v4.6.0 会话关联）")

    except Exception as e:
        logger.warning(f"创建索引失败: {e}")