#!/usr/bin/env python3
"""
分析 Chat API 响应数据结构

用于前端开发参考：
- 数据结构分析
- 类型定义生成
- API 流程文档
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def analyze_chat_response(chunks_file: str):
    """
    分析 Chat API 响应数据

    Args:
        chunks_file: chunks JSON 文件路径
    """
    print("=" * 80)
    print("📊 Chat API 数据结构分析")
    print("=" * 80)

    # 读取数据
    with open(chunks_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)

    # 统计信息
    total_chunks = len(chunks)
    chunk_types = {}
    answer_chunks = []
    sources_data = None
    stream_end_data = None

    # 分析每个chunk
    for chunk in chunks:
        chunk_type = chunk.get('type', 'unknown')
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        if chunk_type == 'answer_chunk':
            answer_chunks.append(chunk.get('data', ''))
        elif chunk_type == 'sources':
            sources_data = chunk.get('data', [])
        elif chunk_type == 'stream_end':
            stream_end_data = chunk.get('data', {})

    # 打印统计
    print(f"\n📈 基本统计:")
    print(f"   总数据块: {total_chunks}")
    print(f"   数据块类型分布:")
    for ctype, count in chunk_types.items():
        print(f"      - {ctype}: {count}")

    # 分析answer_chunks
    full_answer = ''.join(answer_chunks)
    print(f"\n📝 答案内容:")
    print(f"   答案块数量: {len(answer_chunks)}")
    print(f"   完整答案长度: {len(full_answer)} 字符")
    print(f"   平均每块长度: {len(full_answer) / len(answer_chunks):.2f} 字符")
    print(f"\n   完整答案:")
    print("   " + "-" * 76)
    for line in full_answer.split('\n'):
        print(f"   {line}")
    print("   " + "-" * 76)

    # 分析sources
    if sources_data:
        print(f"\n📚 数据来源 (Sources):")
        print(f"   来源数量: {len(sources_data)}")
        for i, source in enumerate(sources_data, 1):
            print(f"\n   来源 {i}:")
            print(f"      ID: {source.get('id')}")
            print(f"      标题: {source.get('title')}")
            print(f"      来源网站: {source.get('source')}")
            print(f"      相关性评分: {source.get('score')}")
            print(f"      发布时间: {source.get('publish_time')}")
            print(f"      MongoDB ID: {source.get('mongo_id')}")
            category = source.get('category', {})
            if category:
                print(f"      分类: {category.get('大类')} > {category.get('类别')} ({category.get('地域')})")
            preview = source.get('preview', '')
            print(f"      预览: {preview[:100]}..." if len(preview) > 100 else f"      预览: {preview}")

    # 分析stream_end
    if stream_end_data:
        print(f"\n🏁 流结束信息:")
        print(f"   状态: {stream_end_data.get('status')}")
        for key, value in stream_end_data.items():
            if key != 'status':
                print(f"   {key}: {value}")

    # 生成TypeScript类型定义
    print(f"\n📋 生成 TypeScript 类型定义:")
    print("=" * 80)

    ts_types = """
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
"""

    print(ts_types)

    # 生成使用示例
    print("=" * 80)
    print("\n💻 前端使用示例:")
    print("=" * 80)

    usage_example = """
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
      const lines = buffer.split('\\n');
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
"""

    print(usage_example)

    # 保存分析结果
    output_dir = Path(chunks_file).parent
    analysis_file = output_dir / f"chat_api_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write("# Chat API 数据结构分析\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 基本统计\n\n")
        f.write(f"- 总数据块: {total_chunks}\n")
        f.write(f"- 答案块数量: {len(answer_chunks)}\n")
        f.write(f"- 来源数量: {len(sources_data) if sources_data else 0}\n\n")
        f.write(f"## TypeScript 类型定义\n\n```typescript\n{ts_types}\n```\n\n")
        f.write(f"## 前端使用示例\n\n```typescript\n{usage_example}\n```\n")

    print(f"\n💾 分析报告已保存: {analysis_file}")

    return {
        'total_chunks': total_chunks,
        'chunk_types': chunk_types,
        'answer_length': len(full_answer),
        'sources_count': len(sources_data) if sources_data else 0,
        'analysis_file': str(analysis_file)
    }

if __name__ == "__main__":
    import sys

    # 查找最新的chunks文件
    chat_dir = Path("data/chat")
    chunks_files = sorted(chat_dir.glob("chat_response_chunks_*.json"))

    if not chunks_files:
        print("❌ 未找到chat响应数据文件")
        print("请先运行: python3 scripts/fetch_chat_stream.py")
        sys.exit(1)

    latest_file = chunks_files[-1]
    print(f"📂 分析文件: {latest_file}\n")

    result = analyze_chat_response(str(latest_file))

    print("\n" + "=" * 80)
    print("✅ 分析完成！")
    print("=" * 80)
