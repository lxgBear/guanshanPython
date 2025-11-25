# RAG 结果字段获取 API 设计

**文档版本**: v1.0.0
**创建日期**: 2025-11-22
**需求**: 前端根据RAG返回的 `mongo_id` 获取 `news_results` 表中的 `markdown_content` 和 `url` 字段

---

## 需求分析

### 背景

RAG系统返回的数据包含：
- `mongo_id`: news_results 表的 `_id`
- `preview`: 简短的内容预览

**前端需求**:
- 用户点击RAG结果时，需要查看完整的 `markdown_content`（格式化的文章内容）
- 需要 `url` 字段用于跳转到原始网页

### news_results 集合字段结构

```javascript
{
  "_id": "249832360786370562",  // mongo_id
  "title": "新闻标题",
  "url": "https://example.com/article",  // ✅ 前端需要
  "content": "原始HTML或文本内容",
  "markdown_content": "# 格式化的Markdown内容...",  // ✅ 前端需要
  "snippet": "摘要",
  "category": {...},
  "source": "来源",
  "search_log_id": "...",
  // ... 其他字段
}
```

---

## 解决方案

### 方案 A: 专用字段获取API (推荐 ⭐)

**优点**:
- ✅ 性能最优（只返回需要的字段）
- ✅ 语义清晰（专门用于获取内容和URL）
- ✅ 易于扩展（未来可以添加其他字段）

**缺点**:
- 需要新增API端点

### 方案 B: 使用现有预览API + 字段参数

**优点**:
- ✅ 复用现有API
- ✅ 灵活（可以指定任意字段）

**缺点**:
- 需要修改现有API
- 可能返回不必要的数据

### 方案 C: 前端直接从完整数据中提取

**优点**:
- ✅ 无需新增API

**缺点**:
- ❌ 性能差（返回整个文档）
- ❌ 浪费带宽

---

## 推荐实现: 方案 A

### API 设计

**端点**: `GET /api/v1/nl-search/rag-content/{mongo_id}`

**功能**: 根据 `mongo_id` 返回 `markdown_content` 和 `url` 字段

**请求示例**:
```bash
curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/249832360786370562"
```

**响应格式**:
```json
{
  "mongo_id": "249832360786370562",
  "url": "https://chineseyouthstandfortibet.substack.com/...",
  "markdown_content": "# 本会编辑留学生张雅笛回国探亲遭"文字狱"！\n\n计划赴英国伦敦求学的一名留学生...",
  "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",  // 额外返回标题，方便前端显示
  "source": "chineseyouthstandfortibet.substack.com"  // 额外返回来源
}
```

---

## 实现代码

### 1. Pydantic 数据模型

```python
# src/api/v1/endpoints/nl_search.py

class RAGContentResponse(BaseModel):
    """RAG内容详情响应"""
    mongo_id: str = Field(..., description="MongoDB news_results表的_id")
    url: str = Field(..., description="原始网页URL")
    markdown_content: Optional[str] = Field(None, description="Markdown格式内容")
    title: str = Field(..., description="新闻标题")
    source: str = Field(..., description="来源网站")

    class Config:
        json_schema_extra = {
            "example": {
                "mongo_id": "249832360786370562",
                "url": "https://chineseyouthstandfortibet.substack.com/p/abc",
                "markdown_content": "# 标题\n\n正文内容...",
                "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",
                "source": "chineseyouthstandfortibet.substack.com"
            }
        }
```

### 2. API 端点实现

```python
# src/api/v1/endpoints/nl_search.py

@router.get(
    "/rag-content/{mongo_id}",
    response_model=RAGContentResponse,
    summary="获取RAG结果的内容和URL",
    description="根据RAG返回的mongo_id获取news_results表中的markdown_content和url字段"
)
async def get_rag_content(mongo_id: str):
    """
    获取RAG结果的内容和URL

    **功能**: 🆕 新增

    **用途**:
    - 前端点击RAG结果时，获取完整的markdown内容用于展示
    - 获取原始URL用于跳转到来源网页

    **性能优化**:
    - 仅返回需要的字段（markdown_content, url, title, source）
    - 不返回完整的news_results文档

    Args:
        mongo_id (str): news_results表的_id (RAG返回的mongo_id)

    Returns:
        RAGContentResponse: 包含markdown_content和url的响应

    Raises:
        HTTPException:
            - 404: mongo_id对应的记录不存在
            - 500: 数据库查询失败

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/249832360786370562"
        ```
    """
    try:
        logger.info(f"获取RAG内容: mongo_id={mongo_id}")

        from src.infrastructure.database.connection import get_mongodb_database

        db = await get_mongodb_database()

        # 性能优化: 只查询需要的字段
        result = await db["news_results"].find_one(
            {"_id": mongo_id},
            {
                "_id": 1,
                "url": 1,
                "markdown_content": 1,
                "title": 1,
                "source": 1
            }
        )

        if not result:
            logger.warning(f"RAG内容不存在: mongo_id={mongo_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "内容不存在",
                    "message": f"未找到对应的news_results记录: mongo_id={mongo_id}",
                    "hint": "请检查mongo_id是否正确，或该记录可能已被删除"
                }
            )

        # 构建响应
        response = RAGContentResponse(
            mongo_id=str(result["_id"]),
            url=result.get("url", ""),
            markdown_content=result.get("markdown_content"),
            title=result.get("title", ""),
            source=result.get("source", "")
        )

        logger.info(
            f"RAG内容获取成功: mongo_id={mongo_id}, "
            f"has_markdown={bool(response.markdown_content)}, "
            f"url_length={len(response.url)}"
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"获取RAG内容失败: mongo_id={mongo_id}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "服务错误",
                "message": "获取内容失败，请稍后重试",
                "mongo_id": mongo_id
            }
        )
```

---

## 性能优化说明

### MongoDB 字段投影 (Projection)

```python
# ✅ 优化后: 只查询需要的字段
result = await db["news_results"].find_one(
    {"_id": mongo_id},
    {
        "_id": 1,
        "url": 1,
        "markdown_content": 1,
        "title": 1,
        "source": 1
    }
)

# ❌ 未优化: 查询整个文档
result = await db["news_results"].find_one({"_id": mongo_id})
```

**性能提升**:
- 减少网络传输数据量（假设完整文档 50KB，优化后仅 5KB）
- 减少MongoDB查询时间（索引覆盖查询）
- 减少Python序列化开销

### 预期性能指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 响应大小 | ~50KB | ~5KB | ✅ 90% |
| 查询时间 | 10-20ms | 5-10ms | ✅ 50% |
| 带宽消耗 | 高 | 低 | ✅ 90% |

---

## 前端使用示例

### TypeScript 接口定义

```typescript
interface RAGContentResponse {
  mongo_id: string;
  url: string;
  markdown_content: string | null;
  title: string;
  source: string;
}
```

### 使用示例

```typescript
// 1. RAG查询获取结果列表
const ragResults = await fetchRAGResults("请介绍关于西藏的新闻");

// ragResults.data = [
//   {
//     mongo_id: "249832360786370562",
//     title: "...",
//     preview: "简短预览..."
//   }
// ]

// 2. 用户点击某个结果，获取完整内容
const handleResultClick = async (mongo_id: string) => {
  try {
    const response = await fetch(
      `/api/v1/nl-search/rag-content/${mongo_id}`
    );

    const content: RAGContentResponse = await response.json();

    // 3. 展示Markdown内容
    if (content.markdown_content) {
      renderMarkdown(content.markdown_content);
    }

    // 4. 提供原始链接
    displaySourceLink(content.url, content.source);

  } catch (error) {
    console.error("获取内容失败:", error);
  }
};
```

### React 组件示例

```tsx
import ReactMarkdown from 'react-markdown';

interface RAGResultViewerProps {
  mongo_id: string;
}

const RAGResultViewer: React.FC<RAGResultViewerProps> = ({ mongo_id }) => {
  const [content, setContent] = useState<RAGContentResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const response = await fetch(
          `/api/v1/nl-search/rag-content/${mongo_id}`
        );
        const data = await response.json();
        setContent(data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [mongo_id]);

  if (loading) return <div>加载中...</div>;
  if (!content) return <div>内容不存在</div>;

  return (
    <div className="rag-result-viewer">
      <h1>{content.title}</h1>

      <div className="source-info">
        <a href={content.url} target="_blank" rel="noopener noreferrer">
          📄 查看原文: {content.source}
        </a>
      </div>

      <div className="markdown-content">
        {content.markdown_content ? (
          <ReactMarkdown>{content.markdown_content}</ReactMarkdown>
        ) : (
          <p>暂无Markdown内容</p>
        )}
      </div>
    </div>
  );
};
```

---

## 错误处理

### 场景 1: mongo_id 不存在

**请求**:
```bash
GET /api/v1/nl-search/rag-content/invalid_id
```

**响应** (404):
```json
{
  "error": "内容不存在",
  "message": "未找到对应的news_results记录: mongo_id=invalid_id",
  "hint": "请检查mongo_id是否正确，或该记录可能已被删除"
}
```

### 场景 2: markdown_content 字段为空

**响应** (200):
```json
{
  "mongo_id": "249832360786370562",
  "url": "https://example.com/article",
  "markdown_content": null,  // 字段存在但为空
  "title": "新闻标题",
  "source": "example.com"
}
```

**前端处理**:
```typescript
if (content.markdown_content) {
  renderMarkdown(content.markdown_content);
} else {
  // 显示提示: "暂无格式化内容，请查看原文"
  showFallbackMessage();
}
```

---

## 与现有API的对比

| API | 用途 | 返回字段 | 性能 |
|-----|------|----------|------|
| **GET /rag-content/{mongo_id}** (新增) | 获取内容和URL | markdown_content, url, title, source | ⭐⭐⭐⭐⭐ 最优 |
| **GET /rag-preview/{mongo_id}** (之前设计) | 获取完整记录 | 所有字段 | ⭐⭐⭐ 中等 |
| **GET /{log_id}/results** | 获取搜索结果列表 | 结果列表 | ⭐⭐⭐⭐ 良好 |

**推荐策略**:
- **点击RAG结果查看详情**: 使用 `GET /rag-content/{mongo_id}` (性能最优)
- **需要完整数据**: 使用 `GET /rag-preview/{mongo_id}` (返回所有字段)

---

## 测试用例

### 测试 1: 正常获取内容

```bash
# 请求
curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/249832360786370562"

# 期望响应 (200)
{
  "mongo_id": "249832360786370562",
  "url": "https://chineseyouthstandfortibet.substack.com/...",
  "markdown_content": "# 标题\n\n正文...",
  "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",
  "source": "chineseyouthstandfortibet.substack.com"
}
```

### 测试 2: mongo_id 不存在

```bash
# 请求
curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/nonexistent_id"

# 期望响应 (404)
{
  "error": "内容不存在",
  "message": "未找到对应的news_results记录: mongo_id=nonexistent_id",
  "hint": "请检查mongo_id是否正确，或该记录可能已被删除"
}
```

### 测试 3: markdown_content 为空

```bash
# 请求
curl -X GET "http://localhost:8000/api/v1/nl-search/rag-content/249832360786370563"

# 期望响应 (200)
{
  "mongo_id": "249832360786370563",
  "url": "https://example.com/article",
  "markdown_content": null,  // 字段为空
  "title": "某新闻标题",
  "source": "example.com"
}
```

---

## 实施计划

### Phase 1: 核心实现 (0.5天)

**任务**:
1. ✅ 新增 `RAGContentResponse` 数据模型
2. ✅ 实现 `GET /rag-content/{mongo_id}` API端点
3. ✅ 添加字段投影优化（仅查询需要的字段）
4. ✅ 添加错误处理和日志记录

**文件修改**:
- `src/api/v1/endpoints/nl_search.py` (新增约50行代码)

### Phase 2: 测试与文档 (0.5天)

**任务**:
1. ✅ 单元测试（正常情况、错误情况）
2. ✅ 集成测试（与RAG查询流程联调）
3. ✅ API文档更新（Swagger/OpenAPI）
4. ✅ 前端使用示例文档

---

## 数据流总结

```
【RAG查询】
   前端 → POST /nl-search/rag-query
       ↓
   RAG系统返回: [{mongo_id, preview, ...}]
       ↓
   前端展示结果列表

【查看详情】
   用户点击某个结果
       ↓
   前端 → GET /nl-search/rag-content/{mongo_id}
       ↓
   后端查询 news_results (仅查询: url, markdown_content, title, source)
       ↓
   返回内容
       ↓
   前端渲染Markdown + 显示原文链接
```

---

## 关键代码位置

| 功能 | 文件 | 说明 |
|------|------|------|
| 🆕 RAG内容API | `src/api/v1/endpoints/nl_search.py` | 新增 `GET /rag-content/{mongo_id}` |
| 数据模型 | `src/api/v1/endpoints/nl_search.py` | `RAGContentResponse` |
| MongoDB查询 | `src/infrastructure/database/connection.py` | 复用现有连接 |

---

## 常见问题

### Q1: 为什么不直接在RAG返回时包含 markdown_content？

**A**:
- ❌ **性能问题**: markdown_content 可能很大（10-50KB），RAG返回的是列表（10-20条），总数据量会非常大
- ❌ **用户体验**: 用户可能只点击1-2条查看详情，不需要加载所有内容
- ✅ **按需加载**: 只在用户点击时才获取内容，节省带宽和加载时间

### Q2: 如果 markdown_content 为空怎么办？

**A**:
- API仍然返回 200，但 `markdown_content` 字段为 `null`
- 前端应该处理这种情况：
  ```typescript
  if (content.markdown_content) {
    renderMarkdown(content.markdown_content);
  } else {
    // 显示: "暂无格式化内容，查看原文" + 跳转链接
  }
  ```

### Q3: 这个API和 `/rag-preview/{mongo_id}` 有什么区别？

**A**:

| API | 返回字段 | 性能 | 用途 |
|-----|----------|------|------|
| `/rag-content/{mongo_id}` | 4个字段 | ⭐⭐⭐⭐⭐ | 前端展示内容（推荐） |
| `/rag-preview/{mongo_id}` | 所有字段 | ⭐⭐⭐ | 需要完整数据的场景 |

**推荐**: 前端优先使用 `/rag-content/` 以获得最佳性能。

---

**文档维护**: Claude Code - Backend & Architect Personas
**审查状态**: 待用户审查
**实施优先级**: P0 (前端必需)
**预计工作量**: 1天 (0.5天开发 + 0.5天测试)
