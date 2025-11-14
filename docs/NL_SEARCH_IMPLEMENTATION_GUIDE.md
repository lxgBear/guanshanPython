# 自然语言搜索 - 模块化实现指南

**版本**: v1.0.0-beta
**状态**: 🚧 实施指南
**目标读者**: 后端开发工程师
**前置文档**: [模块化设计文档](NL_SEARCH_MODULAR_DESIGN.md)

---

## 📋 实施前准备

### 1. 环境准备

确保以下环境已就绪：

```bash
# Python 版本
python --version  # ≥ 3.9

# 依赖包安装
pip install openai  # LLM API 客户端
pip install pydantic  # 配置管理
pip install pytest pytest-asyncio pytest-cov  # 测试框架
```

### 2. API Key 准备

需要准备以下 API Keys：

- OpenAI API Key (用于 LLM 处理)
- GPT-5 Search API Key (用于搜索)
- Firecrawl API Key (已有)

### 3. 功能开关确认

**重要**：默认关闭功能开关！

```bash
# .env 文件
NL_SEARCH_ENABLED=false  # 🚨 默认必须为 false
```

---

## Phase 1: 基础架构搭建

### 步骤 1.1: 创建目录结构

```bash
# 执行以下命令创建目录
mkdir -p src/services/nl_search
mkdir -p src/core/domain/entities/nl_search
mkdir -p tests/nl_search
```

**目录结构验证**：

```
src/
├── services/
│   └── nl_search/
│       ├── __init__.py                    # 空文件
│       ├── config.py                      # 待创建
│       ├── nl_search_service.py           # 待创建
│       ├── llm_processor.py               # 待创建
│       ├── gpt5_search_adapter.py         # 待创建
│       └── content_enricher.py            # 待创建
├── core/domain/entities/
│   └── nl_search/
│       ├── __init__.py                    # 待创建
│       ├── nl_search_log.py               # 待创建
│       ├── nl_user_selection.py           # 待创建
│       └── enums.py                       # 待创建
└── tests/
    └── nl_search/
        ├── __init__.py                    # 空文件
        ├── test_llm_processor.py          # 待创建
        ├── test_gpt5_adapter.py           # 待创建
        └── test_nl_search_service.py      # 待创建
```

### 步骤 1.2: 定义实体模型

**文件**: `src/core/domain/entities/nl_search/nl_search_log.py`

```python
"""
自然语言搜索记录实体（简化版）
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NLSearchLog(BaseModel):
    """自然语言搜索记录（简化版）"""

    id: Optional[int] = Field(None, description="主键ID")
    query_text: str = Field(..., description="原始用户输入", max_length=1000)
    llm_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="大模型解析结构（关键词、实体、时间范围等）"
    )
    created_at: Optional[datetime] = Field(None, description="创建时间")

    class Config:
        from_attributes = True  # SQLAlchemy ORM 支持
        json_schema_extra = {
            "example": {
                "id": 123456,
                "query_text": "最近有哪些AI技术突破",
                "llm_analysis": {
                    "intent": "technology_news",
                    "keywords": ["AI", "技术突破", "2024"],
                    "entities": [
                        {"type": "technology", "value": "AI"}
                    ],
                    "time_range": {
                        "type": "recent",
                        "from": "2024-01-01",
                        "to": "2024-12-31"
                    },
                    "confidence": 0.95
                },
                "created_at": "2024-11-10T10:00:00"
            }
        }
```

**文件**: `src/core/domain/entities/nl_search/__init__.py`

```python
"""
NL Search 实体模块（简化版）
"""
from .nl_search_log import NLSearchLog

__all__ = [
    "NLSearchLog",
]
```

### 步骤 1.3: 实现仓库层（简化版）

**文件**: `src/infrastructure/database/nl_search_repositories.py`

```python
"""
NL Search 数据仓库（简化版 - MySQL）
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from src.infrastructure.database.connection import get_database
from src.core.domain.entities.nl_search import NLSearchLog


class NLSearchLogRepository:
    """自然语言搜索记录仓库（简化版）"""

    def __init__(self):
        self.db = get_database()  # 获取数据库连接

    async def create(
        self,
        query_text: str,
        llm_analysis: Optional[Dict[str, Any]] = None
    ) -> int:
        """创建搜索记录"""
        query = """
        INSERT INTO nl_search_logs (query_text, llm_analysis, created_at)
        VALUES (:query_text, :llm_analysis, NOW())
        """

        llm_analysis_json = json.dumps(llm_analysis) if llm_analysis else None

        result = await self.db.execute(
            query=query,
            values={
                "query_text": query_text,
                "llm_analysis": llm_analysis_json
            }
        )
        return result  # 返回插入的 ID

    async def get_by_id(self, log_id: int) -> Optional[NLSearchLog]:
        """根据ID获取搜索记录"""
        query = """
        SELECT id, query_text, llm_analysis, created_at
        FROM nl_search_logs
        WHERE id = :log_id
        """

        row = await self.db.fetch_one(query=query, values={"log_id": log_id})

        if not row:
            return None

        # 解析 JSON 字段
        llm_analysis = json.loads(row["llm_analysis"]) if row["llm_analysis"] else None

        return NLSearchLog(
            id=row["id"],
            query_text=row["query_text"],
            llm_analysis=llm_analysis,
            created_at=row["created_at"]
        )

    async def update_llm_analysis(
        self,
        log_id: int,
        llm_analysis: Dict[str, Any]
    ) -> bool:
        """更新 LLM 解析结果"""
        query = """
        UPDATE nl_search_logs
        SET llm_analysis = :llm_analysis
        WHERE id = :log_id
        """

        result = await self.db.execute(
            query=query,
            values={
                "log_id": log_id,
                "llm_analysis": json.dumps(llm_analysis)
            }
        )
        return result > 0

    async def get_recent(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> List[NLSearchLog]:
        """获取最近的搜索记录"""
        query = """
        SELECT id, query_text, llm_analysis, created_at
        FROM nl_search_logs
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """

        rows = await self.db.fetch_all(
            query=query,
            values={"limit": limit, "offset": offset}
        )

        logs = []
        for row in rows:
            llm_analysis = json.loads(row["llm_analysis"]) if row["llm_analysis"] else None
            logs.append(NLSearchLog(
                id=row["id"],
                query_text=row["query_text"],
                llm_analysis=llm_analysis,
                created_at=row["created_at"]
            ))

        return logs

    async def search_by_keyword(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[NLSearchLog]:
        """根据关键词搜索（MySQL JSON 查询）"""
        query = """
        SELECT id, query_text, llm_analysis, created_at
        FROM nl_search_logs
        WHERE JSON_CONTAINS(
            llm_analysis->'$.keywords',
            JSON_QUOTE(:keyword)
        )
        OR query_text LIKE :query_pattern
        ORDER BY created_at DESC
        LIMIT :limit
        """

        rows = await self.db.fetch_all(
            query=query,
            values={
                "keyword": keyword,
                "query_pattern": f"%{keyword}%",
                "limit": limit
            }
        )

        logs = []
        for row in rows:
            llm_analysis = json.loads(row["llm_analysis"]) if row["llm_analysis"] else None
            logs.append(NLSearchLog(
                id=row["id"],
                query_text=row["query_text"],
                llm_analysis=llm_analysis,
                created_at=row["created_at"]
            ))

        return logs

    async def delete_old_records(self, days: int = 30) -> int:
        """删除旧记录"""
        query = """
        DELETE FROM nl_search_logs
        WHERE created_at < DATE_SUB(NOW(), INTERVAL :days DAY)
        """

        result = await self.db.execute(
            query=query,
            values={"days": days}
        )
        return result  # 返回删除的行数
```

### 步骤 1.5: 配置功能开关

**文件**: `src/services/nl_search/config.py`

```python
"""
NL Search 功能配置
"""
from pydantic_settings import BaseSettings
from typing import Optional


class NLSearchConfig(BaseSettings):
    """NL Search 功能配置"""

    # 功能开关（默认关闭！）
    enabled: bool = False

    # LLM 配置
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 500

    # GPT-5 搜索配置
    gpt5_search_api_key: Optional[str] = None
    gpt5_max_results: int = 10

    # Scrape 配置
    scrape_timeout: int = 30
    scrape_max_concurrent: int = 3

    # 业务配置
    max_results_per_query: int = 20
    enable_auto_scrape: bool = True

    # 性能配置
    query_timeout: int = 30  # 秒
    cache_ttl: int = 3600    # 缓存时间（秒）

    class Config:
        env_prefix = "NL_SEARCH_"
        env_file = ".env"
        extra = "ignore"


# 全局配置实例
nl_search_config = NLSearchConfig()
```

### 步骤 1.4: 创建数据库表和索引脚本

**文件**: `scripts/create_nl_search_tables.sql`

```sql
-- ===================================================================
-- NL Search 数据表创建脚本（简化版）
-- ===================================================================

-- 1. 创建 nl_search_logs 表
CREATE TABLE IF NOT EXISTS nl_search_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',
  query_text TEXT NOT NULL COMMENT '原始用户输入',
  llm_analysis JSON NULL COMMENT '大模型解析结构（关键词、实体、时间范围等）',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

  -- 索引
  INDEX idx_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自然语言搜索记录表（简化版）';

-- 2. 可选：扩展 search_results 表（如需关联）
-- ALTER TABLE search_results
-- ADD COLUMN nl_search_log_id BIGINT NULL COMMENT '关联的NL搜索记录ID',
-- ADD INDEX idx_nl_search_log (nl_search_log_id);

-- 3. 可选：创建关联表
-- CREATE TABLE IF NOT EXISTS nl_search_result_relations (
--   id BIGINT AUTO_INCREMENT PRIMARY KEY,
--   nl_search_log_id BIGINT NOT NULL COMMENT 'NL搜索记录ID',
--   result_id BIGINT NOT NULL COMMENT '搜索结果ID',
--   result_type ENUM('search_result', 'news_result') DEFAULT 'search_result',
--   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
--   INDEX idx_log (nl_search_log_id),
--   INDEX idx_result (result_id, result_type),
--   UNIQUE KEY uk_log_result (nl_search_log_id, result_id, result_type)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ===================================================================
-- 验证表创建
-- ===================================================================
SELECT
  TABLE_NAME,
  TABLE_COMMENT,
  CREATE_TIME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'nl_search_logs';

-- 验证索引
SHOW INDEX FROM nl_search_logs;
```

**Python 脚本执行 SQL**：

**文件**: `scripts/create_nl_search_tables.py`

```python
"""
创建 NL Search 数据表
"""
import asyncio
from pathlib import Path

from src.infrastructure.database.connection import get_database


async def create_nl_search_tables():
    """创建 NL Search 相关表"""
    db = get_database()

    # 读取 SQL 脚本
    sql_file = Path(__file__).parent / "create_nl_search_tables.sql"
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # 分割并执行 SQL 语句
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]

    for statement in statements:
        # 跳过注释行
        if statement.startswith('--') or statement.startswith('SELECT') or statement.startswith('SHOW'):
            continue

        try:
            await db.execute(statement)
            print(f"✅ 执行成功: {statement[:50]}...")
        except Exception as e:
            print(f"❌ 执行失败: {e}")
            print(f"   SQL: {statement[:100]}...")

    print("\n🎉 数据表创建完成！")


if __name__ == "__main__":
    asyncio.run(create_nl_search_tables())
```

**运行表创建**：

```bash
# 方式1：直接执行 SQL 文件
mysql -u username -p database_name < scripts/create_nl_search_tables.sql

# 方式2：通过 Python 脚本
python scripts/create_nl_search_tables.py
```

### 步骤 1.5: 编写基础测试

**文件**: `tests/nl_search/test_entities.py`

```python
"""
测试 NL Search 实体（简化版）
"""
import pytest
from datetime import datetime

from src.core.domain.entities.nl_search import NLSearchLog


class TestNLSearchLog:
    def test_create_log(self):
        """测试创建搜索记录"""
        log = NLSearchLog(
            query_text="最近有哪些AI技术突破"
        )

        assert log.query_text == "最近有哪些AI技术突破"
        assert log.llm_analysis is None
        assert log.id is None

    def test_create_log_with_analysis(self):
        """测试创建包含分析结果的记录"""
        llm_analysis = {
            "intent": "technology_news",
            "keywords": ["AI", "技术突破"],
            "confidence": 0.95
        }

        log = NLSearchLog(
            query_text="AI技术",
            llm_analysis=llm_analysis
        )

        assert log.query_text == "AI技术"
        assert log.llm_analysis["intent"] == "technology_news"
        assert len(log.llm_analysis["keywords"]) == 2

    def test_log_with_id(self):
        """测试包含 ID 的记录"""
        log = NLSearchLog(
            id=123456,
            query_text="测试查询",
            created_at=datetime.now()
        )

        assert log.id == 123456
        assert log.query_text == "测试查询"
        assert log.created_at is not None
```

**文件**: `tests/nl_search/test_repository.py`

```python
"""
测试 NL Search 仓库层
"""
import pytest
from datetime import datetime

from src.infrastructure.database.nl_search_repositories import NLSearchLogRepository


@pytest.fixture
async def repository():
    """创建仓库实例"""
    return NLSearchLogRepository()


@pytest.mark.asyncio
class TestNLSearchLogRepository:
    async def test_create_search_log(self, repository):
        """测试创建搜索记录"""
        query_text = "最近有哪些AI技术突破"
        llm_analysis = {
            "intent": "technology_news",
            "keywords": ["AI", "技术突破"]
        }

        log_id = await repository.create(
            query_text=query_text,
            llm_analysis=llm_analysis
        )

        assert log_id > 0

    async def test_get_by_id(self, repository):
        """测试根据ID获取记录"""
        # 先创建记录
        log_id = await repository.create(
            query_text="测试查询"
        )

        # 获取记录
        log = await repository.get_by_id(log_id)

        assert log is not None
        assert log.id == log_id
        assert log.query_text == "测试查询"

    async def test_update_llm_analysis(self, repository):
        """测试更新 LLM 分析结果"""
        # 创建记录
        log_id = await repository.create(
            query_text="测试查询"
        )

        # 更新分析结果
        llm_analysis = {
            "intent": "test",
            "keywords": ["测试"]
        }
        success = await repository.update_llm_analysis(
            log_id=log_id,
            llm_analysis=llm_analysis
        )

        assert success is True

        # 验证更新
        log = await repository.get_by_id(log_id)
        assert log.llm_analysis["intent"] == "test"

    async def test_get_recent(self, repository):
        """测试获取最近记录"""
        # 创建多条记录
        for i in range(5):
            await repository.create(query_text=f"查询 {i}")

        # 获取最近3条
        logs = await repository.get_recent(limit=3)

        assert len(logs) <= 3
        # 验证按时间倒序
        if len(logs) > 1:
            assert logs[0].created_at >= logs[1].created_at
```

**运行测试**：

```bash
# 运行所有 NL Search 测试
pytest tests/nl_search/ -v

# 运行特定测试文件
pytest tests/nl_search/test_entities.py -v
pytest tests/nl_search/test_repository.py -v

# 查看测试覆盖率
pytest tests/nl_search/ --cov=src/core/domain/entities/nl_search --cov=src/infrastructure/database/nl_search_repositories --cov-report=html
```

### ✅ Phase 1 验收标准

完成以下检查：

- [ ] 目录结构完整创建
- [ ] 所有实体模型定义完成
- [ ] 仓库层实现完成
- [ ] 配置类定义完成
- [ ] 数据库索引创建成功
- [ ] 基础测试通过

---

## Phase 2-8: 后续实施

**完整的实施步骤请参考**:
- [模块化设计文档 - 实现计划章节](NL_SEARCH_MODULAR_DESIGN.md#实现计划)

**关键提醒**:

1. **功能开关**: 始终保持 `NL_SEARCH_ENABLED=false`，直到所有测试通过
2. **代码隔离**: 不要在现有模块中导入 NL Search 代码
3. **测试先行**: 每个阶段完成后立即编写测试
4. **文档同步**: 及时更新 API 文档和技术文档
5. **代码审查**: 每个 Phase 完成后进行代码审查

---

## 开发规范

### 命名规范

```python
# ✅ 正确
class NLSearchService:
    """NL Search 核心服务"""
    pass

async def create_nl_search_query(...):
    """创建自然语言搜索"""
    pass

# ❌ 错误
class NaturalLanguageSearchService:  # 太长
    pass

async def create_search(...):  # 不明确
    pass
```

### 导入规范

```python
# ✅ 正确：NL Search 可以导入现有模块
from src.infrastructure.crawlers.firecrawl_adapter import FirecrawlAdapter
from src.core.domain.entities.search_result import SearchResult

# ❌ 错误：现有模块不应导入 NL Search
# 在现有服务中：
from src.services.nl_search.nl_search_service import NLSearchService  # 禁止！
```

### 错误处理规范

```python
# ✅ 正确：完善的错误处理
try:
    result = await llm_processor.parse_query(query_text)
except Exception as e:
    logger.error(f"LLM 处理失败: {e}", exc_info=True)
    # 更新状态为失败
    await log_repo.update_status(
        log_id,
        SearchStatus.FAILED,
        error_message=str(e)
    )
    # 返回友好错误信息
    raise HTTPException(
        status_code=500,
        detail="查询处理失败，请稍后重试"
    )

# ❌ 错误：不处理错误
result = await llm_processor.parse_query(query_text)  # 可能抛出异常
```

---

## 测试规范

### 单元测试覆盖率要求

- 实体类: 100%
- 仓库类: >90%
- 服务类: >85%
- 工具类: >90%

### 测试示例

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestNLSearchService:
    @pytest.fixture
    def service(self):
        """创建服务实例"""
        return NLSearchService()

    @pytest.mark.asyncio
    async def test_create_search_success(self, service):
        """测试成功创建搜索"""
        # 准备测试数据
        user_id = "test_user"
        query_text = "AI技术"

        # Mock 外部依赖
        with patch.object(service.llm_processor, 'parse_query') as mock_parse:
            mock_parse.return_value = {"intent": "tech_news"}

            # 执行测试
            log_id = await service.create_search(user_id, query_text)

            # 验证结果
            assert log_id is not None
            mock_parse.assert_called_once_with(query_text)

    @pytest.mark.asyncio
    async def test_create_search_with_llm_error(self, service):
        """测试 LLM 错误处理"""
        user_id = "test_user"
        query_text = "测试查询"

        # Mock LLM 抛出异常
        with patch.object(service.llm_processor, 'parse_query') as mock_parse:
            mock_parse.side_effect = Exception("API Error")

            # 验证异常被正确处理
            with pytest.raises(Exception):
                await service.create_search(user_id, query_text)
```

---

## 部署检查清单

### 部署前检查

- [ ] 所有单元测试通过（覆盖率 >85%）
- [ ] 所有集成测试通过
- [ ] 功能开关默认为 `false`
- [ ] API 文档已更新
- [ ] 数据库索引已创建
- [ ] 配置文件模板已准备
- [ ] 监控告警已配置
- [ ] 回滚方案已确认

### 部署步骤

1. **代码部署**
   ```bash
   git pull origin main
   pip install -r requirements.txt
   ```

2. **数据库迁移**
   ```bash
   python scripts/create_nl_search_indexes.py
   ```

3. **配置检查**
   ```bash
   # 确认功能开关为关闭
   grep "NL_SEARCH_ENABLED" .env
   # 应该输出: NL_SEARCH_ENABLED=false
   ```

4. **重启服务**
   ```bash
   supervisorctl restart gunicorn
   ```

5. **健康检查**
   ```bash
   curl http://localhost:8000/api/v1/nl-search/status
   # 应该返回: {"enabled": false, "version": "1.0.0-beta"}
   ```

---

## 常见问题

### Q1: 如何启用功能？

**A**: 修改 `.env` 文件，设置 `NL_SEARCH_ENABLED=true`，然后重启服务。

### Q2: 如何验证功能隔离？

**A**: 运行隔离测试：
```bash
pytest tests/nl_search/test_isolation.py -v
```

### Q3: 如何回滚？

**A**: 设置 `NL_SEARCH_ENABLED=false`，重启服务即可。

### Q4: 数据如何清理？

**A**: 执行清理脚本：
```bash
python scripts/cleanup_nl_search_data.py
```

---

## 附录

### A. 完整代码示例

完整的代码示例请查看：


- `src/services/nl_search/` - 服务层代码
- `src/core/domain/entities/nl_search/` - 实体层代码
- `tests/nl_search/` - 测试代码

### B. 参考文档

- [模块化设计文档](NL_SEARCH_MODULAR_DESIGN.md)
- [API 文档](API_USAGE_GUIDE_V2.md)
- [Firecrawl 集成文档](FIRECRAWL_MAP_API_GUIDE.md)

---

**文档状态**: ✅ 已完成
**最后更新**: 2025-11-10
**维护者**: Backend Team
