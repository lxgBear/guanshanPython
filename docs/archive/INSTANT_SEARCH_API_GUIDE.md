# 即时搜索API使用指南

**文档地址**: http://localhost:8000/api/docs

**创建日期**: 2025-10-16

---

## 📋 目录

1. [API概述](#api概述)
2. [可用端点](#可用端点)
3. [使用示例](#使用示例)
4. [前端集成](#前端集成)

---

## API概述

即时搜索API（v1.3.0）提供了实时网页爬取和搜索功能，支持两种模式:

- **Crawl模式**: 爬取指定URL的内容（推荐，稳定可靠）
- **Search模式**: 通过关键词搜索网页（需要付费API密钥）

### 核心特性

✅ **跨搜索去重**: content_hash机制确保相同内容只存储一次
✅ **映射表架构**: 多对多关系，结果可跨搜索共享
✅ **发现统计**: 追踪结果被发现次数和首次发现时间
✅ **实时响应**: 即时返回搜索结果，无需等待后台任务

---

## 可用端点

### 1. 创建即时搜索任务

**端点**: `POST /api/v1/instant-search-tasks`
**标签**: ⚡ 即时搜索
**状态码**: 201 Created

**请求体**:
```json
{
  "name": "任务名称",
  "crawl_url": "https://example.com",
  "search_config": {
    "limit": 10
  },
  "created_by": "frontend_user"
}
```

**响应示例**:
```json
{
  "id": "237066331858059264",
  "name": "API测试-Crawl模式",
  "search_mode": "crawl",
  "status": "completed",
  "total_results": 1,
  "new_results": 1,
  "shared_results": 0,
  "execution_time_ms": 5619,
  "created_at": "2025-10-16T04:16:57Z"
}
```

### 2. 获取任务详情

**端点**: `GET /api/v1/instant-search-tasks/{task_id}`
**标签**: ⚡ 即时搜索
**状态码**: 200 OK

**响应示例**:
```json
{
  "id": "237066331858059264",
  "name": "API测试-Crawl模式",
  "crawl_url": "https://example.com",
  "status": "completed",
  "total_results": 1,
  "search_execution_id": "exec_237066331858059265"
}
```

### 3. 获取搜索结果

**端点**: `GET /api/v1/instant-search-tasks/{task_id}/results`
**标签**: ⚡ 即时搜索
**状态码**: 200 OK
**查询参数**:
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认20，最大100）

**响应示例**:
```json
{
  "results": [
    {
      "result": {
        "id": "237066355383910400",
        "title": "Example Domain",
        "url": "https://example.com",
        "content": "This domain is for use in illustrative examples...",
        "markdown_content": "# Example Domain\n\n...",
        "found_count": 4,
        "unique_searches": 4,
        "first_found_at": "2025-10-16T04:16:57Z",
        "last_found_at": "2025-10-16T04:55:12Z"
      },
      "mapping_info": {
        "search_execution_id": "exec_237066331858059265",
        "search_position": 1,
        "is_first_discovery": false,
        "relevance_score": 1.0,
        "found_at": "2025-10-16T04:55:12Z"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 4. 获取任务列表

**端点**: `GET /api/v1/instant-search-tasks`
**标签**: ⚡ 即时搜索
**状态码**: 200 OK
**查询参数**:
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认20，最大100）
- `status`: 状态过滤（pending, running, completed, failed）

---

## 使用示例

### Crawl模式（推荐）

```bash
# 1. 创建Crawl任务
curl -X POST "http://localhost:8000/api/v1/instant-search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "爬取示例网站",
    "crawl_url": "https://example.com",
    "search_config": {"limit": 1},
    "created_by": "test_user"
  }'

# 响应: {"id": "237066331858059264", "status": "completed", ...}

# 2. 获取任务详情
curl "http://localhost:8000/api/v1/instant-search-tasks/237066331858059264"

# 3. 获取搜索结果
curl "http://localhost:8000/api/v1/instant-search-tasks/237066331858059264/results?page=1&page_size=10"
```

### Search模式（需付费密钥）

```bash
# 创建Search任务
curl -X POST "http://localhost:8000/api/v1/instant-search-tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "关键词搜索",
    "query": "python async programming",
    "search_config": {"limit": 5},
    "created_by": "test_user"
  }'
```

### 分页查询

```bash
# 获取第2页，每页20条
curl "http://localhost:8000/api/v1/instant-search-tasks/237066331858059264/results?page=2&page_size=20"

# 获取所有completed状态的任务
curl "http://localhost:8000/api/v1/instant-search-tasks?status=completed&page=1&page_size=50"
```

---

## 前端集成

### JavaScript/TypeScript 示例

```typescript
// 定义类型
interface InstantSearchRequest {
  name: string;
  crawl_url?: string;
  query?: string;
  search_config?: {
    limit?: number;
  };
  created_by?: string;
}

interface InstantSearchTask {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_results: number;
  new_results: number;
  shared_results: number;
  execution_time_ms: number;
  created_at: string;
}

interface SearchResult {
  result: {
    id: string;
    title: string;
    url: string;
    content: string;
    markdown_content?: string;
    found_count: number;
    unique_searches: number;
  };
  mapping_info: {
    search_position: number;
    is_first_discovery: boolean;
    found_at: string;
  };
}

// API调用函数
class InstantSearchAPI {
  private baseUrl = 'http://localhost:8000/api/v1';

  async createTask(request: InstantSearchRequest): Promise<InstantSearchTask> {
    const response = await fetch(`${this.baseUrl}/instant-search-tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return response.json();
  }

  async getTask(taskId: string): Promise<InstantSearchTask> {
    const response = await fetch(`${this.baseUrl}/instant-search-tasks/${taskId}`);
    return response.json();
  }

  async getResults(taskId: string, page = 1, pageSize = 20) {
    const response = await fetch(
      `${this.baseUrl}/instant-search-tasks/${taskId}/results?page=${page}&page_size=${pageSize}`
    );
    return response.json();
  }

  async listTasks(page = 1, pageSize = 20, status?: string) {
    const url = new URL(`${this.baseUrl}/instant-search-tasks`);
    url.searchParams.set('page', page.toString());
    url.searchParams.set('page_size', pageSize.toString());
    if (status) url.searchParams.set('status', status);

    const response = await fetch(url.toString());
    return response.json();
  }
}

// 使用示例
const api = new InstantSearchAPI();

// 创建Crawl任务
const task = await api.createTask({
  name: '爬取新闻网站',
  crawl_url: 'https://news.example.com',
  search_config: { limit: 10 },
  created_by: 'frontend_app'
});

console.log(`任务创建成功: ${task.id}`);
console.log(`执行时间: ${task.execution_time_ms}ms`);
console.log(`总结果: ${task.total_results}, 新结果: ${task.new_results}`);

// 获取搜索结果
const results = await api.getResults(task.id, 1, 20);
results.results.forEach(item => {
  console.log(`标题: ${item.result.title}`);
  console.log(`URL: ${item.result.url}`);
  console.log(`被发现次数: ${item.result.found_count}`);
});
```

### React Hook 示例

```typescript
import { useState, useCallback } from 'react';

function useInstantSearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const api = new InstantSearchAPI();

  const crawlUrl = useCallback(async (url: string, name?: string) => {
    setLoading(true);
    setError(null);

    try {
      const task = await api.createTask({
        name: name || `爬取: ${url}`,
        crawl_url: url,
        created_by: 'react_app'
      });

      const results = await api.getResults(task.id);
      return { task, results };
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { crawlUrl, loading, error };
}

// 组件中使用
function SearchComponent() {
  const { crawlUrl, loading, error } = useInstantSearch();

  const handleSearch = async () => {
    const { task, results } = await crawlUrl('https://example.com');
    console.log('搜索完成:', task, results);
  };

  return (
    <div>
      <button onClick={handleSearch} disabled={loading}>
        {loading ? '搜索中...' : '开始搜索'}
      </button>
      {error && <p>错误: {error.message}</p>}
    </div>
  );
}
```

---

## 注意事项

### 1. API模式选择

- **优先使用Crawl模式**: 基于Scrape API，稳定可靠，响应时间5-10秒
- **Search模式需要付费密钥**: 免费密钥可能超时或受限

### 2. 去重机制

- 相同URL + title + content 的结果只存储一次
- `new_results`: 本次搜索发现的新内容数量
- `shared_results`: 本次搜索命中的已存在内容数量
- `found_count`: 该结果被发现的总次数（跨所有搜索）

### 3. 性能建议

- 合理设置 `search_config.limit`，避免爬取过多页面
- 使用分页查询，每页20-50条为宜
- 监控 `execution_time_ms`，超过30秒可能超时

### 4. 错误处理

- 400: 参数错误（必须提供query或crawl_url）
- 404: 任务不存在
- 500: 服务器错误（Firecrawl API失败、数据库错误）

---

## 测试结果

根据 `V1.3.0_FINAL_TEST_RESULTS.md` 的综合测试:

✅ **Crawl模式**: 100%通过，生产就绪
✅ **去重机制**: 100%准确
✅ **数据完整性**: 100%正确
✅ **API响应**: 正常工作
⚠️ **Search模式**: 受API限制，不推荐在免费版使用

---

## 更多信息

- 完整测试报告: `claudedocs/V1.3.0_FINAL_TEST_RESULTS.md`
- 测试脚本: `scripts/test_crawl_mode_complete.py`
- API文档: http://localhost:8000/api/docs
- OpenAPI Spec: http://localhost:8000/api/openapi.json
