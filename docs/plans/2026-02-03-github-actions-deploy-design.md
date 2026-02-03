# GitHub Actions 自动部署到宝塔服务器 - 设计文档

## 概述

使用 GitHub Actions 实现两个项目的自动部署：
- **前端 (guanshanCMS)**: Next.js 项目，使用 PM2 管理
- **后端 (guanshanPython)**: FastAPI 项目，使用 Docker 部署

## 部署架构

```
┌─────────────────┐     push to main     ┌──────────────────┐
│   开发者本地     │ ──────────────────→  │     GitHub       │
│  guanshanCMS    │                      │   (触发 Actions)  │
│  guanshanPython │                      └────────┬─────────┘
└─────────────────┘                               │
                                                  │ SSH
                                                  ▼
                                    ┌─────────────────────────┐
                                    │      宝塔服务器          │
                                    │                         │
                                    │  /www/wwwroot/          │
                                    │  ├── guanshanCMS/       │
                                    │  │   └── PM2 管理       │
                                    │  └── guanshan/          │
                                    │      └── Docker 容器    │
                                    └─────────────────────────┘
```

## 设计决策

| 决策项 | 选择 | 理由 |
|-------|------|------|
| 触发方式 | push 到 main 分支 | 简单直接，适合快速迭代 |
| 连接方式 | SSH 密钥 | 最常用、最灵活 |
| Docker 策略 | 服务器上构建 | 简单，无需镜像仓库 |
| 部署方式 | 独立部署 | 前后端互不影响 |
| 前端构建 | 服务器上构建 | 简单，无需传输产物 |
| 通知 | 无 | 保持简单 |

## 前端部署流程 (guanshanCMS)

```
1. 触发：push 到 main 分支
           ↓
2. SSH 连接到宝塔服务器
           ↓
3. cd /www/wwwroot/guanshanCMS
           ↓
4. git pull origin main
           ↓
5. npm install
           ↓
6. npm run build
           ↓
7. pm2 restart guanshanCMS
           ↓
8. 健康检查
```

## 后端部署流程 (guanshanPython)

```
1. 触发：push 到 main 分支
           ↓
2. SSH 连接到宝塔服务器
           ↓
3. cd /www/wwwroot/guanshan
           ↓
4. git pull origin main
           ↓
5. docker build -t guanshan-app .
           ↓
6. docker stop guanshan-app (如存在)
           ↓
7. docker rm guanshan-app (如存在)
           ↓
8. docker run -d --name guanshan-app \
     --env-file .env \
     -p 8000:8000 \
     --restart unless-stopped \
     guanshan-app
           ↓
9. 健康检查（curl /health）
```

## GitHub Secrets 配置

两个仓库需要分别配置以下 Secrets：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `SERVER_HOST` | 服务器 IP 或域名 | `123.45.67.89` |
| `SERVER_USER` | SSH 用户名 | `root` |
| `SERVER_PORT` | SSH 端口 | `22` |
| `SSH_PRIVATE_KEY` | SSH 私钥完整内容 | `-----BEGIN OPENSSH...` |

### 配置步骤

1. **生成 SSH 密钥对**：
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy"
```

2. **将公钥添加到服务器**：
```bash
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
```

3. **在 GitHub 仓库配置 Secrets**：
   - 进入仓库 → Settings → Secrets and variables → Actions
   - 添加上述 4 个 Secrets

## 文件清单

| 文件路径 | 说明 |
|---------|------|
| `guanshanCMS/.github/workflows/deploy.yml` | 前端部署工作流 |
| `guanshanPython/.github/workflows/deploy.yml` | 后端部署工作流 |

## 服务器端前置要求

### 前端项目
- 目录 `/www/wwwroot/guanshanCMS` 已通过 `git clone` 初始化
- Node.js 已安装
- PM2 已安装

### 后端项目
- 目录 `/www/wwwroot/guanshan` 已通过 `git clone` 初始化
- Docker 已安装
- `.env` 文件已配置好敏感信息

## 安全注意事项

- SSH 私钥仅存储在 GitHub Secrets，不要提交到代码仓库
- `.env` 文件已在 `.gitignore` 中，敏感信息不会被推送
- 建议使用专用的部署用户而非 root（可选优化）

## 创建日期

2026-02-03
