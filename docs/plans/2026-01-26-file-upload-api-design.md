# 文件上传接口改造设计

## 概述

改造 `/dashboard/info-generation/input` 页面的文件上传功能，优化字段映射和接口安全性。文件上传继续入库到 `data_sources` 集合。

## 需求背景

- 文件上传接口需要移除前端传递的 `created_by`，改由后端从 JWT Token 获取
- 分类字段需要使用 `metadata.category` 格式与系统保持一致
- 移除分类合并到 tags 数组的逻辑

## 设计方案

### 1. 后端接口改造

#### 修改 CreateDataSourceRequest 模型

**文件：** `src/api/v1/endpoints/data_source_management.py`

**改动：**
- 移除 `created_by` 字段
- 端点添加 JWT 认证依赖 `current_user: User = Depends(get_current_user)`
- 从 `current_user.id` 获取用户信息

**改动前：**
```python
class CreateDataSourceRequest(BaseModel):
    title: str = Field(...)
    description: str = Field(...)
    created_by: str = Field(...)  # 前端传递
    tags: Optional[List[str]] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    primary_category: Optional[str] = Field(default=None)
    secondary_category: Optional[str] = Field(default=None)
    tertiary_category: Optional[str] = Field(default=None)
    custom_tags: Optional[List[str]] = Field(default=None)
```

**改动后：**
```python
class CreateDataSourceRequest(BaseModel):
    title: str = Field(...)
    description: str = Field(...)
    # created_by 移除，从 JWT Token 获取
    tags: Optional[List[str]] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    primary_category: Optional[str] = Field(default=None)
    secondary_category: Optional[str] = Field(default=None)
    tertiary_category: Optional[str] = Field(default=None)
    custom_tags: Optional[List[str]] = Field(default=None)
```

#### 修改 create_data_source 端点

```python
@router.post("/", summary="创建数据源")
async def create_data_source(
    request: CreateDataSourceRequest,
    current_user: User = Depends(get_current_user),  # 新增 JWT 认证
    service: DataCurationService = Depends(get_data_curation_service)
):
    data_source = await service.create_data_source(
        title=request.title,
        description=request.description,
        created_by=current_user.id,  # 从 Token 获取
        tags=request.tags,
        metadata=request.metadata,
        primary_category=request.primary_category,
        secondary_category=request.secondary_category,
        tertiary_category=request.tertiary_category,
        custom_tags=request.custom_tags
    )
    ...
```

### 2. 前端改造

#### 修改 CreateDataSourceRequest 类型

**文件：** `guanshanCMS/lib/api-types.ts`

```typescript
export interface CreateDataSourceRequest {
  title: string
  description?: string
  // created_by 移除，由后端从 Token 获取
  tags?: string[]
  metadata?: Record<string, any>
  primary_category?: string | null
  secondary_category?: string | null
  tertiary_category?: string | null
  custom_tags?: string[]
}
```

#### 修改文件上传 saveFileEntry 函数

**文件：** `guanshanCMS/app/dashboard/info-generation/input/page.tsx`

**改动前：**
```typescript
const allTags = [
  uploadedFile.primaryCategory,
  uploadedFile.secondaryCategory,
  uploadedFile.tertiaryCategory,
  ...uploadedFile.tags
].filter(Boolean)

await dataSourcesAPI.create({
  title: uploadedFile.title,
  description: uploadedFile.description || contentToSave.substring(0, 500),
  edited_content: contentToSave,
  created_by: "current_user",
  tags: allTags,
  metadata: {
    source_type: "file",
    source_url: uploadedFile.sourceUrl || fileResponse.storage_url,
    published_at: uploadedFile.publishedAt || undefined,
    file_id: fileResponse.file_id,
    file_type: uploadedFile.type,
    original_filename: uploadedFile.name,
    file_size: uploadedFile.size,
    entry_type: "file",
  }
})
```

**改动后：**
```typescript
await dataSourcesAPI.create({
  title: uploadedFile.title,
  description: uploadedFile.description || contentToSave.substring(0, 500),
  edited_content: contentToSave,
  // created_by 移除
  tags: uploadedFile.tags.length > 0 ? uploadedFile.tags : undefined,
  metadata: {
    source_type: "file",
    source_url: uploadedFile.sourceUrl || fileResponse.storage_url,
    published_at: uploadedFile.publishedAt || undefined,
    file_id: fileResponse.file_id,
    file_type: uploadedFile.type,
    original_filename: uploadedFile.name,
    file_size: uploadedFile.size,
    entry_type: "file",
    category: {
      "大类": uploadedFile.primaryCategory || null,
      "类别": uploadedFile.secondaryCategory || null,
      "地域": uploadedFile.tertiaryCategory || null
    }
  }
})
```

### 3. 改动文件清单

#### 后端

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `src/api/v1/endpoints/data_source_management.py` | 修改 | 移除 `created_by` 字段，添加 JWT 认证 |

#### 前端

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `guanshanCMS/lib/api-types.ts` | 修改 | 移除 `CreateDataSourceRequest.created_by` |
| `guanshanCMS/app/dashboard/info-generation/input/page.tsx` | 修改 | 文件上传移除 `created_by`，分类改用 `metadata.category` |

#### 文档

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `guanshanCMS/docs/PROCESS_FLOW_HANDLE_PROCESSING.md` | 修改 | 更新 API 调用示例 |

## 注意事项

1. **认证必须**：修改后的接口强制要求 JWT 认证，未登录用户无法调用
2. **向后不兼容**：移除 `created_by` 字段是破坏性变更，需确保前端同步更新
3. **分类格式**：使用 `metadata.category` 格式（大类/类别/地域）与系统保持一致
4. **标签分离**：`tags` 只存储自定义标签，分类信息存入 `metadata.category`
