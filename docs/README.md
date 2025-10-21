# 关山智能搜索系统 - 文档中心

**版本**: v1.3.0 | **最后更新**: 2025-10-17

---

## 📚 文档导航

### 快速开始

| 文档 | 说明 | 适用对象 |
|------|------|---------|
| [完整启动指南](../STARTUP_GUIDE.md) | 统一的项目启动和配置指南 | 所有用户 |
| [API使用指南](API_GUIDE.md) | RESTful API完整参考 | 前端/集成 |
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

#### 搜索API

**文档**: [API_GUIDE.md](API_GUIDE.md)

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

#### Firecrawl集成

**文档**: [FIRECRAWL_GUIDE.md](FIRECRAWL_GUIDE.md)

**内容**:
- API密钥获取和配置
- Search API (关键词搜索)
- Scrape API (URL爬取)
- 搜索配置参数
- 测试模式使用

**配置示例**:
```python
search_config = {
    "limit": 10,
    "time_range": "month",
    "language": "zh",
    "include_domains": ["nytimes.com"]
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
├── core/domain/entities/     # 领域实体
├── infrastructure/
│   ├── database/             # 数据库层
│   └── search/               # 搜索适配器
└── services/                 # 业务逻辑
```

### 版本管理

**文档**: [VERSION_MANAGEMENT.md](VERSION_MANAGEMENT.md)

**当前版本**: v1.3.0

**版本历史**:
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
├── README.md                      # 本文档(索引)
├── API_GUIDE.md                   # API完整参考
├── SCHEDULER_GUIDE.md             # 调度器指南
├── MONGODB_GUIDE.md               # MongoDB配置
├── FIRECRAWL_GUIDE.md             # Firecrawl集成
├── RETRY_MECHANISM.md             # 重试机制
├── SYSTEM_ARCHITECTURE.md         # 系统架构
├── VPN_DATABASE_GUIDE.md          # VPN数据库连接指南
├── BACKEND_DEVELOPMENT.md         # 后端开发
├── FEATURE_TRACKER.md             # 功能追踪
├── FUTURE_ROADMAP.md              # 发展路线
├── VERSION_MANAGEMENT.md          # 版本管理
├── SUMMARY_REPORT_SYSTEM_PRD.md   # 总结报告系统PRD
├── reports/                       # 报告目录
│   ├── fixes/                     # 问题修复报告
│   └── tests/                     # 测试报告
└── archive/                       # 历史文档归档
    └── startup/                   # 旧版启动文档（已合并到STARTUP_GUIDE.md）
```

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
**最后审核**: 2025-10-17
**下次审核**: 2025-11-17
