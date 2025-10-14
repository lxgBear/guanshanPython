# 定时搜索任务 API 字段参考

## Language 语言选项

`search_config.language` 字段支持以下选项：

| 值 | 语言 | 说明 |
|---|---|---|
| `zh` | 中文 | 搜索中文内容 |
| `en` | 英文 | 搜索英文内容 |
| `ja` | 日文 | 搜索日文内容 |
| `ko` | 韩文 | 搜索韩文内容 |
| `es` | 西班牙文 | 搜索西班牙文内容 |
| `fr` | 法文 | 搜索法文内容 |
| `de` | 德文 | 搜索德文内容 |
| `auto` | 自动检测 | 根据查询词自动检测语言 |

### 使用示例

```json
{
  "name": "AI新闻监控",
  "query": "人工智能 最新进展",
  "search_config": {
    "language": "zh",
    "limit": 20,
    "sources": ["web", "news"]
  }
}
```

## Schedule Interval 调度间隔选项

`schedule_interval` 字段支持以下预定义间隔：

| 值 | 显示名称 | 执行时间 | 间隔(分钟) | 说明 |
|---|---|---|---|---|
| `HOURLY_1` | 每小时 | 每小时的0分 | 60 | 每小时执行一次 |
| `HOURLY_6` | 每6小时 | 0点、6点、12点、18点 | 360 | 每6小时执行一次 |
| `HOURLY_12` | 每12小时 | 0点、12点 | 720 | 每12小时执行一次 |
| `DAILY` | 每天 | 每天上午9点 | 1440 | 每天执行一次 |
| `DAYS_3` | 每3天 | 每3天上午9点 | 4320 | 每3天执行一次 |
| `WEEKLY` | 每周 | 每周一上午9点 | 10080 | 每周执行一次 |

### 获取所有调度间隔选项

```bash
GET /api/v1/search-tasks/schedule-intervals
```

## 目标网站链接支持

### include_domains 包含特定域名

用于限制搜索结果只来自指定的网站域名：

```json
{
  "name": "特定网站监控",
  "query": "AI技术动态",
  "search_config": {
    "language": "zh",
    "include_domains": [
      "tech.sina.com.cn",
      "www.36kr.com",
      "www.ithome.com"
    ]
  }
}
```

### exclude_domains 排除特定域名

用于排除不想要的网站域名：

```json
{
  "search_config": {
    "exclude_domains": [
      "spam-site.com",
      "low-quality.org"
    ]
  }
}
```

### 支持的URL格式

- **完整域名**: `www.example.com`
- **子域名**: `news.example.com`
- **主域名**: `example.com` (包含所有子域名)

## 完整示例：创建定时搜索任务

```json
POST /api/v1/search-tasks

{
  "name": "科技新闻定时监控",
  "description": "监控主要科技网站的AI相关新闻",
  "query": "人工智能 机器学习 深度学习",
  "search_config": {
    "limit": 30,
    "sources": ["web", "news"],
    "language": "zh",
    "include_domains": [
      "www.36kr.com",
      "tech.sina.com.cn",
      "www.ithome.com",
      "www.pingwest.com"
    ],
    "time_range": "day",
    "enable_ai_summary": true
  },
  "schedule_interval": "DAILY",
  "is_active": true
}
```

## 搜索配置完整选项

### 基础配置
- `limit`: 结果数量 (1-100)
- `sources`: 搜索来源 ["web", "news", "academic", "social", "video", "image"]
- `language`: 语言选择 (见上表)

### 域名过滤
- `include_domains`: 包含的域名列表
- `exclude_domains`: 排除的域名列表

### 时间过滤
- `time_range`: 时间范围 ["day", "week", "month", "year"]

### 高级选项
- `enable_ai_summary`: 启用AI摘要 (boolean)
- `extract_metadata`: 提取元数据 (boolean)
- `follow_links`: 跟随链接 (boolean)
- `max_depth`: 最大搜索深度 (1-3)

## 调度器管理API

### 调度器状态管理

```bash
# 获取调度器状态
GET /api/v1/scheduler/status

# 启动调度器
POST /api/v1/scheduler/start

# 停止调度器
POST /api/v1/scheduler/stop

# 健康检查
GET /api/v1/scheduler/health
```

### 任务控制API

```bash
# 暂停任务
POST /api/v1/scheduler/tasks/{task_id}/pause

# 恢复任务
POST /api/v1/scheduler/tasks/{task_id}/resume

# 立即执行任务
POST /api/v1/scheduler/tasks/{task_id}/execute

# 获取任务下次执行时间
GET /api/v1/scheduler/tasks/{task_id}/next-run

# 获取正在运行的任务
GET /api/v1/scheduler/running-tasks
```

## API响应示例

### 创建任务成功响应

```json
{
  "id": "235320099735863296",
  "name": "科技新闻定时监控",
  "description": "监控主要科技网站的AI相关新闻",
  "query": "人工智能 机器学习 深度学习",
  "search_config": {
    "limit": 30,
    "sources": ["web", "news"],
    "language": "zh",
    "include_domains": ["www.36kr.com", "tech.sina.com.cn"]
  },
  "schedule_interval": "DAILY",
  "schedule_display": "每天",
  "schedule_description": "每天上午9点执行",
  "is_active": true,
  "status": "active",
  "created_by": "current_user",
  "created_at": "2025-10-11T08:32:59.934739",
  "next_run_time": "2025-10-12T09:00:00",
  "execution_count": 0,
  "success_rate": 0.0
}
```

### 调度器状态响应

```json
{
  "status": "running",
  "active_jobs": 5,
  "next_run_time": "2025-10-12T09:00:00",
  "jobs": [
    {
      "id": "search_task_235320099735863296",
      "name": "搜索任务: 科技新闻定时监控",
      "next_run_time": "2025-10-12T09:00:00"
    }
  ]
}
```

### 立即执行任务响应

```json
{
  "task_id": "235320099735863296",
  "task_name": "科技新闻定时监控",
  "executed_at": "2025-10-11T10:30:00.123456",
  "status": "completed",
  "last_execution_success": true,
  "execution_count": 15
}
```

### 正在运行任务响应

```json
{
  "running_tasks": [
    {
      "task_id": "235320099735863296",
      "task_name": "搜索任务: 科技新闻定时监控",
      "next_run_time": "2025-10-12T09:00:00",
      "is_paused": false
    }
  ],
  "count": 1
}
```