# Chat API 数据结构分析

生成时间: 2025-11-24 14:35:46

## 基本统计

- 总数据块: 105
- 答案块数量: 103
- 来源数量: 3

## TypeScript 类型定义

```typescript

// Chat API 流式响应数据类型定义

/**
 * SSE 消息基础类型
 */
interface SSEMessage<T = any> {
  type: string;
  data: T;
}

/**
 * 答案块类型
 */
interface AnswerChunk extends SSEMessage<string> {
  type: 'answer_chunk';
  data: string;  // 答案文本片段
}

/**
 * 分类信息
 */
interface Category {
  大类: string;
  类别: string;
  地域: string;
}

/**
 * 数据来源
 */
interface Source {
  id: string;              // UUID
  score: number;           // 相关性评分 (0-1)
  title: string;           // 标题
  source: string;          // 来源网站
  category: Category;      // 分类
  publish_time: string;    // 发布时间
  mongo_id: string;        // MongoDB ID
  preview: string;         // 内容预览
}

/**
 * 来源数据块
 */
interface SourcesChunk extends SSEMessage<Source[]> {
  type: 'sources';
  data: Source[];
}

/**
 * 流结束数据
 */
interface StreamEndData {
  status: 'success_from_llm' | 'success_from_cache' | string;
  [key: string]: any;
}

/**
 * 流结束块
 */
interface StreamEndChunk extends SSEMessage<StreamEndData> {
  type: 'stream_end';
  data: StreamEndData;
}

/**
 * 所有可能的消息类型
 */
type ChatStreamMessage = AnswerChunk | SourcesChunk | StreamEndChunk;

/**
 * 完整的聊天响应
 */
interface ChatResponse {
  question: string;
  timestamp: string;
  total_chunks: number;
  full_content: string;
  content_length: number;
  sources?: Source[];
  stream_status?: StreamEndData;
}

```

## 前端使用示例

```typescript

// React 组件示例

import { useState, useEffect } from 'react';

interface ChatMessage {
  content: string;
  sources: Source[];
  status: string;
}

function ChatComponent() {
  const [message, setMessage] = useState<ChatMessage>({
    content: '',
    sources: [],
    status: 'idle'
  });

  const fetchChatStream = async (question: string) => {
    const response = await fetch('http://192.168.0.5:8035/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6);
          const data = JSON.parse(jsonStr) as ChatStreamMessage;

          switch (data.type) {
            case 'answer_chunk':
              setMessage(prev => ({
                ...prev,
                content: prev.content + data.data
              }));
              break;

            case 'sources':
              setMessage(prev => ({
                ...prev,
                sources: data.data
              }));
              break;

            case 'stream_end':
              setMessage(prev => ({
                ...prev,
                status: data.data.status
              }));
              break;
          }
        }
      }
    }
  };

  return (
    <div>
      <div>{message.content}</div>
      <div>
        {message.sources.map(source => (
          <div key={source.id}>
            <a href={`/source/${source.mongo_id}`}>{source.title}</a>
          </div>
        ))}
      </div>
    </div>
  );
}

```
