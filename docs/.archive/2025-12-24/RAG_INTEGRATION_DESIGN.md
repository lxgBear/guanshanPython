# RAG 系统集成设计文档

**文档版本**: v1.0.0
**创建日期**: 2025-11-22
**目的**: 设计RAG搜索结果与批量编辑、档案创建流程的集成方案

---

## 功能概述

### RAG 系统角色定位

RAG (Retrieval-Augmented Generation) 系统是**自然语言搜索入库后的查询接口**，用于从已入库的 `news_results` 数据中检索相关内容。

### 完整工作流

```
1. 自然语言搜索 (NL Search) → 数据入库到 news_results
                                      ↓
2. RAG 查询 → 从 news_results 检索相关内容 (通过向量相似度)
                                      ↓
3. 前端展示 → 用户查看RAG返回的结果列表
                                      ↓
4. 批量编辑 → 用户修改标题、摘要、分类等 (user_edits API)
                                      ↓
5. 创建档案 → 保存精选内容到 user_archives
```

---

## RAG 接口分析

### 接口详情

**端点**: `POST http://192.168.0.5:8035/chat`

**请求格式**:
```bash
curl -N -X POST "http://192.168.0.5:8035/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "请介绍关于西藏的新闻"}'
```

**响应格式**: Server-Sent Events (SSE) 流式响应

**数据结构**:
```json
{
  "type": "sources",
  "data": [
    {
      "id": "6e63c831-c473-4079-a18c-bcffb5ee7edb",  // RAG系统内部ID (UUID)
      "score": 0.126,  // 相关性评分
      "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！ - 华语青年挺藏会",
      "source": "chineseyouthstandfortibet.substack.com",
      "category": {
        "大类": "安全情报",
        "类别": "涉藏",
        "地域": "东亚"
      },
      "publish_time": "未知时间",
      "mongo_id": "249832360786370562",  // ✨ 关键：news_results表的_id
      "preview": "**本会编辑留学生张雅笛回国探亲遭"文字狱"！** ..."
    }
  ]
}
```

### 关键字段说明

| 字段 | 类型 | 说明 | 用途 |
|------|------|------|------|
| `id` | UUID | RAG向量数据库ID | RAG系统内部使用 |
| `score` | Float | 向量相似度评分 | 相关性排序 |
| `title` | String | 新闻标题 | 前端显示 |
| `source` | String | 来源网站 | 溯源信息 |
| `category` | Object | 分类信息 | 过滤和分组 |
| `publish_time` | String | 发布时间 | 时间排序 |
| **`mongo_id`** | **String** | **news_results表的_id** | **🔑 关联MongoDB的关键** |
| `preview` | String | 内容预览 | 前端摘要显示 |

---

## 数据流集成方案

### 完整数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│  步骤 1: 自然语言搜索入库 (现有流程)                              │
└─────────────────────────────────────────────────────────────────┘
         │
         │ NL Search API (POST /nl-search)
         ↓
   ┌──────────────┐
   │ nl_search_logs│  存储搜索元数据
   └──────────────┘
         │
         │ Dual-Write
         ↓
   ┌──────────────┐
   │ news_results │  存储搜索结果内容 (_id: mongo_id)
   └──────────────┘
         │
         │ (数据已入库，等待RAG查询)
         │
┌─────────────────────────────────────────────────────────────────┐
│  步骤 2: RAG 检索 (新功能)                                        │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 用户自然语言查询
         ↓
   ┌──────────────┐
   │  RAG 系统    │  向量检索 + 相似度计算
   │(192.168.0.5) │
   └──────────────┘
         │
         │ SSE 流式返回
         ↓
   返回结果列表 (包含 mongo_id)
         │
┌─────────────────────────────────────────────────────────────────┐
│  步骤 3: 前端展示与用户交互                                       │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 前端接收RAG结果
         ↓
   展示结果列表 (带编辑功能)
         │
         │ 用户选择要编辑的记录
         ↓
┌─────────────────────────────────────────────────────────────────┐
│  步骤 4: 批量编辑 (现有API，需要增强)                             │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 使用 mongo_id 作为 record_id
         ↓
   POST /api/v1/user-edits/batch
   {
     "updates": [
       {
         "record_id": "249832360786370562",  // 使用RAG返回的mongo_id
         "fields": {
           "title": "编辑后的标题",
           "summary": "编辑后的摘要"
         }
       }
     ]
   }
         │
         ↓
   ┌──────────────────────┐
   │ user_edited_results  │  保存编辑记录
   └──────────────────────┘
         │
┌─────────────────────────────────────────────────────────────────┐
│  步骤 5: 创建档案 (现有API，需要增强)                             │
└─────────────────────────────────────────────────────────────────┘
         │
         │ 用户选择已编辑的记录创建档案
         ↓
   POST /api/v1/nl-search/archives
   {
     "user_id": 1001,
     "archive_name": "西藏相关新闻汇总",
     "items": [
       {
         "news_result_id": "249832360786370562",  // 使用mongo_id
         "edited_title": "...",  // 可选，优先使用user_edited_results
         "edited_summary": "..."
       }
     ]
   }
         │
         ↓
   ┌──────────────┐
   │ user_archives│  保存档案
   └──────────────┘
```

---

## 需要新增/修改的功能

### 🆕 功能 1: RAG 结果代理API (新增)

**问题**:
- 前端直接调用RAG系统 (192.168.0.5:8035) 存在跨域问题
- 无法统一管理RAG调用和认证

**解决方案**: 在现有系统中新增RAG代理API

**新增端点**: `POST /api/v1/nl-search/rag-query`

**实现代码**:

```python
# src/api/v1/endpoints/nl_search.py

import httpx
from fastapi.responses import StreamingResponse

class RAGQueryRequest(BaseModel):
    """RAG查询请求"""
    question: str = Field(..., description="自然语言查询", min_length=1, max_length=1000)
    user_id: Optional[str] = Field(None, description="用户ID（可选）")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件（类别、地域等）")

class RAGSourceItem(BaseModel):
    """RAG返回的单个结果"""
    id: str = Field(..., description="RAG内部ID (UUID)")
    score: float = Field(..., description="相关性评分")
    title: str = Field(..., description="新闻标题")
    source: str = Field(..., description="来源网站")
    category: Dict[str, str] = Field(..., description="分类信息")
    publish_time: str = Field(..., description="发布时间")
    mongo_id: str = Field(..., description="MongoDB news_results表的_id")
    preview: str = Field(..., description="内容预览")

@router.post(
    "/rag-query",
    summary="RAG自然语言查询",
    description="使用RAG系统从已入库数据中检索相关内容"
)
async def rag_query(request: RAGQueryRequest):
    """
    RAG自然语言查询代理

    **功能**: 🆕 新增

    **流程**:
    1. 接收前端自然语言查询
    2. 转发到RAG系统 (192.168.0.5:8035)
    3. 流式返回SSE结果
    4. (可选) 记录查询日志

    **返回格式**: Server-Sent Events (SSE)

    **数据结构**:
    ```json
    data: {
      "type": "sources",
      "data": [
        {
          "id": "uuid",
          "score": 0.126,
          "title": "新闻标题",
          "source": "来源网站",
          "category": {"大类": "...", "类别": "...", "地域": "..."},
          "publish_time": "时间",
          "mongo_id": "249832360786370562",  // news_results表的_id
          "preview": "内容预览"
        }
      ]
    }
    ```

    Args:
        request (RAGQueryRequest): 查询请求

    Returns:
        StreamingResponse: SSE流式响应

    Example:
        ```bash
        curl -N -X POST "http://localhost:8000/api/v1/nl-search/rag-query" \\
          -H "Content-Type: application/json" \\
          -d '{
            "question": "请介绍关于西藏的新闻",
            "user_id": "user_123"
          }'
        ```
    """
    try:
        logger.info(f"RAG查询: question={request.question}, user_id={request.user_id}")

        # RAG系统配置
        RAG_ENDPOINT = "http://192.168.0.5:8035/chat"

        async def sse_generator():
            """SSE流式生成器"""
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    RAG_ENDPOINT,
                    json={"question": request.question},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            yield f"{line}\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
            }
        )

    except Exception as e:
        logger.error(f"RAG查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "RAG查询失败",
                "message": str(e)
            }
        )
```

---

### 🔧 功能 2: 批量编辑API增强 (修改)

**问题**:
- 现有批量编辑API使用的 `record_id` 需要明确支持 `mongo_id` (news_results的_id)

**解决方案**: 确认 `record_id` 可以接收 `mongo_id`

**现有代码检查**: `src/api/v1/endpoints/user_edits.py`

```python
# 确认批量编辑API已支持使用mongo_id作为record_id
@router.post("/batch", response_model=BatchUpdateResponse)
async def batch_update(request: BatchUpdateRequest):
    """
    批量更新多个记录

    **增强**: 支持使用RAG返回的mongo_id作为record_id

    Args:
        request.updates: [
            {
                "record_id": "249832360786370562",  // ✅ 使用RAG返回的mongo_id
                "fields": {
                    "title": "编辑后的标题",
                    "summary": "编辑后的摘要",
                    "category": {...}
                }
            }
        ]
    """
    # 现有逻辑已支持，无需修改
```

**文档更新**: 在API文档中明确说明支持RAG场景

---

### 🔧 功能 3: 档案创建API增强 (修改)

**问题**:
- 需要在创建档案时自动合并 `user_edited_results` 中的编辑内容

**解决方案**: 实现P0优先级问题的解决方案

**修改位置**: `src/services/nl_search/mongo_archive_service.py:60`

```python
async def create_archive(
    user_id: int,
    archive_name: str,
    items: List[Dict[str, Any]],
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search_log_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    创建档案

    **增强**: 自动合并user_edited_results中的编辑内容

    **流程**:
    1. 从 news_results 创建快照
    2. 🆕 检查 user_edited_results 中是否有编辑记录
    3. 🆕 合并编辑内容 (优先使用已保存的编辑)
    4. 保存到 user_archives
    """
    # 原有验证逻辑...

    archive_items = []
    item_counter = 1

    for item in items:
        news_result_id = item["news_result_id"]

        # 1. 从 news_results 创建快照 (原有逻辑)
        snapshot = await self._create_snapshot(news_result_id)

        if not snapshot:
            logger.warning(f"无法创建快照: news_result_id={news_result_id}")
            continue

        # 🆕 2. 检查是否存在批量编辑记录
        edited_record = await self.db["user_edited_results"].find_one({
            "news_result_id": news_result_id,
            "user_id": user_id
        })

        # 🆕 3. 合并编辑内容 (优先使用已保存的编辑)
        edited_title = item.get("edited_title")
        edited_summary = item.get("edited_summary")

        if edited_record:
            # 优先使用user_edited_results中的编辑内容
            edited_title = edited_title or edited_record.get("edited_title")
            edited_summary = edited_summary or edited_record.get("edited_summary")

            logger.info(
                f"合并批量编辑内容: news_result_id={news_result_id}, "
                f"has_edited_title={bool(edited_title)}, "
                f"has_edited_summary={bool(edited_summary)}"
            )

        # 4. 构建档案条目
        archive_item = {
            "id": item_counter,
            "news_result_id": news_result_id,
            "snapshot": snapshot,
            "edited_title": edited_title,  # 使用合并后的内容
            "edited_summary": edited_summary,  # 使用合并后的内容
            "user_notes": item.get("user_notes"),
            "user_rating": item.get("user_rating"),
            "created_at": datetime.utcnow()
        }

        archive_items.append(archive_item)
        item_counter += 1

    # 原有保存逻辑...
```

---

### 🆕 功能 4: RAG结果预览API (新增，可选)

**用途**: 前端在显示RAG结果时，可能需要查看完整的 news_results 数据

**新增端点**: `GET /api/v1/nl-search/rag-preview/{mongo_id}`

```python
@router.get(
    "/rag-preview/{mongo_id}",
    summary="RAG结果详情预览",
    description="根据RAG返回的mongo_id获取完整的news_results数据"
)
async def get_rag_result_preview(mongo_id: str):
    """
    获取RAG结果的完整详情

    **功能**: 🆕 新增

    **用途**:
    - RAG只返回preview摘要，前端需要查看完整内容
    - 用户在编辑前预览原始数据

    Args:
        mongo_id (str): news_results表的_id (RAG返回的mongo_id)

    Returns:
        完整的news_results记录

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/rag-preview/249832360786370562"
        ```
    """
    try:
        from src.infrastructure.database.connection import get_mongodb_database

        db = await get_mongodb_database()
        result = await db["news_results"].find_one({"_id": mongo_id})

        if not result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "结果不存在",
                    "message": f"未找到news_results记录: mongo_id={mongo_id}"
                }
            )

        # 将MongoDB ObjectId转换为字符串
        result["_id"] = str(result["_id"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取RAG结果预览失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取预览失败，请稍后重试"
            }
        )
```

---

## 前端集成指南

### 前端工作流

```typescript
// 1. RAG查询
const ragQuery = async (question: string) => {
  const eventSource = new EventSource(
    `/api/v1/nl-search/rag-query?question=${encodeURIComponent(question)}`
  );

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "sources") {
      // 显示RAG返回的结果列表
      displayResults(data.data);  // data是数组，包含多个结果
    }
  };
};

// 2. 批量编辑
const batchEdit = async (edits: Array<{mongo_id: string, fields: any}>) => {
  const response = await fetch('/api/v1/user-edits/batch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      updates: edits.map(edit => ({
        record_id: edit.mongo_id,  // 使用RAG返回的mongo_id
        fields: edit.fields
      }))
    })
  });

  return response.json();
};

// 3. 创建档案
const createArchive = async (items: Array<{mongo_id: string}>) => {
  const response = await fetch('/api/v1/nl-search/archives', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: currentUserId,
      archive_name: "西藏相关新闻汇总",
      items: items.map(item => ({
        news_result_id: item.mongo_id,  // 使用RAG返回的mongo_id
        // edited_title/edited_summary 会自动从user_edited_results读取
      }))
    })
  });

  return response.json();
};
```

---

## 数据库集合关系 (更新)

```
┌────────────────────┐
│  nl_search_logs    │  ← NL Search元数据
└────────────────────┘
         │
         │ 关联
         ↓
┌────────────────────┐
│   news_results     │  ← 搜索结果入库 (mongo_id = _id)
└────────────────────┘      ↑
         │                  │
         │ RAG向量检索      │
         ↓                  │
┌────────────────────┐      │
│   RAG 向量数据库   │      │ 快照来源
│  (192.168.0.5)    │      │
└────────────────────┘      │
         │                  │
         │ 返回mongo_id     │
         ↓                  │
   (前端使用mongo_id)       │
         │                  │
         │ 批量编辑         │
         ↓                  │
┌────────────────────┐      │
│user_edited_results │  ← 编辑记录 (通过mongo_id关联)
└────────────────────┘      │
         │                  │
         │ 创建档案时自动合并│
         ↓                  ↓
┌────────────────────────────────────┐
│  user_archives                     │  ← 档案
│  ├─ snapshot (从news_results提取)  │
│  ├─ edited_* (从user_edited_results合并) │
│  └─ user_notes, user_rating        │
└────────────────────────────────────┘
```

---

## 实施计划

### Phase 1: 核心功能 (1-2天)

**优先级**: 🔴 P0

1. ✅ **新增RAG代理API** (`POST /nl-search/rag-query`)
   - 流式SSE代理
   - 错误处理
   - 日志记录

2. ✅ **档案创建增强** (自动合并编辑内容)
   - 修改 `mongo_archive_service.create_archive()`
   - 从 `user_edited_results` 读取编辑记录
   - 优先使用已保存的编辑内容

3. ✅ **文档更新**
   - 批量编辑API文档标注支持RAG场景
   - 更新API使用示例

### Phase 2: 辅助功能 (0.5-1天)

**优先级**: 🟡 P1

1. ✅ **RAG结果预览API** (`GET /nl-search/rag-preview/{mongo_id}`)
   - 查询完整 news_results 数据
   - 前端预览支持

### Phase 3: 前端集成 (由前端团队负责)

**优先级**: 🟢 P2

1. RAG查询界面开发
2. 批量编辑UI集成
3. 档案创建流程优化

---

## 测试场景

### 场景 1: RAG查询 → 批量编辑 → 创建档案

```bash
# 1. RAG查询
curl -N -X POST "http://localhost:8000/api/v1/nl-search/rag-query" \
  -H "Content-Type: application/json" \
  -d '{"question": "请介绍关于西藏的新闻"}'

# 响应 (SSE):
# data: {"type": "sources", "data": [
#   {"mongo_id": "249832360786370562", "title": "...", ...}
# ]}

# 2. 批量编辑
curl -X POST "http://localhost:8000/api/v1/user-edits/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "updates": [
      {
        "record_id": "249832360786370562",
        "fields": {
          "title": "编辑后的标题",
          "summary": "编辑后的摘要"
        }
      }
    ]
  }'

# 3. 创建档案 (自动合并编辑内容)
curl -X POST "http://localhost:8000/api/v1/nl-search/archives" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1001,
    "archive_name": "西藏新闻汇总",
    "items": [
      {
        "news_result_id": "249832360786370562"
        // 不需要提供edited_title/edited_summary
        // 系统会自动从user_edited_results读取
      }
    ]
  }'
```

### 场景 2: RAG查询 → 直接创建档案 (无编辑)

```bash
# 1. RAG查询 (同上)

# 2. 直接创建档案 (跳过编辑步骤)
curl -X POST "http://localhost:8000/api/v1/nl-search/archives" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1001,
    "archive_name": "西藏新闻快速汇总",
    "items": [
      {
        "news_result_id": "249832360786370562",
        "user_notes": "重要参考",
        "user_rating": 4
      }
    ]
  }'
```

---

## 关键代码位置

| 功能 | 文件 | 行号 | 说明 |
|------|------|------|------|
| 🆕 RAG代理API | `src/api/v1/endpoints/nl_search.py` | 新增 | SSE流式代理 |
| 🔧 档案创建增强 | `src/services/nl_search/mongo_archive_service.py` | 60-158 | 合并编辑内容 |
| 批量编辑API | `src/api/v1/endpoints/user_edits.py` | 184-453 | 已支持mongo_id |
| 🆕 RAG预览API | `src/api/v1/endpoints/nl_search.py` | 新增 | 完整数据查询 |

---

## 常见问题

### Q1: RAG返回的 `id` 和 `mongo_id` 有什么区别？

**A**:
- `id`: RAG向量数据库内部ID (UUID格式)，仅用于RAG系统内部
- `mongo_id`: MongoDB `news_results` 表的 `_id` 字段，**这是关联所有系统的关键**

**使用规则**:
- 批量编辑API: 使用 `mongo_id` 作为 `record_id`
- 档案创建API: 使用 `mongo_id` 作为 `news_result_id`
- RAG预览API: 使用 `mongo_id` 查询完整数据

### Q2: 如果用户先批量编辑，然后创建档案时又提供了新的编辑内容，优先使用哪个？

**A**: **优先使用API请求中提供的编辑内容**

```python
# 合并逻辑伪代码:
if request.edited_title:
    use request.edited_title  # 优先使用请求中的内容
elif user_edited_results.edited_title:
    use user_edited_results.edited_title  # 其次使用已保存的编辑
else:
    use news_results.title  # 最后使用原始标题
```

### Q3: RAG系统和NL Search有什么区别？

**A**:

| 特性 | NL Search | RAG系统 |
|------|-----------|---------|
| 用途 | 搜索外部网页 → 入库 | 检索已入库数据 |
| 数据源 | GPT-5 Search API + 爬虫 | news_results 表 + 向量数据库 |
| 检索方式 | 关键词搜索 | 向量相似度检索 |
| 返回内容 | 新数据 | 已入库数据 |
| 典型场景 | 获取最新外部信息 | 从历史数据中查找相关内容 |

**工作流**:
1. **NL Search**: "最新AI技术" → 搜索互联网 → 入库到 news_results
2. **RAG**: "AI技术相关内容" → 从 news_results 检索 → 返回历史记录

---

**文档维护**: Claude Code - Backend & Architect Personas
**审查状态**: 待用户审查
**实施优先级**: P0 (核心功能) → P1 (辅助功能) → P2 (前端集成)
