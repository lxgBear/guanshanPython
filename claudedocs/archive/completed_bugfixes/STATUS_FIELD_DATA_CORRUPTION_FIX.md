# 数据库字段类型错误修复报告

**日期**: 2025-11-06  
**问题**: API 500 错误 - "'float' object has no attribute 'get'"  
**影响**: `/api/v1/search-tasks/{task_id}/results` 端点无法正常返回数据

---

## 🔍 问题定位

### 用户报告
用户访问 API 端点时收到 500 错误:
```
GET /api/v1/search-tasks/244746288889929728/results?page=2&page_size=10

{
    "error": "服务器内部错误",
    "message": "'float' object has no attribute 'get'"
}
```

### 调查过程

#### 初步分析 (误导性)
- 最初怀疑是 `processed_results` 数据有问题
- 检查了 API 端点代码 (`search_results_frontend.py`)
- 检查了数据映射代码 (`processed_result_repositories.py`)
- Python 模拟测试显示数据类型正常

#### 关键发现
通过检查 API 日志 (`/private/tmp/guanshan_api.log`)，发现实际错误来源：

```python
File "src/core/domain/entities/search_task.py", line 202
    include_domains = self.search_config.get('include_domains', [])
                      ^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'float' object has no attribute 'get'
```

**错误不在处理结果，而在加载任务实体时！**

#### 数据库检查
```python
task = await db.search_tasks.find_one({'_id': '244746288889929728'})
print(f'search_config type: {type(task.get("search_config"))}')
# 输出: search_config type: <class 'float'>
print(f'search_config value: {task.get("search_config")}')
# 输出: search_config value: 0.0
```

**根本原因**: 数据库中 `search_config` 被错误地存储为 `0.0` (float) 而非 `{}` (dict)

---

## 🔧 修复方案

### 代码层面修复 (防御性编程)

#### 修复 1: SearchTask 实体
**文件**: `src/core/domain/entities/search_task.py:202`

```python
# 修复前:
def extract_target_website(self) -> Optional[str]:
    include_domains = self.search_config.get('include_domains', [])
    if include_domains and len(include_domains) > 0:
        return include_domains[0]
    return None

# 修复后:
def extract_target_website(self) -> Optional[str]:
    # 防御性编程：确保 search_config 是字典类型
    if not isinstance(self.search_config, dict):
        return None
    
    include_domains = self.search_config.get('include_domains', [])
    if include_domains and len(include_domains) > 0:
        return include_domains[0]
    return None
```

#### 修复 2: SearchTask 仓储
**文件**: `src/infrastructure/database/repositories.py:58`

```python
# 修复前:
def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
    task = SearchTask(
        ...
        search_config=data.get("search_config", {}),
        crawl_config=data.get("crawl_config", {}),
        ...
    )

# 修复后:
def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
    # 防御性编程：确保 search_config 和 crawl_config 是字典类型
    search_config_raw = data.get("search_config", {})
    search_config = search_config_raw if isinstance(search_config_raw, dict) else {}
    
    crawl_config_raw = data.get("crawl_config", {})
    crawl_config = crawl_config_raw if isinstance(crawl_config_raw, dict) else {}
    
    task = SearchTask(
        ...
        search_config=search_config,
        crawl_config=crawl_config,
        ...
    )
```

### 数据库修复

**创建修复脚本**: `scripts/fix_corrupted_status.py`

功能:
- 扫描所有任务的 `search_config` 和 `crawl_config` 字段
- 识别非 dict 类型的字段
- 将错误类型重置为空字典 `{}`

**执行结果**:
```bash
python scripts/fix_corrupted_status.py

📊 开始扫描数据库中的配置字段类型错误
  总任务数: 2
  有问题的任务: 1
  正常任务: 1

⚠️ 发现以下问题任务:
[1] 任务: 天之声 (ID: 244746288889929728)
    ❌ search_config 类型错误: float = 0.0

🔧 开始修复...
修复 天之声 (ID: 244746288889929728): search_config -> {}
  ✅ 修复成功

📈 修复完成统计:
  发现问题: 1 个任务
  修复成功: 1 个任务
```

---

## ✅ 验证结果

### API 重启
```bash
kill 1408 && nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > /private/tmp/guanshan_api.log 2>&1 &
# 新进程 PID: 90106
```

### API 测试
```bash
curl "http://localhost:8000/api/v1/search-tasks/244746288889929728/results?page=2&page_size=10"

# ✅ 成功返回 JSON 数据，包含 10 条结果
{
    "items": [...],
    "total": 100,
    "page": 2,
    "page_size": 10,
    "total_pages": 10,
    "task_id": "244746288889929728",
    "task_name": "天之声"
}
```

---

## 📊 问题总结

### 根本原因
数据库中任务的 `search_config` 字段被错误地存储为 `0.0` (float) 而非 `{}` (dict)，导致:
1. 加载任务实体时，`SearchTask.search_config` 被赋值为 float
2. 调用 `extract_target_website()` 时尝试调用 `float.get()` 方法
3. 触发 `AttributeError: 'float' object has no attribute 'get'`
4. FastAPI 返回 500 Internal Server Error

### 错误传播路径
```
GET /results?page=2
  ↓
validate_task_exists(task_id)  ← 加载任务实体
  ↓
SearchTask.__post_init__()
  ↓
sync_target_website()
  ↓
extract_target_website()
  ↓
self.search_config.get()  ← 💥 AttributeError
```

### 为什么初始调查被误导
1. **错误消息不准确**: 用户提供的错误只显示 "'float' object has no attribute 'get'"，没有完整堆栈
2. **直觉误导**: 自然会先怀疑 `processed_results` 数据（因为是查询结果的接口）
3. **测试差异**: Python 模拟测试绕过了 FastAPI 的任务验证步骤，所以没有触发错误

---

## 💡 经验教训

### 技术改进
1. **防御性编程**: 在处理数据库数据时，始终验证类型
2. **完整日志**: 需要完整的堆栈跟踪才能快速定位问题
3. **类型安全**: 考虑使用 Pydantic 或类型检查工具验证数据库模型

### 调试技巧
1. **不要过早假设**: 错误消息可能指向症状而非根本原因
2. **检查日志**: API 服务器日志包含完整的堆栈跟踪
3. **追踪数据流**: 理解完整的数据流和处理链路

### 数据完整性
1. **数据验证**: 在写入数据库前验证字段类型
2. **迁移脚本**: 提供数据修复工具
3. **监控告警**: 检测和报告数据类型异常

---

## 🚀 后续建议

### 短期
- [x] 修复代码添加类型检查
- [x] 修复数据库中的错误数据
- [x] 重启 API 服务
- [x] 验证 API 正常工作

### 中期
- [ ] 审查其他可能存在类型错误的字段
- [ ] 添加数据库字段类型验证
- [ ] 完善错误处理和日志记录

### 长期
- [ ] 考虑使用数据库 schema 验证
- [ ] 实现自动化的数据完整性检查
- [ ] 增强 API 错误响应的详细程度

---

## 📎 相关文件

**修复的代码文件**:
- `src/core/domain/entities/search_task.py:195-210` - 实体防御性代码
- `src/infrastructure/database/repositories.py:58-76` - 仓储类型检查

**新创建的工具**:
- `scripts/fix_corrupted_status.py` - 数据库修复脚本

**文档**:
- `claudedocs/STATUS_FIELD_DATA_CORRUPTION_FIX.md` - 本文档

---

## 结论

✅ **问题已完全修复**
- 代码层面：添加了防御性类型检查
- 数据层面：修复了数据库中的错误数据
- 验证完成：API 端点正常返回数据

**关键收获**: 500 错误的真正原因不在查询结果处理，而在任务实体加载时的字段类型错误。完整的日志和系统性的调试方法是快速定位问题的关键。
