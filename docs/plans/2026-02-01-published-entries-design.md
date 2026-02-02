# Published Entries 设计文档

## 概述

审核通过后，将内容从 `review_entries`（草稿表）移到新的 `published_entries`（发布表），并物理删除草稿记录。

## 数据模型

### PublishedEntry 实体

集合名：`published_entries`

**内容字段（从草稿复制）：**
- `id` - 新的雪花ID
- `title`、`description`、`summary`、`combined_content`
- `tags`、`primary_category`、`secondary_category`、`tertiary_category`
- `entry_type` (single/batch)
- `raw_data_refs`、`raw_data_count`

**审核溯源字段：**
- `author_id` - 原始创建者
- `reviewer_id` - 审核员
- `review_comment` - 审核意见
- `submitted_at` - 提交审核时间
- `reviewed_at` - 审核通过时间

**新表独有字段：**
- `status` - published / archived
- `published_at` - 发布时间
- `created_at`、`updated_at`

## 审核通过流程

1. 权限校验和状态校验（不变）
2. 读取 `review_entries` 完整数据
3. 创建 `PublishedEntry` 写入 `published_entries`
4. 物理删除 `review_entries` 中的记录
5. 返回 `PublishedEntryResponse`

**安全机制：** 先插入后删除，插入失败不删除。

## API 接口

- `POST /api/v1/review-entries/{id}/approve` - 改为返回 `PublishedEntryResponse`
- `GET /api/v1/published-entries/` - 列表（支持分页、筛选、搜索）
- `GET /api/v1/published-entries/{id}` - 详情

## 文件变更

1. `src/core/domain/entities/published_entry.py` - 新建实体
2. `src/infrastructure/persistence/repositories/mongo/published_entry_repository.py` - 新建仓储
3. `src/api/v1/endpoints/published_entries.py` - 新建 API
4. `src/api/v1/endpoints/review_entries.py` - 修改 approve 逻辑
5. `src/main.py` - 注册新路由
6. `src/infrastructure/database/connection.py` - 添加索引
