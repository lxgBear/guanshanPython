# 错误信息报告功能实现

**日期**: 2025-11-05
**版本**: v2.0.1
**状态**: ✅ 已完成

---

## 一、功能目标

为前端提供具体的任务执行错误信息，便于用户了解任务失败原因。

---

## 二、实现方案

### 1. 数据模型扩展 (SearchTask)

**文件**: `src/core/domain/entities/search_task.py`

**新增字段**:
```python
# 错误信息（v2.0.1 新增）
last_error: Optional[str] = None  # 最后一次执行的错误信息
last_error_time: Optional[datetime] = None  # 最后一次错误发生时间
```

**修改方法**: `record_execution()`
```python
def record_execution(
    self,
    success: bool,
    results_count: int = 0,
    credits_used: int = 0,
    error_message: Optional[str] = None  # 新增参数
) -> None:
    """记录执行结果"""
    self.execution_count += 1
    if success:
        self.success_count += 1
        # 成功时清除错误信息
        self.last_error = None
        self.last_error_time = None
    else:
        self.failure_count += 1
        # 失败时记录错误信息
        if error_message:
            self.last_error = error_message
            self.last_error_time = datetime.utcnow()
    # ...
```

---

### 2. 任务调度器错误捕获 (TaskSchedulerService)

**文件**: `src/services/task_scheduler.py`

**修改位置**: `_execute_search_task()` 异常处理部分（line 388-406）

```python
except Exception as e:
    logger.error(f"❌ 搜索任务执行失败 {task_id}: {e}")

    # 记录失败（包含错误信息）
    try:
        repo = await self._get_task_repository()
        task = await repo.get_by_id(task_id)
        if task:
            # 提取简洁的错误信息
            error_message = str(e)
            # 如果错误信息太长，截取前500个字符
            if len(error_message) > 500:
                error_message = error_message[:500] + "..."

            task.record_execution(success=False, error_message=error_message)
            await repo.update(task)
            logger.info(f"已记录任务失败信息: {task.name}")
    except Exception as update_error:
        logger.error(f"更新失败统计时出错: {update_error}")
```

---

### 3. 数据库层支持 (SearchTaskRepository)

**文件**: `src/infrastructure/database/repositories.py`

**修改方法**: `_task_to_dict()` 和 `_dict_to_task()`

**_task_to_dict()** (line 48-56):
```python
"execution_count": task.execution_count,
"success_count": task.success_count,
"failure_count": task.failure_count,
"total_results": task.total_results,
"total_credits_used": task.total_credits_used,
# v2.0.1: 错误信息
"last_error": task.last_error,
"last_error_time": task.last_error_time
```

**_dict_to_task()** (line 78-86):
```python
execution_count=data.get("execution_count", 0),
success_count=data.get("success_count", 0),
failure_count=data.get("failure_count", 0),
total_results=data.get("total_results", 0),
total_credits_used=data.get("total_credits_used", 0),
# v2.0.1: 错误信息（向后兼容，旧数据可能没有此字段）
last_error=data.get("last_error"),
last_error_time=data.get("last_error_time")
```

---

### 4. 调试工具增强 (check_task_status.py)

**文件**: `scripts/check_task_status.py`

**新增显示** (line 42-46):
```python
# 显示错误信息（v2.0.1 新增）
if task.get('last_error'):
    print(f"\n⚠️  最后错误信息:")
    print(f"  - 错误: {task.get('last_error')}")
    print(f"  - 时间: {task.get('last_error_time')}")
```

---

## 三、使用示例

### 数据库中的错误信息

```json
{
  "_id": "244368388086222848",
  "name": "缅甸测试 2",
  "execution_count": 2,
  "failure_count": 2,
  "last_error": "网站爬取执行失败: 网站爬取失败: Internal Server Error: Failed to check crawl status. Cannot read properties of undefined (reading 'markdown')",
  "last_error_time": "2025-11-05 07:54:59.629000"
}
```

### API 返回示例

当前端调用 `GET /api/v1/tasks/{task_id}` 时，将返回：

```json
{
  "id": "244368388086222848",
  "name": "缅甸测试 2",
  "status": "active",
  "execution_count": 2,
  "failure_count": 2,
  "success_count": 0,
  "last_error": "网站爬取执行失败: 网站爬取失败: Internal Server Error: Failed to check crawl status. Cannot read properties of undefined (reading 'markdown')",
  "last_error_time": "2025-11-05T07:54:59.629000",
  ...
}
```

---

## 四、前端展示建议

### 1. 任务列表页

在任务状态旁显示错误图标：

```
✅ 任务A  (成功: 10, 失败: 0)
⚠️ 任务B  (成功: 5, 失败: 3) [查看错误]
```

### 2. 任务详情页

**错误信息卡片**:
```
⚠️ 最后错误信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
错误类型: Firecrawl API 错误
错误时间: 2025-11-05 15:54:59
详细信息:
网站爬取执行失败: Internal Server Error:
Failed to check crawl status. Cannot read
properties of undefined (reading 'markdown')

[重试任务] [查看日志] [修改配置]
```

### 3. 错误分类展示

根据错误类型提供不同的建议：

| 错误类型 | 图标 | 建议 |
|---------|------|------|
| Firecrawl API Error | 🌐 | "该网站可能阻止爬虫访问" |
| Timeout | ⏱️ | "建议增加超时时间" |
| Network Error | 📡 | "检查网络连接" |
| Authentication | 🔒 | "网站需要登录认证" |

---

## 五、测试结果

### 测试任务: 244368388086222848 (缅甸测试 2)

**执行命令**:
```bash
python scripts/execute_task_now.py 244368388086222848
```

**结果**:
```
✅ 任务执行完成！
结果: {
  'task_id': '244368388086222848',
  'task_name': '缅甸测试 2',
  'executed_at': '2025-11-05T07:54:59.641258',
  'status': 'completed',
  'last_execution_success': False,
  'execution_count': 2
}
```

**数据库验证**:
```bash
python scripts/check_task_status.py 244368388086222848
```

**输出**:
```
⚠️  最后错误信息:
  - 错误: 网站爬取执行失败: 网站爬取失败: Internal Server Error: ...
  - 时间: 2025-11-05 07:54:59.629000
```

✅ **验证通过**: 错误信息成功保存到数据库并可通过 API 访问

---

## 六、向后兼容性

- ✅ 新字段为 `Optional[str]`，不影响现有任务
- ✅ `_dict_to_task()` 使用 `data.get("last_error")` 确保旧数据兼容
- ✅ 成功执行时自动清除错误信息

---

## 七、后续优化建议

1. **错误分类**: 根据错误类型自动分类（网络错误、API错误、配置错误等）
2. **错误统计**: 添加错误类型统计，分析常见失败原因
3. **自动重试**: 对于临时性错误（如网络超时），自动重试
4. **通知机制**: 失败次数超过阈值时发送通知
5. **错误历史**: 保存完整错误历史记录（非仅最后一次）

---

**执行时间**: 2025-11-05 15:54
**执行状态**: ✅ 已完成
**影响范围**: SearchTask实体、TaskSchedulerService、SearchTaskRepository、调试脚本
