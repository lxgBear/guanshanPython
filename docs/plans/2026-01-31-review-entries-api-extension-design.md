# 信息处置中心 API 参数扩展设计

## 背景

根据前端逻辑修改后端接口参数，前端 `compile-v2` 页面将「整编工作台」和「草稿箱」合并为「信息处置中心」。

### 前端路径
`/Users/lanxionggao/Documents/guanshanCMS/app/dashboard/info-generation/compile-v2`

### 目标
完成接口对接参数扩展，保证所有功能都正确对接接口。

---

## 问题分析

### 前端页面结构

信息处置中心包含三个 Tab：
1. **待处理** (pending) - 从 `unifiedResultsAPI` 和 `infoEntriesAPI` 获取数据
2. **草稿箱** (draft) - 从 `reviewEntriesAPI.getMyEntries({ status: "draft" })` 获取
3. **已提交** (submitted) - 从 `reviewEntriesAPI.getMyEntries({ status: "pending_review" })` 获取

### 前端使用的 API

| API | 用途 |
|-----|------|
| `unifiedResultsAPI.getResults()` | 获取统一结果 |
| `infoEntriesAPI.getList()` | 获取信息条目列表 |
| `reviewEntriesAPI.getMyEntries()` | 获取我的条目（草稿/已提交） |
| `reviewEntriesAPI.create()` | 创建审核条目（保存草稿） |
| `reviewEntriesAPI.submit()` | 提交审批 |
| `reviewEntriesAPI.delete()` | 删除草稿 |

### 字段差异分析

#### `MyEntryResponse` 字段缺失

**后端现有字段**（`review_entries.py:140-151`）：
```
id, title, status, entry_type, created_at, updated_at,
submitted_at, reviewed_at, reviewer_id, review_comment
```

**前端期望的额外字段**（根据 `ProcessingItem` 和 `page.tsx` 的使用）：
- `summary` - 摘要
- `primary_category` - 大类
- `secondary_category` - 类别
- `tertiary_category` - 地域
- `tags` - 标签列表
- `raw_data_count` - 原始数据数量
- `reviewer_name` - 审核员名称

**原因**：草稿箱和已提交列表需要显示更多信息用于筛选和预览。

#### `CreateReviewEntryRequest`

前后端字段基本一致，无需修改。

---

## 实现方案

### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `src/api/v1/endpoints/review_entries.py` | 1. 扩展 `MyEntryResponse` 类 <br> 2. 更新 `get_my_entries` 函数 |

### 详细设计

#### 1. 扩展 `MyEntryResponse` 类

**位置**：第 140-151 行

**新定义**：
```python
class MyEntryResponse(BaseModel):
    """我的条目响应（扩展版，用于 dashboard 列表）"""
    id: str
    title: str
    status: str
    entry_type: str
    # 扩展字段 - 用于草稿箱列表展示和筛选
    summary: str = ""
    primary_category: str = ""
    secondary_category: str = ""
    tertiary_category: str = ""
    tags: List[str] = []
    raw_data_count: int = 0
    # 审核相关
    reviewer_name: str = ""  # 审核员用户名
    # 时间字段
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_id: str = ""
    review_comment: str = ""
```

#### 2. 更新 `get_my_entries` 函数

**位置**：第 333-395 行

**修改点**：
1. 获取审核员用户名（复用已有的 `get_user_display_name` 函数）
2. 填充新增字段

**新的返回逻辑**：
```python
items = []
for entry in entries:
    reviewer_name = ""
    if entry.reviewer_id:
        reviewer_name = await get_user_display_name(entry.reviewer_id, db)

    items.append(MyEntryResponse(
        id=entry.id,
        title=entry.title,
        status=entry.status.value,
        entry_type=entry.entry_type.value,
        # 新增字段
        summary=entry.summary or "",
        primary_category=entry.primary_category or "",
        secondary_category=entry.secondary_category or "",
        tertiary_category=entry.tertiary_category or "",
        tags=entry.tags or [],
        raw_data_count=entry.raw_data_count,
        reviewer_name=reviewer_name,
        # 时间字段
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else None,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        reviewer_id=entry.reviewer_id or "",
        review_comment=entry.review_comment or "",
    ))
```

---

## 影响分析

1. **向后兼容**：新增字段都有默认值，不影响现有客户端
2. **性能考虑**：`get_user_display_name` 有缓存机制，不会造成性能问题
3. **前端适配**：前端代码已经预期这些字段存在，无需修改

---

## 实现步骤

1. [ ] 修改 `MyEntryResponse` 类，添加扩展字段
2. [ ] 更新 `get_my_entries` 函数，填充新字段
3. [ ] 测试接口返回数据是否正确
4. [ ] 验证前端草稿箱和已提交列表功能

---

## 创建时间

2026-01-31
