# 关山智能搜索系统 - 文档中心

**版本**: v2.0.2 | **最后更新**: 2025-11-05

---

## 📚 文档导航

### 快速开始

| 文档 | 说明 | 适用对象 |
|------|------|---------|
| [完整启动指南](../STARTUP_GUIDE.md) | 统一的项目启动和配置指南 | 所有用户 |
| [API使用指南 V2](API_USAGE_GUIDE_V2.md) | RESTful API完整参考（最新版本）| 前端/集成 |
| [系统架构](SYSTEM_ARCHITECTURE.md) | 技术架构和设计模式 | 架构师/后端 |

### 核心功能

#### 定时任务调度

**文档**: [SCHEDULER_GUIDE.md](SCHEDULER_GUIDE.md)

**内容**:
- 调度间隔配置 (5分钟/30分钟/每小时/每天/每周)
- 任务CRUD操作
- 手动触发执行
- 故障重试机制
- 监控和告警

**快速命令**:
```bash
# 创建任务
curl -X POST http://localhost:8000/api/v1/search-tasks/ -d '{...}'

# 手动执行
curl -X POST http://localhost:8000/api/v1/scheduler/tasks/{id}/execute

# 查看状态
curl http://localhost:8000/api/v1/scheduler/status
```

#### 搜索结果处理系统 (v2.0.0) 🎯 最新

**文档**: [职责分离架构设计](SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md)

**核心特性**:
- **双表架构**: `search_results`（原始数据）+ `news_results`（AI处理结果）
- **职责分离**: 原始存储与AI处理完全解耦
- **异步处理**: AI服务独立处理，不阻塞定时任务
- **智能增强**: AI翻译、总结、分类、情感分析
- **状态管理**: 6种处理状态，支持重试机制
- **用户操作**: 留存、删除、评分、备注功能

**查询优先级**:
1. **主要查询**: `/api/v1/search-tasks/{id}/results` → 返回 `news_results`（AI增强数据）
2. **备用查询**: `/api/v1/search-results/tasks/{id}` → 返回 `search_results`（原始数据）

**数据流程**:
```
定时任务 → Firecrawl → search_results（只写一次）
                    → create pending in news_results
                    → AI异步处理
                    → news_results（完成）
                    → 前端展示
```

**详细文档**:
- [完整架构设计](SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md) - 54KB完整方案
- [UML图表和数据流](diagrams/) - 4个mermaid图表
- [实施指南](SEARCH_RESULTS_IMPLEMENTATION_GUIDE.md) - 9天实施计划
- [数据库集合指南](DATABASE_COLLECTIONS_GUIDE.md) - v2.1.0更新

#### 搜索API

**文档**: [API_USAGE_GUIDE_V2.md](API_USAGE_GUIDE.md)

**内容**:
- 搜索任务管理
- 结果查询和分页
- 即时搜索(无需创建任务)
- 调度器管理API
- 请求/响应示例 (Python/curl/JavaScript)

**核心端点**:
```
POST   /api/v1/search-tasks/              # 创建任务
GET    /api/v1/search-tasks/              # 查询列表
GET    /api/v1/search-tasks/{id}          # 查询详情
PUT    /api/v1/search-tasks/{id}          # 更新任务
DELETE /api/v1/search-tasks/{id}          # 删除任务
GET    /api/v1/search-tasks/{id}/results  # 查询结果
```

#### 数据源管理

**文档**: [DATA_SOURCE_CURATION_BACKEND.md](DATA_SOURCE_CURATION_BACKEND.md)

**内容**:
- 数据源创建和编辑
- 状态管理（draft ⇄ confirmed）
- 原始数据引用和状态同步
- 数据源确认和退回流程

**存档系统**:
- [数据源存档系统指南](ARCHIVED_DATA_GUIDE.md) - 完整技术方案、UML图表、API文档、部署指南

#### ID系统 (v1.5.0)

**文档**: [ID_SYSTEM_V1.5.0.md](ID_SYSTEM_V1.5.0.md)

**内容**:
- ID系统统一为雪花算法（UUID → Snowflake ID）
- 历史数据迁移（255条记录）
- Repository序列化修复
- 智能错误处理和向后兼容
- 完整的问题分析、解决方案和验证结果

**关键成果**:
- ✅ 所有ID统一为雪花算法格式（15-19位数字）
- ✅ 100%历史数据迁移成功
- ✅ 智能UUID检测和用户友好的错误提示
- ✅ 代码简化，移除UUID相关逻辑

### 基础设施

#### MongoDB数据库

**文档**: [MONGODB_GUIDE.md](MONGODB_GUIDE.md)

**内容**:
- 安装和配置(宝塔面板)
- 数据库初始化
- 迁移系统使用
- 故障排查(连接/认证/端口)
- 性能优化
- 备份与恢复

**快速命令**:
```bash
# 执行迁移
python scripts/run_migrations.py migrate

# 查看状态
python scripts/run_migrations.py status

# 备份数据
mongodump --uri="mongodb://localhost:27017/intelligent_system"
```

#### Firecrawl集成 🎯 最新

**核心文档**:
- [Firecrawl架构 V2](FIRECRAWL_ARCHITECTURE_V2.md) - 模块化架构设计（完整指南）
- [搜索质量优化](SEARCH_QUALITY_OPTIMIZATION.md) - 首页过滤和内容验证（最新）
- [Firecrawl增强功能](FIRECRAWL_ENHANCED_FEATURES.md) - 高级功能和配置
- [Firecrawl基础指南](FIRECRAWL_GUIDE.md) - 快速入门

**v2.0 新特性**:
- ✅ 模块化执行器架构（SearchExecutor / CrawlExecutor / ScrapeExecutor）
- ✅ 四层首页内容防护（URL过滤 + 配置优化 + 内容验证 + 智能重试）
- ✅ 关键词搜索质量大幅提升（首页内容比例从40-60%降至5-15%）
- ✅ 支持三种任务类型（search_keyword / crawl_website / scrape_url）

**配置示例**:
```python
# 关键词搜索（带质量优化）
search_config = {
    "limit": 10,
    "language": "zh",
    "enable_detail_scrape": true,
    "max_concurrent_scrapes": 2,
    "wait_for": 3000,
    "scrape_delay": 2.0
}

# 网站爬取
crawl_config = {
    "limit": 100,
    "max_depth": 3,
    "include_paths": ["/article/", "/news/"],
    "only_main_content": true
}
```

#### 重试机制

**文档**: [RETRY_MECHANISM.md](RETRY_MECHANISM.md)

**内容**:
- 故障自动重试(8分钟×3次)
- 适用场景(DNS/超时/HTTP错误)
- 重试日志和监控
- 性能影响分析

**重试策略**:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(480),  # 8分钟
    retry=retry_if_exception_type((
        httpx.ConnectError,
        httpx.TimeoutException
    ))
)
```

---

## 🔧 开发指南

### 后端开发

**文档**: [BACKEND_DEVELOPMENT.md](BACKEND_DEVELOPMENT.md)

**技术栈**:
- FastAPI (Web框架)
- MongoDB + Motor (数据库)
- APScheduler (定时任务)
- httpx + tenacity (HTTP客户端 + 重试)

**项目结构**:
```
src/
├── api/v1/endpoints/         # API端点
│   ├── search_task_management.py
│   ├── scheduler_management.py
│   └── news_results.py  # v2.0.0新增：AI处理结果API
├── core/domain/entities/     # 领域实体
│   ├── search_task.py
│   ├── search_result.py      # v2.0.0简化：移除状态管理
│   └── processed_result.py   # v2.0.0新增：AI处理结果实体
├── infrastructure/
│   ├── database/             # 数据库层
│   │   ├── repositories.py   # SearchResultRepository（简化）
│   │   └── processed_result_repositories.py  # v2.0.0新增
│   └── search/               # 搜索适配器
└── services/                 # 业务逻辑
    └── task_scheduler.py     # v2.0.0更新：集成AI通知
```

### 版本管理

**文档**: [VERSION_MANAGEMENT.md](VERSION_MANAGEMENT.md)

**当前版本**: v2.0.0 (设计中)

**最近更新**:
- v2.0.0 (2025-11-03): 🎯 **搜索结果职责分离架构** - 双表设计（设计完成，待实施）
  - search_results: 纯原始数据存储（不可变）
  - news_results: AI处理结果（主查询源）
  - 完整架构文档、UML图表、实施指南
- v1.5.2 (2025-10-31): 状态系统简化（5状态→3状态）
- v1.5.0 (2025-10-31): ID系统统一（UUID→雪花ID）+ 历史数据迁移
- v1.4.2 (2025-10-31): 智能ID检测（临时方案）
- v1.4.1 (2025-10-30): 空数据源确认Bug修复

**早期版本**:
- v1.3.0 (2025-10-17): 重试机制、手动执行API
- v1.2.0 (2025-10-15): 即时搜索功能
- v1.1.0 (2025-10-13): 调度器集成
- v1.0.0 (2025-10-11): 基础功能

### 功能追踪

**文档**: [FEATURE_TRACKER.md](FEATURE_TRACKER.md)

**已实现**:
- ✅ 定时搜索任务
- ✅ 调度器管理
- ✅ 即时搜索
- ✅ 重试机制
- ✅ 数据库迁移系统

**规划中**:
- ⏳ 用户认证系统
- ⏳ 搜索结果去重
- ⏳ 导出功能(CSV/JSON)

---

## 🚀 快速参考

### 常用命令

```bash
# 启动服务
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 执行迁移
python scripts/run_migrations.py migrate

# 运行测试
pytest tests/

# 查看日志
tail -f /tmp/8000.log
```

### 环境配置

```bash
# .env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=intelligent_system
FIRECRAWL_API_KEY=your_api_key
FIRECRAWL_BASE_URL=https://api.firecrawl.dev
TEST_MODE=false
```

### API测试

```bash
# 健康检查
curl http://localhost:8000/health

# 创建任务
curl -X POST http://localhost:8000/api/v1/search-tasks/ \
  -H "Content-Type: application/json" \
  -d '{"name":"测试","query":"AI","schedule_interval":"HOURLY","is_active":true}'

# 查询结果
curl "http://localhost:8000/api/v1/search-tasks/{id}/results?page=1&page_size=10"
```

---

## 📁 目录结构

```
docs/
├── README.md                                      # 本文档(索引)
├── SYSTEM_ARCHITECTURE.md                         # 系统架构
│
├── Firecrawl集成 (v2.0) 🎯
│   ├── FIRECRAWL_ARCHITECTURE_V2.md               # 模块化架构设计
│   ├── SEARCH_QUALITY_OPTIMIZATION.md             # 首页过滤和质量优化
│   ├── FIRECRAWL_ENHANCED_FEATURES.md             # 高级功能配置
│   └── FIRECRAWL_GUIDE.md                         # 快速入门指南
│
├── API文档
│   └── API_USAGE_GUIDE_V2.md                      # API完整参考（最新）
│
├── 搜索结果处理系统 (v2.0)
│   ├── SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md  # 职责分离架构
│   ├── SEARCH_RESULTS_IMPLEMENTATION_GUIDE.md     # 实施指南
│   └── INSTANT_SEARCH_MIGRATION_PLAN.md           # 即时搜索迁移
│
├── 数据源管理
│   ├── DATA_SOURCE_CURATION_BACKEND.md            # 数据源管理后端
│   ├── DATA_SOURCE_STATUS_MANAGEMENT.md           # 状态管理系统
│   └── ARCHIVED_DATA_GUIDE.md                     # 数据源存档系统
│
├── 数据库与基础设施
│   ├── DATABASE_COLLECTIONS_GUIDE.md              # 数据库集合指南
│   ├── MONGODB_GUIDE.md                           # MongoDB配置
│   ├── DATABASE_MIGRATION_GUIDE.md                # 数据库迁移
│   ├── PRODUCTION_DATABASE_SETUP.md               # 生产环境配置
│   └── VPN_DATABASE_GUIDE.md                      # VPN数据库连接
│
├── 开发指南
│   ├── BACKEND_DEVELOPMENT.md                     # 后端开发
│   ├── SCHEDULER_GUIDE.md                         # 调度器指南
│   ├── RETRY_MECHANISM.md                         # 重试机制
│   ├── TEST_SUITE_DESIGN.md                       # 测试套件设计
│   └── EXECUTION_HISTORY_DESIGN.md                # 执行历史设计
│
├── 项目管理
│   ├── VERSION_MANAGEMENT.md                      # 版本管理
│   ├── FEATURE_TRACKER.md                         # 功能追踪
│   ├── FUTURE_ROADMAP.md                          # 发展路线
│   ├── ID_SYSTEM_V1.5.0.md                        # ID系统统一
│   ├── FILE_UPLOAD_SYSTEM_DESIGN.md               # 文件上传系统
│   ├── SUMMARY_REPORT_SYSTEM_PRD.md               # 总结报告PRD
│   ├── MILESTONES.md                              # 里程碑
│   └── DOCUMENTATION_CONSOLIDATION_PLAN.md        # 文档整理计划
│
├── diagrams/                                      # 架构图目录
├── reports/                                       # 报告目录
│   ├── fixes/                                     # 问题修复报告
│   ├── tests/                                     # 测试报告
│   └── weekly/                                    # 周报
└── archive/                                       # 历史文档归档
    ├── v1.4.1/                                    # v1.4.1历史文档
    ├── v1.4.2/                                    # v1.4.2历史文档
    └── analysis/                                  # 一次性分析报告
```

### 文档组织说明

**核心活跃文档** (5个):
- `README.md` - 文档中心索引
- `SYSTEM_ARCHITECTURE.md` - 系统架构概览
- `DATA_SOURCE_CURATION_BACKEND.md` - 数据源管理（1395行完整指南）
- `ARCHIVED_DATA_GUIDE.md` - 数据源存档系统（896行完整方案）
- `ID_SYSTEM_V1.5.0.md` - ID系统统一报告（v1.5.0，合并了迁移报告和摘要）

**历史归档** (archive/):
- `v1.4.1/` - v1.4.1版本的Bug修复文档
- `v1.4.2/` - v1.4.2版本的Bug修复文档（已被v1.5.0取代）
- `analysis/` - 一次性架构分析报告
- `startup/` - 旧版启动文档（已合并）

---

## 🔗 相关资源

### 官方文档

- **FastAPI**: https://fastapi.tiangolo.com
- **MongoDB**: https://docs.mongodb.com
- **Firecrawl**: https://docs.firecrawl.dev
- **APScheduler**: https://apscheduler.readthedocs.io

### 在线工具

- **API文档**: http://localhost:8000/docs (Swagger UI)
- **数据库管理**: MongoDB Compass
- **API测试**: Postman / Insomnia

### 问题反馈

- **GitHub Issues**: (项目仓库链接)
- **维护团队**: Backend Team
- **紧急联系**: (联系方式)

---

## 📝 贡献指南

### 文档维护

文档更新流程:
1. 修改相应的Markdown文件
2. 确保内容简洁、准确、完整
3. 更新 `最后更新` 日期
4. 提交Pull Request

### 文档规范

- **标题**: 使用中文,清晰描述功能
- **代码示例**: 提供完整可运行的代码
- **版本标注**: 注明功能所在版本
- **链接**: 相关文档之间添加交叉引用

---

**文档维护**: Backend Team
**最后审核**: 2025-11-05
**下次审核**: 2025-12-05

## 📋 文档整理记录

**v2.0.2 文档清理 (2025-11-05)**:
- ✅ **清理过时文档**：删除 18 个过时的实现日志和临时文件
  - claudedocs/: 29 → 6 文件（-79%，仅保留最新实现记录）
  - 删除类别：服务日志、bug调查、API更新日志、超时修复、版本测试报告
- ✅ **整合架构文档**：移动 6 个重要设计文档从 claudedocs 到 docs
  - DATABASE_COLLECTIONS_GUIDE.md（27K）
  - EXECUTION_HISTORY_DESIGN.md（17K）
  - TEST_SUITE_DESIGN.md（11K）
  - SEARCH_RESULTS_IMPLEMENTATION_GUIDE.md（41K）
  - SEARCH_RESULTS_SEPARATION_ARCHITECTURE.md（19K）
  - INSTANT_SEARCH_MIGRATION_PLAN.md（25K）
- ✅ **更新API文档**：删除旧版 API_GUIDE.md，统一使用 API_USAGE_GUIDE_V2.md
- ✅ **重组文档结构**：按功能模块分类（Firecrawl / API / 搜索结果 / 数据源 / 数据库 / 开发 / 项目管理）
- ✅ **更新所有引用**：修正 README.md 中所有文档链接
- ✅ **备份创建**：所有更改前完整备份到 `.backup/docs_cleanup_20251105/`

**效果**:
- 文档总数减少：63 → 37 文件（-41%）
- claudedocs 精简：仅保留最新6个实现摘要
- docs 集中管理：所有永久文档统一在 docs/
- 清晰的功能分类：7大模块，易于导航

**v1.5.2 文档整理 (2025-10-31)**:
- ✅ 合并ID系统文档：`ID_SYSTEM_MIGRATION_REPORT.md` + `ID_SYSTEM_UNIFICATION_v1.5.0_SUMMARY.md` → `ID_SYSTEM_V1.5.0.md`
- ✅ 归档历史Bug修复文档到 `archive/v1.4.1/` 和 `archive/v1.4.2/`
- ✅ 归档一次性分析报告到 `archive/analysis/`
- ✅ 更新文档索引结构
- ✅ 减少顶层文档数量：9个 → 5个核心文档 (-44%)
- ✅ 详细整理计划：参见 `DOCUMENTATION_CONSOLIDATION_PLAN.md`
