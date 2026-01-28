# 单条信息统一存储到 info_entries 设计方案

> 日期: 2026-01-27
> 状态: 待实现

## 背景

用户在 compile 页面编辑「单条信息」后，点击「保存草稿」或「提交」时，需要将数据持久化。
当前条目(Entry)的流程已经完善，单条信息可以复用相同的存储和流程。

## 设计决策

1. **统一存储**：单条信息和多条条目都存入 `info_entries` 表
2. **区分方式**：通过 `raw_data_count` 区分
   - `= 1` 是单条信息
   - `> 1` 是多条条目
3. **状态流转**：复用现有 `status` 字段（draft / published / archived）
4. **暂不处理审核**：后续需要时再扩展

## 数据映射

### SingleInfoItem → InfoEntry

| SingleInfoItem 字段 | InfoEntry 字段 |
|---------------------|----------------|
| `id` | `raw_data_refs[0].data_id` |
| `title` | `title` |
| `content` (原文) | `raw_data_refs[0].markdown_content` |
| `translatedContent` (译文) | `raw_data_refs[0].translated_content` + `combined_content` |
| `source` | `raw_data_refs[0].origin_site` |
| `url` | `raw_data_refs[0].url` |
| `publishedAt` | `raw_data_refs[0].published_date` |
| `category.primary` | `primary_category` |
| `category.secondary` | `secondary_category` |
| `category.region` | `tertiary_category` |
| `tags` | `tags` |

### 自动填充字段

- `raw_data_count`: 固定为 `1`
- `user_id`: 从 Token 获取
- `created_at` / `updated_at`: 服务端生成
- `raw_data_refs[0].data_type`: 来源类型 (scheduled/smart-search/chat-search/upload/manual)
- `raw_data_refs[0].source_collection`: 来源集合名

## 实现计划

### 1. 后端 API

**新增端点**: `POST /api/v1/info-entries/from-single`

```python
class CreateFromSingleRequest(BaseModel):
    # 原始数据信息
    source_data_id: str          # 原数据 ID
    source_data_type: str        # scheduled/smart-search/chat-search/upload/manual
    source_collection: str       # 来源集合名

    # 内容字段
    title: str
    markdown_content: str        # 原文
    translated_content: str      # 译文
    url: str = ""
    origin_site: str = ""
    published_date: Optional[datetime] = None

    # 分类
    primary_category: str = ""
    secondary_category: str = ""
    tertiary_category: str = ""
    tags: List[str] = []

    # 状态
    status: str = "draft"        # draft / published
```

### 2. 前端修改

**API 客户端**: 在 `infoEntriesAPI` 添加 `createFromSingle` 方法

**Compile 页面**:
- `handleSaveDraft`: 单条信息调用 `createFromSingle`，status = 'draft'
- `handleSubmit`: 单条信息调用 `createFromSingle`，status = 'published'

### 3. 草稿箱显示

根据 `raw_data_count` 显示不同标识：
- `= 1`: 显示「单条」标签
- `> 1`: 显示「N条」标签

## 文件修改清单

### 后端
- `src/api/v1/endpoints/info_entries.py`: 新增 `from-single` 端点

### 前端
- `lib/api-client.ts`: 添加 `createFromSingle` 方法
- `app/dashboard/info-generation/compile/page.tsx`: 修改保存逻辑
