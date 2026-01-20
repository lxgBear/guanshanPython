# 关山智能系统 (Guanshan Intelligence System)

## 项目概述
基于 Firecrawl + LLM + RAG Pipeline 的智能信息采集与处理平台，核心功能是定时搜索任务管理系统。

## 核心功能
- **定时搜索任务**: 支持多种调度间隔的自动化搜索 (HOURLY_1, HOURLY_6, HOURLY_12, DAILY, DAYS_3, WEEKLY)
- **智能搜索引擎**: 基于 Firecrawl 的网页内容爬取
- **LangGraph 搜索**: 基于 LangGraph 的智能搜索工作流
- **任务调度器**: APScheduler 驱动的高性能任务管理
- **认证系统**: JWT 认证 + 角色权限管理
- **RAG Pipeline**: 文档嵌入和检索

## 技术栈

### 核心框架
- **Web框架**: FastAPI 0.109+ (异步高性能)
- **Python版本**: 3.13+
- **配置管理**: Pydantic Settings

### 数据存储
- **主数据库**: MongoDB (motor 异步驱动)
- **备用存储**: InMemory Repository
- **向量数据库**: Qdrant
- **缓存**: Redis

### AI/ML
- **LLM集成**: LangChain + OpenAI + Anthropic
- **嵌入模型**: text-embedding-3-small
- **RAG**: Chunk-based retrieval

### 任务处理
- **调度器**: APScheduler (AsyncIOScheduler)
- **消息队列**: Celery + RabbitMQ
- **搜索服务**: Firecrawl API

## 代码结构

```
src/
├── main.py                  # 应用入口 (lifespan 管理)
├── config.py                # 全局配置 (Pydantic Settings)
│
├── api/v1/                  # API 层
│   ├── router.py            # 路由聚合
│   ├── endpoints/           # REST 端点
│   │   ├── auth/            # 认证相关
│   │   ├── chat.py          # 聊天接口
│   │   ├── instant_search.py # 即时搜索
│   │   ├── smart_search.py  # 智能搜索
│   │   └── scheduler_management.py # 调度管理
│   └── dependencies/        # 依赖注入
│
├── core/                    # 核心层
│   ├── domain/              # 领域模型
│   │   ├── entities/        # 实体定义
│   │   └── interfaces/      # 抽象接口
│   ├── events/              # 事件总线
│   └── interfaces/          # 层接口
│
├── services/                # 服务层
│   ├── langgraph_search/    # LangGraph 搜索 (graph, nodes, state)
│   ├── auth/                # 认证服务
│   ├── firecrawl/           # Firecrawl 集成
│   ├── orchestrators/       # 编排器
│   └── task_scheduler.py    # 任务调度
│
├── infrastructure/          # 基础设施层
│   ├── database/            # 数据库连接
│   ├── llm/                 # LLM 客户端
│   ├── auth/                # JWT 实现
│   ├── crawlers/            # 爬虫实现
│   └── persistence/         # 持久化
│
└── utils/                   # 工具函数
    └── logger.py            # 日志配置
```

## 关键文件路径

### 入口和配置
- `src/main.py` - 应用入口
- `src/config.py` - 全局配置
- `.env` - 环境变量

### API 层
- `src/api/v1/router.py` - 路由定义
- `src/api/v1/endpoints/` - 所有 API 端点

### 业务逻辑
- `src/services/langgraph_search/` - LangGraph 搜索系统
- `src/services/task_scheduler.py` - 任务调度

### 数据模型
- `src/core/domain/entities/` - 所有实体定义
- `src/core/domain/interfaces/` - 接口定义

## 架构特点

1. **清洁架构**: 分层设计 (API → Services → Domain → Infrastructure)
2. **依赖注入**: FastAPI 依赖注入系统
3. **异步优先**: 全栈异步 (async/await)
4. **降级模式**: MongoDB 不可用时自动切换内存存储
5. **事件驱动**: 事件总线解耦组件

## 当前开发状态
- 分支: `feature/llm-driven-language-detection-115`
- 版本: v4.7.0+
