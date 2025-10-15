# 项目变更日志 (Changelog)

本文档记录项目的重要功能开发和变更历史。

---

## [v0.2.0] - 2025-10-15

### ✨ 新增功能

#### 5分钟定时任务调度功能
**完成日期**: 2025-10-15
**状态**: ✅ 已完成并测试通过

**功能描述**:
- 新增 `MINUTES_5` 调度间隔选项，支持每5分钟执行一次的定时任务
- 实现双模式执行逻辑：
  - **关键词搜索模式**: 使用 Firecrawl Search API 进行关键词搜索
  - **URL爬取模式**: 使用 Firecrawl Scrape API 爬取指定网址
- 优先级逻辑: `crawl_url` 参数优先于 `query` 参数

**核心修改**:
- `src/core/domain/entities/search_task.py:24`
  - 添加 `MINUTES_5 = ("MINUTES_5", "*/5 * * * *", "每5分钟", 5, "每5分钟执行一次（测试用）")`

- `src/services/task_scheduler.py:278-420`
  - 重写 `_execute_search_task()` 方法，实现优先级逻辑
  - 新增 `_execute_crawl_task_internal()` 方法，处理URL爬取任务

- `src/infrastructure/crawlers/firecrawl_adapter.py`
  - 修复 Firecrawl SDK 集成问题
  - 从 `AsyncFirecrawl` 更正为 `FirecrawlApp`
  - 修复 `scrape()` 方法为 `scrape_url()`
  - 使用 `asyncio.to_thread()` 包装同步API调用

**测试工具**:
- `scripts/scheduler/create_test_tasks.py` - 快速创建测试任务
- `scripts/scheduler/test_scheduler_5min.py` - 监控任务执行情况
- `scripts/scheduler/test_crawl_url_feature.py` - 测试crawl_url功能

**文档**:
- `claudedocs/SCHEDULER_5MIN_TEST_GUIDE.md` - 完整测试指南

**技术细节**:
- Cron表达式: `*/5 * * * *`
- 调度器: APScheduler AsyncIOScheduler
- 数据持久化: MongoDB (Motor async driver)
- 异步支持: asyncio + FastAPI

**验证结果**:
- ✅ 5分钟调度间隔正确工作
- ✅ 关键词搜索模式正常执行
- ✅ URL爬取模式正常执行
- ✅ 优先级逻辑正确（crawl_url > query）
- ✅ 数据正确存储到MongoDB
- ✅ 任务统计信息准确更新

**相关Issue/PR**: N/A (内部开发)

---

## [v0.1.0] - 2025-10-10

### 🎉 项目初始化

**功能描述**:
- 项目基础架构搭建
- 实现核心搜索任务调度功能
- 集成 Firecrawl API
- MongoDB 数据持久化
- RESTful API 端点

**核心功能**:
- 搜索任务管理 (CRUD)
- 调度器服务 (APScheduler)
- Firecrawl 搜索适配器
- 结果存储和查询

**技术栈**:
- Backend: FastAPI + Python 3.9+
- Database: MongoDB (Motor)
- Scheduler: APScheduler
- Search API: Firecrawl

---

## 项目信息

**项目名称**: 搜索任务调度系统 (Search Task Scheduler)
**当前版本**: v0.2.0
**开始日期**: 2025-10-10
**最后更新**: 2025-10-15

**维护状态**: 🟢 活跃开发中

---

## 版本号说明

项目采用语义化版本 (Semantic Versioning):
- **主版本号 (Major)**: 不兼容的API变更
- **次版本号 (Minor)**: 向后兼容的功能新增
- **修订号 (Patch)**: 向后兼容的问题修复

---

## 待开发功能 (Roadmap)

- [ ] 更多调度间隔选项 (MINUTES_1, MINUTES_15, MINUTES_30)
- [ ] 任务执行历史记录查询API
- [ ] 任务失败重试机制增强
- [ ] 调度器性能监控和指标
- [ ] 多租户支持
- [ ] WebSocket实时任务状态推送

---

**文档生成日期**: 2025-10-15
