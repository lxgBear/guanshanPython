# 文件上传接口改造实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改造文件上传接口，移除前端传递的 `created_by`，改由后端从 JWT Token 获取，并优化分类字段映射。

**Architecture:** 修改 `CreateDataSourceRequest` 模型移除 `created_by` 字段，在 `create_data_source` 端点添加 JWT 认证依赖。前端修改 `saveFileEntry` 函数，移除 `created_by`，将分类信息存入 `metadata.category`。

**Tech Stack:** FastAPI, Pydantic, JWT 认证, Next.js, TypeScript

---

## Task 1: 后端 - 添加认证依赖导入

**Files:**
- Modify: `src/api/v1/endpoints/data_source_management.py:1-20`

**Step 1: 添加认证依赖导入**

在文件顶部导入区域，添加 `get_current_active_user` 和 `User` 导入：

```python
from src.api.dependencies.auth import require_permissions, get_current_active_user
from src.core.domain.entities.user import User
```

**Step 2: 验证导入正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api && python -c "from src.api.v1.endpoints.data_source_management import router; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
git add src/api/v1/endpoints/data_source_management.py
git commit -m "feat(api): 添加认证依赖导入到 data_source_management"
```

---

## Task 2: 后端 - 修改 CreateDataSourceRequest 模型

**Files:**
- Modify: `src/api/v1/endpoints/data_source_management.py:29-40`

**Step 1: 移除 created_by 字段**

找到 `CreateDataSourceRequest` 类（第 29-40 行），移除 `created_by` 字段：

改动前：
```python
class CreateDataSourceRequest(BaseModel):
    """创建数据源请求"""
    title: str = Field(..., description="数据源标题", min_length=1, max_length=200)
    description: str = Field("", description="数据源描述", max_length=1000)
    created_by: str = Field(..., description="创建者", min_length=1)
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    ...
```

改动后：
```python
class CreateDataSourceRequest(BaseModel):
    """创建数据源请求

    注意：created_by 由后端从 JWT Token 获取，不再由前端传递
    """
    title: str = Field(..., description="数据源标题", min_length=1, max_length=200)
    description: str = Field("", description="数据源描述", max_length=1000)
    # created_by 移除，由后端从 JWT Token 获取
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    ...
```

**Step 2: 验证模型正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api && python -c "from src.api.v1.endpoints.data_source_management import CreateDataSourceRequest; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
git add src/api/v1/endpoints/data_source_management.py
git commit -m "feat(api): 移除 CreateDataSourceRequest.created_by 字段"
```

---

## Task 3: 后端 - 修改 create_data_source 端点

**Files:**
- Modify: `src/api/v1/endpoints/data_source_management.py:109-152`

**Step 1: 添加 JWT 认证依赖并修改 created_by 获取方式**

找到 `create_data_source` 函数（第 109-152 行），添加认证依赖：

改动前：
```python
@router.post("/", status_code=201, summary="创建数据源")
async def create_data_source(
    request: CreateDataSourceRequest,
    service: DataCurationService = Depends(get_data_curation_service)
):
```

改动后：
```python
@router.post("/", status_code=201, summary="创建数据源")
async def create_data_source(
    request: CreateDataSourceRequest,
    current_user: User = Depends(get_current_active_user),
    service: DataCurationService = Depends(get_data_curation_service)
):
```

**Step 2: 修改 service 调用中的 created_by**

改动前：
```python
data_source = await service.create_data_source(
    title=request.title,
    description=request.description,
    created_by=request.created_by,
    ...
)
```

改动后：
```python
data_source = await service.create_data_source(
    title=request.title,
    description=request.description,
    created_by=current_user.id,  # 从 JWT Token 获取
    ...
)
```

**Step 3: 更新文档字符串中的请求示例**

移除请求示例中的 `created_by` 字段：

```python
"""创建新的数据源（草稿状态）

**功能说明：**
- 创建草稿状态的数据源
- 初始状态：DRAFT
- 初始数据量：0
- created_by 从 JWT Token 自动获取

**请求示例：**
```json
{
  "title": "Python Web开发最佳实践",
  "description": "收集Python Web开发相关的优质资源",
  "tags": ["Python", "Web开发", "最佳实践"]
}
```
"""
```

**Step 4: 验证端点正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api && python -c "from src.api.v1.endpoints.data_source_management import create_data_source; print('OK')"`

Expected: `OK`

**Step 5: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
git add src/api/v1/endpoints/data_source_management.py
git commit -m "feat(api): 修改 create_data_source 端点使用 JWT 认证"
```

---

## Task 4: 后端 - 编写单元测试

**Files:**
- Create: `tests/unit/api/test_data_source_management_auth.py`

**Step 1: 创建测试文件**

```python
"""
数据源管理接口认证测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.v1.endpoints.data_source_management import (
    CreateDataSourceRequest,
    create_data_source,
)
from src.core.domain.entities.user import User


class TestCreateDataSourceRequest:
    """CreateDataSourceRequest 模型测试"""

    def test_valid_request_without_created_by(self):
        """测试不含 created_by 的有效请求"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述"
        )
        assert request.title == "测试数据源"
        assert request.description == "测试描述"
        # created_by 字段已移除，不应存在
        assert not hasattr(request, 'created_by') or 'created_by' not in request.model_fields

    def test_valid_request_with_categories(self):
        """测试带分类的有效请求"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述",
            primary_category="安全情报",
            secondary_category="维稳",
            tertiary_category="东亚",
            metadata={
                "category": {
                    "大类": "安全情报",
                    "类别": "维稳",
                    "地域": "东亚"
                }
            }
        )
        assert request.primary_category == "安全情报"
        assert request.metadata["category"]["大类"] == "安全情报"


class TestCreateDataSource:
    """create_data_source 端点测试"""

    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = MagicMock(spec=User)
        user.id = "test_user_123"
        user.is_active = True
        user.is_locked = False
        return user

    @pytest.fixture
    def mock_service(self):
        """模拟数据源服务"""
        service = MagicMock()
        mock_data_source = MagicMock()
        mock_data_source.to_dict.return_value = {
            "id": "ds_123",
            "title": "测试数据源",
            "created_by": "test_user_123"
        }
        service.create_data_source = AsyncMock(return_value=mock_data_source)
        return service

    @pytest.mark.asyncio
    async def test_create_data_source_uses_jwt_user(self, mock_user, mock_service):
        """测试 created_by 从 JWT Token 获取"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述"
        )

        response = await create_data_source(
            request=request,
            current_user=mock_user,
            service=mock_service
        )

        assert response["success"] is True

        # 验证 service 调用时使用了 current_user.id
        mock_service.create_data_source.assert_called_once()
        call_kwargs = mock_service.create_data_source.call_args.kwargs
        assert call_kwargs["created_by"] == "test_user_123"

    @pytest.mark.asyncio
    async def test_create_data_source_with_metadata_category(self, mock_user, mock_service):
        """测试带 metadata.category 的创建"""
        request = CreateDataSourceRequest(
            title="测试数据源",
            description="测试描述",
            primary_category="安全情报",
            metadata={
                "source_type": "file",
                "category": {
                    "大类": "安全情报",
                    "类别": "维稳",
                    "地域": "东亚"
                }
            }
        )

        response = await create_data_source(
            request=request,
            current_user=mock_user,
            service=mock_service
        )

        assert response["success"] is True

        call_kwargs = mock_service.create_data_source.call_args.kwargs
        assert call_kwargs["metadata"]["category"]["大类"] == "安全情报"
```

**Step 2: 运行测试**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api && python -m pytest tests/unit/api/test_data_source_management_auth.py -v`

Expected: 测试通过

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
git add tests/unit/api/test_data_source_management_auth.py
git commit -m "test(api): 添加数据源管理接口认证测试"
```

---

## Task 5: 前端 - 修改 API 类型定义

**Files:**
- Modify: `/Users/lanxionggao/Documents/guanshanCMS/lib/api-types.ts`

**Step 1: 找到 CreateDataSourceRequest 类型并移除 created_by**

找到 `CreateDataSourceRequest` 接口定义，移除 `created_by` 字段：

改动前：
```typescript
export interface CreateDataSourceRequest {
  title: string
  description?: string
  created_by: string
  tags?: string[]
  metadata?: Record<string, any>
  primary_category?: string | null
  secondary_category?: string | null
  tertiary_category?: string | null
  custom_tags?: string[]
}
```

改动后：
```typescript
export interface CreateDataSourceRequest {
  title: string
  description?: string
  // created_by 移除，由后端从 JWT Token 获取
  tags?: string[]
  metadata?: Record<string, any>
  primary_category?: string | null
  secondary_category?: string | null
  tertiary_category?: string | null
  custom_tags?: string[]
}
```

**Step 2: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanCMS
git add lib/api-types.ts
git commit -m "feat(types): 移除 CreateDataSourceRequest.created_by"
```

---

## Task 6: 前端 - 修改文件上传 saveFileEntry 函数

**Files:**
- Modify: `/Users/lanxionggao/Documents/guanshanCMS/app/dashboard/info-generation/input/page.tsx`

**Step 1: 找到 saveFileEntry 函数中的 dataSourcesAPI.create 调用**

找到约第 407-431 行的 `saveFileEntry` 函数，修改 `dataSourcesAPI.create` 调用：

改动前：
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

改动后：
```typescript
await dataSourcesAPI.create({
  title: uploadedFile.title,
  description: uploadedFile.description || contentToSave.substring(0, 500),
  edited_content: contentToSave,
  // created_by 移除，由后端从 JWT Token 获取
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

**关键改动说明：**
1. 移除 `created_by: "current_user"`
2. 移除 `allTags` 合并逻辑，`tags` 只存储自定义标签
3. 添加 `metadata.category` 对象存储分类信息

**Step 2: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanCMS
git add app/dashboard/info-generation/input/page.tsx
git commit -m "feat(input): 修改文件上传移除 created_by，使用 metadata.category"
```

---

## Task 7: 集成测试

**Step 1: 启动后端服务（如果未启动）**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
uvicorn src.main:app --reload --port 8000
```

**Step 2: 使用 curl 测试无 Token 应返回 401**

```bash
curl -X POST "http://localhost:8000/api/v1/data-sources/" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试数据源",
    "description": "测试描述"
  }'
```

Expected: HTTP 401 Unauthorized

**Step 3: 使用 curl 测试有效 Token（替换 YOUR_TOKEN）**

```bash
curl -X POST "http://localhost:8000/api/v1/data-sources/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "测试文件上传数据源",
    "description": "测试描述",
    "tags": ["测试"],
    "metadata": {
      "source_type": "file",
      "category": {
        "大类": "安全情报",
        "类别": "维稳",
        "地域": "东亚"
      }
    }
  }'
```

Expected: 返回 `{"success": true, "message": "数据源创建成功", "data": {...}}`

**Step 4: 验证数据库记录**

检查 `data_sources` 集合中新记录的 `created_by` 是否为 Token 对应的用户 ID。

---

## Task 8: 最终提交和合并准备

**Step 1: 运行所有相关测试**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-file-upload-api
python -m pytest tests/unit/api/test_data_source_management_auth.py -v
```

**Step 2: 查看所有提交**

```bash
git log --oneline -10
```

**Step 3: 准备合并**

分支 `feature/file-upload-api` 已准备好合并到主分支。

---

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `src/api/v1/endpoints/data_source_management.py` | 修改 | 添加认证导入，移除 `created_by` 字段，添加 JWT 认证 |
| `tests/unit/api/test_data_source_management_auth.py` | 新增 | 认证相关单元测试 |
| `guanshanCMS/lib/api-types.ts` | 修改 | 移除 `CreateDataSourceRequest.created_by` |
| `guanshanCMS/app/dashboard/info-generation/input/page.tsx` | 修改 | 文件上传移除 `created_by`，使用 `metadata.category` |

## 注意事项

1. **认证必须**：修改后的接口强制要求 JWT 认证，未登录用户无法调用
2. **向后不兼容**：移除 `created_by` 字段是破坏性变更，需确保前端同步更新
3. **分类格式**：使用 `metadata.category` 格式（大类/类别/地域）与系统保持一致
4. **标签分离**：`tags` 只存储自定义标签，分类信息存入 `metadata.category`
