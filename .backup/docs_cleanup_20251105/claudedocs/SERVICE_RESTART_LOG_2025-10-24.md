# 服务重启日志

**重启时间**: 2025-10-24 15:37
**原因**: 应用 Firecrawl 超时配置修复 (30秒 → 60秒)
**执行人员**: Claude Code Backend Analyst

---

## 重启流程

### 1. 停止旧服务
```bash
# 停止 PID: 55141
kill 55141
```

**结果**: ✅ 旧服务已成功停止

### 2. 启动新服务
```bash
nohup uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

**新 PID**: `71098`

**结果**: ✅ 新服务已成功启动

---

## 配置验证

### 环境变量检查

```
✅ FIRECRAWL_TIMEOUT = 60 秒
✅ FIRECRAWL_MAX_RETRIES = 3
✅ FIRECRAWL_BASE_URL = https://api.firecrawl.dev
```

### 服务启动日志

```
2025-10-24 15:37:51 - 🚀 启动关山智能系统...
2025-10-24 15:37:51 - MongoDB连接成功: guanshan
2025-10-24 15:37:51 - 调度器使用MongoDB仓储
2025-10-24 15:37:51 - 🚀 定时搜索任务调度器启动成功
2025-10-24 15:37:51 - ✅ 定时任务调度器启动成功
2025-10-24 15:37:51 - ✅ 系统启动成功
```

---

## 服务状态

### 进程信息
```
PID: 71098
用户: lanxionggao
命令: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
状态: 运行中 ✅
```

### API 端点
- **主机**: 0.0.0.0
- **端口**: 8000
- **Swagger UI**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/health

---

## 配置生效确认

### Firecrawl 超时配置
- **旧值**: 30 秒
- **新值**: 60 秒 ✅
- **生效时间**: 2025-10-24 15:37:51

### 预期效果
- 智能搜索超时失败率降低
- 复杂查询成功率提升
- 用户最长等待时间从30秒增加到60秒

---

## 下一步监控

### 观察指标 (1周内)
1. 智能搜索整体成功率
2. 子搜索超时率
3. 平均查询执行时间
4. 用户等待体验反馈

### 监控命令
```bash
# 查看服务状态
ps aux | grep uvicorn

# 查看最新日志
tail -f /tmp/uvicorn.log

# 检查超时错误
grep "超时" /tmp/uvicorn.log | tail -20
```

---

## 回滚方案

如果60秒超时导致用户等待时间过长:

```bash
# 1. 修改 .env
FIRECRAWL_TIMEOUT=45

# 2. 重启服务
kill <pid>
nohup uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

---

**重启状态**: ✅ 成功完成
**服务状态**: ✅ 正常运行
**配置状态**: ✅ 已生效
