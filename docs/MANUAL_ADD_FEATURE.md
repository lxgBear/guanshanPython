# 手动添加数据功能文档 (v2.2.0)

## 功能概述

本功能允许用户通过两种方式向 `search_results` 表添加数据：

1. **手动添加**：用户直接输入标题、URL、内容等信息
2. **URL爬取**：用户输入URL，系统自动爬取页面内容

所有添加的数据都会标记其数据来源类型，方便后续区分和管理。

## 数据来源类型

| 类型 | 值 | 说明 |
|------|-----|------|
| 定时搜索爬取 | `scheduled_crawl` | 通过定时任务自动爬取的数�� |
| URL爬取 | `url_crawl` | 用户提交URL，系统自动爬取 |
| 用户手动添加 | `user_added` | 用户手动输入的数据 |

## API 端点

### 1. 手动添加搜索结果

**端点：** `POST /api/v1/search-results/manual`

**权限要求：** `info:create` 或 `search:basic`

**请求参数：**

```json
{
  "task_id": "1234567890123456789",
  "title": "Python异步编程��佳实践",
  "url": "https://example.com/python-async",
  "content": "本文介绍Python异步编程的最佳实践...",
  "snippet": "Python异步编程最佳实践",
  "source": "web",
  "language": "zh-CN",
  "author": "作者名",
  "published_date": "2024-01-01T00:00:00Z",
  "tags": ["Python", "异步编程"],
  "user_id": "user123",
  "created_by": "user123"
}
```

**响应示例：**

```json
{
  "success": true,
  "message": "搜索结果添加成功",
  "data": {
    "id": "9876543210987654321",
    "task_id": "1234567890123456789",
    "title": "Python异步编程最佳实践",
    "url": "https://example.com/python-async",
    "data_source_type": "user_added",
    "status": "pending",
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```

### 2. URL爬取添加

**端点：** `POST /api/v1/search-results/crawl`

**权限要求：** `info:create` 或 `search:basic`

**请求参数：**

```json
{
  "task_id": "1234567890123456789",
  "url": "https://example.com/article",
  "source": "web",
  "user_id": "user123",
  "created_by": "user123"
}
```

**响应示例：**

```json
{
  "success": true,
  "message": "URL爬取并添加成功",
  "data": {
    "id": "9876543210987654321",
    "task_id": "1234567890123456789",
    "title": "文章标题（从页面提取）",
    "url": "https://example.com/article",
    "markdown_content": "爬取的Markdown内容...",
    "data_source_type": "url_crawl",
    "status": "pending",
    "created_at": "2024-01-01T12:00:00Z"
  }
}
```



## 数据模型变更

### SearchResult 实体新增字段

```python
# 数据来源类型枚举
class DataSourceType(Enum):
    SCHEDULED_CRAWL = "scheduled_crawl"  # 定时搜索爬取
    URL_CRAWL = "url_crawl"              # 用户提交URL爬取
    USER_ADDED = "user_added"            # 用户手动添加

# SearchResult 新增字段
data_source_type: DataSourceType = field(
    default_factory=lambda: DataSourceType.SCHEDULED_CRAWL
)
```

## 使用场景

### 场景1：用户手动收集资料

用户在研究过程中发现了一些有价值的网页，想手动添加到搜索结果中：

1. 调用 `POST /api/v1/search-results/manual` 接口
2. 填写标题、URL、内容等信息
3. 数据保存后 `data_source_type` 为 `user_added`
4. 后续可通过来源类型筛选查看

### 场景2：用户提交URL让系统爬取

用户只想提供URL，让系统自动获取内容：

1. 调用 `POST /api/v1/search-results/crawl` 接口
2. 只需填写URL
3. 系统自动爬取页面内容并保存
4. 数据保存后 `data_source_type` 为 `url_crawl`

## 注意事项

1. **URL去重**：同一任务下相同URL只会保存一次（非deleted状态）
2. **任务验证**：添加数据前会验证 `task_id` 是否存在
3. **内容限制**：`markdown_content` 最大保存5000字符
4. **权限要求**：所有接口都需要相应的权限才能访问

## 相关文件

- 实体定义：`src/core/domain/entities/search_result.py`
- API端点：`src/api/v1/endpoints/search_results_manual.py`
- 路由注册：`src/api/v1/router.py`
