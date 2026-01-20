# 关山智能系统 - 任务完成检查清单

## 代码提交前必做检查

### 1. 代码格式化
```bash
# 自动格式化
make format
# 或手动执行
black src tests
isort src tests
```

### 2. 类型检查
```bash
mypy src
```
- 确保没有类型错误
- 新代码必须有类型注解

### 3. 代码质量检查
```bash
make lint
# 或分别执行
flake8 src tests
pylint src
```
- 修复所有 error 级别问题
- warning 级别问题应尽量修复

### 4. 运行测试
```bash
make test
# 或
pytest tests/ -v --cov=src --cov-report=term-missing
```
- 所有测试必须通过
- 新功能需要添加对应测试
- 覆盖率不应下降

### 5. 手动验证 (如适用)
```bash
# 启动服务
make run

# 健康检查
curl http://localhost:8000/health

# 测试 API
curl http://localhost:8000/api/v1/xxx
```

## 提交信息规范

### 格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式 (不影响功能)
- `refactor`: 重构 (不新增功能或修复 bug)
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建/工具相关

### 示例
```
feat(langgraph): 添加多语言检测功能

- 实现语言检测节点
- 支持中英日韩四种语言
- 添加单元测试

Closes #115
```

## PR 检查清单

- [ ] 代码已格式化 (`make format`)
- [ ] 类型检查通过 (`mypy src`)
- [ ] Lint 检查通过 (`make lint`)
- [ ] 所有测试通过 (`make test`)
- [ ] 新功能有对应测试
- [ ] 文档已更新 (如需要)
- [ ] 无敏感信息提交
- [ ] 提交信息符合规范

## 新功能开发检查

### 添加新 API 端点
- [ ] 创建 endpoint 文件
- [ ] 添加到 router.py
- [ ] 创建请求/响应 schema
- [ ] 实现服务层逻辑
- [ ] 添加单元测试
- [ ] 添加集成测试
- [ ] 更新 API 文档

### 添加新服务
- [ ] 创建服务类
- [ ] 定义接口 (如需要)
- [ ] 实现依赖注入
- [ ] 添加日志记录
- [ ] 添加错误处理
- [ ] 添加测试

### 数据模型变更
- [ ] 更新实体定义
- [ ] 创建数据库迁移
- [ ] 更新相关 schema
- [ ] 测试数据兼容性

## 常见问题检查

### 安全性
- [ ] 无硬编码密钥/密码
- [ ] API 密钥从环境变量读取
- [ ] 输入已验证
- [ ] SQL/NoSQL 注入防护

### 性能
- [ ] 避免 N+1 查询
- [ ] 合理使用缓存
- [ ] 异步操作正确使用
- [ ] 无阻塞调用

### 可维护性
- [ ] 代码有适当注释
- [ ] 函数/类有文档字符串
- [ ] 变量命名清晰
- [ ] 复杂逻辑有说明

## 快速命令

```bash
# 一键检查 (提交前)
make format && make lint && make test

# 快速测试 (开发中)
pytest tests/unit -v --tb=short

# 检查单个文件
black --check src/services/xxx.py
mypy src/services/xxx.py
flake8 src/services/xxx.py
```
