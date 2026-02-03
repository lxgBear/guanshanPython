# 里程碑：GitHub Actions 自动部署到宝塔服务器

**日期**: 2026-02-03
**状态**: ✅ 已完成

## 概述

成功实现了前后端项目通过 GitHub Actions 自动部署到宝塔服务器的 CI/CD 流程。

## 项目配置

| 项目 | 仓库 | 触发分支 | 服务器路径 | 部署方式 |
|------|------|---------|-----------|---------|
| 后端 | guanshanPython | `main` + `result` | `/www/wwwroot/guanshan` | Docker |
| 前端 | guanshanCMS | `main` | `/www/wwwroot/guanshanCMS` | PM2 |

## 工作流程

### 后端部署流程
```
推送到 result 分支 → GitHub Actions 触发 → SSH 连接服务器 → git pull → docker build → 停止旧容器 → 启动新容器 → 健康检查
```

### 前端部署流程
```
haochun 分支开发测试 → 合并到 main → GitHub Actions 触发 → SSH 连接服务器 → git pull → npm install → npm run build → pm2 restart
```

## 技术实现

### 连接方式
- **SSH 密钥认证** (ed25519)
- 使用 `appleboy/ssh-action@v1.0.3`

### GitHub Secrets 配置
- `SERVER_HOST` - 服务器 IP
- `SERVER_USER` - SSH 用户名
- `SERVER_PORT` - SSH 端口
- `SSH_PRIVATE_KEY` - SSH 私钥

## 文件清单

| 文件 | 说明 |
|------|------|
| `guanshanPython/.github/workflows/deploy.yml` | 后端部署工作流 |
| `guanshanCMS/.github/workflows/deploy.yml` | 前端部署工作流 |
| `docs/plans/2026-02-03-github-actions-deploy-design.md` | 设计文档 |

## 验证结果

- ✅ 后端 GitHub Actions 运行成功
- ✅ 前端 GitHub Actions 运行成功 (14s)
- ✅ 服务器分支配置正确
- ✅ 自动部署流程完整

## 解决的问题

1. **SSH 认证**: 服务器仅支持公钥认证，生成 ed25519 密钥对解决
2. **Git safe.directory**: 添加 `git config --global --add safe.directory` 解决
3. **分支策略**: 后端使用 result 分支，前端使用 main 分支，避免合并冲突

## 后续维护

- 推送到对应分支即可自动部署
- 如需修改部署流程，编辑 `.github/workflows/deploy.yml`
- SSH 密钥存储在 GitHub Secrets，如需更换需同步更新服务器 `~/.ssh/authorized_keys`
