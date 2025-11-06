# 搜索任务重试机制

**版本**: v1.0
**实施日期**: 2025-10-17
**目的**: 防止因临时网络故障导致的数据丢失，提升用户体验

---

## 📋 需求背景

### 问题描述

2025-10-17 14:00时，任务ID `237408060762787840` 执行时遇到DNS解析故障：

```
❌ 搜索发生意外错误: ConnectError: [Errno 8] nodename nor servname provided, or not known
```

**故障持续时间**: 约8分钟（14:00 - 14:08）
**原因**: 临时DNS解析失败（网络连接中断）
**影响**: 该次搜索任务失败，未产生任何搜索结果，前端无数据可用

### 用户需求

1. **重试间隔**: 8分钟（480秒）
2. **重试次数**: 最多3次
3. **用户体验**: 避免因单次临时故障导致的数据丢失

---

## 🛠️ 实施方案

### 核心改动

**文件**: `src/infrastructure/search/firecrawl_search_adapter.py`

#### 1. 导入依赖更新

```python
# 之前
from tenacity import retry, stop_after_attempt, wait_exponential

# 之后
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
```

**变更说明**:
- 移除 `wait_exponential`: 原指数退避策略（4-10秒）不适合长时间网络故障
- 新增 `wait_fixed`: 固定间隔重试，符合用户需求（8分钟）
- 新增 `retry_if_exception_type`: 指定仅对特定异常类型重试

#### 2. 重试装饰器配置

```python
@retry(
    stop=stop_after_attempt(3),  # 最多尝试3次
    wait=wait_fixed(480),          # 每次重试间隔8分钟（480秒）
    retry=retry_if_exception_type((
        httpx.ConnectError,        # DNS解析失败、网络连接错误
        httpx.TimeoutException,    # 请求超时
        httpx.HTTPStatusError      # HTTP错误状态码（如502）
    )),
    before_sleep=lambda retry_state: FirecrawlSearchAdapter._log_retry_attempt(None, retry_state)
)
async def search(...):
    ...
```

**重试策略**:
- **首次尝试**: 立即执行
- **第1次重试**: 失败后等待8分钟
- **第2次重试**: 再次失败后再等待8分钟
- **第3次重试**: 最后一次机会，失败后不再重试

**总耗时**: 最多 24分钟（3次尝试 × 8分钟间隔）

#### 3. 重试日志记录

```python
def _log_retry_attempt(self, retry_state):
    """记录重试尝试"""
    attempt_number = retry_state.attempt_number
    if attempt_number > 1:
        exception = retry_state.outcome.exception()
        logger.warning(
            f"🔄 搜索请求失败，第 {attempt_number - 1} 次重试 (共3次) | "
            f"错误: {type(exception).__name__}: {str(exception)[:100]} | "
            f"将在 8 分钟后重试..."
        )
```

**日志示例**:
```
2025-10-17 14:00:00 - ❌ 搜索发生意外错误: ConnectError: DNS解析失败
2025-10-17 14:00:00 - 🔄 搜索请求失败，第 1 次重试 (共3次) | 错误: ConnectError: DNS解析失败 | 将在 8 分钟后重试...
2025-10-17 14:08:00 - ✅ 解析得到 10 条搜索结果
```

---

## 🎯 重试场景分析

### 场景1: 临时DNS故障（14:00案例）

| 时间 | 状态 | 操作 |
|------|------|------|
| 14:00:00 | ❌ 首次尝试失败 | DNS解析失败 |
| 14:00:01 | ⏳ 等待重试 | 系统等待8分钟 |
| 14:08:01 | ✅ 第1次重试成功 | 网络已恢复，获取10条结果 |

**结果**: 成功获取数据，避免数据丢失

### 场景2: 持续网络中断

| 时间 | 状态 | 操作 |
|------|------|------|
| 14:00:00 | ❌ 首次尝试失败 | 网络不可达 |
| 14:08:00 | ❌ 第1次重试失败 | 网络仍不可达 |
| 14:16:00 | ❌ 第2次重试失败 | 网络仍不可达 |
| 14:24:00 | ❌ 最终失败 | 记录失败统计 |

**结果**: 已尽最大努力，记录失败原因供人工介入

### 场景3: API限流（HTTP 429）

| 时间 | 状态 | 操作 |
|------|------|------|
| 14:00:00 | ❌ 首次尝试失败 | HTTP 429 Too Many Requests |
| 14:08:00 | ✅ 第1次重试成功 | 限流窗口已过，请求成功 |

**结果**: 自动处理限流，无需人工干预

---

## 📊 性能影响分析

### 成功场景（最佳情况）

- **首次成功**: 7秒（正常API响应时间）
- **无重试开销**: 0秒
- **总耗时**: 7秒

### 重试场景（有故障）

- **首次尝试**: 7秒
- **第1次重试**: 8分钟 + 7秒
- **总耗时**: 8分07秒（相比无重试机制，延迟8分钟但成功获取数据）

### 最坏场景（持续故障）

- **3次尝试**: 3 × 7秒 = 21秒
- **2次等待**: 2 × 8分钟 = 16分钟
- **总耗时**: 16分21秒（最终失败，但已尽最大努力）

### 对定时任务的影响

**任务调度间隔**: 每小时（60分钟）
**重试最长耗时**: 16分钟
**安全边距**: 60 - 16 = 44分钟

✅ **结论**: 重试机制不会影响下一次定时任务执行

---

## 🔍 监控与告警

### 日志监控关键词

```bash
# 监控重试事件
grep "🔄 搜索请求失败" /tmp/8000.log

# 监控最终失败
grep "❌ 搜索任务执行失败" /tmp/8000.log

# 监控成功恢复
grep "✅ 搜索任务执行完成" /tmp/server_8000.log
```

### 建议告警规则

1. **首次重试告警** (Warning)
   - 触发条件: 出现 "第 1 次重试" 日志
   - 告警级别: 警告
   - 行动: 记录，观察第2次重试

2. **第2次重试告警** (High)
   - 触发条件: 出现 "第 2 次重试" 日志
   - 告警级别: 高
   - 行动: 通知运维，准备人工介入

3. **最终失败告警** (Critical)
   - 触发条件: 3次重试后仍失败
   - 告警级别: 紧急
   - 行动: 立即人工介入，检查网络/API状态

---

## 🧪 测试建议

### 单元测试

```python
# 测试1: 首次成功（无重试）
async def test_search_success_first_try():
    """测试首次尝试成功，不触发重试"""
    # Mock API返回成功
    # 验证: 只调用1次API

# 测试2: 首次失败，重试成功
async def test_search_retry_success():
    """测试首次失败，第1次重试成功"""
    # Mock: 首次失败(ConnectError)，第2次成功
    # 验证: 调用2次API，间隔480秒

# 测试3: 全部失败
async def test_search_all_retries_fail():
    """测试3次尝试全部失败"""
    # Mock: 3次全部返回ConnectError
    # 验证: 调用3次API，最终抛出异常
```

### 集成测试

```bash
# 模拟DNS故障场景
# 1. 断网8分钟
# 2. 观察重试日志
# 3. 恢复网络
# 4. 验证数据获取成功
```

---

## 📝 运维指南

### 手动重试失败任务

如果自动重试失败，可手动触发：

```bash
curl --noproxy "*" -X POST \
  "http://localhost:8000/api/v1/scheduler/tasks/237408060762787840/execute"
```

### 查看任务执行统计

```bash
curl --noproxy "*" \
  "http://localhost:8000/api/v1/search-tasks/237408060762787840"
```

**关键字段**:
- `execution_count`: 总执行次数（包括重试）
- `success_count`: 成功次数
- `fail_count`: 失败次数
- `last_executed_at`: 最后执行时间

### 调整重试参数

**配置位置**: `src/infrastructure/search/firecrawl_search_adapter.py:54-59`

```python
@retry(
    stop=stop_after_attempt(3),  # 修改重试次数
    wait=wait_fixed(480),         # 修改重试间隔（秒）
    ...
)
```

**常见调整场景**:
- 快速恢复场景: `wait_fixed(60)` (1分钟)
- 极端故障场景: `stop_after_attempt(5)` (5次重试)

---

## 🎯 总结

### 解决的问题

✅ **数据丢失**: 临时故障不再导致数据丢失
✅ **用户体验**: 无需人工干预，系统自动恢复
✅ **可观测性**: 详细日志记录，便于监控告警

### 技术优势

1. **精准重试**: 仅对网络相关异常重试，避免无意义重试
2. **合理间隔**: 8分钟间隔适合临时网络故障恢复
3. **可控上限**: 最多3次重试，避免无限循环
4. **透明日志**: 每次重试都有详细日志，便于排查

### 未来改进方向

1. **动态间隔**: 根据错误类型调整重试间隔（如限流错误使用更长间隔）
2. **智能降级**: 多次失败后使用备用数据源
3. **实时告警**: 集成监控系统（如Prometheus + Grafana）
4. **重试队列**: 持久化失败任务，延迟批量重试

---

**文档维护者**: Claude Code
**最后更新**: 2025-10-17 14:35
**版本**: 1.0
