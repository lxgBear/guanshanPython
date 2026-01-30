# 并行分支开发工作流程

## 概述

使用 Git Worktree 实现 `result` 和 `feature/map-detail-experiment` 分支的并行开发，最终将 feature 分支合并到 result 分支。

## 目录结构

```
~/Documents/
├── guanshanPython/                    # feature/map-detail-experiment 分支
└── guanshanPython-result/             # result 分支
```

## 日常开发流程

### 在两个目录独立工作

```bash
# 目录 1：开发 map-detail 功能
cd ~/Documents/guanshanPython
# 正常开发、commit、push

# 目录 2：开发 result 分支功能
cd ~/Documents/guanshanPython-result
# 正常开发、commit、push
```

### 保持同步（可选）

如果 result 分支有新提交，想让 feature 分支跟上：

```bash
cd ~/Documents/guanshanPython
git fetch origin
git merge origin/result
```

### 注意事项

- 两个目录共享同一个 `.git` 仓库，commit 是即时可见的
- 不要在两个目录同时操作同一个分支

## 合并与清理

### 合并 feature 到 result

```bash
cd ~/Documents/guanshanPython-result
git fetch origin
git merge feature/map-detail-experiment
# 解决冲突（如有），然后 commit
git push origin result
```

### 清理 worktree

```bash
cd ~/Documents/guanshanPython
git worktree remove ../guanshanPython-result
```

### 清理 feature 分支（可选）

```bash
git branch -d feature/map-detail-experiment
git push origin --delete feature/map-detail-experiment
```
