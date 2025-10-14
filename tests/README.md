# 测试目录说明

本目录包含项目的所有测试文件，按照测试类型和功能模块进行组织。

## 目录结构

```
tests/
├── README.md                    # 本文件 - 测试目录说明
├── __init__.py                  # 测试包初始化
│
├── unit/                        # 单元测试
│   ├── __init__.py
│   ├── test_entities.py        # 实体模型测试
│   ├── test_repositories.py    # 数据仓储测试
│   └── test_services.py        # 服务层测试
│
├── integration/                 # 集成测试
│   ├── __init__.py
│   ├── test_api.py             # API端点测试
│   ├── test_database.py        # 数据库集成测试
│   └── test_search.py          # 搜索功能集成测试
│
├── scheduler/                   # 调度器测试
│   ├── __init__.py
│   ├── test_scheduler.py       # 调度器功能测试
│   └── test_search_results_fix.py  # 搜索结果存储测试
│
└── run_tests.py                # 测试运行脚本
```

## 测试类型

### 单元测试 (unit/)

测试单个组件或函数的功能，不依赖外部服务。

**特点**:
- 快速执行
- 隔离性好
- 使用模拟对象（Mock）

**运行**:
```bash
pytest tests/unit/ -v
```

### 集成测试 (integration/)

测试多个组件之间的交互，可能依赖数据库、API等外部服务。

**特点**:
- 需要真实环境
- 验证组件协作
- 执行时间较长

**运行**:
```bash
pytest tests/integration/ -v
```

### 调度器测试 (scheduler/)

专门测试定时任务调度器的功能测试和问题修复验证。

**特点**:
- 功能性测试
- 端到端验证
- 包含修复验证

**运行**:
```bash
# 调度器功能测试
python tests/scheduler/test_scheduler.py

# 搜索结果存储测试
python tests/scheduler/test_search_results_fix.py
```

## 运行所有测试

### 使用pytest (推荐)

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定模块
pytest tests/unit/ -v
pytest tests/integration/ -v

# 运行特定文件
pytest tests/unit/test_entities.py -v

# 显示覆盖率
pytest tests/ --cov=src --cov-report=html
```

### 使用测试运行脚本

```bash
# 运行所有测试
python tests/run_tests.py

# 运行特定类型
python tests/run_tests.py --type unit
python tests/run_tests.py --type integration
python tests/run_tests.py --type scheduler
```

## 测试编写规范

### 命名规范

- 测试文件: `test_*.py`
- 测试类: `Test*`
- 测试函数: `test_*`

### 示例

```python
# tests/unit/test_example.py

import pytest
from src.core.domain.entities.example import ExampleEntity


class TestExampleEntity:
    """ExampleEntity单元测试"""

    def test_create_entity(self):
        """测试实体创建"""
        entity = ExampleEntity(name="test")
        assert entity.name == "test"

    def test_entity_validation(self):
        """测试实体验证"""
        with pytest.raises(ValueError):
            ExampleEntity(name="")
```

## 测试配置

### conftest.py

每个测试目录可以包含`conftest.py`文件，定义共享的fixtures和配置。

```python
# tests/conftest.py

import pytest
from src.infrastructure.database.connection import init_database


@pytest.fixture(scope="session")
async def database():
    """数据库连接fixture"""
    await init_database()
    yield
    # 清理代码
```

### pytest.ini

项目根目录的`pytest.ini`文件配置pytest行为:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## 测试数据

### 使用测试模式

设置环境变量启用测试模式:

```bash
export TEST_MODE=true
```

或在`.env`文件中:

```
TEST_MODE=true
TEST_MAX_RESULTS=10
```

### 测试数据清理

测试后自动清理测试数据，避免污染数据库。

```python
@pytest.fixture
def clean_database():
    """自动清理测试数据"""
    yield
    # 测试后清理
    cleanup_test_data()
```

## 持续集成

### GitHub Actions

`.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=src
```

## 相关文档

- [调度器功能测试报告](../docs/SCHEDULER_TEST_REPORT.md)
- [搜索结果修复报告](../docs/SEARCH_RESULTS_FIX_REPORT.md)
- [API使用指南](../docs/API_USAGE_GUIDE.md)

## 常见问题

### Q: 测试运行很慢怎么办？

A:
1. 使用`pytest -n auto`并行运行测试
2. 跳过慢速的集成测试：`pytest -m "not slow"`
3. 只运行失败的测试：`pytest --lf`

### Q: 测试数据库配置？

A: 使用单独的测试数据库，配置在`.env.test`文件中。

### Q: 如何模拟外部API？

A: 使用`unittest.mock`或`pytest-mock`模拟HTTP请求。

---

**最后更新**: 2025-10-13
**维护者**: Development Team
