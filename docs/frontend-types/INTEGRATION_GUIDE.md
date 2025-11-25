# Chat Sync API 前端集成指南

## 快速开始

### 1. 复制类型定义文件

选择一个版本复制到你的项目：

**完整版**（推荐）:
```bash
cp docs/frontend-types/chat-sync-api.types.ts src/types/
```

**简化版**:
```bash
cp docs/frontend-types/chat-sync-api.simple.ts src/types/
```

---

## TypeScript 类型定义

### 核心类型

```typescript
// 请求类型
interface ChatSyncRequest {
  question: string;           // 必填：用户问题
  user_id?: string;           // 可选：用户ID
  search_mode?: 'single' | 'multi';  // 可选：搜索模式
}

// 响应类型
interface ChatSyncResponse {
  question: string;           // 用户问题
  answer: string;            // 完整答案
  sources: SourceDetail[];   // 数据来源列表
  sources_count: number;     // 来源数量
  answer_length: number;     // 答案长度
  status: string;            // 状态
}

// 来源详情
interface SourceDetail {
  id: string;                // UUID
  mongo_id: string;          // MongoDB ID
  title: string;             // 标题
  source: string;            // 来源网站
  score: number;             // 相关性评分 (0-1)
  category: Category;        // 分类信息
  publish_time: string;      // 发布时间
  preview: string;           // 内容预览
  url?: string | null;       // 完整URL
  markdown_content?: string | null;  // 完整Markdown内容
  content_length?: number | null;    // 内容长度
}

// 分类信息
interface Category {
  大类: string;
  类别: string;
  地域: string;
}
```

---

## 集成示例

### React + TypeScript

```typescript
import { useState } from 'react';
import type { ChatSyncRequest, ChatSyncResponse } from '@/types/chat-sync-api.types';

function ChatComponent() {
  const [response, setResponse] = useState<ChatSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (question: string) => {
    setLoading(true);
    setError(null);

    try {
      const request: ChatSyncRequest = { question };

      const res = await fetch('http://localhost:8000/api/v1/chat/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!res.ok) {
        throw new Error('请求失败');
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
      {error && <div>错误: {error}</div>}

      {response && (
        <div>
          <h2>{response.question}</h2>
          <p>{response.answer}</p>

          <h3>数据来源 ({response.sources_count})</h3>
          {response.sources.map(source => (
            <div key={source.id}>
              <h4>
                {source.url ? (
                  <a href={source.url} target="_blank" rel="noopener">
                    {source.title}
                  </a>
                ) : (
                  source.title
                )}
              </h4>
              <p>相关性: {(source.score * 100).toFixed(1)}%</p>
              <p>{source.preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### Vue 3 Composition API

```typescript
import { ref, Ref } from 'vue';
import type { ChatSyncRequest, ChatSyncResponse } from '@/types/chat-sync-api.types';

export function useChatSync() {
  const data: Ref<ChatSyncResponse | null> = ref(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchChat = async (question: string) => {
    loading.value = true;
    error.value = null;

    try {
      const request: ChatSyncRequest = { question };

      const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      data.value = await response.json();
    } catch (err: any) {
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  };

  return { data, loading, error, fetchChat };
}
```

### Axios 封装

```typescript
import axios, { AxiosError } from 'axios';
import type {
  ChatSyncRequest,
  ChatSyncResponse,
  ChatSyncErrorResponse
} from '@/types/chat-sync-api.types';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60秒超时
});

export async function chatSync(request: ChatSyncRequest): Promise<ChatSyncResponse> {
  try {
    const response = await api.post<ChatSyncResponse>('/chat/sync', request);
    return response.data;
  } catch (error) {
    const axiosError = error as AxiosError<ChatSyncErrorResponse>;

    if (axiosError.response) {
      // 服务器返回错误
      throw axiosError.response.data;
    } else if (axiosError.request) {
      // 请求发送但无响应
      throw { error: 'Network Error', message: '网络连接失败' };
    } else {
      // 请求配置错误
      throw { error: 'Request Error', message: axiosError.message };
    }
  }
}

// 使用示例
async function example() {
  try {
    const response = await chatSync({ question: '请介绍关于西藏的新闻' });
    console.log('答案:', response.answer);
    console.log('来源数量:', response.sources_count);
  } catch (error) {
    const chatError = error as ChatSyncErrorResponse;
    console.error('错误:', chatError.message);
  }
}
```

---

## 完整示例：React + Markdown 渲染

```typescript
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatSyncResponse, SourceDetail } from '@/types/chat-sync-api.types';

function ChatApp() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<ChatSyncResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedSource, setSelectedSource] = useState<SourceDetail | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/v1/chat/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      const data: ChatSyncResponse = await res.json();
      setResponse(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-app">
      {/* 搜索表单 */}
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="输入你的问题..."
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? '搜索中...' : '搜索'}
        </button>
      </form>

      {/* 答案显示 */}
      {response && (
        <div className="response">
          <div className="answer-section">
            <h2>答案</h2>
            <ReactMarkdown>{response.answer}</ReactMarkdown>
          </div>

          {/* 来源列表 */}
          <div className="sources-section">
            <h3>数据来源 ({response.sources_count})</h3>
            <div className="sources-grid">
              {response.sources.map((source) => (
                <div
                  key={source.id}
                  className="source-card"
                  onClick={() => setSelectedSource(source)}
                >
                  <h4>{source.title}</h4>
                  <p className="source-meta">
                    {source.source} | 相关性: {(source.score * 100).toFixed(1)}%
                  </p>
                  <p className="source-preview">{source.preview}</p>
                  <div className="source-category">
                    {source.category.大类} → {source.category.类别} ({source.category.地域})
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 来源详情模态框 */}
      {selectedSource && (
        <div className="modal" onClick={() => setSelectedSource(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setSelectedSource(null)}>关闭</button>

            <h2>{selectedSource.title}</h2>

            {selectedSource.url && (
              <a href={selectedSource.url} target="_blank" rel="noopener noreferrer">
                查看原文 →
              </a>
            )}

            {selectedSource.markdown_content && (
              <div className="markdown-content">
                <ReactMarkdown>{selectedSource.markdown_content}</ReactMarkdown>
              </div>
            )}

            <div className="source-info">
              <p>来源: {selectedSource.source}</p>
              <p>发布时间: {selectedSource.publish_time}</p>
              <p>内容长度: {selectedSource.content_length} 字符</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatApp;
```

---

## API 端点配置

### 开发环境

```typescript
// config/api.ts
export const API_BASE_URL = 'http://localhost:8000/api/v1';
export const CHAT_SYNC_ENDPOINT = `${API_BASE_URL}/chat/sync`;
```

### 生产环境

```typescript
// config/api.ts
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.yourdomain.com/api/v1';
export const CHAT_SYNC_ENDPOINT = `${API_BASE_URL}/chat/sync`;
```

---

## 错误处理

### 标准错误处理

```typescript
import type { ChatSyncErrorResponse } from '@/types/chat-sync-api.types';

async function handleChatSync(question: string) {
  try {
    const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      const error: ChatSyncErrorResponse = await response.json();

      switch (response.status) {
        case 502:
          console.error('外部 API 调用失败:', error.message);
          break;
        case 500:
          console.error('服务器内部错误:', error.message);
          break;
        default:
          console.error('未知错误:', error);
      }

      return null;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('网络错误:', error);
    return null;
  }
}
```

---

## 性能优化建议

### 1. 请求去重

```typescript
const requestCache = new Map<string, Promise<ChatSyncResponse>>();

async function cachedChatSync(question: string): Promise<ChatSyncResponse> {
  if (requestCache.has(question)) {
    return requestCache.get(question)!;
  }

  const promise = fetch('http://localhost:8000/api/v1/chat/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  }).then(res => res.json());

  requestCache.set(question, promise);

  // 5分钟后清除缓存
  setTimeout(() => requestCache.delete(question), 5 * 60 * 1000);

  return promise;
}
```

### 2. 防抖处理

```typescript
import { debounce } from 'lodash';

const debouncedSearch = debounce(async (question: string) => {
  const response = await chatSync({ question });
  // 处理响应
}, 500);
```

---

## 测试

### Jest 单元测试

```typescript
import { chatSync } from '@/api/chat';
import type { ChatSyncResponse } from '@/types/chat-sync-api.types';

describe('Chat Sync API', () => {
  it('should return valid response', async () => {
    const response: ChatSyncResponse = await chatSync({
      question: '测试问题',
    });

    expect(response).toBeDefined();
    expect(response.question).toBe('测试问题');
    expect(response.answer).toBeDefined();
    expect(response.sources).toBeInstanceOf(Array);
    expect(response.sources_count).toBeGreaterThan(0);
  });
});
```

---

## 相关文档

- [完整 API 文档](../CHAT_SYNC_ENDPOINT_API.md)
- [实施总结](../CHAT_SYNC_IMPLEMENTATION_SUMMARY.md)
- [类型定义文件](./chat-sync-api.types.ts)

---

**更新日期**: 2025-11-24
