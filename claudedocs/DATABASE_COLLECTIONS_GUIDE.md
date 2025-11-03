# 数据库集合职责划分指南

**日期**: 2025-11-03
**版本**: v2.1.0（更新：添加processed_results职责分离）
**目的**: 明确各搜索系统的集合职责和使用场景

---

## 📊 核心结论

### 系统职责清晰划分

| 集合名称 | 系统归属 | 职责说明 | 版本 | 状态 |
|---------|---------|---------|------|------|
| `search_results` | **定时搜索系统** | 存储定时任务的原始搜索结果 | 基础系统 | ✅ 使用中 |
| `processed_results` | **AI处理系统** | 存储定时搜索AI处理后的增强结果 | v2.0.0+ | 🚧 设计中 |
| `instant_search_results` | **即时+智能搜索** | 统一存储即时和智能搜索结果 | v1.3.0+ | ✅ 使用中 |
| `instant_processed_results` | **AI处理系统** | 存储即时+智能搜索AI处理后的增强结果 | v2.1.0+ | 🚧 设计中 |
| `smart_search_results` | **已废弃** | 智能搜索聚合结果表（将迁移至instant_search_results） | v1.5.2-v2.0.0 | ⚠️ 待废弃 |
| `scheduled_search_results` | **已废弃** | 定时搜索结果表（重复数据） | 废弃 | ✅ 已删除 |

**重要说明**：
- **v2.1.0 架构统一**：即时搜索和智能搜索结果统一使用 `instant_search_results`，通过 `search_type` 字段区分
- `search_results`（定时）和 `instant_search_results`（即时+智能）是**并行系统**，服务于不同使用场景
- **职责分离一致性**：两个系统都采用"原始数据 + AI处理结果"的双表架构
  - 定时搜索：`search_results` → `processed_results`
  - 即时+智能搜索：`instant_search_results` → `instant_processed_results`
- **统一AI处理**：所有搜索结果都会通过AI服务进行翻译、总结、分类等增强处理

---

## 🏗️ 两大搜索系统架构（v2.1.0 统一）

### 架构演进说明

**v2.1.0 重大变更**：即时搜索和智能搜索结果统一管理
- ✅ **统一原始数据表**：`instant_search_results` 同时存储即时和智能搜索结果
- ✅ **统一AI处理表**：`instant_processed_results` 统一处理两种搜索类型的AI增强
- ✅ **架构一致性**：定时搜索和即时+智能搜索都采用"原始 + AI处理"双表架构
- ⚠️ **废弃计划**：`smart_search_results` 将被废弃，数据迁移至 `instant_search_results`

### 1️⃣ 定时搜索系统（Scheduled Search System）

```
┌─────────────────────────────────────────────────────┐
│   定时搜索系统（基于 APScheduler）                   │
│   - search_tasks (任务表)                           │
│   - search_results (原始结果表) ✅                   │
│   - processed_results (AI处理结果表) 🚧 设计中      │
└─────────────────────────────────────────────────────┘
```

**核心组件**：
- **服务**：`TaskSchedulerService`（定时搜索任务调度器）
- **任务表**：`search_tasks`
- **结果表**：`search_results`
- **Repository**：`SearchTaskRepository`, `SearchResultRepository`

**代码位置**：
```python
# src/services/task_scheduler.py
class TaskSchedulerService:
    def __init__(self):
        self.task_repository = SearchTaskRepository()
        self.result_repository = SearchResultRepository()  # 使用 search_results
```

**特点**：
- ✅ 基于 APScheduler 的 Cron 定时调度
- ✅ 支持关键词搜索和 URL 爬取
- ✅ 定期执行并保存结果到 `search_results`
- ✅ 支持多种调度间隔（hourly, daily, weekly, monthly）

**使用场景**：
- 用户创建定时任务：每天早上8点搜索"AI新闻"
- 系统自动执行并保存结果
- 结果存储在 `search_results` 集合

---

### 2️⃣ 即时+智能搜索系统（Instant + Smart Search System, v2.1.0 统一）

```
┌────────────────────────────────────────────────────────────────┐
│   即时+智能搜索系统（v2.1.0 统一架构）                          │
│   - instant_search_tasks (即时任务表)                          │
│   - smart_search_tasks (智能任务表)                            │
│   - instant_search_results (统一原始结果表) ✅                 │
│     ├─ search_type="instant": 即时搜索结果                     │
│     └─ search_type="smart": 智能搜索聚合结果                   │
│   - instant_processed_results (统一AI处理结果表) 🚧 设计中     │
│   - instant_search_result_mappings (去重映射表)                │
└────────────────────────────────────────────────────────────────┘
```

**核心组件**：
- **即时搜索服务**：`InstantSearchService`
- **智能搜索服务**：`SmartSearchService`（依赖即时搜索服务）
- **统一结果表**：`instant_search_results`（存储两种类型）
- **统一AI处理表**：`instant_processed_results`（v2.1.0 设计中）
- **Repository**：`InstantSearchResultRepository`, `InstantProcessedResultRepository`（待创建）

**代码位置**：
```python
# src/services/instant_search_service.py
class InstantSearchService:
    def __init__(self):
        self.task_repo = InstantSearchTaskRepository()
        self.result_repo = InstantSearchResultRepository()  # instant_search_results
        self.mapping_repo = InstantSearchResultMappingRepository()

# src/services/smart_search_service.py
class SmartSearchService:
    def __init__(self):
        self.instant_search_service = InstantSearchService()
        self.task_repo = SmartSearchTaskRepository()
        self.result_repo = InstantSearchResultRepository()  # v2.1.0: 统一使用
```

**即时搜索特点**：
- ✅ 实时执行，无定时调度
- ✅ `content_hash` 去重机制（避免重复存储相同内容）
- ✅ 映射表实现跨搜索可见性
- ✅ 统计新结果/共享结果
- ✅ 雪花ID系统（v1.3.0 引入）
- ✅ `search_type="instant"` 标识

**智能搜索特点**：
- ✅ LLM 查询分解（1个查询 → 3个子查询）
- ✅ 调用即时搜索系统执行子查询（子查询结果：`search_type="instant"`）
- ✅ 结果去重聚合 + 综合评分
- ✅ v2.1.0 统一存储：聚合结果保存到 `instant_search_results`（`search_type="smart"`）
- ✅ 支持两种查看模式：
  - `combined`：读取 `search_type="smart"` 的聚合结果
  - `by_query`：读取 `search_type="instant"` 的子查询原始结果

**使用场景**：

**即时搜索**：
- 用户点击"立即搜索"按钮
- 系统立即执行搜索并返回结果
- 结果存储：`instant_search_results` (`search_type="instant"`)

**智能搜索**：
- 用户使用智能搜索：输入"AI最新进展"
- LLM 分解为3个子查询：["AI机器学习", "AI深度学习", "AI应用"]
- 即时搜索系统执行3个子查询（存入 `instant_search_results`, `search_type="instant"`）
- 智能搜索系统聚合结果（存入 `instant_search_results`, `search_type="smart"`）

---

## 📝 集合详细说明

### 1. search_results（定时搜索原始结果表）

**集合名称**：`search_results`
**Repository**：`SearchResultRepository`
**代码位置**：`src/infrastructure/database/repositories.py:247`
**版本变更**：v2.0.0 职责简化 - 纯原始数据存储，移除状态管理

**字段结构**：
```json
{
  "_id": "b3b60f5c-e28f-4187-afef-cc4cd10bf20e",  // UUID格式（历史数据）/ 雪花ID（新数据）
  "task_id": "238931083865448448",
  "title": "搜索结果标题",
  "url": "https://example.com",
  "content": "搜索结果内容",
  "snippet": "搜索结果摘要",
  "markdown_content": "Markdown格式内容",
  "html_content": "HTML格式内容",
  "source": "firecrawl",
  "relevance_score": 0.85,
  "quality_score": 0.90,
  "created_at": "2025-11-03T10:00:00Z"
  // ❌ v2.0.0 移除: status, processed_at（迁移到processed_results）
}
```

**使用代码**：
```python
# src/services/task_scheduler.py:93
self.result_repository = SearchResultRepository()

# src/services/task_scheduler.py:326
saved_ids = await result_repo.save_results(result_batch.results)  # v2.0.0: 返回ID列表
```

**职责（v2.0.0 简化）**：
- ✅ 存储定时任务的**原始搜索结果**（不可变）
- ✅ 由 `TaskSchedulerService` 写入（只写一次）
- ✅ 提供原始数据查询接口
- ❌ 不再管理状态（状态管理移至 `processed_results`）

**v2.0.0 变更说明**：
- **职责分离**：原始数据存储 vs AI处理结果
- **不可变性**：一旦写入，不再修改
- **API兼容**：支持 `?view=raw` 查看原始数据

---

### 2. processed_results（AI处理结果表，v2.0.0 新增）

**集合名称**：`processed_results`
**Repository**：`ProcessedResultRepository`
**代码位置**：`src/infrastructure/database/processed_result_repositories.py`（待创建）
**版本**：v2.0.0 职责分离架构

**字段结构**：
```json
{
  "_id": "processed_243583606510436353",  // 雪花ID
  "raw_result_id": "243583606510436353",  // 关联 search_results._id
  "task_id": "243583605956788224",

  // AI处理后的数据
  "translated_title": "人工智能最新进展（翻译后）",
  "translated_content": "AI技术在2025年取得了突破性进展...",
  "summary": "本文介绍了AI在医疗、教育等领域的应用",
  "key_points": ["医疗AI突破", "教育智能化", "自动驾驶进展"],
  "sentiment": "positive",
  "categories": ["科技", "AI", "创新"],

  // AI处理元数据
  "ai_model": "gpt-4",
  "ai_processing_time_ms": 5000,
  "ai_confidence_score": 0.95,
  "ai_metadata": {},

  // 用户操作状态
  "status": "completed",  // pending/processing/completed/failed/archived/deleted
  "user_rating": 5,
  "user_notes": "重要参考资料",

  // 时间戳
  "created_at": "2025-11-03T10:00:00Z",
  "processed_at": "2025-11-03T10:00:15Z",
  "updated_at": "2025-11-03T10:05:00Z",

  // 错误处理
  "processing_error": null,
  "retry_count": 0
}
```

**使用代码（设计中）**：
```python
# src/services/task_scheduler.py（修改后）
# 1. 保存原始结果
saved_ids = await result_repo.save_results(result_batch.results)

# 2. 创建待处理记录
processed_repo = ProcessedResultRepository()
for raw_id in saved_ids:
    await processed_repo.create_pending_result(raw_id, task_id)

# 3. 通知AI服务
await self._notify_ai_service(saved_ids, task_id)

# AI服务（另一个同事负责）
# 4. AI服务处理
await processed_repo.save_ai_result(
    result_id=processed_id,
    translated_title="...",
    translated_content="...",
    summary="...",
    key_points=[...],
    ai_model="gpt-4",
    processing_time_ms=5000
)
```

**职责（v2.0.0 新增）**：
- ✅ 存储AI处理后的增强数据（翻译、总结、分类）
- ✅ 管理AI处理状态（PENDING → PROCESSING → COMPLETED）
- ✅ 记录用户操作（留存、删除、评分）
- ✅ 支持失败重试机制
- ✅ 提供状态统计和查询

**数据流**：
```
search_results (原始数据)
    ↓
AI服务处理
    ↓
processed_results (增强数据)
    ↓
前端展示（默认视图）
```

**状态流转**：
```
PENDING → PROCESSING → COMPLETED ✓
PENDING → PROCESSING → FAILED → PENDING (重试)
COMPLETED → ARCHIVED (用户操作)
COMPLETED → DELETED (用户操作)
```

**API端点（设计中）**：
- `GET /api/v1/search-tasks/{id}/results?view=processed` - 获取AI处理结果（默认）
- `GET /api/v1/search-tasks/{id}/results?view=raw` - 获取原始结果
- `POST /api/v1/processed-results/{id}/archive` - 用户留存
- `POST /api/v1/processed-results/{id}/delete` - 用户删除
- `PUT /api/v1/processed-results/{id}/rating` - 用户评分

**相关文档**：
- [架构设计](SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md)
- [实施指南](SEARCH_RESULTS_IMPLEMENTATION_GUIDE.md)
- [UML图](diagrams/SEARCH_RESULTS_DATA_MODEL.mermaid)

---

### 3. instant_search_results（即时+智能搜索统一结果表，v2.1.0 扩展）

**集合名称**：`instant_search_results`
**Repository**：`InstantSearchResultRepository`
**代码位置**：`src/infrastructure/database/instant_search_repositories.py:187`
**版本变更**：v2.1.0 扩展 - 统一存储即时和智能搜索结果

**字段结构（v2.1.0 扩展）**：
```json
{
  "_id": "239585920781914112",  // 雪花ID
  "task_id": "239585874380328960",  // 指向instant_search_tasks或smart_search_tasks

  // v2.1.0 新增：类型标识
  "search_type": "instant",  // "instant" | "smart"

  // 共享字段
  "title": "搜索结果标题",
  "url": "https://example.com",
  "content": "搜索结果内容",
  "snippet": "搜索结果摘要",
  "markdown_content": "Markdown格式内容",
  "html_content": "HTML格式内容",
  "status": "PENDING",
  "created_at": "2025-11-03T10:00:00Z",

  // 即时搜索专属字段（search_type="instant"）
  "content_hash": "abc123...",  // 去重字段
  "url_normalized": "https://example.com",  // 规范化URL
  "discovered_count": 1,  // 被发现次数
  "first_discovered_at": "2025-11-03T10:00:00Z",
  "last_discovered_at": "2025-11-03T10:00:00Z",
  "relevance_score": 0.95,
  "quality_score": 0.85,

  // 智能搜索聚合专属字段（search_type="smart"）
  "composite_score": 0.7234,  // 综合评分
  "avg_relevance_score": 0.85,  // 平均相关性
  "position_score": 0.5,  // 位置分数
  "multi_source_score": 0.6667,  // 多源分数
  "sources": [  // 多源信息
    {
      "query": "AI机器学习",
      "task_id": "243583605952593920",
      "position": 1,
      "relevance_score": 0.9
    }
  ],
  "source_count": 2,  // 来源数量
  "multi_source_bonus": true  // 多源加成
}
```

**使用代码（v2.1.0 更新）**：
```python
# 即时搜索写入
# src/services/instant_search_service.py
self.result_repo = InstantSearchResultRepository()
result.search_type = "instant"  # v2.1.0 新增
await self.result_repo.create(result)

# 智能搜索聚合写入
# src/services/smart_search_service.py
aggregated_result.search_type = "smart"  # v2.1.0 新增
await self.result_repo.create(aggregated_result)

# 智能搜索读取子查询原始结果
results = await self.result_repo.get_by_task_and_type(
    task_id=sub_task_id,
    search_type="instant"
)

# 智能搜索读取聚合结果
results = await self.result_repo.get_by_task_and_type(
    task_id=smart_task_id,
    search_type="smart"
)
```

**职责（v2.1.0 扩展）**：
- ✅ 统一存储即时搜索和智能搜索结果
- ✅ 通过 `search_type` 区分两种类型
- ✅ 即时搜索：支持 `content_hash` 去重
- ✅ 智能搜索：存储聚合结果和多源信息
- ✅ 由 `InstantSearchService` 和 `SmartSearchService` 写入
- ✅ 作为统一AI处理的数据源

---

### 4. instant_processed_results（即时+智能搜索AI处理结果表，v2.1.0 新增）

**集合名称**：`instant_processed_results`
**Repository**：`InstantProcessedResultRepository`
**代码位置**：`src/infrastructure/database/instant_processed_result_repositories.py`（待创建）
**版本**：v2.1.0 统一AI处理架构

**字段结构**：
```json
{
  "_id": "instant_processed_245678901234567890",  // 雪花ID
  "raw_result_id": "239585920781914112",  // 关联 instant_search_results._id
  "task_id": "239585874380328960",  // 任务ID
  "search_type": "instant",  // "instant" | "smart"（从原始结果继承）

  // AI处理后的数据
  "translated_title": "搜索结果标题（翻译后）",
  "translated_content": "搜索结果内容（翻译后）",
  "summary": "AI生成的摘要",
  "key_points": ["关键点1", "关键点2", "关键点3"],
  "sentiment": "positive",  // 情感分析
  "categories": ["科技", "AI", "创新"],  // 智能分类

  // AI处理元数据
  "ai_model": "gpt-4",
  "ai_processing_time_ms": 3000,
  "ai_confidence_score": 0.92,
  "ai_metadata": {},

  // 用户操作状态
  "status": "completed",  // pending/processing/completed/failed/archived/deleted
  "user_rating": 4,
  "user_notes": "有用的参考资料",

  // 时间戳
  "created_at": "2025-11-03T10:00:00Z",
  "processed_at": "2025-11-03T10:00:03Z",
  "updated_at": "2025-11-03T10:05:00Z",

  // 错误处理
  "processing_error": null,
  "retry_count": 0
}
```

**使用代码（设计中）**：
```python
# src/services/instant_search_service.py（修改后）
# 1. 保存原始结果
await self.result_repo.create(result)

# 2. 创建待处理记录
processed_repo = InstantProcessedResultRepository()
await processed_repo.create_pending_result(
    raw_result_id=result.id,
    task_id=task_id,
    search_type=result.search_type
)

# 3. 通知AI服务
await self._notify_ai_service(result.id, task_id)

# AI服务（异步处理）
# 4. AI服务处理
await processed_repo.save_ai_result(
    result_id=processed_id,
    translated_title="...",
    translated_content="...",
    summary="...",
    key_points=[...],
    sentiment="positive",
    categories=[...],
    ai_model="gpt-4",
    processing_time_ms=3000
)
```

**职责（v2.1.0 新增）**：
- ✅ 统一存储即时和智能搜索的AI处理结果
- ✅ 管理AI处理状态（PENDING → PROCESSING → COMPLETED）
- ✅ 记录用户操作（留存、删除、评分、备注）
- ✅ 支持失败重试机制
- ✅ 提供统一查询接口

**数据流**：
```
instant_search_results (原始数据，search_type=instant/smart)
    ↓
AI服务异步处理
    ↓
instant_processed_results (增强数据)
    ↓
前端展示（默认视图）
```

**API端点（设计中）**：
- `GET /api/v1/instant-search/{id}/results?view=processed` - 获取AI处理结果（默认）
- `GET /api/v1/instant-search/{id}/results?view=raw` - 获取原始结果
- `GET /api/v1/smart-search/{id}/results?view=processed` - 智能搜索AI处理结果（默认）
- `POST /api/v1/instant-processed-results/{id}/archive` - 用户留存
- `POST /api/v1/instant-processed-results/{id}/delete` - 用户删除
- `PUT /api/v1/instant-processed-results/{id}/rating` - 用户评分

---

### 5. smart_search_results（已废弃，v2.1.0 迁移计划）

**集合名称**：`smart_search_results`
**Repository**：`AggregatedSearchResultRepository`
**代码位置**：`src/infrastructure/database/aggregated_search_result_repositories.py`
**状态**：⚠️ **待废弃**（v2.1.0 将迁移至 `instant_search_results`）

**字段结构**：
```json
{
  "_id": "244123456789012345",  // 雪花ID
  "smart_task_id": "243583472259153920",
  "title": "搜索结果标题",
  "url": "https://example.com",
  "content": "搜索结果内容",
  "snippet": "搜索结果摘要",

  // 聚合评分字段（智能搜索专属）
  "composite_score": 0.7234,
  "avg_relevance_score": 0.85,
  "position_score": 0.5,
  "multi_source_score": 0.6667,

  // 多源信息
  "sources": [
    {
      "query": "AI机器学习",
      "task_id": "243583605952593920",
      "position": 1,
      "relevance_score": 0.9
    },
    {
      "query": "AI深度学习",
      "task_id": "243583605952593922",
      "position": 2,
      "relevance_score": 0.8
    }
  ],
  "source_count": 2,
  "multi_source_bonus": true,
  "status": "PENDING",
  "created_at": "2025-11-03T10:00:00Z"
}
```

**废弃理由（v2.1.0）**：
1. ❌ **架构不统一**：独立表增加复杂性，与即时搜索分离
2. ❌ **AI处理困难**：单独为智能搜索设计AI处理流程，代码重复
3. ❌ **查询复杂**：前端需要处理两个不同的结果表
4. ✅ **统一优势**：迁移到 `instant_search_results` 后，统一使用 `instant_processed_results` 处理

**迁移计划**：
- **Phase 1**：扩展 `instant_search_results`，添加 `search_type` 和智能搜索字段
- **Phase 2**：数据迁移脚本（`smart_search_results` → `instant_search_results`）
- **Phase 3**：更新 `SmartSearchService` 代码
- **Phase 4**：废弃 `smart_search_results` 表和 `AggregatedSearchResultRepository`

**原有职责**（v1.5.2-v2.0.0）：
- 存储智能搜索的聚合结果
- 包含综合评分和多源信息
- 由 `SmartSearchService` 写入和读取

---

### 6. scheduled_search_results（已废弃）

**状态**：✅ **已删除**（2025-11-03）

**删除理由**：
1. ❌ 代码中完全未使用（无 Repository，无 API）
2. 📦 数据与 `search_results` 完全重复（220条记录，ID相同）
3. 📅 定时搜索功能已迁移到 `search_results`
4. 💾 占用存储空间（220条记录已删除）

**删除记录**：
- 删除时间：2025-11-03
- 删除记录数：220
- 验证状态：✅ 集合已完全删除

---

## 🎯 使用场景对比（v2.1.0 更新）

| 场景 | 使用系统 | 原始数据存储 | AI处理结果存储 | 示例 |
|-----|---------|------------|--------------|------|
| **定时任务** | 定时搜索系统 | `search_results` | `processed_results` | 每天早上8点搜索"AI新闻" |
| **立即搜索** | 即时搜索系统 | `instant_search_results`<br/>(`search_type="instant"`) | `instant_processed_results` | 用户点击"立即搜索"按钮 |
| **智能搜索** | 智能搜索系统 | `instant_search_results`<br/>(`search_type="instant"` 子查询<br/>`search_type="smart"` 聚合) | `instant_processed_results` | 用户输入"AI最新进展"，LLM分解为3个子查询 |

---

## 📊 数据流对比

### 定时搜索系统数据流（v2.0.0）

```
用户创建定时任务
    ↓
TaskSchedulerService 调度执行
    ↓
FirecrawlSearchAdapter 执行搜索
    ↓
SearchResultRepository.save_results()
    ↓
存储到 search_results（原始数据）
    ↓
ProcessedResultRepository.create_pending_result()
    ↓
AI服务异步处理
    ↓
存储到 processed_results（AI增强数据）
    ↓
前端查询 processed_results（默认视图）
```

### 即时搜索系统数据流（v2.1.0）

```
用户点击"立即搜索"
    ↓
InstantSearchService.create_and_execute_search()
    ↓
FirecrawlSearchAdapter 执行搜索
    ↓
计算 content_hash 去重
    ↓
InstantSearchResultRepository.create(search_type="instant")
    ↓
存储到 instant_search_results（原始数据）
    ↓
InstantProcessedResultRepository.create_pending_result()
    ↓
AI服务异步处理
    ↓
存储到 instant_processed_results（AI增强数据）
    ↓
前端查询 instant_processed_results（默认视图）
```

### 智能搜索系统数据流（v2.1.0 统一）

```
用户输入智能搜索查询
    ↓
SmartSearchService.create_search_task()
    ↓
LLMService 分解查询（1 → 3个子查询）
    ↓
SmartSearchService.confirm_and_execute()
    ↓
并发执行 3个 InstantSearchService 子搜索
    ↓
子搜索结果存储到 instant_search_results（search_type="instant"）
    ↓
ResultAggregator 聚合去重
    ↓
SmartSearchService._save_aggregated_results()
    ↓
存储到 instant_search_results（search_type="smart"）
    ↓
InstantProcessedResultRepository.create_pending_result()
    ↓
AI服务异步处理
    ↓
存储到 instant_processed_results（AI增强数据）
    ↓
前端查询：
  - combined 模式：从 instant_processed_results 读取（search_type="smart"）
  - by_query 模式：从 instant_processed_results 读取（search_type="instant"）
```

---

## 🔧 Repository 对照表（v2.1.0 更新）

| Repository | 集合名称 | 文件位置 | 版本 | 状态 |
|-----------|---------|---------|------|------|
| `SearchResultRepository` | `search_results` | `src/infrastructure/database/repositories.py:247` | 基础 | ✅ 使用中 |
| `ProcessedResultRepository` | `processed_results` | `src/infrastructure/database/processed_result_repositories.py` | v2.0.0 | 🚧 设计中 |
| `InstantSearchResultRepository` | `instant_search_results` | `src/infrastructure/database/instant_search_repositories.py:187` | v1.3.0+ | ✅ 使用中 |
| `InstantProcessedResultRepository` | `instant_processed_results` | `src/infrastructure/database/instant_processed_result_repositories.py` | v2.1.0 | 🚧 设计中 |
| `AggregatedSearchResultRepository` | `smart_search_results` | `src/infrastructure/database/aggregated_search_result_repositories.py` | v1.5.2-v2.0.0 | ⚠️ 待废弃 |

---

## 📋 清理执行记录

### Phase 1: 已完成（2025-11-03）

✅ **删除 scheduled_search_results**
- 删除时间：2025-11-03
- 删除记录数：220
- 风险评估：🟢 低风险（无代码依赖）
- 验证结果：✅ 集合已完全删除，系统运行正常

### Phase 2: 保留决策

✅ **保留 search_results**
- 理由：定时搜索系统仍在使用
- 活跃引用：5处（task_scheduler.py, frontend API, internal API, 测试文件）
- 决策：✅ 保留，继续使用

✅ **保留 instant_search_results**
- 理由：v1.3.0 核心功能集合
- 系统依赖：即时搜索系统 + 智能搜索系统
- 决策：✅ 保留，继续使用

✅ **保留 smart_search_results**
- 理由：v1.5.2 职责分离架构
- 系统依赖：智能搜索系统
- 决策：✅ 保留，继续使用

---

## 🎓 关键概念澄清

### 常见误解

❌ **误解1**：`search_results` 是"旧系统"，应该被 `instant_search_results` 替代
✅ **正确**：两者是并行系统，各司其职（定时 vs 即时）

❌ **误解2**：`scheduled_search_results` 和 `search_results` 是同一个系统
✅ **正确**：`scheduled_search_results` 已废弃删除，`search_results` 仍在使用

❌ **误解3**：智能搜索结果只存储在 `instant_search_results`
✅ **正确**：v1.5.2 后分离存储（原始结果在 `instant_search_results`，聚合结果在 `smart_search_results`）

### 系统关系

```
定时搜索系统 ⊥ 即时搜索系统 (并行独立)
即时搜索系统 → 智能搜索系统 (数据源依赖)
```

- **定时搜索系统**和**即时搜索系统**是**并行独立**的，互不影响
- **智能搜索系统**依赖**即时搜索系统**作为子查询执行引擎和数据源

---

## 📚 相关文档

- [v1.5.2 职责分离实施报告](SEPARATION_OF_CONCERNS_IMPLEMENTATION.md)
- [智能搜索测试报告](SMART_SEARCH_TEST_REPORT.md)
- [ID系统统一报告](ID_SYSTEM_V1.5.0.md)

---

**文档作者**: Claude Code Assistant
**文档状态**: ✅ 已完成并验证
**最后更新**: 2025-11-03
**版本**: v2.1.0（即时+智能搜索统一架构）

---

## 📝 版本更新记录

**v2.1.0（2025-11-03）**：
- ✅ **架构统一**：即时搜索和智能搜索结果统一使用 `instant_search_results`
- ✅ **类型区分**：新增 `search_type` 字段区分 "instant" 和 "smart"
- ✅ **AI处理统一**：新增 `instant_processed_results` 表统一处理两种搜索类型
- ⚠️ **废弃计划**：`smart_search_results` 标记为待废弃，计划迁移数据
- ✅ **架构一致性**：定时搜索和即时+智能搜索都采用"原始 + AI处理"双表架构

**v2.0.0（2025-11-03）**：
- ✅ 定时搜索职责分离：`search_results` + `processed_results`
- ✅ 原始数据不可变性：search_results只写一次
- ✅ AI异步处理：processed_results管理AI处理状态和结果

**v1.5.2及之前**：
- ✅ 智能搜索职责分离：原始结果和聚合结果分开存储
- ✅ 即时搜索去重机制：content_hash和映射表
- ✅ ID系统统一：全部使用雪花ID
