# Makefile for 关山智能系统
.PHONY: help install dev-install test lint format run clean docker-up docker-down

# 默认目标
.DEFAULT_GOAL := help

# 帮助信息
help:
	@echo "关山智能系统 - 可用命令:"
	@echo ""
	@echo "  make install       安装生产环境依赖"
	@echo "  make dev-install   安装开发环境依赖"
	@echo "  make test         运行测试"
	@echo "  make lint         代码质量检查"
	@echo "  make format       格式化代码"
	@echo "  make run          运行应用"
	@echo "  make run-worker   运行Celery Worker"
	@echo "  make clean        清理缓存文件"
	@echo "  make docker-up    启动Docker服务"
	@echo "  make docker-down  停止Docker服务"
	@echo ""

# 安装生产依赖
install:
	pip install -r requirements.txt

# 安装开发依赖
dev-install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

# 运行测试
test:
	pytest tests/ -v --cov=src --cov-report=term-missing

# 单元测试
test-unit:
	pytest tests/unit -v

# 集成测试
test-integration:
	pytest tests/integration -v

# 代码检查
lint:
	flake8 src tests
	mypy src
	pylint src

# 代码格式化
format:
	black src tests
	isort src tests

# 运行应用
run:
	python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 运行Celery Worker
run-worker:
	celery -A src.infrastructure.tasks worker --loglevel=info

# 运行Celery Beat
run-beat:
	celery -A src.infrastructure.tasks beat --loglevel=info

# 数据库迁移
migrate:
	alembic upgrade head

# 创建数据库迁移
migrate-create:
	alembic revision --autogenerate -m "$(message)"

# 清理缓存
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.pytest_cache' -delete
	find . -type d -name '.mypy_cache' -delete
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .ruff_cache

# Docker服务管理
docker-up:
	docker-compose up -d
	@echo "等待服务启动..."
	@sleep 10
	@echo "服务已启动！"

docker-down:
	docker-compose down

docker-restart:
	docker-compose restart

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

# 健康检查
health-check:
	@python scripts/health_check.py

# 初始化项目
init: docker-up install migrate
	@echo "项目初始化完成！"
	@echo "访问 http://localhost:8000/api/docs 查看API文档"