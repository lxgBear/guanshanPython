# 用户内容精选与批量编辑完整指南

**文档版本**: v2.0
**最后更新**: 2025-11-17
**需求来源**: 用户编辑 search_results 功能

---

## 📋 目录

1. [概述](#概述)
2. [方案对比](#方案对比)
3. [方案一：简化批量编辑](#方案一简化批量编辑)
4. [方案二：完整精选工作流](#方案二完整精选工作流)
5. [实施建议](#实施建议)
6. [API参考](#api参考)

---

## 概述

### 背景

用户需要对 AI 服务返回的搜索结果进行编辑和精选，以修正 AI 的错误并保存高质量内容。

### 核心工作流

```
用户自然搜索
  ↓
LLM分解查询
  ↓
GPT-5搜索返回URL列表
  ↓
FirecrawlAPI爬取URL内容
  ↓
存入search_results (processed_results表)
  ↓
AI服务分析整理
  ↓
返回news_results表
  ↓
【新增】用户查看AI分析结果
  ↓
【新增】用户编辑字段修正AI错误
  ↓
【新增】用户勾选编辑好的条目
  ↓
【新增】保存到新的精选表
```

### 核心需求

1. **用户编辑能力**: 允许用户修改 news_results 中的特定字段以修正 AI 错误
2. **批量操作**: 支持批量编辑多条记录
3. **精选机制**: 用户可勾选满意的条目进行保存
4. **独立存储**: 用户精选的内容保存到新的独立表中

---

## 方案对比

### 两种方案概览

| 特性 | 方案一：简化批量编辑 | 方案二：完整精选工作流 |
|------|-------------------|-------------------|
| **表名** | `user_edited_results` | `curated_search_results` |
| **API端点** | 5个 | 11个 |
| **状态管理** | 无状态管理 | 5种状态（draft/submitted/approved/rejected/published） |
| **审核流程** | ❌ 无审核 | ✅ 完整审核流程 |
| **版本控制** | 简单编辑追踪 | 完整版本历史 |
| **编辑历史** | 编辑次数+时间 | 详细变更记录 |
| **开发时间** | 3-5天 | 10-13天 |
| **复杂度** | 低 | 高 |
| **适用场景** | 快速批量编辑测试数据 | 需要审核的正式发布流程 |

### 选择建议

**选择方案一**（简化版）的情况:
- ✅ 主要用于内部测试和数据清理
- ✅ 不需要审核流程
- ✅ 快速实施（3-5天）
- ✅ 简单易维护

**选择方案二**（完整版）的情况:
- ✅ 需要正式的内容发布流程
- ✅ 需要审核机制和权限控制
- ✅ 需要详细的编辑历史追踪
- ✅ 对外发布的高质量内容

---

## 方案一：简化批量编辑

### 数据库设计

**表名**: `user_edited_results`（用户编辑结果表）

**基础字段**: 复用 `ProcessedResult` 实体的所有43+字段

**额外编辑追踪字段**:
```python
editor_id: Optional[str]           # 最后编辑人ID
edited_at: Optional[datetime]      # 最后编辑时间
source_result_id: Optional[str]    # 来源记录ID（如果从原表复制）
edit_count: int = 0                # 编辑次数
```

### 可编辑字段清单

#### 核心内容字段 (6个)
```python
title                    # 标题
content_zh               # 中文翻译内容
title_generated          # AI生成的标题
news_results.title       # 最终标题
news_results.content     # 最终内容
news_results.category    # 分类信息（大类/类别/地域）
```

#### 标签与分类 (2个)
```python
article_tag              # 文章标签列表
cls_results              # 分类结果
```

#### 元数据字段 (5个)
```python
author                   # 作者
published_date           # 发布日期
news_results.published_at # 最终发布时间
news_results.source      # 来源域名
language                 # 语言代码
```

#### 质量评估 (2个)
```python
user_rating              # 用户评分 (1-5)
user_notes               # 用户备注
```

#### 媒体资源 (1个)
```python
news_results.media_urls  # 媒体URL列表
```

**总计**: 16个可编辑字段

### MongoDB索引

```python
# 1. 编辑人查询索引
{"editor_id": 1, "edited_at": -1}

# 2. 来源关联索引
{"source_result_id": 1}

# 3. 任务查询索引
{"task_id": 1, "edited_at": -1}

# 4. 创建时间索引
{"created_at": -1}

# 5. 全文搜索索引
{"title": "text", "content_zh": "text"}
```

### API 端点设计

#### 1. 批量更新（灵活模式）

**端点**: `POST /api/v1/user-edits/batch`

**用途**: 一次更新多条记录，每条可以更新不同字段

**请求体**:
```json
{
  "updates": [
    {
      "id": "record_id_1",
      "title": "修正后的标题1",
      "content_zh": "修正后的内容1",
      "news_results": {
        "category": {
          "大类": "科技",
          "类别": "人工智能",
          "地域": "美国"
        }
      }
    },
    {
      "id": "record_id_2",
      "title": "修正后的标题2",
      "article_tag": ["GPT-5", "AI"]
    }
  ],
  "editor_id": "user_123"
}
```

**响应**:
```json
{
  "success": true,
  "total": 2,
  "updated": 2,
  "failed": 0,
  "results": [...]
}
```

#### 2. 批量更新（统一字段模式）

**端点**: `POST /api/v1/user-edits/batch-fields`

**用途**: 一次更新多条记录的**相同字段**为**相同值**

**请求体**:
```json
{
  "record_ids": [
    "record_id_1",
    "record_id_2",
    "record_id_3"
  ],
  "updates": {
    "news_results": {
      "category": {
        "大类": "科技",
        "类别": "人工智能",
        "地域": "美国"
      }
    },
    "article_tag": ["GPT-5", "AI", "技术"],
    "user_rating": 4
  },
  "editor_id": "user_123"
}
```

#### 3. 单条更新

**端点**: `PATCH /api/v1/user-edits/{id}`

**请求体**:
```json
{
  "title": "修正后的标题",
  "content_zh": "修正后的中文内容",
  "news_results": {
    "category": {
      "大类": "新闻",
      "类别": "国际",
      "地域": "欧洲"
    }
  },
  "editor_id": "user_123"
}
```

#### 4. 获取记录详情

**端点**: `GET /api/v1/user-edits/{id}`

#### 5. 从原表复制

**端点**: `POST /api/v1/user-edits/copy`

**用途**: 从 `processed_results` 表复制记录到 `user_edited_results` 用于编辑

### 前端交互流程

#### 批量编辑流程（统一字段）

```
1. 用户在列表中勾选10条记录
   ↓
2. 点击"批量编辑"按钮
   ↓
3. 弹出编辑表单
   - 分类选择：科技 > AI > 美国
   - 标签输入：GPT-5, 技术突破
   - 评分：5星
   ↓
4. 点击"应用到所选记录"
   → POST /user-edits/batch-fields
   ↓
5. 显示成功提示："已更新10条记录"
```

#### 批量编辑流程（逐条不同）

```
1. 用户勾选5条记录
   ↓
2. 点击"批量编辑（详细）"
   ↓
3. 进入批量编辑页面（类似Excel）
   ┌────────┬────────┬────────┐
   │ 标题   │ 内容   │ 分类   │
   ├────────┼────────┼────────┤
   │ [可编辑] │ [可编辑] │ [可编辑] │
   └────────┴────────┴────────┘
   ↓
4. 用户为每条记录单独编辑
   ↓
5. 点击"批量保存"
   → POST /user-edits/batch
   ↓
6. 显示成功提示："已保存5条记录"
```

### 实施计划

**总工作量**: 3-5天

**阶段1: Repository层 (1天)**
- 创建 `UserEditRepository`
- 实现批量更新方法
- 单元测试

**阶段2: Service层 (1天)**
- 创建 `UserEditService`
- 实现字段验证逻辑
- 单元测试

**阶段3: API层 (1-2天)**
- 创建 `user_edits.py` Router
- 实现5个核心端点
- API集成测试

**阶段4: 测试 (0.5天)**
- 端到端测试
- 性能测试

---

## 方案二：完整精选工作流

### 数据库设计

**表名**: `curated_search_results` (用户精选结果表)

#### 表结构

```python
class CurationStatus(str, Enum):
    """精选状态"""
    DRAFT = "draft"              # 草稿 - 用户正在编辑
    SUBMITTED = "submitted"      # 已提交 - 等待审核
    APPROVED = "approved"        # 已批准 - 审核通过
    REJECTED = "rejected"        # 已拒绝 - 审核未通过
    PUBLISHED = "published"      # 已发布 - 对外可见

class CuratedSearchResult(BaseModel):
    """用户精选搜索结果实体"""

    # ========== 主键 ==========
    id: str

    # ========== 关联引用 ==========
    original_result_id: str      # 原始结果ID
    task_id: str                 # 任务ID
    nl_search_log_id: Optional[str]  # NL搜索日志ID

    # ========== 核心内容字段 (用户编辑) ==========
    title: str                   # 精选标题
    content: str                 # 精选内容
    summary: Optional[str]       # 内容摘要

    # ========== 元数据字段 ==========
    author: Optional[str]
    published_at: Optional[datetime]
    source: str
    language: str

    # ========== 分类与标签 ==========
    category: CategoryInfo       # 分类信息
    tags: List[str]              # 标签列表

    # ========== 质量评估 ==========
    user_rating: Optional[int]   # 用户评分 (1-5)
    quality_score: Optional[float]

    # ========== 媒体资源 ==========
    media_urls: List[str]
    featured_image: Optional[str]

    # ========== 精选管理 ==========
    curation_status: CurationStatus
    curator_id: str              # 精选人ID
    curator_notes: Optional[str]

    # ========== 审核信息 ==========
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]

    # ========== 修改历史 ==========
    edit_history: List[Dict[str, Any]]
    version: int

    # ========== 原始数据快照 ==========
    original_data: Dict[str, Any]

    # ========== 时间戳 ==========
    created_at: datetime
    updated_at: datetime
    curated_at: Optional[datetime]
```

### MongoDB索引

```python
# 1. 任务查询索引
{"task_id": 1, "created_at": -1}

# 2. 状态查询索引
{"curation_status": 1, "created_at": -1}

# 3. 用户精选索引
{"curator_id": 1, "created_at": -1}

# 4. 原始结果关联索引
{"original_result_id": 1}

# 5. NL搜索关联索引
{"nl_search_log_id": 1, "created_at": -1}

# 6. 分类查询索引
{"category.major": 1, "category.category": 1, "created_at": -1}

# 7. 全文搜索索引
{"title": "text", "content": "text", "tags": "text"}
```

### API 端点设计

#### 核心端点 (11个)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/curation/results` | POST | 创建精选记录 |
| `/curation/results/{id}` | PATCH | 更新精选记录 |
| `/curation/results/{id}` | GET | 获取精选详情 |
| `/curation/results/{id}` | DELETE | 删除精选记录 |
| `/curation/tasks/{task_id}/results` | GET | 获取任务的精选列表 |
| `/curation/tasks/{task_id}/statistics` | GET | 获取精选统计 |
| `/curation/results/{id}/submit` | POST | 提交审核 |
| `/curation/results/{id}/approve` | POST | 批准精选 |
| `/curation/results/{id}/reject` | POST | 拒绝精选 |
| `/curation/results/{id}/publish` | POST | 发布精选 |
| `/curation/users/{curator_id}/results` | GET | 获取用户的精选记录 |

### 完整工作流

#### 前端操作流程

```
1. 用户查看AI分析结果
   GET /api/v1/search-tasks/{task_id}/results
   → 返回news_results列表

2. 用户选择一条记录进行编辑
   → 前端展示编辑表单，预填AI生成的内容

3. 用户修改字段
   - 修正标题
   - 调整内容翻译
   - 修正分类
   - 添加/修改标签

4. 用户保存编辑
   POST /api/v1/curation/results
   Body: {
     "original_result_id": "123456",
     "curator_id": "user_789",
     "title": "修正后的标题",
     "content": "修正后的内容",
     "category": {...},
     "tags": ["GPT-5", "AI突破"],
     "user_rating": 5
   }
   → 创建精选记录，状态为DRAFT

5. 用户提交审核
   POST /api/v1/curation/results/{curated_id}/submit
   → 状态变更为SUBMITTED

6. 审核人员批准
   POST /api/v1/curation/results/{curated_id}/approve
   → 状态变更为APPROVED

7. 发布精选内容
   POST /api/v1/curation/results/{curated_id}/publish
   → 状态变更为PUBLISHED，对外可见
```

### Repository 层设计

**文件**: `src/infrastructure/database/curated_result_repository.py`

**核心方法**:
```python
async def create(entity: CuratedSearchResult) -> str
async def get_by_id(id: str) -> Optional[CuratedSearchResult]
async def update(entity: CuratedSearchResult) -> bool
async def delete(id: str) -> bool
async def get_by_task(task_id, status, page, page_size) -> Tuple[List, int]
async def get_by_curator(curator_id, page, page_size) -> Tuple[List, int]
async def update_status(id, new_status, reviewer_id, review_notes) -> bool
async def add_edit_history(id, editor_id, changes) -> bool
async def get_statistics_by_task(task_id) -> Dict[str, int]
async def create_indexes()
```

### Service 层设计

**文件**: `src/services/curation_service.py`

**核心方法**:
```python
async def create_curated_result(
    original_result_id, curator_id, edited_data, nl_search_log_id
) -> CuratedSearchResult

async def update_curated_result(
    curated_id, editor_id, updates
) -> CuratedSearchResult

async def submit_for_review(curated_id, curator_id) -> bool
async def approve_curated_result(curated_id, reviewer_id, review_notes) -> bool
async def reject_curated_result(curated_id, reviewer_id, review_notes) -> bool
async def publish_curated_result(curated_id) -> bool

async def get_curated_results_by_task(
    task_id, status, page, page_size
) -> Dict[str, Any]

async def get_curation_statistics(task_id) -> Dict[str, int]
```

### 实施计划

**总工作量**: 10-13天

**阶段1: 数据模型与Repository (2-3天)**
- 创建 `curated_search_result.py` 实体
- 创建 `curated_result_repository.py`
- 创建索引脚本并执行
- 单元测试Repository方法

**阶段2: Service层 (1-2天)**
- 创建 `curation_service.py`
- 实现核心业务逻辑
- 单元测试Service方法

**阶段3: API层 (2-3天)**
- 创建 `curation.py` Router
- 实现所有API端点
- API集成测试

**阶段4: 集成测试 (1天)**
- 创建集成测试脚本
- 完整工作流测试
- 性能测试

**阶段5: 文档与部署 (1天)**
- API文档更新
- 部署文档
- 用户操作手册

---

## 实施建议

### 推荐策略

#### 阶段性实施

**第一阶段（快速上线）**:
1. 实施方案一（简化批量编辑）
2. 满足基本的批量编辑需求
3. 3-5天快速上线

**第二阶段（功能完善）**:
1. 根据使用反馈评估是否需要审核流程
2. 如需要，实施方案二（完整精选工作流）
3. 10-13天实现完整功能

#### 渐进式升级路径

```
方案一 (简化版)
    ↓
评估使用情况
    ↓
是否需要审核流程？
    ├── 否 → 继续使用方案一
    └── 是 → 升级到方案二
```

### 技术考虑

#### 数据迁移

如果从方案一升级到方案二:
```python
# 迁移脚本示例
async def migrate_to_curation_system():
    """从简化版迁移到完整版"""
    edited_results = await user_edit_repo.find_all()

    for edited in edited_results:
        curated = CuratedSearchResult(
            original_result_id=edited.id,
            task_id=edited.task_id,
            curator_id=edited.editor_id,
            title=edited.title,
            content=edited.content_zh,
            # ... 其他字段映射
            curation_status=CurationStatus.APPROVED,  # 已有数据视为已批准
            version=1
        )
        await curated_repo.create(curated)
```

#### 风险控制

**数据一致性**:
- 原始结果被删除时的处理策略
- 建议：保留原始数据快照，soft delete原始结果

**并发编辑**:
- 多人同时编辑同一条记录的冲突
- 建议：使用乐观锁（version字段）

**存储成本**:
- 保留编辑历史导致的数据膨胀
- 建议：定期归档旧版本历史

---

## API参考

### 方案一 API 参考

详见"方案一：简化批量编辑"章节的"API 端点设计"

### 方案二 API 参考

详见"方案二：完整精选工作流"章节的"API 端点设计"

### 通用请求/响应格式

#### 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "字段验证失败",
    "details": [
      {
        "field": "news_results.category.大类",
        "error": "不能为空"
      }
    ]
  }
}
```

#### 批量操作部分失败响应

```json
{
  "success": false,
  "total": 5,
  "updated": 3,
  "failed": 2,
  "results": [
    {
      "id": "record_1",
      "success": true
    },
    {
      "id": "record_4",
      "success": false,
      "error": "记录不存在"
    }
  ]
}
```

---

## 总结

### 方案选择建议

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 内部测试和数据清理 | 方案一 | 简单快速，3-5天上线 |
| 对外发布的正式内容 | 方案二 | 完整审核流程，质量保证 |
| 快速MVP验证 | 方案一 | 先上线验证需求，后续可升级 |
| 企业级内容管理 | 方案二 | 完整的工作流和权限控制 |

### 关键差异总结

**方案一 (简化版)** 优势:
- ✅ 开发周期短（3-5天）
- ✅ 维护成本低
- ✅ 适合快速迭代

**方案二 (完整版)** 优势:
- ✅ 完整的审核流程
- ✅ 详细的版本控制
- ✅ 适合正式发布流程

### 未来扩展

无论选择哪种方案，都可以在后续扩展：
- 添加权限控制系统
- 添加操作日志审计
- 添加质量评分机制
- 添加内容推荐系统

---

**文档维护**: Backend Team
**最后更新**: 2025-11-17
**审核状态**: 待评审
