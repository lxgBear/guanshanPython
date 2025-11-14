# 代码清理前检查清单

**版本**: v1.0.0
**日期**: 2025-11-14
**用途**: 执行代码清理前的完整检查清单

---

## 📋 使用说明

请在执行代码清理前，**逐项检查**以下内容。确保所有标记为 🔴 **必须** 的项目都已完成，标记为 🟡 **推荐** 的项目根据实际情况决定是否完成。

**符号说明**:
- ✅ 已完成
- ⏸️ 跳过
- ❌ 未完成
- 🔴 必须完成
- 🟡 推荐完成
- 🟢 可选完成

---

## 🔴 第一部分: 系统状态检查（必须）

### 1.1 服务运行状态

- [ ] 🔴 **检查uvicorn服务正在运行**
  ```bash
  ps aux | grep uvicorn
  # 预期：应看到运行中的uvicorn进程
  ```

- [ ] 🔴 **检查MongoDB服务正常**
  ```bash
  ps aux | grep mongod
  mongo --eval "db.runCommand({connectionStatus : 1})"
  # 预期：connected: true
  ```

- [ ] 🔴 **检查最近30条日志无ERROR**
  ```bash
  tail -30 logs/uvicorn.log | grep -i error
  # 预期：无输出或只有旧的ERROR
  ```

- [ ] 🔴 **系统启动完成且功能正常**
  ```bash
  tail -10 logs/uvicorn.log | grep "系统启动成功"
  # 预期：看到"✅ 系统启动成功"日志
  ```

### 1.2 Git仓库状态

- [ ] 🔴 **检查当前分支**
  ```bash
  git branch
  # 预期：在feature分支或main分支
  ```

- [ ] 🟡 **检查是否有未提交的重要更改**
  ```bash
  git status
  # 预期：了解当前工作区状态
  ```

- [ ] 🟡 **确认最近的提交可以作为回滚点**
  ```bash
  git log -1 --oneline
  # 预期：看到最近的有效提交
  ```

### 1.3 磁盘空间

- [ ] 🔴 **检查磁盘空间足够（至少1GB可用）**
  ```bash
  df -h .
  # 预期：Available列 > 1GB
  ```

- [ ] 🟢 **记录清理前项目大小**
  ```bash
  du -sh .
  # 预期：记录初始大小，用于对比
  ```

---

## 🟡 第二部分: 环境准备（推荐）

### 2.1 创建安全备份

- [ ] 🟡 **创建Git安全点（如有未提交更改）**
  ```bash
  git add -A
  git commit -m "chore: 清理前备份点" || git stash save "清理前备份"
  ```

- [ ] 🟡 **创建数据库备份（生产环境必做）**
  ```bash
  python scripts/backup_database.py
  # 或手动导出关键集合
  ```

- [ ] 🟢 **创建项目副本（如有足够空间）**
  ```bash
  cd ..
  cp -r guanshanPython guanshanPython_backup_$(date +%Y%m%d)
  ```

### 2.2 环境验证

- [ ] 🟡 **Python虚拟环境已激活**
  ```bash
  which python
  # 预期：指向venv/bin/python
  ```

- [ ] 🟡 **所有依赖已安装**
  ```bash
  pip check
  # 预期：无依赖冲突
  ```

- [ ] 🟢 **运行单元测试（如有）**
  ```bash
  pytest tests/unit/ -v
  # 预期：测试通过
  ```

---

## 🔴 第三部分: 清理范围确认（必须）

### 3.1 确认待删除的临时文件

- [ ] 🔴 **检查临时日志文件**
  ```bash
  ls -lh api.log uvicorn.log test_url_filtering_output.log 2>/dev/null
  # 预期：看到文件列表及大小
  ```

- [ ] 🔴 **检查临时JSON文件**
  ```bash
  ls -lh crawl_result_*.json 2>/dev/null
  # 预期：看到文件列表
  ```

- [ ] 🔴 **确认这些文件未被引用**
  ```bash
  grep -r "api\.log\|uvicorn\.log\|crawl_result_" src/ --include="*.py"
  # 预期：无输出（未被引用）
  ```

### 3.2 确认待删除的覆盖率报告

- [ ] 🔴 **检查覆盖率报告目录**
  ```bash
  ls -lh htmlcov/ .coverage 2>/dev/null
  # 预期：看到目录和文件
  ```

- [ ] 🔴 **确认可以重新生成**
  ```bash
  # 只需确认pytest已安装pytest-cov插件
  pip show pytest-cov
  # 预期：显示插件信息
  ```

### 3.3 确认待归档的备份目录

- [ ] 🔴 **检查.backup/目录**
  ```bash
  ls -lhR .backup/ 2>/dev/null
  # 预期：看到备份内容和时间戳
  ```

- [ ] 🔴 **检查backups/目录**
  ```bash
  ls -lhR backups/ 2>/dev/null
  # 预期：看到备份内容和时间戳
  ```

- [ ] 🔴 **确认备份已过期（>7天）**
  ```bash
  find .backup backups -type f -mtime +7
  # 预期：列出7天前的文件
  ```

### 3.4 确认待归档的测试脚本

- [ ] 🔴 **统计test_*.py脚本数量**
  ```bash
  ls scripts/test_*.py 2>/dev/null | wc -l
  # 预期：约29个
  ```

- [ ] 🔴 **确认测试脚本未被引用**
  ```bash
  grep -r "scripts/test_" src/ --include="*.py"
  # 预期：无输出（未被引用）
  ```

- [ ] 🟡 **识别核心脚本（应保留）**
  ```bash
  ls scripts/*.py | grep -v test_ | grep -v check_ | grep -v analyze_
  # 预期：看到22个核心功能脚本
  ```

---

## 🟡 第四部分: 工具准备（推荐）

### 4.1 检查清理脚本

- [ ] 🟡 **确认清理脚本存在**
  ```bash
  ls -l scripts/cleanup_stage*.sh
  # 预期：看到stage1和stage2脚本
  ```

- [ ] 🟡 **确认脚本可执行**
  ```bash
  test -x scripts/cleanup_stage1_zero_risk.sh && echo "可执行" || echo "需要chmod +x"
  ```

### 4.2 准备验证工具

- [ ] 🟢 **准备系统监控命令**
  ```bash
  # 记录清理前的进程列表
  ps aux | grep -E "uvicorn|python|mongod" > /tmp/processes_before.txt
  ```

- [ ] 🟢 **准备文件统计命令**
  ```bash
  # 记录清理前的文件统计
  find scripts -name "*.py" | wc -l > /tmp/script_count_before.txt
  ```

---

## 🔴 第五部分: 风险评估（必须）

### 5.1 评估业务影响

- [ ] 🔴 **确认当前无正在运行的重要任务**
  ```bash
  # 检查数据库中的活跃任务
  mongo guanshan --eval "db.search_tasks.count({status: 'running'})"
  # 预期：0 或 可接受的数量
  ```

- [ ] 🔴 **确认清理时间窗口合适**
  - 时间段：___________（填写：如"晚上8点-10点"）
  - 业务影响：☐ 无 ☐ 低 ☐ 中 ☐ 高
  - 用户影响：☐ 无 ☐ 低 ☐ 中 ☐ 高

### 5.2 评估技术风险

- [ ] 🔴 **清理操作的最坏情况已知**
  - 最坏情况：系统无法启动
  - 恢复方案：Git回滚 或 从备份恢复
  - 恢复时间：约____分钟（预估）

- [ ] 🔴 **回滚方案已准备好**
  ```bash
  # 确认Git reflog可用
  git reflog | head -5
  # 预期：看到最近的操作历史
  ```

---

## ✅ 第六部分: 最终确认（必须全部完成）

### 6.1 关键检查项

- [ ] 🔴 **已阅读完整分析报告**
  - 文件：`claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md`
  - 理解：清理范围、风险等级、回滚方案

- [ ] 🔴 **已阅读操作指南**
  - 文件：`docs/CODE_CLEANUP_GUIDE.md`
  - 理解：执行步骤、验证方法、问题排查

- [ ] 🔴 **已有充足时间完成清理和验证**
  - 预计耗时：15-30分钟
  - 可用时间：______分钟

### 6.2 人员准备

- [ ] 🟡 **有其他人员可以协助（生产环境）**
  - 协助人员：__________
  - 联系方式：__________

- [ ] 🟡 **已通知相关人员（如有必要）**
  - 通知对象：☐ 团队负责人 ☐ 其他开发者 ☐ 运维人员
  - 通知时间：__________

### 6.3 最终确认

- [ ] 🔴 **我已理解清理操作的风险**
- [ ] 🔴 **我已准备好回滚方案**
- [ ] 🔴 **我有充足时间完成清理和验证**
- [ ] 🔴 **我确认现在是执行清理的合适时机**

---

## 📝 执行记录

### 执行信息

- **执行人**: __________
- **执行时间**: __________ (YYYY-MM-DD HH:MM)
- **环境**: ☐ 本地开发 ☐ 测试环境 ☐ 生产环境

### 检查结果统计

- 🔴 必须项（共16项）: _____ / 16 完成
- 🟡 推荐项（共13项）: _____ / 13 完成
- 🟢 可选项（共6项）: _____ / 6 完成

### 决策

- [ ] ✅ **所有必须项已完成，可以开始清理**
- [ ] ⏸️ **等待，需要完成更多必须项**
- [ ] ❌ **取消清理，时机不合适**

---

## 🆘 应急联系

### 出现问题时

1. **立即停止清理操作**
2. **记录错误信息**
3. **查看回滚方案** (`docs/CODE_CLEANUP_GUIDE.md` → 回滚方案章节)
4. **如需帮助，准备以下信息**:
   - 错误日志：`tail -100 logs/uvicorn.log`
   - Git状态：`git status`
   - 执行步骤：记录已完成的清理步骤

### 相关文档

- 📝 [完整分析报告](../claudedocs/CODE_CLEANUP_ANALYSIS_2025-11-14.md)
- 📝 [操作指南](./CODE_CLEANUP_GUIDE.md)
- 📝 [Git提交模板](./GIT_COMMIT_TEMPLATE.md)

---

## ✍️ 签名确认（可选）

我已完成上述所有必须检查项，理解清理操作的风险和回滚方案，确认现在是执行代码清理的合适时机。

**签名**: ________________
**日期**: ________________

---

**文档版本**: v1.0.0
**最后更新**: 2025-11-14
**维护者**: Claude Code SuperClaude Framework
