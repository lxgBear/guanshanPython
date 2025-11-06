# 搜索结果职责分离 - 实施指南

**日期**: 2025-11-03
**版本**: v1.0.0
**范围**: 定时任务系统（智能搜索暂不涉及）
**预计工期**: 9天
**风险等级**: 中等（涉及数据模型变更和迁移）

---

## 📋 实施概览

### 总体策略

本次实施采用**渐进式迁移**策略，确保系统稳定性：

1. **Phase 1-2**: 新功能开发（并行运行）
2. **Phase 3**: API适配（兼容性保证）
3. **Phase 4**: 数据迁移（可回滚）
4. **Phase 5**: 测试验证（全面覆盖）

### 关键原则

- ✅ **向后兼容**: 现有API继续工作
- ✅ **渐进部署**: 分阶段上线
- ✅ **可回滚**: 每个阶段都可以回滚
- ✅ **数据安全**: 迁移前完整备份

---

## Phase 1: 数据模型和实体（Day 1-2）

### Day 1: 创建新实体类

#### 1.1 创建 ProcessedResult 实体

**文件**: `src/core/domain/entities/processed_result.py`

```python
"""AI处理结果实体模型

v2.0.0 新增：
- 分离原始数据和AI处理结果
- 支持AI处理状态管理
- 支持用户操作（留存、删除、评分）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from src.infrastructure.id_generator import generate_string_id


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
    """
    AI处理结果实体

    职责：
    1. 存储AI分析、翻译、总结后的数据
    2. 管理用户操作状态（留存、删除）
    3. 记录AI处理元数据

    v2.0.0 设计原则：
    - 关联原始结果（raw_result_id）
    - 状态驱动（ProcessedStatus）
    - 支持重试机制
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)

    # 关联原始结果
    raw_result_id: str = ""  # 关联 search_results 的 ID
    task_id: str = ""        # 关联的搜索任务ID

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
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None  # AI处理完成时间
    updated_at: datetime = field(default_factory=datetime.utcnow)

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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "id": self.id,
            "raw_result_id": self.raw_result_id,
            "task_id": self.task_id,
            "translated_title": self.translated_title,
            "translated_content": self.translated_content,
            "summary": self.summary,
            "key_points": self.key_points,
            "sentiment": self.sentiment,
            "categories": self.categories,
            "ai_model": self.ai_model,
            "ai_processing_time_ms": self.ai_processing_time_ms,
            "ai_confidence_score": self.ai_confidence_score,
            "status": self.status.value,
            "user_rating": self.user_rating,
            "user_notes": self.user_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processing_error": self.processing_error,
            "retry_count": self.retry_count
        }
```

**验证点**:
- [ ] 所有字段类型正确
- [ ] 状态转换方法完整
- [ ] to_dict() 方法完整

#### 1.2 修改 SearchResult 实体

**文件**: `src/core/domain/entities/search_result.py`

**修改内容**:

```python
# 移除以下字段（行79-82）:
# status: ResultStatus = ResultStatus.PENDING
# processed_at: Optional[datetime] = None

# 移除以下方法（行77-85）:
# def mark_as_archived(self) -> None
# def mark_as_deleted(self) -> None
```

**修改后的实体**:
```python
@dataclass
class SearchResult:
    """搜索结果实体（v2.0.0 简化版 - 纯原始数据存储）

    职责：只负责存储从Firecrawl获取的原始数据
    不包含：状态管理、用户操作、AI处理标记
    """
    # 主键（雪花算法ID）
    id: str = field(default_factory=generate_string_id)
    task_id: str = ""

    # 核心原始数据
    title: str = ""
    url: str = ""
    content: str = ""
    snippet: Optional[str] = None

    # ... 其他原始数据字段保持不变 ...

    # 时间戳（简化）
    created_at: datetime = field(default_factory=datetime.utcnow)
    # ❌ 移除 processed_at

    # 测试标记
    is_test_data: bool = False

    # ❌ 移除状态相关方法
    # 保留 to_summary() 方法
```

**验证点**:
- [ ] status 字段已移除
- [ ] processed_at 字段已移除
- [ ] mark_as_archived/deleted 方法已移除
- [ ] to_summary() 方法保留

---

### Day 2: 创建和修改 Repository

#### 2.1 创建 ProcessedResultRepository

**文件**: `src/infrastructure/database/processed_result_repositories.py`

```python
"""AI处理结果仓储实现

v2.0.0 新增：
- 管理AI处理结果的CRUD操作
- 支持状态管理和统计
- 支持重试机制
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.core.domain.entities.processed_result import ProcessedResult, ProcessedStatus
from src.infrastructure.database.connection import get_mongodb_database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProcessedResultRepository:
    """AI处理结果仓储"""

    def __init__(self):
        self.collection_name = "processed_results_new"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    def _result_to_dict(self, result: ProcessedResult) -> Dict[str, Any]:
        """将结果实体转换为字典"""
        return {
            "_id": result.id,
            "raw_result_id": result.raw_result_id,
            "task_id": result.task_id,
            "translated_title": result.translated_title,
            "translated_content": result.translated_content,
            "summary": result.summary,
            "key_points": result.key_points,
            "sentiment": result.sentiment,
            "categories": result.categories,
            "ai_model": result.ai_model,
            "ai_processing_time_ms": result.ai_processing_time_ms,
            "ai_confidence_score": result.ai_confidence_score,
            "ai_metadata": result.ai_metadata,
            "status": result.status.value,
            "user_rating": result.user_rating,
            "user_notes": result.user_notes,
            "created_at": result.created_at,
            "processed_at": result.processed_at,
            "updated_at": result.updated_at,
            "processing_error": result.processing_error,
            "retry_count": result.retry_count
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> ProcessedResult:
        """将字典转换为结果实体"""
        return ProcessedResult(
            id=data.get("_id", ""),
            raw_result_id=data.get("raw_result_id", ""),
            task_id=data.get("task_id", ""),
            translated_title=data.get("translated_title"),
            translated_content=data.get("translated_content"),
            summary=data.get("summary"),
            key_points=data.get("key_points", []),
            sentiment=data.get("sentiment"),
            categories=data.get("categories", []),
            ai_model=data.get("ai_model"),
            ai_processing_time_ms=data.get("ai_processing_time_ms", 0),
            ai_confidence_score=data.get("ai_confidence_score", 0.0),
            ai_metadata=data.get("ai_metadata", {}),
            status=ProcessedStatus(data.get("status", "pending")),
            user_rating=data.get("user_rating"),
            user_notes=data.get("user_notes"),
            created_at=data.get("created_at", datetime.utcnow()),
            processed_at=data.get("processed_at"),
            updated_at=data.get("updated_at", datetime.utcnow()),
            processing_error=data.get("processing_error"),
            retry_count=data.get("retry_count", 0)
        )

    async def create_pending_result(
        self,
        raw_result_id: str,
        task_id: str
    ) -> ProcessedResult:
        """
        创建待处理的结果记录

        Args:
            raw_result_id: 原始结果ID
            task_id: 任务ID

        Returns:
            创建的ProcessedResult实体
        """
        try:
            collection = await self._get_collection()

            result = ProcessedResult(
                raw_result_id=raw_result_id,
                task_id=task_id,
                status=ProcessedStatus.PENDING
            )

            result_dict = self._result_to_dict(result)
            await collection.insert_one(result_dict)

            logger.info(f"创建待处理记录: raw_result_id={raw_result_id}")
            return result

        except Exception as e:
            logger.error(f"创建待处理记录失败: {e}")
            raise

    async def update_processing_status(
        self,
        result_id: str,
        status: ProcessedStatus,
        **kwargs
    ) -> bool:
        """更新处理状态"""
        try:
            collection = await self._get_collection()

            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }
            update_data.update(kwargs)

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"更新处理状态失败: {e}")
            raise

    async def save_ai_result(
        self,
        result_id: str,
        translated_title: str,
        translated_content: str,
        summary: str,
        key_points: List[str],
        ai_model: str,
        processing_time_ms: int,
        **kwargs
    ) -> bool:
        """保存AI处理结果"""
        try:
            collection = await self._get_collection()

            update_data = {
                "translated_title": translated_title,
                "translated_content": translated_content,
                "summary": summary,
                "key_points": key_points,
                "ai_model": ai_model,
                "ai_processing_time_ms": processing_time_ms,
                "status": ProcessedStatus.COMPLETED.value,
                "processed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            # 合并额外参数
            update_data.update(kwargs)

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info(f"保存AI结果成功: {result_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"保存AI结果失败: {e}")
            raise

    async def get_by_id(self, result_id: str) -> Optional[ProcessedResult]:
        """根据ID获取处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"获取处理结果失败: {e}")
            raise

    async def get_by_raw_result_id(
        self,
        raw_result_id: str
    ) -> Optional[ProcessedResult]:
        """根据原始结果ID获取处理结果"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"raw_result_id": raw_result_id})

            if data:
                return self._dict_to_result(data)
            return None

        except Exception as e:
            logger.error(f"根据原始ID获取处理结果失败: {e}")
            raise

    async def get_by_task(
        self,
        task_id: str,
        status: Optional[ProcessedStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[ProcessedResult], int]:
        """获取任务的处理结果（支持状态筛选）"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            filter_dict = {"task_id": task_id}
            if status:
                filter_dict["status"] = status.value

            # 计算总数
            total = await collection.count_documents(filter_dict)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(filter_dict).sort("updated_at", -1).skip(skip).limit(page_size)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results, total

        except Exception as e:
            logger.error(f"获取任务处理结果失败: {e}")
            raise

    async def update_user_action(
        self,
        result_id: str,
        status: ProcessedStatus,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> bool:
        """更新用户操作（留存、删除、评分）"""
        try:
            collection = await self._get_collection()

            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }

            if user_rating is not None:
                update_data["user_rating"] = user_rating
            if user_notes is not None:
                update_data["user_notes"] = user_notes

            result = await collection.update_one(
                {"_id": result_id},
                {"$set": update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"更新用户操作失败: {e}")
            raise

    async def get_status_statistics(self, task_id: str) -> Dict[str, int]:
        """获取任务的状态统计"""
        try:
            collection = await self._get_collection()

            pipeline = [
                {"$match": {"task_id": task_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]

            status_counts = {status.value: 0 for status in ProcessedStatus}

            async for doc in collection.aggregate(pipeline):
                status_counts[doc["_id"]] = doc["count"]

            return status_counts

        except Exception as e:
            logger.error(f"获取状态统计失败: {e}")
            raise

    async def get_failed_results(
        self,
        max_retry: int = 3
    ) -> List[ProcessedResult]:
        """获取失败的结果（用于重试）"""
        try:
            collection = await self._get_collection()

            cursor = collection.find({
                "status": ProcessedStatus.FAILED.value,
                "retry_count": {"$lt": max_retry}
            }).limit(100)

            results = []
            async for data in cursor:
                results.append(self._dict_to_result(data))

            return results

        except Exception as e:
            logger.error(f"获取失败结果失败: {e}")
            raise

    async def delete_by_task(self, task_id: str) -> int:
        """删除任务的所有处理结果（级联删除）"""
        try:
            collection = await self._get_collection()
            result = await collection.delete_many({"task_id": task_id})

            logger.info(f"删除任务处理结果: {task_id}, 删除数量: {result.deleted_count}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"删除任务处理结果失败: {e}")
            raise
```

**验证点**:
- [ ] 所有CRUD方法完整
- [ ] 状态管理方法完整
- [ ] 错误处理完善

#### 2.2 修改 SearchResultRepository

**文件**: `src/infrastructure/database/repositories.py`

**修改内容**:

1. **修改 `save_results` 方法返回ID列表**:

```python
async def save_results(self, results: List[SearchResult]) -> List[str]:
    """批量保存搜索结果

    v2.0.0: 返回保存的ID列表，用于通知AI服务

    Returns:
        保存的结果ID列表
    """
    if not results:
        return []

    try:
        collection = await self._get_collection()
        result_dicts = [self._result_to_dict(result) for result in results]

        await collection.insert_many(result_dicts)
        saved_ids = [result.id for result in results]

        logger.info(f"保存搜索结果成功: {len(results)}条")
        return saved_ids

    except Exception as e:
        logger.error(f"保存搜索结果失败: {e}")
        raise
```

2. **移除状态管理方法**（约422-599行）:

```python
# ❌ 移除以下方法:
# - get_results_by_status()
# - count_by_status()
# - update_result_status()
# - bulk_update_status()
# - get_status_distribution()
```

**验证点**:
- [ ] save_results 返回ID列表
- [ ] 状态管理方法已移除
- [ ] 基础CRUD方法保留

#### 2.3 创建数据库索引

**脚本**: `scripts/create_processed_results_new_indexes.py`

```python
"""创建 processed_results_new 集合索引"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def create_indexes():
    # 连接数据库
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "intelligent_system")

    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]
    collection = db["processed_results_new"]

    # 创建索引
    await collection.create_index("raw_result_id", unique=True)
    await collection.create_index([("task_id", 1), ("status", 1), ("updated_at", -1)])
    await collection.create_index([("status", 1), ("retry_count", 1)])

    print("✅ processed_results_new 索引创建成功")
    client.close()

if __name__ == "__main__":
    asyncio.run(create_indexes())
```

**执行**:
```bash
python scripts/create_processed_results_new_indexes.py
```

---

## Phase 2: 定时任务集成（Day 3-4）

### Day 3: 修改 TaskSchedulerService

**文件**: `src/services/task_scheduler.py`

**修改位置**: `_execute_search_task` 方法（第278行开始）

**修改内容**:

```python
async def _execute_search_task(self, task_id: str):
    """执行单个搜索任务（v2.0.0 职责分离版本）

    新增功能：
    1. 保存原始结果到 search_results
    2. 创建待处理记录到 processed_results_new
    3. 通知AI服务处理
    """
    start_time = datetime.utcnow()
    logger.info(f"🔍 开始执行搜索任务: {task_id}")

    try:
        # 获取任务详情
        repo = await self._get_task_repository()
        task = await repo.get_by_id(task_id)

        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        if not task.is_active:
            logger.info(f"任务已禁用，跳过执行: {task.name}")
            return

        # 更新任务状态
        task.last_executed_at = start_time

        # ========================================
        # 1. 执行搜索/爬取（保持原逻辑）
        # ========================================
        if task.crawl_url:
            logger.info(f"🌐 使用网址爬取模式: {task.crawl_url}")
            result_batch = await self._execute_crawl_task_internal(task, start_time)
        else:
            logger.info(f"🔍 使用关键词搜索模式: {task.query}")
            user_config = UserSearchConfig.from_json(task.search_config)
            result_batch = await self.search_adapter.search(
                query=task.query,
                user_config=user_config,
                task_id=str(task.id)
            )

        # ========================================
        # 2. 保存原始结果（v2.0.0: 返回ID列表）
        # ========================================
        saved_ids = []
        if result_batch.results:
            try:
                result_repo = await self._get_result_repository()
                if result_repo:
                    # v2.0.0: save_results 返回ID列表
                    saved_ids = await result_repo.save_results(result_batch.results)
                    logger.info(f"✅ 原始结果已保存: {len(saved_ids)}条")
                else:
                    logger.warning("⚠️  MongoDB不可用，搜索结果未保存")
            except Exception as e:
                logger.error(f"❌ 保存搜索结果失败: {e}")
                # 失败不影响任务继续执行

        # ========================================
        # 3. 【新增】创建待处理记录
        # ========================================
        if saved_ids:
            try:
                from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
                processed_repo = ProcessedResultRepository()

                for raw_id in saved_ids:
                    await processed_repo.create_pending_result(
                        raw_result_id=raw_id,
                        task_id=task_id
                    )

                logger.info(f"✅ 创建待处理记录: {len(saved_ids)}条")
            except Exception as e:
                logger.error(f"❌ 创建待处理记录失败: {e}")
                # 失败不影响任务继续执行

        # ========================================
        # 4. 【新增】通知AI服务
        # ========================================
        if saved_ids:
            try:
                await self._notify_ai_service(saved_ids, task_id)
                logger.info(f"✅ AI服务通知已发送: {len(saved_ids)}条结果")
            except Exception as e:
                logger.error(f"⚠️  AI服务通知失败: {e}")
                # 通知失败不影响任务完成，AI服务可以轮询

        # ========================================
        # 5. 更新任务统计（保持原逻辑）
        # ========================================
        task.record_execution(
            success=result_batch.success,
            results_count=result_batch.returned_count,
            credits_used=result_batch.credits_used
        )

        # 计算下次执行时间
        interval = ScheduleInterval.from_value(task.schedule_interval)
        trigger = CronTrigger.from_crontab(interval.cron_expression)
        next_run = trigger.get_next_fire_time(None, datetime.now())
        if next_run:
            task.next_run_time = next_run

        # 保存任务更新
        await repo.update(task)

        execution_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"✅ 搜索任务执行完成: {task.name} | "
            f"结果数: {result_batch.returned_count} | "
            f"耗时: {execution_time:.2f}s | "
            f"下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else 'N/A'}"
        )

    except Exception as e:
        logger.error(f"❌ 搜索任务执行失败 {task_id}: {e}")

        # 记录失败
        try:
            repo = await self._get_task_repository()
            task = await repo.get_by_id(task_id)
            if task:
                task.record_execution(success=False)
                await repo.update(task)
        except Exception as update_error:
            logger.error(f"更新失败统计时出错: {update_error}")
```

**验证点**:
- [ ] 原始结果保存返回ID列表
- [ ] 创建待处理记录成功
- [ ] AI服务通知逻辑完整

### Day 4: 实现AI服务通知

**新增方法**: `_notify_ai_service` in `TaskSchedulerService`

```python
async def _notify_ai_service(
    self,
    raw_result_ids: List[str],
    task_id: str
) -> None:
    """
    通知AI服务处理新的搜索结果

    通知方式：HTTP POST请求到AI服务

    Args:
        raw_result_ids: 原始结果ID列表
        task_id: 任务ID
    """
    import httpx
    import os

    ai_service_url = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
    notify_endpoint = f"{ai_service_url}/api/v1/ai/process-results"

    payload = {
        "raw_result_ids": raw_result_ids,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat()
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(notify_endpoint, json=payload)

            if response.status_code == 202:  # Accepted
                logger.info(f"✅ AI服务接受处理请求: {len(raw_result_ids)}条")
            else:
                logger.warning(f"⚠️  AI服务响应异常: {response.status_code}")

    except httpx.RequestError as e:
        logger.error(f"❌ AI服务通知失败 (网络错误): {e}")
        # 不抛出异常，AI服务可以通过轮询获取待处理任务
    except Exception as e:
        logger.error(f"❌ AI服务通知失败 (未知错误): {e}")
```

**环境变量配置**:

```bash
# .env
AI_SERVICE_URL=http://localhost:8001  # AI服务地址
```

**验证点**:
- [ ] HTTP请求正常发送
- [ ] 错误处理完善
- [ ] 不阻塞主流程

---

## Phase 3: API层适配（Day 5-6）

### Day 5: 修改查询API

**文件**: `src/api/v1/endpoints/search_results_frontend.py`

**修改内容**:

1. **添加新的查询端点（默认返回processed_results_new）**:

```python
from src.infrastructure.database.processed_result_repositories import ProcessedResultRepository
from src.core.domain.entities.processed_result import ProcessedStatus

@router.get("/api/v1/search-tasks/{task_id}/results", summary="获取任务结果（v2.0.0）")
async def get_task_results(
    task_id: str,
    view: str = "processed",  # "processed" | "raw"
    status: Optional[str] = None,  # ProcessedStatus值
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    获取任务的搜索结果

    v2.0.0 变更：
    - 默认返回 processed_results_new（AI处理后的结果）
    - 支持 view=raw 查看原始结果
    - 支持按 ProcessedStatus 筛选

    Args:
        task_id: 任务ID
        view: 视图模式（processed: AI处理结果, raw: 原始结果）
        status: 状态筛选（pending/processing/completed/failed/archived/deleted）
        page: 页码
        page_size: 每页数量
    """
    try:
        if view == "raw":
            # 返回原始结果（向后兼容）
            repo = SearchResultRepository()
            results, total = await repo.get_by_task(task_id, page, page_size)

            return {
                "task_id": task_id,
                "view": "raw",
                "results": [result.to_summary() for result in results],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "pages": (total + page_size - 1) // page_size
                }
            }

        else:  # view == "processed" (默认)
            # 返回AI处理结果
            repo = ProcessedResultRepository()

            # 状态筛选
            status_filter = None
            if status:
                try:
                    status_filter = ProcessedStatus(status)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无效的状态值: {status}"
                    )

            results, total = await repo.get_by_task(
                task_id,
                status=status_filter,
                page=page,
                page_size=page_size
            )

            # 获取状态统计
            status_stats = await repo.get_status_statistics(task_id)

            return {
                "task_id": task_id,
                "view": "processed",
                "statistics": status_stats,
                "results": [result.to_dict() for result in results],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "pages": (total + page_size - 1) // page_size
                }
            }

    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**验证点**:
- [ ] 默认返回processed_results_new
- [ ] view=raw 返回原始结果
- [ ] 状态筛选正常工作
- [ ] 分页正确

### Day 6: 新增用户操作API

**新增端点**:

```python
@router.post(
    "/api/v1/processed-results/{result_id}/archive",
    summary="留存结果"
)
async def archive_result(result_id: str, user_notes: Optional[str] = None):
    """用户标记结果为留存"""
    repo = ProcessedResultRepository()
    success = await repo.update_user_action(
        result_id,
        ProcessedStatus.ARCHIVED,
        user_notes=user_notes
    )

    if not success:
        raise HTTPException(status_code=404, detail="结果不存在")

    return {"success": True, "message": "已标记为留存"}


@router.post(
    "/api/v1/processed-results/{result_id}/delete",
    summary="删除结果（软删除）"
)
async def delete_result(result_id: str):
    """用户标记结果为删除"""
    repo = ProcessedResultRepository()
    success = await repo.update_user_action(
        result_id,
        ProcessedStatus.DELETED
    )

    if not success:
        raise HTTPException(status_code=404, detail="结果不存在")

    return {"success": True, "message": "已删除"}


@router.put(
    "/api/v1/processed-results/{result_id}/rating",
    summary="评分结果"
)
async def rate_result(
    result_id: str,
    rating: int = Query(..., ge=1, le=5),
    user_notes: Optional[str] = None
):
    """用户对结果进行评分"""
    repo = ProcessedResultRepository()

    # 获取当前结果
    result = await repo.get_by_id(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")

    # 更新评分
    success = await repo.update_user_action(
        result_id,
        result.status,  # 保持原状态
        user_rating=rating,
        user_notes=user_notes
    )

    return {"success": True, "rating": rating}
```

**验证点**:
- [ ] 留存API正常工作
- [ ] 删除API正常工作
- [ ] 评分API正常工作

---

## Phase 4: 数据迁移（Day 7）

### 创建迁移脚本

**文件**: `scripts/migrate_search_results_to_processed.py`

```python
"""
将现有 search_results 迁移到 processed_results_new

迁移策略：
1. 读取所有 search_results
2. 为每条记录创建对应的 processed_results_new
3. 初始状态设为 PENDING
4. 保留原始数据中的 status 映射
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

async def migrate():
    # 连接数据库
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "intelligent_system")

    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]

    search_results_col = db["search_results"]
    processed_results_new_col = db["processed_results_new"]

    # 统计
    total = await search_results_col.count_documents({})
    migrated = 0
    skipped = 0

    print(f"开始迁移，共 {total} 条记录...")

    # 分批处理（每批1000条）
    batch_size = 1000
    skip = 0

    while skip < total:
        # 读取一批原始结果
        cursor = search_results_col.find({}).skip(skip).limit(batch_size)

        batch = []
        async for doc in cursor:
            raw_id = doc["_id"]
            task_id = doc.get("task_id", "")

            # 检查是否已存在
            existing = await processed_results_new_col.find_one({"raw_result_id": raw_id})
            if existing:
                skipped += 1
                continue

            # 创建processed_result文档
            processed_doc = {
                "_id": f"processed_{raw_id}",  # 生成新ID
                "raw_result_id": raw_id,
                "task_id": task_id,
                "translated_title": None,
                "translated_content": None,
                "summary": None,
                "key_points": [],
                "sentiment": None,
                "categories": [],
                "ai_model": None,
                "ai_processing_time_ms": 0,
                "ai_confidence_score": 0.0,
                "ai_metadata": {},
                "status": "pending",  # 初始状态为PENDING
                "user_rating": None,
                "user_notes": None,
                "created_at": doc.get("created_at", datetime.utcnow()),
                "processed_at": None,
                "updated_at": datetime.utcnow(),
                "processing_error": None,
                "retry_count": 0
            }

            batch.append(processed_doc)
            migrated += 1

        # 批量插入
        if batch:
            await processed_results_new_col.insert_many(batch)
            print(f"已迁移 {migrated}/{total} 条记录...")

        skip += batch_size

    print(f"✅ 迁移完成：")
    print(f"  - 总记录数: {total}")
    print(f"  - 已迁移: {migrated}")
    print(f"  - 已跳过: {skipped}")

    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

**执行迁移**:

```bash
# 1. 备份数据库（重要！）
mongodump --uri="mongodb://localhost:27017/intelligent_system" --out=./backup_$(date +%Y%m%d)

# 2. 执行迁移
python scripts/migrate_search_results_to_processed.py

# 3. 验证迁移结果
python scripts/verify_migration.py
```

**验证脚本**: `scripts/verify_migration.py`

```python
"""验证迁移结果"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def verify():
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "intelligent_system")

    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]

    search_results_count = await db.search_results.count_documents({})
    processed_results_new_count = await db.processed_results_new.count_documents({})

    print(f"search_results 记录数: {search_results_count}")
    print(f"processed_results_new 记录数: {processed_results_new_count}")

    if search_results_count == processed_results_new_count:
        print("✅ 迁移验证成功：记录数一致")
    else:
        print("❌ 迁移验证失败：记录数不一致")
        print(f"   差异: {abs(search_results_count - processed_results_new_count)} 条")

    # 检查关联关系
    cursor = db.processed_results_new.aggregate([
        {
            "$lookup": {
                "from": "search_results",
                "localField": "raw_result_id",
                "foreignField": "_id",
                "as": "raw"
            }
        },
        {"$match": {"raw": {"$size": 0}}},
        {"$count": "orphaned"}
    ])

    orphaned = 0
    async for doc in cursor:
        orphaned = doc.get("orphaned", 0)

    if orphaned > 0:
        print(f"⚠️  发现 {orphaned} 条孤立记录（无对应原始结果）")
    else:
        print("✅ 关联关系验证成功：无孤立记录")

    client.close()

if __name__ == "__main__":
    asyncio.run(verify())
```

---

## Phase 5: 测试和文档（Day 8-9）

### Day 8: 单元测试和集成测试

**创建测试文件**: `tests/test_processed_result.py`

```python
"""ProcessedResult 单元测试"""

import pytest
from datetime import datetime
from src.core.domain.entities.processed_result import (
    ProcessedResult,
    ProcessedStatus
)

def test_create_processed_result():
    """测试创建ProcessedResult"""
    result = ProcessedResult(
        raw_result_id="test_raw_id",
        task_id="test_task_id"
    )

    assert result.raw_result_id == "test_raw_id"
    assert result.task_id == "test_task_id"
    assert result.status == ProcessedStatus.PENDING
    assert result.retry_count == 0


def test_mark_as_processing():
    """测试标记为处理中"""
    result = ProcessedResult(
        raw_result_id="test_raw_id",
        task_id="test_task_id"
    )

    result.mark_as_processing()

    assert result.status == ProcessedStatus.PROCESSING


def test_mark_as_completed():
    """测试标记为完成"""
    result = ProcessedResult(
        raw_result_id="test_raw_id",
        task_id="test_task_id"
    )

    result.mark_as_completed("gpt-4", 5000)

    assert result.status == ProcessedStatus.COMPLETED
    assert result.ai_model == "gpt-4"
    assert result.ai_processing_time_ms == 5000
    assert result.processed_at is not None


def test_mark_as_failed():
    """测试标记为失败"""
    result = ProcessedResult(
        raw_result_id="test_raw_id",
        task_id="test_task_id"
    )

    result.mark_as_failed("AI服务错误")

    assert result.status == ProcessedStatus.FAILED
    assert result.processing_error == "AI服务错误"
    assert result.retry_count == 1


def test_status_transitions():
    """测试状态流转"""
    result = ProcessedResult(
        raw_result_id="test_raw_id",
        task_id="test_task_id"
    )

    # PENDING -> PROCESSING
    result.mark_as_processing()
    assert result.status == ProcessedStatus.PROCESSING

    # PROCESSING -> COMPLETED
    result.mark_as_completed("gpt-4", 5000)
    assert result.status == ProcessedStatus.COMPLETED

    # COMPLETED -> ARCHIVED
    result.mark_as_archived()
    assert result.status == ProcessedStatus.ARCHIVED
```

**创建Repository测试**: `tests/test_processed_result_repository.py`

**创建集成测试**: `tests/integration/test_scheduled_task_flow.py`

### Day 9: 文档更新

**更新文档**:

1. **API_GUIDE.md**: 添加新的API端点文档
2. **DATABASE_COLLECTIONS_GUIDE.md**: 更新集合职责说明
3. **SYSTEM_ARCHITECTURE.md**: 更新架构图
4. **VERSION_MANAGEMENT.md**: 记录v2.0.0变更

---

## 🚨 风险管理

### 风险识别

| 风险 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 数据迁移失败 | 高 | 低 | 完整备份 + 回滚脚本 |
| AI服务通知失败 | 中 | 中 | 轮询机制兜底 |
| 前端兼容性问题 | 中 | 低 | 向后兼容API设计 |
| 性能下降 | 中 | 低 | 索引优化 + 监控 |

### 回滚方案

**回滚条件**:
- 数据迁移失败率 >5%
- API错误率 >10%
- 性能下降 >30%

**回滚步骤**:
1. 停止定时任务调度器
2. 恢复数据库备份
3. 回退代码到上一版本
4. 重启服务

---

## ✅ 验收标准

### 功能验收

- [ ] 定时任务正常执行并保存原始结果
- [ ] processed_results_new 记录自动创建
- [ ] AI服务通知正常发送
- [ ] 查询API返回正确数据
- [ ] 用户操作API正常工作

### 性能验收

- [ ] 定时任务执行时间增加 <10%
- [ ] API响应时间 <200ms
- [ ] 数据库查询效率无明显下降

### 数据验收

- [ ] 历史数据迁移成功率 >99%
- [ ] 关联关系完整性 100%
- [ ] 无孤立记录

---

## 📞 相关文档

- [架构设计文档](SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md)
- [UML图目录](diagrams/)
- [API文档更新](../docs/API_GUIDE.md)
- [数据库集合指南](../docs/DATABASE_COLLECTIONS_GUIDE.md)

---

**文档作者**: Claude Code Assistant
**文档状态**: ✅ 实施指南完成
**审核人**: Backend Team
**预计开始日期**: 待定
**预计完成日期**: 开始后9个工作日
