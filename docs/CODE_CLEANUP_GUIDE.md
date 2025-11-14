# 关山项目代码清理操作指南

**版本**: v1.0.0
**日期**: 2025-11-14
**参考文档**: [claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md](../claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md)

---

## 🎯 快速开始

### 执行前准备

1. ✅ **确认系统正常运行**
```bash
# 检查服务状态
ps aux | grep uvicorn

# 检查最新日志
tail -20 logs/uvicorn.log
```

2. ✅ **创建安全备份点**
```bash
# 创建Git提交（如果有未提交的重要更改）
git add -A
git commit -m "chore: 清理前备份点"

# 或创建Git stash
git stash save "清理前备份"
```

3. ✅ **检查磁盘空间**
```bash
df -h .
du -sh .
```

---

## 📋 三步清理流程

### 🟢 步骤1: 零风险清理（必做）

**耗时**: ~1分钟
**风险**: 零
**收益**: 节省2.4MB空间

```bash
# 方案A: 使用自动化脚本（推荐）
bash scripts/cleanup_stage1_zero_risk.sh

# 方案B: 手动执行
rm -f api.log uvicorn.log test_url_filtering_output.log crawl_result_*.json
rm -rf htmlcov/
rm -f .coverage
rm -rf archive/
```

**验证**:
```bash
# 检查清理结果
ls -lh | grep -E "\.log$|\.json$|htmlcov|\.coverage|archive"
```

---

### 🟡 步骤2: 低风险清理（推荐）

**耗时**: ~3-5分钟
**风险**: 低（有归档备份）
**收益**: 节省1.2MB空间 + 整理29个测试脚本

```bash
# 使用交互式脚本（推荐）
bash scripts/cleanup_stage2_low_risk.sh
```

脚本会询问：
1. ❓ 是否创建备份归档？ → 推荐选择 **y**
2. ❓ 是否删除备份目录？ → 推荐选择 **y**
3. ❓ 是否移动测试脚本？ → 推荐选择 **y**
4. ❓ 是否移动检查脚本？ → 可选择 **n**（保留以备后用）

**手动执行**:
```bash
# 归档备份
tar -czf backup_archive_$(date +%Y%m%d).tar.gz .backup/ backups/
rm -rf .backup/ backups/

# 移动测试脚本
mkdir -p scripts/archive/test_scripts_$(date +%Y%m%d)
mv scripts/test_*.py scripts/archive/test_scripts_$(date +%Y%m%d)/
```

**验证**:
```bash
# 检查归档结果
ls -lh backup_archive_*.tar.gz
ls -lh scripts/archive/test_scripts_*/
```

---

### ✅ 步骤3: 系统验证（必做）

**耗时**: ~2-3分钟
**重要性**: 🔴 **关键** - 确保系统正常运行

```bash
# 1. 重启服务
pkill -15 -f "uvicorn src.main:app"
sleep 2
nohup uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > logs/uvicorn.log 2>&1 &

# 2. 检查启动日志
tail -30 logs/uvicorn.log

# 3. 验证关键功能
# - 查看是否有ERROR或WARNING
# - 确认"系统启动成功"日志
# - 确认"MongoDB连接成功"日志
```

**关键检查点**:
- ✅ 无ERROR日志
- ✅ MongoDB连接成功
- ✅ 调度器启动成功
- ✅ API端点可访问

如果出现问题，参考[回滚方案](#回滚方案)。

---

## 🔄 Git提交流程

### 选项A: 一键提交（推荐）

```bash
# 使用预置提交脚本
bash scripts/cleanup_stage3_git_commit.sh
```

### 选项B: 手动提交

```bash
# 1. 检查Git状态
git status

# 2. 添加Repository重构相关文件
git add src/infrastructure/database/*.py
git add src/infrastructure/persistence/

# 3. 添加新文档
git add claudedocs/REPOSITORY_REFACTORING_V3_SUMMARY.md
git add claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md
git add docs/*.md

# 4. 添加清理脚本和工具
git add scripts/cleanup_stage*.sh
git add scripts/execute_task_244887942339018752.py
git add scripts/monitor_task_execution.sh

# 5. 创建提交（使用提供的模板）
git commit -F docs/GIT_COMMIT_TEMPLATE.md

# 6. 验证提交
git log -1 --stat
```

**提交前检查清单**:
- [ ] src/infrastructure/persistence/ 已添加
- [ ] src/infrastructure/database/ 修改已暂存
- [ ] 新文档已添加（4-6个.md文件）
- [ ] 临时文件未被添加（.log, .json, htmlcov/）
- [ ] 提交信息完整且准确

---

## ⚠️ 回滚方案

### 如果清理后系统无法启动

**方案1: 恢复备份（如果创建了归档）**
```bash
# 恢复备份目录
tar -xzf backup_archive_20251114.tar.gz

# 恢复测试脚本
cp -r scripts/archive/test_scripts_20251114/* scripts/
```

**方案2: Git回滚**
```bash
# 查看最近提交
git log --oneline -5

# 回滚到上一个提交
git reset --hard HEAD~1

# 或者使用reflog找到清理前的提交
git reflog
git reset --hard <commit-hash>
```

**方案3: 从Git stash恢复**
```bash
# 查看stash列表
git stash list

# 恢复最新stash
git stash pop
```

### 常见问题排查

**Q: MongoDB连接失败**
```bash
# 检查MongoDB服务
ps aux | grep mongod

# 查看MongoDB日志
tail -50 /usr/local/var/log/mongodb/mongo.log

# 重启MongoDB（如果需要）
brew services restart mongodb-community
```

**Q: 系统启动报错找不到模块**
```bash
# 检查虚拟环境
source venv/bin/activate
pip list | grep -E "fastapi|uvicorn|pymongo"

# 重新安装依赖（如果需要）
pip install -r requirements.txt
```

**Q: Repository相关错误**
```bash
# 检查persistence目录是否完整
ls -R src/infrastructure/persistence/

# 检查__init__.py文件是否存在
find src/infrastructure/persistence -name "__init__.py"
```

---

## 📊 清理效果统计

### 预期清理结果

| 项目 | 清理前 | 清理后 | 改善 |
|------|--------|--------|------|
| 磁盘空间 | 280MB | 276.5MB | -3.5MB |
| 临时文件 | 4个 | 0个 | -100% |
| 测试脚本 | 29个 | 0个（已归档） | -100% |
| 备份目录 | 2个 | 0个（已归档） | -100% |

### 清理验证命令

```bash
# 统计项目大小
du -sh .

# 检查临时文件
find . -maxdepth 1 -name "*.log" -o -name "*.json"

# 检查测试脚本数量
ls scripts/test_*.py 2>/dev/null | wc -l

# 检查归档目录
ls -lh scripts/archive/
ls -lh backup_archive_*.tar.gz 2>/dev/null
```

---

## 🎯 最佳实践

### 执行建议

1. **时间选择**:
   - ✅ 推荐在非高峰时段执行（如晚上或周末）
   - ✅ 确保有足够时间验证系统

2. **分步执行**:
   - ✅ 先执行步骤1，验证无问题后再执行步骤2
   - ✅ 每步执行后都进行系统验证

3. **保留证据**:
   - ✅ 保存清理前后的 `git status` 输出
   - ✅ 保存清理前后的 `du -sh .` 输出
   - ✅ 保存验证日志

### 定期维护计划

**每周任务**:
```bash
# 清理7天前的日志
find logs/ -name "*.log" -mtime +7 -exec gzip {} \;

# 清理临时文件
find . -maxdepth 1 -name "*.log" -o -name "crawl_result_*.json" | xargs rm -f 2>/dev/null
```

**每月任务**:
```bash
# 归档完成的测试脚本
mkdir -p scripts/archive/monthly_$(date +%Y%m)
mv scripts/test_<completed_feature>.py scripts/archive/monthly_$(date +%Y%m)/
```

**季度任务**:
```bash
# 审查并清理过期备份
find backups/ -type d -mtime +90 -exec tar -czf {}.tar.gz {} \; -exec rm -rf {} \;
```

---

## 📞 获取帮助

### 问题反馈

如果遇到问题，请收集以下信息：

1. **错误日志**:
```bash
tail -100 logs/uvicorn.log > error_report.log
```

2. **系统状态**:
```bash
git status > git_status.txt
ps aux | grep -E "uvicorn|python" > process_status.txt
```

3. **执行步骤**: 记录已执行的清理步骤

### 相关文档

- 📝 [完整分析报告](../claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md)
- 📝 [Repository重构总结](../claudedocs/REPOSITORY_REFACTORING_V3_SUMMARY.md)
- 📝 [Git提交模板](./GIT_COMMIT_TEMPLATE.md)
- 📝 [清理前检查清单](./PRE_CLEANUP_CHECKLIST.md)

---

**文档版本**: v1.0.0
**最后更新**: 2025-11-14
**维护者**: Claude Code SuperClaude Framework
