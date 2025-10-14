# 定时任务调度器集成指南

## 问题诊断

您遇到的问题是调度器API端点无响应，根本原因是：**调度器未在FastAPI应用启动时初始化**。

## 已实施的修复

### 修改文件: `src/main.py`

#### 1. 添加调度器导入

```python
from src.services.task_scheduler import start_scheduler, stop_scheduler
```

#### 2. 在应用启动时初始化调度器

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 启动时初始化
    logger.info("🚀 启动关山智能系统...")

    try:
        # 初始化数据库连接
        await init_database()
        logger.info("✅ 数据库连接初始化成功")

        # 启动定时任务调度器 ← 新增
        try:
            await start_scheduler()
            logger.info("✅ 定时任务调度器启动成功")
        except Exception as e:
            logger.warning(f"⚠️ 定时任务调度器启动失败: {e}")

        logger.info("✅ 系统启动成功")
    except Exception as e:
        logger.warning(f"⚠️ 部分组件初始化失败: {str(e)}")

    yield

    # 关闭时清理
    try:
        # 停止定时任务调度器 ← 新增
        try:
            await stop_scheduler()
            logger.info("✅ 定时任务调度器已停止")
        except Exception as e:
            logger.warning(f"⚠️ 停止调度器时出错: {e}")

        # 关闭数据库连接
        await close_database_connections()
        logger.info("✅ 数据库连接已关闭")
    except Exception as e:
        logger.error(f"⚠️ 关闭时出现错误: {str(e)}")
```

## 重启应用步骤

### 方法1: 终止并重启 (推荐)

```bash
# 1. 找到运行中的进程
ps aux | grep "python.*main.py" | grep -v grep

# 2. 终止进程 (替换 <PID> 为实际进程ID)
kill <PID>

# 例如，根据您的情况:
kill 22435

# 3. 等待几秒确保进程完全停止
sleep 2

# 4. 重新启动应用
python main.py
```

### 方法2: 使用 pkill (更简单)

```bash
# 终止所有 python main.py 进程
pkill -f "python.*main.py"

# 等待几秒
sleep 2

# 重新启动
python main.py
```

### 方法3: 如果使用 uvicorn 直接启动

```bash
# 终止进程
pkill -f uvicorn

# 重新启动
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## 验证调度器运行

重启应用后，您应该在日志中看到：

```
2025-10-13 XX:XX:XX - src.main - INFO - 🚀 启动关山智能系统...
2025-10-13 XX:XX:XX - src.infrastructure.database.connection - INFO - MongoDB连接成功: intelligent_system
2025-10-13 XX:XX:XX - src.main - INFO - ✅ 数据库连接初始化成功
2025-10-13 XX:XX:XX - src.services.task_scheduler - INFO - 调度器使用MongoDB仓储
2025-10-13 XX:XX:XX - src.services.task_scheduler - INFO - 📋 加载了 X 个活跃搜索任务
2025-10-13 XX:XX:XX - src.services.task_scheduler - INFO - 🚀 定时搜索任务调度器启动成功
2025-10-13 XX:XX:XX - src.main - INFO - ✅ 定时任务调度器启动成功
2025-10-13 XX:XX:XX - src.main - INFO - ✅ 系统启动成功
```

## 测试API端点

### 1. 健康检查

```bash
# 应用健康检查
curl http://localhost:8000/health

# 调度器健康检查
curl http://localhost:8000/api/v1/scheduler/health
```

**期望响应**:
```json
{
  "status": "healthy",
  "scheduler_running": true,
  "active_jobs": 5,
  "timestamp": "2025-10-13T06:30:00.000000"
}
```

### 2. 获取调度器状态

```bash
curl http://localhost:8000/api/v1/scheduler/status
```

**期望响应**:
```json
{
  "status": "running",
  "active_jobs": 5,
  "next_run_time": "2025-10-14T09:00:00+08:00",
  "jobs": [
    {
      "id": "search_task_1640109524",
      "name": "搜索任务: AI新闻监控测试",
      "next_run_time": "2025-10-14T09:00:00+08:00"
    }
  ]
}
```

### 3. 获取运行中任务

```bash
curl http://localhost:8000/api/v1/scheduler/running-tasks
```

**期望响应**:
```json
{
  "running_tasks": [
    {
      "task_id": "1640109524",
      "task_name": "搜索任务: AI新闻监控测试",
      "next_run_time": "2025-10-14T09:00:00+08:00",
      "is_paused": false
    }
  ],
  "count": 5
}
```

### 4. 立即执行任务

```bash
# 替换 {task_id} 为实际任务ID
curl -X POST http://localhost:8000/api/v1/scheduler/tasks/1640109524/execute
```

**期望响应**:
```json
{
  "task_id": "1640109524",
  "task_name": "AI新闻监控测试",
  "executed_at": "2025-10-13T06:30:00.000000",
  "status": "completed",
  "last_execution_success": false,
  "execution_count": 1
}
```

### 5. 暂停/恢复任务

```bash
# 暂停任务
curl -X POST http://localhost:8000/api/v1/scheduler/tasks/1640109524/pause

# 恢复任务
curl -X POST http://localhost:8000/api/v1/scheduler/tasks/1640109524/resume
```

## 完整API端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/scheduler/health` | 调度器健康检查 |
| GET | `/api/v1/scheduler/status` | 获取调度器状态 |
| GET | `/api/v1/scheduler/running-tasks` | 获取运行中任务 |
| POST | `/api/v1/scheduler/start` | 启动调度器 |
| POST | `/api/v1/scheduler/stop` | 停止调度器 |
| POST | `/api/v1/scheduler/tasks/{task_id}/execute` | 立即执行任务 |
| POST | `/api/v1/scheduler/tasks/{task_id}/pause` | 暂停任务 |
| POST | `/api/v1/scheduler/tasks/{task_id}/resume` | 恢复任务 |
| GET | `/api/v1/scheduler/tasks/{task_id}/next-run` | 获取下次执行时间 |

## 架构图

```
FastAPI应用启动
    ↓
lifespan() 上下文管理器
    ↓
1. init_database() - 初始化MongoDB
    ↓
2. start_scheduler() - 启动调度器
    ↓
    ├─ 创建APScheduler实例
    ├─ 加载活跃任务到调度器
    ├─ 配置Cron触发器
    └─ 启动后台主检查任务
    ↓
3. 应用运行 - API端点可用
    ↓
应用关闭信号
    ↓
1. stop_scheduler() - 停止调度器
    ↓
2. close_database_connections() - 关闭数据库
    ↓
应用安全退出
```

## 故障排查

### 问题1: 调度器启动失败

**症状**: 日志显示 "⚠️ 定时任务调度器启动失败"

**可能原因**:
- MongoDB连接失败
- 端口冲突
- APScheduler配置问题

**解决方案**:
```bash
# 检查MongoDB是否运行
mongosh --eval "db.adminCommand('ping')"

# 检查端口占用
lsof -ti:8000

# 查看详细错误日志
tail -f logs/app.log
```

### 问题2: API返回404

**症状**: `curl http://localhost:8000/api/v1/scheduler/status` 返回404

**可能原因**:
- 应用未重启
- 路由注册问题

**解决方案**:
```bash
# 确认应用已重启并查看启动日志
ps aux | grep python | grep main

# 检查路由注册
curl http://localhost:8000/api/docs
```

### 问题3: 任务不执行

**症状**: 调度器运行，但任务从不执行

**可能原因**:
- 任务被禁用 (is_active=False)
- Cron表达式错误
- 调度器时区配置问题

**解决方案**:
```bash
# 检查任务状态
curl http://localhost:8000/api/v1/tasks

# 手动触发任务测试
curl -X POST http://localhost:8000/api/v1/scheduler/tasks/{task_id}/execute

# 查看调度器日志
grep "执行搜索任务" logs/app.log
```

## 生产环境部署建议

### 1. 使用系统服务管理

创建 systemd 服务文件 `/etc/systemd/system/guanshan-api.service`:

```ini
[Unit]
Description=Guanshan Intelligence System API
After=network.target mongodb.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/guanshanPython
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable guanshan-api
sudo systemctl start guanshan-api
sudo systemctl status guanshan-api
```

### 2. 使用进程管理器

使用 Supervisor:

```ini
[program:guanshan-api]
directory=/path/to/guanshanPython
command=/path/to/venv/bin/python main.py
autostart=true
autorestart=true
stderr_logfile=/var/log/guanshan/api.err.log
stdout_logfile=/var/log/guanshan/api.out.log
```

### 3. 监控和告警

- 配置Prometheus监控调度器指标
- 设置任务失败告警
- 定期检查调度器健康状态

```bash
# 定期健康检查脚本
#!/bin/bash
HEALTH_CHECK=$(curl -s http://localhost:8000/api/v1/scheduler/health)
STATUS=$(echo $HEALTH_CHECK | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    echo "调度器不健康! 状态: $STATUS"
    # 发送告警通知
    # ...
fi
```

## 相关文档

- [调度器功能测试报告](./SCHEDULER_TEST_REPORT.md)
- [API使用指南](./API_USAGE_GUIDE.md)
- [系统架构文档](./SYSTEM_ARCHITECTURE.md)

---

**更新时间**: 2025-10-13
**作者**: Claude Code (Backend Specialist Mode)
