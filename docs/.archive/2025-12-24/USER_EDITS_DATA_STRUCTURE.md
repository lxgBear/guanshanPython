# 批量编辑数据结构增强方案

**文档版本**: v1.0.0
**创建日期**: 2025-11-22
**需求**: `user_edited_results` 集合保存完整的RAG结果数据，包括 `markdown_content` 和 `url`

---

## 需求分析

### 当前问题

**现有 `user_edited_results` 结构** (简化版):
```javascript
{
  "_id": ObjectId("..."),
  "news_result_id": "249832360786370562",  // 关联 news_results
  "user_id": "user_123",
  "edited_title": "编辑后的标题",
  "edited_summary": "编辑后的摘要",
  "edited_at": ISODate("...")
}
```

**问题**:
- ❌ 缺少原始 `url`，无法直接跳转到原文
- ❌ 缺少 `markdown_content`，无法预览完整内容
- ❌ 每次查看详情都要查询 `news_results`，增加数据库负载

### 用户需求

用户在批量编辑界面需要:
1. **查看原文链接** → 需要 `url` 字段
2. **预览完整内容** → 需要 `markdown_content` 字段
3. **编辑时参考原始数据** → 需要保存原始标题、摘要等

**使用场景**:
```
用户在批量编辑界面:
1. 看到原始标题 "本会编辑留学生张雅笛回国探亲遭"文字狱"！"
2. 点击"查看原文" → 跳转到 url
3. 点击"查看详情" → 弹窗显示 markdown_content
4. 修改标题为 "留学生因支持藏人被捕"
5. 保存 → user_edited_results 同时保存原始数据和编辑数据
```

---

## 增强方案

### 方案 A: 完整快照 + 编辑 (推荐 ⭐)

**设计思路**:
- 在 `user_edited_results` 中保存一份**完整的快照**
- 快照包含所有需要的原始字段
- 编辑字段独立存储

**优点**:
- ✅ 数据完整，无需查询 `news_results`
- ✅ 即使 `news_results` 被删除，编辑记录仍可用
- ✅ 支持离线查看和编辑

**缺点**:
- 数据冗余（每条记录增加约 5-10KB）

**数据结构**:
```javascript
{
  "_id": ObjectId("..."),
  "news_result_id": "249832360786370562",  // 关联ID
  "user_id": "user_123",

  // ===== 原始数据快照 =====
  "snapshot": {
    "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",
    "url": "https://chineseyouthstandfortibet.substack.com/...",
    "markdown_content": "# 本会编辑留学生张雅笛回国探亲遭"文字狱"！\n\n计划赴英国...",
    "source": "chineseyouthstandfortibet.substack.com",
    "category": {
      "大类": "安全情报",
      "类别": "涉藏",
      "地域": "东亚"
    },
    "publish_time": "未知时间",
    "preview": "计划赴英国伦敦求学的一名留学生..."
  },

  // ===== 用户编辑 =====
  "edited_title": "留学生因支持藏人被捕",
  "edited_summary": "张雅笛原定到英国伦敦大学亚非学院读硕士...",
  "edited_category": {  // 可选，允许修改分类
    "大类": "安全情报",
    "类别": "涉藏",
    "地域": "东亚"
  },

  // ===== 元数据 =====
  "edited_at": ISODate("2025-11-22T10:00:00Z"),
  "created_at": ISODate("2025-11-22T10:00:00Z")
}
```

---

### 方案 B: 最小化 + 按需查询

**设计思路**:
- 只保存必要字段（`url`, `markdown_content`）
- 其他字段按需从 `news_results` 查询

**优点**:
- ✅ 数据量较小

**缺点**:
- ❌ 依赖 `news_results`，如果原始数据被删除则无法使用
- ❌ 需要额外查询，性能较差

**不推荐使用**

---

## 推荐方案实现

### 1. 数据结构定义

#### Pydantic 模型

```python
# src/api/v1/endpoints/user_edits.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class NewsResultSnapshot(BaseModel):
    """新闻结果快照"""
    title: str = Field(..., description="原始标题")
    url: str = Field(..., description="原始URL")
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容")
    source: str = Field(..., description="来源网站")
    category: Dict[str, str] = Field(..., description="分类信息")
    publish_time: str = Field(..., description="发布时间")
    preview: str = Field(..., description="内容预览")

class BatchEditItemRequest(BaseModel):
    """批量编辑单个条目请求"""
    record_id: str = Field(..., description="记录ID (mongo_id)")

    # 原始数据快照 (从RAG结果或news_results提取)
    snapshot: NewsResultSnapshot = Field(..., description="原始数据快照")

    # 用户编辑内容
    edited_title: Optional[str] = Field(None, description="编辑后的标题")
    edited_summary: Optional[str] = Field(None, description="编辑后的摘要")
    edited_category: Optional[Dict[str, str]] = Field(None, description="编辑后的分类")

class EnhancedBatchUpdateRequest(BaseModel):
    """增强的批量更新请求"""
    user_id: str = Field(..., description="用户ID")
    items: List[BatchEditItemRequest] = Field(..., description="编辑条目列表")

class UserEditedResultResponse(BaseModel):
    """用户编辑结果响应"""
    id: str = Field(..., description="编辑记录ID")
    news_result_id: str = Field(..., description="关联的news_result_id")

    # 原始数据
    snapshot: NewsResultSnapshot = Field(..., description="原始数据快照")

    # 编辑数据
    edited_title: Optional[str] = Field(None, description="编辑后的标题")
    edited_summary: Optional[str] = Field(None, description="编辑后的摘要")
    edited_category: Optional[Dict[str, str]] = Field(None, description="编辑后的分类")

    # 元数据
    edited_at: datetime = Field(..., description="编辑时间")
    created_at: datetime = Field(..., description="创建时间")
```

---

### 2. API 实现

#### 增强的批量编辑 API

```python
# src/api/v1/endpoints/user_edits.py

@router.post(
    "/batch-with-snapshot",
    response_model=List[UserEditedResultResponse],
    summary="批量编辑（带完整快照）",
    description="保存编辑内容的同时保存完整的原始数据快照（包括url和markdown_content）"
)
async def batch_update_with_snapshot(request: EnhancedBatchUpdateRequest):
    """
    批量编辑（增强版）

    **功能**: 🆕 新增

    **特点**:
    - 保存完整的原始数据快照（url, markdown_content, title, source, category等）
    - 保存用户的编辑内容（edited_title, edited_summary, edited_category）
    - 数据独立存储，不依赖 news_results 的存在

    **使用场景**:
    - RAG查询 → 用户批量编辑 → 保存（包含原始数据）
    - 后续创建档案时，可以直接从 user_edited_results 读取完整数据

    Args:
        request (EnhancedBatchUpdateRequest): 批量编辑请求（包含快照）

    Returns:
        List[UserEditedResultResponse]: 编辑记录列表

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/user-edits/batch-with-snapshot" \\
          -H "Content-Type: application/json" \\
          -d '{
            "user_id": "user_123",
            "items": [
              {
                "record_id": "249832360786370562",
                "snapshot": {
                  "title": "本会编辑留学生张雅笛回国探亲遭\\"文字狱\\"！",
                  "url": "https://chineseyouthstandfortibet.substack.com/...",
                  "markdown_content": "# 完整内容...",
                  "source": "chineseyouthstandfortibet.substack.com",
                  "category": {"大类": "安全情报", "类别": "涉藏", "地域": "东亚"},
                  "publish_time": "未知时间",
                  "preview": "计划赴英国..."
                },
                "edited_title": "留学生因支持藏人被捕",
                "edited_summary": "张雅笛原定到英国伦敦大学..."
              }
            ]
          }'
        ```
    """
    try:
        logger.info(
            f"批量编辑（带快照）: user_id={request.user_id}, "
            f"items_count={len(request.items)}"
        )

        from src.infrastructure.database.connection import get_mongodb_database
        db = await get_mongodb_database()

        results = []

        for item in request.items:
            # 构建编辑记录
            edit_doc = {
                "news_result_id": item.record_id,
                "user_id": request.user_id,

                # 原始数据快照
                "snapshot": item.snapshot.dict(),

                # 用户编辑
                "edited_title": item.edited_title,
                "edited_summary": item.edited_summary,
                "edited_category": item.edited_category,

                # 元数据
                "edited_at": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }

            # Upsert: 如果存在则更新，不存在则插入
            result = await db["user_edited_results"].update_one(
                {
                    "news_result_id": item.record_id,
                    "user_id": request.user_id
                },
                {"$set": edit_doc},
                upsert=True
            )

            # 读取保存的记录
            saved = await db["user_edited_results"].find_one({
                "news_result_id": item.record_id,
                "user_id": request.user_id
            })

            if saved:
                results.append(UserEditedResultResponse(
                    id=str(saved["_id"]),
                    news_result_id=saved["news_result_id"],
                    snapshot=NewsResultSnapshot(**saved["snapshot"]),
                    edited_title=saved.get("edited_title"),
                    edited_summary=saved.get("edited_summary"),
                    edited_category=saved.get("edited_category"),
                    edited_at=saved["edited_at"],
                    created_at=saved["created_at"]
                ))

        logger.info(f"批量编辑完成: 成功保存 {len(results)} 条记录")

        return results

    except Exception as e:
        logger.error(f"批量编辑失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "批量编辑失败",
                "message": str(e)
            }
        )
```

---

### 3. 前端集成

#### TypeScript 接口定义

```typescript
interface NewsResultSnapshot {
  title: string;
  url: string;
  markdown_content: string | null;
  source: string;
  category: {
    大类: string;
    类别: string;
    地域: string;
  };
  publish_time: string;
  preview: string;
}

interface BatchEditItem {
  record_id: string;  // mongo_id
  snapshot: NewsResultSnapshot;
  edited_title?: string;
  edited_summary?: string;
  edited_category?: {
    大类: string;
    类别: string;
    地域: string;
  };
}

interface EnhancedBatchUpdateRequest {
  user_id: string;
  items: BatchEditItem[];
}
```

#### 前端使用流程

```typescript
// 1. RAG查询获取结果
const ragResults = await fetchRAGResults("请介绍关于西藏的新闻");

// 2. 用户选择要编辑的结果
const selectedResults = ragResults.data.filter(item =>
  selectedIds.includes(item.mongo_id)
);

// 3. 为每个结果获取完整的 markdown_content 和 url
const enrichedResults = await Promise.all(
  selectedResults.map(async (item) => {
    const content = await fetch(
      `/api/v1/nl-search/rag-content/${item.mongo_id}`
    ).then(res => res.json());

    return {
      record_id: item.mongo_id,
      snapshot: {
        title: item.title,
        url: content.url,  // 从 rag-content API 获取
        markdown_content: content.markdown_content,  // 从 rag-content API 获取
        source: item.source,
        category: item.category,
        publish_time: item.publish_time,
        preview: item.preview
      },
      edited_title: null,  // 用户编辑后会填充
      edited_summary: null
    };
  })
);

// 4. 用户编辑标题和摘要
const handleEdit = (index: number, field: string, value: string) => {
  const updated = [...enrichedResults];
  updated[index][field] = value;
  setEnrichedResults(updated);
};

// 5. 保存批量编辑（包含完整快照）
const saveBatchEdits = async () => {
  const response = await fetch('/api/v1/user-edits/batch-with-snapshot', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      user_id: currentUserId,
      items: enrichedResults
    })
  });

  const savedRecords = await response.json();
  console.log("批量编辑保存成功:", savedRecords);
};
```

#### 批量编辑界面示例

```tsx
const BatchEditInterface: React.FC = () => {
  const [items, setItems] = useState<BatchEditItem[]>([]);

  return (
    <div className="batch-edit-container">
      {items.map((item, index) => (
        <div key={item.record_id} className="edit-item">
          <h3>条目 {index + 1}</h3>

          {/* 原始数据展示 */}
          <div className="original-data">
            <p><strong>原始标题:</strong> {item.snapshot.title}</p>
            <p><strong>来源:</strong>
              <a href={item.snapshot.url} target="_blank">
                {item.snapshot.source} 🔗
              </a>
            </p>
            <button onClick={() => showMarkdown(item.snapshot.markdown_content)}>
              查看完整内容
            </button>
          </div>

          {/* 编辑区域 */}
          <div className="edit-area">
            <input
              type="text"
              placeholder="编辑标题"
              value={item.edited_title || ''}
              onChange={(e) => handleEdit(index, 'edited_title', e.target.value)}
            />
            <textarea
              placeholder="编辑摘要"
              value={item.edited_summary || ''}
              onChange={(e) => handleEdit(index, 'edited_summary', e.target.value)}
            />
          </div>
        </div>
      ))}

      <button onClick={saveBatchEdits}>
        保存所有编辑
      </button>
    </div>
  );
};
```

---

### 4. 档案创建时的集成

#### 从 user_edited_results 读取完整数据

```python
# src/services/nl_search/mongo_archive_service.py

async def create_archive(
    user_id: int,
    archive_name: str,
    items: List[Dict[str, Any]],
    ...
) -> Dict[str, Any]:
    """创建档案（增强版）"""

    archive_items = []

    for item in items:
        news_result_id = item["news_result_id"]

        # 1️⃣ 优先从 user_edited_results 读取
        edited_record = await self.db["user_edited_results"].find_one({
            "news_result_id": news_result_id,
            "user_id": user_id
        })

        if edited_record and "snapshot" in edited_record:
            # 🆕 使用 user_edited_results 中的完整快照
            snapshot = edited_record["snapshot"]
            edited_title = edited_record.get("edited_title")
            edited_summary = edited_record.get("edited_summary")

            logger.info(
                f"从 user_edited_results 读取完整数据: "
                f"news_result_id={news_result_id}, "
                f"has_url={bool(snapshot.get('url'))}, "
                f"has_markdown={bool(snapshot.get('markdown_content'))}"
            )
        else:
            # 2️⃣ 降级: 从 news_results 创建快照
            snapshot = await self._create_snapshot(news_result_id)
            edited_title = item.get("edited_title")
            edited_summary = item.get("edited_summary")

        # 3️⃣ 构建档案条目
        archive_item = {
            "id": len(archive_items) + 1,
            "news_result_id": news_result_id,
            "snapshot": snapshot,  # 包含 url 和 markdown_content
            "edited_title": edited_title,
            "edited_summary": edited_summary,
            "user_notes": item.get("user_notes"),
            "user_rating": item.get("user_rating"),
            "created_at": datetime.utcnow()
        }

        archive_items.append(archive_item)

    # ... 保存档案逻辑
```

**优势**:
- ✅ 档案中的每个条目都包含完整的 `url` 和 `markdown_content`
- ✅ 无需再次查询 `news_results`
- ✅ 即使原始数据被删除，档案仍保留完整信息

---

## 数据流对比

### 原有流程 (缺少 url 和 markdown_content)

```
RAG查询 → 返回 preview
         ↓
批量编辑 → 只保存 edited_title, edited_summary
         ↓
创建档案 → 从 news_results 查询 (缺少 url 和 markdown_content)
         ↓
档案条目 → ❌ 没有原文链接，无法查看完整内容
```

### 新流程 (包含完整快照)

```
RAG查询 → 返回 mongo_id, preview
         ↓
获取详情 → GET /rag-content/{mongo_id}
         ↓ 返回 url, markdown_content
批量编辑 → 保存完整快照 + 编辑内容
         ↓ user_edited_results (包含 snapshot)
创建档案 → 从 user_edited_results 读取完整数据
         ↓
档案条目 → ✅ 包含 url、markdown_content、编辑内容
```

---

## MongoDB 集合结构对比

### 原有结构

```javascript
// user_edited_results (原有)
{
  "_id": ObjectId("..."),
  "news_result_id": "249832360786370562",
  "user_id": "user_123",
  "edited_title": "留学生因支持藏人被捕",
  "edited_summary": "张雅笛原定...",
  "edited_at": ISODate("...")
}
// 问题: 缺少原始数据，无法独立使用
```

### 增强结构 (推荐)

```javascript
// user_edited_results (增强版)
{
  "_id": ObjectId("..."),
  "news_result_id": "249832360786370562",
  "user_id": "user_123",

  // ✅ 新增: 完整的原始数据快照
  "snapshot": {
    "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",
    "url": "https://chineseyouthstandfortibet.substack.com/...",
    "markdown_content": "# 完整的Markdown内容...",
    "source": "chineseyouthstandfortibet.substack.com",
    "category": {"大类": "安全情报", "类别": "涉藏", "地域": "东亚"},
    "publish_time": "未知时间",
    "preview": "计划赴英国伦敦求学..."
  },

  // 用户编辑
  "edited_title": "留学生因支持藏人被捕",
  "edited_summary": "张雅笛原定到英国伦敦大学...",
  "edited_category": null,

  // 元数据
  "edited_at": ISODate("2025-11-22T10:00:00Z"),
  "created_at": ISODate("2025-11-22T10:00:00Z")
}
// 优势: 数据完整，可独立使用，包含原文链接和完整内容
```

---

## 实施计划

### Phase 1: 新增增强API (1天)

**任务**:
1. ✅ 新增 `NewsResultSnapshot` 数据模型
2. ✅ 新增 `POST /user-edits/batch-with-snapshot` API
3. ✅ 实现带快照的批量编辑逻辑
4. ✅ 添加测试用例

**文件修改**:
- `src/api/v1/endpoints/user_edits.py` (新增约 100 行)

### Phase 2: 档案创建集成 (0.5天)

**任务**:
1. ✅ 修改 `mongo_archive_service.create_archive()`
2. ✅ 优先从 `user_edited_results` 的 `snapshot` 读取
3. ✅ 降级到 `news_results` 查询
4. ✅ 测试完整流程

**文件修改**:
- `src/services/nl_search/mongo_archive_service.py` (修改约 20 行)

### Phase 3: 前端集成 (由前端团队负责)

**任务**:
1. 调用 `/rag-content/{mongo_id}` 获取 `url` 和 `markdown_content`
2. 构建完整的 `snapshot` 数据
3. 调用新的批量编辑API `/batch-with-snapshot`
4. 批量编辑界面显示原文链接和查看详情按钮

---

## API 对比

| API | 保存数据 | 优点 | 缺点 |
|-----|----------|------|------|
| **POST /user-edits/batch-with-snapshot** (新增) | snapshot + 编辑 | ✅ 数据完整 <br> ✅ 包含 url 和 markdown_content <br> ✅ 独立使用 | 数据量较大 |
| POST /user-edits/batch (现有) | 仅编辑 | ✅ 数据量小 | ❌ 缺少原始数据 <br> ❌ 依赖 news_results |

**推荐**: 使用新API `/batch-with-snapshot` 以获得最佳用户体验。

---

## 测试用例

### 测试 1: 批量编辑（带快照）

```bash
# 请求
curl -X POST "http://localhost:8000/api/v1/user-edits/batch-with-snapshot" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "items": [
      {
        "record_id": "249832360786370562",
        "snapshot": {
          "title": "本会编辑留学生张雅笛回国探亲遭\"文字狱\"！",
          "url": "https://chineseyouthstandfortibet.substack.com/p/abc",
          "markdown_content": "# 完整内容...",
          "source": "chineseyouthstandfortibet.substack.com",
          "category": {"大类": "安全情报", "类别": "涉藏", "地域": "东亚"},
          "publish_time": "未知时间",
          "preview": "计划赴英国..."
        },
        "edited_title": "留学生因支持藏人被捕",
        "edited_summary": "张雅笛原定到英国伦敦大学..."
      }
    ]
  }'

# 期望响应 (200)
[
  {
    "id": "...",
    "news_result_id": "249832360786370562",
    "snapshot": {
      "title": "本会编辑留学生张雅笛回国探亲遭\"文字狱\"！",
      "url": "https://chineseyouthstandfortibet.substack.com/p/abc",
      "markdown_content": "# 完整内容...",
      // ...
    },
    "edited_title": "留学生因支持藏人被捕",
    "edited_summary": "张雅笛原定...",
    "edited_at": "2025-11-22T10:00:00Z",
    "created_at": "2025-11-22T10:00:00Z"
  }
]
```

### 测试 2: 档案创建（使用user_edited_results的快照）

```bash
# 前提: 已有批量编辑记录（包含快照）

# 请求
curl -X POST "http://localhost:8000/api/v1/nl-search/archives" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1001,
    "archive_name": "西藏新闻汇总",
    "items": [
      {
        "news_result_id": "249832360786370562",
        "user_rating": 5
      }
    ]
  }'

# 期望:
# 1. 从 user_edited_results 读取 snapshot (包含 url 和 markdown_content)
# 2. 档案条目包含完整的原文链接和内容
```

---

## 常见问题

### Q1: 为什么要在 user_edited_results 中保存 snapshot，不是已经有 news_results 了吗？

**A**:
- **数据独立性**: `news_results` 可能被清理或删除，`user_edited_results` 需要独立存在
- **性能优化**: 避免每次查看编辑记录都要联表查询 `news_results`
- **数据完整性**: 保留编辑时的原始状态，即使 `news_results` 更新也不受影响

### Q2: snapshot 数据量会很大吗？

**A**:
- 单条记录约 **5-10KB** (包含 markdown_content)
- 如果用户编辑 100 条 = 0.5-1MB
- MongoDB 支持 16MB 单文档，完全足够

**优化建议**:
- 定期清理超过 30 天的编辑记录
- 或提供"归档到user_archives后删除编辑记录"功能

### Q3: 前端需要做什么？

**A**:
1. 在批量编辑前，调用 `/rag-content/{mongo_id}` 获取 `url` 和 `markdown_content`
2. 构建完整的 `snapshot` 对象
3. 调用新API `/batch-with-snapshot` 保存
4. UI显示原文链接和查看详情按钮

---

**文档维护**: Claude Code - Backend & Architect Personas
**审查状态**: 待用户审查
**实施优先级**: P0 (核心功能)
**预计工作量**: 1.5天 (1天后端 + 0.5天测试)
