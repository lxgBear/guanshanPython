"""权限领域实体"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import re


class PermissionModule(str, Enum):
    """权限模块枚举"""
    USER = "user"
    ROLE = "role"
    INFO = "info"
    REVIEW = "review"
    SEARCH = "search"
    SYSTEM = "system"
    ARCHIVE = "archive"  # v2.7.0: 档案管理模块
    # v2.8.0: 新增权限模块
    PAGE = "page"        # 页面权限
    BUTTON = "button"    # 按钮权限
    WORKFLOW = "workflow"  # 审批流程


class PermissionAction(str, Enum):
    """权限操作枚举"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    ASSIGN = "assign"
    EXECUTE = "execute"
    APPROVE = "approve"
    CONFIG = "config"
    # v2.8.0: 新增操作类型
    FINAL = "final"        # 终审操作
    VIEW = "view"          # 查看操作（用于页面）
    SUBMIT = "submit"      # 提交操作


class PermissionCode(str, Enum):
    """预定义权限代码"""
    # 用户管理
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"

    # 角色管理
    ROLE_CREATE = "role:create"
    ROLE_READ = "role:read"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_ASSIGN = "role:assign"

    # 信息采集
    INFO_CREATE = "info:create"
    INFO_READ = "info:read"
    INFO_UPDATE = "info:update"
    INFO_DELETE = "info:delete"

    # 校审管理
    REVIEW_ASSIGN = "review:assign"
    REVIEW_EXECUTE = "review:execute"
    REVIEW_APPROVE = "review:approve"
    REVIEW_READ = "review:read"

    # NL搜索
    SEARCH_BASIC = "search:basic"
    SEARCH_ADVANCED = "search:advanced"
    SEARCH_MULTILANG = "search:multilang"

    # 系统管理
    SYSTEM_CONFIG = "system:config"
    SYSTEM_LOG = "system:log"
    SYSTEM_API = "system:api"

    # v2.7.0: 档案管理
    ARCHIVE_CREATE = "archive:create"      # 创建档案
    ARCHIVE_READ = "archive:read"          # 读取档案（自己的+已审核的）
    ARCHIVE_UPDATE = "archive:update"      # 更新档案
    ARCHIVE_DELETE = "archive:delete"      # 删除档案
    ARCHIVE_REVIEW = "archive:review"      # 审核档案（通过/驳回）
    ARCHIVE_READ_ALL = "archive:read_all"  # 读取所有状态档案（含待审核）

    # v2.8.0: 审批流程权限
    REVIEW_APPROVE_FINAL = "review:approve_final"  # 终审权限（可直接结束流程）
    WORKFLOW_CREATE = "workflow:create"    # 创建审批流程
    WORKFLOW_READ = "workflow:read"        # 查看审批流程
    WORKFLOW_UPDATE = "workflow:update"    # 修改审批流程
    WORKFLOW_DELETE = "workflow:delete"    # 删除审批流程

    # v2.8.0: 页面权限
    PAGE_DASHBOARD = "page:dashboard"              # 工作台
    PAGE_COLLECT = "page:collect"                  # 信息采集
    PAGE_COMPILE = "page:compile"                  # 整编页面
    PAGE_GENERATE = "page:generate"                # 信息生成
    PAGE_REVIEW_PENDING = "page:review_pending"    # 待审批列表
    PAGE_REVIEW_HISTORY = "page:review_history"    # 审批历史
    PAGE_USER_MANAGEMENT = "page:user_management"  # 用户管理
    PAGE_ROLE_PERMISSIONS = "page:role_permissions"  # 角色权限管理
    PAGE_SYSTEM_SETTINGS = "page:system_settings"  # 系统设置
    PAGE_DATA_SOURCES = "page:data_sources"        # 数据源管理
    PAGE_ARCHIVES = "page:archives"                # 档案管理

    # v2.8.0: 按钮权限
    BUTTON_EXPORT = "button:export"                # 导出
    BUTTON_BATCH_DELETE = "button:batch_delete"    # 批量删除
    BUTTON_SUBMIT_REVIEW = "button:submit_review"  # 提交审核
    BUTTON_CREATE_USER = "button:create_user"      # 创建用户
    BUTTON_RESET_PASSWORD = "button:reset_password"  # 重置密码
    BUTTON_LOCK_USER = "button:lock_user"          # 锁定用户
    BUTTON_ASSIGN_ROLE = "button:assign_role"      # 分配角色


class PermissionBase(BaseModel):
    """权限基础模型"""
    code: str = Field(..., min_length=3, max_length=100, description="权限代码")
    name: str = Field(..., min_length=2, max_length=100, description="权限名称")
    module: str = Field(..., max_length=50, description="所属模块")
    description: Optional[str] = Field(None, max_length=500, description="权限描述")

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        # v2.8.0: 支持 module:action 和 module:action_subaction 格式
        if not re.match(r'^[a-z]+:[a-z][a-z_]*$', v):
            raise ValueError('权限代码格式必须为 module:action 或 module:action_subaction')
        return v


class PermissionCreate(PermissionBase):
    """创建权限请求模型"""
    pass


class PermissionInDB(PermissionBase):
    """数据库中的权限模型"""
    id: str  # 使用字符串避免JavaScript大整数精度丢失
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class Permission(PermissionInDB):
    """权限响应模型"""
    pass


class PermissionList(BaseModel):
    """权限列表响应模型"""
    items: List[Permission]
    modules: List[str] = Field(default_factory=list, description="模块列表")


# 角色权限配置（用于初始化）
# v2.7.0: 新增档案管理权限
# v2.8.0: 新增页面权限、按钮权限、审批流程权限
DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        # 所有权限
        PermissionCode.USER_CREATE, PermissionCode.USER_READ, PermissionCode.USER_UPDATE,
        PermissionCode.USER_DELETE, PermissionCode.USER_LIST,
        PermissionCode.ROLE_CREATE, PermissionCode.ROLE_READ, PermissionCode.ROLE_UPDATE,
        PermissionCode.ROLE_DELETE, PermissionCode.ROLE_ASSIGN,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        PermissionCode.SYSTEM_CONFIG, PermissionCode.SYSTEM_LOG, PermissionCode.SYSTEM_API,
        # v2.7.0: 档案管理全部权限
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ, PermissionCode.ARCHIVE_UPDATE,
        PermissionCode.ARCHIVE_DELETE, PermissionCode.ARCHIVE_REVIEW, PermissionCode.ARCHIVE_READ_ALL,
        # v2.8.0: 审批流程权限
        PermissionCode.REVIEW_APPROVE_FINAL,
        PermissionCode.WORKFLOW_CREATE, PermissionCode.WORKFLOW_READ,
        PermissionCode.WORKFLOW_UPDATE, PermissionCode.WORKFLOW_DELETE,
        # v2.8.0: 所有页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_COLLECT, PermissionCode.PAGE_COMPILE,
        PermissionCode.PAGE_GENERATE, PermissionCode.PAGE_REVIEW_PENDING, PermissionCode.PAGE_REVIEW_HISTORY,
        PermissionCode.PAGE_USER_MANAGEMENT, PermissionCode.PAGE_ROLE_PERMISSIONS,
        PermissionCode.PAGE_SYSTEM_SETTINGS, PermissionCode.PAGE_DATA_SOURCES, PermissionCode.PAGE_ARCHIVES,
        # v2.8.0: 所有按钮权限
        PermissionCode.BUTTON_EXPORT, PermissionCode.BUTTON_BATCH_DELETE, PermissionCode.BUTTON_SUBMIT_REVIEW,
        PermissionCode.BUTTON_CREATE_USER, PermissionCode.BUTTON_RESET_PASSWORD,
        PermissionCode.BUTTON_LOCK_USER, PermissionCode.BUTTON_ASSIGN_ROLE,
    ],
    "chief_reviewer": [
        PermissionCode.USER_CREATE, PermissionCode.USER_READ, PermissionCode.USER_UPDATE,
        PermissionCode.USER_LIST, PermissionCode.ROLE_ASSIGN,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        PermissionCode.SYSTEM_LOG,
        # v2.7.0: 档案管理（含审核权限）
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ, PermissionCode.ARCHIVE_UPDATE,
        PermissionCode.ARCHIVE_DELETE, PermissionCode.ARCHIVE_REVIEW, PermissionCode.ARCHIVE_READ_ALL,
        # v2.8.0: 终审权限
        PermissionCode.REVIEW_APPROVE_FINAL,
        PermissionCode.WORKFLOW_READ,
        # v2.8.0: 页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_COLLECT, PermissionCode.PAGE_COMPILE,
        PermissionCode.PAGE_GENERATE, PermissionCode.PAGE_REVIEW_PENDING, PermissionCode.PAGE_REVIEW_HISTORY,
        PermissionCode.PAGE_USER_MANAGEMENT, PermissionCode.PAGE_DATA_SOURCES, PermissionCode.PAGE_ARCHIVES,
        # v2.8.0: 按钮权限
        PermissionCode.BUTTON_EXPORT, PermissionCode.BUTTON_BATCH_DELETE, PermissionCode.BUTTON_SUBMIT_REVIEW,
        PermissionCode.BUTTON_CREATE_USER, PermissionCode.BUTTON_RESET_PASSWORD, PermissionCode.BUTTON_LOCK_USER,
    ],
    "direction_reviewer": [
        PermissionCode.USER_READ, PermissionCode.USER_LIST,
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.INFO_DELETE,
        PermissionCode.REVIEW_ASSIGN, PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE,
        PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        # v2.7.0: 档案管理（含审核权限）
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ, PermissionCode.ARCHIVE_UPDATE,
        PermissionCode.ARCHIVE_DELETE, PermissionCode.ARCHIVE_REVIEW, PermissionCode.ARCHIVE_READ_ALL,
        # v2.8.0: 审批权限
        PermissionCode.WORKFLOW_READ,
        # v2.8.0: 页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_COLLECT, PermissionCode.PAGE_COMPILE,
        PermissionCode.PAGE_GENERATE, PermissionCode.PAGE_REVIEW_PENDING, PermissionCode.PAGE_REVIEW_HISTORY,
        PermissionCode.PAGE_DATA_SOURCES, PermissionCode.PAGE_ARCHIVES,
        # v2.8.0: 按钮权限
        PermissionCode.BUTTON_EXPORT, PermissionCode.BUTTON_SUBMIT_REVIEW,
    ],
    "reviewer": [
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.REVIEW_EXECUTE, PermissionCode.REVIEW_APPROVE, PermissionCode.REVIEW_READ,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED, PermissionCode.SEARCH_MULTILANG,
        # v2.7.0: 档案管理（含审核权限）
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ, PermissionCode.ARCHIVE_UPDATE,
        PermissionCode.ARCHIVE_REVIEW, PermissionCode.ARCHIVE_READ_ALL,
        # v2.8.0: 审批权限
        PermissionCode.WORKFLOW_READ,
        # v2.8.0: 页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_COLLECT, PermissionCode.PAGE_COMPILE,
        PermissionCode.PAGE_GENERATE, PermissionCode.PAGE_REVIEW_PENDING, PermissionCode.PAGE_REVIEW_HISTORY,
        PermissionCode.PAGE_ARCHIVES,
        # v2.8.0: 按钮权限
        PermissionCode.BUTTON_EXPORT, PermissionCode.BUTTON_SUBMIT_REVIEW,
    ],
    "collector": [
        PermissionCode.INFO_CREATE, PermissionCode.INFO_READ, PermissionCode.INFO_UPDATE,
        PermissionCode.SEARCH_BASIC, PermissionCode.SEARCH_ADVANCED,
        # v2.7.0: 档案管理（仅基本CRUD，无审核权限）
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ, PermissionCode.ARCHIVE_UPDATE,
        # v2.8.0: 页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_COLLECT, PermissionCode.PAGE_COMPILE,
        PermissionCode.PAGE_GENERATE, PermissionCode.PAGE_ARCHIVES,
        # v2.8.0: 按钮权限
        PermissionCode.BUTTON_SUBMIT_REVIEW,
    ],
    "customer": [
        PermissionCode.SEARCH_BASIC,
        # v2.7.0: 档案管理（仅创建和读取自己的）
        PermissionCode.ARCHIVE_CREATE, PermissionCode.ARCHIVE_READ,
        # v2.8.0: 页面权限
        PermissionCode.PAGE_DASHBOARD, PermissionCode.PAGE_ARCHIVES,
    ],
}
