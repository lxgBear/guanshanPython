# 定时任务调度器指南

**版本**: v1.3.0 | **最后更新**: 2025-10-17

---

## 快速开始

### 基本概念

定时任务调度器基于APScheduler实现,支持:
- ⏰ Cron表达式定时执行
- 🔄 自动故障重试(8分钟×3次)
- 📊 执行统计和监控
- 🎯 手动触发执行

### 调度间隔选项

| 间隔 | Cron表达式 | 说明 |
|------|-----------|------|
| `MINUTES_5` | `*/5 * * * *` | 每5分钟 |
| `MINUTES_30` | `*/30 * * * *` | 每30分钟 |
| `HOURLY` | `0 * * * *` | 每小时 |
| `DAILY` | `0 9 * * *` | 每天9:00 |
| `WEEKLY` | `0 9 * * 1` | 每周一9:00 |

---

## API接口

### 1. 创建搜索任务

```bash
POST /api/v1/search-tasks/
{
  "name": "测试任务",
  "query": "特朗普 贸易战",
  "schedule_interval": "HOURLY",
  "is_active": true,
  "search_config": {
    "limit": 10,
    "time_range": "month"
  }
}
```

### 2. 手动执行任务

```bash
POST /api/v1/scheduler/tasks/{task_id}/execute
```

**响应示例**:
```json
{
  "task_id": "237408060762787840",
  "task_name": "测试任务",
  "executed_at": "2025-10-17T06:26:30",
  "status": "completed",
  "execution_count": 2
}
```

### 3. 查看调度器状态

```bash
GET /api/v1/scheduler/status
```

**响应**:
```json
{
  "status": "running",
  "active_jobs": 1,
  "next_run_time": "2025-10-17T15:00:00",
  "jobs": [...]
}
```

### 4. 查看任务详情

```bash
GET /api/v1/search-tasks/{task_id}
```

---

## 任务字段说明

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 任务唯一标识(雪花ID) |
| `name` | string | 任务名称 |
| `query` | string | 搜索关键词 |
| `crawl_url` | string | 爬取URL(可选,优先级高于query) |
| `schedule_interval` | string | 调度间隔枚举值 |
| `is_active` | boolean | 是否启用 |

### 统计字段

| 字段 | 说明 |
|------|------|
| `execution_count` | 总执行次数 |
| `success_count` | 成功次数 |
| `fail_count` | 失败次数 |
| `last_executed_at` | 最后执行时间 |
| `next_run_time` | 下次执行时间 |

### 配置字段

```python
search_config = {
    "limit": 10,              # 结果数量(默认10)
    "time_range": "month",    # 时间范围: day/week/month/year
    "language": "zh",         # 语言: zh/en
    "include_domains": [],    # 限定域名列表
}
```

---

## 故障处理

### 重试机制

自动重试配置:
- **间隔**: 8分钟
- **次数**: 最多3次
- **触发条件**: DNS故障、超时、HTTP错误

**日志示例**:
```
14:00:00 - ❌ DNS解析失败
14:00:00 - 🔄 第 1 次重试 (共3次)，将在 8 分钟后重试...
14:08:00 - ✅ 重试成功，获取10条结果
```

### 常见问题

**Q: 任务未执行?**
```bash
# 检查is_active状态
GET /api/v1/search-tasks/{task_id}

# 手动触发测试
POST /api/v1/scheduler/tasks/{task_id}/execute
```

**Q: 查看执行日志?**
```bash
tail -f /tmp/server_8000.log | grep {task_id}
```

**Q: 修改调度间隔?**
```bash
PUT /api/v1/search-tasks/{task_id}
{
  "schedule_interval": "MINUTES_30"
}
```

---

## 监控告警

### 关键日志

```bash
# 任务执行
grep "🔍 开始执行搜索任务" /tmp/server_8000.log

# 重试事件
grep "🔄 搜索请求失败" /tmp/server_8000.log

# 执行完成
grep "✅ 搜索任务执行完成" /tmp/server_8000.log
```

### 健康检查

```bash
GET /api/v1/scheduler/health
```

**健康响应**:
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "active_jobs": 1,
  "timestamp": "2025-10-17T06:35:49"
}
```

---

## 最佳实践

### 1. 任务命名
```python
# ✅ 好的命名
name = "特朗普_贸易战_每日监控"

# ❌ 避免
name = "task1"
```

### 2. 合理间隔
- 新闻监控: `HOURLY` 或 `MINUTES_30`
- 数据采集: `DAILY` 或 `WEEKLY`
- 测试调试: `MINUTES_5`

### 3. 结果数量
- 快速扫描: `limit: 10`
- 深度分析: `limit: 50`
- 全面采集: `limit: 100` (注意API限制)

---

## 技术实现

### 架构组件

```
TaskSchedulerService (调度器)
├── APScheduler (调度引擎)
├── FirecrawlSearchAdapter (搜索适配器)
├── SearchTaskRepository (任务仓储)
└── SearchResultRepository (结果仓储)
```

### 执行流程

```
1. 调度器触发 (Cron)
2. 获取任务配置
3. 执行搜索 (含重试)
4. 保存结果到MongoDB
5. 更新任务统计
6. 计算下次执行时间
```

### 代码位置

- 调度器服务: `src/services/task_scheduler.py`
- API端点: `src/api/v1/endpoints/scheduler_management.py`
- 搜索适配器: `src/infrastructure/search/firecrawl_search_adapter.py`

---

## 相关文档

- [重试机制详解](RETRY_MECHANISM.md)
- [API使用指南](API_GUIDE.md)
- [系统架构](SYSTEM_ARCHITECTURE.md)

**维护者**: Backend Team | **问题反馈**: GitHub Issues
