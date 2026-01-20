# 关山智能系统 - 开发命令参考

## 环境设置

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
make install              # 生产依赖
make dev-install          # 开发依赖 (包含测试和代码质量工具)
pip install -r requirements.txt      # 直接安装
pip install -r requirements-dev.txt  # 开发依赖
```

## 运行应用

```bash
# 使用 Makefile
make run

# 直接运行
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 测试

```bash
# 完整测试 (带覆盖率)
make test
pytest tests/ -v --cov=src --cov-report=term-missing

# 单元测试
make test-unit
pytest tests/unit -v

# 集成测试
make test-integration
pytest tests/integration -v

# 运行特定测试
pytest tests/test_xxx.py -v
pytest tests/unit/test_xxx.py::test_function -v

# 带详细输出
pytest -v -s --tb=long
```

## 代码质量

```bash
# 代码格式化
make format
black src tests
isort src tests

# 代码检查
make lint
flake8 src tests
mypy src
pylint src

# 单独运行
black --check src tests  # 检查格式
isort --check-only src tests  # 检查导入顺序
```

## Docker

```bash
# 启动所有服务
make docker-up
docker-compose up -d

# 停止服务
make docker-down
docker-compose down

# 查看日志
make docker-logs
docker-compose logs -f

# 查看状态
make docker-ps
docker-compose ps

# 重启服务
make docker-restart
docker-compose restart
```

## 数据库迁移

```bash
# 运行迁移
make migrate
alembic upgrade head

# 创建新迁移
make migrate-create message="迁移描述"
alembic revision --autogenerate -m "迁移描述"
```

## 清理

```bash
make clean
# 清理内容:
# - *.pyc 文件
# - __pycache__ 目录
# - .pytest_cache
# - .mypy_cache
# - htmlcov
# - .coverage
# - .ruff_cache
```

## 健康检查

```bash
# API 健康检查
curl http://localhost:8000/health

# 调度器状态
curl http://localhost:8000/api/v1/scheduler/status
```

## Git 工作流

```bash
# 查看状态
git status

# 创建功能分支
git checkout -b feature/xxx

# 提交前检查
make format && make lint && make test

# 提交
git add .
git commit -m "feat: 功能描述"

# 推送
git push origin feature/xxx
```

## 系统命令 (macOS/Darwin)

```bash
# 文件查找
find . -name "*.py" -type f
mdfind -onlyin . "kMDItemDisplayName == '*.py'"

# 内容搜索
grep -r "pattern" src/
grep -rn "pattern" --include="*.py" .

# 进程管理
lsof -i :8000  # 查看端口占用
kill -9 PID    # 终止进程

# 环境变量
export VAR=value
echo $VAR
```
