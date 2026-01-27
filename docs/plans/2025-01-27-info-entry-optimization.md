# 信息条目功能优化设计

> 创建时间: 2025-01-27
> 状态: 待实现

## 1. 问题背景

### 1.1 条目创建 500 错误
`RawDataRefResponse` 的 `html_content` 等字段定义为必填 `str`，但数据库可能返回 `None`，导致 Pydantic 校验失败：
```
"创建条目失败: 1 validation error for RawDataRefResponse\nhtml_content\n  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]"
```

### 1.2 缺少 task_name
`RawDataRef` 没有记录原始数据来源的任务名称，不便于追溯数据来源。

### 1.3 接口性能问题
当前创建条目需要前端传递完整的原始数据快照，选择条目过多时数据量大、接口变慢。

## 2. 改进目标

- 修复字段类型导致的 500 错误
- `RawDataRef` 新增 `task_name` 字段
- 简化创建接口，只传 `data_type` + `data_id`，后台自动查询

## 3. 技术方案

### 3.1 Bug 修复：响应模型字段类型

**文件：** `src/api/v1/endpoints/info_entries.py`

**修改 `RawDataRefResponse`：**
```python
class RawDataRefResponse(BaseModel):
    """原始数据引用响应"""
    ref_id: str
    data_id: str
    data_type: str
    source_collection: str
    title: str = ""
    url: str = ""
    origin_site: str = ""
    published_date: Optional[str] = None
    markdown_content: str = ""      # 改为有默认值
    html_content: str = ""          # 改为有默认值
    snippet: str = ""               # 改为有默认值
    translated_title: str = ""      # 改为有默认值
    translated_content: str = ""    # 改为有默认值
    translated_at: Optional[str] = None
    task_name: str = ""             # 新增字段
```

### 3.2 实体层新增 task_name

**文件：** `src/core/domain/entities/info_entry.py`

**修改 `RawDataRef`：**
```python
@dataclass
class RawDataRef:
    # ... 现有字段 ...
    
    # 新增：任务名称（仅 scheduled/manual 类型有值）
    task_name: str = ""
```

同步修改 `to_dict()` 和 `from_dict()` 方法。

**task_name 数据来源映射：**

| data_type | task_name 来源 |
|-----------|---------------|
| `scheduled` / `manual` | `search_results.task_name` |
| `smart-search` / `chat-search` / `upload` | 留空 `""` |

### 3.3 简化请求模型

**文件：** `src/api/v1/endpoints/info_entries.py`

```python
class RawDataRefInput(BaseModel):
    """原始数据引用输入（简化版）"""
    data_id: str = Field(..., description="原始数据ID")
    data_type: str = Field(..., description="数据类型: scheduled/smart-search/chat-search/upload/manual")

class CreateEntryRequest(BaseModel):
    """创建条目请求（简化版）"""
    title: str = Field(..., description="条目标题", min_length=1, max_length=200)
    description: Optional[str] = Field("", description="条目描述")
    summary: Optional[str] = Field("", description="摘要")
    combined_content: Optional[str] = Field("", description="合并后的内容")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    primary_category: Optional[str] = Field("", description="大类")
    secondary_category: Optional[str] = Field("", description="类别")
    tertiary_category: Optional[str] = Field("", description="地域")
    raw_data_refs: List[RawDataRefInput] = Field(..., description="原始数据引用", min_length=1)
```

**移除的字段：** `title`, `url`, `snippet`, `origin_site`, `original_content`, `translated_content` 等快照字段

### 3.4 创建接口逻辑调整

**修改 `create_entry` 端点：**

```python
@router.post("/")
async def create_entry(request: CreateEntryRequest, ...):
    # 1. 从数据源获取原始数据
    raw_data_refs = await repo.fetch_raw_data_from_sources([
        {"data_id": ref.data_id, "data_type": ref.data_type}
        for ref in request.raw_data_refs
    ])
    
    # 2. 校验：必须全部获取成功
    if len(raw_data_refs) != len(request.raw_data_refs):
        failed_ids = set(r.data_id for r in request.raw_data_refs) - set(r.data_id for r in raw_data_refs)
        raise HTTPException(400, f"以下数据获取失败: {failed_ids}")
    
    # 3. 创建条目（移除快照兜底逻辑）
    ...
```

### 3.5 仓储层调整：获取 task_name

**文件：** `src/infrastructure/persistence/repositories/mongo/info_entry_repository.py`

**修改 `_fetch_from_search_results`：**
```python
async def _fetch_from_search_results(self, data_id: str) -> Optional[RawDataRef]:
    doc = await self.db.search_results.find_one({"_id": data_id})
    # ...
    return RawDataRef(
        # ... 现有字段 ...
        task_name=doc.get("task_name", ""),  # 新增
    )
```

**其他数据源（smart-search/chat-search/upload）：** `task_name` 留空

## 4. 涉及文件与改动清单

### 4.1 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/api/v1/endpoints/info_entries.py` | 修改 | 1. `RawDataRefInput` 移除快照字段<br>2. `RawDataRefResponse` 字段加默认值 + 新增 task_name<br>3. `create_entry` 移除兜底逻辑，改为失败报错 |
| `src/core/domain/entities/info_entry.py` | 修改 | `RawDataRef` 新增 `task_name` 字段，更新 `to_dict`/`from_dict` |
| `src/infrastructure/persistence/repositories/mongo/info_entry_repository.py` | 修改 | `_fetch_from_search_results` 读取 `task_name` 字段 |

### 4.2 数据库影响

- **无需迁移**：`task_name` 为可选字段，默认空字符串
- **向后兼容**：现有 `info_entries` 数据无需修改

### 4.3 API 兼容性

| 项目 | 变化 |
|------|------|
| 请求体 | **Breaking Change**：移除 `RawDataRefInput` 的快照字段 |
| 响应体 | **兼容**：新增 `task_name` 字段，有默认值 |
| 错误处理 | **变化**：数据获取失败返回 400 而非降级使用快照 |

**前端需同步调整：** 创建条目时只传 `data_type` + `data_id`

## 5. 实现步骤

1. **修复 Bug**：`RawDataRefResponse` 字段加默认值
2. **实体层**：`RawDataRef` 新增 `task_name` 字段
3. **仓储层**：`_fetch_from_search_results` 读取 `task_name`
4. **API 层**：简化 `RawDataRefInput`，调整 `create_entry` 逻辑
5. **测试**：验证创建、查询功能正常
