# 翻译内容录入接口实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现手动录入翻译内容的 API 接口，将用户输入的翻译内容入库到 news_results 集合。

**Architecture:** 在 `search_results_manual.py` 中新增 `TranslatedContentRequest` 模型和 `/manual/translated` 端点。用户录入的内容完整保存到 `snippet` 和 `markdown_content`，分类信息存入 `metadata.category` 兼容现有系统格式。

**Tech Stack:** FastAPI, Pydantic, MongoDB (motor), JWT 认证

---

## Task 1: 后端 - 新增请求模型

**Files:**
- Modify: `src/api/v1/endpoints/search_results_manual.py:27-53`

**Step 1: 在 ManualAddRequest 之后添加 TranslatedContentRequest 模型**

在 `search_results_manual.py` 文件中，找到 `ManualAddRequest` 类定义结束位置（约第 53 行），在其后添加新模型：

```python
class TranslatedContentRequest(BaseModel):
    """手动录入翻译内容请求

    用于用户直接录入翻译后的内容，无需关联已有任务。
    task_id 和 user_id 由后端自动生成/获取。
    """
    title: str = Field(..., description="标题", min_length=1, max_length=500)
    content: str = Field(..., description="翻译后的内容（完整保存）", min_length=1)
    url: Optional[str] = Field(None, description="来源URL")
    published_date: Optional[datetime] = Field(None, description="发布日期")
    primary_category: Optional[str] = Field(None, description="一级分类（大类）")
    secondary_category: Optional[str] = Field(None, description="二级分类（类别）")
    tertiary_category: Optional[str] = Field(None, description="三级分类（地域）")
    tags: Optional[List[str]] = Field(None, description="自定义标签")
    notes: Optional[str] = Field(None, description="备注")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "某国安全局发布年度威胁评估报告",
                "content": "根据最新发布的年度威胁评估报告，该国面临的主要安全威胁包括...",
                "url": "https://example.com/report",
                "primary_category": "安全情报",
                "secondary_category": "类别",
                "tertiary_category": "东亚",
                "tags": ["年度报告", "威胁评估"]
            }
        }
```

**Step 2: 验证语法正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input && python -c "from src.api.v1.endpoints.search_results_manual import TranslatedContentRequest; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
git add src/api/v1/endpoints/search_results_manual.py
git commit -m "feat(api): 添加 TranslatedContentRequest 请求模型"
```

---

## Task 2: 后端 - 添加认证依赖导入

**Files:**
- Modify: `src/api/v1/endpoints/search_results_manual.py` (文件顶部导入区)

**Step 1: 检查现有导入并添加认证相关导入**

在文件顶部的导入区域，添加获取当前用户的依赖：

```python
from src.api.v1.dependencies.auth import get_current_user
from src.core.domain.entities.user import User
```

**Step 2: 验证导入正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input && python -c "from src.api.v1.endpoints.search_results_manual import router; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
git add src/api/v1/endpoints/search_results_manual.py
git commit -m "feat(api): 添加认证依赖导入"
```

---

## Task 3: 后端 - 实现 API 端点

**Files:**
- Modify: `src/api/v1/endpoints/search_results_manual.py` (文件末尾)

**Step 1: 在文件末尾添加新端点**

在 `crawl_and_add_search_result` 函数之后添加新端点：

```python
@router.post(
    "/manual/translated",
    response_model=ManualAddResponse,
    summary="手动录入翻译内容",
    description="用户录入翻译后的内容，入库到 news_results。task_id 自动生成，user_id 从 Token 获取。"
)
async def add_translated_content(
    request: TranslatedContentRequest,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """手动录入翻译内容

    **功能说明：**
    - 用户录入翻译后的内容
    - task_id 使用雪花算法自动生成
    - user_id/created_by 从 JWT Token 获取
    - content 完整保存到 snippet 和 markdown_content
    - 分类信息存入 metadata.category（兼容现有格式）

    **数据流程：**
    1. 从 Token 获取用户信息
    2. 生成 task_id（雪花算法）
    3. 构建 metadata（包含分类、标签、备注）
    4. 创建 SearchResult 实体
    5. 保存到数据库
    """
    try:
        # 生成 task_id（雪花算法）
        task_id = generate_string_id()

        # 构建 metadata（兼容现有分类格式）
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

        # 生成 content_hash
        result.ensure_content_hash()

        # 保存到数据库
        await db.search_results.insert_one(result.__dict__)

        logger.info(
            f"翻译内容录入成功: id={result.id}, title={request.title[:50]}, user={current_user.id}"
        )

        return ManualAddResponse(
            success=True,
            message="翻译内容录入成功",
            data=search_result_to_dict(result)
        )

    except Exception as e:
        logger.error(f"翻译内容录入失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"录入失败: {str(e)}")
```

**Step 2: 验证语法正确**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input && python -c "from src.api.v1.endpoints.search_results_manual import add_translated_content; print('OK')"`

Expected: `OK`

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
git add src/api/v1/endpoints/search_results_manual.py
git commit -m "feat(api): 实现 /manual/translated 端点"
```

---

## Task 4: 后端 - 编写单元测试

**Files:**
- Create: `tests/unit/api/test_search_results_manual_translated.py`

**Step 1: 创建测试文件**

```python
"""
翻译内容录入接口单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.api.v1.endpoints.search_results_manual import (
    TranslatedContentRequest,
    add_translated_content,
)
from src.core.domain.entities.user import User


class TestTranslatedContentRequest:
    """TranslatedContentRequest 模型测试"""

    def test_valid_minimal_request(self):
        """测试最小有效请求"""
        request = TranslatedContentRequest(
            title="测试标题",
            content="测试内容"
        )
        assert request.title == "测试标题"
        assert request.content == "测试内容"
        assert request.url is None
        assert request.primary_category is None

    def test_valid_full_request(self):
        """测试完整请求"""
        request = TranslatedContentRequest(
            title="完整测试标题",
            content="完整测试内容",
            url="https://example.com",
            published_date=datetime(2026, 1, 26),
            primary_category="安全情报",
            secondary_category="类别",
            tertiary_category="东亚",
            tags=["标签1", "标签2"],
            notes="备注信息"
        )
        assert request.title == "完整测试标题"
        assert request.primary_category == "安全情报"
        assert len(request.tags) == 2

    def test_invalid_empty_title(self):
        """测试空标题应失败"""
        with pytest.raises(ValueError):
            TranslatedContentRequest(
                title="",
                content="测试内容"
            )

    def test_invalid_empty_content(self):
        """测试空内容应失败"""
        with pytest.raises(ValueError):
            TranslatedContentRequest(
                title="测试标题",
                content=""
            )


class TestAddTranslatedContent:
    """add_translated_content 端点测试"""

    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = MagicMock(spec=User)
        user.id = "test_user_123"
        return user

    @pytest.fixture
    def mock_db(self):
        """模拟数据库"""
        db = MagicMock()
        db.search_results = MagicMock()
        db.search_results.insert_one = AsyncMock(return_value=MagicMock())
        return db

    @pytest.mark.asyncio
    async def test_add_translated_content_success(self, mock_user, mock_db):
        """测试成功录入翻译内容"""
        request = TranslatedContentRequest(
            title="测试翻译内容",
            content="这是翻译后的内容，完整保存。",
            primary_category="安全情报",
            secondary_category="维稳",
            tertiary_category="东亚"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_123456", "result_789"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True
        assert response.message == "翻译内容录入成功"
        assert response.data["title"] == "测试翻译内容"

        # 验证数据库调用
        mock_db.search_results.insert_one.assert_called_once()
        inserted_data = mock_db.search_results.insert_one.call_args[0][0]

        # 验证字段映射
        assert inserted_data["user_id"] == "test_user_123"
        assert inserted_data["created_by"] == "test_user_123"
        assert inserted_data["snippet"] == "这是翻译后的内容，完整保存。"
        assert inserted_data["markdown_content"] == "这是翻译后的内容，完整保存。"
        assert inserted_data["source"] == "translated"
        assert inserted_data["language"] == "zh-CN"

        # 验证 metadata 分类格式
        assert inserted_data["metadata"]["category"]["大类"] == "安全情报"
        assert inserted_data["metadata"]["category"]["类别"] == "维稳"
        assert inserted_data["metadata"]["category"]["地域"] == "东亚"
        assert inserted_data["metadata"]["input_type"] == "translated"

    @pytest.mark.asyncio
    async def test_add_translated_content_minimal(self, mock_user, mock_db):
        """测试最小字段录入"""
        request = TranslatedContentRequest(
            title="最小测试",
            content="最小内容"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_min", "result_min"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True

        inserted_data = mock_db.search_results.insert_one.call_args[0][0]
        assert inserted_data["url"] == ""
        assert inserted_data["metadata"]["category"]["大类"] is None
        assert inserted_data["metadata"]["tags"] == []

    @pytest.mark.asyncio
    async def test_add_translated_content_with_tags(self, mock_user, mock_db):
        """测试带标签录入"""
        request = TranslatedContentRequest(
            title="带标签测试",
            content="带标签内容",
            tags=["标签A", "标签B", "标签C"],
            notes="这是备注"
        )

        with patch(
            "src.api.v1.endpoints.search_results_manual.generate_string_id",
            side_effect=["task_tags", "result_tags"]
        ):
            response = await add_translated_content(
                request=request,
                current_user=mock_user,
                db=mock_db
            )

        assert response.success is True

        inserted_data = mock_db.search_results.insert_one.call_args[0][0]
        assert inserted_data["metadata"]["tags"] == ["标签A", "标签B", "标签C"]
        assert inserted_data["metadata"]["notes"] == "这是备注"
```

**Step 2: 运行测试验证失败（TDD）**

Run: `cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input && python -m pytest tests/unit/api/test_search_results_manual_translated.py -v`

Expected: 测试应该通过（因为实现已在 Task 3 完成）

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
git add tests/unit/api/test_search_results_manual_translated.py
git commit -m "test(api): 添加翻译内容录入接口单元测试"
```

---

## Task 5: 前端 - 添加 API 类型定义

**Files:**
- Modify: `/Users/lanxionggao/Documents/guanshanCMS/lib/api-types.ts`

**Step 1: 在文件末尾添加类型定义**

```typescript
// ============================================================================
// 手动录入翻译内容 API 类型
// ============================================================================

/**
 * 手动录入翻译内容请求
 */
export interface TranslatedContentRequest {
  /** 标题（必填） */
  title: string
  /** 翻译后的内容（必填，完整保存） */
  content: string
  /** 来源URL */
  url?: string
  /** 发布日期 */
  published_date?: string
  /** 一级分类（大类） */
  primary_category?: string
  /** 二级分类（类别） */
  secondary_category?: string
  /** 三级分类（地域） */
  tertiary_category?: string
  /** 自定义标签 */
  tags?: string[]
  /** 备注 */
  notes?: string
}

/**
 * 手动录入响应
 */
export interface ManualAddResponse {
  success: boolean
  message: string
  data: {
    id: string
    task_id: string
    title: string
    url: string
    snippet: string
    source: string
    status: string
    created_at: string
    [key: string]: any
  }
}
```

**Step 2: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanCMS
git add lib/api-types.ts
git commit -m "feat(types): 添加翻译内容录入 API 类型定义"
```

---

## Task 6: 前端 - 添加 API 方法

**Files:**
- Modify: `/Users/lanxionggao/Documents/guanshanCMS/lib/api-client.ts`

**Step 1: 在文件中添加 searchResultsManualAPI 对象**

在 `dataSourcesAPI` 对象之后添加：

```typescript
// ============================================================================
// 搜索结果手动录入 API
// ============================================================================

export const searchResultsManualAPI = {
  /**
   * 手动录入翻译内容
   * @param data 翻译内容数据
   * @returns 录入结果
   */
  addTranslated: async (data: import('./api-types').TranslatedContentRequest): Promise<import('./api-types').ManualAddResponse> => {
    const { data: result } = await apiClient.post<import('./api-types').ManualAddResponse>(
      '/search-results/manual/translated',
      data
    )
    return result
  }
}
```

**Step 2: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanCMS
git add lib/api-client.ts
git commit -m "feat(api): 添加 searchResultsManualAPI.addTranslated 方法"
```

---

## Task 7: 前端 - 修改录入页面

**Files:**
- Modify: `/Users/lanxionggao/Documents/guanshanCMS/app/dashboard/info-generation/input/page.tsx`

**Step 1: 添加新 API 导入**

找到导入区域（约第 44 行），修改导入：

```typescript
// 原来的导入
import { fileUploadAPI, dataSourcesAPI } from "@/lib/api-client"

// 改为
import { fileUploadAPI, dataSourcesAPI, searchResultsManualAPI } from "@/lib/api-client"
```

**Step 2: 修改 submitTextEntry 函数**

找到 `submitTextEntry` 函数（约第 188-233 行），替换为：

```typescript
const submitTextEntry = async () => {
  if (!textForm.title.trim()) {
    toast.error("请输入标题")
    return
  }
  if (!textForm.content.trim()) {
    toast.error("请输入内容")
    return
  }
  if (!textForm.primaryCategory) {
    toast.error("请选择分类")
    return
  }

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

**Step 3: Commit**

```bash
cd /Users/lanxionggao/Documents/guanshanCMS
git add app/dashboard/info-generation/input/page.tsx
git commit -m "feat(input): 修改文本录入调用新的翻译内容接口"
```

---

## Task 8: 集成测试

**Step 1: 启动后端服务（如果未启动）**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
# 确保有 .env 配置
uvicorn src.main:app --reload --port 8000
```

**Step 2: 使用 curl 测试接口（需要有效 Token）**

```bash
# 替换 YOUR_TOKEN 为有效的 JWT Token
curl -X POST "http://localhost:8000/api/v1/search-results/manual/translated" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "测试翻译内容",
    "content": "这是一条测试的翻译内容，用于验证接口是否正常工作。",
    "primary_category": "安全情报",
    "secondary_category": "维稳",
    "tertiary_category": "东亚",
    "tags": ["测试", "集成测试"]
  }'
```

Expected: 返回 `{"success": true, "message": "翻译内容录入成功", "data": {...}}`

**Step 3: 验证数据库记录**

```bash
# 使用 MongoDB shell 或 Compass 查看
mongosh --eval 'db.search_results.find({"source": "translated"}).sort({created_at: -1}).limit(1).pretty()'
```

---

## Task 9: 最终提交和合并准备

**Step 1: 运行所有相关测试**

```bash
cd /Users/lanxionggao/Documents/guanshanPython/.worktrees/feature-translated-input
python -m pytest tests/unit/api/test_search_results_manual_translated.py -v
```

**Step 2: 查看所有提交**

```bash
git log --oneline -10
```

**Step 3: 准备合并**

分支 `feature/translated-content-input` 已准备好合并到主分支。

---

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|-----|---------|------|
| `src/api/v1/endpoints/search_results_manual.py` | 修改 | 新增模型和端点 |
| `tests/unit/api/test_search_results_manual_translated.py` | 新增 | 单元测试 |
| `guanshanCMS/lib/api-types.ts` | 修改 | 类型定义 |
| `guanshanCMS/lib/api-client.ts` | 修改 | API 方法 |
| `guanshanCMS/app/dashboard/info-generation/input/page.tsx` | 修改 | 页面调用 |
