# 搜索任务执行历史系统设计

**版本**: 1.0
**日期**: 2025-10-24
**目的**: 为定时搜索任务添加详细的执行历史追踪

---

## 📊 现状分析

### ✅ 已实现的状态追踪

#### 1. InstantSearchTask (即时搜索)
- **状态枚举**: `InstantSearchStatus` (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- **状态方法**: `start_execution()`, `mark_as_completed()`, `mark_as_failed()`
- **时间戳**: started_at, completed_at, updated_at
- **执行指标**: total_results, new_results, shared_results, credits_used, execution_time_ms
- **API支持**:
  - ✅ 状态字段在响应中返回
  - ✅ 支持状态过滤查询

#### 2. SearchTask (定时任务)
- **状态枚举**: `TaskStatus` (ACTIVE, PAUSED, FAILED, COMPLETED, DISABLED)
- **状态方法**: `update_status()`, `record_execution()`
- **时间戳**: last_executed_at, next_run_time, updated_at
- **统计指标**: execution_count, success_count, failure_count, total_results, total_credits_used
- **API支持**:
  - ✅ 状态字段在响应中返回
  - ✅ GET `/search-tasks/{task_id}/status`
  - ✅ PATCH `/search-tasks/{task_id}/status`
  - ✅ 支持状态过滤查询

### ❌ 缺失的功能

#### 定时任务缺少详细执行历史
当前SearchTask只有聚合统计数据，缺少以下功能：

1. **单次执行记录**: 无法查询某次具体执行的详情
2. **执行状态追踪**: 不知道每次执行成功还是失败
3. **错误历史**: 不知道什么时候失败、失败原因
4. **性能分析**: 无法分析每次执行耗时、积分消耗
5. **审计追踪**: 无法追溯历史执行情况

---

## 🎯 设计目标

### 核心需求
为定时搜索任务(SearchTask)添加详细的执行历史追踪系统，实现：

1. ✅ 记录每次定时任务的执行详情
2. ✅ 追踪执行状态（成功/失败/运行中）
3. ✅ 保存执行结果统计和性能指标
4. ✅ 提供执行历史查询API
5. ✅ 支持错误诊断和性能分析

---

## 📐 数据模型设计

### 1. SearchTaskExecution 实体

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from src.infrastructure.id_generator import generate_string_id


class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 执行成功
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 已跳过（任务被禁用）


@dataclass
class SearchTaskExecution:
    """
    定时任务执行历史实体

    记录每次调度器执行定时任务的详细信息
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 关联任务
    task_id: str = ""  # 关联的SearchTask ID
    task_name: str = ""  # 任务名称（冗余字段，便于查询）

    # 执行信息
    execution_number: int = 0  # 执行序号（该任务的第N次执行）
    scheduled_time: datetime = field(default_factory=datetime.utcnow)  # 计划执行时间
    started_at: Optional[datetime] = None  # 实际开始时间
    completed_at: Optional[datetime] = None  # 完成时间
    execution_time_ms: int = 0  # 执行耗时（毫秒）

    # 执行状态
    status: ExecutionStatus = ExecutionStatus.PENDING

    # 执行结果
    total_results: int = 0  # 本次搜索结果数
    new_results: int = 0  # 新结果数
    credits_used: int = 0  # 消耗积分

    # 错误信息
    error_message: Optional[str] = None
    error_type: Optional[str] = None  # 错误类型（网络错误、API错误、超时等）
    retry_count: int = 0  # 重试次数

    # 元数据
    search_config: Dict[str, Any] = field(default_factory=dict)  # 本次执行使用的配置
    firecrawl_request_id: Optional[str] = None  # Firecrawl请求ID（用于追踪）

    # 时间戳
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def start_execution(self) -> None:
        """开始执行"""
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_as_completed(
        self,
        total: int,
        new: int,
        credits: int,
        execution_time: int
    ) -> None:
        """标记为成功完成"""
        self.status = ExecutionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.total_results = total
        self.new_results = new
        self.credits_used = credits
        self.execution_time_ms = execution_time

    def mark_as_failed(
        self,
        error_message: str,
        error_type: str = "unknown"
    ) -> None:
        """标记为失败"""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        self.error_message = error_message
        self.error_type = error_type

    def mark_as_skipped(self, reason: str) -> None:
        """标记为跳过"""
        self.status = ExecutionStatus.SKIPPED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error_message = reason

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "execution_number": self.execution_number,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "status": self.status.value,
            "total_results": self.total_results,
            "new_results": self.new_results,
            "credits_used": self.credits_used,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "retry_count": self.retry_count,
            "search_config": self.search_config,
            "firecrawl_request_id": self.firecrawl_request_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
```

### 2. MongoDB 集合设计

**集合名称**: `search_task_executions`

**索引策略**:
```python
# 1. 任务ID索引（查询某任务的所有执行历史）
{"task_id": 1, "scheduled_time": -1}

# 2. 状态索引（查询失败的执行）
{"status": 1, "scheduled_time": -1}

# 3. 时间索引（查询最近执行）
{"scheduled_time": -1}

# 4. 组合索引（任务+状态查询）
{"task_id": 1, "status": 1, "scheduled_time": -1}
```

**数据示例**:
```json
{
  "_id": "1849365782347890690",
  "task_id": "1849365782347890688",
  "task_name": "缅甸新闻监控",
  "execution_number": 15,
  "scheduled_time": "2025-10-24T09:00:00Z",
  "started_at": "2025-10-24T09:00:01Z",
  "completed_at": "2025-10-24T09:00:03.5Z",
  "execution_time_ms": 2500,
  "status": "completed",
  "total_results": 12,
  "new_results": 3,
  "credits_used": 1,
  "error_message": null,
  "error_type": null,
  "retry_count": 0,
  "search_config": {
    "limit": 20,
    "include_domains": ["www.gnlm.com.mm"]
  },
  "firecrawl_request_id": "req_abc123",
  "created_at": "2025-10-24T09:00:00Z",
  "updated_at": "2025-10-24T09:00:03.5Z"
}
```

---

## 🔧 仓储层设计

### SearchTaskExecutionRepository

```python
from typing import List, Tuple, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.domain.entities.search_task_execution import SearchTaskExecution, ExecutionStatus


class SearchTaskExecutionRepository:
    """搜索任务执行历史仓储"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.search_task_executions

    async def create(self, execution: SearchTaskExecution) -> SearchTaskExecution:
        """创建执行记录"""
        execution_dict = execution.to_dict()
        await self.collection.insert_one({
            "_id": execution.id,
            **execution_dict
        })
        return execution

    async def update(self, execution: SearchTaskExecution) -> bool:
        """更新执行记录"""
        execution_dict = execution.to_dict()
        result = await self.collection.update_one(
            {"_id": execution.id},
            {"$set": execution_dict}
        )
        return result.modified_count > 0

    async def get_by_id(self, execution_id: str) -> Optional[SearchTaskExecution]:
        """根据ID获取执行记录"""
        doc = await self.collection.find_one({"_id": execution_id})
        if doc:
            return self._doc_to_entity(doc)
        return None

    async def list_by_task(
        self,
        task_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[SearchTaskExecution], int]:
        """获取任务的执行历史列表"""
        query = {"task_id": task_id}

        if status:
            query["status"] = status

        # 总数
        total = await self.collection.count_documents(query)

        # 分页查询（按时间倒序）
        skip = (page - 1) * page_size
        cursor = self.collection.find(query).sort("scheduled_time", -1).skip(skip).limit(page_size)

        executions = []
        async for doc in cursor:
            executions.append(self._doc_to_entity(doc))

        return executions, total

    async def get_latest_by_task(self, task_id: str) -> Optional[SearchTaskExecution]:
        """获取任务的最新执行记录"""
        doc = await self.collection.find_one(
            {"task_id": task_id},
            sort=[("scheduled_time", -1)]
        )
        if doc:
            return self._doc_to_entity(doc)
        return None

    async def get_statistics(self, task_id: str) -> Dict[str, Any]:
        """获取任务的执行统计"""
        pipeline = [
            {"$match": {"task_id": task_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "avg_execution_time": {"$avg": "$execution_time_ms"},
                "total_results": {"$sum": "$total_results"},
                "total_credits": {"$sum": "$credits_used"}
            }}
        ]

        stats = {}
        async for doc in self.collection.aggregate(pipeline):
            stats[doc["_id"]] = {
                "count": doc["count"],
                "avg_execution_time_ms": doc["avg_execution_time"],
                "total_results": doc["total_results"],
                "total_credits": doc["total_credits"]
            }

        return stats

    def _doc_to_entity(self, doc: dict) -> SearchTaskExecution:
        """将MongoDB文档转换为实体"""
        # 处理MongoDB的_id字段
        doc["id"] = doc.pop("_id", None)

        # 转换status字段
        if "status" in doc:
            doc["status"] = ExecutionStatus(doc["status"])

        return SearchTaskExecution(**doc)
```

---

## 🚀 调度器集成

### 修改 TaskScheduler

在 `src/services/task_scheduler.py` 中集成执行历史记录：

```python
class TaskScheduler:
    def __init__(self, ...):
        # 添加执行历史仓储
        self.execution_repository = SearchTaskExecutionRepository(db)

    async def execute_task(self, task: SearchTask):
        """执行任务（增强版）"""
        # 1. 创建执行记录
        execution = SearchTaskExecution(
            task_id=task.get_id_string(),
            task_name=task.name,
            execution_number=task.execution_count + 1,
            scheduled_time=datetime.utcnow(),
            search_config=task.search_config
        )
        await self.execution_repository.create(execution)

        # 2. 标记为运行中
        execution.start_execution()
        await self.execution_repository.update(execution)

        try:
            # 3. 执行搜索
            start_time = datetime.utcnow()

            results = await self.search_service.execute_search(
                query=task.query,
                config=task.search_config
            )

            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # 4. 标记为成功
            execution.mark_as_completed(
                total=len(results),
                new=results.new_count,
                credits=results.credits_used,
                execution_time=execution_time_ms
            )
            await self.execution_repository.update(execution)

            # 5. 更新任务统计
            task.record_execution(
                success=True,
                results_count=len(results),
                credits_used=results.credits_used
            )
            await self.task_repository.update(task)

        except Exception as e:
            # 6. 标记为失败
            execution.mark_as_failed(
                error_message=str(e),
                error_type=type(e).__name__
            )
            await self.execution_repository.update(execution)

            # 7. 更新任务统计
            task.record_execution(success=False)
            await self.task_repository.update(task)

            logger.error(f"任务执行失败: {task.name}, 错误: {e}")
```

---

## 🌐 API 端点设计

### 1. 获取任务执行历史列表

```
GET /search-tasks/{task_id}/executions

Query Parameters:
- page: 页码（默认1）
- page_size: 每页数量（默认20，最大100）
- status: 状态过滤（pending, running, completed, failed, skipped）

Response:
{
  "executions": [
    {
      "id": "1849365782347890690",
      "task_id": "1849365782347890688",
      "task_name": "缅甸新闻监控",
      "execution_number": 15,
      "scheduled_time": "2025-10-24T09:00:00Z",
      "started_at": "2025-10-24T09:00:01Z",
      "completed_at": "2025-10-24T09:00:03.5Z",
      "execution_time_ms": 2500,
      "status": "completed",
      "total_results": 12,
      "new_results": 3,
      "credits_used": 1
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### 2. 获取单次执行详情

```
GET /search-tasks/{task_id}/executions/{execution_id}

Response:
{
  "id": "1849365782347890690",
  "task_id": "1849365782347890688",
  "task_name": "缅甸新闻监控",
  "execution_number": 15,
  "scheduled_time": "2025-10-24T09:00:00Z",
  "started_at": "2025-10-24T09:00:01Z",
  "completed_at": "2025-10-24T09:00:03.5Z",
  "execution_time_ms": 2500,
  "status": "completed",
  "total_results": 12,
  "new_results": 3,
  "credits_used": 1,
  "error_message": null,
  "error_type": null,
  "search_config": {
    "limit": 20,
    "include_domains": ["www.gnlm.com.mm"]
  }
}
```

### 3. 获取任务执行统计

```
GET /search-tasks/{task_id}/executions/statistics

Response:
{
  "total_executions": 150,
  "successful_executions": 142,
  "failed_executions": 8,
  "success_rate": 94.67,
  "avg_execution_time_ms": 2340,
  "total_results": 1850,
  "total_credits_used": 150,
  "last_execution": {
    "id": "1849365782347890690",
    "status": "completed",
    "scheduled_time": "2025-10-24T09:00:00Z",
    "execution_time_ms": 2500
  },
  "status_distribution": {
    "completed": 142,
    "failed": 8,
    "running": 0,
    "pending": 0
  }
}
```

---

## 📈 使用场景

### 1. 监控任务健康度
```python
# 查看最近10次执行
GET /search-tasks/{task_id}/executions?page_size=10

# 查看失败的执行
GET /search-tasks/{task_id}/executions?status=failed

# 获取统计信息
GET /search-tasks/{task_id}/executions/statistics
```

### 2. 错误诊断
```python
# 查找错误执行
executions = await repo.list_by_task(task_id, status="failed")

for execution in executions:
    print(f"执行#{execution.execution_number}失败")
    print(f"  时间: {execution.scheduled_time}")
    print(f"  错误: {execution.error_message}")
    print(f"  类型: {execution.error_type}")
```

### 3. 性能分析
```python
# 获取统计数据
stats = await repo.get_statistics(task_id)

print(f"平均执行时间: {stats['completed']['avg_execution_time_ms']}ms")
print(f"总结果数: {stats['completed']['total_results']}")
print(f"总积分消耗: {stats['completed']['total_credits']}")
```

---

## 📋 实施计划

### Phase 1: 核心实体和仓储（1-2小时）
- [x] 分析现状
- [ ] 创建 SearchTaskExecution 实体
- [ ] 实现 SearchTaskExecutionRepository
- [ ] 添加MongoDB索引

### Phase 2: 调度器集成（1小时）
- [ ] 修改 TaskScheduler 集成执行历史记录
- [ ] 添加错误处理和状态更新

### Phase 3: API端点（1小时）
- [ ] 添加执行历史查询端点
- [ ] 添加执行详情端点
- [ ] 添加统计端点

### Phase 4: 测试和文档（1小时）
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 更新API文档

---

## 🎯 预期收益

1. **可观测性提升**: 完整的执行历史追踪
2. **故障诊断**: 快速定位执行失败原因
3. **性能优化**: 基于历史数据优化配置
4. **审计追踪**: 完整的操作记录
5. **数据分析**: 支持BI和数据可视化

---

## ⚠️ 注意事项

1. **存储空间**: 历史记录会持续增长，需要考虑数据归档策略
2. **查询性能**: 需要合理设计索引，避免大数据量查询性能问题
3. **并发安全**: 调度器和API并发访问需要保证数据一致性
4. **数据保留**: 建议保留最近3-6个月的执行历史，旧数据可归档
