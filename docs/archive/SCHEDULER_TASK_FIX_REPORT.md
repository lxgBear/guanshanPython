# 定时任务未启动问题分析与修复报告

**任务ID**: 237408060762787840
**报告时间**: 2025-10-17
**问题**: 定时任务未启动

---

## 📊 问题分析

### 1. 数据库中的任务状态

```
✅ 任务存在于数据库
  ID: 237408060762787840
  Name: 测试任务 10 月 17 日
  Status: active
  Schedule Interval: HOURLY_1
  Created At: 2025-10-17 02:54:52

❌ 关键字段缺失
  is_active: N/A (应该是 True)
  next_run_time: None (应该有计划执行时间)
```

### 2. 调度器状态

```
✅ 调度器正在运行
  Status: running
  Active Jobs: 2

❌ 该任务不在调度器中
  当前已调度任务:
    - 236409735543001088 (测试)
    - 236061650310316032 (test)

  缺失任务:
    - 237408060762787840 ❌
```

### 3. 根本原因分析

#### 问题定位

**SearchTask 实体定义** (`src/core/domain/entities/search_task.py:79`):
```python
is_active: bool = True  # 是否启用
```

**调度器加载逻辑** (`src/services/task_scheduler.py:182-186`):
```python
# 获取所有活跃任务
tasks, _ = await repo.list_tasks(
    page=1,
    page_size=1000,
    is_active=True  # ← 只加载 is_active=True 的任务
)
```

**任务调度条件** (`src/services/task_scheduler.py:240`):
```python
if task.is_active:  # ← 只有 is_active=True 才会被调度
    await self._schedule_task(task)
```

#### 根本原因

**数据不一致问题**:

1. ✅ SearchTask 实体有 `is_active` 字段，默认值为 `True`
2. ❌ 数据库中的任务文档缺少 `is_active` 字段
3. ❌ 调度器启动时，`list_tasks(is_active=True)` 查询不到该任务
4. ❌ 任务从未被加载到调度器中

**可能原因**:
- 任务由旧版本代码创建（当时没有 `is_active` 字段）
- 数据库迁移未执行
- 手动修改数据库导致字段丢失
- Repository 保存逻辑未正确处理 `is_active` 字段

---

## 🔧 修复方案

### 方案 1: 数据库直接修复（推荐）

**优点**:
- 快速生效
- 不影响其他任务
- 修复后自动被调度器加载

**步骤**:
1. 在数据库中为任务添加 `is_active: true` 字段
2. 重启调度器或手动注册任务
3. 验证任务已被调度

### 方案 2: API 修复

**优点**:
- 通过标准 API 操作
- 记录完整的审计日志

**步骤**:
1. 调用 API 更新任务
2. 确保 `is_active` 字段正确设置
3. 调度器自动加载更新后的任务

### 方案 3: 批量修复工具

**优点**:
- 可修复所有类似问题
- 自动化处理

**步骤**:
1. 扫描所有缺少 `is_active` 字段的任务
2. 批量添加 `is_active: true`
3. 重新加载调度器

---

## 📝 修复脚本

### 修复单个任务

```python
#!/usr/bin/env python3
"""修复单个任务的 is_active 字段"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def fix_task(task_id: str):
    client = AsyncIOMotorClient(
        'mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin'
    )
    db = client['intelligent_system']

    # 更新任务，添加 is_active 字段
    result = await db.search_tasks.update_one(
        {'_id': task_id},
        {
            '$set': {
                'is_active': True,
                'updated_at': datetime.utcnow()
            }
        }
    )

    if result.modified_count > 0:
        print(f'✅ 任务已修复: {task_id}')
        print(f'   已添加 is_active: true')
    else:
        print(f'❌ 修复失败: {task_id}')

    client.close()

# 使用
asyncio.run(fix_task('237408060762787840'))
```

### 批量修复所有任务

```python
#!/usr/bin/env python3
"""批量修复所有缺少 is_active 字段的任务"""

import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

async def fix_all_tasks():
    client = AsyncIOMotorClient(
        'mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin'
    )
    db = client['intelligent_system']

    # 查找所有缺少 is_active 字段的任务
    tasks = await db.search_tasks.find({'is_active': {'$exists': False}}).to_list(1000)

    print(f'📊 发现 {len(tasks)} 个缺少 is_active 字段的任务')

    fixed_count = 0
    for task in tasks:
        result = await db.search_tasks.update_one(
            {'_id': task['_id']},
            {
                '$set': {
                    'is_active': True,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        if result.modified_count > 0:
            print(f'✅ 修复: {task["_id"]} - {task.get("name", "未命名")}')
            fixed_count += 1

    print(f'\n📈 修复统计:')
    print(f'   总任务: {len(tasks)}')
    print(f'   已修复: {fixed_count}')

    client.close()

asyncio.run(fix_all_tasks())
```

---

## ✅ 修复后验证

### 1. 验证数据库字段

```python
async def verify_task(task_id: str):
    # 检查 is_active 字段是否存在
    task = await db.search_tasks.find_one({'_id': task_id})
    assert 'is_active' in task
    assert task['is_active'] == True
    print('✅ 数据库字段验证通过')
```

### 2. 验证调度器注册

```bash
# 检查调度器状态
curl -s "http://localhost:8000/api/v1/scheduler/status" | python -m json.tool

# 应该看到任务 237408060762787840 在 jobs 列表中
```

### 3. 验证下次执行时间

```bash
# 获取任务的下次执行时间
curl -s "http://localhost:8000/api/v1/scheduler/tasks/237408060762787840/next-run" | python -m json.tool

# 应该返回有效的 next_run_time
```

---

## 🚀 执行修复

### 推荐操作流程

1. **备份数据库** (可选但推荐)
   ```bash
   mongodump --uri="mongodb://admin:password123@localhost:27017/intelligent_system?authSource=admin" \
             --out="/backup/scheduler_fix_$(date +%Y%m%d_%H%M%S)"
   ```

2. **执行修复脚本**
   ```bash
   python scripts/fix_scheduler_task_237408060762787840.py
   ```

3. **重启调度器**（如果自动加载失败）
   ```bash
   # 调用 API 重启调度器
   curl -X POST "http://localhost:8000/api/v1/scheduler/reload"

   # 或重启整个应用
   ```

4. **验证修复成功**
   ```bash
   # 检查任务状态
   curl -s "http://localhost:8000/api/v1/scheduler/tasks/237408060762787840/next-run"
   ```

---

## 🔍 预防措施

### 1. 数据库迁移

创建迁移脚本确保所有任务都有必需字段:

```python
# migrations/add_is_active_field.py
async def migrate():
    """为所有任务添加 is_active 字段"""
    result = await db.search_tasks.update_many(
        {'is_active': {'$exists': False}},
        {'$set': {'is_active': True}}
    )
    print(f'迁移完成: 更新了 {result.modified_count} 个任务')
```

### 2. Repository 验证

在 `SearchTaskRepository.save()` 中添加字段验证:

```python
def _to_document(self, task: SearchTask) -> dict:
    doc = {
        "_id": str(task.id),
        "name": task.name,
        "is_active": task.is_active,  # ← 确保总是保存
        # ... 其他字段
    }
    # 验证必需字段
    assert 'is_active' in doc, "is_active field is required"
    return doc
```

### 3. 启动时检查

在调度器启动时检查并修复缺失字段:

```python
async def start(self):
    # ... 现有启动逻辑

    # 检查并修复缺失字段
    await self._ensure_task_integrity()

    # 加载任务
    await self._load_active_tasks()

async def _ensure_task_integrity(self):
    """确保所有任务有必需字段"""
    repo = await self._get_task_repository()
    # 修复缺失 is_active 字段的任务
    # ...
```

---

## 📌 总结

### 问题本质
- 数据库任务缺少 `is_active` 字段
- 调度器仅加载 `is_active=True` 的任务
- 导致任务存在但未被调度

### 解决方案
1. ✅ 为任务添加 `is_active: true` 字段
2. ✅ 重新加载调度器
3. ✅ 验证任务已被正确调度

### 长期改进
1. 实施数据库迁移脚本
2. 添加字段完整性验证
3. 启动时自动检查和修复

---

**修复状态**: 🔄 待执行
**负责人**: DevOps Team
**优先级**: 🔴 高
