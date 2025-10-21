# 5分钟定时任务测试指南

## 📋 概述

本文档说明如何测试5分钟定时任务功能，包括关键词搜索和URL爬取两种模式。

## 🎯 测试目标

1. ✅ 验证5分钟调度间隔正确工作
2. ✅ 验证关键词搜索模式正常执行
3. ✅ 验证URL爬取模式正常执行
4. ✅ 验证优先级逻辑（crawl_url > query）
5. ✅ 验证数据正确存储到MongoDB
6. ✅ 验证任务统计信息准确更新

## 🛠️ 实现内容

### 1. 新增调度间隔选项

**文件**: `src/core/domain/entities/search_task.py`

```python
class ScheduleInterval(Enum):
    MINUTES_5 = ("MINUTES_5", "*/5 * * * *", "每5分钟", 5, "每5分钟执行一次（测试用）")
    # ... 其他间隔选项
```

**Cron表达式**: `*/5 * * * *` 表示每5分钟执行一次

### 2. 调度器优先级逻辑

**文件**: `src/services/task_scheduler.py`

**核心逻辑**:
```python
if task.crawl_url:
    # 使用 Firecrawl Scrape API 爬取指定网址
    logger.info(f"🌐 使用网址爬取模式: {task.crawl_url}")
    result_batch = await self._execute_crawl_task_internal(task, start_time)
else:
    # 使用 Firecrawl Search API 关键词搜索
    logger.info(f"🔍 使用关键词搜索模式: {task.query}")
    # ...执行搜索
```

## 🚀 快速开始

### 方式1: 自动创建并监控（推荐）

```bash
# 运行完整测试流程
python test_scheduler_5min.py
```

**功能**:
- ✅ 自动创建两个测试任务（关键词搜索 + URL爬取）
- ✅ 实时监控任务执行情况
- ✅ 显示执行统计和结果预览
- ✅ 提供最终报告
- ✅ 可选择性清理测试数据

**交互流程**:
1. 创建测试任务
2. 询问是否开始监控（默认Y）
3. 询问监控时长（默认15分钟）
4. 实时显示执行情况
5. 生成最终统计报告
6. 询问是否删除测试任务（默认N）

### 方式2: 仅创建任务

```bash
# 快速创建测试任务
python create_test_tasks.py
```

**功能**:
- ✅ 创建两个测试任务
- ✅ 显示任务ID和下次执行时间
- ❌ 不进行监控

**适用场景**: 仅需要创建任务，稍后手动查看执行情况

### 方式3: 手动API调用

```bash
# 创建关键词搜索任务
curl -X POST http://localhost:8000/api/v1/search-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试 - 关键词搜索",
    "query": "AI news",
    "schedule_interval": "MINUTES_5",
    "search_config": {"limit": 3},
    "is_active": true
  }'

# 创建URL爬取任务
curl -X POST http://localhost:8000/api/v1/search-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试 - URL爬取",
    "query": "ignored",
    "crawl_url": "https://www.anthropic.com",
    "schedule_interval": "MINUTES_5",
    "search_config": {"wait_for": 2000},
    "is_active": true
  }'
```

## 📊 监控任务执行

### 1. 查看调度器状态

```bash
curl http://localhost:8000/api/v1/scheduler/status
```

**响应示例**:
```json
{
  "status": "running",
  "active_jobs": 2,
  "next_run_time": "2025-10-15T10:35:00",
  "jobs": [
    {
      "id": "search_task_123456",
      "name": "搜索任务: 【测试】关键词搜索 - 5分钟",
      "next_run_time": "2025-10-15T10:35:00"
    }
  ]
}
```

### 2. 查看任务状态

```bash
curl http://localhost:8000/api/v1/search-tasks/{task_id}
```

**关键字段**:
- `execution_count`: 总执行次数
- `success_count`: 成功次数
- `failure_count`: 失败次数
- `last_executed_at`: 最后执行时间
- `next_run_time`: 下次执行时间
- `total_results`: 总结果数
- `total_credits_used`: 总消耗积分

### 3. 查看任务结果

```bash
curl http://localhost:8000/api/v1/search-results/task/{task_id}?page=1&page_size=10
```

**结果字段**:
- `source`: `"crawl"` 表示爬取结果，其他值表示搜索结果
- `url`: 结果URL
- `title`: 结果标题
- `content`: 文本内容
- `created_at`: 创建时间

### 4. 观察服务器日志

**关键日志标识**:
```
🔍 开始执行搜索任务: {task_id}
🌐 使用网址爬取模式: {url}          # URL爬取模式
🔍 使用关键词搜索模式: {query}      # 关键词搜索模式
✅ 搜索任务执行完成: {name}
✅ 搜索结果已保存到数据库: {count}条
```

## 🧪 验证清单

### 基础功能验证

- [ ] 任务创建成功，返回有效ID
- [ ] `schedule_interval` 字段接受 `"MINUTES_5"` 值
- [ ] 任务出现在调度器的活跃任务列表中
- [ ] `next_run_time` 正确计算（创建时间 + 5分钟）

### 执行逻辑验证

- [ ] 任务在创建后约5分钟首次执行
- [ ] 后续每5分钟执行一次
- [ ] 关键词搜索任务使用 Firecrawl Search API
- [ ] URL爬取任务使用 Firecrawl Scrape API
- [ ] 日志显示正确的执行模式标识

### 优先级逻辑验证

- [ ] 同时存在 `crawl_url` 和 `query` 时，优先使用 `crawl_url`
- [ ] 日志显示 "🌐 使用网址爬取模式"
- [ ] 结果的 `source` 字段为 `"crawl"`

### 数据持久化验证

- [ ] 搜索结果保存到 MongoDB `search_results` 集合
- [ ] 任务统计信息正确更新（execution_count, success_count等）
- [ ] `last_executed_at` 和 `next_run_time` 正确更新
- [ ] 结果可通过 API 正确查询

### 错误处理验证

- [ ] API不可用时任务标记为失败
- [ ] 失败次数正确增加
- [ ] 任务不会因单次失败而停止调度
- [ ] 错误信息记录在日志中

## 📈 预期结果

### 15分钟监控期间（理想状态）

| 时间 | 关键词搜索任务 | URL爬取任务 |
|------|--------------|------------|
| 0:00 | 创建任务 | 创建任务 |
| 5:00 | 第1次执行 ✅ | 第1次执行 ✅ |
| 10:00 | 第2次执行 ✅ | 第2次执行 ✅ |
| 15:00 | 第3次执行 ✅ | 第3次执行 ✅ |

**最终统计**（每个任务）:
- 执行次数: 3次
- 成功次数: 3次（理想状态）
- 成功率: 100%
- 总结果数: ≥3条（取决于搜索/爬取结果）
- 消耗积分: 3-9个（取决于结果数量）

## 🔧 故障排查

### 问题1: 任务未执行

**症状**: 5分钟后任务仍未执行

**检查**:
```bash
# 1. 检查调度器状态
curl http://localhost:8000/api/v1/scheduler/status

# 2. 检查任务是否启用
curl http://localhost:8000/api/v1/search-tasks/{task_id}
# 确认 is_active=true

# 3. 查看服务器日志
# 检查是否有调度器启动日志: "🚀 定时搜索任务调度器启动成功"
```

**解决方案**:
- 确保服务器正常运行
- 确认任务 `is_active=true`
- 重启服务器以重新加载调度器

### 问题2: 执行失败

**症状**: `failure_count` 增加，`success_count` 不变

**检查**:
```bash
# 查看日志中的错误信息
# 关键字: "❌ 搜索任务执行失败"
```

**常见原因**:
- Firecrawl API凭据无效或过期
- 网络连接问题
- MongoDB连接失败（结果无法保存）
- 目标URL无法访问（仅URL爬取模式）

**解决方案**:
- 检查 `.env` 文件中的 `FIRECRAWL_API_KEY`
- 检查 MongoDB 连接状态
- 测试目标URL可访问性

### 问题3: 结果未保存

**症状**: 执行成功但数据库中无结果

**检查**:
```bash
# 1. 检查结果API
curl http://localhost:8000/api/v1/search-results/task/{task_id}

# 2. 直接查询MongoDB
mongo
use search_task_db
db.search_results.find({task_id: "your_task_id"})
```

**解决方案**:
- 确认MongoDB服务运行正常
- 检查日志中是否有 "保存结果失败" 错误
- 验证数据库权限设置

### 问题4: 间隔不准确

**症状**: 执行时间不是精确5分钟间隔

**说明**: 这是**正常现象**

**原因**:
1. Cron调度器基于系统时间对齐（例如：10:05, 10:10, 10:15）
2. 任务执行时间取决于当前系统负载
3. `misfire_grace_time` 允许最多5分钟的延迟容忍

**预期行为**:
- 首次执行: 创建后下一个5的倍数分钟
- 例如10:07创建 → 10:10首次执行 → 10:15第2次 → 10:20第3次

## 📝 测试报告模板

```markdown
## 5分钟定时任务测试报告

**测试日期**: 2025-10-15
**测试时长**: 15分钟
**环境**: 本地开发环境

### 关键词搜索任务

- 任务ID: `1234567890123456`
- 执行次数: 3次
- 成功次数: 3次
- 失败次数: 0次
- 成功率: 100%
- 总结果数: 9条
- 总消耗积分: 3个
- 平均结果数: 3条/次

### URL爬取任务

- 任务ID: `2345678901234567`
- 执行次数: 3次
- 成功次数: 3次
- 失败次数: 0次
- 成功率: 100%
- 总结果数: 3条
- 总消耗积分: 3个
- 平均结果数: 1条/次

### 验证结果

- [x] 调度间隔准确
- [x] 优先级逻辑正确
- [x] 数据正确存储
- [x] 统计信息准确
- [x] 错误处理正常

### 问题记录

无

### 结论

✅ 5分钟定时任务功能正常工作
```

## 🗑️ 清理测试数据

### 方式1: 使用测试脚本清理

```bash
python test_scheduler_5min.py
# 在最后提示时选择 'y' 删除任务
```

### 方式2: 手动删除

```bash
# 删除单个任务
curl -X DELETE http://localhost:8000/api/v1/search-tasks/{task_id}

# 删除任务结果
curl -X DELETE http://localhost:8000/api/v1/search-results/task/{task_id}
```

### 方式3: 停用而非删除

```bash
# 仅停用任务（保留数据）
curl -X PATCH http://localhost:8000/api/v1/search-tasks/{task_id}/status \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

## 📚 相关文档

- [调度器集成指南](./SCHEDULER_INTEGRATION_GUIDE.md)
- [API使用指南](./API_USAGE_GUIDE.md)
- [数据库持久化说明](./DATABASE_PERSISTENCE_FIX.md)
- [Firecrawl API配置](./FIRECRAWL_API_CONFIGURATION.md)

## 🔗 API端点参考

| 端点 | 方法 | 说明 |
|------|-----|------|
| `/api/v1/search-tasks` | POST | 创建任务 |
| `/api/v1/search-tasks/{id}` | GET | 获取任务详情 |
| `/api/v1/search-tasks/{id}` | PUT | 更新任务 |
| `/api/v1/search-tasks/{id}` | DELETE | 删除任务 |
| `/api/v1/search-tasks/{id}/status` | PATCH | 修改任务状态 |
| `/api/v1/search-results/task/{id}` | GET | 获取任务结果 |
| `/api/v1/scheduler/status` | GET | 调度器状态 |
| `/api/v1/scheduler/running-tasks` | GET | 运行中任务 |

---

**最后更新**: 2025-10-15
**版本**: 1.0.0
