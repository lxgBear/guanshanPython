/**
 * Chat Sync API 类型定义（简化版）
 *
 * 适用于快速集成，只包含核心类型定义
 * 完整版请使用: chat-sync-api.types.ts
 */

// ==================== 请求 ====================

export interface ChatSyncRequest {
  question: string;
  user_id?: string;
  search_mode?: 'single' | 'multi';
}

// ==================== 响应 ====================

export interface Category {
  大类: string;
  类别: string;
  地域: string;
}

export interface SourceDetail {
  id: string;
  mongo_id: string;
  title: string;
  source: string;
  score: number;
  category: Category;
  publish_time: string;
  preview: string;
  url?: string | null;
  markdown_content?: string | null;
  content_length?: number | null;
  title_zh?: string | null;      // 中文标题
  summary_zh?: string | null;    // 中文摘要/翻译内容
  content_zh?: string | null;    // 中文总结
}

export interface ChatSyncResponse {
  question: string;
  answer: string;
  sources: SourceDetail[];
  sources_count: number;
  answer_length: number;
  status: string;
}

// ==================== 错误 ====================

export interface ChatSyncErrorResponse {
  error: string;
  message: string;
}
