# NL Search 测试套件

**版本**: v1.0.0-beta
**状态**: 🚧 Phase 1 完成

## 测试结构

```
tests/nl_search/
├── __init__.py                  # 测试模块初始化
├── README.md                    # 本文件
├── test_entities.py             # 实体模型测试
├── test_config.py               # 配置测试
└── test_repository.py           # 仓库层测试 (待实现)
```

## 运行测试

### 运行所有 NL Search 测试

```bash
pytest tests/nl_search/ -v
```

### 运行特定测试文件

```bash
# 测试实体模型
pytest tests/nl_search/test_entities.py -v

# 测试配置
pytest tests/nl_search/test_config.py -v
```

### 查看测试覆盖率

```bash
pytest tests/nl_search/ \
  --cov=src/core/domain/entities/nl_search \
  --cov=src/services/nl_search \
  --cov-report=html \
  --cov-report=term
```

覆盖率报告将生成在 `htmlcov/` 目录。

## 测试内容

### ✅ test_entities.py

测试 NL Search 实体模型:

- `TestNLSearchLog`: 测试 NLSearchLog 实体
  - 基础创建
  - LLM 分析结果
  - 属性方法 (keywords, intent, confidence)
  - 字符串表示

- `TestSearchStatus`: 测试 SearchStatus 枚举
  - 状态值
  - 验证方法

- `TestNLSearchLogValidation`: 测试实体验证
  - 字段验证
  - 长度限制

**测试覆盖率目标**: 100%

### ✅ test_config.py

测试 NL Search 配置:

- `TestNLSearchConfig`: 测试配置类
  - 默认值
  - 验证方法 (LLM, GPT-5)
  - 敏感信息隐藏
  - 全局配置实例

- `TestNLSearchConfigValidation`: 测试配置验证
  - 参数范围验证
  - 边界条件测试

**测试覆盖率目标**: >85%

### 🚧 test_repository.py (Phase 1 待实现)

测试仓库层 (需要 MariaDB 连接):

- `TestNLSearchLogRepository`: 测试仓库操作
  - CRUD 操作
  - 查询和搜索
  - 分页
  - 数据清理

**测试覆盖率目标**: >90%

**注意**: 仓库层测试需要数据库连接，建议使用测试数据库。

## Phase 1 验收标准

- [x] test_entities.py 所有测试通过
- [x] test_config.py 所有测试通过
- [ ] test_repository.py 待实现 (需要数据库)
- [ ] 整体覆盖率 >85%

## 下一步

Phase 2 将添加:
- LLM 处理器测试 (test_llm_processor.py)
- GPT-5 适配器测试 (test_gpt5_adapter.py)
- 集成测试套件

---

**最后更新**: 2025-11-14
**维护者**: Backend Team
