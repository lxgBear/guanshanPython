# 数据整编流程 - 后端实现详细设计

**版本**: v2.2 (状态同步版)
**文档类型**: 后端技术实现
**负责范围**: API设计、服务层逻辑、数据验证、业务流程
**不包含**: 前端UI、用户交互、视觉设计

**⚠️ 重要说明**:
- 数据源功能与智能总结报告**完全隔离**，作为独立功能存在
- 数据源操作**会同步影响原始数据状态**（使用事务保证一致性）

---

## 目录

1. [架构简化说明](#1-架构简化说明)
2. [核心业务流程](#2-核心业务流程)
3. [状态机设计](#3-状态机设计)
4. [API详细设计](#4-api详细设计)
5. [服务层实现](#5-服务层实现)
6. [数据验证规则](#6-数据验证规则)
7. [错误处理策略](#7-错误处理策略)
8. [性能优化](#8-性能优化)
9. [测试策略](#9-测试策略)

---

## 0. 数据源存档系统

**版本**: v1.0
**状态**: ✅ 已实施完成 

### 0.1 概述

数据源存档系统确保已确认数据源拥有独立的完整数据副本，不受原始数据表清理影响。在数据源确认（DRAFT → CONFIRMED）时自动存档完整原始数据到独立存档表。

**详细文档**: [数据源存档系统完整指南](ARCHIVED_DATA_GUIDE.md)
- 完整技术方案（需求分析、方案对比、数据模型）
- UML图表（类图、序列图、组件图）
- API文档和使用示例
- 部署指南和性能优化
- 故障排查和测试策略

---

## 1. 核心设计说明

### 1.1 状态同步机制

**核心特性**：数据源状态与原始数据状态**自动同步**，通过MongoDB事务保证一致性。

| 操作 | 数据源状态变化 | 原始数据状态变化 | 说明 |
|------|---------------|-----------------|------|
| 创建数据源 | → draft（待审核） | → processing（处理中） | 事务保证同步 |
| 确定/通过数据源 | draft → confirmed（已通过） | processing → completed（已完成） | 事务保证同步 |
| 删除数据源 | 删除记录 | confirmed时: 保持completed<br>draft时: → archived（已留存） | 事务保证同步 |
| 退回待处理 | confirmed → draft | completed → processing | 事务保证同步 |

### 1.2 设计优势

1. **状态一致性**：事务机制保证数据源和原始数据状态始终同步
2. **清晰的生命周期**：draft（待审核）→ confirmed（已通过），状态转换明确
3. **独立性强**：数据源作为独立内容库，不依赖报告系统
4. **支持回退**：confirmed可以退回draft状态，支持反复修改

---

## 2. 核心业务流程

### 2.1 整编流程概述

**业务目标**: 将多条原始数据（search_results/instant_search_results）整合为一条高质量数据源（data_source），作为独立内容库

**核心步骤（含状态同步）**:
```
步骤1: 用户选择原始数据 → 创建数据源
      ├─ 数据源状态: draft（待审核）
      └─ 原始数据状态: pending/archived → processing（处理中）【事务】
      ↓
步骤2: 编辑内容、添加/移除原始数据 → 保存草稿
      ├─ 添加原始数据: 新数据 → processing【事务】
      └─ 移除原始数据: processing → archived【事务】
      ↓
步骤3: 确定/通过数据源
      ├─ 数据源状态: draft → confirmed（已通过）
      └─ 原始数据状态: processing → completed（已完成）【事务】
      ↓
步骤4: 如需修改 → 退回待处理
      ├─ 数据源状态: confirmed → draft
      └─ 原始数据状态: completed → processing【事务】
      ↓
步骤5: 重复步骤2-4，直到满意
      ↓
步骤6: 删除数据源
      ├─ draft状态删除: 原始数据 → archived【事务】
      └─ confirmed状态删除: 原始数据保持completed
```

**关键点**:
- ✅ 原始数据状态**与数据源操作同步**（通过MongoDB事务保证一致性）
- ✅ 数据源状态可以**反复切换**（draft ⇄ confirmed）
- ✅ 数据源作为**独立内容库**，不关联到报告系统

### 2.2 关键约束

#### 2.2.1 状态约束
- **原始数据**:
  - 5个状态：pending, archived, processing, completed, deleted
  - **数据源操作会自动同步状态**（通过事务保证）
  - 批量操作可独立改变状态（留存/删除）
  - `processing`和`completed`状态的数据不能被删除

- **数据源**:
  - 只有2个状态：`draft`（待审核）、`confirmed`（已通过）
  - `draft` 状态：可以修改内容、添加/移除原始数据
  - `confirmed` 状态：可以查看、下载原始数据，可以退回到draft

#### 2.2.2 状态转换规则（事务保证）
- **创建数据源**：原始数据 pending/archived → processing
- **确定数据源**：原始数据 processing → completed
- **退回待处理**：原始数据 completed → processing
- **删除draft数据源**：原始数据 processing → archived
- **删除confirmed数据源**：原始数据保持completed（不回退）

#### 2.2.3 数据完整性
- 所有状态变更必须在MongoDB事务中完成，保证原子性
- 原始数据被删除后，数据源保留引用但标记为"源数据已删除"
- draft状态可以随时添加或移除原始数据引用（同步状态）

#### 2.2.4 与报告系统隔离
- 数据源不自动关联到Summary Report
- 数据源作为独立内容库存在
- 未来如需在报告中使用，由用户显式选择（后续功能）

---

## 3. 状态机设计

### 3.1 原始数据状态机（含数据源同步逻辑）

```python
class ResultStatus(Enum):
    """原始数据状态枚举"""
    PENDING = "pending"         # 初始状态：刚采集
    ARCHIVED = "archived"       # 已留存继续：用户标记重要
    PROCESSING = "processing"   # 处理中：数据源正在整编
    COMPLETED = "completed"     # 已完成：数据源已确定
    DELETED = "deleted"         # 已删除：软删除
```

**状态转换规则**（含数据源自动同步）:
```
# 手动操作（独立批量操作）
pending → archived      允许（用户批量留存）
pending → deleted       允许（用户批量删除）
archived → deleted      允许（用户批量删除）

# 数据源自动同步（事务保证）
pending/archived → processing    数据源创建/添加原始数据时自动触发
processing → completed           数据源确定时自动触发
completed → processing           数据源退回待处理时自动触发
processing → archived            draft数据源删除时自动触发

# 终态
deleted → X                      禁止（终态）
```

**重要**: `processing` 和 `completed` 状态由数据源操作自动管理，用户不能手动设置。

### 3.2 数据源状态机（含状态同步）

```python
class DataSourceStatus(Enum):
    """数据源状态枚举"""
    DRAFT = "draft"             # 待审核：可编辑
    CONFIRMED = "confirmed"     # 已通过：可查看、下载、退回
```

**状态转换规则**（双向，含原始数据同步）:
```
draft → confirmed       允许（确定数据源）
                       ├─ 数据源状态: draft → confirmed
                       └─ 原始数据状态: processing → completed【事务】

confirmed → draft       允许（退回待处理）
                       ├─ 数据源状态: confirmed → draft
                       └─ 原始数据状态: completed → processing【事务】
```

**实体验证方法**（含状态同步逻辑）:
```python
class DataSource:
    """数据源实体"""

    def can_edit(self) -> bool:
        """是否可以编辑"""
        return self.status == DataSourceStatus.DRAFT

    def can_confirm(self) -> bool:
        """是否可以确定"""
        return self.status == DataSourceStatus.DRAFT

    def can_revert_to_draft(self) -> bool:
        """是否可以退回待处理"""
        return self.status == DataSourceStatus.CONFIRMED

    def confirm(self, confirmed_by: str) -> None:
        """确定数据源（仅更新数据源状态，原始数据状态由Repository层事务处理）"""
        if not self.can_confirm():
            raise ValidationError("只有draft状态可以确定")
        self.status = DataSourceStatus.CONFIRMED
        self.confirmed_at = datetime.utcnow()
        self.confirmed_by = confirmed_by
        self.updated_at = datetime.utcnow()
        # 注意：原始数据状态同步由Repository层在事务中处理

    def revert_to_draft(self) -> None:
        """退回待处理（仅更新数据源状态，原始数据状态由Repository层事务处理）"""
        if not self.can_revert_to_draft():
            raise ValidationError("只有confirmed状态可以退回")
        self.status = DataSourceStatus.DRAFT
        self.confirmed_at = None
        self.confirmed_by = None
        self.updated_at = datetime.utcnow()
        # 注意：原始数据状态同步由Repository层在事务中处理
```

### 3.3 状态同步验证规则

```python
class StatusSyncValidator:
    """状态同步验证器"""

    @staticmethod
    def validate_raw_data_for_create(raw_data_status: ResultStatus) -> None:
        """验证原始数据是否可以添加到数据源"""
        # 只有pending或archived状态的原始数据可以添加到数据源
        if raw_data_status not in [ResultStatus.PENDING, ResultStatus.ARCHIVED]:
            raise ValidationError(
                f"只有pending或archived状态的原始数据可以添加到数据源，当前状态: {raw_data_status}",
                error_code="INVALID_RAW_DATA_STATUS"
            )

    @staticmethod
    def validate_raw_data_for_delete(
        data_source_status: DataSourceStatus,
        raw_data_status: ResultStatus
    ) -> None:
        """验证原始数据删除时的状态转换"""
        # draft状态的数据源删除时，原始数据应该是processing状态
        if data_source_status == DataSourceStatus.DRAFT:
            if raw_data_status != ResultStatus.PROCESSING:
                raise ValidationError(
                    f"draft数据源的原始数据应为processing状态，当前: {raw_data_status}"
                )
        # confirmed状态的数据源删除时，原始数据应该是completed状态且保持不变
        elif data_source_status == DataSourceStatus.CONFIRMED:
            if raw_data_status != ResultStatus.COMPLETED:
                raise ValidationError(
                    f"confirmed数据源的原始数据应为completed状态，当前: {raw_data_status}"
                )
```

---

## 4. API详细设计

### 4.1 增强原始数据查询API

**端点**: `GET /api/v1/search-results/` (增强现有接口)

**查询参数**:
```python
class SearchResultQueryParams(BaseModel):
    """查询参数"""
    # 分页参数
    cursor: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)

    # 过滤参数
    task_id: Optional[str] = None
    status: Optional[ResultStatus] = None  # 新增：状态过滤

    # 时间范围过滤
    published_after: Optional[datetime] = None   # 新增：发布时间起始
    published_before: Optional[datetime] = None  # 新增：发布时间截止
    crawled_after: Optional[datetime] = None     # 新增：采集时间起始
    crawled_before: Optional[datetime] = None    # 新增：采集时间截止

    # 关键词搜索
    keyword: Optional[str] = None
```

**响应结构**:
```python
class SearchResultListResponse(BaseModel):
    """响应结构"""
    items: List[SearchResultDTO]
    meta: PaginationMeta
```

**业务逻辑**: 同原文档，无变化

---

### 4.2 批量留存API

**端点**: `POST /api/v1/search-results/batch-archive`

**请求体**:
```python
class BatchArchiveRequest(BaseModel):
    """批量留存请求"""
    result_ids: List[str] = Field(..., min_items=1, max_items=100)
    source_type: str = Field(..., regex="^(search_result|instant_search_result)$")
```

**响应体**: `BatchOperationResponse`

**业务逻辑**: 同原文档，无变化

---

### 4.3 批量删除API

**端点**: `POST /api/v1/search-results/batch-delete`

**请求体**、**响应体**、**业务逻辑**: 同原文档，无变化

---

### 4.4 创建数据源API（简化版）

**端点**: `POST /api/v1/data-sources/`

**请求体**:
```python
class CreateDataSourceRequest(BaseModel):
    """创建数据源请求"""
    title: str = Field(..., min_length=1, max_length=200)
    content_text: str = Field(..., min_length=1)
    content_format: str = Field(default="markdown", regex="^(markdown|html)$")
    category: str = Field(..., min_length=1, max_length=50)
    tags: List[str] = Field(default_factory=list, max_items=10)

    # 关联的原始数据
    raw_data_sources: List[RawDataSourceRequest]

    created_by: str
```

**响应体**:
```python
class DataSourceResponse(BaseModel):
    """数据源响应"""
    source_id: str
    title: str
    content: Dict[str, Any]
    category: str
    tags: List[str]
    quality_score: float
    status: str  # draft/confirmed
    raw_data_count: int
    created_by: str
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
```

**业务逻辑（含状态同步）**:
```python
async def create_data_source(request: CreateDataSourceRequest) -> DataSourceResponse:
    """创建数据源（使用事务同步原始数据状态）"""
    # 1. 验证所有原始数据是否存在且状态有效
    raw_data_refs = []
    raw_data_updates = []  # 需要更新状态的原始数据

    for ref in request.raw_data_sources:
        # 1.1 查询原始数据
        if ref.source_type == "search_result":
            raw_data = await search_result_repo.find_by_id(ref.source_id)
            repo = search_result_repo
        else:
            raw_data = await instant_search_repo.find_by_id(ref.source_id)
            repo = instant_search_repo

        if not raw_data:
            raise NotFoundException(f"原始数据不存在: {ref.source_id}")

        # 1.2 验证状态（只有pending/archived可以添加）
        if raw_data.status not in [ResultStatus.PENDING, ResultStatus.ARCHIVED]:
            raise ValidationError(
                f"原始数据状态必须是pending或archived，当前: {raw_data.status}",
                field="raw_data_sources"
            )

        # 1.3 构建引用
        raw_data_refs.append(RawDataReference(
            source_type=ref.source_type,
            source_id=ref.source_id,
            title=raw_data.title,
            url=raw_data.url,
            crawled_at=raw_data.crawled_at
        ))

        # 1.4 记录需要更新的原始数据
        raw_data_updates.append((repo, ref.source_id, ResultStatus.PROCESSING))

    # 2. 创建数据源实体
    data_source = DataSource(
        title=request.title,
        content={
            "format": request.content_format,
            "text": request.content_text,
            "manual_edits": True
        },
        category=request.category,
        tags=request.tags,
        quality_score=calculate_quality_score(request.content_text, len(raw_data_refs)),
        status=DataSourceStatus.DRAFT,  # 创建时为draft状态
        raw_data_sources=raw_data_refs,
        raw_data_count=len(raw_data_refs),
        created_by=request.created_by
    )

    # 3. 使用MongoDB事务保证状态同步
    async with await database.start_session() as session:
        async with session.start_transaction():
            try:
                # 3.1 保存数据源
                await data_source_repo.create(data_source, session=session)

                # 3.2 更新所有原始数据状态为processing
                for repo, source_id, new_status in raw_data_updates:
                    await repo.update_status(source_id, new_status, session=session)

                # 3.3 提交事务
                await session.commit_transaction()
            except Exception as e:
                # 回滚事务
                await session.abort_transaction()
                raise e

    # 4. 返回响应
    return DataSourceResponse.from_entity(data_source)
```

---

### 4.5 更新数据源内容API

**端点**: `PUT /api/v1/data-sources/{source_id}/content`

**请求体**:
```python
class UpdateDataSourceContentRequest(BaseModel):
    """更新内容请求"""
    content_text: str = Field(..., min_length=1)
    content_format: str = Field(default="markdown", regex="^(markdown|html)$")
    updated_by: str
```

**业务逻辑（无变化，只能在draft状态编辑）**:
```python
async def update_data_source_content(
    source_id: str,
    request: UpdateDataSourceContentRequest
) -> DataSourceResponse:
    """更新数据源内容"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 验证状态（只有draft状态可以编辑）
    if not data_source.can_edit():
        raise ValidationError("只有draft状态可以编辑内容")

    # 3. 更新内容
    data_source.content = {
        "format": request.content_format,
        "text": request.content_text,
        "manual_edits": True
    }
    data_source.updated_at = datetime.utcnow()

    # 4. 重新计算质量分
    data_source.quality_score = calculate_quality_score(
        request.content_text,
        data_source.raw_data_count
    )

    # 5. 保存
    await data_source_repo.update(data_source)

    return DataSourceResponse.from_entity(data_source)
```

---

### 4.6 添加原始数据到数据源API（简化版）

**端点**: `POST /api/v1/data-sources/{source_id}/raw-data`

**请求体**:
```python
class AddRawDataRequest(BaseModel):
    """添加原始数据请求"""
    raw_data_sources: List[RawDataSourceRequest]
```

**业务逻辑（含状态同步）**:
```python
async def add_raw_data_to_source(
    source_id: str,
    request: AddRawDataRequest
) -> DataSourceResponse:
    """添加原始数据到数据源（使用事务同步状态）"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 验证状态（只有draft状态可以添加）
    if not data_source.can_edit():
        raise ValidationError("只有draft状态可以添加原始数据")

    # 3. 验证并获取原始数据
    new_refs = []
    raw_data_updates = []  # 需要更新状态的原始数据

    for ref in request.raw_data_sources:
        # 3.1 检查是否已存在
        if any(r.source_id == ref.source_id for r in data_source.raw_data_sources):
            raise ValidationError(f"原始数据已存在: {ref.source_id}")

        # 3.2 查询并验证状态
        if ref.source_type == "search_result":
            raw_data = await search_result_repo.find_by_id(ref.source_id)
            repo = search_result_repo
        else:
            raw_data = await instant_search_repo.find_by_id(ref.source_id)
            repo = instant_search_repo

        if not raw_data:
            raise NotFoundException(f"原始数据不存在: {ref.source_id}")

        # 3.3 验证状态（只有pending/archived可以添加）
        if raw_data.status not in [ResultStatus.PENDING, ResultStatus.ARCHIVED]:
            raise ValidationError(
                f"只有pending/archived状态的原始数据可以添加，当前: {raw_data.status}"
            )

        # 3.4 构建引用
        new_refs.append(RawDataReference(
            source_type=ref.source_type,
            source_id=ref.source_id,
            title=raw_data.title,
            url=raw_data.url,
            crawled_at=raw_data.crawled_at
        ))

        # 3.5 记录需要更新的原始数据
        raw_data_updates.append((repo, ref.source_id, ResultStatus.PROCESSING))

    # 4. 更新数据源
    data_source.raw_data_sources.extend(new_refs)
    data_source.raw_data_count = len(data_source.raw_data_sources)
    data_source.updated_at = datetime.utcnow()

    # 重新计算质量分
    data_source.quality_score = calculate_quality_score(
        data_source.content["text"],
        data_source.raw_data_count
    )

    # 5. 使用MongoDB事务保证状态同步
    async with await database.start_session() as session:
        async with session.start_transaction():
            try:
                # 5.1 更新数据源
                await data_source_repo.update(data_source, session=session)

                # 5.2 更新所有新添加的原始数据状态为processing
                for repo, source_id, new_status in raw_data_updates:
                    await repo.update_status(source_id, new_status, session=session)

                # 5.3 提交事务
                await session.commit_transaction()
            except Exception as e:
                # 回滚事务
                await session.abort_transaction()
                raise e

    return DataSourceResponse.from_entity(data_source)
```

---

### 4.7 移除原始数据API（新增）

**端点**: `DELETE /api/v1/data-sources/{source_id}/raw-data/{raw_data_id}`

**查询参数**:
```python
class RemoveRawDataParams(BaseModel):
    """移除原始数据参数"""
    source_type: str = Field(..., regex="^(search_result|instant_search_result)$")
```

**业务逻辑（含状态同步）**:
```python
async def remove_raw_data_from_source(
    source_id: str,
    raw_data_id: str,
    params: RemoveRawDataParams
) -> DataSourceResponse:
    """从数据源移除原始数据（使用事务同步状态）"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 验证状态（只有draft状态可以移除）
    if not data_source.can_edit():
        raise ValidationError("只有draft状态可以移除原始数据")

    # 3. 查找并移除引用
    original_count = len(data_source.raw_data_sources)
    removed_ref = None

    data_source.raw_data_sources = [
        ref for ref in data_source.raw_data_sources
        if not (ref.source_id == raw_data_id and ref.source_type == params.source_type)
    ]

    # 4. 检查是否找到并移除
    if len(data_source.raw_data_sources) == original_count:
        raise NotFoundException(f"原始数据不存在于数据源中: {raw_data_id}")

    # 5. 更新数据源
    data_source.raw_data_count = len(data_source.raw_data_sources)
    data_source.updated_at = datetime.utcnow()

    # 重新计算质量分
    if data_source.raw_data_count > 0:
        data_source.quality_score = calculate_quality_score(
            data_source.content["text"],
            data_source.raw_data_count
        )
    else:
        data_source.quality_score = 0.0

    # 6. 使用MongoDB事务保证状态同步
    async with await database.start_session() as session:
        async with session.start_transaction():
            try:
                # 6.1 更新数据源
                await data_source_repo.update(data_source, session=session)

                # 6.2 更新被移除的原始数据状态为archived
                if params.source_type == "search_result":
                    repo = search_result_repo
                else:
                    repo = instant_search_repo

                await repo.update_status(raw_data_id, ResultStatus.ARCHIVED, session=session)

                # 6.3 提交事务
                await session.commit_transaction()
            except Exception as e:
                # 回滚事务
                await session.abort_transaction()
                raise e

    return DataSourceResponse.from_entity(data_source)
```

---

### 4.8 确定数据源API（新增 - 替代原审核通过）

**端点**: `POST /api/v1/data-sources/{source_id}/confirm`

**请求体**:
```python
class ConfirmDataSourceRequest(BaseModel):
    """确定数据源请求"""
    confirmed_by: str
```

**业务逻辑（含状态同步）**:
```python
async def confirm_data_source(
    source_id: str,
    request: ConfirmDataSourceRequest
) -> DataSourceResponse:
    """确定数据源（使用事务同步原始数据状态）"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 验证状态
    if not data_source.can_confirm():
        raise ValidationError("只有draft状态可以确定")

    # 3. 验证内容完整性
    if not data_source.content.get("text"):
        raise ValidationError("数据源内容为空，不能确定")

    if data_source.raw_data_count == 0:
        raise ValidationError("数据源未关联原始数据，不能确定")

    # 4. 准备状态更新
    data_source.confirm(confirmed_by=request.confirmed_by)

    # 5. 使用MongoDB事务保证状态同步
    async with await database.start_session() as session:
        async with session.start_transaction():
            try:
                # 5.1 更新数据源状态
                await data_source_repo.update(data_source, session=session)

                # 5.2 更新所有关联的原始数据状态为completed
                for ref in data_source.raw_data_sources:
                    if ref.source_type == "search_result":
                        repo = search_result_repo
                    else:
                        repo = instant_search_repo

                    await repo.update_status(
                        ref.source_id,
                        ResultStatus.COMPLETED,
                        session=session
                    )

                # 5.3 提交事务
                await session.commit_transaction()
            except Exception as e:
                # 回滚事务
                await session.abort_transaction()
                raise e

    return DataSourceResponse.from_entity(data_source)
```

---

### 4.9 退回待处理API（新增）

**端点**: `POST /api/v1/data-sources/{source_id}/revert-to-draft`

**请求体**:
```python
class RevertToDraftRequest(BaseModel):
    """退回待处理请求"""
    reason: Optional[str] = None  # 退回原因（可选）
```

**业务逻辑（含状态同步）**:
```python
async def revert_to_draft(
    source_id: str,
    request: RevertToDraftRequest
) -> DataSourceResponse:
    """退回待处理（使用事务同步原始数据状态）"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 验证状态
    if not data_source.can_revert_to_draft():
        raise ValidationError("只有confirmed状态可以退回待处理")

    # 3. 准备状态更新
    data_source.revert_to_draft()

    # 4. 使用MongoDB事务保证状态同步
    async with await database.start_session() as session:
        async with session.start_transaction():
            try:
                # 4.1 更新数据源状态
                await data_source_repo.update(data_source, session=session)

                # 4.2 更新所有关联的原始数据状态为processing
                for ref in data_source.raw_data_sources:
                    if ref.source_type == "search_result":
                        repo = search_result_repo
                    else:
                        repo = instant_search_repo

                    await repo.update_status(
                        ref.source_id,
                        ResultStatus.PROCESSING,
                        session=session
                    )

                # 4.3 提交事务
                await session.commit_transaction()
            except Exception as e:
                # 回滚事务
                await session.abort_transaction()
                raise e

    return DataSourceResponse.from_entity(data_source)
```

---

### 4.10 下载原始数据API（新增）

**端点**: `GET /api/v1/data-sources/{source_id}/download-raw-data`

**查询参数**:
```python
class DownloadRawDataParams(BaseModel):
    """下载参数"""
    format: str = Field(default="json", regex="^(json|csv|markdown)$")
```

**响应体**:
```python
class DownloadRawDataResponse(BaseModel):
    """下载响应"""
    source_id: str
    title: str
    raw_data_count: int
    raw_data: List[RawDataDetail]
    generated_at: datetime

class RawDataDetail(BaseModel):
    """原始数据详情"""
    source_type: str
    source_id: str
    title: str
    url: str
    content: str  # 完整内容
    crawled_at: datetime
    published_date: Optional[datetime]
```

**业务逻辑**:
```python
async def download_raw_data(
    source_id: str,
    params: DownloadRawDataParams
) -> DownloadRawDataResponse:
    """下载数据源关联的原始数据"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 获取所有原始数据的完整内容
    raw_data_details = []
    for ref in data_source.raw_data_sources:
        # 查询原始数据完整信息
        if ref.source_type == "search_result":
            raw_data = await search_result_repo.find_by_id(ref.source_id)
        else:
            raw_data = await instant_search_repo.find_by_id(ref.source_id)

        if raw_data:
            raw_data_details.append(RawDataDetail(
                source_type=ref.source_type,
                source_id=ref.source_id,
                title=raw_data.title,
                url=raw_data.url,
                content=raw_data.content,  # 完整内容
                crawled_at=raw_data.crawled_at,
                published_date=getattr(raw_data, 'published_date', None)
            ))
        else:
            # 原始数据已被删除，标记为不可用
            raw_data_details.append(RawDataDetail(
                source_type=ref.source_type,
                source_id=ref.source_id,
                title=f"[已删除] {ref.title}",
                url=ref.url,
                content="原始数据已被删除",
                crawled_at=ref.crawled_at,
                published_date=None
            ))

    # 3. 返回下载响应
    return DownloadRawDataResponse(
        source_id=source_id,
        title=data_source.title,
        raw_data_count=len(raw_data_details),
        raw_data=raw_data_details,
        generated_at=datetime.utcnow()
    )
```

---

### 4.11 删除数据源API（简化版）

**端点**: `DELETE /api/v1/data-sources/{source_id}`

**业务逻辑（含条件状态同步）**:
```python
async def delete_data_source(source_id: str) -> DeleteDataSourceResponse:
    """删除数据源（使用事务同步原始数据状态，根据数据源状态有条件处理）"""
    # 1. 查询数据源
    data_source = await data_source_repo.find_by_id(source_id)
    if not data_source:
        raise NotFoundException(f"数据源不存在: {source_id}")

    # 2. 根据数据源状态决定是否需要更新原始数据
    need_update_raw_data = data_source.status == DataSourceStatus.DRAFT
    affected_count = 0

    # 3. 使用MongoDB事务保证状态同步（如果需要）
    if need_update_raw_data:
        # draft状态删除 → 原始数据回退到archived
        async with await database.start_session() as session:
            async with session.start_transaction():
                try:
                    # 3.1 删除数据源
                    await data_source_repo.delete(source_id, session=session)

                    # 3.2 更新所有关联的原始数据状态为archived
                    for ref in data_source.raw_data_sources:
                        if ref.source_type == "search_result":
                            repo = search_result_repo
                        else:
                            repo = instant_search_repo

                        await repo.update_status(
                            ref.source_id,
                            ResultStatus.ARCHIVED,
                            session=session
                        )
                        affected_count += 1

                    # 3.3 提交事务
                    await session.commit_transaction()
                except Exception as e:
                    # 回滚事务
                    await session.abort_transaction()
                    raise e

        message = f"数据源已删除（draft状态），{affected_count}条原始数据已回退为archived"
    else:
        # confirmed状态删除 → 原始数据保持completed（不需要事务）
        await data_source_repo.delete(source_id)
        message = "数据源已删除（confirmed状态），原始数据保持completed状态"

    # 4. 返回响应
    return DeleteDataSourceResponse(
        success=True,
        message=message,
        affected_raw_data_count=affected_count
    )
```

---

## 5. 服务层实现

### 5.1 数据整编服务（含状态同步）

```python
class DataCurationService:
    """数据整编服务（含MongoDB事务状态同步）"""

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        data_source_repo: DataSourceRepository,
        search_result_repo: SearchResultRepository,
        instant_search_repo: InstantSearchResultRepository,
        quality_service: QualityScoreService
    ):
        self.database = database
        self.data_source_repo = data_source_repo
        self.search_result_repo = search_result_repo
        self.instant_search_repo = instant_search_repo
        self.quality_service = quality_service

    async def create_data_source(
        self,
        request: CreateDataSourceRequest
    ) -> DataSource:
        """创建数据源（使用事务同步原始数据状态）"""
        # 1. 验证原始数据存在性和状态
        raw_data_refs, raw_data_updates = await self._validate_and_prepare_raw_data(
            request.raw_data_sources
        )

        # 2. 计算质量分
        quality_score = self.quality_service.calculate_score(
            content_text=request.content_text,
            raw_data_count=len(raw_data_refs),
            category=request.category
        )

        # 3. 创建数据源实体
        data_source = self._build_data_source_entity(request, raw_data_refs, quality_score)

        # 4. 使用MongoDB事务保证状态同步
        async with await self.database.start_session() as session:
            async with session.start_transaction():
                try:
                    # 4.1 保存数据源
                    await self.data_source_repo.create(data_source, session=session)

                    # 4.2 更新所有原始数据状态为processing
                    for repo, source_id, new_status in raw_data_updates:
                        await repo.update_status(source_id, new_status, session=session)

                    # 4.3 提交事务
                    await session.commit_transaction()
                except Exception as e:
                    # 回滚事务
                    await session.abort_transaction()
                    raise e

        return data_source

    async def _validate_and_prepare_raw_data(
        self,
        raw_data_requests: List[RawDataSourceRequest]
    ) -> Tuple[List[RawDataReference], List[Tuple]]:
        """验证原始数据并准备更新列表"""
        raw_data_refs = []
        raw_data_updates = []

        for ref in raw_data_requests:
            # 查询数据
            if ref.source_type == "search_result":
                raw_data = await self.search_result_repo.find_by_id(ref.source_id)
                repo = self.search_result_repo
            else:
                raw_data = await self.instant_search_repo.find_by_id(ref.source_id)
                repo = self.instant_search_repo

            # 验证存在性
            if not raw_data:
                raise NotFoundException(
                    f"原始数据不存在: {ref.source_id}",
                    error_code="RAW_DATA_NOT_FOUND"
                )

            # 验证状态（只有pending/archived可以添加到数据源）
            if raw_data.status not in [ResultStatus.PENDING, ResultStatus.ARCHIVED]:
                raise ValidationError(
                    f"只有pending/archived状态的原始数据可以添加到数据源，当前: {raw_data.status}",
                    error_code="INVALID_RAW_DATA_STATUS"
                )

            # 构建引用
            raw_data_refs.append(RawDataReference(
                source_type=ref.source_type,
                source_id=ref.source_id,
                title=raw_data.title,
                url=raw_data.url,
                crawled_at=raw_data.crawled_at
            ))

            # 记录需要更新的原始数据
            raw_data_updates.append((repo, ref.source_id, ResultStatus.PROCESSING))

        return raw_data_refs, raw_data_updates

    def _build_data_source_entity(
        self,
        request: CreateDataSourceRequest,
        raw_data_refs: List[RawDataReference],
        quality_score: float
    ) -> DataSource:
        """构建数据源实体"""
        return DataSource(
            title=request.title,
            content={
                "format": request.content_format,
                "text": request.content_text,
                "manual_edits": True
            },
            category=request.category,
            tags=request.tags,
            quality_score=quality_score,
            status=DataSourceStatus.DRAFT,
            raw_data_sources=raw_data_refs,
            raw_data_count=len(raw_data_refs),
            created_by=request.created_by
        )
```

### 5.2 质量评分服务（无变化）

质量评分服务保持不变，参见原文档第4.2节。

---

## 6. 数据验证规则

### 6.1 创建数据源验证（简化版）

```python
class CreateDataSourceValidator:
    """创建数据源验证器（简化版）"""

    @staticmethod
    def validate(request: CreateDataSourceRequest) -> None:
        """验证创建请求"""
        # 1. 标题验证
        if not request.title or len(request.title.strip()) == 0:
            raise ValidationError("标题不能为空", field="title")

        if len(request.title) > 200:
            raise ValidationError("标题长度不能超过200字符", field="title")

        # 2. 内容验证
        if not request.content_text or len(request.content_text.strip()) == 0:
            raise ValidationError("内容不能为空", field="content_text")

        if len(request.content_text) < 50:
            raise ValidationError("内容长度至少50字符", field="content_text")

        # 3. 分类验证
        if not request.category:
            raise ValidationError("分类不能为空", field="category")

        # 4. 标签验证
        if len(request.tags) > 10:
            raise ValidationError("标签数量不能超过10个", field="tags")

        # 5. 原始数据验证
        if not request.raw_data_sources or len(request.raw_data_sources) == 0:
            raise ValidationError("必须关联至少1条原始数据", field="raw_data_sources")

        if len(request.raw_data_sources) > 50:
            raise ValidationError("关联的原始数据不能超过50条", field="raw_data_sources")

        # 6. 原始数据去重验证
        source_ids = [r.source_id for r in request.raw_data_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValidationError("原始数据列表中存在重复项", field="raw_data_sources")
```

其他验证规则参见原文档第5节。

---

## 7. 错误处理策略

错误处理策略保持不变，参见原文档第7节。

---

## 8. 性能优化

### 8.1 数据库索引（简化版）

```python
# data_sources索引
await data_sources_collection.create_index([
    ("status", 1),
    ("created_at", -1)
], name="idx_status_created")

await data_sources_collection.create_index([
    ("category", 1),
    ("quality_score", -1)
], name="idx_category_quality")

await data_sources_collection.create_index([
    ("created_by", 1),
    ("status", 1)
], name="idx_creator_status")
```

其他性能优化策略参见原文档第8节。

---

## 9. 测试策略

### 9.1 单元测试（简化版）

#### 9.1.1 数据源实体测试

```python
import pytest
from src.core.domain.entities.data_source import DataSource, DataSourceStatus

class TestDataSourceEntity:
    """DataSource实体测试（简化版）"""

    def test_can_edit_when_draft(self):
        """测试draft状态可以编辑"""
        ds = DataSource(status=DataSourceStatus.DRAFT)
        assert ds.can_edit() is True

    def test_cannot_edit_when_confirmed(self):
        """测试confirmed状态不能编辑"""
        ds = DataSource(status=DataSourceStatus.CONFIRMED)
        assert ds.can_edit() is False

    def test_confirm_success(self):
        """测试确定数据源"""
        ds = DataSource(status=DataSourceStatus.DRAFT)
        ds.confirm(confirmed_by="test_user")
        assert ds.status == DataSourceStatus.CONFIRMED
        assert ds.confirmed_by == "test_user"
        assert ds.confirmed_at is not None

    def test_revert_to_draft_success(self):
        """测试退回待处理"""
        ds = DataSource(status=DataSourceStatus.CONFIRMED)
        ds.revert_to_draft()
        assert ds.status == DataSourceStatus.DRAFT
        assert ds.confirmed_by is None
        assert ds.confirmed_at is None
```

### 9.2 集成测试（含状态同步验证）

#### 9.2.1 完整整编流程测试

```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
class TestDataCurationWorkflowWithStatusSync:
    """数据整编完整流程测试（含状态同步验证）"""

    @pytest.mark.asyncio
    async def test_complete_curation_workflow_with_status_sync(self, client: AsyncClient):
        """测试完整的整编流程（验证状态同步机制）"""
        # 步骤1: 创建测试数据
        # ... 创建search_result测试数据，确保状态为pending ...

        # 步骤2: 查询pending状态的原始数据
        response = await client.get(
            "/api/v1/search-results/",
            params={"status": "pending", "limit": 10}
        )
        assert response.status_code == 200
        results = response.json()["items"]
        assert len(results) > 0
        assert results[0]["status"] == "pending"  # 初始状态为pending
        test_result_id = results[0]["id"]

        # 步骤3: 创建数据源（应触发状态同步：pending → processing）
        response = await client.post("/api/v1/data-sources/", json={
            "title": "集成测试数据源",
            "content_text": "这是整编后的内容" * 50,
            "category": "技术",
            "raw_data_sources": [
                {"source_type": "search_result", "source_id": test_result_id}
            ],
            "created_by": "test_user"
        })
        assert response.status_code == 201
        data_source = response.json()
        source_id = data_source["source_id"]
        assert data_source["status"] == "draft"

        # 步骤4: 验证原始数据状态已变为processing
        response = await client.get(f"/api/v1/search-results/{test_result_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "processing"  # pending → processing

        # 步骤5: 确定数据源（应触发状态同步：processing → completed）
        response = await client.post(
            f"/api/v1/data-sources/{source_id}/confirm",
            json={"confirmed_by": "admin_user"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

        # 步骤6: 验证原始数据状态已变为completed
        response = await client.get(f"/api/v1/search-results/{test_result_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"  # processing → completed

        # 步骤7: 退回待处理（应触发状态同步：completed → processing）
        response = await client.post(
            f"/api/v1/data-sources/{source_id}/revert-to-draft",
            json={}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "draft"

        # 步骤8: 验证原始数据状态已回退为processing
        response = await client.get(f"/api/v1/search-results/{test_result_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "processing"  # completed → processing

        # 步骤9: 下载原始数据
        response = await client.get(
            f"/api/v1/data-sources/{source_id}/download-raw-data",
            params={"format": "json"}
        )
        assert response.status_code == 200
        download_data = response.json()
        assert download_data["raw_data_count"] > 0

        # 步骤10: 删除draft状态的数据源（应触发状态同步：processing → archived）
        response = await client.delete(f"/api/v1/data-sources/{source_id}")
        assert response.status_code == 200
        assert "archived" in response.json()["message"]

        # 步骤11: 验证原始数据状态已变为archived
        response = await client.get(f"/api/v1/search-results/{test_result_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"  # processing → archived

    @pytest.mark.asyncio
    async def test_delete_confirmed_data_source_keeps_status(self, client: AsyncClient):
        """测试删除confirmed状态的数据源，原始数据保持completed"""
        # ... 创建并确定数据源到confirmed状态 ...

        # 删除confirmed数据源
        response = await client.delete(f"/api/v1/data-sources/{source_id}")
        assert response.status_code == 200
        assert "completed" in response.json()["message"]

        # 验证原始数据状态保持completed
        response = await client.get(f"/api/v1/search-results/{test_result_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"  # 保持不变
```

---

## 10. API端点总结

| 端点 | 方法 | 功能 | 状态码 | 影响原始数据 |
|------|------|------|--------|--------------|
| `/api/v1/search-results/` | GET | 查询原始数据（增强：状态+时间过滤） | 200 | 否 |
| `/api/v1/search-results/batch-archive` | POST | 批量留存 | 200 | **是（独立操作）** |
| `/api/v1/search-results/batch-delete` | POST | 批量删除 | 200 | **是（独立操作）** |
| `/api/v1/data-sources/` | POST | 创建数据源 | 201 | **是（→processing）** |
| `/api/v1/data-sources/{source_id}` | GET | 获取数据源详情 | 200 | 否 |
| `/api/v1/data-sources/{source_id}/content` | PUT | 更新数据源内容 | 200 | 否 |
| `/api/v1/data-sources/{source_id}/raw-data` | POST | 添加原始数据 | 200 | **是（新数据→processing）** |
| `/api/v1/data-sources/{source_id}/raw-data/{id}` | DELETE | 移除原始数据 | 200 | **是（→archived）** |
| `/api/v1/data-sources/{source_id}/confirm` | POST | **确定数据源** | 200 | **是（→completed）** |
| `/api/v1/data-sources/{source_id}/revert-to-draft` | POST | **退回待处理** | 200 | **是（→processing）** |
| `/api/v1/data-sources/{source_id}/download-raw-data` | GET | **下载原始数据** | 200 | 否 |
| `/api/v1/data-sources/{source_id}` | DELETE | 删除数据源 | 200 | **是（条件：draft→archived，confirmed不变）** |

**状态同步规则（事务保证）**：
- ✅ **创建数据源**: 原始数据 pending/archived → processing
- ✅ **添加原始数据**: 新数据 pending/archived → processing
- ✅ **移除原始数据**: 被移除数据 processing → archived
- ✅ **确定数据源**: 所有关联数据 processing → completed
- ✅ **退回待处理**: 所有关联数据 completed → processing
- ✅ **删除draft数据源**: 所有关联数据 processing → archived
- ✅ **删除confirmed数据源**: 所有关联数据保持 completed（不回退）
- ✅ 数据源可以在draft和confirmed之间**反复切换**

---

## 11. 实施建议

### 11.1 优先级（简化版）

**Phase 1 (高优先级)**:
1. 数据库迁移（添加status字段到原始数据）
2. 实体层修改（DataSource实体，只有2个状态）
3. Repository层基础方法

**Phase 2 (中优先级)**:
4. 服务层核心逻辑（创建、确定、退回）
5. API端点实现（11个端点）
6. 下载功能实现

**Phase 3 (低优先级)**:
7. 性能优化（索引、缓存）
8. 完整测试覆盖
9. 监控和日志

### 11.2 风险点

1. **数据一致性**: 原始数据删除后数据源引用失效
   - **解决**: 保留引用但标记为"源数据已删除"

2. **状态切换频繁**: 用户可能频繁在draft和confirmed之间切换
   - **解决**: 无限制，允许随时切换

3. **下载性能**: 下载大量原始数据可能较慢
   - **解决**: 限制单次下载数量，提供分页下载

---

**文档结束**
