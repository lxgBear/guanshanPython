# 翻译内容录入接口设计

## 概述

修改 `/dashboard/info-generation/input` 页面的单条信息录入功能，将用户录入的翻译内容入库到 `news_results` 集合，而非原有的 `data_sources` 集合。

## 需求背景

- 用户录入的内容是翻译后的中文内容
- 需要入库到 `news_results` 集合
- 分类字段需要与系统现有分类体系兼容
- 字段映射需要清晰明确

## 设计方案

### 1. 接口设计

#### 新增端点

```
POST /api/v1/search-results/manual/translated
```

#### 请求体

```python
class TranslatedContentRequest(BaseModel):
    # 必填字段
    title: str                    # 标题
    content: str                  # 翻译后的内容（完整保存）

    # 可选字段
    url: Optional[str]            # 来源URL
    published_date: Optional[datetime]  # 原文发布时间

    # 分类字段
    primary_category: Optional[str]     # 一级分类（大类）
    secondary_category: Optional[str]   # 二级分类（类别）
    tertiary_category: Optional[str]    # 三级分类（地域）

    # 标签和备注
    tags: Optional[List[str]]     # 自定义标签
    notes: Optional[str]          # 备注
```

#### 后端自动处理字段

| 字段 | 来源 |
|-----|------|
| `user_id` / `created_by` | JWT Token 提取 |
| `task_id` | 雪花算法生成 |
| `id` | 雪花算法生成 |
| `snippet` | 完整保存 content |
| `markdown_content` | 完整保存 content |
| `data_source_type` | `USER_ADDED` |
| `source` | `"translated"` |
| `language` | `"zh-CN"` |
| `status` | `PENDING` |

### 2. 字段映射

#### 前端 → 后端映射

| 前端字段 | 后端字段 | 说明 |
|---------|---------|------|
| `title` | `title` | 标题 |
| `content` | `snippet` + `markdown_content` | 完整保存 |
| `sourceUrl` | `url` | 来源URL |
| `publishedAt` | `published_date` | 发布时间 |
| `primaryCategory` | `metadata.category.大类` | 一级分类 |
| `secondaryCategory` | `metadata.category.类别` | 二级分类 |
| `tertiaryCategory` | `metadata.category.地域` | 三级分类 |
| `tags` | `metadata.tags` | 自定义标签 |
| `notes` | `metadata.notes` | 备注 |

#### metadata 结构（兼容现有系统）

```python
metadata = {
    "category": {
        "大类": primary_category,
        "类别": secondary_category,
        "地域": tertiary_category
    },
    "tags": tags,
    "notes": notes,
    "input_type": "translated"  # 标识来源
}
```

### 3. 后端实现

#### 文件：`src/api/v1/endpoints/search_results_manual.py`

新增请求模型：

```python
class TranslatedContentRequest(BaseModel):
    """手动录入翻译内容请求"""
    title: str = Field(..., description="标题", min_length=1, max_length=500)
    content: str = Field(..., description="翻译后的内容", min_length=1)
    url: Optional[str] = Field(None, description="来源URL")
    published_date: Optional[datetime] = Field(None, description="发布日期")
    primary_category: Optional[str] = Field(None, description="一级分类（大类）")
    secondary_category: Optional[str] = Field(None, description="二级分类（类别）")
    tertiary_category: Optional[str] = Field(None, description="三级分类（地域）")
    tags: Optional[List[str]] = Field(None, description="自定义标签")
    notes: Optional[str] = Field(None, description="备注")
```

新增 API 端点：

```python
@router.post(
    "/manual/translated",
    response_model=ManualAddResponse,
    summary="手动录入翻译内容",
    description="用户录入翻译后的内容，入库到 news_results"
)
async def add_translated_content(
    request: TranslatedContentRequest,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    # 生成 task_id（雪花算法）
    task_id = generate_string_id()

    # 构建 metadata（兼容现有格式）
    metadata = {
        "category": {
            "大类": request.primary_category,
            "类别": request.secondary_category,
            "地域": request.tertiary_category
        },
        "tags": request.tags or [],
        "notes": request.notes,
        "input_type": "translated"
    }

    # 创建 SearchResult 实体
    result = SearchResult(
        id=generate_string_id(),
        task_id=task_id,
        user_id=current_user.id,
        created_by=current_user.id,
        title=request.title,
        url=request.url or "",
        snippet=request.content,
        markdown_content=request.content,
        source="translated",
        language="zh-CN",
        published_date=request.published_date,
        data_source_type=DataSourceType.USER_ADDED,
        status=ResultStatus.PENDING,
        metadata=metadata,
        created_at=datetime.utcnow()
    )

    result.ensure_content_hash()
    await db.search_results.insert_one(result.__dict__)

    return ManualAddResponse(
        success=True,
        message="翻译内容录入成功",
        data=search_result_to_dict(result)
    )
```

### 4. 前端实现

#### 文件：`guanshanCMS/lib/api-client.ts`

新增 API 方法：

```typescript
export const searchResultsManualAPI = {
  addTranslated: async (data: {
    title: string
    content: string
    url?: string
    published_date?: string
    primary_category?: string
    secondary_category?: string
    tertiary_category?: string
    tags?: string[]
    notes?: string
  }): Promise<ManualAddResponse> => {
    const { data: result } = await apiClient.post(
      '/search-results/manual/translated',
      data
    )
    return result
  }
}
```

#### 文件：`guanshanCMS/app/dashboard/info-generation/input/page.tsx`

修改 `submitTextEntry` 函数：

```typescript
const submitTextEntry = async () => {
  // 验证...

  setIsSubmittingText(true)
  try {
    await searchResultsManualAPI.addTranslated({
      title: textForm.title,
      content: textForm.content,
      url: textForm.sourceUrl || undefined,
      published_date: textForm.publishedAt || undefined,
      primary_category: textForm.primaryCategory || undefined,
      secondary_category: textForm.secondaryCategory || undefined,
      tertiary_category: textForm.tertiaryCategory || undefined,
      tags: textForm.tags.length > 0 ? textForm.tags : undefined,
      notes: textForm.notes || undefined,
    })

    toast.success("信息录入成功")
    resetTextForm()
  } catch (error) {
    console.error("录入失败:", error)
    toast.error("录入失败，请稍后重试")
  } finally {
    setIsSubmittingText(false)
  }
}
```

### 5. 改动文件清单

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `src/api/v1/endpoints/search_results_manual.py` | 修改 | 新增 `TranslatedContentRequest` 模型和 `add_translated_content` 端点 |
| `guanshanCMS/lib/api-client.ts` | 修改 | 新增 `searchResultsManualAPI.addTranslated` 方法 |
| `guanshanCMS/lib/api-types.ts` | 修改 | 新增请求/响应类型定义（可选） |
| `guanshanCMS/app/dashboard/info-generation/input/page.tsx` | 修改 | 修改 `submitTextEntry` 调用新接口 |

## 注意事项

1. **认证**：新接口需要 JWT 认证，从 Token 中提取 `user_id`
2. **分类兼容**：使用 `metadata.category` 存储，格式与现有系统一致（大类/类别/地域）
3. **内容完整保存**：`snippet` 和 `markdown_content` 都完整保存 `content`，不截断
4. **task_id 生成**：使用雪花算法自动生成，便于后续扩展
5. **文件上传**：本次仅改动文本录入，文件上传功能后续再议

## 后续扩展

- 文件上传录入也改为入库到 `news_results`
- 支持批量录入
- 支持关联已有任务
