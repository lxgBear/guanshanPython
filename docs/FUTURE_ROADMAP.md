# 关山智能情报处理平台 - 未来规划与架构愿景

> **文档性质**: 未来规划文档 (Future Roadmap)
> **状态**: 设计阶段，尚未实施
> **版本**: 1.0.0
> **更新日期**: 2025-01-10
> **代号**: Guanshan Intelligence System (GIS)

---

## ⚠️ 重要说明

**本文档描述的是关山智能系统的未来愿景和长期规划**，包含大量尚未实现的功能和架构设计。

### 当前实现状态
✅ **已实现**: 定时搜索任务系统 (参见 `SYSTEM_ARCHITECTURE.md`)
- MongoDB持久化存储
- APScheduler任务调度
- Firecrawl API集成
- RESTful API接口

❌ **未实现** (本文档描述的功能):
- RAG Pipeline + Reranking
- 智能翻译服务
- 报告生成模块
- 向量数据库集成
- Celery分布式任务队列
- LLM深度集成

### 文档用途
- 📋 技术规划参考
- 🎯 长期发展路线图
- 💡 架构设计思路
- 🔮 功能演进方向

**如需了解当前系统实际架构，请参阅**: [`SYSTEM_ARCHITECTURE.md`](./SYSTEM_ARCHITECTURE.md)

---

## 📋 产品定位

关山开源信息采集整编系统是一个基于 **Firecrawl + LLM + RAG Pipeline + Reranking** 的智能情报处理平台，实现从信息采集、文本清洗、智能翻译到结构化报告生成的全流程自动化。

### 核心价值
- 🌐 **全网信息采集**: 支持网页、PDF、API等多源数据采集
- 🧹 **智能文本处理**: 自动清洗、格式化、去噪
- 🌍 **多语言翻译**: 集成多家翻译API，支持60+语言
- 🤖 **RAG智能分析**: 基于检索增强生成的深度分析
- 📊 **结构化报告**: 自动生成专业情报报告

---

## 1. 系统架构总览

### 1.1 技术架构

```
┌──────────────────────────────────────────────────────────┐
│                     前端展示层                            │
│           Web UI / API Gateway / WebSocket               │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    应用服务层                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │   FastAPI Application Server (异步处理)           │   │
│  ├──────────────────────────────────────────────────┤   │
│  │  • 采集管理  • 任务调度  • 报告生成              │   │
│  │  • 用户认证  • API服务   • WebSocket推送         │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                  智能处理层 (AI Services)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐    │
│  │  Firecrawl  │  │     LLM     │  │     RAG      │    │
│  │   爬虫引擎  │  │   GPT/Claude │  │   Pipeline   │    │
│  └─────────────┘  └─────────────┘  └──────────────┘    │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐    │
│  │  翻译服务   │  │  文本清洗   │  │   Reranking  │    │
│  │ DeepL/Google│  │   NLP处理   │  │    重排序    │    │
│  └─────────────┘  └─────────────┘  └──────────────┘    │
└──────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    消息队列层                             │
│         RabbitMQ / Kafka (异步任务处理)                   │
│                  Celery (任务调度)                        │
└──────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                     数据存储层                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ MariaDB  │  │ MongoDB  │  │  Redis   │  │ MinIO  │  │
│  │ 元数据   │  │ 文档存储 │  │   缓存   │  │ 文件   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │          向量数据库 (Qdrant/Milvus)              │   │
│  │              嵌入向量存储与检索                    │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 1.2 核心技术栈

| 组件类型 | 技术选型 | 用途 | 选型理由 |
|---------|---------|------|---------|
| **Web框架** | FastAPI | API服务 | 异步支持、高性能、自动文档 |
| **爬虫引擎** | Firecrawl | 数据采集 | 强大的网页解析、JS渲染支持 |
| **LLM集成** | LangChain | AI编排 | 统一的LLM接口、RAG支持 |
| **向量数据库** | Qdrant | 向量检索 | 高性能、支持过滤、易扩展 |
| **文档数据库** | MongoDB | 非结构化存储 | 灵活Schema、横向扩展 |
| **关系数据库** | MariaDB | 结构化数据 | ACID事务、成熟稳定 |
| **消息队列** | RabbitMQ | 异步处理 | 可靠性高、支持优先级队列 |
| **任务调度** | Celery | 定时任务 | 分布式、支持任务链 |
| **缓存** | Redis | 高速缓存 | 内存存储、支持发布订阅 |
| **文件存储** | MinIO | 对象存储 | S3兼容、私有部署 |

---

## 2. 功能模块设计

### 2.1 信息采集模块

```python
# 模块结构
crawler/
├── engines/
│   ├── firecrawl_engine.py    # Firecrawl集成
│   ├── scrapy_engine.py       # Scrapy备用
│   └── api_crawler.py         # API数据源
├── parsers/
│   ├── html_parser.py         # HTML解析
│   ├── pdf_parser.py          # PDF提取
│   └── json_parser.py         # JSON处理
├── scheduler/
│   ├── task_queue.py          # 任务队列管理
│   ├── rate_limiter.py        # 访问频率控制
│   └── proxy_pool.py          # 代理池管理
└── storage/
    └── raw_data_store.py      # 原始数据存储
```

**核心功能**：
- 多源数据采集（网页、RSS、API、文件）
- JavaScript渲染支持
- 反爬虫策略（代理池、User-Agent轮换）
- 增量采集与去重
- 采集任务调度与监控

### 2.2 文本处理模块

```python
# 数据清洗流水线
class TextProcessor:
    async def process_pipeline(self, raw_text: str) -> ProcessedDocument:
        # 1. 基础清洗
        text = await self.clean_html(raw_text)
        text = await self.remove_noise(text)
        
        # 2. 格式标准化
        text = await self.normalize_format(text)
        
        # 3. 语言检测
        language = await self.detect_language(text)
        
        # 4. 分句分段
        segments = await self.segment_text(text)
        
        # 5. 实体识别
        entities = await self.extract_entities(segments)
        
        # 6. 关键词提取
        keywords = await self.extract_keywords(segments)
        
        return ProcessedDocument(
            text=text,
            language=language,
            segments=segments,
            entities=entities,
            keywords=keywords
        )
```

### 2.3 智能翻译模块

```python
# 翻译服务管理
class TranslationService:
    def __init__(self):
        self.engines = {
            'deepl': DeepLTranslator(),
            'google': GoogleTranslator(),
            'baidu': BaiduTranslator(),
            'openai': OpenAITranslator()
        }
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        engine: str = 'auto'
    ) -> TranslationResult:
        # 智能选择翻译引擎
        if engine == 'auto':
            engine = self.select_best_engine(source_lang, target_lang)
        
        # 批量处理长文本
        if len(text) > 5000:
            return await self.batch_translate(text, source_lang, target_lang)
        
        # 执行翻译
        result = await self.engines[engine].translate(
            text, source_lang, target_lang
        )
        
        # 质量评估
        quality_score = await self.evaluate_quality(result)
        
        return TranslationResult(
            text=result.text,
            engine=engine,
            quality_score=quality_score
        )
```

### 2.4 RAG智能分析模块

```python
# RAG Pipeline实现
class RAGPipeline:
    def __init__(self):
        self.embedder = SentenceTransformer('multilingual-e5-large')
        self.vector_db = QdrantClient(url='localhost:6333')
        self.llm = ChatOpenAI(model='gpt-4')
        self.reranker = CrossEncoder('ms-marco-MiniLM-L-6-v2')
    
    async def process(self, query: str, context_docs: List[Document]) -> str:
        # 1. 文档切片
        chunks = await self.chunk_documents(context_docs)
        
        # 2. 向量化
        embeddings = await self.embed_chunks(chunks)
        
        # 3. 存储到向量数据库
        await self.store_vectors(chunks, embeddings)
        
        # 4. 检索相关文档
        relevant_docs = await self.retrieve(query, top_k=20)
        
        # 5. 重排序
        reranked_docs = await self.rerank(query, relevant_docs, top_k=5)
        
        # 6. 生成答案
        answer = await self.generate_answer(query, reranked_docs)
        
        return answer
    
    async def retrieve(self, query: str, top_k: int = 20) -> List[Document]:
        # 向量检索
        query_embedding = self.embedder.encode(query)
        
        search_result = self.vector_db.search(
            collection_name="intelligence",
            query_vector=query_embedding,
            limit=top_k,
            query_filter=Filter(...)  # 添加过滤条件
        )
        
        return [hit.payload for hit in search_result]
    
    async def rerank(
        self,
        query: str,
        docs: List[Document],
        top_k: int = 5
    ) -> List[Document]:
        # 交叉编码器重排序
        pairs = [[query, doc.content] for doc in docs]
        scores = self.reranker.predict(pairs)
        
        # 按分数排序
        sorted_docs = sorted(
            zip(docs, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [doc for doc, _ in sorted_docs[:top_k]]
```

### 2.5 报告生成模块

```python
# 智能报告生成
class ReportGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(model='gpt-4')
        self.templates = TemplateManager()
        self.formatter = DocumentFormatter()
    
    async def generate_report(
        self,
        analysis_results: Dict,
        report_type: str = 'intelligence'
    ) -> Report:
        # 1. 选择报告模板
        template = self.templates.get_template(report_type)
        
        # 2. 结构化内容生成
        sections = await self.generate_sections(analysis_results, template)
        
        # 3. 执行摘要生成
        executive_summary = await self.generate_summary(sections)
        
        # 4. 图表生成
        charts = await self.generate_charts(analysis_results)
        
        # 5. 格式化输出
        formatted_report = await self.formatter.format(
            title=analysis_results['title'],
            summary=executive_summary,
            sections=sections,
            charts=charts,
            metadata=analysis_results['metadata']
        )
        
        # 6. 导出多种格式
        outputs = {
            'html': await self.export_html(formatted_report),
            'pdf': await self.export_pdf(formatted_report),
            'docx': await self.export_docx(formatted_report),
            'json': await self.export_json(formatted_report)
        }
        
        return Report(
            id=str(uuid4()),
            content=formatted_report,
            outputs=outputs,
            created_at=datetime.utcnow()
        )
```

---

## 3. 数据流设计

### 3.1 主数据流程

```mermaid
graph LR
    A[数据源] --> B[Firecrawl采集]
    B --> C[原始数据存储]
    C --> D[文本清洗]
    D --> E[语言检测]
    E --> F{需要翻译?}
    F -->|是| G[智能翻译]
    F -->|否| H[文档切片]
    G --> H
    H --> I[向量化]
    I --> J[向量数据库]
    J --> K[RAG检索]
    K --> L[重排序]
    L --> M[LLM分析]
    M --> N[报告生成]
    N --> O[多格式输出]
```

### 3.2 异步任务流

```python
# Celery任务链定义
from celery import chain, group, chord

# 定义任务链
def create_intelligence_pipeline(source_url: str, config: Dict):
    return chain(
        # 采集任务
        crawl_task.s(source_url, config),
        
        # 并行处理
        group(
            clean_text_task.s(),
            extract_metadata_task.s(),
            detect_language_task.s()
        ),
        
        # 条件任务
        translate_if_needed_task.s(),
        
        # RAG处理链
        chain(
            chunk_document_task.s(),
            generate_embeddings_task.s(),
            store_vectors_task.s()
        ),
        
        # 分析和报告
        chord(
            group(
                rag_analysis_task.s(),
                entity_extraction_task.s(),
                sentiment_analysis_task.s()
            )
        )(generate_report_task.s())
    )
```

---

## 4. API接口设计

### 4.1 RESTful API

```python
# API路由定义
from fastapi import APIRouter, Depends, BackgroundTasks
from typing import List, Optional

router = APIRouter(prefix="/api/v1")

# 采集任务API
@router.post("/crawl/tasks", response_model=TaskResponse)
async def create_crawl_task(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    创建采集任务
    - 支持单个URL或批量URL
    - 可配置采集深度、频率、代理等
    """
    task_id = str(uuid4())
    
    # 异步执行采集
    background_tasks.add_task(
        execute_crawl_pipeline,
        task_id=task_id,
        urls=request.urls,
        config=request.config,
        user_id=current_user.id
    )
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        created_at=datetime.utcnow()
    )

# RAG查询API
@router.post("/intelligence/query", response_model=QueryResponse)
async def query_intelligence(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    智能查询接口
    - 支持自然语言查询
    - 返回相关文档和分析结果
    """
    # 执行RAG检索
    results = await rag_pipeline.process(
        query=request.query,
        filters=request.filters,
        top_k=request.top_k
    )
    
    return QueryResponse(
        query=request.query,
        results=results,
        sources=results.sources,
        confidence=results.confidence_score
    )

# 报告生成API
@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    生成情报报告
    - 支持多种报告模板
    - 可导出PDF/Word/HTML
    """
    report = await report_generator.generate(
        data_sources=request.source_ids,
        template=request.template,
        language=request.language,
        format=request.output_format
    )
    
    return ReportResponse(
        report_id=report.id,
        title=report.title,
        download_url=report.download_url,
        preview_url=report.preview_url
    )
```

### 4.2 WebSocket实时推送

```python
# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.send_personal_message(
            {"type": "connection", "message": "Connected successfully"},
            client_id
        )
    
    async def broadcast_task_update(self, task_id: str, update: Dict):
        """广播任务状态更新"""
        message = {
            "type": "task_update",
            "task_id": task_id,
            "status": update["status"],
            "progress": update["progress"],
            "message": update.get("message"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for connection in self.active_connections.values():
            await connection.send_json(message)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...)
):
    # 验证token
    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            
            # 处理不同类型的消息
            if data["type"] == "subscribe_task":
                await subscribe_to_task(client_id, data["task_id"])
            elif data["type"] == "query":
                result = await process_realtime_query(data["query"])
                await manager.send_personal_message(result, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
```

---

## 5. 安全与合规

### 5.1 数据安全

```python
# 数据加密和脱敏
class DataSecurity:
    def __init__(self):
        self.encryptor = Fernet(settings.ENCRYPTION_KEY)
        self.pii_detector = PIIDetector()
    
    async def process_sensitive_data(self, data: str) -> str:
        # 1. PII检测
        pii_entities = await self.pii_detector.detect(data)
        
        # 2. 数据脱敏
        masked_data = await self.mask_pii(data, pii_entities)
        
        # 3. 加密存储
        if self.requires_encryption(data):
            encrypted_data = self.encrypt(masked_data)
            return encrypted_data
        
        return masked_data
    
    def mask_pii(self, text: str, entities: List[PIIEntity]) -> str:
        """PII数据脱敏"""
        for entity in entities:
            if entity.type == 'email':
                text = text.replace(entity.value, self.mask_email(entity.value))
            elif entity.type == 'phone':
                text = text.replace(entity.value, self.mask_phone(entity.value))
            elif entity.type == 'id_card':
                text = text.replace(entity.value, '***')
        return text
```

### 5.2 访问控制

```python
# RBAC权限模型
class RBACPermission:
    """基于角色的访问控制"""
    
    ROLES = {
        'admin': ['*'],  # 所有权限
        'analyst': [
            'crawl:read', 'crawl:create',
            'report:read', 'report:create',
            'intelligence:query'
        ],
        'viewer': [
            'report:read',
            'intelligence:query'
        ]
    }
    
    @classmethod
    def check_permission(
        cls,
        user: User,
        resource: str,
        action: str
    ) -> bool:
        permission = f"{resource}:{action}"
        user_permissions = cls.ROLES.get(user.role, [])
        
        return '*' in user_permissions or permission in user_permissions

# API权限装饰器
def require_permission(resource: str, action: str):
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ):
        if not RBACPermission.check_permission(
            current_user, resource, action
        ):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        return current_user
    return permission_checker

# 使用示例
@router.post("/crawl/tasks")
async def create_task(
    request: CrawlRequest,
    user: User = Depends(require_permission("crawl", "create"))
):
    pass
```

### 5.3 审计日志

```python
# 审计日志记录
class AuditLogger:
    async def log_operation(
        self,
        user_id: str,
        operation: str,
        resource: str,
        details: Dict,
        ip_address: str
    ):
        audit_log = {
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "operation": operation,
            "resource": resource,
            "details": details,
            "ip_address": ip_address,
            "user_agent": details.get("user_agent"),
            "status": details.get("status", "success")
        }
        
        # 存储到MongoDB
        await self.audit_collection.insert_one(audit_log)
        
        # 关键操作告警
        if operation in ['delete', 'export', 'admin_action']:
            await self.send_security_alert(audit_log)
```

---

## 6. 性能优化

### 6.1 缓存策略

```python
# 多级缓存实现
class CacheManager:
    def __init__(self):
        self.redis_client = Redis(
            host='localhost',
            decode_responses=True,
            connection_pool=BlockingConnectionPool(max_connections=50)
        )
        self.local_cache = TTLCache(maxsize=1000, ttl=300)
    
    async def get_with_cache(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 3600
    ):
        # 1. 本地缓存
        if key in self.local_cache:
            return self.local_cache[key]
        
        # 2. Redis缓存
        redis_value = await self.redis_client.get(key)
        if redis_value:
            value = json.loads(redis_value)
            self.local_cache[key] = value
            return value
        
        # 3. 获取并缓存
        value = await fetch_func()
        await self.redis_client.setex(
            key,
            ttl,
            json.dumps(value)
        )
        self.local_cache[key] = value
        
        return value
```

### 6.2 批处理优化

```python
# 批量处理优化
class BatchProcessor:
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.queue = asyncio.Queue()
        self.processing = False
    
    async def add_item(self, item: Any):
        await self.queue.put(item)
        
        if not self.processing:
            asyncio.create_task(self.process_batch())
    
    async def process_batch(self):
        self.processing = True
        batch = []
        
        while True:
            try:
                # 收集批次
                while len(batch) < self.batch_size:
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                    batch.append(item)
                    
            except asyncio.TimeoutError:
                # 超时则处理当前批次
                if batch:
                    await self.process_items(batch)
                    batch = []
                    
                if self.queue.empty():
                    self.processing = False
                    break
    
    async def process_items(self, items: List):
        """批量处理逻辑"""
        # 批量向量化
        embeddings = self.model.encode_batch(items)
        
        # 批量存储
        await self.vector_db.upsert_batch(embeddings)
```

### 6.3 异步并发控制

```python
# 并发限制
class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_limit(self, coro):
        async with self.semaphore:
            return await coro

# 使用示例
async def crawl_multiple_urls(urls: List[str]):
    limiter = ConcurrencyLimiter(max_concurrent=5)
    
    tasks = [
        limiter.run_with_limit(crawl_url(url))
        for url in urls
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

---

## 7. 监控与运维

### 7.1 系统监控

```python
# Prometheus指标定义
from prometheus_client import Counter, Histogram, Gauge

# 定义监控指标
crawl_requests_total = Counter(
    'crawl_requests_total',
    'Total number of crawl requests',
    ['status', 'source']
)

crawl_duration_seconds = Histogram(
    'crawl_duration_seconds',
    'Time spent crawling',
    ['source_type']
)

active_crawl_tasks = Gauge(
    'active_crawl_tasks',
    'Number of active crawl tasks'
)

rag_query_latency = Histogram(
    'rag_query_latency_seconds',
    'RAG query latency',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

vector_db_size = Gauge(
    'vector_db_documents_total',
    'Total documents in vector database'
)

# 监控中间件
@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # 记录指标
    if request.url.path.startswith("/api/v1/crawl"):
        crawl_duration_seconds.labels(
            source_type=request.query_params.get("type", "web")
        ).observe(duration)
    
    return response
```

### 7.2 健康检查

```python
@router.get("/health", tags=["monitoring"])
async def health_check():
    """系统健康检查"""
    checks = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "services": {}
    }
    
    # 检查各个服务
    try:
        # MariaDB
        await mariadb_session.execute("SELECT 1")
        checks["services"]["mariadb"] = "healthy"
    except Exception as e:
        checks["services"]["mariadb"] = f"unhealthy: {str(e)}"
        checks["status"] = "degraded"
    
    try:
        # MongoDB
        await mongodb_client.admin.command("ping")
        checks["services"]["mongodb"] = "healthy"
    except Exception as e:
        checks["services"]["mongodb"] = f"unhealthy: {str(e)}"
        checks["status"] = "degraded"
    
    try:
        # Redis
        await redis_client.ping()
        checks["services"]["redis"] = "healthy"
    except Exception as e:
        checks["services"]["redis"] = f"unhealthy: {str(e)}"
        checks["status"] = "degraded"
    
    try:
        # Vector DB
        collections = await vector_client.get_collections()
        checks["services"]["vector_db"] = f"healthy ({len(collections)} collections)"
    except Exception as e:
        checks["services"]["vector_db"] = f"unhealthy: {str(e)}"
        checks["status"] = "degraded"
    
    # 返回适当的状态码
    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)
```

### 7.3 日志聚合

```yaml
# ELK Stack配置
version: '3.8'

services:
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: kibana:8.11.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  filebeat:
    image: elastic/filebeat:8.11.0
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml
      - /var/log:/var/log:ro
      - ./logs:/app/logs:ro
```

---

## 8. 部署方案

### 8.1 容器化部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ ./src/

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# 启动应用
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 8.2 Kubernetes部署

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: guanshan-api
  namespace: intelligence
spec:
  replicas: 3
  selector:
    matchLabels:
      app: guanshan-api
  template:
    metadata:
      labels:
        app: guanshan-api
    spec:
      containers:
      - name: api
        image: guanshan/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          value: redis://redis-service:6379
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: guanshan-api-service
  namespace: intelligence
spec:
  selector:
    app: guanshan-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: guanshan-api-hpa
  namespace: intelligence
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: guanshan-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 8.3 Docker Compose开发环境

```yaml
# docker-compose.yml
version: '3.8'

services:
  # API服务
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=mysql://user:pass@mariadb:3306/guanshan
      - MONGODB_URL=mongodb://mongodb:27017/intelligence
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - mariadb
      - mongodb
      - redis
      - rabbitmq
      - qdrant
    volumes:
      - ./src:/app/src
      - ./logs:/app/logs
    command: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

  # Celery Worker
  celery:
    build: .
    environment:
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - rabbitmq
      - redis
    command: celery -A src.tasks worker --loglevel=info

  # Celery Beat (定时任务)
  celery-beat:
    build: .
    environment:
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - rabbitmq
    command: celery -A src.tasks beat --loglevel=info

  # MariaDB
  mariadb:
    image: mariadb:10.11
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: guanshan
      MYSQL_USER: user
      MYSQL_PASSWORD: pass
    volumes:
      - mariadb_data:/var/lib/mysql
    ports:
      - "3306:3306"

  # MongoDB
  mongodb:
    image: mongo:7.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: admin123
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"

  # Redis
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

  # Qdrant向量数据库
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  # MinIO对象存储
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  # Flower (Celery监控)
  flower:
    image: mher/flower
    environment:
      - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672
      - FLOWER_PORT=5555
    ports:
      - "5555:5555"
    depends_on:
      - rabbitmq

volumes:
  mariadb_data:
  mongodb_data:
  redis_data:
  rabbitmq_data:
  qdrant_data:
  minio_data:

networks:
  default:
    name: guanshan_network
```

---

## 9. 测试策略

### 9.1 单元测试

```python
# tests/test_crawler.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_firecrawl_engine():
    """测试Firecrawl引擎"""
    engine = FirecrawlEngine()
    mock_response = Mock()
    mock_response.text = "<html><body>Test content</body></html>"
    
    engine.client.get = AsyncMock(return_value=mock_response)
    
    result = await engine.crawl("https://example.com")
    
    assert result.status == "success"
    assert "Test content" in result.content
    assert result.url == "https://example.com"

@pytest.mark.asyncio
async def test_text_processor():
    """测试文本处理器"""
    processor = TextProcessor()
    
    raw_text = "<p>This is a <b>test</b> document.</p>"
    result = await processor.process_pipeline(raw_text)
    
    assert result.text == "This is a test document."
    assert result.language == "en"
    assert len(result.segments) > 0
```

### 9.2 集成测试

```python
# tests/test_integration.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_crawl_to_report_pipeline(test_client: AsyncClient):
    """测试完整的数据处理流程"""
    
    # 1. 创建采集任务
    crawl_response = await test_client.post(
        "/api/v1/crawl/tasks",
        json={
            "urls": ["https://example.com"],
            "config": {"depth": 1}
        }
    )
    assert crawl_response.status_code == 201
    task_id = crawl_response.json()["task_id"]
    
    # 2. 等待任务完成
    await asyncio.sleep(5)
    
    # 3. 查询任务状态
    status_response = await test_client.get(
        f"/api/v1/tasks/{task_id}/status"
    )
    assert status_response.json()["status"] == "completed"
    
    # 4. 执行RAG查询
    query_response = await test_client.post(
        "/api/v1/intelligence/query",
        json={
            "query": "What is the main topic?",
            "filters": {"task_id": task_id}
        }
    )
    assert query_response.status_code == 200
    assert len(query_response.json()["results"]) > 0
    
    # 5. 生成报告
    report_response = await test_client.post(
        "/api/v1/reports/generate",
        json={
            "source_ids": [task_id],
            "template": "intelligence",
            "format": "pdf"
        }
    )
    assert report_response.status_code == 201
    assert report_response.json()["report_id"] is not None
```

### 9.3 性能测试

```python
# tests/test_performance.py
import asyncio
from locust import HttpUser, task, between

class IntelligenceSystemUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(1)
    def crawl_task(self):
        """测试采集任务创建"""
        self.client.post(
            "/api/v1/crawl/tasks",
            json={
                "urls": ["https://example.com"],
                "config": {"depth": 1}
            }
        )
    
    @task(3)
    def query_intelligence(self):
        """测试RAG查询"""
        self.client.post(
            "/api/v1/intelligence/query",
            json={
                "query": "test query",
                "top_k": 5
            }
        )
    
    @task(2)
    def health_check(self):
        """健康检查"""
        self.client.get("/health")
```

---

## 10. 成本优化

### 10.1 LLM API成本控制

```python
class LLMCostOptimizer:
    def __init__(self):
        self.cost_tracker = CostTracker()
        self.cache = LLMCache()
    
    async def optimize_llm_call(
        self,
        prompt: str,
        model: str = "gpt-3.5-turbo"
    ) -> str:
        # 1. 缓存检查
        cached_result = await self.cache.get(prompt)
        if cached_result:
            return cached_result
        
        # 2. 模型选择优化
        optimal_model = self.select_optimal_model(prompt)
        
        # 3. Prompt压缩
        compressed_prompt = self.compress_prompt(prompt)
        
        # 4. 执行调用
        result = await self.llm.generate(compressed_prompt, model=optimal_model)
        
        # 5. 记录成本
        cost = self.calculate_cost(len(compressed_prompt), len(result), optimal_model)
        await self.cost_tracker.record(cost, model=optimal_model)
        
        # 6. 缓存结果
        await self.cache.set(prompt, result, ttl=3600)
        
        return result
    
    def select_optimal_model(self, prompt: str) -> str:
        """根据任务复杂度选择模型"""
        complexity = self.assess_complexity(prompt)
        
        if complexity < 0.3:
            return "gpt-3.5-turbo"  # 简单任务用便宜模型
        elif complexity < 0.7:
            return "gpt-4-turbo"    # 中等任务
        else:
            return "gpt-4"          # 复杂任务用最强模型
```

### 10.2 存储优化

```python
# 数据生命周期管理
class DataLifecycleManager:
    async def manage_data_lifecycle(self):
        """数据生命周期管理"""
        
        # 1. 归档旧数据
        old_documents = await self.find_old_documents(days=30)
        await self.archive_to_cold_storage(old_documents)
        
        # 2. 压缩大文件
        large_files = await self.find_large_files(size_mb=10)
        await self.compress_files(large_files)
        
        # 3. 清理临时文件
        temp_files = await self.find_temp_files()
        await self.cleanup_temp_files(temp_files)
        
        # 4. 优化向量索引
        await self.vector_db.optimize_index()
        
        # 5. 数据库维护
        await self.mariadb.analyze_tables()
        await self.mongodb.compact_collections()
```

---

## 附录A: 项目结构

```
guanshan-intelligence/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI应用入口
│   ├── config.py                  # 配置管理
│   ├── api/                       # API路由
│   │   ├── v1/
│   │   │   ├── crawl.py
│   │   │   ├── intelligence.py
│   │   │   ├── reports.py
│   │   │   └── auth.py
│   │   └── websocket.py
│   ├── core/                      # 核心功能
│   │   ├── crawler/              # 爬虫模块
│   │   ├── processor/            # 文本处理
│   │   ├── translator/           # 翻译服务
│   │   ├── rag/                  # RAG pipeline
│   │   └── generator/            # 报告生成
│   ├── models/                    # 数据模型
│   ├── schemas/                   # Pydantic schemas
│   ├── services/                  # 业务服务
│   ├── tasks/                     # Celery任务
│   ├── utils/                     # 工具函数
│   └── middleware/                # 中间件
├── tests/                         # 测试
├── migrations/                    # 数据库迁移
├── scripts/                       # 脚本工具
├── docker/                        # Docker配置
├── k8s/                          # Kubernetes配置
├── docs/                         # 文档
├── requirements.txt              # Python依赖
├── docker-compose.yml            # 开发环境配置
├── Dockerfile                    # 容器构建
└── README.md                     # 项目说明
```

## 附录B: 技术选型理由

| 技术 | 选择理由 |
|------|---------|
| **FastAPI** | 异步支持好，性能高，自动API文档，类型安全 |
| **Firecrawl** | 强大的爬虫功能，支持JS渲染，易于集成 |
| **LangChain** | 统一的LLM接口，丰富的工具链，RAG支持完善 |
| **Qdrant** | 专门的向量数据库，性能优秀，支持过滤和元数据 |
| **MongoDB** | 灵活的文档存储，适合非结构化数据 |
| **MariaDB** | 成熟稳定，事务支持，适合结构化数据 |
| **RabbitMQ** | 消息可靠性高，支持优先级队列，运维成熟 |
| **Celery** | Python生态最成熟的任务队列，功能丰富 |
| **Redis** | 高性能缓存，支持多种数据结构 |
| **MinIO** | S3兼容，私有化部署，成本可控 |

## 附录C: 常用命令

```bash
# 开发环境启动
docker-compose up -d

# 查看日志
docker-compose logs -f api

# 运行测试
pytest tests/ -v --cov=src

# 数据库迁移
alembic upgrade head

# 启动Celery Worker
celery -A src.tasks worker --loglevel=info

# 启动Flower监控
celery -A src.tasks flower

# 生产部署
kubectl apply -f k8s/

# 性能测试
locust -f tests/test_performance.py --host=http://localhost:8000
```

---

## 更新日志

- 2025-01-10: v1.0.0 - 初始架构设计
- 2025-01-10: v1.0.0 - 添加RAG Pipeline设计
- 2025-01-10: v1.0.0 - 完善安全和监控方案

---

## 联系方式

- **项目负责人**: tech@guanshan.ai
- **技术支持**: support@guanshan.ai
- **GitHub**: https://github.com/guanshan/intelligence-system
- **文档**: https://docs.guanshan.ai