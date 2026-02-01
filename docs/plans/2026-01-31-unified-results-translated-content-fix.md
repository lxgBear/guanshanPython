# 统一结果 API 翻译内容字段修复设计

## 背景

前端 `compile-v2` 信息处置中心需要显示翻译后的内容，但后端 `unified_results` API 没有正确返回 `translated_content` 字段。

## 问题分析

### 数据存储结构

`search_results` 集合中有一个嵌套字段 `news_results`，包含 AI 翻译后的内容：

```json
{
  "_id": "...",
  "title": "原始标题（英文）",
  "news_results": {
    "title": "翻译后的标题（中文）",
    "content": "翻译后的内容（中文）",
    "title_zh": "翻译后的标题（中文）",  // 备用字段
    "content_zh": "翻译后的内容（中文）"   // 备用字段
  },
  "translated_content": ""  // 顶层字段可能为空
}
```

### 问题所在

**文件**：`src/infrastructure/persistence/repositories/mongo/unified_result_repository.py`

**方法**：`_query_search_results`（第222-297行）

**现有代码**（第293行）：
```python
"translated_content": doc.get("translated_content", ""),
```

直接从顶层 `translated_content` 字段获取，但该字段可能为空。

### 正确实现参考

`info_entry_repository.py` 和 `review_entry_repository.py` 已经正确处理：

```python
news_results = doc.get("news_results", {}) or {}
translated_title = news_results.get("title_zh", "")
translated_content = news_results.get("content_zh", "")
```

## 修复方案

### 修改文件

`src/infrastructure/persistence/repositories/mongo/unified_result_repository.py`

### 修改内容

在 `_query_search_results` 方法中，修改翻译内容的获取逻辑：

**修改前**（第293行）：
```python
"translated_content": doc.get("translated_content", ""),
```

**修改后**：
```python
# 从 news_results 嵌套字段获取翻译内容
news_results = doc.get("news_results", {}) or {}
translated_content = (
    news_results.get("content_zh", "") or
    news_results.get("content", "") or
    doc.get("translated_content", "")
)

# ...在返回字典中使用：
"translated_content": translated_content,
```

### 完整修改

需要在构建返回字典之前添加 `news_results` 的解析逻辑，并将解析结果应用到返回值中。

## 影响范围

- **API 端点**：`GET /unified-results/`
- **前端页面**：`compile-v2` 信息处置中心
- **向后兼容**：是（只是增加了数据来源，不改变字段结构）

## 测试计划

1. 验证 API 返回的 `translated_content` 字段不为空
2. 验证前端信息处置中心能正确显示翻译内容
3. 验证原有功能不受影响

## 创建时间

2026-01-31
