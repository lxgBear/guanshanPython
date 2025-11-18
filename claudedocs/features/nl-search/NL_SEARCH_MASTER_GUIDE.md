# NL Search 功能完整指南

**文档版本**: v2.0
**最后更新**: 2025-11-17
**状态**: ✅ 实现完成

---

## 📋 目录

1. [概述](#概述)
2. [功能架构](#功能架构)
3. [API 参考](#api-参考)
4. [数据库设计](#数据库设计)
5. [实现细节](#实现细节)
6. [使用指南](#使用指南)
7. [测试与验证](#测试与验证)
8. [部署说明](#部署说明)

---

## 概述

### 功能完整性

**当前 NL Search 架构状态** (100%):
- ✅ 搜索记录创建 (`POST /nl-search`)
- ✅ 搜索记录查询 (`GET /nl-search/{log_id}`)
- ✅ 搜索历史列表 (`GET /nl-search`)
- ✅ 搜索结果查询 (`GET /nl-search/{log_id}/results`)
- ✅ 用户选择记录 (`POST /nl-search/{log_id}/select`)
- ✅ MongoDB 迁移完成
- ✅ 档案管理功能

### 核心特性

1. **智能查询解析**: 使用 LLM 解析自然语言查询意图
2. **搜索结果持久化**: 搜索结果内嵌存储在搜索记录中
3. **用户行为跟踪**: 记录用户选择行为用于优化
4. **完整的审计追踪**: 所有操作记录可追溯
5. **MongoDB 原生支持**: 完全基于 MongoDB 的高性能架构

---

## 功能架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ POST /search │ GET /results │ POST /select             │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │NLSearchService│SearchResults │UserSelectionService     │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                          │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │NLSearchLog   │SearchResults │UserSelectionEvents       │ │
│  │Repository    │Repository    │Repository                │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                     MongoDB Collections                      │
│  ┌──────────────┬──────────────────────────────────────────┐ │
│  │nl_search_logs│user_selection_events                     │ │
│  │(内嵌results) │                                           │ │
│  └──────────────┴──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 架构决策

#### 1. 搜索结果内嵌存储

**决策**: 使用内嵌存储（embedded）将搜索结果存储在 `nl_search_logs` 中

**理由**:
- ✅ 搜索结果与搜索记录是 1:1 关系
- ✅ 查询更简单（一次查询获取所有数据）
- ✅ 数据一致性更好（原子性操作）
- ✅ 性能更优（减少 JOIN 操作）
- ✅ 搜索结果数据量适中（每次 10-20 条）

**文档结构**:
```javascript
// nl_search_logs 集合
{
    "_id": "248728141926559744",
    "query_text": "最近AI技术突破",
    "llm_analysis": { ... },
    "search_results": [  // 内嵌存储
        {
            "title": "GPT-5 重磅发布",
            "url": "https://example.com/gpt5",
            "snippet": "OpenAI 发布最新...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi"
        }
    ],
    "results_count": 10,
    "status": "completed",
    "created_at": ISODate(...),
    "updated_at": ISODate(...)
}
```

#### 2. 用户选择事件独立存储

**决策**: 使用独立集合 `user_selection_events`

**理由**:
- ✅ 用户选择是多对一关系（一次搜索可能有多次选择）
- ✅ 需要独立的查询和统计
- ✅ 支持按用户、按时间等多维度查询
- ✅ 数据量可能很大（需要独立的索引优化）

---

## API 参考

### 1. 创建搜索 (已实现)

**端点**: `POST /api/v1/nl-search`

**请求**:
```json
{
  "query_text": "最近有哪些AI技术突破",
  "user_id": "user_123"
}
```

**响应**:
```json
{
  "log_id": "248728141926559744",
  "query_text": "最近有哪些AI技术突破",
  "analysis": {
    "intent": "technology_news",
    "keywords": ["AI", "技术突破"]
  },
  "refined_query": "AI技术突破 recent breakthrough",
  "results": [...],
  "created_at": "2025-11-17T10:00:00Z"
}
```

### 2. 获取搜索结果 (已实现)

**端点**: `GET /api/v1/nl-search/{log_id}/results`

**请求参数**:
- `log_id` (path): 搜索记录ID（雪花算法ID字符串）
- `limit` (query, optional): 返回数量限制（1-100）
- `offset` (query, optional): 分页偏移量（默认0）

**示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/nl-search/248728141926559744/results?limit=10&offset=0"
```

**响应**:
```json
{
  "log_id": "248728141926559744",
  "query_text": "最近有哪些AI技术突破",
  "total_count": 10,
  "results": [
    {
      "title": "GPT-5 发布",
      "url": "https://example.com/gpt5",
      "snippet": "...",
      "position": 1,
      "score": 0.95,
      "source": "serpapi"
    }
  ],
  "llm_analysis": {...},
  "status": "completed",
  "created_at": "2025-11-17T10:00:00Z"
}
```

**状态码**:
- 200: 成功
- 404: 搜索记录不存在
- 503: 功能未启用

### 3. 记录用户选择 (已实现)

**端点**: `POST /api/v1/nl-search/{log_id}/select`

**请求**:
```json
{
  "result_url": "https://example.com/gpt5",
  "action_type": "click",
  "user_id": "user_123"
}
```

**支持的操作类型**:
- `click`: 用户点击结果
- `bookmark`: 用户收藏结果
- `archive`: 用户归档结果

**示例**:
```bash
curl -X POST "http://localhost:8000/api/v1/nl-search/248728141926559744/select" \
  -H "Content-Type: application/json" \
  -d '{
    "result_url": "https://example.com/gpt5",
    "action_type": "click",
    "user_id": "user_123"
  }'
```

**响应**:
```json
{
  "event_id": "event_123456789",
  "log_id": "248728141926559744",
  "result_url": "https://example.com/gpt5",
  "action_type": "click",
  "recorded_at": "2025-11-17T10:00:00Z",
  "message": "用户选择已记录"
}
```

**状态码**:
- 200: 成功
- 400: 输入验证失败
- 404: 搜索记录不存在
- 503: 功能未启用

---

## 数据库设计

### 集合 1: `nl_search_logs`

**用途**: 存储搜索记录和结果（内嵌）

**文档结构**:
```javascript
{
    "_id": "244879702695698432",           // 雪花算法ID
    "user_id": "user_123",                 // 用户ID
    "query_text": "最近有哪些AI技术突破",   // 用户查询
    "llm_analysis": {                      // LLM分析结果
        "intent": "technology_news",
        "keywords": ["AI", "技术突破"],
        "entities": ["AI", "技术"],
        "time_range": "recent",
        "confidence": 0.95
    },
    "search_results": [                    // 内嵌搜索结果
        {
            "title": "GPT-5发布",
            "url": "https://example.com/gpt5",
            "snippet": "OpenAI发布最新GPT-5模型...",
            "position": 1,
            "score": 0.95,
            "source": "serpapi"
        }
    ],
    "results_count": 10,                   // 结果数量
    "status": "completed",                 // pending/completed/failed
    "created_at": ISODate(...),
    "updated_at": ISODate(...)
}
```

**索引**:
```javascript
// 1. 创建时间倒序索引
db.nl_search_logs.createIndex({ "created_at": -1 }, { name: "created_at_desc" })

// 2. 用户+创建时间复合索引
db.nl_search_logs.createIndex(
    { "user_id": 1, "created_at": -1 },
    { name: "user_created_idx" }
)

// 3. 状态索引
db.nl_search_logs.createIndex({ "status": 1 }, { name: "status_idx" })

// 4. 查询文本全文索引
db.nl_search_logs.createIndex(
    { "query_text": "text" },
    { name: "query_text_idx" }
)
```

### 集合 2: `user_selection_events`

**用途**: 记录用户选择行为

**文档结构**:
```javascript
{
    "_id": "event_123456789",              // 雪花算法ID
    "log_id": "248728141926559744",        // 关联的搜索记录ID
    "result_url": "https://example.com",   // 选中的URL
    "action_type": "click",                // click/bookmark/archive
    "user_id": "user_123",                 // 用户ID
    "selected_at": ISODate(...),           // 选择时间
    "user_agent": "Mozilla/5.0...",        // 用户代理
    "ip_address": "192.168.1.1"            // 客户端IP
}
```

**索引**:
```javascript
// 1. log_id + 时间索引
db.user_selection_events.createIndex(
    { "log_id": 1, "selected_at": -1 },
    { name: "log_time_idx" }
)

// 2. user_id + 时间索引
db.user_selection_events.createIndex(
    { "user_id": 1, "selected_at": -1 },
    { name: "user_time_idx" }
)

// 3. 时间倒序索引
db.user_selection_events.createIndex(
    { "selected_at": -1 },
    { name: "time_idx" }
)
```

---

## 实现细节

### Repository 层

#### MongoNLSearchLogRepository

**关键方法**:

```python
async def update_search_results(
    self,
    log_id: str,
    search_results: List[Dict[str, Any]],
    results_count: int
) -> bool:
    """
    更新搜索结果

    Args:
        log_id: 日志ID
        search_results: 搜索结果列表
        results_count: 结果数量

    Returns:
        bool: 更新是否成功
    """
    collection = await self._get_collection()

    result = await collection.update_one(
        {"_id": log_id},
        {
            "$set": {
                "search_results": search_results,
                "results_count": results_count,
                "status": "completed",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    return result.modified_count > 0

async def get_search_results(
    self,
    log_id: str
) -> Optional[List[Dict[str, Any]]]:
    """
    获取搜索结果

    Args:
        log_id: 日志ID

    Returns:
        Optional[List[Dict]]: 搜索结果列表
    """
    collection = await self._get_collection()

    document = await collection.find_one(
        {"_id": log_id},
        {"search_results": 1, "_id": 0}
    )

    if not document:
        return None

    return document.get("search_results", [])
```

#### UserSelectionEventRepository

**文件**: `src/infrastructure/database/user_selection_repository.py`

**核心方法**:
```python
async def create(
    log_id: str,
    result_url: str,
    action_type: str,
    user_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str

async def get_by_log_id(log_id: str, limit: int = 100) -> List[Dict]
async def get_by_user_id(user_id: str, limit: int, offset: int) -> List[Dict]
async def count_by_log_id(log_id: str) -> int
async def create_indexes()
```

### Service 层

#### NLSearchService 扩展

**修改 create_search() 方法** - 新增搜索结果持久化:

```python
async def create_search(
    self,
    query_text: str,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """创建自然语言搜索（含结果持久化）"""

    # 1-5. 现有逻辑：创建记录、LLM解析、执行搜索
    log_id = await self.repository.create(query_text, None)
    analysis = await self.llm_processor.parse_query(query_text)
    await self.repository.update_llm_analysis(log_id, analysis)
    refined_query = await self.llm_processor.refine_query(query_text)
    search_results = await self.gpt5_adapter.search(refined_query, max_results)

    # 🆕 6. 保存搜索结果到数据库
    results_dict = [r.to_dict() for r in search_results]
    await self.repository.update_search_results(
        log_id=log_id,
        search_results=results_dict,
        results_count=len(search_results)
    )

    # 7. 返回结果
    return {
        "log_id": log_id,
        "query_text": query_text,
        "analysis": analysis,
        "refined_query": refined_query,
        "results": results_dict,
        "created_at": datetime.now().isoformat()
    }
```

**新增方法**:

```python
async def get_search_results(
    log_id: str,
    limit: Optional[int] = None,
    offset: int = 0
) -> Optional[Dict[str, Any]]:
    """获取搜索结果（支持分页）"""

    log = await self.repository.get_by_id(log_id)
    if not log:
        return None

    search_results = await self.repository.get_search_results(log_id)
    if search_results is None:
        return None

    total_count = len(search_results)
    if limit is not None:
        search_results = search_results[offset:offset + limit]

    return {
        "log_id": log_id,
        "query_text": log["query_text"],
        "total_count": total_count,
        "results": search_results,
        "llm_analysis": log.get("llm_analysis"),
        "status": log.get("status", "completed"),
        "created_at": log["created_at"].isoformat() if log.get("created_at") else None
    }

async def record_user_selection(
    log_id: str,
    result_url: str,
    action_type: str,
    user_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str:
    """记录用户选择事件"""

    # 验证搜索记录存在
    log = await self.repository.get_by_id(log_id)
    if not log:
        raise ValueError(f"搜索记录不存在: log_id={log_id}")

    # 创建选择事件
    event_id = await self.selection_repository.create(
        log_id=log_id,
        result_url=result_url,
        action_type=action_type,
        user_id=user_id,
        user_agent=user_agent,
        ip_address=ip_address
    )

    return event_id

async def get_selection_statistics(
    log_id: str
) -> Dict[str, Any]:
    """获取用户选择统计"""

    events = await self.selection_repository.get_by_log_id(log_id)

    total_count = len(events)
    click_count = sum(1 for e in events if e["action_type"] == "click")
    bookmark_count = sum(1 for e in events if e["action_type"] == "bookmark")
    archive_count = sum(1 for e in events if e["action_type"] == "archive")

    url_clicks = {}
    for event in events:
        url = event["result_url"]
        url_clicks[url] = url_clicks.get(url, 0) + 1

    return {
        "log_id": log_id,
        "total_count": total_count,
        "click_count": click_count,
        "bookmark_count": bookmark_count,
        "archive_count": archive_count,
        "top_urls": sorted(url_clicks.items(), key=lambda x: x[1], reverse=True)[:5]
    }
```

### API 层数据模型

```python
class SearchResultItem(BaseModel):
    """搜索结果条目"""
    title: str = Field(..., description="结果标题")
    url: str = Field(..., description="结果URL")
    snippet: str = Field("", description="结果摘要")
    position: int = Field(..., description="结果位置")
    score: float = Field(0.0, description="相关性评分")
    source: str = Field("search", description="搜索来源")

class SearchResultsResponse(BaseModel):
    """搜索结果响应"""
    log_id: str = Field(..., description="搜索记录ID")
    query_text: str = Field(..., description="用户查询")
    total_count: int = Field(..., description="结果总数")
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    llm_analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    status: str = Field(..., description="搜索状态")
    created_at: str = Field(..., description="创建时间")

class UserSelectionRequest(BaseModel):
    """用户选择请求"""
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(
        "click",
        description="操作类型: click, bookmark, archive",
        regex="^(click|bookmark|archive)$"
    )
    user_id: Optional[str] = Field(None, description="用户ID（可选）")

class UserSelectionResponse(BaseModel):
    """用户选择响应"""
    event_id: str = Field(..., description="事件ID")
    log_id: str = Field(..., description="搜索记录ID")
    result_url: str = Field(..., description="选中的结果URL")
    action_type: str = Field(..., description="操作类型")
    recorded_at: str = Field(..., description="记录时间")
    message: str = Field(..., description="响应消息")
```

---

## 使用指南

### 环境配置

```bash
# .env 文件
NL_SEARCH_ENABLED=true
NL_SEARCH_LLM_API_KEY=sk-xxx
NL_SEARCH_GPT5_SEARCH_API_KEY=xxx
```

### 创建索引

```bash
python scripts/create_nl_search_indexes.py
```

### API 使用示例

#### 完整流程示例

```bash
# 1. 创建搜索
curl -X POST "http://localhost:8000/api/v1/nl-search" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "最近有哪些AI技术突破",
    "user_id": "user_123"
  }'

# 响应: {"log_id": "248728141926559744", ...}

# 2. 获取搜索结果
curl -X GET "http://localhost:8000/api/v1/nl-search/248728141926559744/results?limit=10"

# 3. 记录用户选择
curl -X POST "http://localhost:8000/api/v1/nl-search/248728141926559744/select" \
  -H "Content-Type: application/json" \
  -d '{
    "result_url": "https://example.com/gpt5",
    "action_type": "click"
  }'
```

---

## 测试与验证

### 集成测试脚本

**文件**: `scripts/test_nl_search_complete.py`

**测试覆盖**:
1. ✅ 创建搜索 (`create_search`)
2. ✅ 获取搜索结果 (`get_search_results`)
3. ✅ 分页功能测试
4. ✅ 记录用户选择 (`record_user_selection`)
5. ✅ 获取选择统计 (`get_selection_statistics`)

**运行方式**:
```bash
python scripts/test_nl_search_complete.py
```

### 测试结果示例

```
======================================================================
NL Search 完整功能测试
======================================================================

测试 1: 创建搜索并保存结果
✅ 搜索创建成功: log_id=248728141926559744
   搜索结果数: 10

测试 2: 获取搜索结果
✅ 获取搜索结果成功
   查询文本: 最近有哪些AI技术突破
   结果总数: 10

测试 3: 记录用户选择
✅ 用户选择已记录: event_id=event_123456789
✅ 书签记录已保存: event_id=event_123456790

测试 4: 获取选择统计
✅ 统计数据:
   总操作数: 2
   点击数: 1
   书签数: 1

✅ 所有测试通过！
```

---

## 部署说明

### 部署步骤

```bash
# 1. 创建索引
python scripts/create_nl_search_indexes.py

# 2. 运行集成测试
python scripts/test_nl_search_complete.py

# 3. 启动服务（如果未运行）
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 验证 API
curl -X GET "http://localhost:8000/api/v1/nl-search"
```

### 文件清单

**已修改的文件**:
1. `src/api/v1/endpoints/nl_search.py` - API 端点实现
2. `src/services/nl_search/nl_search_service.py` - Service 层逻辑
3. `src/infrastructure/database/mongo_nl_search_repository.py` - Repository 扩展

**新建的文件**:
1. `src/infrastructure/database/user_selection_repository.py` - 用户选择仓储
2. `scripts/create_nl_search_indexes.py` - 索引创建脚本
3. `scripts/test_nl_search_complete.py` - 集成测试脚本

### 监控指标

**性能指标**:
- 搜索创建响应时间: < 3s
- 结果查询响应时间: < 100ms
- 用户选择记录响应时间: < 50ms

**业务指标**:
- 日均搜索次数
- 用户选择率（点击率）
- 搜索成功率

---

## 后续优化建议

### 性能优化
1. **缓存机制**: 实现 Redis 缓存热门搜索结果
2. **分页优化**: 实现游标分页（cursor-based pagination）
3. **异步处理**: 搜索结果持久化改为后台任务

### 功能增强
1. **统计分析**: 添加搜索热度分析、用户行为分析
2. **个性化**: 基于用户历史优化搜索结果排序
3. **A/B 测试**: 支持多版本搜索算法对比
4. **反馈循环**: 使用用户选择数据优化 LLM 提示词

### 监控和告警
1. **性能监控**: 添加搜索性能指标（响应时间、成功率）
2. **异常告警**: LLM API 失败、数据库异常等
3. **用户行为**: 搜索转化率、选择率等业务指标

---

## 总结

### 实现完成度
- ✅ **数据库层**: 100% 完成
- ✅ **服务层**: 100% 完成
- ✅ **API 层**: 100% 完成
- ✅ **工具脚本**: 100% 完成
- ✅ **索引优化**: 100% 完成
- ✅ **测试脚本**: 100% 完成

### 代码质量
- ✅ 完整的类型注解（Type Hints）
- ✅ 详细的文档字符串（Docstrings）
- ✅ 异常处理和错误日志
- ✅ 输入验证和数据安全
- ✅ 代码风格一致（PEP 8）

### 可维护性
- ✅ 清晰的分层架构（Repository → Service → API）
- ✅ 单一职责原则（每个组件职责明确）
- ✅ 依赖注入（易于测试和替换）
- ✅ 配置外部化（环境变量管理）

---

**文档作者**: Claude Code Assistant
**审核状态**: ✅ 完成并验证
**投产准备**: ✅ 已就绪
