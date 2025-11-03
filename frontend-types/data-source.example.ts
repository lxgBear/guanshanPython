/**
 * 数据源管理 API 使用示例
 *
 * 演示如何在 React/Vue/Angular 项目中使用类型定义
 *
 * @version 1.0.0
 */

import type {
  DataSource,
  DataSourceSummary,
  DataSourceStatus,
  DataSourceType,
  CreateDataSourceRequest,
  UpdateDataSourceInfoRequest,
  UpdateDataSourceContentRequest,
  AddRawDataRequest,
  ListDataSourcesParams,
  SuccessResponse,
  ApiResponse,
  DataSourceAPI,
  API_PATHS,
  DEFAULT_PAGINATION
} from './data-source.types';

import {
  isSuccessResponse,
  isErrorResponse,
  canEditDataSource,
  canConfirmDataSource,
  canRevertToDraft,
  STATUS_LABELS,
  TYPE_LABELS
} from './data-source.types';

// ==========================================
// 1. 基础 HTTP 客户端实现示例
// ==========================================

/**
 * 创建 axios/fetch 的 API 客户端
 */
class DataSourceApiClient implements DataSourceAPI {
  private baseURL: string;

  constructor(baseURL: string = 'http://localhost:8000') {
    this.baseURL = baseURL;
  }

  /**
   * 创建数据源
   */
  async createDataSource(
    request: CreateDataSourceRequest
  ): Promise<SuccessResponse<DataSource>> {
    const response = await fetch(`${this.baseURL}${API_PATHS.CREATE}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 获取数据源详情
   */
  async getDataSource(dataSourceId: string): Promise<SuccessResponse<DataSource>> {
    const response = await fetch(`${this.baseURL}${API_PATHS.GET(dataSourceId)}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 列出数据源（带查询参数）
   */
  async listDataSources(params?: ListDataSourcesParams): Promise<SuccessResponse> {
    const queryParams = new URLSearchParams();

    if (params?.created_by) queryParams.append('created_by', params.created_by);
    if (params?.status) queryParams.append('status', params.status);
    if (params?.source_type) queryParams.append('source_type', params.source_type);
    if (params?.start_date) queryParams.append('start_date', params.start_date);
    if (params?.end_date) queryParams.append('end_date', params.end_date);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.skip) queryParams.append('skip', params.skip.toString());

    const url = `${this.baseURL}${API_PATHS.LIST}?${queryParams}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 更新数据源基础信息
   */
  async updateDataSourceInfo(
    dataSourceId: string,
    request: UpdateDataSourceInfoRequest
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.UPDATE_INFO(dataSourceId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 更新数据源内容
   */
  async updateDataSourceContent(
    dataSourceId: string,
    request: UpdateDataSourceContentRequest
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.UPDATE_CONTENT(dataSourceId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 删除数据源
   */
  async deleteDataSource(dataSourceId: string, deletedBy: string): Promise<SuccessResponse> {
    const response = await fetch(
      `${this.baseURL}${API_PATHS.DELETE(dataSourceId)}?deleted_by=${deletedBy}`,
      { method: 'DELETE' }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 添加原始数据到数据源
   */
  async addRawDataToSource(
    dataSourceId: string,
    request: AddRawDataRequest
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.ADD_RAW_DATA(dataSourceId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 从数据源移除原始数据
   */
  async removeRawDataFromSource(
    dataSourceId: string,
    request: any
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.REMOVE_RAW_DATA(dataSourceId)}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 确定数据源
   */
  async confirmDataSource(
    dataSourceId: string,
    request: any
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.CONFIRM(dataSourceId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 恢复数据源为草稿
   */
  async revertDataSourceToDraft(
    dataSourceId: string,
    request: any
  ): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.REVERT(dataSourceId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 批量留存原始数据
   */
  async batchArchiveRawData(request: any): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.BATCH_ARCHIVE}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * 批量删除原始数据
   */
  async batchDeleteRawData(request: any): Promise<SuccessResponse> {
    const response = await fetch(`${this.baseURL}${API_PATHS.BATCH_DELETE}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }
}

// ==========================================
// 2. React 使用示例
// ==========================================

/**
 * React Hook 示例：创建数据源
 */
export function useCreateDataSource() {
  const apiClient = new DataSourceApiClient();

  const createDataSource = async (title: string, description: string, userId: string) => {
    const request: CreateDataSourceRequest = {
      title,
      description,
      created_by: userId,
      tags: [],
      // 分类字段示例（可选）
      primary_category: '技术文档',
      secondary_category: 'Python',
      tertiary_category: 'Web开发',
      custom_tags: ['FastAPI', '最佳实践']
    };

    try {
      const response = await apiClient.createDataSource(request);

      if (isSuccessResponse(response)) {
        console.log('✅ 数据源创建成功:', response.data);
        return response.data;
      }
    } catch (error) {
      console.error('❌ 创建失败:', error);
      throw error;
    }
  };

  return { createDataSource };
}

/**
 * React Hook 示例：获取数据源详情
 */
export function useDataSource(dataSourceId: string) {
  const apiClient = new DataSourceApiClient();

  const fetchDataSource = async (): Promise<DataSource | null> => {
    try {
      const response = await apiClient.getDataSource(dataSourceId);

      if (isSuccessResponse(response)) {
        return response.data!;
      }

      return null;
    } catch (error) {
      console.error('❌ 获取数据源失败:', error);
      return null;
    }
  };

  return { fetchDataSource };
}

/**
 * React Hook 示例：列出数据源
 */
export function useDataSourceList() {
  const apiClient = new DataSourceApiClient();

  const fetchDataSources = async (
    filters?: ListDataSourcesParams
  ): Promise<DataSourceSummary[]> => {
    try {
      const response = await apiClient.listDataSources(filters);

      if (isSuccessResponse(response) && response.data) {
        return response.data.items;
      }

      return [];
    } catch (error) {
      console.error('❌ 获取数据源列表失败:', error);
      return [];
    }
  };

  return { fetchDataSources };
}

// ==========================================
// 3. React Query 使用示例
// ==========================================

/**
 * React Query 配置示例
 *
 * 使用 @tanstack/react-query
 */
export function useDataSourceQuery(dataSourceId: string) {
  const apiClient = new DataSourceApiClient();

  // 这里假设使用 React Query
  // import { useQuery } from '@tanstack/react-query';

  /*
  return useQuery({
    queryKey: ['dataSource', dataSourceId],
    queryFn: () => apiClient.getDataSource(dataSourceId),
    select: (response) => {
      if (isSuccessResponse(response)) {
        return response.data;
      }
      return null;
    }
  });
  */
}

// ==========================================
// 4. Vue 使用示例
// ==========================================

/**
 * Vue Composable 示例：数据源管理
 */
export function useDataSourceManagement() {
  const apiClient = new DataSourceApiClient();

  // Vue ref
  // const dataSource = ref<DataSource | null>(null);
  // const loading = ref(false);
  // const error = ref<string | null>(null);

  const loadDataSource = async (id: string) => {
    // loading.value = true;
    // error.value = null;

    try {
      const response = await apiClient.getDataSource(id);

      if (isSuccessResponse(response)) {
        // dataSource.value = response.data!;
        return response.data;
      }
    } catch (err) {
      // error.value = String(err);
      console.error('加载失败:', err);
    } finally {
      // loading.value = false;
    }
  };

  return {
    // dataSource,
    // loading,
    // error,
    loadDataSource
  };
}

// ==========================================
// 5. 类型守卫使用示例
// ==========================================

/**
 * 示例：使用类型守卫处理 API 响应
 */
async function handleApiResponse() {
  const apiClient = new DataSourceApiClient();

  try {
    const response = await apiClient.getDataSource('123456');

    // 类型守卫：检查响应是否成功
    if (isSuccessResponse(response)) {
      const dataSource = response.data!;

      console.log('数据源标题:', dataSource.title);
      console.log('状态:', STATUS_LABELS[dataSource.status]);
      console.log('类型:', TYPE_LABELS[dataSource.source_type]);

      // 业务逻辑判断
      if (canEditDataSource(dataSource)) {
        console.log('✅ 可以编辑');
      }

      if (canConfirmDataSource(dataSource)) {
        console.log('✅ 可以确定');
      }

      if (canRevertToDraft(dataSource)) {
        console.log('✅ 可以恢复为草稿');
      }
    } else if (isErrorResponse(response)) {
      console.error('❌ 错误:', response.detail);
    }
  } catch (error) {
    console.error('❌ 请求失败:', error);
  }
}

// ==========================================
// 6. UI 组件示例
// ==========================================

/**
 * 示例：数据源状态徽章组件
 */
export function DataSourceStatusBadge({ status }: { status: DataSourceStatus }) {
  const label = STATUS_LABELS[status];
  const color = status === DataSourceStatus.DRAFT ? 'blue' : 'green';

  return `<span class="badge badge-${color}">${label}</span>`;
}

/**
 * 示例：数据源类型标签
 */
export function DataSourceTypeLabel({ type }: { type: DataSourceType }) {
  const label = TYPE_LABELS[type];
  return `<span class="label">${label}</span>`;
}

/**
 * 示例：数据源操作按钮
 */
export function DataSourceActions({ dataSource }: { dataSource: DataSource }) {
  const actions = [];

  if (canEditDataSource(dataSource)) {
    actions.push('edit');
  }

  if (canConfirmDataSource(dataSource)) {
    actions.push('confirm');
  }

  if (canRevertToDraft(dataSource)) {
    actions.push('revert');
  }

  return actions;
}

// ==========================================
// 7. 表单验证示例
// ==========================================

/**
 * 创建数据源表单验证
 */
export function validateCreateDataSourceForm(
  title: string,
  description: string
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!title || title.length < 1) {
    errors.push('标题不能为空');
  }

  if (title.length > 200) {
    errors.push('标题长度不能超过200字符');
  }

  if (description.length > 1000) {
    errors.push('描述长度不能超过1000字符');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

// ==========================================
// 8. 工具函数示例
// ==========================================

/**
 * 格式化日期时间
 */
export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString('zh-CN');
}

/**
 * 格式化统计信息
 */
export function formatDataSourceStats(dataSource: DataSource): string {
  const { total_raw_data_count, scheduled_data_count, instant_data_count } = dataSource;

  return `共 ${total_raw_data_count} 条（定时: ${scheduled_data_count}，即时: ${instant_data_count}）`;
}

/**
 * 获取数据源状态描述
 */
export function getDataSourceStatusDescription(dataSource: DataSource): string {
  if (dataSource.status === DataSourceStatus.DRAFT) {
    return '草稿状态，可以编辑和添加数据';
  } else {
    return `已确定于 ${formatDateTime(dataSource.confirmed_at!)}`;
  }
}

/**
 * 格式化分类路径
 */
export function formatCategoryPath(dataSource: DataSource): string {
  const parts = [
    dataSource.primary_category,
    dataSource.secondary_category,
    dataSource.tertiary_category
  ].filter(Boolean);

  return parts.length > 0 ? parts.join(' > ') : '未分类';
}

/**
 * 获取所有标签（包括 tags 和 custom_tags）
 */
export function getAllTags(dataSource: DataSource): string[] {
  const allTags = [...dataSource.tags];
  if (dataSource.custom_tags) {
    allTags.push(...dataSource.custom_tags);
  }
  return Array.from(new Set(allTags)); // 去重
}

// ==========================================
// 9. 批量操作示例
// ==========================================

/**
 * 批量添加原始数据到数据源
 */
export async function batchAddRawData(
  dataSourceId: string,
  dataIds: string[],
  dataType: 'scheduled' | 'instant',
  userId: string
) {
  const apiClient = new DataSourceApiClient();

  const results = {
    success: 0,
    failed: 0,
    errors: [] as string[]
  };

  for (const dataId of dataIds) {
    try {
      const request: AddRawDataRequest = {
        data_id: dataId,
        data_type: dataType,
        added_by: userId
      };

      await apiClient.addRawDataToSource(dataSourceId, request);
      results.success++;
    } catch (error) {
      results.failed++;
      results.errors.push(`数据 ${dataId} 添加失败: ${error}`);
    }
  }

  return results;
}

// ==========================================
// 10. 导出 API 客户端单例
// ==========================================

/**
 * 默认 API 客户端实例
 */
export const dataSourceApi = new DataSourceApiClient();

/**
 * 使用示例：
 *
 * ```typescript
 * import { dataSourceApi } from './data-source.example';
 *
 * // 创建数据源
 * const response = await dataSourceApi.createDataSource({
 *   title: 'Python 最佳实践',
 *   description: 'Python 开发最佳实践收集',
 *   created_by: 'user123'
 * });
 *
 * // 获取数据源
 * const dataSource = await dataSourceApi.getDataSource('123456');
 *
 * // 更新数据源
 * await dataSourceApi.updateDataSourceInfo('123456', {
 *   title: '新标题',
 *   updated_by: 'user123'
 * });
 * ```
 */
