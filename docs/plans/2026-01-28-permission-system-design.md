# 权限系统设计方案

> 创建日期: 2026-01-28
> 状态: 设计完成，待实现

## 一、需求概述

### 1.1 核心需求
- 接口级别的细粒度权限控制
- 灵活可配置的权限系统
- 动态审批流程（3级或更多）
- 前端页面和按钮的权限控制

### 1.2 设计决策
| 问题 | 决策 |
|------|------|
| 审批类型 | 审批流程级别（内容需经多级审批） |
| 流程配置 | 动态形成（非预配置流程） |
| 审批人指定 | 混合模式（按角色或具体用户） |
| 流程结束条件 | 审批人主动选择（通过并结束/通过并继续） |
| 权限控制粒度 | 扩展现有权限码格式 |
| 前端控制级别 | 页面 + 按钮级别 |
| 权限管理者 | 仅超级管理员 |
| 审核员选择范围 | 所有拥有 review:approve 权限的用户 |

## 二、权限系统增强

### 2.1 权限码扩展

在现有 `模块:操作` 格式基础上增加：

```python
# === 审批相关权限 ===
"review:approve"           # 基础审批权限（可被选为审核员）
"review:approve:final"     # 终审权限（可直接结束流程，跳过后续审批）

# === 页面权限 ===
"page:dashboard"           # 工作台
"page:compile"             # 整编页面
"page:collect"             # 信息采集
"page:generate"            # 信息生成
"page:user-management"     # 用户管理
"page:role-permissions"    # 角色权限管理
"page:review-pending"      # 待审批列表
"page:review-history"      # 审批历史
"page:system-settings"     # 系统设置

# === 按钮权限 ===
"button:export"            # 导出
"button:batch-delete"      # 批量删除
"button:submit-review"     # 提交审核
"button:create-user"       # 创建用户
"button:reset-password"    # 重置密码
```

### 2.2 权限模块扩展

```python
class PermissionModule(str, Enum):
    USER = "user"           # 用户管理
    ROLE = "role"           # 角色管理
    INFO = "info"           # 信息采集
    REVIEW = "review"       # 校审管理
    SEARCH = "search"       # 搜索功能
    SYSTEM = "system"       # 系统配置
    ARCHIVE = "archive"     # 档案管理
    PAGE = "page"           # 页面权限 (新增)
    BUTTON = "button"       # 按钮权限 (新增)
    WORKFLOW = "workflow"   # 审批流程 (新增)
```

## 三、动态审批流程

### 3.1 审批流程模型

```python
class ReviewFlowStatus(str, Enum):
    PENDING = "pending"       # 待审批
    APPROVED = "approved"     # 已通过
    REJECTED = "rejected"     # 已拒绝

class ReviewAction(str, Enum):
    PASS_AND_CONTINUE = "pass_and_continue"  # 通过并继续（指定下一审核员）
    PASS_AND_END = "pass_and_end"            # 通过并结束
    REJECT = "reject"                         # 拒绝

class ReviewStep:
    step: int                  # 步骤序号
    reviewer_id: str           # 审核员ID
    reviewer_name: str         # 审核员姓名
    status: ReviewFlowStatus   # 本步骤状态
    action: Optional[ReviewAction]  # 审核操作
    comment: Optional[str]     # 审核意见
    assigned_at: datetime      # 指派时间
    reviewed_at: Optional[datetime]  # 审核时间

class ReviewFlow:
    id: str                    # 流程ID
    target_id: str             # 被审批对象ID
    target_type: str           # 对象类型 (review_entry, info_entry等)

    review_chain: List[ReviewStep]  # 审批链（动态形成）
    current_step: int          # 当前步骤
    status: ReviewFlowStatus   # 整体状态

    submitter_id: str          # 提交人ID
    submitter_name: str        # 提交人姓名

    created_at: datetime       # 创建时间
    completed_at: Optional[datetime]  # 完成时间
```

### 3.2 审批流程图

```
┌─────────┐     选择审核员A     ┌──────────┐
│  提交人  │ ─────────────────→ │  审核员A  │
└─────────┘                     └────┬─────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────┐
            │ 通过并结束    │  │ 通过并继续    │  │   拒绝   │
            │ (流程完成 ✅) │  │ (选择审核员B) │  │(流程终止❌)│
            └──────────────┘  └──────┬───────┘  └──────────┘
                                     │
                                     ▼
                              ┌──────────┐
                              │  审核员B  │
                              └────┬─────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                   ...           ...            ...
```

### 3.3 核心API设计

```
# 提交审批
POST /api/v1/review-flow/submit
Body: {
  target_id: str,           # 被审批对象ID
  target_type: str,         # 对象类型
  reviewer_id: str          # 首个审核员ID
}

# 审批通过
POST /api/v1/review-flow/{flow_id}/approve
Body: {
  action: "pass_and_continue" | "pass_and_end",
  comment?: str,            # 审核意见
  next_reviewer_id?: str    # 下一审核员（action=pass_and_continue时必填）
}

# 审批拒绝
POST /api/v1/review-flow/{flow_id}/reject
Body: {
  comment?: str             # 拒绝原因
}

# 获取我的待审批列表
GET /api/v1/review-flow/pending
Query: page, page_size, target_type?

# 获取审批历史
GET /api/v1/review-flow/history
Query: page, page_size, target_type?, status?

# 获取审批详情
GET /api/v1/review-flow/{flow_id}

# 获取可选审核员列表
GET /api/v1/users/reviewers
Response: [{ id, username, display_name, department }]
```

## 四、前端权限控制

### 4.1 权限 Hook

```typescript
// hooks/usePermission.ts
export function usePermission() {
  const user = useCurrentUser()

  const hasPermission = (permission: string): boolean => {
    return user?.permissions?.includes(permission) ?? false
  }

  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(p => hasPermission(p))
  }

  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(p => hasPermission(p))
  }

  return { hasPermission, hasAnyPermission, hasAllPermissions }
}
```

### 4.2 权限守卫组件

```tsx
// components/permission-guard.tsx
interface PermissionGuardProps {
  permission: string | string[]
  mode?: 'any' | 'all'           // 多权限时的判断模式
  fallback?: 'hide' | 'disable' | ReactNode  // 无权限时的行为
  children: ReactNode
}

export function PermissionGuard({
  permission,
  mode = 'any',
  fallback = 'hide',
  children
}: PermissionGuardProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions } = usePermission()

  const permissions = Array.isArray(permission) ? permission : [permission]
  const hasAccess = mode === 'all'
    ? hasAllPermissions(permissions)
    : hasAnyPermission(permissions)

  if (hasAccess) {
    return <>{children}</>
  }

  if (fallback === 'hide') return null
  if (fallback === 'disable') {
    return React.cloneElement(children as React.ReactElement, { disabled: true })
  }
  return <>{fallback}</>
}
```

### 4.3 使用示例

```tsx
// 页面级控制
<PermissionGuard permission="page:user-management">
  <UserManagementPage />
</PermissionGuard>

// 按钮级控制
<PermissionGuard permission="button:export">
  <Button>导出</Button>
</PermissionGuard>

// 禁用而非隐藏
<PermissionGuard permission="button:delete" fallback="disable">
  <Button>删除</Button>
</PermissionGuard>

// 多权限（满足任一）
<PermissionGuard permission={["button:edit", "button:update"]} mode="any">
  <Button>编辑</Button>
</PermissionGuard>
```

### 4.4 菜单动态过滤

```typescript
// 侧边栏菜单配置
const menuConfig = [
  { label: "工作台", href: "/dashboard", permission: "page:dashboard", icon: Home },
  { label: "信息采集", href: "/collect", permission: "page:collect", icon: Search },
  { label: "整编", href: "/compile", permission: "page:compile", icon: FileEdit },
  { label: "待审批", href: "/review-pending", permission: "page:review-pending", icon: Clock },
  { label: "用户管理", href: "/user-management", permission: "page:user-management", icon: Users },
  // ...
]

// 过滤菜单
const visibleMenus = menuConfig.filter(item => hasPermission(item.permission))
```

## 五、实现计划

### 5.1 后端改动

| 文件路径 | 改动说明 |
|----------|----------|
| `src/core/domain/entities/auth/permission.py` | 扩展权限模块和权限码 |
| `src/core/domain/entities/review_flow.py` | 新增审批流程实体 |
| `src/infrastructure/persistence/repositories/mongo/review_flow_repository.py` | 新增审批流程仓储 |
| `src/api/v1/endpoints/review_flow.py` | 新增审批流程 API |
| `src/api/v1/endpoints/auth/users.py` | 新增获取审核员列表接口 |
| `src/api/v1/router.py` | 注册新路由 |

### 5.2 前端改动

| 文件路径 | 改动说明 |
|----------|----------|
| `hooks/usePermission.ts` | 新增权限 Hook |
| `components/permission-guard.tsx` | 新增权限守卫组件 |
| `components/sidebar.tsx` 或 `app-sidebar.tsx` | 菜单权限过滤 |
| `lib/api-client.ts` | 新增审批流程 API 客户端 |
| `lib/api-types.ts` | 新增相关类型定义 |
| 各页面/按钮 | 添加权限守卫 |

### 5.3 数据库

| 集合名称 | 说明 |
|----------|------|
| `review_flows` | 审批流程记录 |

## 六、角色权限预设

基于现有角色，建议的权限配置：

| 角色 | 页面权限 | 按钮权限 | 审批权限 |
|------|----------|----------|----------|
| admin | 所有 | 所有 | review:approve, review:approve:final |
| chief_reviewer | 大部分 | 大部分 | review:approve, review:approve:final |
| direction_reviewer | 采集/整编/审批 | 常规操作 | review:approve |
| reviewer | 采集/整编/审批 | 常规操作 | review:approve |
| collector | 采集/整编 | 提交审核 | - |
| customer | 工作台/搜索 | 查看 | - |
