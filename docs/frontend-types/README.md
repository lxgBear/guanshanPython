# Chat Sync API - 前端类型定义

为前端开发提供的完整 TypeScript 类型定义和集成指南。

---

## 📁 文件清单

### 核心类型定义

| 文件 | 说明 | 推荐用途 |
|------|------|---------|
| **`chat-sync-api.types.ts`** | 完整类型定义（含注释和示例） | ⭐ 生产环境推荐 |
| **`chat-sync-api.simple.ts`** | 简化类型定义 | 快速原型开发 |
| **`chat-sync-api.schema.json`** | JSON Schema | 验证、文档生成 |

### 文档

| 文件 | 说明 |
|------|------|
| **`INTEGRATION_GUIDE.md`** | 详细集成指南（含 React/Vue 示例） |
| **`QUICK_REFERENCE.md`** | 快速参考卡片 |
| **`README.md`** | 本文档 |

---

## 🚀 快速开始

### 1. 复制类型定义到你的项目

**推荐方式**（完整版）:
```bash
cp docs/frontend-types/chat-sync-api.types.ts src/types/
```

**或者**（简化版）:
```bash
cp docs/frontend-types/chat-sync-api.simple.ts src/types/chat-sync-api.ts
```

### 2. 在项目中导入

```typescript
import type {
  ChatSyncRequest,
  ChatSyncResponse,
  SourceDetail
} from '@/types/chat-sync-api.types';
```

### 3. 使用类型

```typescript
const request: ChatSyncRequest = {
  question: "你的问题"
};

const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request),
});

const data: ChatSyncResponse = await response.json();
```

---

## 📋 核心类型概览

### ChatSyncRequest（请求）

```typescript
interface ChatSyncRequest {
  question: string;           // 必填：用户问题
  user_id?: string;           // 可选：用户ID
  search_mode?: 'single' | 'multi';  // 可选：搜索模式
}
```

### ChatSyncResponse（响应）

```typescript
interface ChatSyncResponse {
  question: string;           // 用户问题
  answer: string;            // 完整答案
  sources: SourceDetail[];   // 数据来源列表
  sources_count: number;     // 来源数量
  answer_length: number;     // 答案长度
  status: string;            // 状态
}
```

### SourceDetail（来源详情）

```typescript
interface SourceDetail {
  id: string;                // UUID
  mongo_id: string;          // MongoDB ID
  title: string;             // 标题
  source: string;            // 来源网站
  score: number;             // 相关性评分 (0-1)
  category: Category;        // 分类信息
  publish_time: string;      // 发布时间
  preview: string;           // 内容预览

  // ⭐ 增强字段（v2.0 新增）
  url?: string | null;              // 完整URL
  markdown_content?: string | null;  // Markdown内容
  content_length?: number | null;    // 内容长度
}
```

---

## 💡 使用示例

### React

```typescript
import { useState } from 'react';
import type { ChatSyncResponse } from '@/types/chat-sync-api.types';

function ChatComponent() {
  const [data, setData] = useState<ChatSyncResponse | null>(null);

  const fetchChat = async (question: string) => {
    const res = await fetch('http://localhost:8000/api/v1/chat/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data: ChatSyncResponse = await res.json();
    setData(data);
  };

  return (
    <div>
      {data && (
        <>
          <h2>{data.question}</h2>
          <p>{data.answer}</p>
          <ul>
            {data.sources.map(source => (
              <li key={source.id}>
                <a href={source.url || '#'}>{source.title}</a>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
```

### Vue 3

```typescript
import { ref } from 'vue';
import type { ChatSyncResponse } from '@/types/chat-sync-api.types';

const data = ref<ChatSyncResponse | null>(null);

async function fetchChat(question: string) {
  const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  data.value = await response.json();
}
```

---

## 🔧 工具集成

### JSON Schema 验证

```bash
npm install ajv
```

```typescript
import Ajv from 'ajv';
import schema from './chat-sync-api.schema.json';

const ajv = new Ajv();
const validate = ajv.compile(schema);

const valid = validate(responseData);
if (!valid) {
  console.error(validate.errors);
}
```

### 从 JSON Schema 生成 TypeScript

```bash
npm install json-schema-to-typescript -D

json2ts -i chat-sync-api.schema.json -o chat-sync-api.generated.ts
```

---

## 📚 相关文档

### 完整文档
- **[API 完整文档](../CHAT_SYNC_ENDPOINT_API.md)** - 详细的 API 规格说明
- **[实施总结](../CHAT_SYNC_IMPLEMENTATION_SUMMARY.md)** - 后端实现细节

### 前端集成
- **[集成指南](./INTEGRATION_GUIDE.md)** - 详细的集成步骤和示例
- **[快速参考](./QUICK_REFERENCE.md)** - 速查卡片

### 数据分析
- **[数据结构分析](../../data/chat/chat_api_analysis_20251124_143546.md)** - 原始数据分析

---

## 🎯 API 端点信息

### 开发环境
```
POST http://localhost:8000/api/v1/chat/sync
```

### 生产环境
```
POST https://api.yourdomain.com/api/v1/chat/sync
```

### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/chat/sync' \
  -H 'Content-Type: application/json' \
  -d '{"question": "请介绍关于西藏的新闻"}'
```

---

## ⚡ 性能数据

| 指标 | 数值 |
|------|------|
| 端到端延迟 | ~1-2秒 |
| 响应大小 | ~27KB |
| 来源数量 | 3-5个 |
| 答案长度 | 200-500字符 |

---

## 🔍 关键字段说明

### 增强字段（v2.0 新增）

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `url` | `string \| null` | MongoDB | 完整URL，可能为 null |
| `markdown_content` | `string \| null` | MongoDB | Markdown格式完整内容 |
| `content_length` | `number \| null` | 计算 | 内容字符数 |

### 核心字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `answer` | `string` | Chat API | 完整答案文本 |
| `sources` | `SourceDetail[]` | Chat API + MongoDB | 数据来源列表 |
| `score` | `number` | Chat API | 相关性评分 (0-1) |

---

## 🛠️ 开发建议

### TypeScript 配置

确保 `tsconfig.json` 包含:

```json
{
  "compilerOptions": {
    "strict": true,
    "strictNullChecks": true
  }
}
```

### 代码风格

```typescript
// ✅ 推荐：使用类型断言
const data = await response.json() as ChatSyncResponse;

// ✅ 推荐：类型守卫
function isChatSyncResponse(data: any): data is ChatSyncResponse {
  return data && typeof data.question === 'string' && Array.isArray(data.sources);
}

// ❌ 避免：any 类型
const data: any = await response.json();
```

---

## 📦 NPM 包（可选）

如果你想发布为 NPM 包：

```json
{
  "name": "@yourorg/chat-sync-api-types",
  "version": "2.0.0",
  "main": "chat-sync-api.types.ts",
  "types": "chat-sync-api.types.ts",
  "files": [
    "chat-sync-api.types.ts",
    "chat-sync-api.simple.ts",
    "chat-sync-api.schema.json"
  ]
}
```

---

## 🤝 贡献

如有问题或建议，请联系后端团队或提交 Issue。

---

## 📄 许可证

内部使用

---

**版本**: v2.0.0
**更新日期**: 2025-11-24
**维护者**: Backend Team
