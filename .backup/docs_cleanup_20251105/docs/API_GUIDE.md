# API 使用指南

**版本**: v1.3.0 | **服务地址**: `http://localhost:8000/api/v1/`

---

## API 概览

### 核心功能模块

| 模块 | 端点前缀 | 说明 |
|------|---------|------|
| 搜索任务 | `/search-tasks/` | CRUD操作 |
| 搜索结果 | `/search-tasks/{id}/results` | 查询结果 |
| 调度器 | `/scheduler/` | 调度管理 |
| 即时搜索 | `/instant-search/` | 一次性搜索 |

### 认证方式

当前版本: **无需认证** (开发环境)
生产环境: 计划支持API Key认证

---

## 搜索任务API

### 创建任务

```http
POST /api/v1/search-tasks/
Content-Type: application/json

{
  "name": "特朗普贸易战监控",
  "query": "特朗普 贸易战 关税",
  "schedule_interval": "HOURLY",
  "is_active": true,
  "search_config": {
    "limit": 10,
    "time_range": "month",
    "language": "zh"
  }
}
```

**响应** (201 Created):
```json
{
  "id": "237408060762787840",
  "name": "特朗普贸易战监控",
  "query": "特朗普 贸易战 关税",
  "schedule_interval": "HOURLY",
  "is_active": true,
  "execution_count": 0,
  "created_at": "2025-10-17T06:00:00Z"
}
```

### 查询任务列表

```http
GET /api/v1/search-tasks/?page=1&page_size=10&is_active=true
```

**参数**:
- `page`: 页码 (默认1)
- `page_size`: 每页数量 (默认10, 最大100)
- `is_active`: 过滤活跃任务 (可选)

**响应**:
```json
{
  "items": [...],
  "total": 5,
  "page": 1,
  "page_size": 10
}
```

### 查询单个任务

```http
GET /api/v1/search-tasks/{task_id}
```

### 更新任务

```http
PUT /api/v1/search-tasks/{task_id}
Content-Type: application/json

{
  "name": "更新后的名称",
  "schedule_interval": "DAILY",
  "is_active": false
}
```

### 删除任务

```http
DELETE /api/v1/search-tasks/{task_id}
```

---

## 搜索结果API

### 查询任务结果

```http
GET /api/v1/search-tasks/{task_id}/results?page=1&page_size=10
```

**响应**:
```json
{
  "items": [
    {
      "id": "237408060762788001",
      "task_id": "237408060762787840",
      "title": "中国对特朗普亮出最强底牌",
      "url": "https://...",
      "content": "...",
      "published_date": "2025-10-15",
      "relevance_score": 0.95,
      "created_at": "2025-10-17T06:26:30Z"
    }
  ],
  "total": 10,
  "page": 1
}
```

### 结果字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 标题 |
| `url` | string | 原文链接 |
| `content` | string | 内容摘要(最多5000字符) |
| `snippet` | string | 简短摘要(~200字符) |
| `markdown_content` | string | Markdown格式内容 |
| `html_content` | string | HTML格式内容 |
| `published_date` | datetime | 发布时间 |
| `relevance_score` | float | 相关性评分(0-1) |
| `language` | string | 语言代码(zh/en) |

---

## 调度器API

### 查看调度器状态

```http
GET /api/v1/scheduler/status
```

**响应**:
```json
{
  "status": "running",
  "active_jobs": 3,
  "next_run_time": "2025-10-17T15:00:00Z",
  "jobs": [
    {
      "id": "search_task_237408060762787840",
      "name": "搜索任务: 特朗普贸易战监控",
      "next_run_time": "2025-10-17T15:00:00Z"
    }
  ]
}
```

### 手动执行任务

```http
POST /api/v1/scheduler/tasks/{task_id}/execute
```

**响应** (200 OK):
```json
{
  "task_id": "237408060762787840",
  "task_name": "特朗普贸易战监控",
  "executed_at": "2025-10-17T06:26:30Z",
  "status": "completed",
  "last_execution_success": true,
  "execution_count": 2
}
```

### 查看正在运行的任务

```http
GET /api/v1/scheduler/running-tasks
```

### 健康检查

```http
GET /api/v1/scheduler/health
```

---

## 即时搜索API

### 执行即时搜索

无需创建任务,直接搜索获取结果:

```http
POST /api/v1/instant-search/
Content-Type: application/json

{
  "query": "人工智能 最新进展",
  "config": {
    "limit": 20,
    "time_range": "week",
    "language": "zh"
  }
}
```

**响应** (200 OK):
```json
{
  "query": "人工智能 最新进展",
  "results": [...],
  "total_count": 20,
  "execution_time_ms": 3450,
  "credits_used": 1
}
```

---

## 搜索配置参数

### 通用配置

```json
{
  "limit": 10,              // 结果数量 (1-100)
  "time_range": "month",    // 时间范围
  "language": "zh",         // 语言
  "include_domains": []     // 限定域名
}
```

### 时间范围选项

| 值 | 说明 | Firecrawl参数 |
|----|------|--------------|
| `day` | 最近24小时 | `qdr:d` |
| `week` | 最近一周 | `qdr:w` |
| `month` | 最近一月 | `qdr:m` |
| `year` | 最近一年 | `qdr:y` |

### 语言选项

| 值 | 说明 |
|----|------|
| `zh` | 中文 |
| `en` | 英文 |
| `auto` | 自动检测 |

### 域名限定示例

```json
{
  "include_domains": [
    "nytimes.com",
    "reuters.com",
    "bbc.com"
  ]
}
```

---

## 错误处理

### 标准错误响应

```json
{
  "detail": "任务不存在: 237408060762787840",
  "status_code": 404
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |
| 503 | 调度器未运行 |

### 常见错误

**1. 任务未找到**
```json
{
  "detail": "任务不存在: xxx",
  "status_code": 404
}
```

**2. 调度器未运行**
```json
{
  "detail": "调度器未运行，无法执行任务",
  "status_code": 503
}
```

**3. 参数验证失败**
```json
{
  "detail": "schedule_interval必须是有效的枚举值",
  "status_code": 400
}
```

---

## 使用示例

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 创建任务
response = requests.post(
    f"{BASE_URL}/search-tasks/",
    json={
        "name": "AI新闻监控",
        "query": "人工智能",
        "schedule_interval": "HOURLY",
        "is_active": True
    }
)
task = response.json()
task_id = task["id"]

# 手动执行
requests.post(f"{BASE_URL}/scheduler/tasks/{task_id}/execute")

# 查询结果
results = requests.get(
    f"{BASE_URL}/search-tasks/{task_id}/results"
).json()

print(f"获取到 {len(results['items'])} 条结果")
```

### curl

```bash
# 创建任务
curl -X POST http://localhost:8000/api/v1/search-tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试任务",
    "query": "特朗普",
    "schedule_interval": "HOURLY",
    "is_active": true
  }'

# 查询结果
curl http://localhost:8000/api/v1/search-tasks/237408060762787840/results
```

### JavaScript/Fetch

```javascript
// 创建任务
const response = await fetch('http://localhost:8000/api/v1/search-tasks/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    name: '测试任务',
    query: '特朗普',
    schedule_interval: 'HOURLY',
    is_active: true
  })
});

const task = await response.json();

// 查询结果
const results = await fetch(
  `http://localhost:8000/api/v1/search-tasks/${task.id}/results`
).json();
```

---

## 速率限制

当前版本: **无限制** (开发环境)

生产环境建议:
- 即时搜索: 10次/分钟
- 任务创建: 100次/小时
- 结果查询: 1000次/小时

---

## 相关文档

- [调度器指南](SCHEDULER_GUIDE.md)
- [Firecrawl集成](FIRECRAWL_GUIDE.md)
- [重试机制](RETRY_MECHANISM.md)

**维护者**: Backend Team | **API文档**: Swagger UI at `/docs`
