# 智能搜索流程图 v4.6.0

## 完整流程 Mermaid 图

```mermaid
flowchart TD
    %% ==================== 前端层 ====================
    subgraph Frontend["前端层 (Next.js)"]
        User["用户输入"]
        Page["qa-chat/page.tsx"]
        APIClient["lib/api-client.ts"]

        User -->|"输入问题"| Page
        Page -->|"chatAPI.chat()"| APIClient
    end

    %% ==================== 后端 API 层 ====================
    subgraph BackendAPI["后端 API 层 (FastAPI)"]
        ChatEndpoint["/api/v1/chat/sync"]
        ChatTaskService["chat_task_service.py"]
        SearchAdapter["search_engine_adapter.py"]
    end

    %% ==================== 搜索引擎层 ====================
    subgraph SearchEngine["搜索引擎层"]
        NLSearch["nl_search_service<br/>(NL Search)"]
        LangGraph["langgraph_search_service<br/>(LangGraph v4.5+)"]

        subgraph LangGraphFlow["LangGraph 工作流"]
            QueryAnalyzer["QueryAnalyzer<br/>(查询分析)"]
            SourceDiscovery["SourceDiscovery<br/>(源发现)"]
            LayerSearch["LayerSearch<br/>(分层搜索)"]
            ResultFilter["ResultFilter<br/>(结果过滤)"]
            QualityGate["QualityGate<br/>(质量门控)"]
            Aggregator["Aggregator<br/>(结果聚合)"]
        end
    end

    %% ==================== AI 处理层 ====================
    subgraph AIProcessing["AI 处理层"]
        RemoteAIService["远程 AI 服务<br/>(192.168.0.5:8035)"]
        SSE["SSE 流式响应"]
    end

    %% ==================== 数据层 ====================
    subgraph DataLayer["数据层 (MongoDB)"]
        FileUploads["file_uploads<br/>(用户上传)"]
        NewsResults["news_results<br/>(搜索结果)"]
        LangGraphResults["langgraph_search_results<br/>(库外信息)"]
        ChatConversations["chat_conversations<br/>(对话记录)"]
        SearchHistory["search_history<br/>(搜索历史)"]
    end

    %% ==================== 流程连接 ====================

    %% 前端 → 后端
    APIClient -->|"POST /chat/sync<br/>(question, conversation_id)"| ChatEndpoint

    %% 后端内部流程
    ChatEndpoint -->|"创建任务记录"| ChatTaskService
    ChatTaskService -->|"search_engine_adapter.search()"| SearchAdapter

    %% 搜索引擎路由
    SearchAdapter -->|"SEARCH_ENGINE=langgraph"| LangGraph
    SearchAdapter -.->|"回退<br/>SEARCH_ENGINE=nl"| NLSearch

    %% LangGraph 工作流
    LangGraph --> QueryAnalyzer
    QueryAnalyzer --> SourceDiscovery
    SourceDiscovery --> LayerSearch
    LayerSearch --> ResultFilter
    ResultFilter --> QualityGate
    QualityGate --> Aggregator

    %% 搜索结果存储
    Aggregator -->|"存储"| LangGraphResults
    NLSearch -->|"存储"| NewsResults

    %% 返回搜索结果
    SearchAdapter -->|"返回 log_id + results"| ChatTaskService

    %% AI 处理 (可选 skip_summary)
    ChatTaskService -->|"skip_summary=false"| RemoteAIService
    RemoteAIService -->|"SSE 流"| SSE

    %% 数据增强
    ChatTaskService -->|"查询完整内容"| FileUploads
    ChatTaskService -->|"查询完整内容"| NewsResults

    %% 保存历史
    ChatTaskService -->|"保存"| ChatConversations
    ChatTaskService -->|"保存"| SearchHistory

    %% 响应返回
    ChatEndpoint -->|"ChatSyncResponse<br/>(task_id=log_id)"| APIClient

    %% 前端保存关联
    APIClient -->|"processChatResponse"| Page
    Page -->|"保存 langgraphTaskId"| PageState["页面状态<br/>(conversation.langgraphTaskId)"]

    %% 库外信息查询 (使用保存的 task_id)
    PageState -.->|"langgraphAPI.getResults(task_id)"| LangGraphResults

    %% ==================== 样式定义 ====================
    classDef frontendStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef backendStyle fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef searchStyle fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef aiStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef dataStyle fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef langgraphStyle fill:#e0f2f1,stroke:#004d40,stroke-width:2px

    class User,Page,APIClient frontendStyle
    class ChatEndpoint,ChatTaskService,SearchAdapter backendStyle
    class NLSearch,LangGraph searchStyle
    class QueryAnalyzer,SourceDiscovery,LayerSearch,ResultFilter,QualityGate,Aggregator langgraphStyle
    class RemoteAIService,SSE aiStyle
    class FileUploads,NewsResults,LangGraphResults,ChatConversations,SearchHistory,PageState dataStyle
```

## 数据流关键点

### 1. task_id 传递链路 (v4.6.0 统一)

```
LangGraph thread_id (log_id)
    ↓
search_engine_adapter.search() 返回 log_id
    ↓
ChatSyncResponse.task_id = log_id
    ↓
前端 processChatResponse() 保存到 conversation.langgraphTaskId
    ↓
用于查询 langgraphAPI.getResults({ task_id })
```

### 2. 三种 ID 系统对比

| ID 类型 | 格式 | 用途 | 示例 |
|--------|------|------|------|
| conversation_id | MongoDB ObjectId | 对话会话标识 | 67a3f2e9b1d4c8e9f0a1b2c3 |
| task_id (v4.6.0) | LangGraph thread_id | LangGraph 工作流标识，用于查询库外信息 | 248728141926559744 |
| mongo_id | MongoDB ObjectId | 数据库文档 ID | 69312ed5cf789ae4312d6036 |

### 3. API 请求/响应格式

#### 请求: POST /api/v1/chat/sync
```json
{
  "question": "西藏最新新闻",
  "conversation_id": "248728141926559744",
  "search_mode": "single"
}
```

#### 响应: ChatSyncResponse
```json
{
  "question": "西藏最新新闻",
  "answer": "为您找到 5 条相关信息...",
  "sources": [...],
  "sources_count": 5,
  "answer_length": 1234,
  "status": "success_ai",
  "task_id": "248728141926559744"  // LangGraph thread_id
}
```

### 4. 库外信息查询

#### 请求: GET /api/v1/langgraph/results
```json
{
  "task_id": "248728141926559744",  // 使用保存的 langgraphTaskId
  "page": 1,
  "page_size": 100
}
```

## 版本历史

- **v4.6.0** (2025-01-14): 统一 task_id 存储 LangGraph thread_id
- **v4.5.0** (2025-01-10): 集成 LangGraph 搜索引擎
- **v4.0.0** (2024-12-20): 引入 SearchEngineAdapter
- **v3.0.0** (2024-11-15): 统一任务化模型
