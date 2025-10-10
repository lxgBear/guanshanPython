# 后端开发指南

## 架构设计

### 六边形架构 (Hexagonal Architecture)

系统采用六边形架构，实现业务逻辑与技术实现的完全分离：

```
┌─────────────────────────────────────┐
│         API Layer (FastAPI)         │
└─────────────────────────────────────┘
                 ↕
┌─────────────────────────────────────┐
│       Application Services          │
└─────────────────────────────────────┘
                 ↕
┌─────────────────────────────────────┐
│        Domain (Core Logic)          │
└─────────────────────────────────────┘
                 ↕
┌─────────────────────────────────────┐
│     Infrastructure (Technical)      │
└─────────────────────────────────────┘
```

### 核心原则

- **SOLID原则**: 单一职责、开闭原则、里氏替换、接口隔离、依赖倒置
- **DRY**: 不重复原则
- **KISS**: 保持简单
- **YAGNI**: 只实现当前需求

### 设计模式

| 模式 | 用途 | 应用场景 |
|------|------|----------|
| Repository | 数据访问抽象 | MongoDB/MariaDB操作 |
| Factory | 对象创建 | Crawler/LLM实例化 |
| Strategy | 算法切换 | 检索/排序策略 |
| Pipeline | 流式处理 | RAG管道 |
| Observer | 事件通知 | 任务状态变更 |

## 项目结构

```
src/
├── api/               # API层
│   ├── v1/           # API版本
│   │   ├── endpoints/  # 端点定义
│   │   └── schemas/    # Pydantic模型
│   └── deps.py       # 依赖注入
├── application/       # 应用服务层
│   └── services/     # 业务服务
├── core/             # 核心域
│   ├── domain/       # 领域模型
│   └── services/     # 领域服务  
├── infrastructure/   # 基础设施
│   ├── database/     # 数据库连接
│   ├── crawlers/     # 爬虫实现
│   ├── llm/         # LLM集成
│   ├── rag/         # RAG管道
│   └── tasks/       # Celery任务
├── config.py        # 配置管理
└── main.py          # 应用入口
```

## 核心实现

### 1. 应用入口

```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.config import settings
from src.api.v1 import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    await init_services()
    yield
    # 关闭时清理
    await cleanup_services()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")
```

### 2. 领域模型

```python
# src/core/domain/entities/document.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Document:
    id: UUID = field(default_factory=uuid4)
    url: str = ""
    content: str = ""
    status: DocumentStatus = DocumentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_processable(self) -> bool:
        return self.status in [DocumentStatus.PENDING, DocumentStatus.FAILED]
```

### 3. 仓库模式

```python
# src/infrastructure/repositories/mongodb/document_repository.py
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.domain.repositories import DocumentRepositoryInterface

class MongoDocumentRepository(DocumentRepositoryInterface):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.documents
    
    async def get(self, id: UUID) -> Optional[Document]:
        data = await self.collection.find_one({"_id": str(id)})
        return Document(**data) if data else None
    
    async def save(self, document: Document) -> Document:
        await self.collection.insert_one(document.dict())
        return document
```

### 4. API端点

```python
# src/api/v1/endpoints/documents.py
from fastapi import APIRouter, Depends, HTTPException
from src.api.deps import get_document_service

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/", response_model=DocumentResponse)
async def create_document(
    request: DocumentCreateRequest,
    service = Depends(get_document_service)
):
    try:
        document = await service.create_document(
            url=request.url,
            content=request.content
        )
        return DocumentResponse.from_entity(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 5. RAG管道

```python
# src/infrastructure/rag/pipeline.py
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class RAGContext:
    query: str
    retrieved_documents: List[Dict[str, Any]]
    generated_answer: Optional[str] = None

class RAGPipeline:
    def __init__(self):
        self.steps = []
    
    def add_step(self, step: RAGStep):
        self.steps.append(step)
        return self
    
    async def run(self, query: str) -> RAGContext:
        context = RAGContext(query=query, retrieved_documents=[])
        for step in self.steps:
            context = await step.execute(context)
        return context
```

### 6. 异步任务

```python
# src/infrastructure/tasks/document_tasks.py
from celery import Celery

celery_app = Celery(
    "intelligent_system",
    broker=settings.RABBITMQ_URL,
    backend=f"redis://{settings.REDIS_URL}"
)

@celery_app.task(name="process_document")
def process_document_task(document_id: str):
    # 异步处理文档
    return {"status": "success", "document_id": document_id}
```

## 数据层设计

### MongoDB (文档存储)
- 文档内容
- 爬取结果
- 非结构化数据

### MariaDB (关系数据)
- 用户信息
- 权限管理
- 审计日志

### Redis (缓存)
- 会话管理
- 临时数据
- 任务队列结果

### Qdrant (向量搜索)
- 文档嵌入
- 相似度搜索
- RAG检索

## API设计规范

### RESTful原则
- 使用HTTP动词: GET, POST, PUT, DELETE
- 资源命名使用复数: `/api/v1/documents`
- 状态码规范: 200, 201, 400, 401, 403, 404, 500

### 请求/响应格式
```python
# 请求
class DocumentCreateRequest(BaseModel):
    url: str = Field(..., description="文档URL")
    content: Optional[str] = Field(None, description="文档内容")

# 响应
class DocumentResponse(BaseModel):
    id: UUID
    url: str
    status: DocumentStatus
    created_at: datetime
```

## 异步处理

### Celery配置
```python
# 任务配置
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
task_time_limit = 30 * 60  # 30分钟
```

### 任务类型
- **即时任务**: API直接处理
- **异步任务**: Celery队列处理
- **定时任务**: Celery Beat调度

## 错误处理

### 异常层级
1. **领域异常**: 业务规则违反
2. **应用异常**: 服务层错误
3. **基础设施异常**: 技术故障

### 错误响应
```python
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

## 测试策略

### 测试类型
- **单元测试**: 测试单个组件
- **集成测试**: 测试组件交互
- **E2E测试**: 测试完整流程

### 测试示例
```python
# tests/unit/test_document_service.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_create_document():
    # 准备
    mock_repo = Mock()
    mock_repo.save = AsyncMock(return_value=document)
    service = DocumentService(mock_repo)
    
    # 执行
    result = await service.create_document(url="test.com")
    
    # 验证
    assert result.url == "test.com"
    mock_repo.save.assert_called_once()
```

## 性能优化

### 数据库优化
- 创建合适索引
- 使用连接池
- 批量操作

### 缓存策略
- Redis缓存热点数据
- 设置合理TTL
- 缓存失效策略

### 异步优化
- 使用异步IO
- 并发请求限制
- 任务队列优化

## 安全实践

### 认证授权
- JWT Token认证
- 基于角色的访问控制
- API密钥管理

### 数据安全
- 输入验证
- SQL注入防护
- XSS防护
- 敏感数据加密

### 安全配置
```python
# 安全头部
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block"
}
```

## 部署配置

### Docker化
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0"]
```

### 环境变量
参考 `.env.example` 配置必要的环境变量

### 监控指标
- API响应时间
- 错误率
- 资源使用率
- 业务指标

## 开发工作流

1. **需求分析**: 理解业务需求
2. **设计**: 领域建模、API设计
3. **实现**: 编码实现
4. **测试**: 单元测试、集成测试
5. **代码审查**: PR审查
6. **部署**: CI/CD流程

## 最佳实践

### 代码规范
- 使用Black格式化
- 类型注解
- Docstring文档
- 有意义的命名

### Git工作流
- Feature分支开发
- Commit规范 (feat, fix, docs, refactor)
- PR模板
- Code Review

### 文档维护
- API文档自动生成
- README保持更新
- 架构决策记录

## 常见问题

### Q: 如何添加新的API端点？
A: 在 `src/api/v1/endpoints/` 创建新文件，定义router，在 `api_router` 中注册。

### Q: 如何实现新的爬虫？
A: 继承 `BaseCrawler`，实现 `crawl()` 方法，在 `CrawlerFactory` 中注册。

### Q: 如何添加新的Celery任务？
A: 在 `src/infrastructure/tasks/` 创建任务文件，使用 `@celery_app.task` 装饰器。

### Q: 如何扩展RAG管道？
A: 实现 `RAGStep` 接口，添加到 `RAGPipeline` 中。

## 相关文档

- [系统架构](./GUANSHAN_ARCHITECTURE.md)
- [项目设置](./PROJECT_SETUP.md)
- [功能追踪](./FEATURE_TRACKER.md)
- [版本管理](./VERSION_MANAGEMENT.md)