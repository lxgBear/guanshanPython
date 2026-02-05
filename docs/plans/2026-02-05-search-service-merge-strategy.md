# 搜索服务架构重构 - 合并策略设计

## 概述

**目标**：将 `feature/search-service-replacement` 实验分支成功合并回 `result` 分支

**策略选择**：Merge 策略 + 冲突时以实验分支为准

## 当前分支状态

| 分支 | 提交 | 状态 |
|------|------|------|
| `result` | e5b197b | 主开发分支，包含 AchievementDraft 等新功能 |
| `feature/search-service-replacement` | 701e7c0 | 实验分支，包含 SearchPipeline 新架构 |
| 共同祖先 | 0981cdb | 分叉点 |

## 变更对比

**实验分支新增**：
- `src/search_service/` 完整模块 (1,287 行)
- 设计文档 (128 行)
- `gsac_engine.py` 重构 (-141 行改动)

**result 分支新增** (需保留)：
- AchievementDraft 功能 (实体、仓储、服务、API)
- gsac 超时和结果数配置调整

---

## 合并执行步骤

### 步骤 1：准备工作

```bash
# 确保两个分支都是最新
git fetch origin
git checkout result
git pull origin result

git checkout feature/search-service-replacement
git pull origin feature/search-service-replacement
```

### 步骤 2：先在实验分支测试合并

```bash
# 在实验分支合并 result，验证冲突情况
git checkout feature/search-service-replacement
git merge result
```

### 步骤 3：解决冲突（如有）

冲突文件优先级：

| 文件 | 策略 |
|------|------|
| `src/search_service/*` | 保留实验分支版本 |
| `src/services/langgraph_search/gsac_engine.py` | 保留实验分支版本 |
| `src/services/achievement/*` | 保留 result 版本 |
| 其他 `src/services/*` | 保留 result 版本 |
| `docs/*` | 合并两边内容 |

### 步骤 4：验证与测试

```bash
# 运行测试确保合并正确
pytest tests/ -v

# 启动服务验证功能
python -m uvicorn src.main:app --reload
```

### 步骤 5：正式合并到 result

```bash
git checkout result
git merge feature/search-service-replacement -m "feat(search): merge SearchPipeline architecture from experiment"
git push origin result
```

---

## 回滚策略

如果合并后发现问题，可以快速回滚：

```bash
# 查找合并前的 result 提交
git reflog

# 回滚到合并前状态
git checkout result
git reset --hard e5b197b  # 合并前的 result 提交
git push origin result --force-with-lease
```

---

## 清理工作

合并成功且验证通过后：

### 删除实验分支

```bash
# 删除本地分支
git branch -d feature/search-service-replacement

# 删除远程分支
git push origin --delete feature/search-service-replacement
```

### 清理 worktree

```bash
# 删除 worktree
git worktree remove .worktrees/search-service-experiment

# 验证清理完成
git worktree list
```

### 合并后检查清单

- [ ] 所有测试通过
- [ ] API 文档可访问 (`/api/docs`)
- [ ] 搜索功能正常工作
- [ ] AchievementDraft 功能不受影响
- [ ] 无遗留的冲突标记 (`<<<<<<<`)

---

## 并行开发期间的同步策略

在实验分支合并前，如果需要保持同步：

```bash
# 定期将 result 合并到实验分支（建议每周一次）
git checkout feature/search-service-replacement
git merge result

# 解决冲突后继续实验开发
```

---

## 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 实验分支 | `experiment/<模块>-<描述>` | `experiment/search-pipeline` |
| 功能分支 | `feature/<功能名>` | `feature/achievement-draft` |
| 修复分支 | `fix/<问题描述>` | `fix/gsac-timeout` |

## Worktree 目录规范

```
.worktrees/
├── <分支简称>-experiment/   # 实验性开发
├── <分支简称>-feature/      # 功能开发
└── <分支简称>-hotfix/       # 紧急修复
```

---

## 合并时机判断

实验分支应在满足以下条件时合并：

1. 核心功能实现完成
2. 单元测试覆盖关键路径
3. 与现有功能无破坏性冲突
4. 性能不低于原有实现
