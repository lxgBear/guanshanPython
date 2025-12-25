# 用户权限系统设计文档

## 1. 概述

### 1.1 项目背景
为关山系统添加完整的用户认证和权限管理功能，支持多角色、细粒度权限控制，采用模块化设计便于后期扩展和修改。

### 1.2 设计目标
- **安全性**: JWT Token 认证，密码加密存储
- **灵活性**: RBAC (基于角色的访问控制) 模型，支持动态配置权限
- **可扩展性**: 模块化架构，易于添加新角色和权限
- **可维护性**: 清晰的代码结构，符合 DDD 分层架构

### 1.3 技术栈
- **认证**: JWT (JSON Web Tokens)
- **加密**: bcrypt (密码哈希)
- **数据库**: MariaDB (用户和权限数据)
- **框架**: FastAPI + Pydantic

---

## 2. 用户角色定义

### 2.1 角色层级

```
系统管理员 (admin)
    ├── 总校审员 (chief_reviewer)
    │       ├── 方向校审员 (direction_reviewer)
    │       │       └── 校审员 (reviewer)
    │       └── 信息采集员 (collector)
    └── 客户 (customer)
```

### 2.2 角色详细定义

| 角色代码 | 角色名称 | 描述 | 权限级别 |
|---------|---------|------|---------|
| `admin` | 系统管理员 | 系统最高权限，管理所有用户和配置 | 100 |
| `chief_reviewer` | 总校审员 | 管理所有校审工作，分配任务 | 80 |
| `direction_reviewer` | 方向校审员 | 负责特定方向的校审工作 | 60 |
| `reviewer` | 校审员 | 执行具体校审任务 | 40 |
| `collector` | 信息采集员 | 采集和录入信息 | 30 |
| `customer` | 客户 | 查看和使用服务 | 20 |

### 2.3 角色属性扩展

```python
class Role:
    code: str           # 角色代码
    name: str           # 角色名称
    level: int          # 权限级别 (1-100)
    description: str    # 角色描述
    parent_role: str    # 父级角色 (用于继承)
    is_system: bool     # 是否系统内置角色
    is_active: bool     # 是否启用
```

---

## 3. 权限矩阵

### 3.1 功能模块权限

| 功能模块 | admin | chief_reviewer | direction_reviewer | reviewer | collector | customer |
|---------|:-----:|:--------------:|:------------------:|:--------:|:---------:|:--------:|
| **用户管理** |
| 创建用户 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 编辑用户 | ✅ | ✅ | ⚪ | ❌ | ❌ | ❌ |
| 删除用户 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 查看用户列表 | ✅ | ✅ | ✅ | ⚪ | ❌ | ❌ |
| **角色管理** |
| 创建角色 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 分配角色 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **信息采集** |
| 采集信息 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 编辑信息 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 删除信息 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **校审管理** |
| 分配校审任务 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 执行校审 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 审批校审结果 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **NL搜索** |
| 基础搜索 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 高级搜索 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚪ |
| 多语言搜索 | ✅ | ✅ | ✅ | ✅ | ⚪ | ❌ |
| **系统管理** |
| 系统配置 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 查看日志 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| API管理 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

> 图例: ✅ 完全权限 | ⚪ 部分权限(仅自己的数据) | ❌ 无权限

### 3.2 权限代码定义

```python
class Permission(Enum):
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
```

---

## 4. 数据库模型设计

### 4.1 ER 图

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     users       │     │   user_roles    │     │     roles       │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id (PK)         │────<│ user_id (FK)    │>────│ id (PK)         │
│ username        │     │ role_id (FK)    │     │ code            │
│ email           │     │ assigned_at     │     │ name            │
│ password_hash   │     │ assigned_by     │     │ level           │
│ display_name    │     └─────────────────┘     │ description     │
│ phone           │                             │ parent_role     │
│ department      │                             │ is_system       │
│ is_active       │     ┌─────────────────┐     │ is_active       │
│ is_locked       │     │ role_permissions│     │ created_at      │
│ last_login      │     ├─────────────────┤     │ updated_at      │
│ created_at      │     │ role_id (FK)    │>────┴─────────────────┘
│ updated_at      │     │ permission_id(FK│>────┬─────────────────┐
│ created_by      │     │ granted_at      │     │  permissions    │
└─────────────────┘     └─────────────────┘     ├─────────────────┤
                                                │ id (PK)         │
┌─────────────────┐     ┌─────────────────┐     │ code            │
│  login_history  │     │  user_tokens    │     │ name            │
├─────────────────┤     ├─────────────────┤     │ module          │
│ id (PK)         │     │ id (PK)         │     │ description     │
│ user_id (FK)    │     │ user_id (FK)    │     │ is_active       │
│ login_time      │     │ token_hash      │     └─────────────────┘
│ ip_address      │     │ device_info     │
│ user_agent      │     │ expires_at      │
│ status          │     │ created_at      │
│ fail_reason     │     │ revoked_at      │
└─────────────────┘     └─────────────────┘
```

### 4.2 表结构定义

#### users 表
```sql
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    phone VARCHAR(20),
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_locked BOOLEAN DEFAULT FALSE,
    lock_reason VARCHAR(255),
    last_login DATETIME,
    login_attempts INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by BIGINT,

    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### roles 表
```sql
CREATE TABLE roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    level INT NOT NULL DEFAULT 0,
    description TEXT,
    parent_role_id BIGINT,
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_code (code),
    INDEX idx_level (level),
    FOREIGN KEY (parent_role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### permissions 表
```sql
CREATE TABLE permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    module VARCHAR(50) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_code (code),
    INDEX idx_module (module)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### user_roles 表
```sql
CREATE TABLE user_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT,

    UNIQUE KEY uk_user_role (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### role_permissions 表
```sql
CREATE TABLE role_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    granted_by BIGINT,

    UNIQUE KEY uk_role_permission (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### user_tokens 表 (Token 黑名单/白名单)
```sql
CREATE TABLE user_tokens (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    device_info VARCHAR(255),
    ip_address VARCHAR(45),
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    revoked_at DATETIME,
    revoke_reason VARCHAR(255),

    INDEX idx_user_id (user_id),
    INDEX idx_token_hash (token_hash),
    INDEX idx_expires_at (expires_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### login_history 表
```sql
CREATE TABLE login_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    status ENUM('success', 'failed', 'locked') NOT NULL,
    fail_reason VARCHAR(255),

    INDEX idx_user_id (user_id),
    INDEX idx_login_time (login_time),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 5. 模块化目录结构

### 5.1 目录架构

```
src/
├── core/
│   └── domain/
│       ├── entities/
│       │   └── auth/                      # 认证领域实体
│       │       ├── __init__.py
│       │       ├── user.py                # 用户实体
│       │       ├── role.py                # 角色实体
│       │       └── permission.py          # 权限实体
│       │
│       └── interfaces/
│           └── auth/                      # 认证领域接口
│               ├── __init__.py
│               ├── user_repository.py     # 用户仓储接口
│               ├── role_repository.py     # 角色仓储接口
│               └── auth_service.py        # 认证服务接口
│
├── infrastructure/
│   ├── auth/                              # 认证基础设施
│   │   ├── __init__.py
│   │   ├── jwt_handler.py                 # JWT 处理器
│   │   ├── password_handler.py            # 密码处理器
│   │   └── token_blacklist.py             # Token 黑名单
│   │
│   └── persistence/
│       └── auth/                          # 认证持久化
│           ├── __init__.py
│           ├── user_repository_impl.py    # 用户仓储实现
│           ├── role_repository_impl.py    # 角色仓储实现
│           └── models/                    # SQLAlchemy 模型
│               ├── __init__.py
│               ├── user_model.py
│               ├── role_model.py
│               └── permission_model.py
│
├── services/
│   └── auth/                              # 认证服务层
│       ├── __init__.py
│       ├── auth_service.py                # 认证服务
│       ├── user_service.py                # 用户管理服务
│       ├── role_service.py                # 角色管理服务
│       └── permission_service.py          # 权限管理服务
│
└── api/
    ├── v1/
    │   └── endpoints/
    │       └── auth/                      # 认证 API 端点
    │           ├── __init__.py
    │           ├── auth.py                # 登录/登出/刷新
    │           ├── users.py               # 用户管理
    │           ├── roles.py               # 角色管理
    │           └── permissions.py         # 权限管理
    │
    ├── middleware/
    │   ├── __init__.py
    │   └── auth_middleware.py             # 认证中间件
    │
    └── dependencies/
        ├── __init__.py
        └── auth.py                        # 认证依赖注入
```

### 5.2 模块职责说明

| 模块 | 路径 | 职责 |
|-----|------|------|
| **领域实体** | `core/domain/entities/auth/` | 定义用户、角色、权限的核心业务对象 |
| **领域接口** | `core/domain/interfaces/auth/` | 定义仓储和服务的抽象接口 |
| **认证基础设施** | `infrastructure/auth/` | JWT生成/验证、密码加密、Token管理 |
| **持久化实现** | `infrastructure/persistence/auth/` | 数据库模型和仓储实现 |
| **业务服务** | `services/auth/` | 认证、用户、角色、权限的业务逻辑 |
| **API端点** | `api/v1/endpoints/auth/` | RESTful API 接口定义 |
| **中间件** | `api/middleware/` | 请求认证拦截和权限检查 |
| **依赖注入** | `api/dependencies/` | FastAPI 依赖项，获取当前用户等 |

---

## 6. API 接口设计

### 6.1 认证接口

#### 登录
```http
POST /api/v1/auth/login
Content-Type: application/json

{
    "username": "string",
    "password": "string",
    "remember_me": false
}

Response 200:
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
        "id": 1,
        "username": "admin",
        "display_name": "系统管理员",
        "roles": ["admin"],
        "permissions": ["user:create", "user:read", ...]
    }
}
```

#### 登出
```http
POST /api/v1/auth/logout
Authorization: Bearer {token}

Response 200:
{
    "message": "登出成功"
}
```

#### 刷新 Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
    "refresh_token": "eyJ..."
}

Response 200:
{
    "access_token": "eyJ...",
    "expires_in": 86400
}
```

#### 获取当前用户
```http
GET /api/v1/auth/me
Authorization: Bearer {token}

Response 200:
{
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "display_name": "系统管理员",
    "roles": [
        {"code": "admin", "name": "系统管理员"}
    ],
    "permissions": ["user:create", "user:read", ...]
}
```

### 6.2 用户管理接口

#### 获取用户列表
```http
GET /api/v1/users?page=1&size=20&keyword=&role=&status=
Authorization: Bearer {token}

Response 200:
{
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 20,
    "pages": 5
}
```

#### 创建用户
```http
POST /api/v1/users
Authorization: Bearer {token}
Content-Type: application/json

{
    "username": "reviewer1",
    "password": "securePassword123",
    "email": "reviewer1@example.com",
    "display_name": "校审员张三",
    "phone": "13800138000",
    "department": "校审部",
    "roles": ["reviewer"]
}

Response 201:
{
    "id": 10,
    "username": "reviewer1",
    "message": "用户创建成功"
}
```

#### 更新用户
```http
PUT /api/v1/users/{user_id}
Authorization: Bearer {token}
Content-Type: application/json

{
    "display_name": "校审员张三(已升级)",
    "roles": ["direction_reviewer"]
}
```

#### 重置密码
```http
POST /api/v1/users/{user_id}/reset-password
Authorization: Bearer {token}
Content-Type: application/json

{
    "new_password": "newSecurePassword123"
}
```

#### 锁定/解锁用户
```http
POST /api/v1/users/{user_id}/lock
POST /api/v1/users/{user_id}/unlock
Authorization: Bearer {token}
```

### 6.3 角色管理接口

#### 获取角色列表
```http
GET /api/v1/roles
Authorization: Bearer {token}

Response 200:
{
    "items": [
        {
            "id": 1,
            "code": "admin",
            "name": "系统管理员",
            "level": 100,
            "description": "系统最高权限",
            "is_system": true,
            "permissions_count": 20
        },
        ...
    ]
}
```

#### 创建角色
```http
POST /api/v1/roles
Authorization: Bearer {token}
Content-Type: application/json

{
    "code": "senior_reviewer",
    "name": "高级校审员",
    "level": 50,
    "description": "高级校审员，可审批普通校审",
    "parent_role": "direction_reviewer",
    "permissions": ["review:execute", "review:approve"]
}
```

#### 分配角色权限
```http
PUT /api/v1/roles/{role_id}/permissions
Authorization: Bearer {token}
Content-Type: application/json

{
    "permissions": ["user:read", "info:create", "info:read", "review:execute"]
}
```

### 6.4 权限管理接口

#### 获取权限列表
```http
GET /api/v1/permissions?module=user
Authorization: Bearer {token}

Response 200:
{
    "items": [
        {
            "id": 1,
            "code": "user:create",
            "name": "创建用户",
            "module": "user",
            "description": "允许创建新用户"
        },
        ...
    ],
    "modules": ["user", "role", "info", "review", "search", "system"]
}
```

---

## 7. 安全设计

### 7.1 密码安全
- 使用 bcrypt 算法进行密码哈希
- 密码强度要求：最少8位，包含大小写字母和数字
- 密码错误5次后锁定账户30分钟

### 7.2 Token 安全
- Access Token 有效期：24小时（可配置）
- Refresh Token 有效期：7天
- 支持 Token 撤销（登出时加入黑名单）
- Token 包含用户ID、角色、权限等关键信息

### 7.3 JWT Token 结构
```json
{
    "header": {
        "alg": "HS256",
        "typ": "JWT"
    },
    "payload": {
        "sub": "1",                    // 用户ID
        "username": "admin",
        "roles": ["admin"],
        "permissions": ["user:*", "system:*"],
        "iat": 1703836800,             // 签发时间
        "exp": 1703923200,             // 过期时间
        "jti": "unique-token-id"       // Token ID (用于撤销)
    }
}
```

### 7.4 API 安全
- 所有 API 需要认证（除登录接口）
- 基于权限的细粒度访问控制
- 请求频率限制（防止暴力破解）
- 敏感操作需要二次确认

### 7.5 审计日志
- 记录所有登录尝试（成功/失败）
- 记录敏感操作（用户创建、权限变更等）
- 记录 IP 地址和设备信息

---

## 8. 配置项

### 8.1 环境变量

```bash
# JWT 配置
SECRET_KEY=your-secret-key-at-least-32-characters
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_HOURS=24
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# 密码策略
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_DIGIT=true
PASSWORD_REQUIRE_SPECIAL=false

# 登录安全
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=30
LOGIN_REMEMBER_ME_DAYS=30

# 会话管理
SESSION_MAX_CONCURRENT=3
TOKEN_BLACKLIST_ENABLED=true
```

### 8.2 配置类

```python
# src/config.py 新增配置
class AuthSettings(BaseSettings):
    # JWT
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_hours: int = Field(default=24)
    refresh_token_expire_days: int = Field(default=7)

    # 密码策略
    password_min_length: int = Field(default=8)
    password_require_uppercase: bool = Field(default=True)
    password_require_digit: bool = Field(default=True)

    # 登录安全
    login_max_attempts: int = Field(default=5)
    login_lockout_minutes: int = Field(default=30)
```

---

## 9. 初始化数据

### 9.1 初始角色

```sql
INSERT INTO roles (code, name, level, description, is_system) VALUES
('admin', '系统管理员', 100, '系统最高权限，管理所有用户和配置', TRUE),
('chief_reviewer', '总校审员', 80, '管理所有校审工作，分配任务', TRUE),
('direction_reviewer', '方向校审员', 60, '负责特定方向的校审工作', TRUE),
('reviewer', '校审员', 40, '执行具体校审任务', TRUE),
('collector', '信息采集员', 30, '采集和录入信息', TRUE),
('customer', '客户', 20, '查看和使用服务', TRUE);
```

### 9.2 初始权限

```sql
-- 用户管理权限
INSERT INTO permissions (code, name, module) VALUES
('user:create', '创建用户', 'user'),
('user:read', '查看用户', 'user'),
('user:update', '更新用户', 'user'),
('user:delete', '删除用户', 'user'),
('user:list', '用户列表', 'user');

-- 角色管理权限
INSERT INTO permissions (code, name, module) VALUES
('role:create', '创建角色', 'role'),
('role:read', '查看角色', 'role'),
('role:update', '更新角色', 'role'),
('role:delete', '删除角色', 'role'),
('role:assign', '分配角色', 'role');

-- 更多权限...
```

### 9.3 初始管理员

```sql
-- 密码: Admin@123 (bcrypt哈希后)
INSERT INTO users (username, email, password_hash, display_name, is_active) VALUES
('admin', 'admin@system.com', '$2b$12$...', '系统管理员', TRUE);

INSERT INTO user_roles (user_id, role_id) VALUES
(1, 1);  -- admin 角色
```

---

## 10. 实施计划

### Phase 1: 基础架构 (1-2天)
- [ ] 创建目录结构
- [ ] 定义领域实体
- [ ] 创建数据库表
- [ ] 实现 JWT 处理器
- [ ] 实现密码处理器

### Phase 2: 认证功能 (2-3天)
- [ ] 实现用户仓储
- [ ] 实现认证服务
- [ ] 实现登录/登出 API
- [ ] 实现认证中间件
- [ ] 实现权限检查依赖

### Phase 3: 用户管理 (1-2天)
- [ ] 实现用户服务
- [ ] 实现用户管理 API
- [ ] 用户 CRUD 功能

### Phase 4: 角色权限 (1-2天)
- [ ] 实现角色服务
- [ ] 实现权限服务
- [ ] 角色权限管理 API

### Phase 5: 测试与优化 (1-2天)
- [ ] 单元测试
- [ ] 集成测试
- [ ] 安全审计
- [ ] 性能优化

---

## 11. 扩展预留

### 11.1 未来功能
- OAuth2.0 / SSO 集成
- 多因素认证 (MFA)
- 组织架构支持
- 数据权限（行级权限）
- 审批工作流

### 11.2 接口预留
- `POST /api/v1/auth/mfa/enable` - 启用 MFA
- `POST /api/v1/auth/oauth/{provider}` - OAuth 登录
- `GET /api/v1/users/{id}/audit-log` - 用户操作日志

---

## 附录

### A. 错误码定义

| 错误码 | 描述 |
|-------|------|
| AUTH_001 | 用户名或密码错误 |
| AUTH_002 | 账户已锁定 |
| AUTH_003 | Token 已过期 |
| AUTH_004 | Token 无效 |
| AUTH_005 | 权限不足 |
| AUTH_006 | 用户已禁用 |

### B. 参考资料
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- JWT Best Practices: https://auth0.com/docs/secure/tokens/json-web-tokens
- OWASP Authentication: https://owasp.org/www-project-web-security-testing-guide/
