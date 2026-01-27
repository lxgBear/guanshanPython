# 统一聚合 API 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建统一聚合 API，解决 N+1 查询问题，实现服务端筛选、排序、分页

**Architecture:** 使用 MongoDB 聚合管道从多个集合查询数据，在服务端完成筛选、排序和分页

**Tech Stack:** FastAPI, MongoDB (motor), Pydantic

---

## 背景

当前 `/dashboard/info-generation/generate/single` 页面存在以下问题：
1. **N+1 查询** - 前端需要先获取任务列表，再逐个获取每个任务的结果
2. **客户端筛选** - 所有筛选都在前端完成，数据量大时性能差
3. **无统一分页** - 无法实现真正的服务端分页

## 数据源映射

| 采集方式 | MongoDB 集合 | 任务集合 | source_type |
|----------|--------------|----------|-------------|
| 定时任务 | `search_results` | `search_tasks` | `scheduled` |
| 智能搜索 | `instant_search_results` | `instant_search_tasks` | `smart-search` |
| Chat搜索 | `langgraph_search_results` | `chat_v2_tasks` | `chat-search` |
| 文档上传 | `data_sources` | - | `upload` |

---

## Task 1: 创建 Pydantic 模型

**Files:**
- Create: `src/api/v1/endpoints/unified_results.py`

**Step 1: 创建请求和响应模型**

```python
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class SourceType(str, Enum):
    ALL = "all"
    SCHEDULED = "scheduled"
    SMART_SEARCH = "smart-search"
    CHAT_SEARCH = "chat-search"
    UPLOAD = "upload"

class TimeRange(str, Enum):
    ALL = "all"
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    CUSTOM = "custom"

class UnifiedResultItem(BaseModel):
    """统一结果项"""
    id: str
    title: str
    url: str
    snippet: Optional[str] = None
    source_type: str  # scheduled, smart-search, chat-search, upload
    source_type_name: str  # 显示名称
    origin_site: str  # 数据来源网站
    task_id: str
    published_date: Optional[str] = None
    created_at: Optional[str] = None
    original_content: Optional[str] = None
    translated_content: Optional[str] = None

class SourceTypeStats(BaseModel):
    """按来源类型统计"""
    scheduled: int = 0
    smart_search: int = Field(0, alias="smart-search")
    chat_search: int = Field(0, alias="chat-search")
    upload: int = 0

class UnifiedResultsResponse(BaseModel):
    """统一结果响应"""
    items: List[UnifiedResultItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    statistics: Optional[Dict[str, Any]] = None
```

---

## Task 2: 创建统一结果仓储层

**Files:**
- Create: `src/infrastructure/persistence/repositories/mongo/unified_result_repository.py`

**Step 1: 实现仓储类**

```python
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

class UnifiedResultRepository:
    """统一结果仓储 - 聚合多个数据源"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def query_unified_results(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        source_type: str = "all",
        time_range: str = "all",
        date_start: Optional[datetime] = None,
        date_end: Optional[datetime] = None,
        task_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Dict], int, Dict[str, int]]:
        """
        统一查询多个数据源的结果

        Returns:
            (items, total, statistics)
        """
        # 实现聚合查询逻辑
        pass
```

---

## Task 3: 实现 API 端点

**Files:**
- Modify: `src/api/v1/endpoints/unified_results.py`

**Step 1: 创建 GET /unified-results 端点**

```python
@router.get(
    "/",
    response_model=UnifiedResultsResponse,
    summary="获取统一聚合结果",
    description="从多个数据源聚合查询结果，支持服务端筛选、排序、分页"
)
async def get_unified_results(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    source_type: str = Query("all", description="采集方式筛选"),
    time_range: str = Query("all", description="时间范围"),
    date_start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    task_id: Optional[str] = Query(None, description="任务ID筛选"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    current_user: User = Depends(get_current_active_user)
):
    pass
```

---

## Task 4: 注册路由

**Files:**
- Modify: `src/api/v1/router.py`

**Step 1: 添加路由注册**

```python
from src.api.v1.endpoints import unified_results

router.include_router(
    unified_results.router,
    prefix="/unified-results",
    tags=["📊 统一聚合结果"]
)
```

---

## Task 5: 更新前端 API 客户端

**Files:**
- Modify: `guanshanCMS/lib/api-client.ts`
- Modify: `guanshanCMS/lib/api-types.ts`

**Step 1: 添加类型定义**

```typescript
// api-types.ts
export interface UnifiedResultItem {
  id: string
  title: string
  url: string
  snippet?: string
  source_type: "scheduled" | "smart-search" | "chat-search" | "upload"
  source_type_name: string
  origin_site: string
  task_id: string
  published_date?: string
  created_at?: string
  original_content?: string
  translated_content?: string
}

export interface UnifiedResultsResponse {
  items: UnifiedResultItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  statistics?: {
    by_source_type: Record<string, number>
  }
}

export interface UnifiedResultsParams {
  page?: number
  page_size?: number
  keyword?: string
  source_type?: string
  time_range?: string
  date_start?: string
  date_end?: string
  task_id?: string
  sort_by?: string
  sort_order?: string
}
```

**Step 2: 添加 API 方法**

```typescript
// api-client.ts
export const unifiedResultsAPI = {
  getResults: async (params?: UnifiedResultsParams): Promise<UnifiedResultsResponse> => {
    const query = buildQueryString(params)
    const { data } = await apiClient.get(`/unified-results${query}`)
    return data
  }
}
```

---

## Task 6: 更新前端页面

**Files:**
- Modify: `guanshanCMS/app/dashboard/info-generation/generate/single/page.tsx`

**Step 1: 替换数据获取逻辑**

将原有的多次 API 调用替换为单次 `unifiedResultsAPI.getResults()` 调用。

---

## Task 7: 测试验证

**Step 1: 后端 API 测试**

```bash
curl -X GET "http://localhost:8003/api/v1/unified-results?page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

**Step 2: 前端集成测试**

验证页面筛选、分页、排序功能正常工作。

---

## 实现顺序

1. Task 1 + Task 2: 后端模型和仓储层
2. Task 3 + Task 4: API 端点和路由注册
3. Task 5: 前端类型和 API 客户端
4. Task 6: 前端页面更新
5. Task 7: 测试验证
