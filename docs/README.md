# 关山智能系统 - 系统级文档

**版本**: v3.0.0
**最后更新**: 2025-12-24
**文档数量**: 20 个活动文档

---

## 文档职责

| 目录 | 职责 | 说明 |
|------|------|------|
| **`docs/`** | 系统级文档 | 架构、API、基础设施、部署指南 |
| **`claudedocs/`** | 功能级文档 | NL Search、爬虫、用户精选、版本发布 |

---

## 文档导航

### 核心架构

| 文档 | 说明 |
|------|------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | 系统架构概览 |
| [BACKEND_DEVELOPMENT.md](BACKEND_DEVELOPMENT.md) | 后端开发指南 |
| [ID_SYSTEM_V1.5.0.md](ID_SYSTEM_V1.5.0.md) | ID 系统设计 (雪花算法) |

### API 文档

| 文档 | 说明 |
|------|------|
| [API_USAGE_GUIDE_V2.md](API_USAGE_GUIDE_V2.md) | API 使用指南 v2 |
| [CHAT_SYNC_ENDPOINT_API.md](CHAT_SYNC_ENDPOINT_API.md) | Chat 同步 API |
| [CHAT_SYNC_V3_UPDATE.md](CHAT_SYNC_V3_UPDATE.md) | Chat 同步 v3 更新 |
| [CHAT_SYNC_IMPLEMENTATION_SUMMARY.md](CHAT_SYNC_IMPLEMENTATION_SUMMARY.md) | Chat 同步实现总结 |
| [CHAT_ENDPOINT_ARCHITECTURE_PROPOSAL.md](CHAT_ENDPOINT_ARCHITECTURE_PROPOSAL.md) | Chat 端点架构提案 |

### 数据库

| 文档 | 说明 |
|------|------|
| [MONGODB_GUIDE.md](MONGODB_GUIDE.md) | MongoDB 基础指南 |
| [MONGODB_VPN_CONNECTION_FIX.md](MONGODB_VPN_CONNECTION_FIX.md) | MongoDB VPN 连接修复 |
| [PRODUCTION_DATABASE_SETUP.md](PRODUCTION_DATABASE_SETUP.md) | 生产环境数据库配置 |
| [DATABASE_COLLECTIONS_GUIDE.md](DATABASE_COLLECTIONS_GUIDE.md) | 数据库集合指南 |

### Firecrawl 爬虫

| 文档 | 说明 |
|------|------|
| [FIRECRAWL_ARCHITECTURE_V2.md](FIRECRAWL_ARCHITECTURE_V2.md) | Firecrawl 架构 v2 |
| [FIRECRAWL_GUIDE.md](FIRECRAWL_GUIDE.md) | Firecrawl 入门指南 |

### 调度与重试

| 文档 | 说明 |
|------|------|
| [SCHEDULER_GUIDE.md](SCHEDULER_GUIDE.md) | 调度器使用指南 |
| [RETRY_MECHANISM.md](RETRY_MECHANISM.md) | 重试机制说明 |

### 功能模块

| 文档 | 说明 |
|------|------|
| [FILE_UPLOAD_SYSTEM.md](FILE_UPLOAD_SYSTEM.md) | 文件上传系统 |
| [NL_SEARCH_TEST_DATA_GUIDE.md](NL_SEARCH_TEST_DATA_GUIDE.md) | NL Search 测试数据 |
| [user-auth-design.md](user-auth-design.md) | 用户认证设计 |

### 前端类型

| 目录 | 说明 |
|------|------|
| [frontend-types/](frontend-types/) | 前端 TypeScript 类型定义 |

---

## 归档文档

旧文档已归档至 `.archive/2025-12-24/`，包含 23 个历史设计文档。

---

## 相关链接

- **功能文档**: [claudedocs/README.md](../claudedocs/README.md)
- **项目根目录**: [README.md](../README.md)

---

**文档维护**: Claude Code
**清理日期**: 2025-12-24
**清理内容**: 归档 23 个冗余/过时文档，保留 20 个核心文档
