# 启动服务器指南

## ✅ 项目已成功配置

您的关山智能系统已准备好启动！

---

## 🚀 快速启动

### 方法1: 使用启动脚本（推荐）

```bash
./scripts/start_local.sh
```

这个脚本会自动：
- 检查并停止现有服务
- 启动MongoDB（如果可用）
- 启动FastAPI应用
- 提供清晰的状态反馈

### 方法2: 直接运行

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📋 服务访问地址

启动成功后，您可以访问：

### API文档
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

### 健康检查
- **Health Check**: http://localhost:8000/health
- **根路径**: http://localhost:8000/

### API端点
- **基础路径**: http://localhost:8000/api/v1/

主要功能：
- `/api/v1/search-tasks/` - 搜索任务管理
- `/api/v1/instant-search/` - 即时搜索
- `/api/v1/scheduler/` - 调度器管理
- `/api/v1/summary-reports/` - 总结报告

---

## 🗄️ MongoDB配置

### 当前配置
```
连接地址: localhost:27017
数据库名: intelligent_system
用户名: admin
密码: password123
```

### 启动MongoDB（如果需要）

#### 使用Docker（推荐）:
```bash
# 启动Docker Desktop
open -a Docker

# 等待Docker启动完成（约30秒），然后运行：
docker-compose -f docker-compose.mongodb.yml up -d

# 检查状态
docker ps | grep mongodb
```

#### 检查MongoDB连接:
```bash
# 使用mongosh
mongosh "mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin"

# 或使用Navicat Premium等GUI工具
```

---

## ✅ 启动成功标志

当看到以下日志时，说明服务启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
🚀 启动关山智能系统...
✅ 数据库连接初始化成功
✅ 定时任务调度器启动成功
✅ 系统启动成功
INFO:     Application startup complete.
```

---

## 🔍 测试服务

### 1. 健康检查
```bash
curl http://localhost:8000/health
```

预期响应:
```json
{
  "status": "healthy",
  "app": "Guanshan Intelligence System",
  "version": "1.0.0",
  "debug": true
}
```

### 2. 查看API文档
在浏览器中打开: http://localhost:8000/api/docs

### 3. 测试即时搜索
```bash
curl -X POST "http://localhost:8000/api/v1/instant-search/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python最新特性",
    "max_results": 5
  }'
```

---

## 📊 查看日志

### 实时日志
```bash
# 如果使用启动脚本，日志会直接显示在终端

# 如果使用后台运行
tail -f logs/server.log
```

### 日志级别
当前配置的日志级别: INFO

修改日志级别（.env文件）:
```
LOG_LEVEL=DEBUG  # 调试模式
LOG_LEVEL=INFO   # 信息模式
LOG_LEVEL=WARNING  # 警告模式
LOG_LEVEL=ERROR  # 错误模式
```

---

## 🛑 停止服务

### 如果在前台运行
按 `Ctrl+C`

### 如果在后台运行
```bash
# 查找进程
ps aux | grep uvicorn | grep -v grep

# 停止进程
kill <进程ID>

# 或强制停止所有uvicorn进程
pkill -f "uvicorn src.main:app"
```

---

## ⚙️ 环境配置

### 当前配置文件
- `.env` - 主配置文件（已配置）
- `.env.example` - 配置模板
- `.env.test` - 测试环境配置
- `.env.baota.example` - VPN数据库配置示例

### 关键配置项

```bash
# 应用配置
DEBUG=true
HOST=0.0.0.0
PORT=8000

# 数据库配置
MONGODB_URL=mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin

# Firecrawl API
FIRECRAWL_API_KEY=fc-0de3f26ef85c4e77b3edd90abd733d71

# 安全配置
SECRET_KEY=guanshan-secret-key-change-in-production-2024
```

---

## 🔧 故障排查

### 问题1: 端口被占用
```
Error: Address already in use
```

**解决方法**:
```bash
# 查找占用8000端口的进程
lsof -i :8000

# 停止该进程
kill <进程ID>
```

### 问题2: MongoDB连接失败
```
MongoDB连接失败: 连接超时
```

**解决方法**:
1. 检查MongoDB是否运行:
   ```bash
   docker ps | grep mongodb
   # 或
   ps aux | grep mongod
   ```

2. 启动MongoDB:
   ```bash
   docker-compose -f docker-compose.mongodb.yml up -d
   ```

3. 如果仍然失败，应用会以降级模式启动（数据库功能不可用）

### 问题3: 模块导入错误
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方法**:
```bash
# 安装依赖
pip install -r requirements.txt

# 或使用poetry
poetry install
```

---

## 📚 相关文档

- [VPN数据库连接指南](docs/VPN_DATABASE_GUIDE.md)
- [VPN连接测试报告](docs/VPN_CONNECTION_TEST_REPORT.md)
- API文档: http://localhost:8000/api/docs（服务启动后访问）

---

## 💡 提示

1. **首次启动**: 建议使用 `./scripts/start_local.sh`，它会自动处理所有依赖
2. **开发调试**: 使用 `--reload` 参数可以在代码修改后自动重启
3. **生产部署**: 移除 `--reload`，使用多个workers
4. **日志查看**: 实时查看日志可以快速发现问题

---

**祝您使用愉快！** 🎉
