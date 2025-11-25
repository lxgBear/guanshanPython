# Chat Sync API 快速参考

## 基本信息

```
端点: POST /api/v1/chat/sync
Content-Type: application/json
超时: 60秒
```

---

## 请求示例

```typescript
{
  "question": "请介绍关于西藏的新闻",
  "user_id": "可选",
  "search_mode": "single"  // 或 "multi"
}
```

```bash
curl -X POST 'http://localhost:8000/api/v1/chat/sync' \
  -H 'Content-Type: application/json' \
  -d '{"question": "你的问题"}'
```

---

## 响应结构

```typescript
{
  "question": string,        // 用户问题
  "answer": string,          // 完整答案
  "sources": SourceDetail[], // 来源列表
  "sources_count": number,   // 来源数量
  "answer_length": number,   // 答案长度
  "status": string          // 状态
}
```

### SourceDetail 结构

```typescript
{
  "id": string,              // UUID
  "mongo_id": string,        // MongoDB ID
  "title": string,           // 标题
  "source": string,          // 来源网站
  "score": number,           // 相关性 (0-1)
  "category": {              // 分类
    "大类": string,
    "类别": string,
    "地域": string
  },
  "publish_time": string,    // 发布时间
  "preview": string,         // 预览
  "url": string | null,      // 完整URL ⭐
  "markdown_content": string | null,  // Markdown内容 ⭐
  "content_length": number | null     // 内容长度 ⭐
}
```

---

## TypeScript 类型（复制即用）

```typescript
export interface ChatSyncRequest {
  question: string;
  user_id?: string;
  search_mode?: 'single' | 'multi';
}

export interface ChatSyncResponse {
  question: string;
  answer: string;
  sources: SourceDetail[];
  sources_count: number;
  answer_length: number;
  status: string;
}

export interface SourceDetail {
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
  url?: string | null;
  markdown_content?: string | null;
  content_length?: number | null;
}
```

---

## React 快速集成

```typescript
const [data, setData] = useState<ChatSyncResponse | null>(null);

const fetchChat = async (question: string) => {
  const res = await fetch('http://localhost:8000/api/v1/chat/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  const data = await res.json();
  setData(data);
};
```

---

## 错误处理

| HTTP 状态码 | 错误类型 | 说明 |
|------------|---------|------|
| 502 | 外部API调用失败 | 无法连接到Chat API |
| 500 | 服务器内部错误 | 服务暂时不可用 |

```typescript
if (!response.ok) {
  const error = await response.json();
  console.error(error.message);
}
```

---

## 性能数据

- **端到端延迟**: ~1-2秒
- **响应大小**: ~27KB
- **来源数量**: 通常 3-5 个
- **答案长度**: 200-500 字符

---

## 核心字段说明

| 字段 | 说明 | 来源 |
|------|------|------|
| `url` | 完整URL | MongoDB news_results ⭐ |
| `markdown_content` | Markdown格式完整内容 | MongoDB news_results ⭐ |
| `content_length` | 内容字符数 | 计算得出 ⭐ |
| `score` | 相关性评分 (0-1) | Chat API |
| `preview` | 内容预览 | Chat API |

⭐ = 增强字段（v2.0 新增）

---

## 文件位置

```
docs/frontend-types/
├── chat-sync-api.types.ts      # 完整类型定义（推荐）
├── chat-sync-api.simple.ts     # 简化类型定义
├── INTEGRATION_GUIDE.md        # 集成指南（含示例）
└── QUICK_REFERENCE.md          # 本文档
```

---

## 示例数据

**请求**:
```json
{"question": "请介绍关于西藏的新闻"}
```

**响应**（简化）:
```json
{
  "question": "请介绍关于西藏的新闻",
  "answer": "近期关于西藏的新闻涉及到...",
  "sources": [
    {
      "id": "6e63c831-c473-4079-a18c-bcffb5ee7edb",
      "mongo_id": "249832360786370562",
      "title": "本会编辑留学生张雅笛...",
      "source": "chineseyouthstandfortibet.substack.com",
      "score": 0.126,
      "url": "https://...",
      "markdown_content": "完整内容...",
      "content_length": 5000
    }
  ],
  "sources_count": 3,
  "answer_length": 307,
  "status": "success_from_cache"
}
```

---

**版本**: v2.0.0 | **更新**: 2025-11-24
