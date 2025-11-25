# NL Search 到档案创建完整流程文档

**文档版本**: v1.0.0
**创建日期**: 2025-11-22
**目的**: 详细记录从自然语言搜索到档案创建的完整数据流和API调用链

---

## 流程概览

```
用户查询 → NL Search创建 → 结果保存 → 用户查看 → (可选)批量编辑 → 档案创建
```

---

## 详细流程步骤

### 步骤 1: 创建自然语言搜索 (NL Search Creation)

**API端点**: `POST /api/v1/nl-search/`

**用户操作**:
- 用户输入自然语言查询，例如: "最近有哪些AI技术突破"
- 选择搜索模式: `single` (单次快速) 或 `multi` (多问题深度)

**系统执行流程**:

1. **API层接收请求** - `src/api/v1/endpoints/nl_search.py:382`
   ```python
   async def create_nl_search(request: NLSearchRequest):
       # 请求参数: query_text, user_id, search_mode
   ```

2. **服务层处理** - `src/services/nl_search/nl_search_service.py:95`
   ```python
   async def create_search(
       query_text: str,
       user_id: Optional[str] = None,
       search_mode: str = "single"
   ) -> Dict[str, Any]:
   ```

3. **生成搜索记录ID** - 使用雪花算法生成唯一ID
   ```python
   log_id = self.id_generator.generate_id()  # 返回字符串格式
   ```

4. **LLM 分析查询** - `src/services/nl_search/nl_search_service.py:148`
   ```python
   analysis = await self._analyze_query_with_llm(query_text)
   # 提取: keywords, intent, entities, time_range
   ```

5. **执行搜索**:
   - **Single模式** → `_execute_single_search()` → GPT-5 Search API
   - **Multi模式** → `_execute_multi_search()` → 分解子问题 → 多次搜索

6. **内容爬取与去重** - `src/services/nl_search/nl_search_service.py:415`
   ```python
   async def _scrape_and_deduplicate_results(results: List[Dict]) -> List[Dict]:
       # URL归一化 (26个跟踪参数移除)
       # 内容Hash去重
       # 抓取网页内容
   ```

7. **保存到 nl_search_logs 集合**:
   ```python
   await self.search_log_repo.create(
       log_id=log_id,
       query_text=query_text,
       search_mode=search_mode,
       analysis=analysis,
       results=results,
       created_at=datetime.utcnow()
   )
   ```

8. **🔑 关键步骤: Dual-Write 到 news_results** - `src/services/nl_search/nl_search_service.py:579`
   ```python
   await self._write_to_search_results_collection(log_id, results)
   # 将搜索结果同时写入 news_results 集合
   # 这是后续档案创建的数据来源
   ```

**数据流**:
```
用户输入 → nl_search_service.create_search()
         ↓
   生成 log_id (雪花ID字符串)
         ↓
   LLM 分析 + GPT-5 Search + 爬取去重
         ↓
   保存到两个集合:
   ├─ nl_search_logs (搜索元数据)
   └─ news_results (搜索结果内容) ← Dual-Write
```

**涉及集合**:
- ✅ **nl_search_logs**: 存储搜索记录 (log_id, query_text, analysis, status)
- ✅ **news_results**: 存储搜索结果 (title, url, content, category, media_urls)

**代码位置**:
- API: `src/api/v1/endpoints/nl_search.py:382-486`
- Service: `src/services/nl_search/nl_search_service.py:95-649`
- URL去重: `src/services/nl_search/url_normalizer.py:23-85`

---

### 步骤 2: 用户查看搜索结果 (View Search Results)

**API端点**: `GET /api/v1/nl-search/{log_id}/results`

**用户操作**:
- 前端使用 `log_id` 获取搜索结果列表
- 支持分页: `?limit=10&offset=0`

**系统执行流程**:

1. **API层接收请求** - `src/api/v1/endpoints/nl_search.py:826`
   ```python
   async def get_search_results(
       log_id: str,
       limit: Optional[int] = Query(None, ge=1, le=100),
       offset: int = Query(0, ge=0)
   ):
   ```

2. **服务层查询** - `src/services/nl_search/nl_search_service.py:651`
   ```python
   async def get_search_results(
       log_id: str,
       limit: Optional[int] = None,
       offset: int = 0
   ) -> Optional[Dict[str, Any]]:
       # 从 news_results 集合查询结果
   ```

3. **数据返回**:
   ```python
   SearchResultsResponse(
       log_id=log_id,
       query_text=query_text,
       total_count=len(results),
       results=[
           SearchResultItem(
               title=item["title"],
               url=item["url"],
               snippet=item["snippet"],
               position=item["position"],
               score=item["score"],
               source=item["source"]
           )
       ],
       llm_analysis=analysis,
       status="completed",
       created_at=created_at
   )
   ```

**数据流**:
```
前端请求 (log_id) → API → Service
                            ↓
                    查询 news_results 集合
                            ↓
                    返回结果列表
```

**涉及集合**:
- ✅ **news_results**: 读取搜索结果数据

**代码位置**:
- API: `src/api/v1/endpoints/nl_search.py:788-958`
- Service: `src/services/nl_search/nl_search_service.py:651-726`

---

### 步骤 3: 用户批量编辑 (Optional - Batch Editing)

**⚠️ 注意**: 这是一个**独立的**批量编辑系统，与档案创建流程**不直接关联**

**API端点**:
- `POST /api/v1/user-edits/batch` - 批量更新不同字段
- `POST /api/v1/user-edits/batch-fields` - 批量更新相同字段
- `PATCH /api/v1/user-edits/{record_id}` - 单条记录更新

**用户操作**:
- 用户可以批量编辑搜索结果的标题、摘要、分类等

**系统执行流程**:

1. **批量编辑API** - `src/api/v1/endpoints/user_edits.py:184`
   ```python
   @router.post("/batch", response_model=BatchUpdateResponse)
   async def batch_update(request: BatchUpdateRequest):
       # 批量更新多个记录，每个记录可以有不同的字段
   ```

2. **保存到独立集合**:
   ```
   user_edited_results 集合
   ```

**⚠️ 当前问题**:
- 批量编辑结果存储在 `user_edited_results` 集合
- 档案创建从 `news_results` 集合读取
- **两者之间没有数据同步**

**数据流**:
```
用户批量编辑 → user_edits API
                      ↓
              user_edited_results 集合
                      ↓
              ❌ 未同步到 news_results
                      ↓
              档案创建时无法读取编辑内容
```

**涉及集合**:
- ✅ **user_edited_results**: 存储批量编辑结果 (独立系统)

**代码位置**:
- API: `src/api/v1/endpoints/user_edits.py:184-453`

---

### 步骤 4: 创建档案 (Archive Creation)

**API端点**: `POST /api/v1/nl-search/archives`

**用户操作**:
- 用户选择多个搜索结果创建档案
- 提供档案名称、描述、标签
- 为每个结果提供: 编辑标题、编辑摘要、备注、评分

**系统执行流程**:

1. **API层接收请求** - `src/api/v1/endpoints/nl_search.py:969`
   ```python
   async def create_archive(request: CreateArchiveRequest):
       # 请求参数:
       # - user_id: 用户ID
       # - archive_name: 档案名称
       # - description: 档案描述
       # - tags: 标签列表
       # - search_log_id: 关联的搜索记录ID (可选)
       # - items: 档案条目列表
       #   - news_result_id: 新闻结果ID (MongoDB ObjectId)
       #   - edited_title: 编辑后的标题 (可选)
       #   - edited_summary: 编辑后的摘要 (可选)
       #   - user_notes: 用户备注 (可选)
       #   - user_rating: 用户评分 1-5 (可选)
   ```

2. **准备条目数据**:
   ```python
   items_data = [
       {
           "news_result_id": item.news_result_id,
           "edited_title": item.edited_title,
           "edited_summary": item.edited_summary,
           "user_notes": item.user_notes,
           "user_rating": item.user_rating
       }
       for item in request.items
   ]
   ```

3. **服务层创建档案** - `src/services/nl_search/mongo_archive_service.py:60`
   ```python
   async def create_archive(
       user_id: int,
       archive_name: str,
       items: List[Dict[str, Any]],
       description: Optional[str] = None,
       tags: Optional[List[str]] = None,
       search_log_id: Optional[int] = None
   ) -> Dict[str, Any]:
   ```

4. **为每个条目创建快照** - `src/services/nl_search/mongo_archive_service.py:392`
   ```python
   async def _create_snapshot(self, news_result_id: str) -> Optional[Dict[str, Any]]:
       # 从 news_results 集合读取原始数据
       news_result = await self.db["news_results"].find_one({"_id": news_result_id})

       # 提取关键字段
       snapshot = {
           "title": news_result.get("title"),
           "content": news_result.get("content"),
           "category": news_result.get("category"),
           "published_at": news_result.get("published_at"),
           "source": news_result.get("source"),
           "media_urls": news_result.get("media_urls", [])
       }
       return snapshot
   ```

5. **构建档案文档**:
   ```python
   archive_doc = {
       "_id": archive_id,  # MongoDB ObjectId
       "user_id": user_id,
       "archive_name": archive_name,
       "description": description,
       "tags": tags or [],
       "search_log_id": search_log_id,
       "items": [
           {
               "id": item_counter,
               "news_result_id": item["news_result_id"],
               "snapshot": snapshot,  # 从 news_results 提取
               "edited_title": item.get("edited_title"),
               "edited_summary": item.get("edited_summary"),
               "user_notes": item.get("user_notes"),
               "user_rating": item.get("user_rating"),
               "created_at": datetime.utcnow()
           }
       ],
       "items_count": len(items),
       "created_at": datetime.utcnow(),
       "updated_at": datetime.utcnow()
   }
   ```

6. **保存到 user_archives 集合**:
   ```python
   await self.db["user_archives"].insert_one(archive_doc)
   ```

**数据流**:
```
用户选择结果 → 创建档案请求
               ↓
     API → mongo_archive_service.create_archive()
               ↓
     为每个 news_result_id 创建快照
               ↓
     从 news_results 集合读取原始数据
               ↓
     合并用户编辑 (edited_title, edited_summary, user_notes, user_rating)
               ↓
     保存到 user_archives 集合
```

**涉及集合**:
- ✅ **news_results**: 读取原始搜索结果数据 (快照来源)
- ✅ **user_archives**: 存储档案及条目

**代码位置**:
- API: `src/api/v1/endpoints/nl_search.py:963-1069`
- Service: `src/services/nl_search/mongo_archive_service.py:60-158`
- Snapshot创建: `src/services/nl_search/mongo_archive_service.py:392-445`

---

## 数据集合关系图

```
┌────────────────────┐
│  nl_search_logs    │  ← 搜索元数据 (log_id, query_text, analysis)
└────────────────────┘
         │
         │ 关联关系 (search_log_id)
         ↓
┌────────────────────┐
│   news_results     │  ← 搜索结果 (title, url, content, category)
└────────────────────┘      ↑
         │                  │
         │                  │ 档案快照来源
         │                  │
         ↓                  │
┌────────────────────┐      │
│user_edited_results │  ← 批量编辑 (独立系统，未集成)
└────────────────────┘      │
                            │
                            ↓
                    ┌────────────────────┐
                    │  user_archives     │  ← 用户档案
                    └────────────────────┘
                            │
                            └─ items: [
                                 news_result_id,
                                 snapshot (从 news_results 提取),
                                 edited_title,
                                 edited_summary,
                                 user_notes,
                                 user_rating
                               ]
```

---

## 当前架构问题与改进建议

### 🔴 问题 1: 批量编辑与档案创建未集成

**现状**:
- 批量编辑结果存储在 `user_edited_results` 集合
- 档案创建从 `news_results` 集合读取
- **两者之间没有数据同步**

**影响**:
- 用户通过批量编辑API编辑的内容，在创建档案时无法自动使用
- 用户需要在创建档案时**重新输入**编辑内容

**改进建议**:

**方案 A: 档案创建时合并批量编辑数据**
```python
# 在 mongo_archive_service.create_archive() 中:
async def create_archive(...):
    for item in items:
        # 1. 从 news_results 读取原始数据
        snapshot = await self._create_snapshot(item["news_result_id"])

        # 2. 检查是否存在批量编辑记录
        edited = await self.db["user_edited_results"].find_one({
            "news_result_id": item["news_result_id"],
            "user_id": user_id
        })

        # 3. 优先使用批量编辑的内容
        if edited:
            item["edited_title"] = item.get("edited_title") or edited.get("edited_title")
            item["edited_summary"] = item.get("edited_summary") or edited.get("edited_summary")
```

**方案 B: 批量编辑直接更新 news_results**
```python
# 修改 user_edits API，使其直接更新 news_results 集合
# 优点: 简化数据流，无需额外集合
# 缺点: 失去编辑历史追踪能力
```

**方案 C: 增加同步机制**
```python
# 在批量编辑后，自动同步到 news_results
# 保留 user_edited_results 用于历史追踪
# 优点: 保持两个系统独立性，同时实现数据同步
# 缺点: 增加复杂度
```

---

### 🟡 问题 2: 档案条目编辑缺少API

**现状**:
- 档案创建后，无法单独编辑某个条目
- 只能通过 `PUT /archives/{archive_id}` 更新档案基本信息 (名称、描述、标签)

**影响**:
- 用户创建档案后，发现某个条目有错误，无法单独修改
- 只能删除整个档案重新创建

**改进建议**:

新增API端点:
```python
# 更新档案条目
PATCH /api/v1/nl-search/archives/{archive_id}/items/{item_id}

# 删除档案条目
DELETE /api/v1/nl-search/archives/{archive_id}/items/{item_id}

# 添加档案条目
POST /api/v1/nl-search/archives/{archive_id}/items
```

---

### 🟡 问题 3: 缺少档案与搜索记录的双向关联

**现状**:
- 档案可以关联 `search_log_id`
- 但从搜索记录无法查询"基于此搜索创建了哪些档案"

**影响**:
- 用户无法追溯某次搜索产生了哪些档案
- 无法实现"基于搜索的档案管理"功能

**改进建议**:

新增API端点:
```python
# 查询某个搜索记录关联的所有档案
GET /api/v1/nl-search/{log_id}/archives

# 返回:
{
    "log_id": "248728141926559744",
    "archives": [
        {"archive_id": "xxx", "archive_name": "AI技术汇总"},
        {"archive_id": "yyy", "archive_name": "深度学习进展"}
    ]
}
```

---

### 🟢 问题 4: 档案快照可能过时

**现状**:
- 档案创建时，从 `news_results` 提取快照
- 如果 `news_results` 的数据后续被更新或删除，档案快照仍保持创建时的状态

**评估**:
- ✅ **优点**: 档案内容稳定，不受原始数据变化影响
- ⚠️ **缺点**: 无法获取最新数据

**改进建议** (可选):
```python
# 提供"刷新快照"功能
POST /api/v1/nl-search/archives/{archive_id}/items/{item_id}/refresh

# 从 news_results 重新提取最新数据更新快照
```

---

## 完整数据流总结

### 正常流程 (无批量编辑):
```
1. 用户查询
   ↓
2. NL Search创建 → 保存到 nl_search_logs + news_results (Dual-Write)
   ↓
3. 用户查看结果 (从 news_results 读取)
   ↓
4. 用户创建档案 → 从 news_results 创建快照 → 保存到 user_archives
```

### 有批量编辑的流程 (当前问题):
```
1. 用户查询
   ↓
2. NL Search创建 → nl_search_logs + news_results
   ↓
3. 用户批量编辑 → user_edited_results (❌ 未同步)
   ↓
4. 用户创建档案 → 从 news_results 读取 (❌ 无法获取编辑内容)
                ↓
              用户需要重新输入编辑内容
```

---

## 关键代码位置速查

| 功能 | 文件 | 行号 | 说明 |
|------|------|------|------|
| NL Search创建 | `src/api/v1/endpoints/nl_search.py` | 382-486 | API端点 |
| NL Search服务 | `src/services/nl_search/nl_search_service.py` | 95-649 | 核心服务 |
| Dual-Write | `src/services/nl_search/nl_search_service.py` | 579-649 | 写入news_results |
| URL归一化 | `src/services/nl_search/url_normalizer.py` | 23-85 | 去重26个参数 |
| 查看结果 | `src/api/v1/endpoints/nl_search.py` | 788-958 | 结果查询API |
| 批量编辑 | `src/api/v1/endpoints/user_edits.py` | 184-453 | 独立系统 |
| 档案创建 | `src/api/v1/endpoints/nl_search.py` | 963-1069 | API端点 |
| 档案服务 | `src/services/nl_search/mongo_archive_service.py` | 60-158 | 核心服务 |
| 快照创建 | `src/services/nl_search/mongo_archive_service.py` | 392-445 | 从news_results提取 |
| 档案查询 | `src/api/v1/endpoints/nl_search.py` | 1072-1109 | 列表查询 |
| 档案详情 | `src/api/v1/endpoints/nl_search.py` | 1110-1229 | 详情查询 |
| 档案更新 | `src/api/v1/endpoints/nl_search.py` | 1230-1350 | 更新基本信息 |
| 档案删除 | `src/api/v1/endpoints/nl_search.py` | 1351-1430 | 删除档案 |

---

## MongoDB 集合结构

### nl_search_logs
```javascript
{
    "_id": "248728141926559744",  // 雪花ID字符串
    "query_text": "最近有哪些AI技术突破",
    "user_id": "user_123",
    "search_mode": "single",
    "analysis": {
        "keywords": ["AI", "技术突破"],
        "intent": "technology_news",
        "entities": [],
        "time_range": "recent"
    },
    "status": "completed",
    "created_at": ISODate("2025-11-22T08:00:00Z")
}
```

### news_results
```javascript
{
    "_id": ObjectId("507f1f77bcf86cd799439011"),
    "search_log_id": "248728141926559744",  // 关联nl_search_logs
    "title": "GPT-5发布：AI技术新突破",
    "url": "https://example.com/gpt5",
    "content": "完整网页内容...",
    "snippet": "摘要内容...",
    "category": {
        "main": "Technology",
        "sub": "AI"
    },
    "published_at": ISODate("2025-11-20T10:00:00Z"),
    "source": "serpapi",
    "media_urls": ["https://..."],
    "position": 1,
    "score": 0.95,
    "created_at": ISODate("2025-11-22T08:00:00Z")
}
```

### user_edited_results (独立系统)
```javascript
{
    "_id": ObjectId("..."),
    "news_result_id": ObjectId("507f1f77bcf86cd799439011"),
    "user_id": "user_123",
    "edited_title": "GPT-5重磅发布",
    "edited_summary": "OpenAI发布最新GPT-5模型...",
    "edited_category": {...},
    "edited_at": ISODate("2025-11-22T09:00:00Z")
}
```

### user_archives
```javascript
{
    "_id": ObjectId("..."),
    "user_id": 1001,
    "archive_name": "2024年AI技术突破汇总",
    "description": "整理2024年重要的AI技术突破新闻",
    "tags": ["AI", "技术", "2024"],
    "search_log_id": "248728141926559744",  // 可选，关联nl_search_logs
    "items": [
        {
            "id": 1,
            "news_result_id": "507f1f77bcf86cd799439011",
            "snapshot": {  // 从news_results创建时提取
                "title": "GPT-5发布：AI技术新突破",
                "content": "完整网页内容...",
                "category": {...},
                "published_at": ISODate("..."),
                "source": "serpapi",
                "media_urls": [...]
            },
            "edited_title": "GPT-5重磅发布",  // 用户在创建档案时提供
            "edited_summary": "OpenAI发布最新GPT-5模型...",
            "user_notes": "重要技术突破，值得关注",
            "user_rating": 5,
            "created_at": ISODate("2025-11-22T10:00:00Z")
        }
    ],
    "items_count": 1,
    "created_at": ISODate("2025-11-22T10:00:00Z"),
    "updated_at": ISODate("2025-11-22T10:00:00Z")
}
```

---

## 推荐改进优先级

| 优先级 | 问题 | 影响范围 | 实施难度 | 建议方案 |
|--------|------|----------|----------|----------|
| 🔴 **P0** | 批量编辑与档案创建未集成 | 用户体验 | 中 | 方案A: 档案创建时合并数据 |
| 🟡 **P1** | 档案条目编辑缺少API | 功能完整性 | 低 | 新增3个API端点 |
| 🟡 **P2** | 缺少双向关联查询 | 功能完整性 | 低 | 新增1个API端点 |
| 🟢 **P3** | 档案快照可能过时 | 数据新鲜度 | 低 | 新增刷新快照API (可选) |

---

**文档维护**: Claude Code - Backend & Architect Personas
**审查状态**: 待用户审查
**后续计划**: 根据用户反馈实施改进方案
