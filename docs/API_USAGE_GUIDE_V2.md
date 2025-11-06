# Firecrawl API 使用指南 v2.0.0

## 📋 目录

1. [概述](#概述)
2. [任务类型](#任务类型)
3. [API 端点](#api-端点)
4. [请求示例](#请求示例)
5. [响应格式](#响应格式)
6. [配置参数](#配置参数)
7. [最佳实践](#最佳实践)

---

## 概述

### v2.0.0 主要更新

- ✅ **显式任务类型**: 新增 `task_type` 字段明确指定任务类型
- ✅ **配置分离**: `search_config` 和 `crawl_config` 分别管理不同类型的配置
- ✅ **向后兼容**: 兼容旧版本数据，自动判断任务类型
- ✅ **更清晰的 API**: 明确的参数和更好的文档

### 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证方式**: JWT Token（开发中）
- **内容类型**: `application/json`

---

## 任务类型

### TaskType 枚举

| 类型值 | 显示名称 | 说明 | 必填字段 |
|--------|---------|------|----------|
| `search_keyword` | 关键词搜索 + 详情页爬取 | 搜索关键词，获取结果后批量爬取详情页 | `query`, `search_config` |
| `crawl_website` | 网站递归爬取 | 递归爬取整个网站的所有页面 | `crawl_url`, `crawl_config` |
| `scrape_url` | 单页面爬取 | 定期爬取单个页面内容 | `crawl_url`, `search_config` |

### 任务类型对比

| 特性 | SEARCH_KEYWORD | CRAWL_WEBSITE | SCRAPE_URL |
|------|----------------|---------------|------------|
| **输入** | 关键词 | 起始URL | 单个URL |
| **输出** | 搜索结果+详情页 | 整站内容 | 单页内容 |
| **API** | Search + Scrape | Crawl | Scrape |
| **数据量** | 中等（10-50页） | 大量（50-500页） | 单页 |
| **速度** | 中等 | 慢 | 快 |
| **适用场景** | 行业资讯、竞品分析 | 网站归档、知识库 | 页面监控 |

---

## API 端点

### 1. 创建搜索任务

```http
POST /api/v1/search-tasks
Content-Type: application/json
```

**请求体**:

```json
{
  "name": "string",              // 任务名称（必填）
  "description": "string",       // 任务描述（可选）
  "query": "string",             // 搜索关键词（search_keyword模式必填）
  "crawl_url": "string",         // 爬取URL（crawl_website和scrape_url模式必填）
  "task_type": "string",         // 任务类型（可选，推荐明确指定）
  "search_config": {},           // 搜索配置（search_keyword和scrape_url）
  "crawl_config": {},            // 爬取配置（crawl_website）
  "schedule_interval": "string", // 调度间隔（默认DAILY）
  "is_active": true,             // 是否启用（默认true）
  "execute_immediately": true    // 是否立即执行（默认true）
}
```

**响应**: `201 Created`

```json
{
  "id": "task_abc123",
  "name": "AI新闻监控",
  "task_type": "search_keyword",
  "task_mode": "关键词搜索 + 详情页爬取",
  "status": "active",
  "created_at": "2025-01-15T10:00:00Z",
  ...
}
```

### 2. 获取任务列表

```http
GET /api/v1/search-tasks?page=1&page_size=20
```

**查询参数**:
- `page`: 页码（默认1）
- `page_size`: 每页大小（默认20，最大100）
- `status`: 状态过滤
- `is_active`: 启用状态过滤
- `query`: 关键词模糊查询

**响应**: `200 OK`

```json
{
  "items": [...],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### 3. 获取任务详情

```http
GET /api/v1/search-tasks/{task_id}
```

**响应**: `200 OK`

```json
{
  "id": "task_abc123",
  "name": "AI新闻监控",
  "query": "人工智能 深度学习",
  "task_type": "search_keyword",
  "task_mode": "关键词搜索 + 详情页爬取",
  "search_config": {
    "limit": 10,
    "language": "zh",
    "enable_detail_scrape": true
  },
  "execution_count": 5,
  "success_count": 5,
  "success_rate": 100.0,
  ...
}
```

### 4. 更新任务

```http
PUT /api/v1/search-tasks/{task_id}
Content-Type: application/json
```

**请求体**: 所有字段可选

```json
{
  "name": "新任务名称",
  "query": "新关键词",
  "task_type": "search_keyword",
  "search_config": {...},
  "crawl_config": {...},
  "is_active": false
}
```

### 5. 修改任务状态

```http
PATCH /api/v1/search-tasks/{task_id}/status
Content-Type: application/json
```

**请求体**:

```json
{
  "is_active": false
}
```

### 6. 删除任务

```http
DELETE /api/v1/search-tasks/{task_id}
```

**响应**: `200 OK`

```json
{
  "success": true,
  "message": "任务删除成功",
  "task_id": "task_abc123",
  "task_name": "AI新闻监控"
}
```

---

## 请求示例

### 示例 1: 创建关键词搜索任务

**场景**: 定期监控 AI 领域最新资讯

```json
{
  "name": "AI新闻监控",
  "description": "监控人工智能领域的最新进展和技术动态",
  "query": "人工智能 深度学习 最新进展",
  "task_type": "search_keyword",
  "search_config": {
    "limit": 10,
    "language": "zh",
    "enable_detail_scrape": true,
    "max_concurrent_scrapes": 3,
    "scrape_delay": 1.0,
    "only_main_content": true,
    "exclude_tags": ["nav", "footer", "header", "aside"]
  },
  "schedule_interval": "DAILY",
  "is_active": true,
  "execute_immediately": true
}
```

**说明**:
- ✅ 每天执行一次搜索
- ✅ 获取 10 条搜索结果
- ✅ 自动爬取每个结果的详情页
- ✅ 最多 3 个页面并发爬取
- ✅ 只提取主要内容，排除导航等

### 示例 2: 创建网站爬取任务

**场景**: 定期归档技术博客的所有文章

```json
{
  "name": "技术博客归档",
  "description": "爬取技术博客的所有文章用于知识库建设",
  "crawl_url": "https://example.com/blog",
  "task_type": "crawl_website",
  "crawl_config": {
    "limit": 100,
    "max_depth": 3,
    "include_paths": ["/blog/*", "/articles/*"],
    "exclude_paths": ["/admin/*", "/login/*"],
    "allow_backward_links": false,
    "only_main_content": true,
    "wait_for": 1000,
    "exclude_tags": ["nav", "footer", "header"],
    "timeout": 300
  },
  "schedule_interval": "WEEKLY",
  "is_active": true,
  "execute_immediately": false
}
```

**说明**:
- ✅ 每周执行一次爬取
- ✅ 最多爬取 100 个页面
- ✅ 最大深度 3 层
- ✅ 只爬取博客和文章路径
- ✅ 排除管理页面

### 示例 3: 创建单页面爬取任务

**场景**: 定期监控官网首页内容变化

```json
{
  "name": "官网首页监控",
  "description": "每小时检查官网首页是否有更新",
  "crawl_url": "https://example.com",
  "task_type": "scrape_url",
  "search_config": {
    "only_main_content": true,
    "wait_for": 2000,
    "exclude_tags": ["nav", "footer", "header"],
    "timeout": 90
  },
  "schedule_interval": "HOURLY",
  "is_active": true,
  "execute_immediately": true
}
```

**说明**:
- ✅ 每小时执行一次
- ✅ 只爬取首页单个页面
- ✅ 等待 2 秒确保内容加载
- ✅ 创建后立即执行一次

### 示例 4: 更新任务配置

**场景**: 修改搜索任务的关键词和配置

```json
{
  "query": "人工智能 机器学习 ChatGPT",
  "search_config": {
    "limit": 20,
    "enable_detail_scrape": true,
    "max_concurrent_scrapes": 5
  }
}
```

**说明**:
- ✅ 只更新指定的字段
- ✅ 其他字段保持不变
- ✅ 自动重新调度

---

## 响应格式

### 任务响应对象

```json
{
  "id": "task_abc123",
  "name": "AI新闻监控",
  "description": "监控人工智能领域最新进展",
  "query": "人工智能 深度学习",
  "crawl_url": null,
  "task_type": "search_keyword",
  "task_mode": "关键词搜索 + 详情页爬取",
  "search_config": {
    "limit": 10,
    "language": "zh",
    "enable_detail_scrape": true
  },
  "crawl_config": {},
  "schedule_interval": "DAILY",
  "schedule_display": "每日",
  "schedule_description": "每天执行一次（上午8点）",
  "is_active": true,
  "status": "active",
  "created_by": "current_user",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z",
  "last_executed_at": "2025-01-16T08:00:00Z",
  "next_run_time": "2025-01-17T08:00:00Z",
  "execution_count": 5,
  "success_count": 5,
  "failure_count": 0,
  "success_rate": 100.0,
  "average_results": 8.6,
  "total_results": 43,
  "total_credits_used": 53
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 任务唯一标识符 |
| `task_type` | string | 任务类型枚举值 |
| `task_mode` | string | 任务模式描述（用于前端显示） |
| `query` | string | 搜索关键词（search_keyword模式） |
| `crawl_url` | string | 爬取URL（crawl/scrape模式） |
| `search_config` | object | 搜索配置 |
| `crawl_config` | object | 爬取配置 |
| `execution_count` | integer | 总执行次数 |
| `success_count` | integer | 成功次数 |
| `success_rate` | float | 成功率（%） |
| `average_results` | float | 平均结果数 |
| `total_results` | integer | 累计结果总数 |
| `total_credits_used` | integer | 累计消耗积分 |

---

## 配置参数

### SearchConfig (search_keyword 和 scrape_url)

```json
{
  "limit": 10,                      // 搜索结果数量（默认10）
  "language": "zh",                 // 搜索语言（默认zh）
  "include_domains": [],            // 限制域名（可选）
  "strict_language_filter": true,   // 严格语言过滤（默认true）
  "enable_detail_scrape": true,     // 是否爬取详情页（默认true）
  "max_concurrent_scrapes": 3,      // 最大并发数（默认3）
  "scrape_delay": 1.0,              // 爬取间隔秒数（默认1.0）
  "only_main_content": true,        // 只提取主要内容（默认true）
  "wait_for": 2000,                 // 等待加载毫秒（默认2000）
  "exclude_tags": ["nav", "footer"], // 排除HTML标签（默认["nav","footer","header","aside"]）
  "timeout": 90                     // 超时秒数（默认90）
}
```

### CrawlConfig (crawl_website)

```json
{
  "limit": 100,                     // 最大页面数（默认100）
  "max_depth": 3,                   // 最大爬取深度（默认3）
  "include_paths": ["/blog/*"],     // 包含路径模式（默认[]）
  "exclude_paths": ["/admin/*"],    // 排除路径模式（默认[]）
  "allow_backward_links": false,    // 是否允许向后链接（默认false）
  "only_main_content": true,        // 只提取主要内容（默认true）
  "wait_for": 1000,                 // 等待加载毫秒（默认1000）
  "exclude_tags": ["nav", "footer"], // 排除HTML标签（默认["nav","footer","header"]）
  "timeout": 300,                   // 整体超时秒数（默认300）
  "poll_interval": 10               // 状态轮询间隔秒数（默认10）
}
```

### ScheduleInterval 选项

| 值 | 显示名称 | 说明 | 间隔分钟数 |
|----|---------|------|-----------|
| `HOURLY` | 每小时 | 每小时执行一次（整点） | 60 |
| `DAILY` | 每日 | 每天执行一次（上午8点） | 1440 |
| `WEEKLY` | 每周 | 每周一执行一次（上午8点） | 10080 |
| `MONTHLY` | 每月 | 每月1号执行一次（上午8点） | 43200 |

**获取所有选项**:
```http
GET /api/v1/search-tasks/schedule-intervals
```

---

## 最佳实践

### 1. 任务类型选择

**关键词搜索 (search_keyword)**:
- ✅ 需要获取多个来源的信息
- ✅ 关注行业动态、竞品分析
- ✅ 需要定期更新的资讯类内容
- ❌ 不适合：特定网站的全站爬取

**网站爬取 (crawl_website)**:
- ✅ 需要归档整个网站内容
- ✅ 构建知识库或文档库
- ✅ 定期备份网站内容
- ❌ 不适合：单页监控、实时更新需求

**单页面爬取 (scrape_url)**:
- ✅ 监控特定页面变化
- ✅ 定期更新的公告、新闻页
- ✅ 快速获取单页内容
- ❌ 不适合：需要多页面数据的场景

### 2. 配置优化

**关键词搜索优化**:
```json
{
  "enable_detail_scrape": true,   // 启用详情页爬取
  "max_concurrent_scrapes": 3,    // 平衡速度和资源（推荐2-5）
  "scrape_delay": 1.0,            // 避免请求过快（推荐1-2秒）
  "only_main_content": true       // 减少噪音
}
```

**网站爬取优化**:
```json
{
  "limit": 50,                    // 合理的页面限制（避免过大）
  "max_depth": 2,                 // 避免爬取过深（推荐1-3）
  "exclude_paths": ["/admin/*"],  // 排除不相关路径
  "timeout": 300                  // 足够的超时时间
}
```

### 3. 调度间隔选择

| 场景 | 推荐间隔 | 理由 |
|------|---------|------|
| 实时新闻监控 | HOURLY | 及时获取最新内容 |
| 行业资讯跟踪 | DAILY | 平衡时效性和资源消耗 |
| 知识库更新 | WEEKLY | 内容更新频率较低 |
| 月度报告归档 | MONTHLY | 按月周期更新 |

### 4. 错误处理

**常见错误及解决方案**:

1. **任务创建失败**
   - 检查必填字段是否完整
   - 验证 task_type 与配置字段是否匹配
   - 确认 URL 格式正确

2. **详情页爬取失败**
   - 降低 max_concurrent_scrapes
   - 增加 scrape_delay
   - 增加 timeout

3. **网站爬取超时**
   - 减少 limit
   - 减少 max_depth
   - 增加 timeout

### 5. 性能优化

**提高效率**:
- 使用 `only_main_content: true` 减少内容量
- 合理设置 `exclude_tags` 过滤无用内容
- 使用 `include_paths` 和 `exclude_paths` 精准爬取

**控制成本**:
- 设置合理的 `limit` 限制
- 使用 `is_active: false` 暂停不需要的任务
- 选择合适的 `schedule_interval`

---

## 附录

### 错误码

| 状态码 | 说明 | 处理方式 |
|--------|------|---------|
| 200 | 成功 | - |
| 201 | 创建成功 | - |
| 400 | 请求参数错误 | 检查请求体格式和必填字段 |
| 404 | 任务不存在 | 验证任务ID是否正确 |
| 500 | 服务器错误 | 查看服务器日志，联系技术支持 |

### 版本变更

#### v2.0.0 (当前版本)

- ✅ 新增 `task_type` 字段
- ✅ 新增 `crawl_config` 配置
- ✅ 新增 `task_mode` 响应字段
- ✅ 更新请求示例
- ✅ 向后兼容 v1.x 数据

#### v1.x (旧版本)

- 隐式任务类型判断
- 统一使用 `search_config`

---

**文档版本**: v2.0.0
**最后更新**: 2025-01-XX
**API 版本**: v1
