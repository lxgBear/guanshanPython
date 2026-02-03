# AI Search 页面接口迁移设计文档

> **日期**: 2026-02-03
> **状态**: 设计完成，待实施
> **相关项目**: guanshanCMS (前端) + guanshanPython (后端)

## 1. 背景

原有智能问答功能 (`qa-chat`) 过于复杂，已迁移到新的 `ai-search` 页面。新页面目前使用 Mock 数据，需要对接真实后端 API。

### 1.1 前端路径
- **新页面**: `/app/dashboard/info-generation/collect/ai-search/`
- **旧页面**: `/app/dashboard/info-generation/collect/qa-chat/` (已弃用)

### 1.2 设计目标
1. 将 ai-search 页面从 Mock 模式切换到真实 API
2. 使用 Chat API + Chat V2 作为后端接口
3. 标记可废弃的数据库集合
4. 保持页面功能简洁（相比 qa-chat 精简功能）

---

## 2. 接口映射方案

### 2.1 API 选择决策

| 功能域 | 选择的 API | 原因 |
|--------|-----------|------|
| 历史记录管理 | `chatAPI` (`/chat/*`) | 已有成熟的对话管理接口 |
| 搜索执行 | Chat V2 (`/chat/v2/sync`) | 支持要素确认流程，层级分离架构 |
| 搜索结果 | `langgraphAPI` | 结果存储在 langgraph_search_results |

### 2.2 详细接口映射

#### 历史记录（保持不变）
```typescript
// 获取历史记录列表
chatAPI.getConversations({ limit: 50 })
// → GET /chat/conversations?limit=50

// 获取单个对话详情
chatAPI.getConversation(conversationId)
// → GET /chat/conversations/{conversation_id}
```

#### 搜索提交（需修改）
```typescript
// 当前 Mock 实现
const response = await nlSearchAPI.createSearch(request)

// 改为 Chat V2
const response = await chatAPI.chat(query, {
  conversationId,
  requireConfirmation: true  // 启用要素确认流程
})
// → POST /chat/v2/sync?require_confirmation=true
```

#### 要素确认执行搜索（新增）
```typescript
// 确认要素并执行搜索
const response = await chatAPI.confirmElements(taskId, elements, wait)
// → POST /chat/v2/tasks/{task_id}/confirm?wait=false
```

#### 加载搜索结果（需修改）
```typescript
// 当前 Mock 实现
const response = await nlSearchAPI.getResults(logId, offset, limit)

// 改为 LangGraph API
const response = await langgraphAPI.getResults({
  conversation_id: conversationId,
  page: 1,
  page_size: 100,
  include_content: true
})
// → GET /langgraph/results?conversation_id=xxx
```

#### 任务状态轮询（需修改）
```typescript
// 当前实现（如果使用）
const log = await nlSearchAPI.getLog(logId)

// 改为 Chat API 轮询
const result = await chatAPI.pollTask(taskId, {
  interval: 2000,
  maxAttempts: 60,
  onProgress: (task) => { /* 更新进度 */ }
})
```

---

## 3. 数据流程设计

### 3.1 搜索流程（带要素确认）

```
用户输入查询
    │
    ▼
POST /chat/v2/sync?require_confirmation=true
    │
    ▼
返回 { task_id, status: "awaiting_confirmation", extracted_elements }
    │
    ▼
前端显示 ConfirmationPanel，用户可修改要素
    │
    ▼
POST /chat/v2/tasks/{task_id}/confirm?wait=false
    │
    ▼
返回 { task_id, status: "processing" }
    │
    ▼
轮询任务状态 或 用户稍后查看结果
    │
    ▼
GET /langgraph/results?conversation_id=xxx
    │
    ▼
显示搜索结果
```

### 3.2 历史记录加载流程

```
页面加载
    │
    ▼
GET /chat/conversations?limit=50
    │
    ▼
用户选择历史记录
    │
    ▼
GET /langgraph/results?conversation_id={selected_id}
    │
    ▼
显示该记录的搜索结果
```

---

## 4. 前端代码修改清单

### 4.1 主要修改文件

| 文件 | 修改内容 |
|------|----------|
| `hooks/useSearchWorkspace.ts` | 核心逻辑修改，切换到真实 API |
| `@/lib/api-client.ts` | 添加 Chat V2 专用方法（如缺失） |
| `types/search.ts` | 类型定义对齐后端响应 |

### 4.2 useSearchWorkspace.ts 修改详情

#### 4.2.1 禁用 Mock 模式
```typescript
// 修改前
const USE_MOCK = true

// 修改后
const USE_MOCK = false
```

#### 4.2.2 修改 handleSubmitSearch
```typescript
// 修改前
const response = await nlSearchAPI.createSearch(request)

// 修改后
const chatOptions = { conversationId: currentConversationId }
const response = await chatAPI.chat(currentQuery, chatOptions)

if (chatAPI.isElementsConfirmationResponse(response)) {
  // 显示要素确认面板
  setConfirmationPanel({
    isOpen: true,
    elements: response.extracted_elements,
  })
  setCurrentTask({
    id: response.task_id,
    status: "awaiting_confirmation"
  })
}
```

#### 4.2.3 修改 handleConfirmSearch
```typescript
// 修改前 (Mock)
// 模拟进度...
setResults(mockSearchResults)

// 修改后
const response = await chatAPI.confirmElements(
  currentTask.id!,
  elements,
  false  // wait=false，异步执行
)

// 启动轮询或提示用户稍后查看
toast.success('搜索任务已启动')
```

#### 4.2.4 修改 loadResults / handleSelectHistory
```typescript
// 修改前
const response = await nlSearchAPI.getResults(logId, 0, 100)

// 修改后
const response = await langgraphAPI.getResults({
  conversation_id: historyId,
  page: 1,
  page_size: 100,
  include_content: true,
  sort_by: 'final_score',
  sort_order: 'desc'
})

const searchResults = (response.data || []).map((item, index) => ({
  id: item.id,
  title: item.title,
  summary: item.snippet || '',
  source: item.source || '未知来源',
  sourceType: 'external',
  url: item.url,
  publishedAt: item.published_date,
  tags: [],
  score: item.final_score,
}))
```

### 4.3 api-client.ts 检查项

确保以下方法存在：

```typescript
// chatAPI 需要的方法
chatAPI.chat(query, options)           // POST /chat/v2/sync
chatAPI.confirmElements(taskId, elements, wait)  // POST /chat/v2/tasks/{task_id}/confirm
chatAPI.isElementsConfirmationResponse(response) // 类型守卫
chatAPI.getConversations(params)       // GET /chat/conversations
chatAPI.pollTask(taskId, options)      // 轮询任务状态

// langgraphAPI 需要的方法
langgraphAPI.getResults(params)        // GET /langgraph/results
```

---

## 5. 数据库集合分析

### 5.1 ai-search 使用的集合

| 集合名称 | 用途 | 状态 |
|----------|------|------|
| `chat_conversations` | 对话/历史记录存储 | ✅ 保留 |
| `chat_tasks` | 任务状态、要素确认 | ✅ 保留 |
| `langgraph_search_results` | 搜索结果存储 | ✅ 保留 |

### 5.2 可废弃的集合（仅 NL Search 使用）

| 集合名称 | 原用途 | 废弃原因 | 依赖检查 |
|----------|--------|----------|----------|
| `nl_search_logs` | NL Search 日志 | 功能已被 Chat V2 替代 | 需确认无其他引用 |

### 5.3 废弃前需检查

在废弃 `nl_search_logs` 前，需确认：

1. **后端代码引用检查**:
   ```bash
   grep -r "nl_search_logs" src/
   grep -r "NLSearchLog" src/
   grep -r "MongoNLSearchRepository" src/
   ```

2. **API 端点检查**:
   - `/nl-search/*` 端点是否还有其他功能使用
   - 是否有定时任务依赖此集合

3. **数据迁移**:
   - 历史数据是否需要迁移到新集合
   - 是否需要保留一段时间供回溯

---

## 6. 实施步骤

### Phase 1: 前端 API 对接
1. [ ] 检查并补充 `api-client.ts` 中的 Chat V2 方法
2. [ ] 修改 `useSearchWorkspace.ts` 切换到真实 API
3. [ ] 测试搜索流程（提交 → 确认 → 结果）
4. [ ] 测试历史记录加载流程

### Phase 2: 功能验证
1. [ ] 验证要素确认面板正常工作
2. [ ] 验证搜索结果正确显示
3. [ ] 验证历史记录选择和加载
4. [ ] 验证筛选和分页功能

### Phase 3: 清理工作
1. [ ] 确认 nl_search 相关代码无其他引用
2. [ ] 标记 `nl_search_logs` 集合为废弃
3. [ ] 更新 API 文档

---

## 7. 风险和注意事项

### 7.1 兼容性风险
- Chat V2 API 返回结构可能与前端类型定义不完全匹配
- 需要仔细对比 `ChatSearchElements` 等类型

### 7.2 数据迁移风险
- 废弃集合前需确保历史数据不会丢失
- 建议在废弃前做数据备份

### 7.3 性能考虑
- LangGraph 结果查询可能返回大量数据
- 考虑分页策略和前端虚拟滚动

---

## 8. 附录

### 8.1 相关文件路径

**前端 (guanshanCMS)**:
- 主页面: `app/dashboard/info-generation/collect/ai-search/page.tsx`
- 核心Hook: `app/dashboard/info-generation/collect/ai-search/hooks/useSearchWorkspace.ts`
- API客户端: `lib/api-client.ts`
- 类型定义: `lib/api-types.ts`

**后端 (guanshanPython)**:
- Chat API: `src/api/v1/endpoints/chat.py`
- Chat V2 API: `src/api/v1/endpoints/chat_v2.py`
- LangGraph API: `src/api/v1/endpoints/langgraph.py`
- 数据库仓库: `src/infrastructure/database/`

### 8.2 参考的 qa-chat 实现

qa-chat 的 `useQaChatWorkspace.ts` 包含完整的 Chat API 对接实现，可作为参考：
- 要素确认流程: 第 524-551 行
- 结果处理: 第 401-442 行
- LangGraph 结果获取: 第 890-922 行
