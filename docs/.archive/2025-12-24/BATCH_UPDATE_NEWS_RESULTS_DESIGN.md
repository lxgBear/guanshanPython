# 批量修改 news_results 字段功能设计文档

**版本**: v1.0.0
**状态**: 🚧 设计阶段
**创建日期**: 2025-11-13
**设计人员**: Backend Team

---

## 📋 目录

1. [需求分析](#需求分析)
2. [功能设计](#功能设计)
3. [数据模型设计](#数据模型设计)
4. [API设计](#api设计)
5. [数据库设计](#数据库设计)
6. [仓储层设计](#仓储层设计)
7. [安全性设计](#安全性设计)
8. [实现方案](#实现方案)
9. [测试方案](#测试方案)
10. [风险评估](#风险评估)

---

## 需求分析

### 功能需求

#### FR-1: 批量修改字段内容
- **描述**: 用户可以批量修改 `news_results` 集合中的 `markdown_content` 和 `content` 字段
- **优先级**: 高
- **使用场景**:
  - 批量更正内容错误
  - 批量格式化内容
  - 批量添加或删除内容片段

#### FR-2: 按任务批量修改
- **描述**: 支持按 `task_id` 批量修改所有相关结果
- **优先级**: 高
- **使用场景**: 修改整个搜索任务的所有结果

#### FR-3: 按ID列表批量修改
- **描述**: 支持按 `result_id` 列表批量修改指定的多个结果
- **优先级**: 高
- **使用场景**: 精确修改用户选择的特定结果

#### FR-4: 修改历史记录
- **描述**: 记录每次批量修改的历史，支持查询和回滚
- **优先级**: 中
- **使用场景**:
  - 审计和追踪修改记录
  - 回滚错误的批量修改
  - 分析修改模式

### 非功能需求

#### NFR-1: 性能要求
- 批量修改 100 条记录耗时 < 5 秒
- 批量修改 1000 条记录耗时 < 30 秒
- 支持异步批量修改大数据集

#### NFR-2: 安全性要求
- 操作需要身份验证
- 记录操作者信息
- 防止恶意批量修改

#### NFR-3: 可靠性要求
- 批量修改失败时支持部分回滚
- 修改历史持久化存储
- 错误日志完整记录

---

## 功能设计

### 功能模块

```
┌─────────────────────────────────────────────────────────────────┐
│                    批量修改功能架构                               │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              API层（FastAPI）                              │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  POST /batch-updates                                │  │  │
│  │  │  - 创建批量修改任务                                 │  │  │
│  │  ├─────────────────────────────────────────────────────┤  │  │
│  │  │  GET /batch-updates/{update_id}                     │  │  │
│  │  │  - 查询批量修改状态                                 │  │  │
│  │  ├─────────────────────────────────────────────────────┤  │  │
│  │  │  GET /batch-updates/{update_id}/history             │  │  │
│  │  │  - 查询修改历史                                     │  │  │
│  │  ├─────────────────────────────────────────────────────┤  │  │
│  │  │  POST /batch-updates/{update_id}/rollback           │  │  │
│  │  │  - 回滚批量修改                                     │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           服务层（BatchUpdateService）                     │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  - 验证修改参数                                     │  │  │
│  │  │  - 执行批量修改                                     │  │  │
│  │  │  - 记录修改历史                                     │  │  │
│  │  │  - 处理异步任务                                     │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           仓储层（Repositories）                           │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  ProcessedResultRepository                          │  │  │
│  │  │  - batch_update_fields()                            │  │  │
│  │  ├─────────────────────────────────────────────────────┤  │  │
│  │  │  BatchUpdateHistoryRepository                       │  │  │
│  │  │  - create_history()                                 │  │  │
│  │  │  - get_history()                                    │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  数据库层（MongoDB）                       │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  news_results（主数据集合）                         │  │  │
│  │  ├─────────────────────────────────────────────────────┤  │  │
│  │  │  batch_update_history（修改历史集合）               │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 批量修改流程

```
用户发起批量修改请求
         │
         ▼
┌────────────────────┐
│ 1. 参数验证        │
│ - 验证字段名       │
│ - 验证修改内容     │
│ - 验证目标范围     │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 2. 权限检查        │
│ - 验证用户身份     │
│ - 检查操作权限     │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 3. 创建修改记录    │
│ - 生成update_id    │
│ - 记录修改前数据   │
│ - 状态设为pending  │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐     Yes    ┌───────────────────┐
│ 4. 检查数据量      │ ────────▶  │ 异步任务处理      │
│ - 大于阈值?        │            │ - 后台执行        │
└────────┬───────────┘            │ - 定期更新状态    │
         │ No                      └───────────────────┘
         ▼
┌────────────────────┐
│ 5. 执行批量修改    │
│ - 逐条更新记录     │
│ - 记录成功/失败    │
│ - 更新updated_at   │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 6. 更新修改记录    │
│ - 记录修改后数据   │
│ - 状态设为completed│
│ - 统计修改数量     │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 7. 返回结果        │
│ - update_id        │
│ - 修改统计         │
│ - 操作状态         │
└────────────────────┘
```

---

## 数据模型设计

### BatchUpdateRequest（批量修改请求）

```python
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class BatchUpdateRequest(BaseModel):
    """批量修改请求"""

    # 修改目标
    target_type: Literal["task_id", "result_ids"] = Field(
        ...,
        description="目标类型：task_id（按任务）或 result_ids（按ID列表）"
    )
    task_id: Optional[str] = Field(
        None,
        description="任务ID（target_type=task_id时必填）"
    )
    result_ids: Optional[List[str]] = Field(
        None,
        description="结果ID列表（target_type=result_ids时必填）"
    )

    # 修改内容
    updates: Dict[str, Any] = Field(
        ...,
        description="要修改的字段和新值，支持：markdown_content, content"
    )

    # 可选参数
    reason: Optional[str] = Field(
        None,
        description="修改原因（用于历史记录）",
        max_length=500
    )
    operator: Optional[str] = Field(
        None,
        description="操作者标识（用户ID或名称）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_type": "task_id",
                "task_id": "240011812325298176",
                "updates": {
                    "markdown_content": "# 新的Markdown内容\n...",
                    "content": "新的文本内容"
                },
                "reason": "批量更正内容格式",
                "operator": "admin_user"
            }
        }
```

### BatchUpdateHistory（批量修改历史）

```python
from enum import Enum


class BatchUpdateStatus(Enum):
    """批量修改状态"""
    PENDING = "pending"           # 待执行
    PROCESSING = "processing"     # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    ROLLED_BACK = "rolled_back"   # 已回滚


class BatchUpdateHistory(BaseModel):
    """批量修改历史记录"""

    # 基本信息
    id: str = Field(default_factory=generate_string_id, alias="_id")
    status: BatchUpdateStatus = Field(BatchUpdateStatus.PENDING)

    # 目标信息
    target_type: str = Field(..., description="目标类型")
    task_id: Optional[str] = Field(None, description="任务ID")
    result_ids: Optional[List[str]] = Field(None, description="结果ID列表")

    # 修改内容
    field_updates: Dict[str, Any] = Field(..., description="修改的字段和新值")

    # 修改前快照
    before_snapshot: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="修改前的数据快照"
    )

    # 修改后快照
    after_snapshot: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="修改后的数据快照"
    )

    # 执行结果
    total_count: int = Field(0, description="总计划修改数量")
    success_count: int = Field(0, description="成功修改数量")
    failed_count: int = Field(0, description="失败数量")
    error_messages: List[str] = Field(default_factory=list, description="错误信息列表")

    # 操作者信息
    operator: Optional[str] = Field(None, description="操作者")
    reason: Optional[str] = Field(None, description="修改原因")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 回滚信息
    is_rolled_back: bool = Field(False, description="是否已回滚")
    rollback_at: Optional[datetime] = Field(None, description="回滚时间")
    rollback_operator: Optional[str] = Field(None, description="回滚操作者")
```

---

## API设计

### 1. 创建批量修改任务

**接口**: `POST /api/v1/batch-updates`

**请求体**:
```json
{
  "target_type": "task_id",
  "task_id": "240011812325298176",
  "updates": {
    "markdown_content": "# 更新后的Markdown内容\n\n...",
    "content": "更新后的文本内容"
  },
  "reason": "批量修正内容格式错误",
  "operator": "admin_user"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "批量修改任务创建成功",
  "data": {
    "update_id": "batch_update_123456789",
    "status": "processing",
    "target_type": "task_id",
    "task_id": "240011812325298176",
    "total_count": 150,
    "estimated_time_seconds": 15,
    "created_at": "2025-11-13T10:00:00Z"
  }
}
```

### 2. 查询批量修改状态

**接口**: `GET /api/v1/batch-updates/{update_id}`

**响应**:
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "update_id": "batch_update_123456789",
    "status": "completed",
    "target_type": "task_id",
    "task_id": "240011812325298176",
    "total_count": 150,
    "success_count": 148,
    "failed_count": 2,
    "error_messages": [
      "结果ID xxx 不存在",
      "结果ID yyy 更新失败"
    ],
    "created_at": "2025-11-13T10:00:00Z",
    "completed_at": "2025-11-13T10:00:15Z",
    "duration_seconds": 15,
    "operator": "admin_user",
    "reason": "批量修正内容格式错误"
  }
}
```

### 3. 查询修改历史

**接口**: `GET /api/v1/batch-updates`

**查询参数**:
- `task_id`: 按任务筛选
- `operator`: 按操作者筛选
- `status`: 按状态筛选
- `page`: 页码
- `page_size`: 每页数量

**响应**:
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "items": [
      {
        "update_id": "batch_update_123456789",
        "status": "completed",
        "target_type": "task_id",
        "task_id": "240011812325298176",
        "total_count": 150,
        "success_count": 148,
        "created_at": "2025-11-13T10:00:00Z",
        "operator": "admin_user"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 4. 查询详细修改记录

**接口**: `GET /api/v1/batch-updates/{update_id}/details`

**响应**:
```json
{
  "code": 200,
  "message": "查询成功",
  "data": {
    "update_id": "batch_update_123456789",
    "status": "completed",
    "field_updates": {
      "markdown_content": "# 新内容",
      "content": "新文本"
    },
    "before_snapshot": [
      {
        "result_id": "result_001",
        "markdown_content": "# 旧内容",
        "content": "旧文本"
      }
    ],
    "after_snapshot": [
      {
        "result_id": "result_001",
        "markdown_content": "# 新内容",
        "content": "新文本"
      }
    ]
  }
}
```

### 5. 回滚批量修改

**接口**: `POST /api/v1/batch-updates/{update_id}/rollback`

**请求体**:
```json
{
  "operator": "admin_user",
  "reason": "误操作，需要回滚"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "回滚成功",
  "data": {
    "update_id": "batch_update_123456789",
    "rollback_count": 148,
    "rollback_at": "2025-11-13T10:30:00Z"
  }
}
```

---

## 数据库设计

### batch_update_history 集合

**集合名**: `batch_update_history`

**文档结构**:
```javascript
{
  "_id": "batch_update_123456789",
  "status": "completed",

  // 目标信息
  "target_type": "task_id",
  "task_id": "240011812325298176",
  "result_ids": null,

  // 修改内容
  "field_updates": {
    "markdown_content": "# 新内容",
    "content": "新文本"
  },

  // 快照数据
  "before_snapshot": [
    {
      "result_id": "result_001",
      "markdown_content": "# 旧内容 1",
      "content": "旧文本 1"
    },
    {
      "result_id": "result_002",
      "markdown_content": "# 旧内容 2",
      "content": "旧文本 2"
    }
  ],

  "after_snapshot": [
    {
      "result_id": "result_001",
      "markdown_content": "# 新内容",
      "content": "新文本"
    },
    {
      "result_id": "result_002",
      "markdown_content": "# 新内容",
      "content": "新文本"
    }
  ],

  // 执行结果
  "total_count": 150,
  "success_count": 148,
  "failed_count": 2,
  "error_messages": [
    "结果ID xxx 不存在",
    "结果ID yyy 更新失败"
  ],

  // 操作者信息
  "operator": "admin_user",
  "reason": "批量修正内容格式错误",

  // 时间戳
  "created_at": ISODate("2025-11-13T10:00:00Z"),
  "started_at": ISODate("2025-11-13T10:00:01Z"),
  "completed_at": ISODate("2025-11-13T10:00:15Z"),

  // 回滚信息
  "is_rolled_back": false,
  "rollback_at": null,
  "rollback_operator": null
}
```

**索引设计**:
```javascript
// 按任务查询
db.batch_update_history.createIndex({ "task_id": 1, "created_at": -1 })

// 按操作者查询
db.batch_update_history.createIndex({ "operator": 1, "created_at": -1 })

// 按状态查询
db.batch_update_history.createIndex({ "status": 1, "created_at": -1 })

// 按创建时间查询
db.batch_update_history.createIndex({ "created_at": -1 })
```

---

## 仓储层设计

### ProcessedResultRepository 扩展

**新增方法**：

```python
async def batch_update_fields(
    self,
    filter_query: Dict[str, Any],
    field_updates: Dict[str, Any]
) -> tuple[int, List[str]]:
    """
    批量更新字段

    Args:
        filter_query: MongoDB查询条件
        field_updates: 要更新的字段字典

    Returns:
        (成功数量, 错误消息列表)
    """
    try:
        collection = await self._get_collection()

        # 构建更新语句
        update_data = {
            "updated_at": datetime.utcnow()
        }
        update_data.update(field_updates)

        # 执行批量更新
        result = await collection.update_many(
            filter_query,
            {"$set": update_data}
        )

        success_count = result.modified_count
        logger.info(f"✅ 批量更新成功: {success_count}条记录")

        return success_count, []

    except Exception as e:
        error_msg = f"批量更新失败: {e}"
        logger.error(f"❌ {error_msg}")
        return 0, [error_msg]


async def get_fields_snapshot(
    self,
    filter_query: Dict[str, Any],
    fields: List[str]
) -> List[Dict[str, Any]]:
    """
    获取指定字段的快照数据

    Args:
        filter_query: MongoDB查询条件
        fields: 要获取的字段列表

    Returns:
        字段快照列表
    """
    try:
        collection = await self._get_collection()

        # 构建投影
        projection = {"_id": 1}
        for field in fields:
            projection[field] = 1

        # 查询数据
        cursor = collection.find(filter_query, projection)

        snapshot = []
        async for doc in cursor:
            snapshot.append({
                "result_id": str(doc["_id"]),
                **{field: doc.get(field) for field in fields}
            })

        return snapshot

    except Exception as e:
        logger.error(f"❌ 获取字段快照失败: {e}")
        return []
```

### BatchUpdateHistoryRepository（新建）

```python
class BatchUpdateHistoryRepository:
    """批量修改历史仓储"""

    def __init__(self):
        self.collection_name = "batch_update_history"

    async def _get_collection(self):
        """获取集合"""
        db = await get_mongodb_database()
        return db[self.collection_name]

    async def create(
        self,
        history: BatchUpdateHistory
    ) -> str:
        """创建批量修改历史记录"""
        try:
            collection = await self._get_collection()

            history_dict = {
                "_id": history.id,
                "status": history.status.value,
                "target_type": history.target_type,
                "task_id": history.task_id,
                "result_ids": history.result_ids,
                "field_updates": history.field_updates,
                "before_snapshot": history.before_snapshot,
                "after_snapshot": history.after_snapshot,
                "total_count": history.total_count,
                "success_count": history.success_count,
                "failed_count": history.failed_count,
                "error_messages": history.error_messages,
                "operator": history.operator,
                "reason": history.reason,
                "created_at": history.created_at,
                "started_at": history.started_at,
                "completed_at": history.completed_at,
                "is_rolled_back": history.is_rolled_back,
                "rollback_at": history.rollback_at,
                "rollback_operator": history.rollback_operator
            }

            await collection.insert_one(history_dict)
            logger.info(f"✅ 创建批量修改历史: {history.id}")

            return history.id

        except Exception as e:
            logger.error(f"❌ 创建批量修改历史失败: {e}")
            raise

    async def update_status(
        self,
        update_id: str,
        status: BatchUpdateStatus,
        **kwargs
    ) -> bool:
        """更新批量修改状态"""
        try:
            collection = await self._get_collection()

            update_data = {
                "status": status.value
            }
            update_data.update(kwargs)

            result = await collection.update_one(
                {"_id": update_id},
                {"$set": update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ 更新批量修改状态失败: {e}")
            raise

    async def get_by_id(
        self,
        update_id: str
    ) -> Optional[BatchUpdateHistory]:
        """根据ID获取批量修改历史"""
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"_id": update_id})

            if data:
                return self._dict_to_history(data)
            return None

        except Exception as e:
            logger.error(f"❌ 获取批量修改历史失败: {e}")
            raise

    async def get_list(
        self,
        task_id: Optional[str] = None,
        operator: Optional[str] = None,
        status: Optional[BatchUpdateStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[BatchUpdateHistory], int]:
        """获取批量修改历史列表"""
        try:
            collection = await self._get_collection()

            # 构建查询条件
            query = {}
            if task_id:
                query["task_id"] = task_id
            if operator:
                query["operator"] = operator
            if status:
                query["status"] = status.value

            # 总数
            total = await collection.count_documents(query)

            # 分页查询
            skip = (page - 1) * page_size
            cursor = collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)

            histories = []
            async for data in cursor:
                histories.append(self._dict_to_history(data))

            return histories, total

        except Exception as e:
            logger.error(f"❌ 获取批量修改历史列表失败: {e}")
            raise

    def _dict_to_history(
        self,
        data: Dict[str, Any]
    ) -> BatchUpdateHistory:
        """将字典转换为BatchUpdateHistory实体"""
        status_value = data.get("status", "pending")
        try:
            status = BatchUpdateStatus(status_value)
        except ValueError:
            status = BatchUpdateStatus.PENDING

        return BatchUpdateHistory(
            id=str(data["_id"]),
            status=status,
            target_type=data.get("target_type", ""),
            task_id=data.get("task_id"),
            result_ids=data.get("result_ids"),
            field_updates=data.get("field_updates", {}),
            before_snapshot=data.get("before_snapshot", []),
            after_snapshot=data.get("after_snapshot", []),
            total_count=data.get("total_count", 0),
            success_count=data.get("success_count", 0),
            failed_count=data.get("failed_count", 0),
            error_messages=data.get("error_messages", []),
            operator=data.get("operator"),
            reason=data.get("reason"),
            created_at=data.get("created_at", datetime.utcnow()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            is_rolled_back=data.get("is_rolled_back", False),
            rollback_at=data.get("rollback_at"),
            rollback_operator=data.get("rollback_operator")
        )
```

---

## 安全性设计

### 1. 身份验证和授权

```python
from fastapi import Depends, HTTPException, Header
from typing import Optional


async def verify_admin_user(
    authorization: Optional[str] = Header(None)
) -> str:
    """验证管理员权限"""
    if not authorization:
        raise HTTPException(401, "未提供身份验证信息")

    # 验证token（实际实现需要根据项目的认证系统）
    # token = authorization.replace("Bearer ", "")
    # user = await verify_token(token)

    # 简化示例
    if authorization != "Bearer admin_token":
        raise HTTPException(403, "无权限执行批量修改操作")

    return "admin_user"
```

### 2. 字段白名单验证

```python
ALLOWED_UPDATE_FIELDS = {
    "markdown_content",
    "content"
}


def validate_update_fields(updates: Dict[str, Any]) -> None:
    """验证更新字段是否在白名单中"""
    for field in updates.keys():
        if field not in ALLOWED_UPDATE_FIELDS:
            raise HTTPException(
                400,
                f"不允许修改字段: {field}. 允许的字段: {ALLOWED_UPDATE_FIELDS}"
            )
```

### 3. 数据量限制

```python
MAX_BATCH_SIZE = 1000  # 单次最大修改数量
MAX_ASYNC_BATCH_SIZE = 5000  # 异步任务最大修改数量


def validate_batch_size(target_count: int, is_async: bool = False) -> None:
    """验证批量修改数量"""
    max_size = MAX_ASYNC_BATCH_SIZE if is_async else MAX_BATCH_SIZE

    if target_count > max_size:
        raise HTTPException(
            400,
            f"批量修改数量超过限制: {target_count} > {max_size}"
        )
```

---

## 实现方案

### Phase 1: 基础数据模型和仓储（1-2天）

**任务清单**:
- [ ] 创建 `BatchUpdateHistory` 实体模型
- [ ] 创建 `BatchUpdateHistoryRepository` 仓储类
- [ ] 扩展 `ProcessedResultRepository` 添加批量更新方法
- [ ] 编写仓储层单元测试

### Phase 2: 核心服务层（2-3天）

**任务清单**:
- [ ] 创建 `BatchUpdateService` 服务类
- [ ] 实现批量修改核心逻辑
- [ ] 实现修改历史记录功能
- [ ] 实现回滚功能
- [ ] 编写服务层单元测试

**核心服务代码框架**:

```python
class BatchUpdateService:
    """批量修改服务"""

    def __init__(self):
        self.processed_repo = ProcessedResultRepository()
        self.history_repo = BatchUpdateHistoryRepository()

    async def create_batch_update(
        self,
        request: BatchUpdateRequest,
        operator: str
    ) -> BatchUpdateHistory:
        """创建批量修改任务"""

        # 1. 验证更新字段
        validate_update_fields(request.updates)

        # 2. 构建查询条件
        filter_query = self._build_filter_query(request)

        # 3. 获取修改前快照
        fields_to_update = list(request.updates.keys())
        before_snapshot = await self.processed_repo.get_fields_snapshot(
            filter_query,
            fields_to_update
        )

        total_count = len(before_snapshot)

        # 4. 验证批量大小
        validate_batch_size(total_count)

        # 5. 创建历史记录
        history = BatchUpdateHistory(
            target_type=request.target_type,
            task_id=request.task_id,
            result_ids=request.result_ids,
            field_updates=request.updates,
            before_snapshot=before_snapshot,
            total_count=total_count,
            operator=operator or request.operator,
            reason=request.reason
        )

        await self.history_repo.create(history)

        # 6. 执行批量更新
        await self._execute_batch_update(history.id, filter_query, request.updates)

        return history

    async def _execute_batch_update(
        self,
        update_id: str,
        filter_query: Dict[str, Any],
        field_updates: Dict[str, Any]
    ) -> None:
        """执行批量更新"""

        # 更新状态为处理中
        await self.history_repo.update_status(
            update_id,
            BatchUpdateStatus.PROCESSING,
            started_at=datetime.utcnow()
        )

        try:
            # 执行批量更新
            success_count, error_messages = await self.processed_repo.batch_update_fields(
                filter_query,
                field_updates
            )

            # 获取修改后快照
            fields = list(field_updates.keys())
            after_snapshot = await self.processed_repo.get_fields_snapshot(
                filter_query,
                fields
            )

            # 更新历史记录
            await self.history_repo.update_status(
                update_id,
                BatchUpdateStatus.COMPLETED,
                success_count=success_count,
                failed_count=len(error_messages),
                error_messages=error_messages,
                after_snapshot=after_snapshot,
                completed_at=datetime.utcnow()
            )

        except Exception as e:
            # 更新为失败状态
            await self.history_repo.update_status(
                update_id,
                BatchUpdateStatus.FAILED,
                error_messages=[str(e)],
                completed_at=datetime.utcnow()
            )
            raise

    async def rollback_batch_update(
        self,
        update_id: str,
        operator: str
    ) -> int:
        """回滚批量修改"""

        # 1. 获取历史记录
        history = await self.history_repo.get_by_id(update_id)
        if not history:
            raise HTTPException(404, f"批量修改记录不存在: {update_id}")

        if history.is_rolled_back:
            raise HTTPException(400, "该批量修改已回滚")

        # 2. 构建回滚更新
        rollback_updates = {}
        for item in history.before_snapshot:
            result_id = item["result_id"]
            # 逐条回滚
            for field, old_value in item.items():
                if field != "result_id":
                    rollback_updates[field] = old_value

        # 3. 构建过滤条件
        filter_query = self._build_filter_query_from_history(history)

        # 4. 执行回滚
        success_count, _ = await self.processed_repo.batch_update_fields(
            filter_query,
            rollback_updates
        )

        # 5. 更新历史记录
        await self.history_repo.update_status(
            update_id,
            BatchUpdateStatus.ROLLED_BACK,
            is_rolled_back=True,
            rollback_at=datetime.utcnow(),
            rollback_operator=operator
        )

        return success_count

    def _build_filter_query(
        self,
        request: BatchUpdateRequest
    ) -> Dict[str, Any]:
        """构建MongoDB查询条件"""
        if request.target_type == "task_id":
            return {"task_id": request.task_id}
        elif request.target_type == "result_ids":
            return {"_id": {"$in": request.result_ids}}
        else:
            raise HTTPException(400, f"不支持的目标类型: {request.target_type}")
```

### Phase 3: API端点实现（1-2天）

**任务清单**:
- [ ] 创建批量修改API端点
- [ ] 实现查询和回滚端点
- [ ] 添加API文档和示例
- [ ] 集成身份验证

### Phase 4: 测试和优化（2-3天）

**任务清单**:
- [ ] 编写集成测试
- [ ] 性能测试和优化
- [ ] 异步任务支持（可选）
- [ ] 文档完善

---

## 测试方案

### 1. 单元测试

```python
import pytest
from src.services.batch_update_service import BatchUpdateService


@pytest.mark.asyncio
class TestBatchUpdateService:
    async def test_batch_update_by_task_id(self):
        """测试按任务ID批量修改"""
        service = BatchUpdateService()

        request = BatchUpdateRequest(
            target_type="task_id",
            task_id="test_task_123",
            updates={
                "markdown_content": "# 测试内容",
                "content": "测试文本"
            },
            operator="test_user"
        )

        history = await service.create_batch_update(request, "test_user")

        assert history.status == BatchUpdateStatus.COMPLETED
        assert history.success_count > 0

    async def test_batch_update_by_result_ids(self):
        """测试按ID列表批量修改"""
        service = BatchUpdateService()

        request = BatchUpdateRequest(
            target_type="result_ids",
            result_ids=["result_001", "result_002"],
            updates={
                "content": "批量修改的内容"
            },
            operator="test_user"
        )

        history = await service.create_batch_update(request, "test_user")

        assert history.total_count == 2

    async def test_rollback_batch_update(self):
        """测试回滚批量修改"""
        service = BatchUpdateService()

        # 先执行批量修改
        request = BatchUpdateRequest(
            target_type="result_ids",
            result_ids=["result_001"],
            updates={"content": "新内容"},
            operator="test_user"
        )
        history = await service.create_batch_update(request, "test_user")

        # 执行回滚
        rollback_count = await service.rollback_batch_update(
            history.id,
            "test_user"
        )

        assert rollback_count > 0
```

### 2. 集成测试

```python
@pytest.mark.asyncio
class TestBatchUpdateAPI:
    async def test_create_batch_update_api(self):
        """测试批量修改API"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/batch-updates",
                json={
                    "target_type": "task_id",
                    "task_id": "test_task",
                    "updates": {
                        "markdown_content": "# 新内容"
                    }
                },
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "update_id" in data["data"]
```

### 3. 性能测试

```python
import time


@pytest.mark.asyncio
async def test_batch_update_performance():
    """测试批量修改性能"""
    service = BatchUpdateService()

    # 准备100条测试数据
    result_ids = [f"result_{i:03d}" for i in range(100)]

    request = BatchUpdateRequest(
        target_type="result_ids",
        result_ids=result_ids,
        updates={"content": "性能测试内容"},
        operator="test_user"
    )

    start_time = time.time()
    history = await service.create_batch_update(request, "test_user")
    elapsed = time.time() - start_time

    # 验证性能要求：100条记录 < 5秒
    assert elapsed < 5.0
    assert history.success_count == 100
```

---

## 风险评估

### 1. 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 批量修改性能问题 | 高 | 中 | 实现异步任务、分批处理 |
| 数据快照占用空间大 | 中 | 高 | 设置快照保留期限、压缩存储 |
| 并发修改冲突 | 高 | 低 | 使用MongoDB事务、乐观锁 |

### 2. 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 误操作批量修改 | 高 | 中 | 实现回滚功能、二次确认 |
| 权限控制不足 | 高 | 低 | 严格的身份验证和授权 |
| 修改历史丢失 | 中 | 低 | 持久化存储、定期备份 |

### 3. 安全风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 恶意批量修改 | 高 | 身份验证、操作审计、限流 |
| 敏感数据泄露 | 高 | 权限控制、字段白名单 |
| SQL注入（NoSQL） | 中 | 参数化查询、输入验证 |

---

## 附录

### A. 配置参数

```python
# 批量修改配置
BATCH_UPDATE_CONFIG = {
    "max_batch_size": 1000,           # 同步最大批量
    "max_async_batch_size": 5000,     # 异步最大批量
    "snapshot_retention_days": 30,    # 快照保留天数
    "allowed_fields": [                # 允许修改的字段
        "markdown_content",
        "content"
    ]
}
```

### B. 错误码

| 错误码 | 描述 | HTTP状态码 |
|--------|------|-----------|
| BATCH_001 | 无效的目标类型 | 400 |
| BATCH_002 | 不允许修改的字段 | 400 |
| BATCH_003 | 批量数量超过限制 | 400 |
| BATCH_004 | 批量修改记录不存在 | 404 |
| BATCH_005 | 批量修改已回滚 | 400 |
| BATCH_006 | 无权限执行批量修改 | 403 |

### C. 性能指标

| 指标 | 目标值 | 备注 |
|------|--------|------|
| 100条记录修改时间 | < 5秒 | 同步执行 |
| 1000条记录修改时间 | < 30秒 | 同步执行 |
| 5000条记录修改时间 | < 2分钟 | 异步执行 |
| API响应时间（P95） | < 500ms | 创建任务 |
| 快照存储开销 | < 10MB/1000条 | 压缩后 |

---

**文档状态**: ✅ 设计完成
**下一步**: 等待技术评审和实施确认
