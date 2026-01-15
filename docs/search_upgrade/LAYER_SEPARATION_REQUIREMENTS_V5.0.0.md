# 搜索系统层分离架构重构需求分析文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v5.0.0 |
| 创建日期 | 2025-01-14 |
| 当前版本 | v4.6.0 |
| 目标版本 | v5.0.0 |
| 架构师 | Claude (Architect Persona) |

---

## 1. 执行摘要

### 1.1 重构目标

将当前紧密耦合的搜索处理流程拆分为两个独立的、可并行执行的层：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户请求                                        │
│                    /api/v1/chat/sync?wait=false                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │            并行执行               │
                    ▼                                   ▼
┌───────────────────────────────────┐  ┌───────────────────────────────────────┐
│     搜索引擎层 (Layer 3)          │  │        AI 处理层 (Layer 4/5)          │
│                                   │  │                                       │
│  LangGraph 工作流 (6节点)         │  │  远程 AI 服务 (192.168.0.5:8035)     │
│  ├─ QueryAnalyzer                 │  │  ├─ SSE 流式响应                      │
│  ├─ SourceDiscovery               │  │  ├─ 对话历史管理                      │
│  ├─ LayerSearch (5层)             │  │  └─ 前端数据推送                      │
│  ├─ ResultFilter                  │  │                                       │
│  ├─ QualityGate                   │  │  数据来源:                            │
│  └─ OutputNode                    │  │  ├─ langgraph_search_results         │
│                                   │  │  └─ chat_history                     │
│  NL Search 回退机制               │  │                                       │
│                                   │  │                                       │
│  输出: langgraph_search_results   │  │  输出: 前端 SSE 流                    │
└───────────────────────────────────┘  └───────────────────────────────────────┘
                    │                                   │
                    ▼                                   ▼
            ┌───────────────┐                   ┌───────────────────┐
            │ MongoDB 集合   │                   │   前端 WebSocket   │
            │ langgraph_    │                   │   或 SSE 响应      │
            │ search_results│                   │                   │
            └───────────────┘                   └───────────────────┘
```

### 1.2 核心价值

| 价值维度 | 描述 |
|----------|------|
| **解耦** | 搜索与 AI 处理独立运行，互不阻塞 |
| **可扩展** | 各层可独立扩容、优化、替换 |
| **容错** | 搜索失败不影响 AI 响应；AI 失败不影响搜索结果存储 |
| **可测试** | 各层可独立测试，降低测试复杂度 |
| **性能** | 并行执行减少总响应时间 |

---

## 2. 当前架构分析

### 2.1 现有代码结构

```
src/
├── api/v1/endpoints/
│   └── chat.py                    # 主入口，耦合了搜索和AI处理
├── services/
│   ├── chat_task_service.py       # 任务编排，耦合了搜索和AI处理
│   ├── search_engine_adapter.py   # 搜索适配器（LangGraph/NL Search）
│   └── langgraph_search/
│       ├── service.py             # LangGraph 搜索服务
│       ├── config.py              # 配置
│       └── nodes/                 # 6个工作流节点
│           ├── query_analyzer.py
│           ├── source_discovery.py
│           ├── layer_search.py
│           ├── result_filter.py
│           ├── quality_gate.py
│           └── output.py
└── infrastructure/
    └── persistence/repositories/mongo/
        └── langgraph_result_repository.py
```

### 2.2 当前数据流（耦合状态）

```
chat_sync_endpoint() @ chat.py:174-710
│
├─ 1. 创建任务 (ChatTaskRepository)
│
├─ 2. 搜索阶段 (紧密耦合)
│   ├─ SearchEngineAdapter.search()
│   │   ├─ LangGraphSearchService.execute_search()
│   │   │   ├─ QueryAnalyzer → SourceDiscovery → LayerSearch
│   │   │   └─ ResultFilter → QualityGate → OutputNode
│   │   └─ 回退: NL Search
│   │
│   └─ 保存到 langgraph_search_results
│
├─ 3. AI 处理阶段 (紧密耦合，依赖搜索结果)
│   ├─ 构建 AI 请求数据
│   │   ├─ search_results (来自第2步)
│   │   └─ conversation_history
│   │
│   ├─ httpx.stream("POST", REMOTE_AI_SERVICE_URL)
│   │   └─ 192.168.0.5:8035/chat
│   │
│   └─ 解析 SSE 流
│       ├─ event_type: "chunk" → answer_chunks
│       ├─ event_type: "source" → ai_sources
│       └─ event_type: "stream_end" → 完成
│
└─ 4. 保存聊天历史
```

### 2.3 关键问题诊断

#### 2.3.1 耦合点分析

| 文件 | 位置 | 耦合描述 | 影响 |
|------|------|----------|------|
| `chat.py` | L570-710 | 搜索完成后立即调用 AI 服务 | 串行执行，无法并行 |
| `chat.py` | L595 | AI 请求依赖 search_results | 数据流硬编码 |
| `chat_task_service.py` | L180-280 | execute_task() 混合搜索和AI | 职责不清 |
| `search_engine_adapter.py` | L320 | 返回结果直接用于 AI 输入 | 数据模型耦合 |

#### 2.3.2 当前 wait=false 行为

```python
# chat.py L474-490 (当前实现)
if not wait:
    # 后台任务执行完整流程（搜索 + AI）
    background_tasks.add_task(
        ChatTaskService.execute_task,  # 仍然是串行执行
        task_id=task_id,
        ...
    )
    return {"task_id": task_id, "status": "processing"}
```

**问题**: `wait=false` 仅将整个流程移至后台，但搜索和 AI 处理仍然串行。

---

## 3. 目标架构设计

### 3.1 层职责定义

#### 搜索引擎层 (Search Engine Layer - Layer 3)

```yaml
职责:
  - 接收用户查询
  - 执行 LangGraph 6 节点工作流
  - 回退到 NL Search (如需)
  - 将结果存储到 langgraph_search_results 集合
  - 发送"搜索完成"事件通知

输入:
  - user_id: str
  - query: str
  - search_options: SearchOptions

输出:
  - task_id: str  # 用于关联 AI 处理层
  - status: "completed" | "failed"
  - result_count: int
  - 存储位置: langgraph_search_results 集合

独立性:
  - 不依赖 AI 处理层
  - 不关心结果如何被使用
  - 完成即保存，流程结束
```

#### AI 处理层 (AI Processing Layer - Layer 4/5)

```yaml
职责:
  - 监听/轮询搜索完成事件
  - 从 langgraph_search_results 读取搜索结果
  - 获取对话历史 (chat_history)
  - 调用远程 AI 服务 (192.168.0.5:8035/chat)
  - 解析 SSE 流
  - 将 AI 响应推送给前端
  - 保存聊天记录

输入:
  - task_id: str  # 关联搜索结果
  - user_id: str
  - query: str
  - skip_summary: bool  # 是否跳过 AI 总结

输出:
  - SSE 流 (event_type: chunk | source | stream_end)
  - 保存到 chat_history 集合

独立性:
  - 不执行搜索
  - 从数据库读取搜索结果
  - 可独立于搜索层运行
```

### 3.2 新数据流设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    /api/v1/chat/sync?wait=false                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────┐
                    │      ChatOrchestrator           │
                    │  (新增: 协调器组件)             │
                    └─────────────────┬───────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
            ▼                                                   ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│   SearchEngineLayer               │       │   AIProcessingLayer               │
│                                   │       │                                   │
│   async def execute(              │       │   async def execute(              │
│       task_id: str,               │       │       task_id: str,               │
│       query: str,                 │       │       query: str,                 │
│       user_id: str                │       │       user_id: str                │
│   ) -> SearchResult:              │       │   ) -> AsyncGenerator[SSEEvent]:  │
│                                   │       │                                   │
│   1. LangGraph 工作流             │       │   1. 等待搜索完成 (或跳过)        │
│   2. 保存到 MongoDB               │       │   2. 读取 langgraph_search_results│
│   3. 发送完成事件                 │       │   3. 获取对话历史                 │
│                                   │       │   4. 调用远程 AI 服务             │
│                                   │       │   5. 解析 SSE 流                  │
│                                   │       │   6. 推送到前端                   │
└───────────────────────────────────┘       └───────────────────────────────────┘
            │                                               │
            ▼                                               │
    ┌───────────────────┐                                   │
    │ langgraph_        │◄──────────────────────────────────┘
    │ search_results    │      (读取搜索结果)
    └───────────────────┘
```

### 3.3 并行执行模式

#### 模式 1: 全并行 (搜索与 AI 同时启动)

```
时间线:
t0 ──────┬─────────────────────────────────────────────────────► t_end
         │
         ├─ [搜索引擎层] ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ → 保存结果
         │
         └─ [AI处理层]   等待... ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ → SSE 响应
                         ↑
                         读取搜索结果 (polling/event)
```

**实现**: AI 层启动后轮询 `langgraph_search_results`，每 500ms 检查一次搜索是否完成。

#### 模式 2: 事件驱动 (推荐)

```
时间线:
t0 ──────┬─────────────────────────────────────────────────────► t_end
         │
         ├─ [搜索引擎层] ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ → 保存 → 发送事件
         │                                              │
         └─ [AI处理层]   等待事件 ◀─────────────────────┘
                         ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ → SSE 响应
```

**实现**: 使用 Redis Pub/Sub 或内存事件总线通知 AI 层。

---

## 4. 详细设计

### 4.1 新增组件

#### 4.1.1 ChatOrchestrator (协调器)

```python
# src/services/chat_orchestrator.py

class ChatOrchestrator:
    """聊天协调器 - 协调搜索层和 AI 处理层的执行"""

    def __init__(
        self,
        search_engine_layer: SearchEngineLayer,
        ai_processing_layer: AIProcessingLayer,
        event_bus: EventBus,  # 可选: 用于事件驱动模式
    ):
        self.search_layer = search_engine_layer
        self.ai_layer = ai_processing_layer
        self.event_bus = event_bus

    async def execute_parallel(
        self,
        task_id: str,
        query: str,
        user_id: str,
        wait: bool = False,
        skip_summary: bool = False,
    ) -> Dict[str, Any]:
        """并行执行搜索和 AI 处理

        Args:
            task_id: 任务ID
            query: 用户查询
            user_id: 用户ID
            wait: 是否同步等待
            skip_summary: 是否跳过 AI 总结

        Returns:
            执行结果或任务状态
        """
        if wait:
            # 同步模式: 按顺序执行
            return await self._execute_sync(task_id, query, user_id, skip_summary)
        else:
            # 异步模式: 并行执行
            return await self._execute_async(task_id, query, user_id, skip_summary)

    async def _execute_async(
        self,
        task_id: str,
        query: str,
        user_id: str,
        skip_summary: bool,
    ) -> Dict[str, Any]:
        """异步并行执行"""
        # 1. 创建并行任务
        search_task = asyncio.create_task(
            self.search_layer.execute(task_id, query, user_id)
        )

        if not skip_summary:
            ai_task = asyncio.create_task(
                self.ai_layer.execute(task_id, query, user_id)
            )

        # 2. 立即返回任务状态
        return {
            "task_id": task_id,
            "status": "processing",
            "layers": {
                "search": "running",
                "ai": "waiting" if not skip_summary else "skipped",
            }
        }
```

#### 4.1.2 SearchEngineLayer (搜索引擎层)

```python
# src/services/layers/search_engine_layer.py

class SearchEngineLayer:
    """搜索引擎层 - 职责单一: 执行搜索并存储结果"""

    def __init__(
        self,
        search_adapter: SearchEngineAdapter,
        result_repository: LangGraphResultRepository,
        event_bus: Optional[EventBus] = None,
    ):
        self.search_adapter = search_adapter
        self.result_repository = result_repository
        self.event_bus = event_bus

    async def execute(
        self,
        task_id: str,
        query: str,
        user_id: str,
        options: Optional[SearchOptions] = None,
    ) -> SearchLayerResult:
        """执行搜索并存储结果

        职责:
        1. 调用 LangGraph 或 NL Search
        2. 保存结果到 langgraph_search_results
        3. 发送搜索完成事件

        不做:
        - 不调用 AI 服务
        - 不处理对话历史
        - 不推送前端
        """
        try:
            # 1. 执行搜索
            search_result = await self.search_adapter.search(
                query=query,
                user_id=user_id,
                options=options or SearchOptions(),
            )

            # 2. 保存到数据库
            await self.result_repository.save(
                task_id=task_id,
                user_id=user_id,
                query=query,
                results=search_result.results,
                statistics=search_result.statistics,
            )

            # 3. 发送完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    SearchCompletedEvent(
                        task_id=task_id,
                        user_id=user_id,
                        result_count=len(search_result.results),
                    )
                )

            return SearchLayerResult(
                task_id=task_id,
                status="completed",
                result_count=len(search_result.results),
            )

        except Exception as e:
            logger.error(f"Search layer failed: {e}")
            return SearchLayerResult(
                task_id=task_id,
                status="failed",
                error=str(e),
            )
```

#### 4.1.3 AIProcessingLayer (AI 处理层)

```python
# src/services/layers/ai_processing_layer.py

class AIProcessingLayer:
    """AI 处理层 - 职责单一: 调用 AI 服务并推送响应"""

    REMOTE_AI_SERVICE_URL = "http://192.168.0.5:8035/chat"
    POLL_INTERVAL = 0.5  # 500ms
    MAX_WAIT_TIME = 300  # 5分钟

    def __init__(
        self,
        result_repository: LangGraphResultRepository,
        history_repository: ChatHistoryRepository,
        event_bus: Optional[EventBus] = None,
    ):
        self.result_repository = result_repository
        self.history_repository = history_repository
        self.event_bus = event_bus

    async def execute(
        self,
        task_id: str,
        query: str,
        user_id: str,
    ) -> AsyncGenerator[SSEEvent, None]:
        """执行 AI 处理并返回 SSE 流

        职责:
        1. 等待/获取搜索结果
        2. 获取对话历史
        3. 调用远程 AI 服务
        4. 解析并转发 SSE 流
        5. 保存聊天记录

        不做:
        - 不执行搜索
        - 不管理搜索工作流
        """
        # 1. 等待搜索完成并获取结果
        search_results = await self._wait_for_search_results(task_id, user_id)

        if not search_results:
            yield SSEEvent(
                event_type="error",
                data={"message": "搜索结果未找到"},
            )
            return

        # 2. 获取对话历史
        conversation_history = await self.history_repository.get_recent(
            user_id=user_id,
            limit=10,
        )

        # 3. 构建 AI 请求
        ai_request = {
            "query": query,
            "search_results": search_results,
            "history": conversation_history,
            "user_id": user_id,
        }

        # 4. 调用 AI 服务并转发 SSE
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                self.REMOTE_AI_SERVICE_URL,
                json=ai_request,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event_data = json.loads(line[6:])
                        yield SSEEvent.from_dict(event_data)

        # 5. 保存聊天记录
        await self._save_chat_history(task_id, user_id, query)

    async def _wait_for_search_results(
        self,
        task_id: str,
        user_id: str,
    ) -> Optional[List[Dict]]:
        """等待搜索完成并返回结果"""
        start_time = time.time()

        while (time.time() - start_time) < self.MAX_WAIT_TIME:
            # 尝试获取搜索结果
            result = await self.result_repository.find_by_task_id(task_id)

            if result and result.get("status") == "completed":
                return result.get("results", [])

            if result and result.get("status") == "failed":
                return None

            # 等待后重试
            await asyncio.sleep(self.POLL_INTERVAL)

        return None  # 超时
```

### 4.2 数据模型更新

#### 4.2.1 langgraph_search_results 集合 (已存在，需增强)

```python
# 新增字段用于层分离
{
    "_id": ObjectId,
    "task_id": str,           # 必需: 关联任务
    "user_id": str,
    "query": str,
    "status": str,            # 新增: "processing" | "completed" | "failed"
    "created_at": datetime,
    "completed_at": datetime, # 新增: 搜索完成时间

    # 搜索结果
    "results": List[Dict],
    "statistics": Dict,

    # 层分离标识
    "layer_type": "search_engine",  # 新增: 标识这是搜索层输出
    "processed_by_ai": bool,        # 新增: AI 层是否已处理
}
```

### 4.3 API 端点更新

#### 4.3.1 /api/v1/chat/sync 修改

```python
@router.post("/chat/sync")
async def chat_sync_endpoint(
    request: ChatRequest,
    wait: bool = Query(True),
    skip_summary: bool = Query(False),
    background_tasks: BackgroundTasks,
):
    """统一聊天端点 - 支持层分离

    新行为:
    - wait=true: 顺序执行搜索和 AI，等待完成
    - wait=false: 并行启动搜索和 AI，立即返回 task_id
    - skip_summary=true: 仅执行搜索，跳过 AI 处理
    """
    orchestrator = get_chat_orchestrator()

    return await orchestrator.execute_parallel(
        task_id=generate_task_id(),
        query=request.query,
        user_id=request.user_id,
        wait=wait,
        skip_summary=skip_summary,
    )
```

#### 4.3.2 新增 /api/v1/chat/search-only 端点 (可选)

```python
@router.post("/chat/search-only")
async def search_only_endpoint(
    request: SearchRequest,
):
    """仅执行搜索，不调用 AI

    用途: 纯搜索场景，或前端自行处理 AI
    """
    search_layer = get_search_engine_layer()

    return await search_layer.execute(
        task_id=generate_task_id(),
        query=request.query,
        user_id=request.user_id,
    )
```

---

## 5. 实施计划

### 5.1 阶段划分

| 阶段 | 名称 | 预计工期 | 依赖 | 风险 |
|------|------|----------|------|------|
| Phase 1 | 创建层抽象 | 1-2 天 | 无 | 低 |
| Phase 2 | 搜索引擎层重构 | 2-3 天 | Phase 1 | 中 |
| Phase 3 | AI 处理层重构 | 2-3 天 | Phase 1 | 中 |
| Phase 4 | 协调器实现 | 1-2 天 | Phase 2, 3 | 低 |
| Phase 5 | API 端点更新 | 1 天 | Phase 4 | 低 |
| Phase 6 | 测试与验证 | 2-3 天 | Phase 5 | 低 |

### 5.2 Phase 1: 创建层抽象

**目标**: 定义层接口和基础组件

**新增文件**:
```
src/services/layers/
├── __init__.py
├── base.py              # 基础层接口
├── search_engine_layer.py
└── ai_processing_layer.py

src/services/
└── chat_orchestrator.py  # 协调器

src/core/domain/events/
├── __init__.py
└── search_events.py      # 搜索完成事件
```

**关键代码**:
```python
# src/services/layers/base.py
from abc import ABC, abstractmethod

class BaseLayer(ABC):
    """层基类"""

    @abstractmethod
    async def execute(self, *args, **kwargs):
        """执行层逻辑"""
        pass

    @property
    @abstractmethod
    def layer_name(self) -> str:
        """层名称"""
        pass

# src/core/domain/events/search_events.py
@dataclass
class SearchCompletedEvent:
    """搜索完成事件"""
    task_id: str
    user_id: str
    result_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 5.3 Phase 2: 搜索引擎层重构

**目标**: 将搜索逻辑封装到 SearchEngineLayer

**修改文件**:
```
src/services/search_engine_adapter.py  # 移除 AI 处理相关代码
src/services/langgraph_search/service.py  # 添加状态更新
```

**验收标准**:
- [ ] SearchEngineLayer 可独立执行搜索
- [ ] 结果正确保存到 langgraph_search_results
- [ ] 搜索完成后发送事件
- [ ] 不依赖 AI 处理层

### 5.4 Phase 3: AI 处理层重构

**目标**: 将 AI 处理逻辑封装到 AIProcessingLayer

**修改文件**:
```
src/api/v1/endpoints/chat.py  # 移除 AI 处理代码到新层
```

**验收标准**:
- [ ] AIProcessingLayer 可独立执行 AI 处理
- [ ] 正确轮询/等待搜索结果
- [ ] 正确调用远程 AI 服务
- [ ] 正确解析和转发 SSE 流
- [ ] 不执行搜索

### 5.5 Phase 4: 协调器实现

**目标**: 实现 ChatOrchestrator 协调两层执行

**验收标准**:
- [ ] wait=true 时顺序执行
- [ ] wait=false 时并行执行
- [ ] skip_summary=true 时跳过 AI 层
- [ ] 正确处理各层错误

### 5.6 Phase 5: API 端点更新

**目标**: 更新 /api/v1/chat/sync 使用新架构

**验收标准**:
- [ ] 现有 API 行为保持兼容
- [ ] 新参数正常工作
- [ ] 错误处理正确

---

## 6. 验收标准

### 6.1 功能验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| FV-1 | 层独立性 | 搜索层可独立运行，无 AI 依赖 |
| FV-2 | 层独立性 | AI 层可从数据库读取搜索结果 |
| FV-3 | 并行执行 | wait=false 时两层并行启动 |
| FV-4 | 数据流 | 搜索结果正确存储和读取 |
| FV-5 | SSE 流 | AI SSE 流正确解析和转发 |
| FV-6 | 向后兼容 | 现有 API 调用者无感知 |

### 6.2 性能验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| PV-1 | 并行加速 | wait=false 时总时间 < 串行时间 80% |
| PV-2 | 搜索层延迟 | 增加 < 100ms (存储开销) |
| PV-3 | AI 层延迟 | 轮询开销 < 1s |

### 6.3 质量验收

| 编号 | 验收项 | 标准 |
|------|--------|------|
| QV-1 | 代码覆盖率 | 新增代码覆盖率 ≥ 80% |
| QV-2 | 单元测试 | 各层可独立测试 |
| QV-3 | 集成测试 | 协调器测试通过 |

---

## 7. 风险与对策

| 风险 | 影响 | 概率 | 对策 |
|------|------|------|------|
| 并行执行时序问题 | 高 | 中 | 使用事件驱动或轮询机制确保同步 |
| 数据库读写竞争 | 中 | 低 | 使用任务状态字段确保读取正确数据 |
| 向后兼容性问题 | 高 | 低 | 保持 API 签名不变，渐进式迁移 |
| 事件总线可靠性 | 中 | 中 | 回退到轮询机制作为备选 |

---

## 8. 附录

### 8.1 相关文件索引

| 文件 | 说明 |
|------|------|
| `src/api/v1/endpoints/chat.py` | 主 API 端点 (需重构) |
| `src/services/chat_task_service.py` | 任务服务 (需重构) |
| `src/services/search_engine_adapter.py` | 搜索适配器 (需修改) |
| `src/services/langgraph_search/service.py` | LangGraph 服务 (需修改) |
| `docs/search_upgrade/INTELLIGENT_SEARCH_FLOW_V4.6.0.md` | 现有架构文档 |

### 8.2 术语表

| 术语 | 定义 |
|------|------|
| 搜索引擎层 | 负责执行搜索并存储结果的组件 |
| AI 处理层 | 负责调用 AI 服务并推送响应的组件 |
| 协调器 | 协调两层执行的中央组件 |
| SSE | Server-Sent Events，服务器推送事件 |
| 事件总线 | 层间通信的消息系统 |

### 8.3 版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| v5.0.0 | 2025-01-14 | Claude (Architect) | 层分离架构重构需求文档 |
