# 项目快速启动指南

## 环境要求

- Python 3.11+
- Docker & Docker Compose
- 8GB+ RAM (推荐16GB)
- 20GB+ 可用磁盘空间

## 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd guanshanPython
```

### 2. 配置环境
```bash
# 复制环境配置模板
cp .env.example .env
# 编辑 .env 文件设置必要的API密钥和配置
```

### 3. 启动依赖服务
```bash
# 使用项目根目录的 docker-compose.yml
make docker-up
# 或直接运行
docker-compose up -d
```

### 4. 安装Python依赖
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. 运行应用
```bash
make run
# 或直接运行
python -m uvicorn src.main:app --reload
```

## 配置文件说明

| 文件 | 描述 |
|------|------|
| `docker-compose.yml` | Docker服务编排配置 |
| `requirements.txt` | Python生产依赖 |
| `requirements-dev.txt` | Python开发依赖 |
| `.env.example` | 环境变量配置模板 |
| `Makefile` | 常用命令快捷方式 |

## 服务端口

- **FastAPI**: http://localhost:8000
- **API文档**: http://localhost:8000/api/docs
- **MongoDB**: localhost:27017
- **MariaDB**: localhost:3306
- **Redis**: localhost:6379
- **RabbitMQ**: localhost:5672 (管理界面: http://localhost:15672)
- **Qdrant**: http://localhost:6333

## 常用命令

```bash
make help         # 查看所有可用命令
make test        # 运行测试
make lint        # 代码检查
make format      # 代码格式化
make clean       # 清理缓存
```

## 健康检查

```bash
# 检查所有服务状态
make health-check
```

## 故障排查

### MongoDB连接失败
```bash
docker logs intelligent_mongo
# 检查连接字符串配置
```

### Celery任务未执行
```bash
make run-worker  # 启动Worker
# 检查任务队列
celery -A src.infrastructure.tasks inspect active
```

### 端口被占用
```bash
# 检查端口占用
lsof -i :8000
# 更改 .env 中的 PORT 配置
```

## 开发流程

1. 创建功能分支: `git checkout -b feature/your-feature`
2. 安装开发依赖: `pip install -r requirements-dev.txt`
3. 编写代码和测试
4. 运行测试: `make test`
5. 提交代码: `git commit -m "feat: description"`

## 部署

参考 [部署文档](./DEPLOYMENT.md) 了解生产环境部署详情。