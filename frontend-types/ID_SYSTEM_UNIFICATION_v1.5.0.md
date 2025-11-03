# ID系统统一 - v1.5.0 雪花算法迁移

**迁移日期**: 2025-10-31
**版本**: v1.5.0
**影响范围**: 所有实体ID字段

---

## 概述

v1.5.0 版本完成了系统范围的 ID 统一，所有实体统一使用**雪花算法 (Snowflake ID)** 生成唯一标识符，移除了旧的 UUID 格式。

## ID 格式说明

### 雪花算法 ID (Snowflake ID)

**特征**:
- 纯数字字符串
- 长度: 15-19 位
- 时间有序 (可按时间排序)
- 分布式友好 (支持高并发和多节点部署)
- 全局唯一

**示例**:
```typescript
"242547193395171328"  // 有效的雪花ID
"238931083865448448"  // 有效的雪花ID
```

### 旧 UUID 格式 (已废弃)

**特征**:
- 包含横杠 `-`
- 格式: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- 不再使用

**示例**:
```typescript
"7c2a1e9e-e92e-4325-bd81-c8c3e29df0c5"  // ❌ 已废弃，不再支持
"0b75c1a7-2fc0-58a8-8ee6-6dcebe4d85d3"  // ❌ 已废弃，不再支持
```

---

## 前端开发指南

### TypeScript 类型定义

所有 ID 字段都是 `string` 类型 (雪花ID格式):

```typescript
// ✅ 正确：所有ID都是雪花算法生成的字符串
interface DataSource {
  id: string;  // 雪花ID: "242547193395171328"
  // ...
}

interface RawDataReference {
  data_id: string;  // 雪花ID: "238931083865448448"
  data_type: 'scheduled' | 'instant';
  // ...
}

interface AddRawDataRequest {
  data_id: string;  // 雪花ID: "242540877529686016"
  data_type: 'scheduled' | 'instant';
  added_by: string;
}
```

### ID 验证函数

```typescript
/**
 * 检查是否为有效的雪花ID格式
 */
function isValidSnowflakeId(id: string): boolean {
  // 雪花ID特征：纯数字且长度在15-19位之间
  return /^\d{15,19}$/.test(id);
}

/**
 * 检查是否为旧UUID格式（已废弃）
 */
function isDeprecatedUUID(id: string): boolean {
  // UUID特征：包含横杠
  return id.includes('-');
}

// 使用示例
const dataId = "242547193395171328";

if (isValidSnowflakeId(dataId)) {
  console.log("✅ 有效的雪花ID");
} else if (isDeprecatedUUID(dataId)) {
  console.warn("⚠️ 检测到旧UUID格式，请联系后端升级");
} else {
  console.error("❌ 无效的ID格式");
}
```

### 数据类型检测 (已移除)

**v1.4.2 之前**: 后端有智能ID检测逻辑，自动纠正 `data_type` 不匹配的情况。

**v1.5.0 之后**: 所有ID统一为雪花格式，不再需要智能检测。前端直接根据数据来源设置 `data_type`:

```typescript
// ✅ v1.5.0: 直接根据来源设置data_type
interface AddRawDataRequest {
  data_id: string;  // 雪花ID（统一格式）
  data_type: 'scheduled' | 'instant';  // 根据数据来源设置
  added_by: string;
}

// 示例：从定时搜索任务添加数据
const scheduledData: AddRawDataRequest = {
  data_id: "242547193395171328",  // 雪花ID
  data_type: "scheduled",  // 定时搜索类型
  added_by: "user123"
};

// 示例：从即时搜索添加数据
const instantData: AddRawDataRequest = {
  data_id: "242540877529686016",  // 雪花ID
  data_type: "instant",  // 即时搜索类型
  added_by: "user123"
};
```

---

## API 请求示例

### 添加原始数据到数据源

```typescript
// POST /api/v1/data-sources/{data_source_id}/raw-data
const request: AddRawDataRequest = {
  data_id: "242547193395171328",  // 雪花ID（定时搜索结果）
  data_type: "scheduled",
  added_by: "user123"
};

// 或

const request: AddRawDataRequest = {
  data_id: "242540877529686016",  // 雪花ID（即时搜索结果）
  data_type: "instant",
  added_by: "user123"
};
```

### 移除原始数据

```typescript
// DELETE /api/v1/data-sources/{data_source_id}/raw-data
const request: RemoveRawDataRequest = {
  data_id: "242547193395171328",  // 雪花ID
  data_type: "scheduled",
  removed_by: "user123"
};
```

### 批量操作

```typescript
// POST /api/v1/data-sources/batch/archive
const request: BatchOperationRequest = {
  data_ids: [
    "242547193395171328",
    "242540877529686016",
    "238931083865448448"
  ],  // 所有ID都是雪花格式
  data_type: "instant",
  operator: "user123"
};
```

---

## 数据来源与 data_type 映射

### scheduled (定时搜索)
- **集合**: `search_results`
- **ID格式**: 雪花ID
- **特征**: 来自定时搜索任务 (SearchTask)
- **示例**: `"242547193395171328"`

### instant (即时搜索)
- **集合**: `instant_search_results`
- **ID格式**: 雪花ID
- **特征**: 来自用户即时搜索
- **示例**: `"242540877529686016"`

---

## 迁移影响总结

### 后端变更 (v1.5.0)

1. ✅ **核心实体统一**:
   - `SearchResult`: `id`, `task_id` 改为雪花ID
   - `SearchTask`: `id` 完全使用雪花ID（移除UUID fallback）
   - `SearchResultBatch`: `id`, `task_id` 改为雪花ID

2. ✅ **服务层简化**:
   - 移除 `_detect_data_type_from_id()` 智能检测方法
   - 移除智能纠正逻辑
   - 直接根据 `data_type` 决定查询集合

3. ✅ **API层保持兼容**:
   - 所有请求/响应已使用 `str` 类型
   - 无需修改API端点
   - 文档已更新雪花ID示例

### 前端变更 (建议)

1. ✅ **TypeScript类型已兼容**:
   - 所有ID字段已定义为 `string` 类型
   - 无需修改类型定义

2. ⚠️ **移除旧代码** (如果存在):
   - 移除UUID格式检测逻辑
   - 移除ID格式自动纠正逻辑
   - 直接使用雪花ID

3. 💡 **最佳实践**:
   - 添加雪花ID验证函数 (可选)
   - 显示时可保持原样 (纯数字字符串)
   - 排序时按字符串比较 (雪花ID时间有序)

---

## 常见问题 (FAQ)

### Q1: 如何区分 scheduled 和 instant 类型？

**A**: 根据数据来源确定：
- 来自定时搜索任务 (SearchTask) → `scheduled`
- 来自用户即时搜索 → `instant`

### Q2: 雪花ID可以直接用于URL参数吗？

**A**: 可以。雪花ID是纯数字字符串，无需URL编码。

```typescript
// ✅ 直接使用
const url = `/api/v1/data-sources/${dataSourceId}`;  // dataSourceId = "242547193395171328"
```

### Q3: 雪花ID可以用于前端显示吗？

**A**: 可以，但建议截断显示或使用友好格式：

```typescript
function formatId(id: string): string {
  // 显示前8位 + 省略号 + 后4位
  if (id.length > 12) {
    return `${id.slice(0, 8)}...${id.slice(-4)}`;
  }
  return id;
}

// 示例
formatId("242547193395171328");  // "24254719...1328"
```

### Q4: 如何处理旧数据中的UUID？

**A**: v1.5.0 部署时所有MongoDB集合为空，无历史UUID数据。新系统完全使用雪花ID。

### Q5: 雪花ID是否支持排序？

**A**: 是的。雪花ID包含时间戳信息，按字典序排序等同于按时间排序。

```typescript
const ids = ["242547193395171328", "238931083865448448"];
ids.sort();  // 自动按时间顺序排列
```

---

## 技术参考

- **雪花算法**: Twitter开源的分布式ID生成算法
- **生成器**: `src.infrastructure.id_generator.generate_string_id()`
- **验证规则**: 纯数字字符串 && 长度15-19位
- **文档**: 详见 `src/core/domain/entities/search_result.py` v1.5.0注释

---

**变更历史**:

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.4.2 | 2025-10-31 | 添加智能ID检测（临时方案） |
| v1.5.0 | 2025-10-31 | 统一雪花算法ID，移除UUID |

**相关文档**:
- `docs/BUG_FIX_RAW_DATA_TYPE_DETECTION.md` - v1.4.2 智能检测方案（已被v1.5.0取代）
- `src/core/domain/entities/` - 核心实体定义
- `frontend-types/data-source.types.ts` - TypeScript类型定义
