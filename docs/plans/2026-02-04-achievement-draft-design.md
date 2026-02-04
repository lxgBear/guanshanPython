# 整编成果功能设计文档

> 创建日期: 2026-02-04
> 状态: 已确认

## 1. 功能概述

### 1.1 目标
创建一个全新的"整编成果"功能，独立于现有推送流程，支持：
- 从已发布成果 (`published_entries`) 中选择数据
- 生成成果草稿 (`achievement_draft`)
- 动态链式多级审核流程
- 审核统计分析

### 1.2 核心特性
- **数据来源**: `published_entries` 表（已发布的成果，`entry_type = "single"`）
- **审核模式**: 动态链式多级审核（A → B → C...）
- **审核操作**: 5种（通过、转交、退回提交人、退回上一级、作废）
- **权限控制**: 提交审核后，提交人不可修改

---

## 2. 业务流程

### 2.1 整体流程

```
第1步：选择订阅分类
    ↓
第2步：调用 published_entries 数据
    │   - 展示列表（可展开查看用户编辑内容，注意高度）
    │   - 点击跳转详情页（只读展示）
    ↓
第3步：已选数据汇总
    │   - 内容展示不全时，点击跳转详情页查看
    │   - 点击"生成" → 存入 achievement_draft（草稿状态）
    ↓
提交审核：选择第一个审核员 → 状态变为 pending_review
    │   （提交后，提交人不可修改）
    ↓
审核流程：审核员可执行 5 种操作
    - 通过 → 流程结束
    - 转交 → 下一级审核员
    - 退回提交人 → 提交人修改后回到此审核员
    - 退回上一级 → 上一级审核员重新审核
    - 作废 → 流程终止，不可编辑
```

### 2.2 状态流转图

```
┌─────────┐     提交审核      ┌────────────────┐
│  DRAFT  │ ─────────────────→│ PENDING_REVIEW │
│  草稿   │   选择审核员A      │    待审核       │
└─────────┘                   └───────┬────────┘
     ↑                                │
     │                                ├──── 通过 ────→ APPROVED (已通过)
     │                                │
重新提交                               ├──── 作废 ────→ VOIDED (已作废)
     │                                │
┌────┴────┐    退回提交人             ├──── 转交 ────→ 审核员B (仍是 PENDING)
│ RETURNED│ ←─────────────────────────┤                    │
│  已退回  │                           │                    ├── 通过
└─────────┘                           │                    ├── 转交C
                                      │                    ├── 退回提交人
                                      │←── 退回上一级 ─────┤
                                                           └── 作废
```

### 2.3 状态可编辑性

| 状态 | 提交人可编辑 | 审核员可操作 | 说明 |
|------|-------------|-------------|------|
| DRAFT (草稿) | ✅ | ❌ | 初始状态 |
| PENDING_REVIEW (待审核) | ❌ | ✅ | 等待审核 |
| RETURNED (已退回) | ✅ | ❌ | 修改后重新提交，回到退回的审核员 |
| APPROVED (已通过) | ❌ | ❌ | 流程结束 |
| VOIDED (已作废) | ❌ | ❌ | 流程终止，不可编辑 |

---

## 3. 数据模型

### 3.1 achievement_draft (成果草稿表)

```python
class AchievementStatus(Enum):
    """成果草稿状态"""
    DRAFT = "draft"                    # 草稿（可编辑）
    PENDING_REVIEW = "pending_review"  # 待审核（提交人不可编辑）
    RETURNED = "returned"              # 已退回（提交人可编辑）
    APPROVED = "approved"              # 已通过（流程结束）
    VOIDED = "voided"                  # 已作废（流程终止，不可编辑）

@dataclass
class AchievementDraft:
    # === 主键 ===
    id: str                            # 雪花算法ID

    # === 内容字段 ===
    title: str                         # 标题
    description: str                   # 描述
    summary: str                       # 摘要
    combined_content: str              # 整编内容（HTML/JSON）

    # === 分类与标签 ===
    tags: List[str]
    primary_category: str              # 大类
    secondary_category: str            # 类别
    tertiary_category: str             # 地域

    # === 来源引用 ===
    source_entry_ids: List[str]        # 关联的 published_entries IDs
    raw_data_count: int                # 原始数据数量

    # === 提交人信息（后台自动获取） ===
    author_id: str                     # 创建/提交人ID
    author_name: str                   # 创建/提交人姓名

    # === 状态管理 ===
    status: AchievementStatus          # 当前状态

    # === 当前审核信息 ===
    current_reviewer_id: str           # 当前审核员ID
    current_reviewer_name: str         # 当前审核员姓名
    current_review_level: int          # 当前审核层级（1, 2, 3...）

    # === 时间戳 ===
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]   # 提交审核时间
    completed_at: Optional[datetime]   # 流程完成时间（通过/作废）
```

### 3.2 achievement_review_log (审核日志表)

```python
class ReviewAction(Enum):
    """审核操作类型"""
    SUBMIT = "submit"                  # 提交审核
    APPROVE = "approve"                # 通过（流程结束）
    FORWARD = "forward"                # 转交下一级
    RETURN_TO_AUTHOR = "return_to_author"    # 退回提交人
    RETURN_TO_PREVIOUS = "return_to_previous" # 退回上一级
    VOID = "void"                      # 作废
    RESUBMIT = "resubmit"              # 重新提交（退回后）

@dataclass
class AchievementReviewLog:
    # === 主键 ===
    id: str                            # 雪花算法ID

    # === 关联 ===
    achievement_id: str                # 关联的 achievement_draft ID

    # === 操作信息 ===
    action: ReviewAction               # 操作类型
    review_level: int                  # 审核层级（1, 2, 3...）

    # === 操作人 ===
    operator_id: str                   # 操作人ID
    operator_name: str                 # 操作人姓名

    # === 流转信息 ===
    from_user_id: str                  # 来自谁（上一个处理人）
    to_user_id: str                    # 转给谁（下一个处理人，可为空）
    to_user_name: str                  # 下一个处理人姓名

    # === 审核意见 ===
    comment: str                       # 审核意见/备注

    # === 时间 ===
    created_at: datetime               # 操作时间
```

---

## 4. API 接口设计

### 4.1 端点列表

```yaml
# === 基础 CRUD ===
POST   /api/v1/achievement-drafts              # 创建草稿
GET    /api/v1/achievement-drafts              # 列表查询
GET    /api/v1/achievement-drafts/{id}         # 获取详情
PUT    /api/v1/achievement-drafts/{id}         # 更新草稿
DELETE /api/v1/achievement-drafts/{id}         # 删除草稿

# === 审核流程 ===
POST   /api/v1/achievement-drafts/{id}/submit  # 提交审核
POST   /api/v1/achievement-drafts/{id}/review  # 审核操作
POST   /api/v1/achievement-drafts/{id}/resubmit # 重新提交

# === 审核日志 ===
GET    /api/v1/achievement-drafts/{id}/logs    # 获取审核历史

# === 统计 ===
GET    /api/v1/achievement-review-stats        # 审核统计
```

### 4.2 接口详情

#### 创建草稿
```yaml
POST /api/v1/achievement-drafts
请求体:
  {
    "source_entry_ids": ["id1", "id2", ...],
    "title": "整编标题",
    "description": "描述"
  }
# author_id, author_name 从当前登录用户自动获取
```

#### 提交审核
```yaml
POST /api/v1/achievement-drafts/{id}/submit
请求体:
  {
    "reviewer_id": "reviewer_a_id",
    "reviewer_name": "审核员A"
  }
```

#### 审核操作
```yaml
POST /api/v1/achievement-drafts/{id}/review
请求体:
  {
    "action": "forward",           # approve|forward|return_to_author|return_to_previous|void
    "to_user_id": "reviewer_b_id", # 转交时必填
    "to_user_name": "审核员B",
    "comment": "内容完整，转交终审"
  }
```

### 4.3 前端接口对接

```yaml
# === 第2步：调用数据 ===
GET /api/v1/published-entries
  参数:
    - page, page_size
    - entry_type: "single"
    - primary_category
    - secondary_category
    - keyword

# 详情页（只读展示）
GET /api/v1/published-entries/{id}

# === 第3步：生成草稿 ===
POST /api/v1/achievement-drafts

# === 提交审核 ===
POST /api/v1/achievement-drafts/{id}/submit
```

---

## 5. 权限设计

### 5.1 角色定义

| 角色 | 说明 |
|------|------|
| 编辑人员 (editor) | 可创建、编辑、提交 |
| 审核人员 (reviewer) | 可审核 |
| 管理员 (admin) | 全部权限 |

### 5.2 权限点

```
achievement:create       # 创建草稿
achievement:edit         # 编辑草稿（仅自己创建的）
achievement:delete       # 删除草稿（仅自己创建的 DRAFT 状态）
achievement:submit       # 提交审核
achievement:review       # 审核操作
achievement:view         # 查看列表和详情
achievement:view_all     # 查看所有人的草稿（管理员）
achievement:stats        # 查看审核统计
```

### 5.3 权限矩阵

| 操作 | 编辑人员 | 审核人员 | 管理员 |
|------|---------|---------|--------|
| 创建草稿 | ✅ | ❌ | ✅ |
| 编辑自己的草稿 | ✅ | ❌ | ✅ |
| 删除自己的草稿 | ✅ | ❌ | ✅ |
| 提交审核 | ✅ | ❌ | ✅ |
| 审核操作 | ❌ | ✅ | ✅ |
| 查看审核统计 | ❌ | ✅ | ✅ |

---

## 6. 文件结构

```
src/
├── core/domain/entities/
│   ├── achievement_draft.py          # 成果草稿实体
│   └── achievement_review_log.py     # 审核日志实体
│
├── infrastructure/persistence/repositories/mongo/
│   ├── achievement_draft_repository.py      # 草稿仓储
│   └── achievement_review_log_repository.py # 日志仓储
│
├── services/
│   └── achievement/
│       ├── __init__.py
│       ├── achievement_draft_service.py     # 草稿服务（CRUD）
│       └── achievement_review_service.py    # 审核服务（流程控制）
│
├── api/v1/endpoints/
│   └── achievement_drafts.py         # API 端点
│
└── api/v1/router.py                  # 注册路由
```

### MongoDB 集合

```
guanshan (database)
├── achievement_drafts          # 成果草稿
└── achievement_review_logs     # 审核日志
```

---

## 7. 统计查询示例

```python
# 审核员A本月审核了多少条
db.achievement_review_logs.count({
    "operator_id": "审核员A",
    "action": {"$in": ["approve", "forward", "return_to_author", "return_to_previous", "void"]},
    "created_at": {"$gte": 本月开始, "$lt": 本月结束}
})
```

---

## 8. 参考

- 前端页面参考: guanshanCMS `/dashboard/achievement/results-db/[id]`
- 详情页只做展示，不做任何功能
- 列表展开时注意高度控制
