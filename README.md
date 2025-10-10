# 关山智能信息采集整编系统 (Guanshan Intelligence System)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg)](https://www.mongodb.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-11.0-blue.svg)](https://mariadb.org/)

基于 **Firecrawl + LLM + RAG Pipeline + Reranking** 的智能信息采集与处理平台

## 🎯 系统概述

关山智能系统是一个模块化、高性能的信息采集与智能处理平台，采用六边形架构设计，实现业务逻辑与技术细节的完全分离。

### 核心特性

- 🏗️ **六边形架构**: 业务核心与技术实现解耦
- 🔧 **模块化设计**: 高内聚、低耦合、易扩展
- 🚀 **异步高性能**: 基于FastAPI异步框架
- 🤖 **AI原生**: 集成LLM和RAG管道
- 📊 **双数据库**: MongoDB文档存储 + MariaDB关系数据
- 🔍 **向量搜索**: Qdrant向量数据库支持
- ⚡ **任务队列**: Celery + RabbitMQ异步处理

## 📚 文档结构

| 文档 | 描述 |
|------|------|
| [开发指南](docs/BACKEND_DEVELOPMENT.md) | 架构设计、开发规范与代码示例 |
| [快速开始](docs/PROJECT_SETUP.md) | 项目环境搭建与配置 |
| [系统架构](docs/GUANSHAN_ARCHITECTURE.md) | 关山系统详细架构设计 |
| [Firecrawl集成](docs/FIRECRAWL_INTEGRATION.md) | Firecrawl爬虫集成方案 |
| [项目管理](docs/FEATURE_TRACKER.md) | 功能开发进度跟踪 |
| [版本记录](docs/VERSION_MANAGEMENT.md) | 版本发布与变更历史 |

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose
- 8GB+ RAM
- 20GB+ 磁盘空间

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd guanshanPython
```

2. **启动依赖服务**
```bash
docker-compose up -d
```

3. **安装Python依赖**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件配置必要参数
```

5. **运行应用**
```bash
python -m uvicorn src.main:app --reload
```

访问 http://localhost:8000/api/docs 查看API文档

## 🏗️ 技术架构

### 核心技术栈

- **Web框架**: FastAPI (异步、高性能)
- **数据存储**: 
  - MongoDB (文档存储)
  - MariaDB (结构化数据)
  - Redis (缓存)
  - Qdrant (向量数据库)
- **消息队列**: RabbitMQ + Celery
- **AI/ML**: 
  - LangChain (AI编排)
  - OpenAI/Claude (LLM)
  - RAG Pipeline (检索增强生成)
- **爬虫**: Firecrawl
- **容器化**: Docker + Kubernetes

### 系统架构

```
┌─────────────────────────────────────────┐
│           API Gateway (FastAPI)          │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│          Application Services            │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Document │ │   RAG    │ │ Crawler │ │
│  │ Service  │ │ Service  │ │ Service │ │
│  └──────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│           Domain Services                │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Business │ │ Document │ │  User   │ │
│  │   Logic  │ │  Domain  │ │ Domain  │ │
│  └──────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│          Infrastructure Layer            │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐│
│  │Mongo │ │Maria │ │Redis │ │ Qdrant ││
│  │  DB  │ │  DB  │ │Cache │ │ Vector ││
│  └──────┘ └──────┘ └──────┘ └────────┘│
└─────────────────────────────────────────┘
```

## 🔧 开发指南

### 项目结构

```
intelligent-system/
├── src/                      # 源代码
│   ├── api/                 # API层
│   ├── application/         # 应用服务层
│   ├── core/               # 核心业务层
│   └── infrastructure/     # 基础设施层
├── tests/                   # 测试代码
├── docs/                    # 文档
├── scripts/                 # 脚本工具
└── configs/                 # 配置文件
```

### 开发流程

1. **创建功能分支**
```bash
git checkout -b feature/your-feature
```

2. **运行测试**
```bash
pytest tests/
```

3. **代码质量检查**
```bash
black src tests
flake8 src tests
mypy src
```

4. **提交代码**
```bash
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature
```

## 📊 监控与运维

- **健康检查**: `GET /health`
- **指标监控**: Prometheus metrics at `/metrics`
- **日志聚合**: 结构化JSON日志
- **追踪**: OpenTelemetry集成

## 🤝 贡献指南

欢迎贡献代码！请查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- FastAPI 团队提供的优秀Web框架
- LangChain 社区的AI工具链
- 所有开源贡献者

## 📞 联系方式

- 项目主页: [GitHub Repository](https://github.com/your-org/guanshan-system)
- 问题反馈: [Issue Tracker](https://github.com/your-org/guanshan-system/issues)
- 技术支持: support@guanshan-system.com

---

© 2025 Guanshan Team. All rights reserved.