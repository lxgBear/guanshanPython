# 智能搜索职责分离实施报告

**日期**: 2025-11-03
**版本**: v1.5.2
**实施内容**: 选项B - 实现真正的职责分离（增加复杂度）

---

## 🎯 实施目标

### 原问题
- `smart_search_results` 集合存在但从未被使用
- 包含3条历史UUID格式数据
- 智能搜索聚合结果实际存储在 `instant_search_results`
- 职责不清晰：即时搜索和智能搜索结果混合存储

### 解决方案
**选项B**: 实现真正的职责分离
- `instant_search_results`: 仅存储即时搜索的原始结果
- `smart_search_results`: 专门存储智能搜索的去重聚合结果
- 包含综合评分、多源信息等智能搜索特有字段

---

## 📂 新增文件

### 1. AggregatedSearchResult 实体
**文件**: `src/core/domain/entities/aggregated_search_result.py`

**核心数据结构**:
```python
@dataclass
class AggregatedSearchResult:
    # 核心标识
    id: str  # 雪花ID
    smart_task_id: str  # 智能搜索任务ID

    # 基础搜索结果字段（从原始结果继承）
    title: str
    url: str
    content: str
    snippet: Optional[str]

    # 聚合评分字段（智能搜索专属）
    composite_score: float  # 综合评分
    avg_relevance_score: float  # 平均相关性评分
    avg_quality_score: float  # 平均质量评分
    position_score: float  # 位置评分
    multi_source_score: float  # 多源评分

    # 多源信息（智能搜索专属）
    sources: List[SourceInfo]  # 来源列表
    source_count: int  # 出现在多少个查询中
    multi_source_bonus: bool  # 是否获得多源奖励

    # 元数据
    result_type: str
    language: Optional[str]
    published_date: Optional[datetime]
    status: ResultStatus
```

**评分公式**:
```
composite_score = 0.4 * multi_source_score +
                 0.4 * avg_relevance_score +
                 0.2 * position_score
```

### 2. AggregatedSearchResultRepository
**文件**: `src/infrastructure/database/aggregated_search_result_repositories.py`

**核心方法**:
- `save_results(List[AggregatedSearchResult])` - 批量保存聚合结果
- `get_results_by_task(smart_task_id, page, page_size)` - 分页获取结果
- `get_top_results(smart_task_id, limit)` - 获取top结果
- `get_multi_source_results(smart_task_id)` - 获取多源结果
- `get_statistics_by_task(smart_task_id)` - 获取聚合统计

**集合名称**: `smart_search_results`

---

## 🔧 修改文件

### 1. SmartSearchService 扩展
**文件**: `src/services/smart_search_service.py`

#### 新增导入:
```python
from src.core.domain.entities.aggregated_search_result import (
    AggregatedSearchResult,
    SourceInfo
)
from src.infrastructure.database.aggregated_search_result_repositories import (
    AggregatedSearchResultRepository
)
```

#### 新增Repository:
```python
def __init__(self):
    # ...现有代码
    self.aggregated_result_repo = AggregatedSearchResultRepository()  # v1.5.2
```

#### 新增方法: `_save_aggregated_results()`
**位置**: 第492-592行

**功能**: 将 `ResultAggregator.aggregate()` 的输出转换为 `AggregatedSearchResult` 实体并保存

**关键逻辑**:
```python
async def _save_aggregated_results(
    self,
    smart_task_id: str,
    aggregation_result: Dict[str, Any]
) -> int:
    """保存聚合结果到 smart_search_results 集合"""

    # 转换 ResultAggregator 输出为 AggregatedSearchResult 实体
    for item in aggregation_result["results"]:
        # 构建 SourceInfo 列表
        sources = [SourceInfo(...) for s in item["sources"]]

        # 计算分项评分
        avg_relevance_score = ...
        position_score = ...
        multi_source_score = ...

        # 创建实体
        aggregated_entity = AggregatedSearchResult(
            smart_task_id=smart_task_id,
            composite_score=item["composite_score"],
            sources=sources,
            ...
        )

    # 批量保存
    return await self.aggregated_result_repo.save_results(entities)
```

#### 修改方法: `confirm_and_execute()`
**变更**: 第273-274行

**新增代码**:
```python
# 6.5. 保存聚合结果到 smart_search_results 集合（v1.5.2 职责分离）
await self._save_aggregated_results(task.id, aggregation_result)
```

#### 修改方法: `get_aggregated_results()`
**变更**: 第413-516行

**核心变更**:
- `combined` 模式从 `smart_search_results` 读取（新行为）
- `by_query` 模式仍从 `instant_search_results` 读取（保持不变）

**新逻辑**:
```python
if view_mode == "combined":
    # v1.5.2: 从 smart_search_results 集合读取聚合结果
    results, total = await self.aggregated_result_repo.get_results_by_task(
        smart_task_id=task_id,
        skip=(page - 1) * page_size,
        limit=page_size,
        sort_by="composite_score"
    )

    # 转换为 API 响应格式
    formatted_results = [...]

    return {
        "statistics": task.aggregated_stats,  # 从任务读取
        "results": formatted_results,
        "pagination": {...}
    }
```

---

## 🗂️ 数据流变化

### Before (v1.5.1 及之前):
```
SmartSearchService.confirm_and_execute()
    ↓
并发执行 InstantSearchService (3个子查询)
    ↓
保存到 instant_search_results (30条原始结果)
    ↓
ResultAggregator.aggregate() (内存聚合)
    ↓
保存 aggregated_stats 到 SmartSearchTask

SmartSearchService.get_aggregated_results()
    ↓
从 instant_search_results 读取
    ↓
ResultAggregator.aggregate() (重新聚合)
    ↓
返回聚合结果
```

**问题**:
- 每次获取结果都需要重新聚合（性能开销）
- `smart_search_results` 集合未使用
- 职责混乱：即时搜索和智能搜索结果混合

### After (v1.5.2):
```
SmartSearchService.confirm_and_execute()
    ↓
并发执行 InstantSearchService (3个子查询)
    ↓
保存到 instant_search_results (30条原始结果)
    ↓
ResultAggregator.aggregate() (内存聚合)
    ↓
保存 aggregated_stats 到 SmartSearchTask
    ↓
🆕 _save_aggregated_results()
    ↓
保存到 smart_search_results (30条聚合结果,含评分和来源)

SmartSearchService.get_aggregated_results()
    ↓
🆕 从 smart_search_results 读取（已聚合）
    ↓
直接返回（无需重新聚合）
```

**优势**:
- ✅ 职责分离清晰
- ✅ 无需重复聚合（性能提升）
- ✅ 聚合结果持久化存储
- ✅ 支持更复杂的查询（多源结果、评分排序等）

---

## 📊 集合职责划分

| 集合名称 | 职责 | 存储内容 | Repository |
|---------|------|----------|------------|
| `instant_search_results` | 即时搜索原始结果 | InstantSearchResult | InstantSearchResultRepository |
| `smart_search_results` | 智能搜索聚合结果 | AggregatedSearchResult | AggregatedSearchResultRepository |
| `smart_search_tasks` | 智能搜索任务元数据 | SmartSearchTask | SmartSearchTaskRepository |

### instant_search_results 文档示例:
```json
{
  "_id": "243583606510436353",
  "task_id": "243583605956788224",
  "title": "测试结果 10: 人工智能深度学习技术...",
  "url": "https://example.com/ai-dl-10",
  "content": "...",
  "content_hash": "abc123...",
  "status": "PENDING",
  "result_type": "web"
}
```

### smart_search_results 文档示例:
```json
{
  "_id": "244123456789012345",
  "smart_task_id": "243583472259153920",
  "title": "测试结果 10: 人工智能深度学习技术...",
  "url": "https://example.com/ai-dl-10",
  "content": "...",

  "composite_score": 0.7234,
  "avg_relevance_score": 0.85,
  "position_score": 0.5,
  "multi_source_score": 0.6667,

  "sources": [
    {
      "query": "人工智能机器学习进展",
      "task_id": "243583605952593920",
      "position": 1,
      "relevance_score": 0.9
    },
    {
      "query": "人工智能深度学习技术",
      "task_id": "243583605952593922",
      "position": 2,
      "relevance_score": 0.8
    }
  ],
  "source_count": 2,
  "multi_source_bonus": true,

  "status": "PENDING",
  "result_type": "web"
}
```

---

## ✅ 实施完成清单

- [x] 创建 `AggregatedSearchResult` 实体
- [x] 创建 `SourceInfo` 辅助数据类
- [x] 创建 `AggregatedSearchResultRepository`
- [x] 修改 `SmartSearchService.__init__()` 添加 Repository
- [x] 实现 `SmartSearchService._save_aggregated_results()`
- [x] 修改 `SmartSearchService.confirm_and_execute()` 保存聚合结果
- [x] 修改 `SmartSearchService.get_aggregated_results()` 读取聚合结果
- [x] 修复导入路径错误 (`src.infrastructure.id_generator`)

---

## 🧪 测试建议

### 1. 单元测试
```python
# 测试 AggregatedSearchResult 实体
def test_aggregated_search_result_to_dict():
    result = AggregatedSearchResult(...)
    doc = result.to_dict()
    assert doc["composite_score"] == 0.7234
    assert len(doc["sources"]) == 2

# 测试 Repository 保存和读取
async def test_save_and_retrieve():
    results = [AggregatedSearchResult(...)]
    await repo.save_results(results)

    retrieved, total = await repo.get_results_by_task(task_id)
    assert total == len(results)
```

### 2. 集成测试流程
```bash
# 1. 创建智能搜索任务
curl -X POST .../smart-search-tasks -d '{
  "name": "测试职责分离",
  "query": "AI最新进展"
}'
# 返回: task_id = "XXX"

# 2. 确认并执行搜索
curl -X POST .../smart-search-tasks/XXX/confirm -d '{
  "confirmed_queries": ["AI机器学习", "AI深度学习", "AI应用"]
}'
# 预期:
# - instant_search_results: 新增30条原始结果
# - smart_search_results: 新增30条聚合结果

# 3. 验证 smart_search_results 数据
db.smart_search_results.find({"smart_task_id": "XXX"}).count()
# 预期: 30

db.smart_search_results.findOne({"smart_task_id": "XXX"})
# 验证字段:
# - composite_score 存在
# - sources 数组非空
# - source_count > 0

# 4. 获取聚合结果（combined模式）
curl .../smart-search-tasks/XXX/results?view_mode=combined
# 预期: 从 smart_search_results 读取,包含聚合字段

# 5. 获取按查询分组结果
curl .../smart-search-tasks/XXX/results?view_mode=by_query
# 预期: 从 instant_search_results 读取（保持原行为）
```

### 3. 性能测试
```python
# 对比 v1.5.1 vs v1.5.2 性能

# v1.5.1: 每次获取结果都重新聚合
# 预期: 200-500ms (取决于结果数量)

# v1.5.2: 直接从 smart_search_results 读取
# 预期: 10-50ms (纯数据库查询)

# 性能提升: 4-10倍
```

---

## 🚨 注意事项

### 1. 数据一致性
- `instant_search_results` 和 `smart_search_results` 的URL应该一致
- 如果修改/删除原始结果,需要同步更新聚合结果

### 2. 迁移现有数据
**不需要迁移**:
- `smart_search_results` 之前的3条UUID数据已清理
- 新系统从空集合开始
- 历史智能搜索结果仍可通过 `by_query` 模式访问

### 3. API兼容性
- ✅ 完全向后兼容
- `combined` 模式返回格式不变（仅数据来源改变）
- `by_query` 模式完全不变

### 4. 错误处理
- 如果 `_save_aggregated_results()` 失败,不影响任务完成状态
- 可通过重新调用 `confirm_and_execute()` 重新生成聚合结果

---

## 📈 未来优化方向

### 1. 增量更新
- 当前: 删除任务时需同时删除 `smart_search_results`
- 优化: 实现级联删除或软删除

### 2. 缓存策略
- 对高频访问的聚合结果使用 Redis 缓存
- 减少数据库查询压力

### 3. 聚合算法优化
- 支持自定义评分权重
- 支持机器学习排序模型

### 4. 实时更新
- 当原始结果状态变更时,自动更新聚合结果
- 支持增量聚合（新增子查询时）

---

## 🔗 相关文档

- [数据不一致根因分析](DATA_INCONSISTENCY_ROOT_CAUSE_ANALYSIS.md)
- [智能搜索测试报告](SMART_SEARCH_TEST_REPORT.md)
- [智能搜索分析报告](SMART_SEARCH_ANALYSIS_REPORT.md)
- [ID系统统一报告](ID_SYSTEM_V1.5.0.md)

---

**实施人**: Claude Code Assistant
**实施状态**: ✅ 代码完成，待测试验证
**下一步**:
1. 重启服务器并验证启动成功
2. 执行完整的端到端测试
3. 验证数据库数据一致性
4. 性能对比测试

**报告生成时间**: 2025-11-03
**版本**: v1.0.0
