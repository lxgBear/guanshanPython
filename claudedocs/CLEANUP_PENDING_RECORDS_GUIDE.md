# 清理 Pending 记录脚本使用指南

## 概述

`cleanup_pending_news_results.py` 脚本用于安全清理 `news_results` 集合中 `status="pending"` 的记录。

**脚本位置**: `scripts/cleanup_pending_news_results.py`

## 功能特性

✅ **安全预览模式** - 默认 dry-run 模式，不会删除数据
✅ **时间过滤** - 支持按天数过滤（只删除 N 天前的记录）
✅ **详细统计** - 显示详细的记录统计和样本数据
✅ **按任务分组** - 查看哪些任务产生了最多的 pending 记录
✅ **确认机制** - 执行删除前需要用户明确确认
✅ **结果验证** - 删除后自动验证清理结果

## 使用场景

1. **清理长期未处理的记录** - AI 处理失败或卡住的任务
2. **重置任务队列** - 清空待处理队列重新开始
3. **释放数据库空间** - 删除不需要的 pending 记录
4. **测试数据清理** - 清理测试期间产生的 pending 记录

## 使用方法

### 1. 预览模式（推荐先运行）

```bash
# 查看所有 pending 记录统计（不删除）
python3 scripts/cleanup_pending_news_results.py

# 查看 7 天前创建的 pending 记录（不删除）
python3 scripts/cleanup_pending_news_results.py --days 7
```

**输出示例**:
```
📊 Pending 记录统计
======================================================================
⏰ 时间范围: 所有时间
📈 总计: 4838 条 pending 记录

📋 按任务分组统计 (Top 10):
  1. Task ID: 245059966926098432
     数量: 3816 条
  2. Task ID: 244895743529586688
     数量: 350 条
  ...

🔍 样本数据 (前5条):
  [1] ID: 244879702695698432
      Task: 244879584026255360
      Title: Editor in-Chief - Tibet Post International
      ...
```

### 2. 执行删除

```bash
# 删除所有 pending 记录
python3 scripts/cleanup_pending_news_results.py --execute

# 只删除 7 天前创建的 pending 记录
python3 scripts/cleanup_pending_news_results.py --execute --days 7

# 只删除 30 天前创建的 pending 记录
python3 scripts/cleanup_pending_news_results.py --execute --days 30
```

**确认提示**:
```
⚠️  准备删除 pending 记录
   数量: 4838 条
   范围: 所有 pending 记录

⚠️  此操作不可逆！

确认删除? (yes/no):
```

输入 `yes` 确认执行删除。

### 3. 查看帮助

```bash
python3 scripts/cleanup_pending_news_results.py --help
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--execute` | 执行删除操作（不加此参数为预览模式） | 预览模式 |
| `--days N` | 只处理 N 天前创建的记录 | 所有时间 |

## 安全机制

1. **默认预览模式** - 不加 `--execute` 参数时不会删除任何数据
2. **明确确认** - 执行删除前需要输入 `yes` 确认
3. **时间过滤** - 使用 `--days` 参数避免误删新记录
4. **删除前统计** - 显示详细的删除目标统计信息
5. **删除后验证** - 自动验证删除结果并显示剩余记录数

## 实际案例

### 案例 1: 清理测试数据

**场景**: 测试期间产生了大量 pending 记录，需要清理

```bash
# 步骤 1: 预览所有 pending 记录
python3 scripts/cleanup_pending_news_results.py

# 输出: 📈 总计: 4838 条 pending 记录

# 步骤 2: 确认后执行删除
python3 scripts/cleanup_pending_news_results.py --execute

# 输入 yes 确认

# 输出: ✅ 已删除: 4838 条 pending 记录
```

### 案例 2: 只清理旧记录

**场景**: 只想清理 7 天前的旧记录，保留最近的

```bash
# 步骤 1: 预览 7 天前的记录
python3 scripts/cleanup_pending_news_results.py --days 7

# 输出: 📈 总计: 1250 条 pending 记录（7天前）

# 步骤 2: 执行删除
python3 scripts/cleanup_pending_news_results.py --execute --days 7

# 输入 yes 确认

# 输出: ✅ 已删除: 1250 条 pending 记录
```

### 案例 3: 按任务清理

**场景**: 从统计中发现某个任务产生了大量 pending 记录

```bash
# 步骤 1: 运行预览查看任务统计
python3 scripts/cleanup_pending_news_results.py

# 输出显示:
# 1. Task ID: 245059966926098432
#    数量: 3816 条

# 步骤 2: 如果需要只删除该任务的记录，可以:
# - 临时修改脚本添加 task_id 过滤
# - 或者使用 MongoDB shell 手动删除特定任务
```

## 输出说明

### 统计报告

- **总计** - 符合条件的 pending 记录总数
- **按任务分组** - Top 10 任务及其 pending 记录数
- **样本数据** - 前 5 条记录的详细信息（ID、Task、Title、URL、创建时间）

### 删除结果

- **删除记录数** - 实际删除的记录数量
- **当前 pending 记录数** - 删除后剩余的 pending 记录数（可能是新创建的）

## 注意事项

⚠️ **删除不可逆** - 删除的记录无法恢复，请谨慎操作
⚠️ **生产环境** - 在生产环境执行前务必先在测试环境验证
⚠️ **备份建议** - 重要数据建议先备份再执行删除
⚠️ **时间过滤** - 使用 `--days` 参数时注意计算正确的天数
⚠️ **服务影响** - 删除操作会影响数据库性能，建议在低峰期执行

## 故障排除

### 问题 1: 数据库连接失败

**错误**: `MongoDB连接失败`

**解决**:
1. 检查 `.env` 文件中的 `MONGODB_URL` 配置
2. 确认 MongoDB 服务正在运行
3. 检查网络连接

### 问题 2: 权限错误

**错误**: `Permission denied`

**解决**:
```bash
# 添加执行权限
chmod +x scripts/cleanup_pending_news_results.py
```

### 问题 3: 导入错误

**错误**: `ModuleNotFoundError: No module named 'src'`

**解决**:
```bash
# 确保在项目根目录执行
cd /Users/lanxionggao/Documents/guanshanPython
python3 scripts/cleanup_pending_news_results.py
```

## 相关文档

- **数据模型**: `src/core/domain/entities/processed_result.py`
- **数据库集合**: `news_results`
- **状态枚举**: `ProcessedStatus` (pending, processing, completed, failed, archived, deleted)

## 版本历史

**v1.0.0** (2025-11-18)
- 初始版本
- 支持 dry-run 和 execute 模式
- 支持按天数过滤
- 详细统计和样本展示
- 删除确认和结果验证

---

**作者**: Claude Code
**创建日期**: 2025-11-18
**最后更新**: 2025-11-18
