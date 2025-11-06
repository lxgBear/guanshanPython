# processed_results_new → news_results 表迁移总结

**日期**: 2025-11-05
**版本**: v2.0.2
**执行人**: Claude Code
**状态**: ✅ 已完成

**最新更新**: v2.0.3 - 新增 media_urls 字段 (2025-11-05) → 详见 `NEWS_RESULTS_V2.0.3_UPDATE_2025-11-05.md`

---

## 一、迁移目标

将架构文档和代码中的 `processed_results_new` 表名统一更新为 `news_results`，并根据数据库中实际的 `news_results` 表字段结构更新实体定义。

---

## 二、执行步骤

### 1. 数据库字段分析 ✅

**方法**: 创建 Python 脚本查询 `news_results` 集合

**脚本**: `scripts/get_news_results_schema.py`

**发现的字段结构**:
```json
{
  "_id": "244036665001316352",
  "task_id": "244028887716896768",
  "title": "Voice of the Voiceless - Tibet Post International",
  "url": "https://www.thetibetpost.com/",
  "snippet": "## Sidebar...",
  "source": "crawl",
  "published_date": null,
  "author": null,
  "language": null,
  "markdown_content": "## Sidebar...",
  "html_content": null,
  "article_tag": null,
  "article_published_time": null,
  "source_url": null,
  "http_status_code": null,
  "search_position": null,
  "metadata": { ... },
  "relevance_score": 1.0,
  "quality_score": 0.0,
  "status": "pending",
  "created_at": "2025-11-04 09:54:34.918000",
  "processed_at": null,
  "is_test_data": false,

  // 🆕 新增字段（news_results特有）
  "news_results": {
    "title": "西藏问题引发国际关注与抗议",
    "published_at": "2023-10-23 00:00:00",
    "source": "thetibetpost.com",
    "content": "达兰萨拉——在建设连接成都与拉萨的铁路过程中...",
    "category": {
      "大类": "安全情报",
      "类别": "维稳",
      "地域": "东亚"
    }
  },
  "content_cleaned": "Dharamshala — While constructing...",
  "processing_status": "success"
}
```

**关键发现**:
- ✅ 表中已有 26 条记录
- ✅ 新增 `news_results` 嵌套字段（包含翻译后的新闻内容和分类）
- ✅ 新增 `content_cleaned` 字段（清理后的英文原文）
- ✅ 保留所有原始 `ProcessedResult` 字段

---

### 2. 实体定义更新 ✅

**文件**: `src/core/domain/entities/processed_result.py`

**修改内容**:

1. **更新文档注释**:
```python
v2.0.2 字段更新（基于 news_results 表实际结构）：
- 添加 news_results 嵌套字段（title, published_at, source, content, category）
- 添加 content_cleaned 字段（清理后的内容）
- 保留所有原始字段以确保向后兼容
```

2. **新增字段**:
```python
# ==================== news_results 嵌套字段（v2.0.2 新增）====================
news_results: Optional[Dict[str, Any]] = None  # AI处理后的新闻结果
# news_results 结构示例：
# {
#     "title": "新闻标题（翻译后）",
#     "published_at": datetime(2023, 10, 23),
#     "source": "来源域名",
#     "content": "新闻内容（翻译后）",
#     "category": {
#         "大类": "安全情报",
#         "类别": "维稳",
#         "地域": "东亚"
#     }
# }

# ==================== 内容清理字段（v2.0.2 新增）====================
content_cleaned: Optional[str] = None  # 清理后的英文原文内容
```

---

### 3. Repository 更新 ✅

**文件**: `src/infrastructure/database/processed_result_repositories.py`

**修改内容**:

1. **更新集合名称**:
```python
def __init__(self):
    self.collection_name = "news_results"  # 从 "processed_results_new" 更改
```

2. **更新文档注释**:
```python
v2.0.2 表名更新：
- 集合名从 processed_results_new 更新为 news_results
- 添加 news_results 嵌套字段和 content_cleaned 字段支持
```

3. **扩展字段映射**:

在 `_result_to_dict()` 方法中添加:
```python
# news_results嵌套字段（v2.0.2）
"news_results": result.news_results,
# 内容清理字段（v2.0.2）
"content_cleaned": result.content_cleaned
```

在 `_dict_to_result()` 方法中添加:
```python
# news_results嵌套字段（v2.0.2）
news_results=data.get("news_results"),
# 内容清理字段（v2.0.2）
content_cleaned=data.get("content_cleaned")
```

---

### 4. 文档更新 ✅

**批量替换命令**:
```bash
# docs 目录
find docs -name "*.md" -type f -exec sed -i '' 's/processed_results_new/news_results/g' {} \;

# claudedocs 目录
find claudedocs -name "*.md" -type f -exec sed -i '' 's/processed_results_new/news_results/g' {} \;
```

**更新的文档**:
1. ✅ `docs/SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md` - 架构设计文档
2. ✅ `docs/DATABASE_COLLECTIONS_GUIDE.md` - 数据库集合指南
3. ✅ `docs/README.md` - 主文档索引
4. ✅ `docs/SYSTEM_ARCHITECTURE.md` - 系统架构文档
5. ✅ `docs/SEARCH_RESULTS_IMPLEMENTATION_GUIDE.md` - 实施指南
6. ✅ `docs/INSTANT_SEARCH_MIGRATION_PLAN.md` - 即时搜索迁移计划
7. ✅ `claudedocs/*.md` - 所有 Claude 工作文档

---

## 三、验证结果

### 代码验证 ✅

```bash
# 检查核心代码中的引用
grep -r "processed_results_new" src/infrastructure/database/*.py src/core/domain/entities/*.py

# 结果：只剩注释中的历史说明
src/infrastructure/database/processed_result_repositories.py:- 集合名从 processed_results_new 更新为 news_results
```

**验证结论**: ✅ 所有代码引用已更新，仅保留版本说明注释

### 数据库验证 ✅

- ✅ `news_results` 集合已存在
- ✅ 包含 26 条记录
- ✅ 字段结构与实体定义匹配

---

## 四、向后兼容性

### 保留的字段 ✅

所有 v2.0.1 的字段均已保留：
- ✅ 原始字段（title, url, content 等）
- ✅ AI 处理字段（content_zh, cls_results 等）
- ✅ 用户操作字段（status, user_rating 等）
- ✅ 时间戳字段（created_at, processed_at, updated_at）

### 新增字段 ✅

v2.0.2 新增字段为可选（Optional），不影响现有数据：
- ✅ `news_results: Optional[Dict[str, Any]] = None`
- ✅ `content_cleaned: Optional[str] = None`

---

## 五、影响范围

### 已更新的组件 ✅

1. **实体层**:
   - ✅ `src/core/domain/entities/processed_result.py`

2. **数据访问层**:
   - ✅ `src/infrastructure/database/processed_result_repositories.py`

3. **文档**:
   - ✅ 所有架构文档（7个文件）
   - ✅ 所有工作文档（claudedocs 目录）

### 不需要修改的组件

1. **API 层**:
   - ℹ️ API 端点已经通过 Repository 间接访问，无需修改

2. **服务层**:
   - ℹ️ 服务层使用 Repository 接口，无需修改

3. **前端**:
   - ℹ️ 前端通过 API 访问，字段名称保持一致，无需修改

---

## 六、测试建议

### 功能测试

```python
# 1. 测试读取 news_results
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository

repo = ProcessedResultRepository()
result = await repo.get_by_id("244036665001316352")

# 验证新字段
assert result.news_results is not None
assert result.news_results["title"] == "西藏问题引发国际关注与抗议"
assert result.content_cleaned is not None

# 2. 测试创建记录
new_result = await repo.create_pending_result(
    raw_result_id="test_id",
    task_id="test_task"
)
assert new_result.id is not None
```

### 集成测试

```bash
# 启动服务并验证
python scripts/get_news_results_schema.py

# 预期输出
✅ news_results 集合存在
📊 news_results 表字段结构（基于样例文档）
...
```

---

## 七、后续工作

### 数据迁移（可选）

如果需要将旧的 `processed_results_new` 数据迁移到 `news_results`：

```python
# scripts/migrate_processed_to_news_results.py

async def migrate():
    """迁移 processed_results_new → news_results"""
    db = await get_mongodb_database()

    # 1. 检查是否存在旧集合
    if "processed_results_new" in await db.list_collection_names():
        # 2. 批量迁移数据
        old_collection = db.processed_results_new
        new_collection = db.news_results

        cursor = old_collection.find({})
        async for doc in cursor:
            # 添加新字段默认值
            doc["news_results"] = None
            doc["content_cleaned"] = None
            await new_collection.insert_one(doc)

        # 3. 验证迁移完成后删除旧集合
        # await db.drop_collection("processed_results_new")
```

### 索引优化（推荐）

```javascript
// 为 news_results 集合创建优化索引
db.news_results.createIndex({"task_id": 1, "status": 1, "created_at": -1});
db.news_results.createIndex({"news_results.category.大类": 1});
db.news_results.createIndex({"news_results.published_at": -1});
```

---

## 八、总结

### 完成的工作 ✅

1. ✅ 获取 `news_results` 表的实际字段结构（26个字段，26条记录）
2. ✅ 更新 `ProcessedResult` 实体定义（新增 2 个字段）
3. ✅ 更新 `ProcessedResultRepository` 集合名称和字段映射
4. ✅ 批量更新所有架构文档（7个文件）
5. ✅ 批量更新所有工作文档（claudedocs 目录）
6. ✅ 验证代码引用已全部更新

### 关键成果

- **表名统一**: `processed_results_new` → `news_results`
- **字段扩展**: 新增 `news_results` 嵌套字段和 `content_cleaned` 字段
- **向后兼容**: 所有原有字段保留，新字段为可选
- **文档同步**: 所有文档已更新，架构描述一致

### 数据统计

| 项目 | 数量 |
|------|------|
| 更新的实体文件 | 1 |
| 更新的 Repository 文件 | 1 |
| 更新的文档文件 | 13+ |
| 新增实体字段 | 2 |
| 数据库记录数 | 26 |
| 数据库字段数 | 26 |

---

**执行时间**: 2025-11-05
**执行状态**: ✅ 已完成
**下一步**: 可选择执行数据迁移或索引优化
