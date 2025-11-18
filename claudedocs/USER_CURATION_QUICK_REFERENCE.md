# 用户精选工作流 - 快速参考指南

**版本**: v1.0.0
**日期**: 2025-11-17
**完整文档**: `USER_CURATION_WORKFLOW_REQUIREMENTS.md`

---

## 核心需求总结

### 问题
用户需要能够：
1. 查看AI处理后的news_results
2. **编辑字段修正AI错误**
3. **勾选编辑好的条目**
4. **保存到新表**

### 解决方案
新增**用户精选系统**，包括：
- 新表: `curated_search_results`
- 新接口: 11个API端点
- 完整工作流: 编辑 → 提交 → 审核 → 发布

---

## 新增文件清单

### 1. 实体层
```
src/core/domain/entities/curated_search_result.py
```
- `CuratedSearchResult` - 精选结果实体
- `CurationStatus` - 精选状态枚举
- `CategoryInfo` - 分类信息模型

### 2. Repository层
```
src/infrastructure/database/curated_result_repository.py
```
- CRUD操作
- 业务查询（按任务、按精选人、按状态）
- 状态更新
- 统计分析

### 3. Service层
```
src/services/curation_service.py
```
- `create_curated_result()` - 创建精选
- `update_curated_result()` - 更新精选
- `submit_for_review()` - 提交审核
- `approve_curated_result()` - 批准
- `publish_curated_result()` - 发布

### 4. API层
```
src/api/v1/endpoints/curation.py
```
11个端点（见下方API快速参考）

### 5. 数据库脚本
```
scripts/create_curation_indexes.py
```
创建7个MongoDB索引

### 6. 测试脚本
```
scripts/test_curation_workflow.py
```
完整工作流集成测试

---

## API快速参考

### 核心操作

| 端点 | 方法 | 说明 |
|------|------|------|
| `/curation/results` | POST | 创建精选记录 |
| `/curation/results/{id}` | GET | 获取精选详情 |
| `/curation/results/{id}` | PATCH | 更新精选记录 |
| `/curation/results/{id}` | DELETE | 删除精选记录 |

### 工作流操作

| 端点 | 方法 | 说明 |
|------|------|------|
| `/curation/results/{id}/submit` | POST | 提交审核 |
| `/curation/results/{id}/approve` | POST | 批准精选 |
| `/curation/results/{id}/reject` | POST | 拒绝精选 |
| `/curation/results/{id}/publish` | POST | 发布精选 |

### 查询操作

| 端点 | 方法 | 说明 |
|------|------|------|
| `/curation/tasks/{task_id}/results` | GET | 获取任务的精选列表 |
| `/curation/tasks/{task_id}/statistics` | GET | 获取精选统计 |

---

## 数据库Schema

### curated_search_results 集合

**核心字段**:
```python
id: str                          # 精选记录ID
original_result_id: str          # 原始结果ID（关联）
task_id: str                     # 任务ID
nl_search_log_id: Optional[str]  # NL搜索日志ID

# 用户编辑的内容
title: str                       # 精选标题
content: str                     # 精选内容
category: CategoryInfo           # 分类信息
tags: List[str]                  # 标签列表

# 精选管理
curation_status: CurationStatus  # 状态（draft/submitted/approved/rejected/published）
curator_id: str                  # 精选人ID
version: int                     # 版本号
edit_history: List[Dict]         # 编辑历史

# 审核信息
reviewed_by: Optional[str]       # 审核人ID
reviewed_at: Optional[datetime]  # 审核时间
review_notes: Optional[str]      # 审核意见
```

**索引** (7个):
1. `task_created_idx` - 任务查询
2. `status_created_idx` - 状态筛选
3. `curator_created_idx` - 精选人查询
4. `original_ref_idx` - 原始结果关联
5. `nl_search_idx` - NL搜索关联
6. `category_idx` - 分类查询
7. `fulltext_idx` - 全文搜索

---

## 工作流示例

### 用户操作流程

```
1. 查看AI结果
   GET /search-tasks/{task_id}/results
   ↓
2. 选择一条记录
   → 前端展示编辑表单
   ↓
3. 编辑字段
   - 修正标题
   - 调整内容
   - 修正分类
   ↓
4. 保存精选
   POST /curation/results
   Body: {
     "original_result_id": "...",
     "curator_id": "...",
     "title": "修正后的标题",
     "content": "修正后的内容",
     "category": {...},
     "tags": [...]
   }
   ↓
5. 提交审核（可选）
   POST /curation/results/{id}/submit
   ↓
6. 审核批准
   POST /curation/results/{id}/approve
   ↓
7. 发布
   POST /curation/results/{id}/publish
```

### 批量精选流程

```python
# 前端勾选多条记录
selected_ids = ["result_1", "result_2", "result_3"]

# 批量创建精选
for result_id in selected_ids:
    response = await post("/curation/results", {
        "original_result_id": result_id,
        "curator_id": "user_123",
        # ... 编辑的数据
    })
    curated_ids.append(response["id"])

# 批量发布
for curated_id in curated_ids:
    await post(f"/curation/results/{curated_id}/publish")
```

---

## 可编辑字段清单

### 核心内容字段 ✅
- `title_generated` - AI生成的标题
- `content_zh` - 中文翻译内容
- `news_results.title` - 最终标题
- `news_results.content` - 最终内容
- `news_results.category` - 分类信息
- `article_tag` - 文章标签

### 元数据字段 ✅
- `author` - 作者信息
- `published_date` - 发布日期
- `news_results.published_at` - 最终发布时间
- `news_results.source` - 来源信息

### 质量评估 ✅
- `user_rating` - 用户评分
- `user_notes` - 用户备注

### 不建议编辑 ❌
- `url` - 原始URL
- `content` - 原始内容
- `html_content` - 原始HTML
- `ai_model` - AI元数据
- `processing_status` - 处理状态

---

## 实施步骤

### 开发阶段 (10-13个工作日)

**阶段1**: 数据模型与Repository (2-3天)
- 创建实体和Repository
- 创建索引
- 单元测试

**阶段2**: Service层 (1-2天)
- 实现业务逻辑
- 单元测试

**阶段3**: API层 (2-3天)
- 实现API端点
- 集成测试

**阶段4**: 集成测试 (1天)
- 完整工作流测试
- 性能测试

**阶段5**: 文档与部署 (1天)
- API文档
- 用户手册

### 部署步骤

1. **创建索引**
   ```bash
   python scripts/create_curation_indexes.py
   ```

2. **运行测试**
   ```bash
   python scripts/test_curation_workflow.py
   ```

3. **注册Router**
   - 修改 `src/api/v1/router.py`
   - 添加 `curation.router`

4. **启动服务**
   ```bash
   uvicorn src.main:app --reload
   ```

---

## 关键设计决策

### 1. 为什么要新建表？
- **数据独立性**: 精选内容与AI结果解耦
- **版本控制**: 支持编辑历史和版本管理
- **审核流程**: 支持多状态工作流
- **查询性能**: 独立索引优化精选内容查询

### 2. 为什么保留原始数据快照？
- 允许对比原始AI结果和用户编辑
- 支持回滚到原始版本
- 分析用户修正模式以改进AI

### 3. 为什么需要审核流程？
- 质量控制：确保精选内容质量
- 责任追溯：明确创建者和审核者
- 灵活配置：可选启用/禁用审核

---

## 常见问题

**Q1: 用户可以编辑哪些字段？**
A: 核心内容字段（标题、内容、分类、标签）和元数据字段，不能编辑原始URL和AI元数据。

**Q2: 如果原始结果被删除了怎么办？**
A: 精选记录保留了原始数据快照，删除原始结果不影响精选内容。

**Q3: 是否必须经过审核？**
A: 审核流程是可选的，可以直接从DRAFT状态发布到PUBLISHED。

**Q4: 如何处理并发编辑？**
A: 使用版本号（version字段）实现乐观锁，检测并发冲突。

**Q5: 编辑历史会一直保留吗？**
A: 默认保留所有历史，可定期归档旧版本历史以控制存储成本。

---

## 技术栈

- **数据库**: MongoDB (curated_search_results集合)
- **后端**: FastAPI + Motor (异步MongoDB驱动)
- **数据验证**: Pydantic
- **ID生成**: 雪花算法（Snowflake）
- **架构模式**: Repository + Service + API三层架构

---

## 相关文档

- 📄 **完整需求文档**: `USER_CURATION_WORKFLOW_REQUIREMENTS.md`
- 📄 **NL Search完成报告**: `NL_SEARCH_COMPLETION_2025-11-17.md`
- 📄 **API文档**: FastAPI自动生成 `/docs`

---

**最后更新**: 2025-11-17
**维护人员**: Backend Team
