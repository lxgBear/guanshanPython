# 数据库集合职责划分指南

**日期**: 2025-11-03
**版本**: v2.0.0（更新：澄清系统职责）
**目的**: 明确各搜索系统的集合职责和使用场景

---

## 📊 核心结论

### 系统职责清晰划分

| 集合名称 | 系统归属 | 职责说明 | 版本 | 状态 |
|---------|---------|---------|------|------|
| `search_results` | **定时搜索系统** | 存储定时任务的搜索结果 | 基础系统 | ✅ 使用中 |
| `instant_search_results` | **即时搜索系统** | 存储即时搜索的结果（支持去重） | v1.3.0+ | ✅ 使用中 |
| `smart_search_results` | **智能搜索系统** | 存储聚合后的智能搜索结果 | v1.5.2+ | ✅ 使用中 |
| `scheduled_search_results` | **已废弃** | 定时搜索结果表（重复数据） | 废弃 | ✅ 已删除 |

**重要说明**：
- `search_results` 和 `instant_search_results` 是**并行系统**，不是新旧替代关系
- 两者各司其职，服务于不同的使用场景
- `smart_search_results` 依赖 `instant_search_results` 作为数据源

---

## 🏗️ 三大搜索系统架构

### 1️⃣ 定时搜索系统（Scheduled Search System）

```
┌─────────────────────────────────────────┐
│   定时搜索系统（基于 APScheduler）       │
│   - search_tasks (任务表)               │
│   - search_results (结果表) ✅          │
└─────────────────────────────────────────┘
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

### 2️⃣ 即时搜索系统（Instant Search System, v1.3.0）

```
┌─────────────────────────────────────────┐
│   即时搜索系统（v1.3.0 去重机制）        │
│   - instant_search_tasks (任务表)       │
│   - instant_search_results (结果表) ✅  │
│   - instant_search_result_mappings      │
└─────────────────────────────────────────┘
```

**核心组件**：
- **服务**：`InstantSearchService`（即时搜索服务）
- **任务表**：`instant_search_tasks`
- **结果表**：`instant_search_results`
- **映射表**：`instant_search_result_mappings`
- **Repository**：`InstantSearchTaskRepository`, `InstantSearchResultRepository`

**代码位置**：
```python
# src/services/instant_search_service.py
class InstantSearchService:
    def __init__(self):
        self.task_repo = InstantSearchTaskRepository()
        self.result_repo = InstantSearchResultRepository()  # 使用 instant_search_results
        self.mapping_repo = InstantSearchResultMappingRepository()
```

**特点**：
- ✅ 实时执行，无定时调度
- ✅ `content_hash` 去重机制（避免重复存储相同内容）
- ✅ 映射表实现跨搜索可见性
- ✅ 统计新结果/共享结果
- ✅ 雪花ID系统（v1.3.0 引入）

**使用场景**：
- 用户点击"立即搜索"按钮
- 系统立即执行搜索并返回结果
- 结果存储在 `instant_search_results` 集合

---

### 3️⃣ 智能搜索系统（Smart Search System, v2.0.0 + v1.5.2）

```
┌─────────────────────────────────────────┐
│   智能搜索系统（LLM 查询分解）           │
│   - smart_search_tasks (任务表)         │
│   - instant_search_results (数据源)     │
│   - smart_search_results (聚合表) ✅    │
└─────────────────────────────────────────┘
```

**核心组件**：
- **服务**：`SmartSearchService`（智能搜索服务）
- **任务表**：`smart_search_tasks`
- **数据源**：`instant_search_results`（读取子查询原始结果）
- **聚合表**：`smart_search_results`（v1.5.2 存储聚合结果）
- **Repository**：`SmartSearchTaskRepository`, `AggregatedSearchResultRepository`

**代码位置**：
```python
# src/services/smart_search_service.py
class SmartSearchService:
    def __init__(self):
        self.instant_search_service = InstantSearchService()
        self.task_repo = SmartSearchTaskRepository()
        self.aggregated_result_repo = AggregatedSearchResultRepository()  # v1.5.2
```

**特点**：
- ✅ LLM 查询分解（1个查询 → 3个子查询）
- ✅ 调用即时搜索系统执行子查询（结果存入 `instant_search_results`）
- ✅ 结果去重聚合 + 综合评分
- ✅ v1.5.2 职责分离：原始结果和聚合结果分开存储
- ✅ 支持两种查看模式：
  - `combined`：从 `smart_search_results` 读取聚合结果
  - `by_query`：从 `instant_search_results` 读取原始子查询结果

**使用场景**：
- 用户使用智能搜索：输入"AI最新进展"
- LLM 分解为3个子查询：["AI机器学习", "AI深度学习", "AI应用"]
- 即时搜索系统执行3个子查询（结果存入 `instant_search_results`）
- 智能搜索系统聚合结果（存入 `smart_search_results`）

---

## 📝 集合详细说明

### 1. search_results（定时搜索结果表）

**集合名称**：`search_results`
**Repository**：`SearchResultRepository`
**代码位置**：`src/infrastructure/database/repositories.py:247`

**字段结构**：
```json
{
  "_id": "b3b60f5c-e28f-4187-afef-cc4cd10bf20e",  // UUID格式
  "task_id": "238931083865448448",
  "title": "搜索结果标题",
  "url": "https://example.com",
  "content": "搜索结果内容",
  "snippet": "搜索结果摘要",
  "markdown_content": "Markdown格式内容",
  "html_content": "HTML格式内容",
  "source": "firecrawl",
  "created_at": "2025-11-03T10:00:00Z"
}
```

**使用代码**：
```python
# src/services/task_scheduler.py:93
self.result_repository = SearchResultRepository()

# src/services/task_scheduler.py:326
await result_repo.save_results(result_batch.results)
```

**职责**：
- 存储定时任务的搜索结果
- 由 `TaskSchedulerService` 管理
- 支持定时任务的结果查询和统计

---

### 2. instant_search_results（即时搜索结果表）

**集合名称**：`instant_search_results`
**Repository**：`InstantSearchResultRepository`
**代码位置**：`src/infrastructure/database/instant_search_repositories.py:187`

**字段结构**：
```json
{
  "_id": "239585920781914112",  // 雪花ID
  "task_id": "239585874380328960",
  "content_hash": "abc123...",  // 去重字段
  "url_normalized": "https://example.com",  // 规范化URL
  "title": "搜索结果标题",
  "url": "https://example.com",
  "content": "搜索结果内容",
  "snippet": "搜索结果摘要",
  "markdown_content": "Markdown格式内容",
  "html_content": "HTML格式内容",
  "relevance_score": 0.95,
  "quality_score": 0.85,
  "discovered_count": 1,  // 被发现次数
  "first_discovered_at": "2025-11-03T10:00:00Z",
  "last_discovered_at": "2025-11-03T10:00:00Z",
  "status": "PENDING",
  "created_at": "2025-11-03T10:00:00Z"
}
```

**使用代码**：
```python
# src/services/instant_search_service.py:41
self.result_repo = InstantSearchResultRepository()

# src/services/instant_search_service.py:291
await self.result_repo.create(result)

# src/services/smart_search_service.py (读取原始结果)
results = await self.instant_search_service.get_task_results(sub_task_id)
```

**职责**：
- 存储即时搜索的原始结果
- 支持 `content_hash` 去重
- 作为智能搜索系统的数据源
- 由 `InstantSearchService` 写入
- 由 `SmartSearchService` 读取（作为子查询结果）

---

### 3. smart_search_results（智能搜索聚合结果表）

**集合名称**：`smart_search_results`
**Repository**：`AggregatedSearchResultRepository`
**代码位置**：`src/infrastructure/database/aggregated_search_result_repositories.py`

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

**使用代码**：
```python
# src/services/smart_search_service.py:76
self.aggregated_result_repo = AggregatedSearchResultRepository()

# src/services/smart_search_service.py (保存聚合结果)
await self._save_aggregated_results(task.id, aggregation_result)

# src/services/smart_search_service.py (读取聚合结果)
results, total = await self.aggregated_result_repo.get_results_by_task(
    smart_task_id=task_id,
    skip=(page - 1) * page_size,
    limit=page_size
)
```

**职责**：
- 存储智能搜索的聚合结果
- 包含综合评分和多源信息
- 由 `SmartSearchService` 写入和读取
- v1.5.2 职责分离：与 `instant_search_results` 分开存储

**评分公式**：
```python
composite_score = (
    0.4 * multi_source_score +
    0.4 * avg_relevance_score +
    0.2 * position_score
)
```

---

### 4. scheduled_search_results（已废弃）

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

## 🎯 使用场景对比

| 场景 | 使用系统 | 结果存储位置 | 示例 |
|-----|---------|------------|------|
| **定时任务** | 定时搜索系统 | `search_results` | 每天早上8点搜索"AI新闻" |
| **立即搜索** | 即时搜索系统 | `instant_search_results` | 用户点击"立即搜索"按钮 |
| **智能搜索** | 智能搜索系统 | `instant_search_results`（原始）<br/>`smart_search_results`（聚合） | 用户输入"AI最新进展"，LLM分解为3个子查询 |

---

## 📊 数据流对比

### 定时搜索系统数据流

```
用户创建定时任务
    ↓
TaskSchedulerService 调度执行
    ↓
FirecrawlSearchAdapter 执行搜索
    ↓
SearchResultRepository.save_results()
    ↓
存储到 search_results 集合
```

### 即时搜索系统数据流

```
用户点击"立即搜索"
    ↓
InstantSearchService.create_and_execute_search()
    ↓
FirecrawlSearchAdapter 执行搜索
    ↓
计算 content_hash 去重
    ↓
InstantSearchResultRepository.create()
    ↓
存储到 instant_search_results 集合
    ↓
创建映射记录（instant_search_result_mappings）
```

### 智能搜索系统数据流

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
子搜索结果存储到 instant_search_results
    ↓
ResultAggregator 聚合去重
    ↓
SmartSearchService._save_aggregated_results()
    ↓
存储到 smart_search_results 集合
    ↓
用户获取结果：
  - combined 模式：从 smart_search_results 读取
  - by_query 模式：从 instant_search_results 读取
```

---

## 🔧 Repository 对照表

| Repository | 集合名称 | 文件位置 |
|-----------|---------|---------|
| `SearchResultRepository` | `search_results` | `src/infrastructure/database/repositories.py:247` |
| `InstantSearchResultRepository` | `instant_search_results` | `src/infrastructure/database/instant_search_repositories.py:187` |
| `AggregatedSearchResultRepository` | `smart_search_results` | `src/infrastructure/database/aggregated_search_result_repositories.py` |

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
**版本**: v2.0.0
