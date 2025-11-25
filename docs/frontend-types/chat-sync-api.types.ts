/**
 * Chat Sync API 类型定义
 *
 * 端点: POST /api/v1/chat/sync
 * 版本: v2.0.0
 * 更新: 2025-11-24
 *
 * 使用方法:
 * import { ChatSyncRequest, ChatSyncResponse, SourceDetail } from './chat-sync-api.types';
 */

// ==================== 请求类型 ====================

/**
 * Chat Sync API 请求参数
 */
export interface ChatSyncRequest {
  /** 用户问题（必填，1-1000字符） */
  question: string;

  /** 用户ID（可选） */
  user_id?: string;

  /** 搜索模式（可选，默认 single） */
  search_mode?: 'single' | 'multi';
}

// ==================== 响应类型 ====================

/**
 * 分类信息
 */
export interface Category {
  /** 大类 */
  大类: string;

  /** 类别 */
  类别: string;

  /** 地域 */
  地域: string;
}

/**
 * 数据来源详情（增强版，包含完整内容）
 */
export interface SourceDetail {
  /** UUID */
  id: string;

  /** MongoDB ID */
  mongo_id: string;

  /** 标题 */
  title: string;

  /** 来源网站 */
  source: string;

  /** 相关性评分 (0-1) */
  score: number;

  /** 分类信息 */
  category: Category;

  /** 发布时间 */
  publish_time: string;

  /** 内容预览 */
  preview: string;

  /** 完整URL（从 news_results 查询，可能为 null） */
  url?: string | null;

  /** 完整Markdown内容（从 news_results 查询，可能为 null） */
  markdown_content?: string | null;

  /** 内容长度（字符数，可能为 null） */
  content_length?: number | null;

  /** 中文标题（从 news_results.news_results 查询，可能为 null） */
  title_zh?: string | null;

  /** 中文摘要/翻译内容（从 news_results.news_results 查询，可能为 null） */
  summary_zh?: string | null;

  /** 中文总结（从 news_results.news_results 查询，可能为 null） */
  content_zh?: string | null;
}

/**
 * Chat Sync API 成功响应
 */
export interface ChatSyncResponse {
  /** 用户问题 */
  question: string;

  /** 完整答案 */
  answer: string;

  /** 数据来源列表（含完整内容） */
  sources: SourceDetail[];

  /** 来源数量 */
  sources_count: number;

  /** 答案长度 */
  answer_length: number;

  /** 状态 */
  status: 'success_from_llm' | 'success_from_cache' | string;
}

// ==================== 错误响应类型 ====================

/**
 * API 错误响应
 */
export interface ChatSyncErrorResponse {
  /** 错误类型 */
  error: string;

  /** 错误消息 */
  message: string;
}

// ==================== API 调用辅助类型 ====================

/**
 * API 调用状态
 */
export type ApiStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * API 调用结果（联合类型）
 */
export type ChatSyncResult =
  | { status: 'success'; data: ChatSyncResponse }
  | { status: 'error'; error: ChatSyncErrorResponse };

// ==================== 使用示例 ====================

/**
 * 示例：React Hook 使用
 *
 * ```typescript
 * import { useState } from 'react';
 * import { ChatSyncRequest, ChatSyncResponse, ChatSyncErrorResponse } from './chat-sync-api.types';
 *
 * function useChatSync() {
 *   const [data, setData] = useState<ChatSyncResponse | null>(null);
 *   const [error, setError] = useState<ChatSyncErrorResponse | null>(null);
 *   const [loading, setLoading] = useState(false);
 *
 *   const fetchChat = async (request: ChatSyncRequest) => {
 *     setLoading(true);
 *     setError(null);
 *
 *     try {
 *       const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
 *         method: 'POST',
 *         headers: { 'Content-Type': 'application/json' },
 *         body: JSON.stringify(request),
 *       });
 *
 *       if (!response.ok) {
 *         const errorData: ChatSyncErrorResponse = await response.json();
 *         setError(errorData);
 *         return;
 *       }
 *
 *       const data: ChatSyncResponse = await response.json();
 *       setData(data);
 *     } catch (err: any) {
 *       setError({ error: 'Network Error', message: err.message });
 *     } finally {
 *       setLoading(false);
 *     }
 *   };
 *
 *   return { data, error, loading, fetchChat };
 * }
 * ```
 */

/**
 * 示例：Axios 使用
 *
 * ```typescript
 * import axios, { AxiosError } from 'axios';
 * import { ChatSyncRequest, ChatSyncResponse, ChatSyncErrorResponse } from './chat-sync-api.types';
 *
 * const api = axios.create({
 *   baseURL: 'http://localhost:8000/api/v1',
 *   headers: { 'Content-Type': 'application/json' },
 * });
 *
 * async function chatSync(request: ChatSyncRequest): Promise<ChatSyncResponse> {
 *   try {
 *     const response = await api.post<ChatSyncResponse>('/chat/sync', request);
 *     return response.data;
 *   } catch (error) {
 *     const axiosError = error as AxiosError<ChatSyncErrorResponse>;
 *     throw axiosError.response?.data || { error: 'Unknown', message: 'Unknown error' };
 *   }
 * }
 * ```
 */

/**
 * 示例：Vue 3 Composition API 使用
 *
 * ```typescript
 * import { ref, Ref } from 'vue';
 * import { ChatSyncRequest, ChatSyncResponse, ChatSyncErrorResponse } from './chat-sync-api.types';
 *
 * export function useChatSync() {
 *   const data: Ref<ChatSyncResponse | null> = ref(null);
 *   const error: Ref<ChatSyncErrorResponse | null> = ref(null);
 *   const loading = ref(false);
 *
 *   const fetchChat = async (request: ChatSyncRequest) => {
 *     loading.value = true;
 *     error.value = null;
 *
 *     try {
 *       const response = await fetch('http://localhost:8000/api/v1/chat/sync', {
 *         method: 'POST',
 *         headers: { 'Content-Type': 'application/json' },
 *         body: JSON.stringify(request),
 *       });
 *
 *       if (!response.ok) {
 *         error.value = await response.json();
 *         return;
 *       }
 *
 *       data.value = await response.json();
 *     } catch (err: any) {
 *       error.value = { error: 'Network Error', message: err.message };
 *     } finally {
 *       loading.value = false;
 *     }
 *   };
 *
 *   return { data, error, loading, fetchChat };
 * }
 * ```
 */
