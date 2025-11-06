# 测试套件设计文档

**版本**: v1.0.0 | **创建时间**: 2025-10-17

---

## 📋 总体架构

### 测试金字塔

```
           /\
          /  \        E2E Tests (5%)
         /____\       - API端到端测试
        /      \      - 完整工作流测试
       /________\
      /          \    Integration Tests (15%)
     /            \   - Firecrawl API集成
    /______________\  - 数据库集成
   /                \ - 调度器集成
  /                  \
 /____________________\ Unit Tests (80%)
                        - Adapter单元测试
                        - Service单元测试
                        - Entity单元测试
```

### 测试组织结构

```
tests/
├── unit/                      # 单元测试 (80%覆盖率)
│   ├── test_firecrawl_adapter.py      # Firecrawl适配器单元测试
│   ├── test_task_scheduler.py         # 任务调度器单元测试
│   ├── test_domain_entities.py        # 领域实体测试
│   ├── test_config.py                 # 配置测试
│   └── test_repositories.py           # 仓储层测试
│
├── integration/               # 集成测试 (15%覆盖率)
│   ├── test_api_endpoints.py          # API端点集成测试
│   ├── test_firecrawl_integration.py  # Firecrawl真实API测试
│   ├── test_database_integration.py   # 数据库集成测试
│   └── test_scheduler_integration.py  # 调度器集成测试
│
├── e2e/                       # 端到端测试 (5%覆盖率)
│   ├── test_search_workflow.py        # 搜索工作流测试
│   └── test_scheduler_workflow.py     # 调度器工作流测试
│
├── fixtures/                  # 测试固件和工具
│   ├── mock_data.py                   # 模拟数据生成器
│   ├── test_helpers.py                # 测试辅助函数
│   └── assertions.py                  # 自定义断言
│
├── conftest.py                # pytest全局配置
├── run_tests.py               # 测试运行脚本
└── README.md                  # 测试文档
```

---

## 🎯 测试目标

### 代码覆盖率目标
- **总体覆盖率**: ≥ 85%
- **核心模块覆盖率**: ≥ 90%
  - `firecrawl_search_adapter.py`: 90%+
  - `task_scheduler.py`: 90%+
  - Domain Entities: 95%+
- **边界情况覆盖**: 100% (错误处理、异常场景)

### 测试质量标准
- **测试速度**: 单元测试 < 0.1s/test, 集成测试 < 5s/test
- **测试独立性**: 每个测试独立运行，无依赖顺序
- **测试可维护性**: 使用fixtures减少重复代码
- **测试可读性**: 清晰的测试名称和文档

---

## 🧪 核心测试模块

### 1. Firecrawl Search Adapter 测试

**文件**: `tests/unit/test_firecrawl_adapter_unit.py`

**测试范围**:
```python
FirecrawlSearchAdapter:
  ├── __init__()
  │   ├── ✓ API密钥配置正确
  │   ├── ✓ 测试模式检测正确
  │   └── ✓ 配置管理器初始化
  │
  ├── search()
  │   ├── ✓ 成功搜索返回结果
  │   ├── ✓ 测试模式返回模拟数据
  │   ├── ✓ HTTP错误处理(401, 429, 500)
  │   ├── ✓ 超时错误处理
  │   ├── ✓ 网络连接错误处理
  │   ├── ✓ 重试机制验证(3次重试, 8分钟间隔)
  │   └── ✓ 空结果处理
  │
  ├── _build_request_body()
  │   ├── ✓ 基础请求体构建
  │   ├── ✓ scrapeOptions配置
  │   ├── ✓ 域名限制(site:操作符)
  │   ├── ✓ 时间范围转换
  │   └── ✓ 自定义配置合并
  │
  ├── _parse_search_results()
  │   ├── ✓ v2格式解析(data.web)
  │   ├── ✓ v0格式兼容
  │   ├── ✓ markdown内容截断(5000字符)
  │   ├── ✓ metadata精简
  │   ├── ✓ 文章字段提取
  │   └── ✓ 空数据处理
  │
  └── batch_search()
      ├── ✓ 并发搜索执行
      ├── ✓ 部分失败处理
      └── ✓ 异常聚合
```

**关键测试用例**:
```python
# 成功场景
test_search_success()
test_search_with_custom_config()
test_search_with_domain_filter()
test_batch_search_success()

# 错误场景
test_search_http_401_unauthorized()
test_search_http_429_rate_limit()
test_search_http_500_server_error()
test_search_timeout()
test_search_connection_error()

# 重试机制
test_retry_on_connection_error()
test_retry_on_timeout()
test_no_retry_on_4xx_errors()

# 数据解析
test_parse_v2_format()
test_parse_v0_format()
test_parse_empty_results()
test_markdown_truncation()
```

### 2. Task Scheduler 测试

**文件**: `tests/unit/test_task_scheduler_unit.py`

**测试范围**:
```python
TaskSchedulerService:
  ├── start() / stop()
  │   ├── ✓ 成功启动调度器
  │   ├── ✓ 重复启动检测
  │   ├── ✓ 停止调度器
  │   ├── ✓ 停止时停用任务
  │   └── ✓ 数据库连接失败降级
  │
  ├── add_task() / remove_task()
  │   ├── ✓ 添加活跃任务
  │   ├── ✓ 跳过非活跃任务
  │   ├── ✓ 移除任务
  │   └── ✓ 更新任务
  │
  ├── execute_task_now()
  │   ├── ✓ 立即执行任务
  │   ├── ✓ 任务不存在错误
  │   ├── ✓ 调度器未运行错误
  │   └── ✓ 执行统计更新
  │
  ├── _execute_search_task()
  │   ├── ✓ 搜索模式执行
  │   ├── ✓ 爬取模式执行
  │   ├── ✓ 结果保存到数据库
  │   ├── ✓ 任务统计更新
  │   ├── ✓ 下次执行时间计算
  │   └── ✓ 执行失败处理
  │
  └── get_status() / get_running_tasks()
      ├── ✓ 调度器状态获取
      ├── ✓ 运行任务列表
      └── ✓ 下次执行时间
```

### 3. API Endpoints 测试

**文件**: `tests/integration/test_api_endpoints_comprehensive.py`

**测试范围**:
```python
API Endpoints:
  ├── /api/v1/search-tasks/
  │   ├── POST   ✓ 创建任务
  │   ├── GET    ✓ 查询列表(分页)
  │   ├── GET    ✓ 查询详情
  │   ├── PUT    ✓ 更新任务
  │   └── DELETE ✓ 删除任务
  │
  ├── /api/v1/search-tasks/{id}/results
  │   ├── GET    ✓ 查询结果(分页)
  │   └── GET    ✓ 结果过滤
  │
  ├── /api/v1/scheduler/
  │   ├── GET    /status           ✓ 调度器状态
  │   ├── GET    /running-tasks    ✓ 运行任务
  │   ├── GET    /tasks/{id}/next-run ✓ 下次执行时间
  │   ├── POST   /tasks/{id}/execute  ✓ 手动执行
  │   └── GET    /health           ✓ 健康检查
  │
  └── Error Handling
      ├── ✓ 400 Bad Request
      ├── ✓ 404 Not Found
      ├── ✓ 500 Internal Server Error
      └── ✓ 422 Validation Error
```

---

## 🛠️ 测试工具和固件

### Mock 数据生成器

**文件**: `tests/fixtures/mock_data.py`

```python
# Firecrawl API响应模拟
def create_mock_search_response(count=10, include_markdown=True)
def create_mock_error_response(status_code=500, message="Error")

# 任务实体模拟
def create_mock_search_task(**kwargs)
def create_mock_search_result(**kwargs)
def create_mock_search_config(**kwargs)

# 批量数据生成
def create_mock_result_batch(count=10, success=True)
```

### 测试辅助函数

**文件**: `tests/fixtures/test_helpers.py`

```python
# 异步测试辅助
async def wait_for_condition(condition, timeout=5)
async def wait_for_task_execution(task_id, timeout=10)

# 数据验证
def assert_search_result_valid(result: SearchResult)
def assert_task_statistics_valid(task: SearchTask)

# 清理辅助
async def cleanup_test_tasks(task_ids: List[str])
async def cleanup_test_results(task_id: str)
```

---

## 📊 测试执行策略

### 本地开发测试
```bash
# 运行所有测试
pytest tests/ -v

# 运行特定类型测试
pytest tests/unit/ -v                    # 单元测试
pytest tests/integration/ -v             # 集成测试
pytest tests/e2e/ -v                     # E2E测试

# 运行特定模块测试
pytest tests/unit/test_firecrawl_adapter_unit.py -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

### CI/CD 测试流程
```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run Unit Tests
        run: pytest tests/unit/ --cov=src --cov-report=xml

      - name: Run Integration Tests
        run: pytest tests/integration/ -v

      - name: Upload Coverage
        uses: codecov/codecov-action@v3
```

### 测试环境配置
```bash
# .env.test
TESTING=true
FIRECRAWL_API_KEY=test-api-key
TEST_MODE=true
LOG_LEVEL=DEBUG
MONGODB_URL=mongodb://localhost:27017/test_db
```

---

## 🎯 测试最佳实践

### 1. 测试命名规范
```python
# ✅ Good
def test_search_returns_results_when_api_succeeds():
    pass

def test_search_raises_error_when_api_returns_401():
    pass

# ❌ Bad
def test_1():
    pass

def test_search():
    pass
```

### 2. 使用Fixtures
```python
@pytest.fixture
async def mock_firecrawl_client():
    """模拟Firecrawl客户端"""
    client = AsyncMock()
    client.search.return_value = create_mock_search_response()
    return client

async def test_search_with_mock(mock_firecrawl_client):
    adapter = FirecrawlSearchAdapter()
    adapter.client = mock_firecrawl_client
    result = await adapter.search("test query")
    assert result.success
```

### 3. 测试隔离
```python
@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """每个测试后自动清理"""
    yield
    # 清理测试数据
    await cleanup_test_tasks()
    await cleanup_test_results()
```

### 4. 参数化测试
```python
@pytest.mark.parametrize("status_code,expected_error", [
    (401, "Unauthorized"),
    (429, "Rate limit exceeded"),
    (500, "Internal server error"),
])
async def test_http_errors(status_code, expected_error):
    # 测试不同HTTP错误
    pass
```

---

## 📈 测试监控和报告

### 覆盖率报告
```bash
# 生成HTML覆盖率报告
pytest tests/ --cov=src --cov-report=html

# 查看报告
open htmlcov/index.html
```

### 性能测试
```python
@pytest.mark.benchmark
def test_search_performance(benchmark):
    result = benchmark(lambda: adapter.search("test"))
    assert result.execution_time_ms < 5000  # 5秒内完成
```

### 测试报告生成
```bash
# 生成详细测试报告
pytest tests/ --html=report.html --self-contained-html
```

---

## 🔄 持续改进

### 定期评审
- **每周**: 检查测试覆盖率趋势
- **每月**: 评审慢速测试和优化
- **每季度**: 更新测试策略和最佳实践

### 测试债务管理
- 标记待修复的测试: `@pytest.mark.xfail`
- 标记慢速测试: `@pytest.mark.slow`
- 定期清理过时测试

### 测试文档维护
- 保持测试文档与代码同步
- 记录测试覆盖的边界情况
- 文档化已知问题和限制

---

**文档维护**: Backend Team | **最后更新**: 2025-10-17
