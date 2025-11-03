# 数据源管理 API - TypeScript 类型定义

> 为前端项目提供完整的 TypeScript 类型定义和使用示例

## 📦 文件清单

| 文件 | 说明 |
|------|------|
| `data-source.types.ts` | **核心类型定义**：包含所有接口、枚举、类型守卫和工具函数 |
| `data-source.example.ts` | **使用示例**：React/Vue/Angular 集成示例 |
| `README.md` | **使用指南**：本文件 |

## 🚀 快速开始

### 1. 复制文件到您的前端项目

```bash
# 将类型定义文件复制到项目中
cp data-source.types.ts your-frontend-project/src/types/
cp data-source.example.ts your-frontend-project/src/api/
```

### 2. 在代码中导入类型

```typescript
// 导入类型定义
import type {
  DataSource,
  DataSourceSummary,
  CreateDataSourceRequest,
  DataSourceAPI
} from '@/types/data-source.types';

// 导入工具函数
import {
  canEditDataSource,
  STATUS_LABELS
} from '@/types/data-source.types';
```

## 📋 核心类型说明

### 1. 实体类型

#### `DataSource` - 完整数据源实体
用于详情页面和编辑表单

```typescript
interface DataSource {
  id: string;                      // 主键
  title: string;                   // 标题
  description: string;             // 描述
  status: DataSourceStatus;        // 状态（draft/confirmed）
  source_type: DataSourceType;     // 类型（scheduled/instant/mixed）
  raw_data_refs: RawDataReference[]; // 原始数据引用列表
  edited_content: string;          // 编辑内容（Markdown）
  total_raw_data_count: number;    // 数据总数

  // 分类字段（新增）
  primary_category?: string;       // 第一级分类（大类）
  secondary_category?: string;     // 第二级分类（子目录）
  tertiary_category?: string;      // 第三级分类（具体分类）
  custom_tags?: string[];          // 自定义标签数组
  // ... 更多字段
}
```

#### `DataSourceSummary` - 轻量级摘要
用于列表页面（不包含原始数据引用和编辑内容）

```typescript
interface DataSourceSummary {
  id: string;
  title: string;
  description: string;
  status: DataSourceStatus;
  total_raw_data_count: number;
  created_at: string;
  // ... 其他摘要字段
}
```

### 2. 枚举类型

```typescript
// 数据源状态（仅2个状态）
enum DataSourceStatus {
  DRAFT = 'draft',           // 草稿：可编辑
  CONFIRMED = 'confirmed'    // 已确定：只读
}

// 数据源类型
enum DataSourceType {
  SCHEDULED = 'scheduled',   // 定时任务
  INSTANT = 'instant',       // 即时搜索
  MIXED = 'mixed'           // 混合
}
```

### 3. 请求类型

```typescript
// 创建数据源
interface CreateDataSourceRequest {
  title: string;               // 必填，1-200字符
  description?: string;        // 可选，最多1000字符
  created_by: string;         // 必填
  tags?: string[];            // 可选
  metadata?: Record<string, any>; // 可选
}

// 更新基础信息
interface UpdateDataSourceInfoRequest {
  title?: string;
  description?: string;
  tags?: string[];
  updated_by: string;         // 必填
}

// 更新内容
interface UpdateDataSourceContentRequest {
  edited_content: string;     // Markdown 格式
  updated_by: string;
}
```

## 🔧 API 端点映射

### 基础 CRUD

| 操作 | 方法 | 端点 | 请求类型 | 响应类型 |
|------|------|------|----------|----------|
| 创建 | POST | `/data-sources/` | `CreateDataSourceRequest` | `DataSource` |
| 详情 | GET | `/data-sources/{id}` | - | `DataSource` |
| 列表 | GET | `/data-sources/` | `ListDataSourcesParams` | `ListResponseData` |
| 更新信息 | PUT | `/data-sources/{id}/info` | `UpdateDataSourceInfoRequest` | - |
| 更新内容 | PUT | `/data-sources/{id}/content` | `UpdateDataSourceContentRequest` | - |
| 删除 | DELETE | `/data-sources/{id}` | `deleted_by` (query) | - |

### 原始数据管理

| 操作 | 方法 | 端点 | 请求类型 |
|------|------|------|----------|
| 添加数据 | POST | `/data-sources/{id}/raw-data` | `AddRawDataRequest` |
| 移除数据 | DELETE | `/data-sources/{id}/raw-data` | `RemoveRawDataRequest` |

### 状态管理

| 操作 | 方法 | 端点 | 请求类型 | 状态转换 |
|------|------|------|----------|----------|
| 确定 | POST | `/data-sources/{id}/confirm` | `ConfirmDataSourceRequest` | DRAFT → CONFIRMED |
| 恢复草稿 | POST | `/data-sources/{id}/revert` | `RevertDataSourceRequest` | CONFIRMED → DRAFT |

### 批量操作

| 操作 | 方法 | 端点 | 请求类型 |
|------|------|------|----------|
| 批量留存 | POST | `/data-sources/batch/archive` | `BatchOperationRequest` |
| 批量删除 | POST | `/data-sources/batch/delete` | `BatchOperationRequest` |

## 💡 使用示例

### React + TypeScript

#### 1. 创建数据源

```typescript
import { dataSourceApi } from '@/api/data-source.example';
import type { CreateDataSourceRequest } from '@/types/data-source.types';

async function createDataSource() {
  const request: CreateDataSourceRequest = {
    title: 'Python Web开发最佳实践',
    description: '收集Python Web开发相关的优质资源',
    created_by: 'user123',
    tags: ['Python', 'Web开发']
  };

  try {
    const response = await dataSourceApi.createDataSource(request);

    if (response.success) {
      console.log('✅ 创建成功:', response.data);
      return response.data;
    }
  } catch (error) {
    console.error('❌ 创建失败:', error);
  }
}
```

#### 2. 获取数据源详情

```typescript
import { dataSourceApi } from '@/api/data-source.example';
import { canEditDataSource, STATUS_LABELS } from '@/types/data-source.types';

async function loadDataSource(id: string) {
  try {
    const response = await dataSourceApi.getDataSource(id);

    if (response.success && response.data) {
      const dataSource = response.data;

      console.log('标题:', dataSource.title);
      console.log('状态:', STATUS_LABELS[dataSource.status]);
      console.log('数据数量:', dataSource.total_raw_data_count);

      // 业务逻辑判断
      if (canEditDataSource(dataSource)) {
        console.log('✅ 可以编辑');
      }

      return dataSource;
    }
  } catch (error) {
    console.error('❌ 加载失败:', error);
  }
}
```

#### 3. React Hook 封装

```typescript
import { useState, useEffect } from 'react';
import { dataSourceApi } from '@/api/data-source.example';
import type { DataSource } from '@/types/data-source.types';

function useDataSource(id: string) {
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const response = await dataSourceApi.getDataSource(id);

        if (response.success && response.data) {
          setDataSource(response.data);
        }
      } catch (err) {
        setError(String(err));
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [id]);

  return { dataSource, loading, error };
}

// 使用
function DataSourceDetail({ id }: { id: string }) {
  const { dataSource, loading, error } = useDataSource(id);

  if (loading) return <div>加载中...</div>;
  if (error) return <div>错误: {error}</div>;
  if (!dataSource) return <div>未找到数据源</div>;

  return (
    <div>
      <h1>{dataSource.title}</h1>
      <p>{dataSource.description}</p>
      <span>数据量: {dataSource.total_raw_data_count}</span>
    </div>
  );
}
```

### React Query 集成

```typescript
import { useQuery, useMutation } from '@tanstack/react-query';
import { dataSourceApi } from '@/api/data-source.example';
import type { CreateDataSourceRequest } from '@/types/data-source.types';

// 查询数据源
export function useDataSourceQuery(id: string) {
  return useQuery({
    queryKey: ['dataSource', id],
    queryFn: async () => {
      const response = await dataSourceApi.getDataSource(id);
      return response.success ? response.data : null;
    }
  });
}

// 创建数据源
export function useCreateDataSource() {
  return useMutation({
    mutationFn: (request: CreateDataSourceRequest) =>
      dataSourceApi.createDataSource(request),
    onSuccess: () => {
      console.log('✅ 创建成功');
    }
  });
}

// 使用
function CreateDataSourceForm() {
  const createMutation = useCreateDataSource();

  const handleSubmit = (formData: CreateDataSourceRequest) => {
    createMutation.mutate(formData);
  };

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      // 提取表单数据并提交
    }}>
      {/* 表单字段 */}
    </form>
  );
}
```

### Vue 3 + TypeScript

```typescript
import { ref, onMounted } from 'vue';
import { dataSourceApi } from '@/api/data-source.example';
import type { DataSource } from '@/types/data-source.types';

export function useDataSource(id: string) {
  const dataSource = ref<DataSource | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const loadDataSource = async () => {
    loading.value = true;
    error.value = null;

    try {
      const response = await dataSourceApi.getDataSource(id);

      if (response.success && response.data) {
        dataSource.value = response.data;
      }
    } catch (err) {
      error.value = String(err);
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    loadDataSource();
  });

  return {
    dataSource,
    loading,
    error,
    reload: loadDataSource
  };
}
```

## 🗂️ 分类功能

### 分类字段说明

数据源支持三级分类体系和自定义标签：

| 字段 | 说明 | 示例 |
|------|------|------|
| `primary_category` | 第一级分类（大类） | "技术文档"、"产品资料"、"市场分析" |
| `secondary_category` | 第二级分类（子目录） | "Python"、"前端开发"、"数据分析" |
| `tertiary_category` | 第三级分类（具体分类） | "Web开发"、"机器学习"、"React" |
| `custom_tags` | 自定义标签数组 | ["FastAPI", "最佳实践", "性能优化"] |

### 创建带分类的数据源

```typescript
import { dataSourceApi } from '@/api/data-source.example';

const request = {
  title: 'Python Web开发最佳实践',
  description: '收集Python Web开发相关的优质资源',
  created_by: 'user123',
  tags: ['Python', 'Web'],

  // 三级分类
  primary_category: '技术文档',
  secondary_category: 'Python',
  tertiary_category: 'Web开发',

  // 自定义标签
  custom_tags: ['FastAPI', 'Django', '最佳实践']
};

const response = await dataSourceApi.createDataSource(request);
```

### 更新分类信息

```typescript
await dataSourceApi.updateDataSourceInfo('data-source-id', {
  primary_category: '产品资料',
  secondary_category: '技术规格',
  tertiary_category: 'API文档',
  custom_tags: ['RESTful', 'OpenAPI'],
  updated_by: 'user123'
});
```

### 按分类筛选

```typescript
// 筛选第一级分类
const response = await dataSourceApi.listDataSources({
  primary_category: '技术文档',
  limit: 20
});

// 筛选二级分类
const response = await dataSourceApi.listDataSources({
  primary_category: '技术文档',
  secondary_category: 'Python',
  limit: 20
});

// 精确筛选到三级分类
const response = await dataSourceApi.listDataSources({
  primary_category: '技术文档',
  secondary_category: 'Python',
  tertiary_category: 'Web开发',
  limit: 20
});
```

### 分类工具函数

```typescript
import { formatCategoryPath, getAllTags } from '@/api/data-source.example';

// 格式化分类路径
const categoryPath = formatCategoryPath(dataSource);
// 输出: "技术文档 > Python > Web开发"

// 获取所有标签（合并 tags 和 custom_tags）
const allTags = getAllTags(dataSource);
// 输出: ['Python', 'Web', 'FastAPI', 'Django', '最佳实践']
```

### 分类树形展示示例

```tsx
interface CategoryTreeNode {
  label: string;
  value: string;
  children?: CategoryTreeNode[];
  count?: number;
}

function CategoryTree({ dataSource }: { dataSource: DataSource }) {
  const categoryPath = [
    dataSource.primary_category,
    dataSource.secondary_category,
    dataSource.tertiary_category
  ].filter(Boolean);

  return (
    <div className="category-tree">
      {categoryPath.map((category, index) => (
        <span key={index}>
          {index > 0 && <span className="separator"> &gt; </span>}
          <span className="category-item">{category}</span>
        </span>
      ))}
    </div>
  );
}
```

## 🛡️ 类型守卫和工具函数

### 响应类型守卫

```typescript
import { isSuccessResponse, isErrorResponse } from '@/types/data-source.types';

const response = await dataSourceApi.getDataSource('123');

if (isSuccessResponse(response)) {
  // TypeScript 知道 response.data 存在
  console.log(response.data.title);
} else if (isErrorResponse(response)) {
  // TypeScript 知道 response.detail 存在
  console.error(response.detail);
}
```

### 业务逻辑判断

```typescript
import {
  canEditDataSource,
  canConfirmDataSource,
  canRevertToDraft
} from '@/types/data-source.types';

// 判断是否可以编辑
if (canEditDataSource(dataSource)) {
  showEditButton();
}

// 判断是否可以确定
if (canConfirmDataSource(dataSource)) {
  showConfirmButton();
}

// 判断是否可以恢复为草稿
if (canRevertToDraft(dataSource)) {
  showRevertButton();
}
```

### 显示文本映射

```typescript
import { STATUS_LABELS, TYPE_LABELS } from '@/types/data-source.types';

// 状态显示文本
const statusText = STATUS_LABELS[dataSource.status]; // "草稿" 或 "已确定"

// 类型显示文本
const typeText = TYPE_LABELS[dataSource.source_type]; // "定时任务"、"即时搜索" 或 "混合数据源"
```

## 📐 状态流转图

```
┌─────────┐
│  DRAFT  │ ←─────────────┐
│  草稿   │               │
└─────────┘               │
     │                    │
     │ confirm           │ revert
     │ (确定)            │ (恢复草稿)
     ↓                    │
┌───────────┐             │
│ CONFIRMED │ ────────────┘
│ 已确定     │
└───────────┘
```

### 状态限制规则

| 状态 | 可编辑 | 可添加数据 | 可移除数据 | 可确定 | 可恢复草稿 |
|------|--------|-----------|-----------|--------|-----------|
| DRAFT | ✅ | ✅ | ✅ | ✅* | ❌ |
| CONFIRMED | ❌ | ❌ | ❌ | ❌ | ✅ |

*注：确定前提条件：必须包含至少 1 条原始数据

## 🎨 UI 组件示例

### 状态徽章

```tsx
import { DataSourceStatus, STATUS_LABELS } from '@/types/data-source.types';

function StatusBadge({ status }: { status: DataSourceStatus }) {
  const color = status === DataSourceStatus.DRAFT ? 'blue' : 'green';
  const label = STATUS_LABELS[status];

  return (
    <span className={`badge badge-${color}`}>
      {label}
    </span>
  );
}
```

### 数据源卡片

```tsx
import type { DataSourceSummary } from '@/types/data-source.types';
import { STATUS_LABELS, TYPE_LABELS } from '@/types/data-source.types';

function DataSourceCard({ dataSource }: { dataSource: DataSourceSummary }) {
  return (
    <div className="card">
      <h3>{dataSource.title}</h3>
      <p>{dataSource.description}</p>

      <div className="meta">
        <span className="badge">{STATUS_LABELS[dataSource.status]}</span>
        <span className="label">{TYPE_LABELS[dataSource.source_type]}</span>
        <span className="count">数据: {dataSource.total_raw_data_count}</span>
      </div>

      <div className="tags">
        {dataSource.tags.map(tag => (
          <span key={tag} className="tag">{tag}</span>
        ))}
      </div>

      <div className="footer">
        创建于: {new Date(dataSource.created_at).toLocaleDateString()}
      </div>
    </div>
  );
}
```

## 📝 表单验证

### Zod Schema 示例

```typescript
import { z } from 'zod';
import type { CreateDataSourceRequest } from '@/types/data-source.types';

// 创建数据源表单验证
export const createDataSourceSchema = z.object({
  title: z.string()
    .min(1, '标题不能为空')
    .max(200, '标题长度不能超过200字符'),
  description: z.string()
    .max(1000, '描述长度不能超过1000字符')
    .optional(),
  created_by: z.string().min(1, '创建者不能为空'),
  tags: z.array(z.string()).optional(),
  metadata: z.record(z.any()).optional()
}) satisfies z.ZodType<CreateDataSourceRequest>;

// 使用
const formData = {
  title: 'Test',
  description: 'Description',
  created_by: 'user123'
};

try {
  const validated = createDataSourceSchema.parse(formData);
  // 验证通过，提交数据
} catch (error) {
  // 验证失败，显示错误
  console.error(error);
}
```

## 🔗 API 路径常量

```typescript
import { API_PATHS } from '@/types/data-source.types';

// 使用预定义的路径
const createUrl = API_PATHS.CREATE;                    // "/api/v1/data-sources/"
const detailUrl = API_PATHS.GET('123');               // "/api/v1/data-sources/123"
const updateUrl = API_PATHS.UPDATE_INFO('123');       // "/api/v1/data-sources/123/info"
const confirmUrl = API_PATHS.CONFIRM('123');          // "/api/v1/data-sources/123/confirm"
```

## 🚨 错误处理

### 统一错误处理

```typescript
import type { ApiResponse } from '@/types/data-source.types';
import { isSuccessResponse, isErrorResponse } from '@/types/data-source.types';

async function handleApiCall<T>(
  apiCall: () => Promise<ApiResponse<T>>
): Promise<T | null> {
  try {
    const response = await apiCall();

    if (isSuccessResponse(response)) {
      return response.data ?? null;
    } else if (isErrorResponse(response)) {
      console.error('API 错误:', response.detail);
      return null;
    }
  } catch (error) {
    console.error('网络错误:', error);
    return null;
  }

  return null;
}

// 使用
const dataSource = await handleApiCall(() =>
  dataSourceApi.getDataSource('123')
);
```

## 📚 相关文档

- **后端 API 文档**: http://localhost:8000/api/docs
- **OpenAPI Specification**: http://localhost:8000/api/openapi.json
- **数据源实体定义**: `/src/core/domain/entities/data_source.py`
- **API 端点实现**: `/src/api/v1/endpoints/data_source_management.py`

## 🔄 版本更新

### v1.1.0 (2025-10-30)
- ✅ 新增分类功能：三级分类体系（primary/secondary/tertiary_category）
- ✅ 新增自定义标签：custom_tags 字段
- ✅ 新增分类工具函数：formatCategoryPath、getAllTags
- ✅ 更新 API 查询：支持按分类筛选
- ✅ 更新文档：添加分类功能完整示例

### v1.0.0 (2025-10-30)
- ✅ 初始版本
- ✅ 完整的类型定义
- ✅ React/Vue 使用示例
- ✅ 工具函数和类型守卫
- ✅ UI 组件示例

## 📮 反馈与支持

如有问题或建议，请联系后端团队或提交 Issue。

---

**生成时间**: 2025-10-30
**后端版本**: v1.4.0
**API Base URL**: http://localhost:8000/api/v1
