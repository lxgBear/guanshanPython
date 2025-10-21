# 数据库迁移系统实施报告

**实施日期**: 2025-10-17
**版本**: 1.0.0
**状态**: ✅ 已完成

---

## 📋 目录

1. [概述](#概述)
2. [系统架构](#系统架构)
3. [使用指南](#使用指南)
4. [迁移脚本](#迁移脚本)
5. [最佳实践](#最佳实践)
6. [故障排除](#故障排除)

---

## 概述

### 背景

由于系统缺少数据库迁移机制，当数据模型演进时，现有数据无法自动更新，导致：
- 数据不一致问题
- 业务逻辑失败
- 维护成本高

### 解决方案

实施了一套完整的数据库迁移系统，包括:
- ✅ 迁移脚本框架
- ✅ 版本管理机制
- ✅ 自动执行和回滚
- ✅ 迁移状态跟踪

### 核心特性

1. **版本化迁移**: 每个 schema 变更都有唯一版本号
2. **自动发现**: 自动发现并执行待执行的迁移
3. **可回滚**: 支持安全回滚到任意版本
4. **状态跟踪**: 记录所有已应用的迁移
5. **验证机制**: 自动验证迁移结果

---

## 系统架构

### 目录结构

```
guanshanPython/
├── migrations/                    # 迁移系统根目录
│   ├── __init__.py               # 包初始化
│   ├── base_migration.py         # 迁移基类
│   ├── migration_runner.py       # 迁移运行器
│   └── versions/                 # 迁移脚本目录
│       ├── __init__.py
│       └── migration_001_add_is_active_field.py
├── scripts/
│   └── run_migrations.py         # 迁移命令行工具
└── src/
    └── ...
```

### 核心组件

#### 1. BaseMigration (基类)

**文件**: `migrations/base_migration.py`

**职责**:
- 定义迁移接口
- 提供通用功能
- 强制子类实现 upgrade/downgrade

**接口**:
```python
class BaseMigration(ABC):
    @property
    @abstractmethod
    def version(self) -> str:
        """版本号"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """迁移描述"""
        pass

    @abstractmethod
    async def upgrade(self) -> dict:
        """执行迁移"""
        pass

    @abstractmethod
    async def downgrade(self) -> dict:
        """回滚迁移"""
        pass

    async def validate(self) -> bool:
        """验证迁移结果"""
        return True
```

#### 2. MigrationRunner (运行器)

**文件**: `migrations/migration_runner.py`

**职责**:
- 自动发现迁移脚本
- 执行迁移和回滚
- 跟踪迁移状态
- 验证迁移结果

**核心方法**:
```python
class MigrationRunner:
    async def run_migrations(target_version=None) -> dict
    async def rollback_migration(version: str) -> dict
    async def get_migration_status() -> dict
    def discover_migrations() -> List[Type[BaseMigration]]
```

#### 3. 迁移脚本

**文件**: `migrations/versions/migration_XXX_description.py`

**命名规范**:
- `migration_001_add_is_active_field.py`
- 前缀: `migration_`
- 版本号: 3位数字 `001`, `002`, `003`
- 描述: 简短的蛇形命名

**示例**:
```python
class Migration001AddIsActiveField(BaseMigration):
    version = "001"
    description = "为 search_tasks 添加 is_active 字段"

    async def upgrade(self) -> dict:
        result = await self.db.search_tasks.update_many(
            {'is_active': {'$exists': False}},
            {'$set': {'is_active': True}}
        )
        return {'modified_count': result.modified_count}

    async def downgrade(self) -> dict:
        result = await self.db.search_tasks.update_many(
            {},
            {'$unset': {'is_active': ''}}
        )
        return {'modified_count': result.modified_count}

    async def validate(self) -> bool:
        count = await self.db.search_tasks.count_documents(
            {'is_active': {'$exists': False}}
        )
        return count == 0
```

---

## 使用指南

### 查看迁移状态

```bash
python scripts/run_migrations.py status
```

**输出示例**:
```
📊 数据库迁移状态
============================================================

已应用迁移: 1 个
  ✅ 001: 为 search_tasks 添加 is_active 字段
     应用时间: 2025-10-17T13:30:00Z

待执行迁移: 0 个
  (无待执行迁移)
```

### 执行迁移

```bash
# 执行所有待执行的迁移
python scripts/run_migrations.py migrate

# 执行到指定版本的迁移
python scripts/run_migrations.py migrate 002
```

**输出示例**:
```
🚀 开始执行数据库迁移...
============================================================
📋 发现 1 个待执行迁移
🔄 执行迁移: 001 - 为 search_tasks 添加 is_active 字段
✅ 迁移成功: 001
🎉 迁移完成: 执行了 1 个迁移

============================================================
✅ 迁移执行完成
   已执行: 1 个迁移
   已跳过: 0 个迁移

📋 执行详情:
   ✅ 001: 为 search_tasks 添加 is_active 字段
      成功为 15 个任务添加 is_active 字段
```

### 回滚迁移

```bash
python scripts/run_migrations.py rollback 001
```

**输出示例**:
```
🔙 开始回滚迁移: 001
============================================================

============================================================
✅ 迁移回滚成功: 001
   成功移除 15 个任务的 is_active 字段
```

---

## 迁移脚本

### 当前迁移列表

| 版本 | 描述 | 状态 | 应用时间 |
|------|------|------|----------|
| 001 | 为 search_tasks 添加 is_active 字段 | ✅ 已应用 | 2025-10-17 |

### Migration 001: 添加 is_active 字段

**问题**: 旧版本任务缺少 `is_active` 字段，导致无法被调度器加载

**解决方案**: 为所有缺少该字段的任务添加 `is_active: true`

**影响**:
- 修改文档数: 取决于旧任务数量
- 数据迁移时间: <1秒
- 向后兼容: ✅ 是

**验证**:
- 检查是否还有任务缺少 `is_active` 字段
- 验证所有任务的 `is_active` 值为 `True`

---

## 最佳实践

### 创建新迁移

#### 1. 创建迁移文件

```bash
# 文件名格式: migration_XXX_description.py
touch migrations/versions/migration_002_add_priority_field.py
```

#### 2. 实现迁移类

```python
from migrations.base_migration import BaseMigration

class Migration002AddPriorityField(BaseMigration):
    version = "002"
    description = "为 search_tasks 添加 priority 字段"

    async def upgrade(self) -> dict:
        # 实现迁移逻辑
        result = await self.db.search_tasks.update_many(
            {'priority': {'$exists': False}},
            {'$set': {'priority': 'normal'}}
        )
        return {
            'modified_count': result.modified_count,
            'message': f'成功添加 priority 字段到 {result.modified_count} 个任务'
        }

    async def downgrade(self) -> dict:
        # 实现回滚逻辑
        result = await self.db.search_tasks.update_many(
            {},
            {'$unset': {'priority': ''}}
        )
        return {
            'modified_count': result.modified_count,
            'message': f'成功移除 {result.modified_count} 个任务的 priority 字段'
        }

    async def validate(self) -> bool:
        # 实现验证逻辑
        count = await self.db.search_tasks.count_documents(
            {'priority': {'$exists': False}}
        )
        return count == 0
```

#### 3. 测试迁移

```bash
# 1. 查看迁移状态
python scripts/run_migrations.py status

# 2. 执行迁移
python scripts/run_migrations.py migrate 002

# 3. 验证结果
# 检查数据库中的数据是否正确更新

# 4. 测试回滚
python scripts/run_migrations.py rollback 002

# 5. 验证回滚
# 确认数据已恢复到迁移前状态

# 6. 重新执行迁移
python scripts/run_migrations.py migrate 002
```

### 迁移设计原则

#### 1. 向后兼容

- ✅ **好**: 添加可选字段或带默认值的字段
- ✅ **好**: 扩展枚举值（添加新值）
- ❌ **坏**: 删除必需字段
- ❌ **坏**: 改变字段类型

#### 2. 幂等性

迁移应该是幂等的，可以安全地多次执行:

```python
# ✅ 好的实践 - 幂等性
async def upgrade(self) -> dict:
    # 只更新缺少字段的文档
    result = await self.db.tasks.update_many(
        {'new_field': {'$exists': False}},
        {'$set': {'new_field': 'default'}}
    )

# ❌ 坏的实践 - 非幂等
async def upgrade(self) -> dict:
    # 无条件更新所有文档
    result = await self.db.tasks.update_many(
        {},
        {'$set': {'new_field': 'default'}}
    )
```

#### 3. 数据完整性

始终验证迁移结果:

```python
async def validate(self) -> bool:
    # 检查数据完整性
    invalid_count = await self.db.tasks.count_documents({
        '$or': [
            {'new_field': {'$exists': False}},
            {'new_field': None},
            {'new_field': ''}
        ]
    })
    return invalid_count == 0
```

#### 4. 性能考虑

对于大数据集，使用批量操作:

```python
async def upgrade(self) -> dict:
    batch_size = 1000
    skip = 0
    total_modified = 0

    while True:
        tasks = await self.db.tasks.find(
            {'new_field': {'$exists': False}}
        ).skip(skip).limit(batch_size).to_list(batch_size)

        if not tasks:
            break

        # 批量更新
        operations = [
            UpdateOne(
                {'_id': task['_id']},
                {'$set': {'new_field': 'default'}}
            )
            for task in tasks
        ]

        result = await self.db.tasks.bulk_write(operations)
        total_modified += result.modified_count
        skip += batch_size

    return {'modified_count': total_modified}
```

### 部署流程

#### 1. 开发环境测试

```bash
# 1. 创建迁移脚本
# 2. 本地测试
python scripts/run_migrations.py migrate
# 3. 验证结果
# 4. 测试回滚
python scripts/run_migrations.py rollback XXX
# 5. 重新执行
python scripts/run_migrations.py migrate
```

#### 2. 代码审查

- 检查迁移逻辑正确性
- 验证向后兼容性
- 确认回滚机制
- 评估性能影响

#### 3. 生产部署

```bash
# 1. 备份数据库
mongodump --uri="mongodb://..." --out="backup_$(date +%Y%m%d_%H%M%S)"

# 2. 查看待执行迁移
python scripts/run_migrations.py status

# 3. 执行迁移
python scripts/run_migrations.py migrate

# 4. 验证结果
# 检查应用日志、数据库数据

# 5. 如果失败，回滚
python scripts/run_migrations.py rollback XXX

# 6. 恢复数据库（最后手段）
mongorestore --uri="mongodb://..." backup_dir
```

---

## 故障排除

### 常见问题

#### 1. 迁移执行失败

**症状**: 迁移执行时抛出异常

**排查步骤**:
1. 检查错误日志
2. 验证数据库连接
3. 检查数据格式
4. 测试迁移逻辑

**解决方案**:
```bash
# 1. 查看详细错误
python scripts/run_migrations.py migrate 2>&1 | tee migration.log

# 2. 如果部分成功，检查状态
python scripts/run_migrations.py status

# 3. 回滚已执行的迁移
python scripts/run_migrations.py rollback XXX

# 4. 修复迁移脚本后重新执行
python scripts/run_migrations.py migrate
```

#### 2. 迁移状态不一致

**症状**: 数据库显示已应用，但数据未更新

**排查步骤**:
1. 检查 schema_migrations 集合
2. 验证数据是否真的更新
3. 检查迁移验证逻辑

**解决方案**:
```python
# 手动验证
from motor.motor_asyncio import AsyncIOMotorClient
client = AsyncIOMotorClient('mongodb://...')
db = client['intelligent_system']

# 检查迁移记录
await db.schema_migrations.find().to_list(100)

# 检查实际数据
await db.search_tasks.find({'is_active': {'$exists': False}}).to_list(100)

# 如果数据未更新，手动执行迁移逻辑
# 或删除迁移记录重新执行
await db.schema_migrations.delete_one({'version': '001'})
```

#### 3. 回滚失败

**症状**: 回滚操作失败或数据未恢复

**排查步骤**:
1. 检查回滚逻辑
2. 验证数据库状态
3. 检查是否有依赖

**解决方案**:
```bash
# 1. 从备份恢复（最安全）
mongorestore --uri="mongodb://..." backup_dir

# 2. 手动执行回滚逻辑
python -c "
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def manual_rollback():
    client = AsyncIOMotorClient('mongodb://...')
    db = client['intelligent_system']

    # 手动执行回滚操作
    await db.search_tasks.update_many(
        {},
        {'\$unset': {'is_active': ''}}
    )

asyncio.run(manual_rollback())
"
```

### 日志分析

迁移系统使用标准日志格式:

```
[时间] - [模块] - [级别] - [消息]

2025-10-17 13:30:00 - migrations.migration_runner - INFO - ✅ 迁移成功: 001
2025-10-17 13:30:01 - migrations.migration_runner - ERROR - ❌ 迁移失败: 002 - connection timeout
```

---

## 总结

### 实施成果

1. ✅ **迁移系统**: 完整的数据库迁移框架
2. ✅ **版本管理**: 迁移脚本版本控制
3. ✅ **自动化工具**: 命令行工具简化操作
4. ✅ **文档完善**: 使用指南和最佳实践

### 预期收益

1. **数据一致性**: 自动同步 schema 和数据
2. **维护效率**: 减少手动修复成本
3. **可追溯性**: 完整的变更历史记录
4. **风险控制**: 支持安全回滚

### 后续改进

1. **集成到 CI/CD**: 自动执行迁移
2. **监控告警**: 迁移失败自动通知
3. **性能优化**: 大数据集批量处理
4. **测试覆盖**: 迁移脚本单元测试

---

**文档版本**: 1.0.0
**最后更新**: 2025-10-17
**维护人**: DevOps Team
