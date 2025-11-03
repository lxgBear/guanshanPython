/**
 * 数据源管理 API 类型定义
 *
 * 基于后端实现自动生成
 * API Base URL: /api/v1/data-sources
 *
 * @version 1.5.0
 * @generated 2025-10-31
 * @changelog v1.5.0 - ID系统统一：所有ID字段统一使用雪花算法（详见 ID_SYSTEM_UNIFICATION_v1.5.0.md）
 */

// ==========================================
// 枚举类型
// ==========================================

/**
 * 数据源状态枚举（仅2个状态）
 */
export enum DataSourceStatus {
  /** 草稿：可编辑、可添加删除数据 */
  DRAFT = 'draft',
  /** 已确定：只读、数据已锁定 */
  CONFIRMED = 'confirmed'
}

/**
 * 数据源类型枚举
 */
export enum DataSourceType {
  /** 来自定时任务 */
  SCHEDULED = 'scheduled',
  /** 来自即时搜索 */
  INSTANT = 'instant',
  /** 混合数据源 */
  MIXED = 'mixed'
}

/**
 * 原始数据类型（用于 data_type 字段）
 */
export type RawDataType = 'scheduled' | 'instant';

// ==========================================
// 核心实体类型
// ==========================================

/**
 * 原始数据引用
 *
 * 存储对 SearchResult 或 InstantSearchResult 的引用
 */
export interface RawDataReference {
  /** 数据ID */
  data_id: string;

  /** 数据类型（scheduled 或 instant） */
  data_type: RawDataType;

  /** 标题（快照数据，用于展示） */
  title: string;

  /** URL（快照数据） */
  url: string;

  /** 摘要（快照数据） */
  snippet: string;

  /** 添加时间（ISO 8601 格式） */
  added_at: string;

  /** 添加者 */
  added_by: string;
}

/**
 * 数据源实体（完整数据）
 *
 * 用于详情页面和编辑表单
 */
export interface DataSource {
  /** 主键（雪花算法ID，全局唯一） */
  id: string;

  // ========== 基础信息 ==========

  /** 数据源标题 */
  title: string;

  /** 数据源描述 */
  description: string;

  /** 数据源类型 */
  source_type: DataSourceType;

  // ========== 状态管理 ==========

  /** 当前状态 */
  status: DataSourceStatus;

  // ========== 原始数据引用 ==========

  /** 原始数据引用列表 */
  raw_data_refs: RawDataReference[];

  // ========== 编辑内容 ==========

  /** 用户编辑的内容（Markdown格式） */
  edited_content: string;

  /** 内容版本号 */
  content_version: number;

  // ========== 统计信息 ==========

  /** 原始数据总数 */
  total_raw_data_count: number;

  /** 定时任务数据数量 */
  scheduled_data_count: number;

  /** 即时搜索数据数量 */
  instant_data_count: number;

  // ========== 创建和确定信息 ==========

  /** 创建者 */
  created_by: string;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;

  /** 确定者（可选） */
  confirmed_by: string | null;

  /** 确定时间（可选，ISO 8601 格式） */
  confirmed_at: string | null;

  // ========== 更新信息 ==========

  /** 最后更新者 */
  updated_by: string;

  /** 最后更新时间（ISO 8601 格式） */
  updated_at: string;

  // ========== 元数据 ==========

  /** 标签列表 */
  tags: string[];

  /** 扩展元数据（键值对） */
  metadata: Record<string, any>;

  // ========== 分类字段 ==========

  /** 第一级分类：大类（可选） */
  primary_category?: string;

  /** 第二级分类：子目录（可选） */
  secondary_category?: string;

  /** 第三级分类：具体分类（可选） */
  tertiary_category?: string;

  /** 自定义标签数组（可选） */
  custom_tags?: string[];
}

/**
 * 数据源摘要（轻量级）
 *
 * 用于列表页面
 */
export interface DataSourceSummary {
  /** 主键 */
  id: string;

  /** 标题 */
  title: string;

  /** 描述 */
  description: string;

  /** 数据源类型 */
  source_type: DataSourceType;

  /** 当前状态 */
  status: DataSourceStatus;

  /** 原始数据总数 */
  total_raw_data_count: number;

  /** 定时任务数据数量 */
  scheduled_data_count: number;

  /** 即时搜索数据数量 */
  instant_data_count: number;

  /** 创建者 */
  created_by: string;

  /** 创建时间（ISO 8601 格式） */
  created_at: string;

  /** 确定时间（可选，ISO 8601 格式） */
  confirmed_at: string | null;

  /** 标签列表 */
  tags: string[];

  /** 第一级分类：大类（可选） */
  primary_category?: string;

  /** 第二级分类：子目录（可选） */
  secondary_category?: string;

  /** 第三级分类：具体分类（可选） */
  tertiary_category?: string;

  /** 自定义标签数组（可选） */
  custom_tags?: string[];
}

// ==========================================
// API 请求类型
// ==========================================

/**
 * 创建数据源请求
 */
export interface CreateDataSourceRequest {
  /** 数据源标题（1-200字符） */
  title: string;

  /** 数据源描述（最多1000字符，可选） */
  description?: string;

  /** 创建者 */
  created_by: string;

  /** 标签列表（可选） */
  tags?: string[];

  /** 扩展元数据（可选） */
  metadata?: Record<string, any>;

  /** 第一级分类：大类（可选） */
  primary_category?: string;

  /** 第二级分类：子目录（可选） */
  secondary_category?: string;

  /** 第三级分类：具体分类（可选） */
  tertiary_category?: string;

  /** 自定义标签数组（可选） */
  custom_tags?: string[];
}

/**
 * 更新数据源基础信息请求
 */
export interface UpdateDataSourceInfoRequest {
  /** 新标题（1-200字符，可选） */
  title?: string;

  /** 新描述（最多1000字符，可选） */
  description?: string;

  /** 新标签列表（可选） */
  tags?: string[];

  /** 第一级分类：大类（可选） */
  primary_category?: string;

  /** 第二级分类：子目录（可选） */
  secondary_category?: string;

  /** 第三级分类：具体分类（可选） */
  tertiary_category?: string;

  /** 自定义标签数组（可选） */
  custom_tags?: string[];

  /** 更新者 */
  updated_by: string;
}

/**
 * 更新数据源内容请求
 */
export interface UpdateDataSourceContentRequest {
  /** 编辑内容（Markdown格式） */
  edited_content: string;

  /** 更新者 */
  updated_by: string;
}

/**
 * 添加原始数据请求
 */
export interface AddRawDataRequest {
  /** 原始数据ID */
  data_id: string;

  /** 数据类型（scheduled 或 instant） */
  data_type: RawDataType;

  /** 添加者 */
  added_by: string;
}

/**
 * 移除原始数据请求
 */
export interface RemoveRawDataRequest {
  /** 原始数据ID */
  data_id: string;

  /** 数据类型（scheduled 或 instant） */
  data_type: RawDataType;

  /** 移除者 */
  removed_by: string;
}

/**
 * 确定数据源请求
 */
export interface ConfirmDataSourceRequest {
  /** 确定者 */
  confirmed_by: string;
}

/**
 * 恢复草稿请求
 */
export interface RevertDataSourceRequest {
  /** 操作者 */
  reverted_by: string;
}

/**
 * 批量操作请求
 */
export interface BatchOperationRequest {
  /** 原始数据ID列表（至少1个） */
  data_ids: string[];

  /** 数据类型（scheduled 或 instant） */
  data_type: RawDataType;

  /** 操作者 */
  operator: string;
}

// ==========================================
// API 响应类型
// ==========================================

/**
 * 标准成功响应
 */
export interface SuccessResponse<T = any> {
  /** 操作是否成功 */
  success: true;

  /** 响应消息 */
  message?: string;

  /** 响应数据 */
  data?: T;
}

/**
 * 标准错误响应
 */
export interface ErrorResponse {
  /** 操作是否成功 */
  success: false;

  /** 错误详情 */
  detail: string;
}

/**
 * API 响应（成功或失败）
 */
export type ApiResponse<T = any> = SuccessResponse<T> | ErrorResponse;

/**
 * 列表响应数据
 */
export interface ListResponseData {
  /** 数据源摘要列表 */
  items: DataSourceSummary[];

  /** 总数量 */
  total: number;

  /** 每页数量 */
  limit: number;

  /** 跳过数量 */
  skip: number;
}

/**
 * 批量操作结果
 */
export interface BatchOperationResult {
  /** 成功数量 */
  success_count: number;

  /** 失败数量 */
  failed_count: number;

  /** 失败的ID列表 */
  failed_ids?: string[];
}

// ==========================================
// API 查询参数类型
// ==========================================

/**
 * 列出数据源的查询参数
 */
export interface ListDataSourcesParams {
  /** 创建者过滤（可选） */
  created_by?: string;

  /** 状态过滤（可选） */
  status?: DataSourceStatus;

  /** 数据源类型过滤（可选） */
  source_type?: DataSourceType;

  /** 开始日期过滤（可选，ISO 8601 格式） */
  start_date?: string;

  /** 结束日期过滤（可选，ISO 8601 格式） */
  end_date?: string;

  /** 每页数量（1-100，默认50） */
  limit?: number;

  /** 跳过数量（默认0） */
  skip?: number;

  /** 第一级分类过滤（可选） */
  primary_category?: string;

  /** 第二级分类过滤（可选） */
  secondary_category?: string;

  /** 第三级分类过滤（可选） */
  tertiary_category?: string;
}

// ==========================================
// API 函数类型定义（TypeScript 函数签名）
// ==========================================

/**
 * 数据源管理 API 接口定义
 *
 * 可用于 React Query、SWR 等数据获取库
 */
export interface DataSourceAPI {
  // ========== 基础 CRUD 操作 ==========

  /**
   * 创建数据源
   * POST /api/v1/data-sources/
   */
  createDataSource(request: CreateDataSourceRequest): Promise<SuccessResponse<DataSource>>;

  /**
   * 获取数据源详情
   * GET /api/v1/data-sources/{data_source_id}
   */
  getDataSource(dataSourceId: string): Promise<SuccessResponse<DataSource>>;

  /**
   * 列出数据源（分页）
   * GET /api/v1/data-sources/
   */
  listDataSources(params?: ListDataSourcesParams): Promise<SuccessResponse<ListResponseData>>;

  /**
   * 更新数据源基础信息
   * PUT /api/v1/data-sources/{data_source_id}/info
   */
  updateDataSourceInfo(
    dataSourceId: string,
    request: UpdateDataSourceInfoRequest
  ): Promise<SuccessResponse>;

  /**
   * 更新数据源内容
   * PUT /api/v1/data-sources/{data_source_id}/content
   */
  updateDataSourceContent(
    dataSourceId: string,
    request: UpdateDataSourceContentRequest
  ): Promise<SuccessResponse>;

  /**
   * 删除数据源
   * DELETE /api/v1/data-sources/{data_source_id}
   */
  deleteDataSource(dataSourceId: string, deletedBy: string): Promise<SuccessResponse>;

  // ========== 原始数据管理 ==========

  /**
   * 添加原始数据到数据源
   * POST /api/v1/data-sources/{data_source_id}/raw-data
   */
  addRawDataToSource(
    dataSourceId: string,
    request: AddRawDataRequest
  ): Promise<SuccessResponse>;

  /**
   * 从数据源移除原始数据
   * DELETE /api/v1/data-sources/{data_source_id}/raw-data
   */
  removeRawDataFromSource(
    dataSourceId: string,
    request: RemoveRawDataRequest
  ): Promise<SuccessResponse>;

  // ========== 状态管理 ==========

  /**
   * 确定数据源（DRAFT → CONFIRMED）
   * POST /api/v1/data-sources/{data_source_id}/confirm
   */
  confirmDataSource(
    dataSourceId: string,
    request: ConfirmDataSourceRequest
  ): Promise<SuccessResponse>;

  /**
   * 恢复数据源为草稿（CONFIRMED → DRAFT）
   * POST /api/v1/data-sources/{data_source_id}/revert
   */
  revertDataSourceToDraft(
    dataSourceId: string,
    request: RevertDataSourceRequest
  ): Promise<SuccessResponse>;

  // ========== 批量操作 ==========

  /**
   * 批量留存原始数据
   * POST /api/v1/data-sources/batch/archive
   */
  batchArchiveRawData(
    request: BatchOperationRequest
  ): Promise<SuccessResponse<BatchOperationResult>>;

  /**
   * 批量删除原始数据
   * POST /api/v1/data-sources/batch/delete
   */
  batchDeleteRawData(
    request: BatchOperationRequest
  ): Promise<SuccessResponse<BatchOperationResult>>;
}

// ==========================================
// 类型守卫和工具函数
// ==========================================

/**
 * 检查响应是否成功
 */
export function isSuccessResponse<T>(
  response: ApiResponse<T>
): response is SuccessResponse<T> {
  return response.success === true;
}

/**
 * 检查响应是否失败
 */
export function isErrorResponse(
  response: ApiResponse
): response is ErrorResponse {
  return response.success === false;
}

/**
 * 检查数据源是否可编辑
 */
export function canEditDataSource(dataSource: DataSource | DataSourceSummary): boolean {
  return dataSource.status === DataSourceStatus.DRAFT;
}

/**
 * 检查数据源是否可确定
 */
export function canConfirmDataSource(dataSource: DataSource): boolean {
  return (
    dataSource.status === DataSourceStatus.DRAFT &&
    dataSource.total_raw_data_count > 0
  );
}

/**
 * 检查数据源是否可恢复为草稿
 */
export function canRevertToDraft(dataSource: DataSource | DataSourceSummary): boolean {
  return dataSource.status === DataSourceStatus.CONFIRMED;
}

// ==========================================
// 常量定义
// ==========================================

/**
 * API 路径常量
 */
export const API_PATHS = {
  BASE: '/api/v1/data-sources',
  CREATE: '/api/v1/data-sources/',
  GET: (id: string) => `/api/v1/data-sources/${id}`,
  LIST: '/api/v1/data-sources/',
  UPDATE_INFO: (id: string) => `/api/v1/data-sources/${id}/info`,
  UPDATE_CONTENT: (id: string) => `/api/v1/data-sources/${id}/content`,
  DELETE: (id: string) => `/api/v1/data-sources/${id}`,
  ADD_RAW_DATA: (id: string) => `/api/v1/data-sources/${id}/raw-data`,
  REMOVE_RAW_DATA: (id: string) => `/api/v1/data-sources/${id}/raw-data`,
  CONFIRM: (id: string) => `/api/v1/data-sources/${id}/confirm`,
  REVERT: (id: string) => `/api/v1/data-sources/${id}/revert`,
  BATCH_ARCHIVE: '/api/v1/data-sources/batch/archive',
  BATCH_DELETE: '/api/v1/data-sources/batch/delete'
} as const;

/**
 * 默认分页参数
 */
export const DEFAULT_PAGINATION = {
  LIMIT: 50,
  SKIP: 0,
  MAX_LIMIT: 100
} as const;

/**
 * 状态显示文本映射（中文）
 */
export const STATUS_LABELS: Record<DataSourceStatus, string> = {
  [DataSourceStatus.DRAFT]: '草稿',
  [DataSourceStatus.CONFIRMED]: '已确定'
};

/**
 * 类型显示文本映射（中文）
 */
export const TYPE_LABELS: Record<DataSourceType, string> = {
  [DataSourceType.SCHEDULED]: '定时任务',
  [DataSourceType.INSTANT]: '即时搜索',
  [DataSourceType.MIXED]: '混合数据源'
};

/**
 * 状态颜色映射（用于 UI 显示）
 */
export const STATUS_COLORS: Record<DataSourceStatus, string> = {
  [DataSourceStatus.DRAFT]: 'blue',
  [DataSourceStatus.CONFIRMED]: 'green'
};
