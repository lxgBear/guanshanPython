# 关山智能系统 - 完整启动指南

**版本**: v1.3.0 | **最后更新**: 2025-10-21

---

## 📋 目录

- [快速开始](#快速开始)
- [环境要求](#环境要求)
- [安装步骤](#安装步骤)
- [启动方式](#启动方式)
  - [方式1: 本地开发（Docker MongoDB）](#方式1-本地开发docker-mongodb)
  - [方式2: VPN远程数据库](#方式2-vpn远程数据库)
  - [方式3: 降级模式](#方式3-降级模式)
- [验证服务](#验证服务)
- [配置说明](#配置说明)
- [常用命令](#常用命令)
- [故障排查](#故障排查)
- [进阶配置](#进阶配置)

---

## 🚀 快速开始

### 最快启动路径

```bash
# 1. 克隆项目
git clone <repository-url>
cd guanshanPython

# 2. 安装依赖
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env 文件，配置 FIRECRAWL_API_KEY

# 4. 启动MongoDB（Docker）
docker-compose -f docker-compose.mongodb.yml up -d

# 5. 启动应用
./scripts/start_local.sh
# 或
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 访问服务

启动成功后，访问：
- **API文档**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/health
- **根路径**: http://localhost:8000/

---

## 📦 环境要求

### 必需
- **Python**: 3.11+ (推荐 3.13)
- **内存**: 8GB+ RAM (推荐 16GB)
- **磁盘空间**: 20GB+

### 可选（根据启动方式）
- **Docker Desktop**: 用于本地MongoDB（推荐）
- **OpenVPN**: 用于连接远程数据库
- **MongoDB**: 本地安装（如不使用Docker）

### API密钥
- **Firecrawl API Key**: 从 https://firecrawl.dev 获取

---

## 🔧 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd guanshanPython
```

### 2. 创建Python虚拟环境

```bash
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. 安装依赖

```bash
# 安装生产依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

### 4. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
nano .env  # 或使用你喜欢的编辑器
```

**必需配置项**:
```bash
# Firecrawl API配置
FIRECRAWL_API_KEY=your-api-key-here

# 数据库配置（选择其一）
# 选项1: 本地Docker MongoDB
MONGODB_URL=mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin

# 选项2: VPN远程MongoDB
# MONGODB_URL=mongodb://app_user:密码@<数据库内网IP>:27017/intelligent_system?authSource=intelligent_system

# 应用配置
DEBUG=true
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# 安全配置
SECRET_KEY=guanshan-secret-key-change-in-production-2024
```

---

## 🚀 启动方式

### 方式1: 本地开发（Docker MongoDB）

**适用场景**: 本地开发、测试、演示

#### 步骤

**1. 启动Docker Desktop**
```bash
# macOS
open -a Docker

# 等待Docker启动完成（约30秒）
docker ps
```

**2. 启动MongoDB容器**
```bash
docker-compose -f docker-compose.mongodb.yml up -d

# 验证容器运行
docker ps | grep mongodb
```

**3. 启动应用**

使用启动脚本（推荐）:
```bash
chmod +x scripts/start_local.sh
./scripts/start_local.sh
```

或直接运行:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**4. 验证启动**

看到以下日志表示成功:
```
🚀 启动关山智能系统...
✅ MongoDB连接成功: intelligent_system
✅ 数据库连接初始化成功
✅ 定时任务调度器启动成功
✅ 系统启动成功
INFO: Application startup complete.
```

---

### 方式2: VPN远程数据库

**适用场景**: 访问生产环境数据、远程开发

#### 前提条件

1. 拥有VPN配置文件（如 `vpn/lxg.ovpn`）
2. 已安装OpenVPN客户端
3. 知道远程数据库的内网IP地址

#### 步骤

**1. 连接VPN**

```bash
# 使用VPN连接脚本
chmod +x scripts/vpn_connect.sh
./scripts/vpn_connect.sh connect

# 验证VPN连接
./scripts/vpn_connect.sh status
```

**2. 测试数据库连接**

```bash
# 运行数据库连接测试
chmod +x scripts/test_vpn_database.py
python scripts/test_vpn_database.py
```

**3. 更新.env配置**

```bash
# 编辑 .env 文件
nano .env

# 更新MongoDB URL（使用VPN内网IP）
MONGODB_URL=mongodb://app_user:密码@<数据库内网IP>:27017/intelligent_system?authSource=intelligent_system
```

**4. 启动应用**

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

#### VPN故障排查

如果无法连接数据库，运行诊断脚本:
```bash
chmod +x scripts/diagnose_vpn_database.sh
./scripts/diagnose_vpn_database.sh
```

详细VPN配置指南: [docs/VPN_DATABASE_GUIDE.md](docs/VPN_DATABASE_GUIDE.md)

---

### 方式3: 降级模式

**适用场景**: MongoDB不可用时的应急启动

#### 特点

- 应用正常启动
- 使用内存存储（数据重启后丢失）
- 部分功能受限

#### 启动

```bash
# 直接启动（会自动检测MongoDB不可用并降级）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

应用会显示警告但继续运行:
```
⚠️ MongoDB连接失败: 连接超时
✅ 系统启动成功（降级模式）
```

---

## ✅ 验证服务

### 1. 健康检查

```bash
curl http://localhost:8000/health
```

**预期响应**:
```json
{
  "status": "healthy",
  "app": "Guanshan Intelligence System",
  "version": "1.0.0",
  "debug": true
}
```

### 2. API文档

浏览器访问: http://localhost:8000/api/docs

### 3. 测试调度器

```bash
curl http://localhost:8000/api/v1/scheduler/status
```

**预期响应**:
```json
{
  "scheduler_running": true,
  "active_jobs": 1,
  "next_run_time": "..."
}
```

### 4. 测试即时搜索

```bash
curl -X POST "http://localhost:8000/api/v1/instant-search/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python最新特性",
    "max_results": 5
  }'
```

---

## ⚙️ 配置说明

### 环境变量完整参考

```bash
# ====== 应用基础配置 ======
APP_NAME=Guanshan Intelligence System
VERSION=1.0.0
DEBUG=true
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=INFO

# ====== 测试模式配置 ======
TEST_MODE=false
TEST_MAX_RESULTS=10
TEST_DEFAULT_LIMIT=10

# ====== 安全配置 ======
SECRET_KEY=guanshan-secret-key-change-in-production-2024
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
ALLOWED_ORIGINS=http://localhost:3000

# ====== MongoDB配置 ======
# 选项1: 本地Docker
MONGODB_URL=mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin

# 选项2: VPN远程
# MONGODB_URL=mongodb://app_user:密码@内网IP:27017/intelligent_system?authSource=intelligent_system

MONGODB_DB_NAME=intelligent_system
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10

# ====== Firecrawl配置 ======
FIRECRAWL_API_KEY=your-api-key-here
FIRECRAWL_BASE_URL=https://api.firecrawl.dev
FIRECRAWL_TIMEOUT=30
FIRECRAWL_MAX_RETRIES=3

# ====== 其他服务配置（可选） ======
# MariaDB
MARIADB_URL=mysql+aiomysql://user:password@localhost:3306/db

# Redis
REDIS_URL=redis://localhost:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

### MongoDB连接字符串说明

**格式**: `mongodb://[username:password@]host[:port]/[database][?options]`

**示例**:
```bash
# 本地无认证
mongodb://localhost:27017/intelligent_system

# 本地有认证
mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin

# 远程连接
mongodb://app_user:MyPass123@192.168.0.50:27017/intelligent_system?authSource=intelligent_system

# 特殊字符密码需URL编码
# 例如: password@123 → password%40123
mongodb://user:password%40123@host:27017/db
```

---

## 📚 常用命令

### 服务管理

```bash
# 启动服务（开发模式）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 启动服务（生产模式）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

# 使用启动脚本
./scripts/start_local.sh

# 停止服务
# 前台运行: Ctrl+C
# 后台运行: pkill -f "uvicorn src.main:app"
```

### Docker管理

```bash
# 启动MongoDB
docker-compose -f docker-compose.mongodb.yml up -d

# 停止MongoDB
docker-compose -f docker-compose.mongodb.yml down

# 查看日志
docker-compose -f docker-compose.mongodb.yml logs -f

# 查看容器状态
docker ps | grep mongodb
```

### VPN管理

```bash
# 连接VPN
./scripts/vpn_connect.sh connect

# 断开VPN
./scripts/vpn_connect.sh disconnect

# 查看状态
./scripts/vpn_connect.sh status

# 查看日志
./scripts/vpn_connect.sh log

# 测试数据库
./scripts/vpn_connect.sh test
```

### 数据库管理

```bash
# 运行迁移
python scripts/run_migrations.py migrate

# 查看迁移状态
python scripts/run_migrations.py status

# 回滚迁移
python scripts/run_migrations.py rollback

# 连接MongoDB（Docker）
mongosh "mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin"
```

### 开发工具

```bash
# 代码格式化
black src/

# 代码检查
pylint src/

# 类型检查
mypy src/

# 运行测试
pytest tests/

# 查看测试覆盖率
pytest --cov=src tests/
```

---

## 🔍 故障排查

### 问题1: 端口被占用

**错误信息**:
```
Error: Address already in use
```

**解决方法**:
```bash
# 查找占用端口的进程
lsof -i :8000

# 停止进程
kill <PID>

# 或修改 .env 中的PORT配置
PORT=8001
```

---

### 问题2: MongoDB连接失败

**错误信息**:
```
MongoDB连接失败: 连接超时
```

**解决方法**:

1. **检查MongoDB是否运行**:
```bash
# Docker方式
docker ps | grep mongodb

# 本地安装
ps aux | grep mongod
```

2. **启动MongoDB**:
```bash
# Docker方式
docker-compose -f docker-compose.mongodb.yml up -d

# 等待启动完成
sleep 5
docker ps | grep mongodb
```

3. **检查连接字符串**:
```bash
# 验证 .env 中的 MONGODB_URL 配置
grep MONGODB_URL .env
```

4. **测试连接**:
```bash
mongosh "mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin"
```

5. **如果仍失败，使用降级模式**:
   - 应用会自动降级，使用内存存储
   - 数据不会持久化

---

### 问题3: Firecrawl API错误

**错误信息**:
```
401 Unauthorized: Invalid API key
```

**解决方法**:

1. **检查API密钥**:
```bash
grep FIRECRAWL_API_KEY .env
```

2. **验证密钥**:
   - 登录 https://firecrawl.dev
   - 检查API密钥是否正确
   - 确认密钥未过期

3. **更新配置**:
```bash
nano .env
# 更新 FIRECRAWL_API_KEY=新密钥
```

4. **重启应用**:
```bash
# Ctrl+C 停止
python -m uvicorn src.main:app --reload
```

---

### 问题4: VPN连接失败

**错误信息**:
```
VPN连接超时
```

**解决方法**:

1. **检查VPN配置文件**:
```bash
ls -la vpn/lxg.ovpn
```

2. **检查OpenVPN安装**:
```bash
which openvpn
# 如果未安装
brew install openvpn
```

3. **运行VPN诊断**:
```bash
./scripts/diagnose_vpn_database.sh
```

4. **查看VPN日志**:
```bash
./scripts/vpn_connect.sh log
```

5. **联系管理员**:
   - 确认VPN账号状态
   - 获取数据库内网IP
   - 检查防火墙规则

详细VPN故障排查: [docs/VPN_DATABASE_GUIDE.md](docs/VPN_DATABASE_GUIDE.md#故障排查)

---

### 问题5: 模块导入错误

**错误信息**:
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方法**:

1. **确认虚拟环境已激活**:
```bash
which python
# 应该显示虚拟环境路径
```

2. **重新安装依赖**:
```bash
pip install -r requirements.txt
```

3. **清理并重新安装**:
```bash
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 问题6: Docker启动失败

**错误信息**:
```
Cannot connect to the Docker daemon
```

**解决方法**:

1. **启动Docker Desktop**:
```bash
open -a Docker  # macOS
```

2. **等待Docker启动**:
```bash
# 等待30秒左右
sleep 30
docker ps
```

3. **检查Docker状态**:
```bash
docker info
```

4. **重启Docker**:
   - 退出Docker Desktop
   - 重新打开

---

## 🎯 进阶配置

### 生产环境部署

```bash
# 使用多个workers
python -m uvicorn src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-reload

# 使用Gunicorn（推荐）
gunicorn src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 日志配置

```bash
# 修改 .env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# 查看日志
tail -f logs/server.log
```

### 性能优化

```bash
# MongoDB连接池
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10

# Firecrawl超时
FIRECRAWL_TIMEOUT=30
FIRECRAWL_MAX_RETRIES=3

# Workers数量（生产环境）
WORKERS=4  # CPU核心数 * 2 + 1
```

### 安全配置

```bash
# 生产环境必须修改
SECRET_KEY=生成一个强密码
DEBUG=false

# CORS配置
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

---

## 📖 相关文档

### 核心文档
- [系统架构](docs/SYSTEM_ARCHITECTURE.md)
- [API使用指南](docs/API_GUIDE.md)
- [调度器指南](docs/SCHEDULER_GUIDE.md)

### 配置文档
- [MongoDB配置](docs/MONGODB_GUIDE.md)
- [Firecrawl集成](docs/FIRECRAWL_GUIDE.md)
- [VPN数据库连接](docs/VPN_DATABASE_GUIDE.md)

### 开发文档
- [后端开发指南](docs/BACKEND_DEVELOPMENT.md)
- [测试文档](tests/README.md)
- [文档中心](docs/README.md)

---

## 🆘 获取帮助

### 在线资源
- **API文档**: http://localhost:8000/api/docs (启动后访问)
- **项目文档**: [docs/README.md](docs/README.md)
- **变更日志**: [CHANGELOG.md](CHANGELOG.md)

### 常见问题
- MongoDB连接问题: [docs/MONGODB_GUIDE.md](docs/MONGODB_GUIDE.md)
- VPN配置问题: [docs/VPN_DATABASE_GUIDE.md](docs/VPN_DATABASE_GUIDE.md)
- API使用问题: [docs/API_GUIDE.md](docs/API_GUIDE.md)

### 支持渠道
- GitHub Issues
- 技术文档
- 团队联系方式

---

## 📝 快速参考卡

### 最常用命令

```bash
# 启动服务
./scripts/start_local.sh

# 启动MongoDB
docker-compose -f docker-compose.mongodb.yml up -d

# 连接VPN
./scripts/vpn_connect.sh connect

# 健康检查
curl http://localhost:8000/health

# API文档
open http://localhost:8000/api/docs

# 停止服务
pkill -f "uvicorn src.main:app"
```

### 服务地址

| 服务 | 地址 |
|------|------|
| API文档 | http://localhost:8000/api/docs |
| 健康检查 | http://localhost:8000/health |
| 调度器状态 | http://localhost:8000/api/v1/scheduler/status |
| MongoDB | localhost:27017 |

---

**最后更新**: 2025-10-21
**维护团队**: Backend Team
**文档版本**: v1.0

祝您使用愉快！ 🎉
