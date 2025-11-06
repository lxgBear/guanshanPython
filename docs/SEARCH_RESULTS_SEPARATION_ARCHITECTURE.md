# 搜索结果职责分离架构设计

**日期**: 2025-11-03
**版本**: v1.0.0
**范围**: 定时任务系统（智能搜索暂不涉及）
**目的**: 分离原始数据存储和AI处理结果，实现清晰的职责划分

---

## 📋 架构概述

### 核心变更

**Before (当前架构)**:
```
search_results 表 = 原始数据 + 用户操作状态 + 混合职责
```

**After (新架构)**:
```
search_results 表 = 纯原始数据（只读存储）
news_results 表 = AI处理结果（分析、翻译、增强）
```

### 职责分离

| 集合名称 | 职责 | 数据来源 | 操作权限 |
|---------|------|----------|----------|
| **search_results** | 原始搜索结果存储 | Firecrawl API | 只写（定时任务）、只读（查询） |
| **news_results** | AI处理后的结果 | AI服务处理 | AI服务写入、前端读取 |

---

## 🏗️ 数据模型设计

### 1. SearchResult (search_results 表)

**职责**: 纯原始数据存储，不包含任何业务逻辑状态

```python
@dataclass
class SearchResult:
    """原始搜索结果实体（v2.0.0 简化版）

    职责：只负责存储从Firecrawl获取的原始数据
    不包含：状态管理、用户操作、AI处理标记
    """
    # 主键
    id: str = field(default_factory=generate_string_id)
    task_id: str  # 关联的搜索任务ID

    # 核心原始数据（从Firecrawl获取）
    title: str
    url: str
    content: str  # 提取的主要内容
    snippet: Optional[str]  # 搜索结果摘要

    # 原始元数据
    source: str = "web"  # 来源：web, news, academic
    published_date: Optional[datetime]
    author: Optional[str]
    language: Optional[str]

    # Firecrawl 原始字段
    markdown_content: Optional[str]  # Markdown格式（最大5000字符）
    html_content: Optional[str]  # HTML格式
    article_tag: Optional[str]
    article_published_time: Optional[str]
    source_url: Optional[str]  # 原始URL（重定向场景）
    http_status_code: Optional[int]
    search_position: Optional[int]  # 搜索结果排名
    metadata: Dict[str, Any]  # 扩展元数据

    # 质量指标（Firecrawl提供或计算）
    relevance_score: float = 0.0
    quality_score: float = 0.0

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)

    # 测试标记
    is_test_data: bool = False
```

**移除字段**:
- ❌ `status` - 业务状态管理移至news_results
- ❌ `processed_at` - AI处理时间移至news_results

**保留字段**:
- ✅ 所有原始数据字段（title, url, content等）
- ✅ Firecrawl原始元数据
- ✅ 质量评分（relevance_score, quality_score）

---

### 2. ProcessedResult (news_results 表)

**职责**: 存储AI处理后的增强数据和用户操作状态

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

class ProcessedStatus(Enum):
    """处理结果状态枚举"""
    PENDING = "pending"         # 待AI处理
    PROCESSING = "processing"   # AI处理中
    COMPLETED = "completed"     # AI处理完成
    FAILED = "failed"           # AI处理失败
    ARCHIVED = "archived"       # 用户留存
    DELETED = "deleted"         # 用户删除（软删除）


@dataclass
class ProcessedResult:
    """AI处理结果实体（v2.0.0 新增）

    职责：
    1. 存储AI分析、翻译、总结后的数据
    2. 管理用户操作状态（留存、删除）
    3. 记录AI处理元数据
    """
    # 主键
    id: str = field(default_factory=generate_string_id)

    # 关联原始结果
    raw_result_id: str  # 关联 search_results 的 ID
    task_id: str        # 关联的搜索任务ID

    # AI处理后的数据
    translated_title: Optional[str] = None  # 翻译后的标题
    translated_content: Optional[str] = None  # 翻译后的内容
    summary: Optional[str] = None  # AI生成的摘要
    key_points: List[str] = field(default_factory=list)  # 关键要点
    sentiment: Optional[str] = None  # 情感分析（positive/neutral/negative）
    categories: List[str] = field(default_factory=list)  # AI分类标签

    # AI处理元数据
    ai_model: Optional[str] = None  # 使用的AI模型（如：gpt-4）
    ai_processing_time_ms: int = 0  # AI处理耗时（毫秒）
    ai_confidence_score: float = 0.0  # AI置信度分数（0-1）
    ai_metadata: Dict[str, Any] = field(default_factory=dict)  # AI额外元数据

    # 用户操作状态
    status: ProcessedStatus = ProcessedStatus.PENDING
    user_rating: Optional[int] = None  # 用户评分（1-5）
    user_notes: Optional[str] = None  # 用户备注

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)  # 创建时间（原始结果时间）
    processed_at: Optional[datetime] = None  # AI处理完成时间
    updated_at: datetime = field(default_factory=datetime.utcnow)  # 最后更新时间

    # 错误处理
    processing_error: Optional[str] = None  # AI处理错误信息
    retry_count: int = 0  # 重试次数

    def mark_as_processing(self) -> None:
        """标记为AI处理中"""
        self.status = ProcessedStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_as_completed(self, ai_model: str, processing_time_ms: int) -> None:
        """标记为AI处理完成"""
        self.status = ProcessedStatus.COMPLETED
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.ai_model = ai_model
        self.ai_processing_time_ms = processing_time_ms

    def mark_as_failed(self, error_message: str) -> None:
        """标记为AI处理失败"""
        self.status = ProcessedStatus.FAILED
        self.processing_error = error_message
        self.retry_count += 1
        self.updated_at = datetime.utcnow()

    def mark_as_archived(self) -> None:
        """用户标记为留存"""
        self.status = ProcessedStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def mark_as_deleted(self) -> None:
        """用户标记为删除（软删除）"""
        self.status = ProcessedStatus.DELETED
        self.updated_at = datetime.utcnow()
```

---

## 🔄 数据流设计

### 定时任务数据流（v2.0.0）

```
┌─────────────────────────────────────────┐
│   TaskSchedulerService                  │
│   (定时任务调度器)                       │
└────────────┬────────────────────────────┘
             │
             ↓ 执行搜索/爬取
┌─────────────────────────────────────────┐
│   FirecrawlSearchAdapter                │
│   (Firecrawl API 集成)                  │
└────────────┬────────────────────────────┘
             │
             ↓ 获取原始数据
┌─────────────────────────────────────────┐
│   SearchResult (search_results)         │
│   - 原始标题、内容、URL                  │
│   - Firecrawl元数据                     │
│   - 质量评分                             │
│   - 只写一次，不再修改                   │
└────────────┬────────────────────────────┘
             │
             ↓ 通知AI服务（新增）
┌─────────────────────────────────────────┐
│   AI Service Notification               │
│   (向AI服务发送处理请求)                 │
│   - 发送 raw_result_id                  │
│   - 发送 task_id                        │
└────────────┬────────────────────────────┘
             │
             ↓ AI服务处理（另一个同事负责）
┌─────────────────────────────────────────┐
│   AI Processing Service                 │
│   (独立的AI服务)                         │
│   1. 从 search_results 读取原始数据      │
│   2. 分析、翻译、总结                     │
│   3. 写入 news_results              │
└────────────┬────────────────────────────┘
             │
             ↓ 保存AI结果
┌─────────────────────────────────────────┐
│   ProcessedResult (news_results)   │
│   - AI翻译内容                           │
│   - AI总结摘要                           │
│   - 情感分析、分类标签                   │
│   - 用户操作状态                         │
└─────────────────────────────────────────┘
```

### 关键设计点

1. **单向数据流**:
   - `search_results` → 只写入一次（定时任务）
   - `news_results` → AI服务异步写入

2. **职责清晰**:
   - 定时任务：负责获取原始数据并通知AI服务
   - AI服务：负责处理和增强数据
   - 前端：从 `news_results` 读取最终数据

3. **状态管理**:
   - `search_results`: 无状态，纯数据存储
   - `news_results`: 有状态（PENDING → PROCESSING → COMPLETED）

---

## 📊 数据库集合职责

| 集合名称 | 读权限 | 写权限 | 更新权限 | 删除权限 |
|---------|--------|--------|----------|----------|
| **search_results** | ✅ 所有服务 | ✅ 定时任务 | ❌ 无 | ⚠️ 仅管理员 |
| **news_results** | ✅ 前端/API | ✅ AI服务 | ✅ AI服务/用户 | ⚠️ 软删除 |

### 数据一致性规则

1. **search_results 不可变性**:
   - 一旦写入，永不修改（immutable）
   - 删除操作仅通过管理员API

2. **news_results 状态流转**:
   ```
   PENDING → PROCESSING → COMPLETED ✓
   PENDING → PROCESSING → FAILED → PENDING (重试)
   COMPLETED → ARCHIVED (用户操作)
   COMPLETED → DELETED (用户操作)
   ```

3. **关联关系**:
   - `news_results.raw_result_id` 必须存在于 `search_results._id`
   - 级联删除：删除 `search_results` → 同时删除对应的 `news_results`

---

## 🔧 Repository层设计

### 1. SearchResultRepository (修改)

```python
class SearchResultRepository:
    """原始搜索结果仓储（v2.0.0 简化版）"""

    def __init__(self):
        self.collection_name = "search_results"

    async def save_results(self, results: List[SearchResult]) -> List[str]:
        """
        批量保存原始搜索结果（只写一次）

        Returns:
            保存的结果ID列表（用于通知AI服务）
        """
        # 实现批量插入
        # 返回ID列表以便后续通知AI服务

    async def get_by_id(self, result_id: str) -> Optional[SearchResult]:
        """根据ID获取原始结果（只读）"""
        pass

    async def get_by_task(self, task_id: str, page: int, page_size: int) -> tuple[List[SearchResult], int]:
        """获取任务的所有原始结果（只读）"""
        pass

    # ❌ 移除状态管理方法（不再需要）
    # - update_result_status()
    # - bulk_update_status()
    # - get_results_by_status()
    # - count_by_status()
```

### 2. ProcessedResultRepository (新增)

```python
class ProcessedResultRepository:
    """AI处理结果仓储（v2.0.0 新增）"""

    def __init__(self):
        self.collection_name = "news_results"

    async def create_pending_result(self, raw_result_id: str, task_id: str) -> ProcessedResult:
        """
        创建待处理的结果记录

        Args:
            raw_result_id: 原始结果ID
            task_id: 任务ID

        Returns:
            创建的ProcessedResult实体
        """
        pass

    async def update_processing_status(
        self,
        result_id: str,
        status: ProcessedStatus,
        **kwargs
    ) -> bool:
        """更新处理状态"""
        pass

    async def save_ai_result(
        self,
        result_id: str,
        translated_title: str,
        translated_content: str,
        summary: str,
        key_points: List[str],
        ai_model: str,
        processing_time_ms: int
    ) -> bool:
        """保存AI处理结果"""
        pass

    async def get_by_raw_result_id(self, raw_result_id: str) -> Optional[ProcessedResult]:
        """根据原始结果ID获取处理结果"""
        pass

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[ProcessedStatus],
        page: int,
        page_size: int
    ) -> tuple[List[ProcessedResult], int]:
        """获取任务的处理结果（支持状态筛选）"""
        pass

    async def update_user_action(
        self,
        result_id: str,
        status: ProcessedStatus,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """更新用户操作（留存、删除、评分）"""
        pass

    async def get_status_statistics(self, task_id: str) -> Dict[str, int]:
        """获取任务的状态统计"""
        pass

    async def get_failed_results(self, max_retry: int = 3) -> List[ProcessedResult]:
        """获取失败的结果（用于重试）"""
        pass
```

---

## 🚀 实施计划（仅定时任务范围）

### Phase 1: 数据模型和Repository（2天）

**1.1 创建新实体类**（1天）
- [ ] 创建 `src/core/domain/entities/processed_result.py`
  - ProcessedResult 数据类
  - ProcessedStatus 枚举
  - 状态转换方法
- [ ] 修改 `SearchResult` 实体
  - 移除 `status` 字段
  - 移除 `processed_at` 字段
  - 保留所有原始数据字段

**1.2 创建新Repository**（1天）
- [ ] 创建 `src/infrastructure/database/processed_result_repositories.py`
  - ProcessedResultRepository 完整实现
  - 索引设计（raw_result_id, task_id, status）
- [ ] 修改 `SearchResultRepository`
  - 移除状态管理相关方法
  - 简化为纯读写操作
  - 添加批量插入返回ID功能

### Phase 2: 定时任务集成（2天）

**2.1 修改TaskSchedulerService**（1天）
```python
async def _execute_search_task(self, task_id: str):
    """执行搜索任务（v2.0.0 职责分离版本）"""
    # 1. 执行搜索/爬取（不变）
    result_batch = await self.search_adapter.search(...)

    # 2. 保存原始结果到 search_results（修改：返回ID列表）
    saved_ids = await result_repo.save_results(result_batch.results)

    # 3. 【新增】为每个原始结果创建待处理记录
    processed_repo = ProcessedResultRepository()
    for raw_id in saved_ids:
        await processed_repo.create_pending_result(
            raw_result_id=raw_id,
            task_id=task_id
        )

    # 4. 【新增】通知AI服务（可选：消息队列或HTTP回调）
    await self._notify_ai_service(saved_ids, task_id)
```

**2.2 实现AI服务通知机制**（1天）
- [ ] 设计通知接口（HTTP回调 或 消息队列）
- [ ] 实现通知逻辑
- [ ] 错误处理和重试

### Phase 3: API层适配（2天）

**3.1 修改查询API**（1天）
- [ ] `/api/v1/search-tasks/{id}/results` 端点
  - 默认返回 `news_results`（用户视角）
  - 新增 `?view=raw` 参数返回原始结果
  - 状态筛选基于 `ProcessedStatus`

**3.2 新增用户操作API**（1天）
- [ ] `POST /api/v1/processed-results/{id}/archive` - 留存
- [ ] `POST /api/v1/processed-results/{id}/delete` - 删除
- [ ] `PUT /api/v1/processed-results/{id}/rating` - 评分

### Phase 4: 数据迁移（1天）

**4.1 历史数据迁移脚本**
```python
# scripts/migrate_search_results_to_processed.py

async def migrate():
    """
    将现有 search_results 中的状态数据迁移到 news_results

    迁移策略：
    1. 读取所有 search_results
    2. 为每条记录创建对应的 news_results
    3. 初始状态设为 PENDING（等待AI处理）
    4. 移除 search_results 中的 status 字段（可选）
    """
    # 实现迁移逻辑
```

**4.2 数据一致性验证**
- [ ] 验证所有 raw_result_id 都存在
- [ ] 验证状态转换正确
- [ ] 生成迁移报告

### Phase 5: 测试和文档（2天）

**5.1 单元测试**（1天）
- [ ] ProcessedResult 实体测试
- [ ] ProcessedResultRepository 测试
- [ ] TaskSchedulerService 修改后的测试
- [ ] API端点测试

**5.2 集成测试和文档**（1天）
- [ ] 端到端测试（定时任务 → 原始结果 → 通知AI服务）
- [ ] 更新API文档
- [ ] 更新数据库集合说明文档

---

## ⚠️ 注意事项

### 1. 智能搜索暂不修改

**原因**: 避免大量修改导致风险
**策略**: 智能搜索继续使用现有的 `instant_search_results` 和 `smart_search_results`

### 2. AI服务接口需求

AI服务（另一个同事负责）需要实现：

**输入**:
```json
{
  "raw_result_ids": ["id1", "id2", "id3"],
  "task_id": "task123"
}
```

**处理流程**:
1. 从 `search_results` 读取原始数据
2. 执行分析、翻译、总结
3. 更新 `news_results` 状态为 PROCESSING
4. 保存AI结果到 `news_results`
5. 更新状态为 COMPLETED

**错误处理**:
- AI处理失败 → 状态设为 FAILED
- 支持重试机制（最多3次）

### 3. 前端适配

前端需要：
1. 修改查询接口从 `news_results` 读取数据
2. 显示AI处理状态（PENDING, PROCESSING, COMPLETED）
3. 实现用户操作（留存、删除、评分）
4. 显示原始数据和AI增强数据的对比（可选）

### 4. 数据库索引

**search_results 索引**:
```javascript
db.search_results.createIndex({ "task_id": 1, "created_at": -1 })
db.search_results.createIndex({ "url": 1 }, { unique: true })  // 去重
```

**news_results 索引**:
```javascript
db.news_results.createIndex({ "raw_result_id": 1 }, { unique: true })
db.news_results.createIndex({ "task_id": 1, "status": 1, "updated_at": -1 })
db.news_results.createIndex({ "status": 1, "retry_count": 1 })  // 重试查询
```

---

## 📝 总结

### 架构优势

1. **职责清晰**: search_results 纯数据存储，news_results 业务逻辑
2. **可扩展**: AI服务独立，易于升级和替换
3. **性能优化**: 原始数据不可变，缓存友好
4. **数据安全**: 原始数据不会被意外修改

### 向后兼容

- 保留 `search_results` 所有原始字段
- API支持 `?view=raw` 参数查看原始数据
- 渐进式迁移，不影响现有功能

### 依赖关系

```
定时任务 → search_results (自包含)
AI服务 → search_results (读) + news_results (写)
前端 → news_results (读写)
```

---

**文档作者**: Claude Code Assistant
**文档状态**: ✅ 设计完成，待审核
**下一步**: 创建UML图和详细实施文档
**审核人**: Backend Team
**预计工期**: 9天（不包含AI服务开发）
