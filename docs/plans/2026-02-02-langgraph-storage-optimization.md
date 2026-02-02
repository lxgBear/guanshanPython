# LangGraph 搜索结果存储优化设计

## 概述

优化 gs-ai-crawl 返回数据保存到 `langgraph_search_results` 表的逻辑：
1. **移除 html_content 字段** - 完全移除，不再存储 HTML 内容
2. **过滤空 markdown 记录** - 如果 `markdown_content` 为空，不保存该记录

## 变更范围

### 1. 数据实体层

**文件**: `src/core/domain/entities/search_result.py`
- 移除 `html_content` 字段定义

**文件**: `src/core/domain/entities/langgraph_search_result.py`
- 继承父类变更，无需额外修改

### 2. Repository 层

**文件**: `src/infrastructure/persistence/repositories/mongo/langgraph_result_repository.py`
- `_result_to_dict()`: 移除 `html_content` 字段映射
- `_dict_to_result()`: 移除 `html_content` 字段读取（兼容旧数据时忽略）

### 3. 数据转换层

**文件**: `src/services/langgraph_search/gsac_engine.py`
- `_convert_results()`: 移除 `html` 字段返回

**文件**: `src/services/layers/search_engine_layer.py`
- `_convert_to_langgraph_results()`:
  - 移除 `html_content` 赋值
  - 添加 markdown 为空过滤逻辑

**文件**: `src/services/langgraph_search/converters/result_converter.py`
- `to_db_entity()`: 移除 `html_content` 赋值
- `from_db_entity()`: 移除 `html_content` 读取
- `to_api_response()`: 移除 `html_content` 返回

**文件**: `src/services/langgraph_search/converters/output_adapter.py`
- `adapt_result_item()`: 移除 `html_content` 字段处理

### 4. 影响的其他转换器

**文件**: `src/services/langgraph_search/converters/aggregated_converter.py`
- 检查是否使用 `html_content`，如有则移除

## 实现细节

### markdown 为空过滤逻辑

在 `_convert_to_langgraph_results()` 方法中添加过滤：

```python
def _convert_to_langgraph_results(self, raw_results, ...):
    results = []
    for idx, raw in enumerate(raw_results):
        # 获取 markdown 内容
        markdown_content = raw.get("markdown") or raw.get("content")

        # 过滤：markdown 为空则跳过
        if not markdown_content or not markdown_content.strip():
            logger.debug(f"[SearchEngineLayer] Skipping result without markdown: {raw.get('url')}")
            continue

        # 创建实体（不含 html_content）
        result = LangGraphSearchResult(
            ...
            markdown_content=markdown_content,
            # html_content 已移除
        )
        results.append(result)
```

## 向后兼容性

- **数据库旧数据**: 已存在的 `html_content` 字段在读取时会被忽略
- **API 响应**: 不再返回 `html_content` 字段
- **前端**: 需确认前端是否依赖 `html_content` 字段（当前 DetailSheet 使用 iframe 加载原 URL，不依赖此字段）

### 5. API 响应层

**文件**: `src/api/v1/endpoints/langgraph_transfer.py`
- `LangGraphResultItem` 模型：移除 `has_html_content` 和 `html_content` 字段
- `get_langgraph_results()` 端点：移除响应中的 `html_content` 相关代码

### 6. LangGraph 内部状态

**文件**: `src/services/langgraph_search/state.py`
- `SearchResult` dataclass：移除 `html_content` 字段
- `to_dict()` 和 `from_dict()`：移除 `html_content` 序列化

### 7. 转移服务

**文件**: `src/services/langgraph_search/transfer_service.py`
- `_create_processed_result()`: 移除 `html_content` 赋值

## 测试计划

1. 单元测试：验证空 markdown 记录被过滤
2. 集成测试：验证 gs-ai-crawl 搜索后保存的记录不含 html_content
3. 回归测试：验证旧数据读取正常（忽略 html_content）

## 实施记录

- **v4.9.2** (2026-02-02): 完成所有变更，后端热加载验证通过
  - 实体层 `html_content` 字段已完全移除
  - Repository 可正常读取旧数据（忽略 `html_content`）
  - API 响应不再返回 `html_content` 字段
