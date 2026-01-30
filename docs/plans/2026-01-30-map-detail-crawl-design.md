# Map + Detail 详情页爬取功能设计

> 创建日期: 2026-01-30
> 状态: 已确认

## 1. 功能概述

用户输入网址，使用 Firecrawl Map API 获取页面所有链接，通过规则过滤 + LLM 判断筛选出详情页，批量爬取详情页内容并存储到 `search_results` 表。

### 核心流程

```
用户输入URL → Map API获取链接 → URL去重 → 规则过滤 → LLM判断 → Scrape爬取 → AI处理(可选) → 存储
```

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户/定时任务                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  API Layer: POST /api/v1/crawl/map-detail                       │
│  - 创建异步任务，返回 task_id                                     │
│  - GET /api/v1/crawl/map-detail/{task_id} 查询状态               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service Layer: MapDetailService                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Firecrawl Map API → 获取所有链接 (≤500)               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 2. URL 去重 → 过滤已爬取的 URL                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3. 规则过滤 → 黑名单模式过滤导航页                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 4. LangGraph 工作流 → LLM 判断剩余 URL 是否为详情页        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 5. Firecrawl Scrape API → 批量爬取详情页 (并发10)         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 6. AI 处理 (可选) → 翻译/分类/提取                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 7. 存储 → search_results + news_results                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 数据模型

### 3.1 复用现有表结构

- **任务表**: `search_tasks` - 添加新的 `task_type = "map_detail"`
- **结果表**: `search_results` - 存储爬取的详情页内容
- **去重**: 基于 `search_results.url` 字段判断是否已爬取

### 3.2 SearchTask 扩展

```python
class TaskType(str, Enum):
    SEARCH = "search"
    INSTANT = "instant"
    SMART = "smart"
    MAP_DETAIL = "map_detail"  # 新增类型
```

### 3.3 配置选项 (存入 SearchTask.config)

```python
config = {
    "enable_ai_processing": True,   # 是否启用AI处理
    "map_limit": 500,               # Map API 最大链接数
    "scrape_concurrency": 10,       # Scrape 并发数
    "max_retries": 5,               # 失败重试次数
    "stats": {
        "total_urls_found": 0,      # Map 发现的总链接数
        "urls_after_dedup": 0,      # 去重后链接数
        "urls_after_filter": 0,     # 规则过滤后链接数
        "urls_after_llm": 0,        # LLM 判断后的详情页数
        "urls_scraped": 0,          # 成功爬取数
        "urls_failed": 0            # 爬取失败数
    }
}
```

## 4. URL 过滤规则

### 4.1 黑名单模式

```python
NAVIGATION_BLACKLIST = [
    # 导航类
    "/category/", "/categories/",
    "/tag/", "/tags/",
    "/page/", "/pages/",
    "/archive/", "/archives/",
    "/author/", "/authors/",

    # 列表类
    "/list/", "/index/",
    "/search/", "/browse/",

    # 功能类
    "/login/", "/register/", "/signup/",
    "/contact/", "/about/", "/faq/",
    "/privacy/", "/terms/", "/policy/",
]
```

### 4.2 过滤流程

1. **URL 去重** - 查询 `search_results` 表，过滤已爬取的 URL
2. **规则过滤** - 黑名单模式排除明显的导航页
3. **LLM 判断** - 剩余全部 URL 发给 LLM 二次判断

## 5. LangGraph 工作流

### 5.1 工作流结构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  输入URLs   │ ──▶ │  LLM判断    │ ──▶ │  输出详情页  │
│  (规则过滤后) │     │  是否详情页  │     │  URL列表    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 5.2 State 定义

```python
class UrlFilterState(TypedDict):
    urls: List[str]              # 输入的URL列表
    detail_pages: List[str]      # 判断为详情页的URL
    navigation_pages: List[str]  # 判断为导航页的URL
    error: Optional[str]         # 错误信息
```

### 5.3 LLM Prompt

```python
DETAIL_PAGE_FILTER_PROMPT = """
你是一个URL分类专家。请判断以下URL哪些是"详情页"，哪些是"导航页/列表页"。

详情页特征：
- 包含具体文章、新闻、产品的完整内容
- URL通常包含文章ID、日期、slug等标识
- 例如: /news/2024/01/article-title, /post/12345, /p/abc123

导航页/列表页特征：
- 展示多个内容的链接列表
- URL通常是分类、标签、首页等
- 例如: /news/, /blog/, /products/

请分析以下URL列表，返回JSON格式：
{
    "detail_pages": ["url1", "url2", ...],
    "navigation_pages": ["url3", "url4", ...]
}

URL列表：
{urls}
"""
```

### 5.4 分批处理

- 每批最多 50 个 URL 发给 LLM（避免 token 超限）
- 合并多批结果

## 6. API 接口设计

### 6.1 创建任务

```
POST /api/v1/crawl/map-detail

Request Body:
{
    "source_url": "https://example.com/news",  # 必填
    "enable_ai_processing": true,               # 可选，默认true
    "map_limit": 500,                           # 可选，默认500
    "scrape_concurrency": 10,                   # 可选，默认10
    "max_retries": 5                            # 可选，默认5
}

Response:
{
    "task_id": "task_abc123",
    "status": "pending",
    "message": "任务已创建，正在执行"
}
```

### 6.2 查询任务状态

```
GET /api/v1/crawl/map-detail/{task_id}

Response:
{
    "task_id": "task_abc123",
    "status": "running",
    "source_url": "https://example.com/news",
    "stats": {
        "total_urls_found": 120,
        "urls_after_dedup": 95,
        "urls_after_filter": 80,
        "urls_after_llm": 65,
        "urls_scraped": 45,
        "urls_failed": 2
    },
    "created_at": "2024-01-30T10:00:00Z",
    "started_at": "2024-01-30T10:00:01Z",
    "completed_at": null,
    "error_message": null
}
```

### 6.3 查询任务结果

```
GET /api/v1/crawl/map-detail/{task_id}/results?page=1&limit=20

Response:
{
    "task_id": "task_abc123",
    "total": 65,
    "page": 1,
    "limit": 20,
    "results": [
        {
            "id": "result_001",
            "url": "https://example.com/news/article-1",
            "title": "文章标题",
            "content": "...",
            "news_results": {...}
        }
    ]
}
```

### 6.4 权限要求

- 权限: `info:create`

## 7. 定时任务集成

### 7.1 定时配置模型

```python
@dataclass
class MapDetailScheduleConfig:
    id: str
    name: str                        # 任务名称
    source_url: str                  # 目标URL
    enable_ai_processing: bool       # 是否启用AI处理
    schedule_type: str               # HOURLY_1/HOURLY_6/DAILY/WEEKLY
    is_active: bool                  # 是否启用
    last_run_at: Optional[datetime]  # 上次执行时间
    next_run_at: Optional[datetime]  # 下次执行时间
```

### 7.2 调度器集成

```python
async def execute_map_detail_scheduled_task(config_id: str):
    """执行定时 Map+Detail 爬取任务"""
    config = await get_schedule_config(config_id)
    task = await map_detail_service.create_task(
        source_url=config.source_url,
        enable_ai_processing=config.enable_ai_processing
    )
    await map_detail_service.execute(task.id)
    await update_last_run(config_id)
```

## 8. 执行限制

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| map_limit | 500 | Map API 最大返回链接数 |
| scrape_concurrency | 10 | Scrape API 并发数 |
| max_retries | 5 | 失败重试次数 |
| llm_batch_size | 50 | LLM 每批处理 URL 数 |

## 9. 文件结构

```
src/
├── api/v1/endpoints/
│   └── map_detail.py              # 新增：API 端点
│
├── core/domain/entities/
│   └── search_task.py             # 修改：添加 MAP_DETAIL 任务类型
│
├── services/
│   ├── map_detail/                # 新增：服务目录
│   │   ├── __init__.py
│   │   ├── service.py             # 核心服务逻辑
│   │   ├── url_filter.py          # 规则过滤器
│   │   └── langgraph_filter.py    # LangGraph URL判断工作流
│   │
│   └── task_scheduler.py          # 修改：添加定时任务支持
│
├── infrastructure/database/
│   └── map_detail_schedule_repository.py  # 新增：定时配置仓储
│
└── api/v1/router.py               # 修改：注册新路由
```

## 10. 实现优先级

| 优先级 | 模块 | 描述 |
|-------|------|------|
| P0 | `url_filter.py` | 规则过滤（黑名单） |
| P0 | `langgraph_filter.py` | LLM 判断工作流 |
| P0 | `service.py` | 核心服务（Map→过滤→Scrape→存储） |
| P1 | `map_detail.py` | API 端点 |
| P1 | `router.py` | 路由注册 |
| P2 | `task_scheduler.py` | 定时任务集成 |
| P2 | `map_detail_schedule_repository.py` | 定时配置管理 |

## 11. 关键设计决策

1. **混合过滤模式** - 规则快速过滤 + LLM 二次判断，平衡效率和准确性
2. **复用现有表结构** - 任务存 `search_tasks`，结果存 `search_results`，降低复杂度
3. **基于 URL 去重** - 已爬取的 URL 直接跳过，避免重复消耗 API 积分
4. **可配置 AI 处理** - 用户可选择是否启用翻译/分类，灵活适应不同场景
5. **异步任务模式** - 支持长时间运行，适合定时任务调度
