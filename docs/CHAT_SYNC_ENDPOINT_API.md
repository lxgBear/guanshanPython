# Chat Sync API Endpoint Documentation

**端点**: `/api/v1/chat/sync`
**方法**: POST
**版本**: v2.0.0
**更新日期**: 2025-11-24

## 概述

Chat Sync API 提供同步方式调用智能问答服务，集成外部 Chat API 并自动从 MongoDB 获取完整内容。

**核心功能**:
1. 调用外部 Chat API (http://192.168.0.5:8035/chat)
2. 解析流式 SSE (Server-Sent Events) 响应
3. 提取数据来源的 mongo_id
4. 查询 MongoDB `news_results` 集合获取完整内容
5. 返回包含 URL 和 Markdown 内容的增强响应

---

## 数据流架构

```
用户请求
   ↓
[/api/v1/chat/sync]
   ↓
调用外部 Chat API (http://192.168.0.5:8035/chat)
   ↓
解析 SSE 流式响应
   ├─ answer_chunk → 拼接完整答案
   ├─ sources → 提取 mongo_id
   └─ stream_end → 记录状态
   ↓
MongoDB 查询 (news_results 集合)
   ├─ 输入: mongo_id
   └─ 输出: url, markdown_content
   ↓
返回增强响应 (含完整内容)
```

---

## API 规格

### 请求

**URL**: `POST /api/v1/chat/sync`

**Headers**:
```http
Content-Type: application/json
```

**Body**:
```json
{
  "question": "用户问题（必填，1-1000字符）",
  "user_id": "用户ID（可选）",
  "search_mode": "single"  // single | multi（可选，默认single）
}
```

**请求示例**:
```bash
curl -X POST 'http://localhost:8000/api/v1/chat/sync' \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "请介绍关于西藏的新闻"
  }'
```

---

### 响应

**成功响应** (HTTP 200):

```json
{
  "question": "请介绍关于西藏的新闻",
  "answer": "近期关于西藏的新闻涉及到...",
  "sources": [
    {
      "id": "6e63c831-c473-4079-a18c-bcffb5ee7edb",
      "mongo_id": "249832360786370562",
      "title": "本会编辑留学生张雅笛回国探亲遭"文字狱"！",
      "source": "chineseyouthstandfortibet.substack.com",
      "score": 0.126,
      "category": {
        "大类": "安全情报",
        "类别": "涉藏",
        "地域": "东亚"
      },
      "publish_time": "未知时间",
      "preview": "**本会编辑留学生张雅笛...",
      "url": "https://chineseyouthstandfortibet.substack.com/p/zhangyadi",
      "markdown_content": "[![华语青年挺藏会]...",
      "content_length": 5000
    }
  ],
  "sources_count": 3,
  "answer_length": 307,
  "status": "success_from_cache"
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `question` | string | 用户问题 |
| `answer` | string | 完整答案 |
| `sources` | array | 数据来源列表（含完整内容） |
| `sources[].id` | string | UUID |
| `sources[].mongo_id` | string | MongoDB ID |
| `sources[].title` | string | 标题 |
| `sources[].source` | string | 来源网站 |
| `sources[].score` | float | 相关性评分 (0-1) |
| `sources[].category` | object | 分类信息 |
| `sources[].publish_time` | string | 发布时间 |
| `sources[].preview` | string | 内容预览 |
| `sources[].url` | string | 完整URL（从 news_results 查询） |
| `sources[].markdown_content` | string | 完整Markdown内容（从 news_results 查询） |
| `sources[].content_length` | int | 内容长度 |
| `sources_count` | int | 来源数量 |
| `answer_length` | int | 答案长度 |
| `status` | string | 状态 (success_from_llm / success_from_cache) |

---

### 错误响应

**外部 API 调用失败** (HTTP 502):
```json
{
  "error": "外部API调用失败",
  "message": "无法连接到Chat API: ..."
}
```

**服务内部错误** (HTTP 500):
```json
{
  "error": "搜索失败",
  "message": "服务暂时不可用，请稍后重试"
}
```

---

## TypeScript 类型定义

```typescript
// 请求类型
interface ChatSyncRequest {
  question: string;
  user_id?: string;
  search_mode?: 'single' | 'multi';
}

// 分类信息
interface Category {
  大类: string;
  类别: string;
  地域: string;
}

// 来源详情（增强版，含完整内容）
interface SourceDetail {
  id: string;              // UUID
  mongo_id: string;        // MongoDB ID
  title: string;           // 标题
  source: string;          // 来源网站
  score: number;           // 相关性评分 (0-1)
  category: Category;      // 分类信息
  publish_time: string;    // 发布时间
  preview: string;         // 内容预览
  url?: string;            // 完整URL（从news_results查询）
  markdown_content?: string; // 完整Markdown内容（从news_results查询）
  content_length?: number;   // 内容长度
}

// 响应类型
interface ChatSyncResponse {
  question: string;
  answer: string;
  sources: SourceDetail[];
  sources_count: number;
  answer_length: number;
  status: string;
}
```

---

## 前端集成示例

### React + TypeScript

```typescript
import { useState } from 'react';

interface ChatSyncResponse {
  question: string;
  answer: string;
  sources: SourceDetail[];
  sources_count: number;
  answer_length: number;
  status: string;
}

interface SourceDetail {
  id: string;
  mongo_id: string;
  title: string;
  source: string;
  score: number;
  category: {
    大类: string;
    类别: string;
    地域: string;
  };
  publish_time: string;
  preview: string;
  url?: string;
  markdown_content?: string;
  content_length?: number;
}

function ChatComponent() {
  const [response, setResponse] = useState<ChatSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChat = async (question: string) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('http://localhost:8000/api/v1/chat/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.message || '请求失败');
      }

      const data: ChatSyncResponse = await res.json();
      setResponse(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {loading && <div>加载中...</div>}
      {error && <div style={{ color: 'red' }}>错误: {error}</div>}

      {response && (
        <div>
          <h2>问题: {response.question}</h2>
          <div>
            <h3>答案:</h3>
            <p>{response.answer}</p>
          </div>

          <div>
            <h3>数据来源 ({response.sources_count}):</h3>
            {response.sources.map((source) => (
              <div key={source.id} style={{ border: '1px solid #ccc', padding: '10px', margin: '10px 0' }}>
                <h4>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      {source.title}
                    </a>
                  ) : (
                    source.title
                  )}
                </h4>
                <p><strong>来源:</strong> {source.source}</p>
                <p><strong>相关性:</strong> {(source.score * 100).toFixed(1)}%</p>
                <p><strong>分类:</strong> {source.category.大类} → {source.category.类别} ({source.category.地域})</p>
                <p><strong>预览:</strong> {source.preview}</p>

                {source.markdown_content && (
                  <details>
                    <summary>查看完整内容 ({source.content_length} 字符)</summary>
                    <pre style={{ whiteSpace: 'pre-wrap' }}>{source.markdown_content.slice(0, 500)}...</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatComponent;
```

---

## 技术实现细节

### 1. 外部 API 调用

使用 `httpx.AsyncClient` 调用外部 Chat API:

```python
async with httpx.AsyncClient(proxies=proxies, timeout=60.0) as client:
    async with client.stream(
        'POST',
        'http://192.168.0.5:8035/chat',
        json={"question": request.question},
        headers={"Content-Type": "application/json"}
    ) as response:
        # 处理流式响应
        async for line in response.aiter_lines():
            # 解析 SSE 格式
            if line.startswith('data: '):
                json_text = line[6:]  # 去掉 "data: " 前缀
                chunk_data = json.loads(json_text)
```

**关键配置**:
- **代理配置**: 禁用代理以访问本地网络 (192.168.0.5)
- **超时时间**: 60秒
- **流式处理**: 使用 `stream()` 方法避免内存溢出

### 2. SSE 格式解析

外部 Chat API 返回三种消息类型:

```python
# 1. 答案块
{"type": "answer_chunk", "data": "文本片段"}

# 2. 数据来源
{"type": "sources", "data": [{...}, {...}]}

# 3. 流结束
{"type": "stream_end", "data": {"status": "success_from_cache"}}
```

### 3. MongoDB 查询优化

使用字段投影优化查询性能:

```python
news_result = await db["news_results"].find_one(
    {"_id": mongo_id},
    {"url": 1, "markdown_content": 1, "_id": 0}  # 只返回需要的字段
)
```

**查询优化**:
- 仅查询 `url` 和 `markdown_content` 字段
- 排除 `_id` 字段减少数据传输
- 支持批量查询（循环处理每个 source）

---

## 性能指标

**测试环境**: MacBook Pro, 本地 MongoDB, 外部 API 在同一局域网

**性能数据**:
- **端到端延迟**: ~1-2秒
- **外部 API 响应时间**: ~500-800ms
- **MongoDB 查询时间**: ~50-100ms (3个来源)
- **数据传输大小**: ~27KB (包含完整 Markdown 内容)

**优化建议**:
1. 实施 Redis 缓存常见问题的响应
2. 实施 MongoDB 查询结果缓存 (TTL: 1小时)
3. 使用连接池优化数据库连接
4. 考虑实施 CDN 缓存静态内容

---

## 测试验证

### 功能测试

```bash
# 1. 基本功能测试
curl -X POST 'http://localhost:8000/api/v1/chat/sync' \
  -H 'Content-Type: application/json' \
  -d '{"question": "请介绍关于西藏的新闻"}'

# 2. 保存响应到文件
curl -X POST 'http://localhost:8000/api/v1/chat/sync' \
  -H 'Content-Type: application/json' \
  -d '{"question": "请介绍关于西藏的新闻"}' \
  -o response.json

# 3. 格式化查看响应
cat response.json | python3 -m json.tool
```

### 验证清单

- [x] 外部 API 调用成功
- [x] SSE 流式响应解析正确
- [x] answer_chunks 拼接完整
- [x] sources 数据提取正确
- [x] MongoDB 查询返回 url
- [x] MongoDB 查询返回 markdown_content
- [x] 响应结构符合 Pydantic 模型
- [x] 错误处理正确（502 for API failure, 500 for internal error）
- [x] 日志记录完整

---

## 已知限制和注意事项

### 1. 网络依赖
- 依赖外部 Chat API (http://192.168.0.5:8035/chat) 可用
- 如果外部 API 不可用，返回 HTTP 502 错误

### 2. 数据可用性
- 如果 MongoDB 中不存在对应的 `mongo_id`，则该来源的 `url` 和 `markdown_content` 为 `null`
- 不会因为部分数据缺失而失败，仍返回已有数据

### 3. 性能考虑
- 每个请求会触发多次 MongoDB 查询（每个 source 一次）
- 建议实施缓存策略优化性能

### 4. 字符编码
- 所有响应使用 UTF-8 编码
- 支持中文和特殊字符

---

## 变更历史

### v2.0.0 (2025-11-24)
- **重大更新**: 完全重写端点逻辑
- 集成外部 Chat API 调用
- 添加 MongoDB 查询获取完整内容
- 响应增强：添加 `url`, `markdown_content`, `content_length` 字段
- 更新响应模型使用 Pydantic

### v1.0.0 (2025-11-22)
- 初始版本
- 调用内部 nl_search_service
- 基本搜索功能

---

## 相关文档

- [Chat API 数据结构分析](../data/chat/chat_api_analysis_20251124_143546.md)
- [NL Search Service 文档](./NL_SEARCH_SERVICE.md)
- [MongoDB Schema 文档](./MONGODB_SCHEMA.md)
- [前端集成指南](./FRONTEND_INTEGRATION.md)

---

## 支持和反馈

如有问题或建议，请联系开发团队或提交 Issue。

**文档更新日期**: 2025-11-24
**API 版本**: v2.0.0
