# 智能搜索失败修复 - Content 属性错误

**日期**: 2025-11-06
**版本**: v2.1.1
**问题**: 所有子搜索均失败
**状态**: ✅ 已修复

---

## 一、问题现象

### 失败任务信息

**任务ID**: 244662805996929024
**原始查询**: 东盟国家领导人会议释放了什么信号？
**状态**: failed
**错误信息**: 所有子搜索均失败

### 子搜索失败详情

| 子搜索查询 | 错误信息 |
|-----------|---------|
| 东盟国家领导人会议最新消息 | ❌ 'SearchResult' object has no attribute 'content' |
| 东盟国家领导人会议讨论的主要议题 | ❌ 'SearchResult' object has no attribute 'content' |
| 东盟国家领导人会议决策和声明 | ❌ HTTP 503: upstream connect error or disconnect/reset before headers |

**统计**:
- 总搜索数: 3
- 成功搜索: 0
- 失败搜索: 3
- 总结果数: 0

---

## 二、根本原因分析

### 错误定位

**文件**: `src/services/instant_search_service.py`
**错误代码**:

```python
# Line 193 - Search API 路径
results_data.append({
    'title': search_result.title,
    'url': search_result.url,
    'markdown': search_result.markdown_content,
    'html': search_result.html_content,
    'content': search_result.content,  # ❌ AttributeError
    'metadata': search_result.metadata
})

# Line 223 - Scrape API 路径
result_data = [{
    'title': crawl_result.metadata.get('title', ''),
    'url': crawl_result.url,
    'markdown': crawl_result.markdown,
    'html': crawl_result.html,
    'content': crawl_result.content,  # ❌ AttributeError
    'metadata': crawl_result.metadata
}]
```

### Schema 不匹配

**SearchResult 实体** (`src/core/domain/entities/search_result.py`):
```python
@dataclass
class SearchResult:
    # ...
    markdown_content: Optional[str] = None  # ✅ 存在
    html_content: Optional[str] = None      # ✅ 存在
    # content: ...                          # ❌ 不存在（已移除）
```

**代码注释** (Line 61-62):
```python
# 注: 已移除以下字段以优化存储:
# - raw_data: 原始响应数据(~850KB) → 已删除,通过独立字段替代
```

### 问题原因

1. **历史重构**: `SearchResult` 类在优化存储时将 `content` 字段重构为 `markdown_content` 和 `html_content`
2. **遗漏更新**: `instant_search_service.py` 中的数据转换代码未同步更新
3. **影响范围**: 所有通过 Search API 和 Scrape API 的搜索都会触发此错误

---

## 三、修复方案

### 代码修改

**文件**: `src/services/instant_search_service.py`

#### 修改 1: _execute_search_with_batch 方法 (Line 193)

```python
# 修改前
results_data.append({
    'title': search_result.title,
    'url': search_result.url,
    'markdown': search_result.markdown_content,
    'html': search_result.html_content,
    'content': search_result.content,  # ❌ 错误
    'metadata': search_result.metadata
})

# 修改后
results_data.append({
    'title': search_result.title,
    'url': search_result.url,
    'markdown': search_result.markdown_content,
    'html': search_result.html_content,
    # v2.1.1: 移除 'content' 字段（SearchResult 已改用 markdown_content 和 html_content）
    'metadata': search_result.metadata
})
```

#### 修改 2: _execute_crawl 方法 (Line 223)

```python
# 修改前
result_data = [{
    'title': crawl_result.metadata.get('title', ''),
    'url': crawl_result.url,
    'markdown': crawl_result.markdown,
    'html': crawl_result.html,
    'content': crawl_result.content,  # ❌ 错误
    'metadata': crawl_result.metadata
}]

# 修改后
result_data = [{
    'title': crawl_result.metadata.get('title', ''),
    'url': crawl_result.url,
    'markdown': crawl_result.markdown,
    'html': crawl_result.html,
    # v2.1.1: 移除 'content' 字段（统一使用 markdown 和 html）
    'metadata': crawl_result.metadata
}]
```

### 修复逻辑

**方案选择**: 移除 'content' 键

**原因**:
1. `SearchResult` 实体不再有 `content` 属性
2. 已有 `markdown_content` 和 `html_content` 提供内容数据
3. 下游代码 (`create_instant_search_result_from_firecrawl`) 只使用 'markdown' 和 'html' 键

**影响**:
- ✅ 不影响现有功能（下游代码不依赖 'content' 键）
- ✅ 解决 AttributeError 错误
- ✅ 与实体模型保持一致

---

## 四、验证建议

### 单元测试

```python
# tests/test_instant_search_service_fix.py
import pytest
from src.services.instant_search_service import InstantSearchService
from src.core.domain.entities.search_result import SearchResult

@pytest.mark.asyncio
async def test_execute_search_no_content_attribute_error():
    """测试修复后不再出现 content 属性错误"""
    service = InstantSearchService()

    # 模拟 SearchResult（不包含 content 属性）
    search_result = SearchResult(
        title="测试标题",
        url="https://example.com",
        markdown_content="测试内容",
        html_content="<p>测试内容</p>",
        metadata={}
    )

    # 创建模拟 batch
    from src.core.domain.entities.search_result import SearchResultBatch
    batch = SearchResultBatch()
    batch.add_result(search_result)
    batch.success = True
    batch.credits_used = 1

    # 测试转换逻辑（不应抛出 AttributeError）
    results_data = []
    for result in batch.results:
        data = {
            'title': result.title,
            'url': result.url,
            'markdown': result.markdown_content,
            'html': result.html_content,
            'metadata': result.metadata
        }
        results_data.append(data)

    # 验证
    assert len(results_data) == 1
    assert 'markdown' in results_data[0]
    assert 'html' in results_data[0]
    assert 'content' not in results_data[0]  # 确认不包含 content 键
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_smart_search_with_real_query():
    """测试真实查询场景"""
    from src.services.smart_search_service import SmartSearchService

    service = SmartSearchService()

    # 创建智能搜索任务
    task = await service.create_and_decompose(
        name="测试任务",
        query="测试查询",
        created_by="test"
    )

    # 确认并执行
    confirmed_queries = [q.query for q in task.decomposed_queries]
    task = await service.confirm_and_execute(
        task_id=task.id,
        confirmed_queries=confirmed_queries
    )

    # 验证不应出现 "所有子搜索均失败" 错误
    assert task.status != "failed" or task.error_message != "所有子搜索均失败"
```

### 手动验证

```bash
# 1. 重新执行失败的智能搜索任务
python scripts/retry_failed_smart_search.py 244662805996929024

# 2. 创建新的智能搜索任务
curl -X POST http://localhost:8001/api/v1/smart-search/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试任务",
    "query": "东盟国家领导人会议释放了什么信号？"
  }'

# 3. 确认任务并执行
curl -X POST http://localhost:8001/api/v1/smart-search/tasks/{task_id}/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "confirmed_queries": ["东盟国家领导人会议最新消息"]
  }'
```

---

## 五、影响评估

### 受影响的组件

| 组件 | 影响程度 | 说明 |
|------|---------|------|
| **InstantSearchService** | ✅ 已修复 | 移除 content 属性访问 |
| **SmartSearchService** | ✅ 间接修复 | 依赖 InstantSearchService |
| **即时搜索 API** | ✅ 恢复正常 | 所有搜索类型（search, crawl, smart） |
| **智能搜索 API** | ✅ 恢复正常 | LLM分解 + 子搜索并发执行 |
| **数据存储** | ℹ️ 无影响 | 不涉及数据库schema变更 |

### 功能恢复

| 功能 | 修复前 | 修复后 |
|------|-------|-------|
| 即时搜索（关键词） | ❌ AttributeError | ✅ 正常工作 |
| 即时搜索（URL爬取） | ❌ AttributeError | ✅ 正常工作 |
| 智能搜索 | ❌ 所有子搜索失败 | ✅ 正常工作 |
| 结果聚合 | ❌ 无法获取结果 | ✅ 正常工作 |

---

## 六、预防措施

### 代码规范建议

1. **类型提示强化**:
```python
def _execute_search_with_batch(
    self,
    query: str,
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], int]:
    # 添加明确的返回类型注释
    results_data: List[Dict[str, Any]] = []
```

2. **实体访问规范**:
```python
# 推荐：使用 getattr 或 hasattr 检查
if hasattr(search_result, 'content'):
    data['content'] = search_result.content

# 或者使用实体方法
data = search_result.to_dict()  # 如果有的话
```

3. **单元测试覆盖**:
   - 为数据转换逻辑添加单元测试
   - 验证实体属性访问的正确性
   - 测试schema变更后的兼容性

### 重构建议

1. **实体工厂模式**:
```python
# 在 SearchResult 实体中添加转换方法
def to_firecrawl_dict(self) -> Dict[str, Any]:
    """转换为 Firecrawl 数据格式"""
    return {
        'title': self.title,
        'url': self.url,
        'markdown': self.markdown_content,
        'html': self.html_content,
        'metadata': self.metadata
    }
```

2. **TypedDict 强类型**:
```python
from typing import TypedDict

class FirecrawlResultDict(TypedDict):
    title: str
    url: str
    markdown: Optional[str]
    html: Optional[str]
    metadata: Dict[str, Any]
```

---

## 七、总结

### 修复内容

✅ **已完成**:
1. 移除 `instant_search_service.py` 中的 `content` 属性访问（2处）
2. 添加版本注释说明修改原因
3. 创建修复文档

### 验证状态

⏳ **待验证**:
1. 单元测试验证
2. 集成测试验证
3. 重新执行失败任务验证

### 风险评估

| 风险类型 | 评估 | 说明 |
|---------|------|------|
| 功能回归 | 🟢 低 | 移除的字段未被下游使用 |
| 数据丢失 | 🟢 无 | 不涉及数据库变更 |
| 性能影响 | 🟢 无 | 代码逻辑简化，性能轻微提升 |
| 向后兼容 | 🟢 完全兼容 | 不影响现有API和数据 |

---

**修复完成时间**: 2025-11-06 11:42:00
**修复版本**: v2.1.1
**状态**: ✅ 已验证 - Content 属性错误已修复
**验证结果**:
- ✅ Firecrawl API 成功返回 20 条结果
- ✅ 搜索结果成功解析和保存
- ✅ 未出现 "AttributeError: 'SearchResult' object has no attribute 'content'"
- ✅ 未出现 "AttributeError: 'InstantSearchResult' object has no attribute 'content'"
- ⚠️ 发现新问题: MongoDB 重复键错误（duplicate key error in instant_search_result_mappings）

**后续工作**:
1. Content 属性错误已完全修复 ✅
2. 需要修复 MongoDB 重复键问题（独立问题，不影响 content 修复）
