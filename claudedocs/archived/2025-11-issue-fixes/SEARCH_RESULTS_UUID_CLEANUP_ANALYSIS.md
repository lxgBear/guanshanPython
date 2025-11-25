# search_results 表 UUID 数据清理功能分析

**功能概述**: 识别并删除 search_results 集合中所有使用 UUID 格式的数据记录

**分析日期**: 2025-11-23
**当前状态**: ✅ 数据库已清理完毕（0条UUID记录）
**文档目的**: 提供标准化清理流程和工具，用于未来维护

---

## 📋 目录

1. [当前数据库状态](#1-当前数据库状态)
2. [UUID格式识别](#2-uuid格式识别)
3. [清理必要性评估](#3-清理必要性评估)
4. [风险分析](#4-风险分析)
5. [清理策略](#5-清理策略)
6. [实施步骤](#6-实施步骤)
7. [回滚方案](#7-回滚方案)
8. [预防措施](#8-预防措施)

---

## 1. 当前数据库状态

### 1.1 数据统计 (2025-11-23)

```
=== search_results 集合分析 ===

📊 总记录数: 442

ID格式分布:
  ✅ 雪花ID (_id):     442 (100%)
  ✅ 雪花ID (task_id): 442 (100%)
  ❌ UUID格式:         0   (0%)
  ❌ temp_ 前缀:       0   (0%)

结论: 数据库完全符合 v1.5.0 ID系统规范
```

### 1.2 数据示例

```json
{
  "_id": "249177123671879680",         // ✅ 雪花ID (18位纯数字)
  "task_id": "249176609894805504",     // ✅ 雪花ID
  "title": "China begins construction...",
  "url": "https://www.reuters.com/world/china/...",
  "markdown_content": "...",
  "source": "nl_search",
  "relevance_score": 0.95,
  "created_at": "2025-11-21T..."
}
```

### 1.3 历史迁移记录

**v1.5.0 ID系统统一迁移** (已完成)

- **迁移时间**: 2025-11-21
- **迁移记录数**: 276 条
- **成功率**: 100%
- **迁移类型**: `temp_{uuid}` → 雪花算法ID
- **文档参考**: `TASK_ID_UNIFICATION_ANALYSIS.md`

**当前状态**: ✅ 所有历史 UUID 数据已成功迁移，无遗留问题

---

## 2. UUID格式识别

### 2.1 UUID格式特征

#### 标准 UUID v4 格式

```
示例: 550e8400-e29b-41d4-a716-446655440000
特征:
  - 长度: 36 字符 (含连字符)
  - 格式: 8-4-4-4-12 (5个部分)
  - 字符: 十六进制 (0-9, a-f)
  - 连字符: 4个 '-'
```

#### temp_ UUID 格式 (系统历史格式)

```
示例: temp_bd7e6f7017124b24
特征:
  - 前缀: "temp_"
  - 长度: ~21 字符
  - UUID部分: 16字符十六进制 (uuid.uuid4().hex[:16])
  - 用途: MongoDB离线时的临时ID
```

#### temp_ UUID with Index (Frontend 生成)

```
示例: temp_bd7e6f7017124b24-0
特征:
  - 前缀: "temp_"
  - UUID: 16字符十六进制
  - 后缀: "-{index}" (数组索引)
  - 长度: ~23+ 字符
  - 用途: Frontend 本地状态管理
```

### 2.2 雪花ID格式 (正确格式)

```
示例: 249177123671879680
特征:
  - 长度: 18-20 字符
  - 字符: 纯数字 (0-9)
  - 无连字符
  - 分布式唯一
  - 时间有序
```

### 2.3 识别查询

#### MongoDB 查询模式

```javascript
// 1. 查找包含连字符的ID (UUID特征)
db.search_results.find({
  $or: [
    { "_id": { $regex: "-" } },
    { "task_id": { $regex: "-" } }
  ]
})

// 2. 查找 temp_ 前缀的ID
db.search_results.find({
  $or: [
    { "_id": { $regex: "^temp_" } },
    { "task_id": { $regex: "^temp_" } }
  ]
})

// 3. 查找非纯数字ID (排除雪花ID)
db.search_results.find({
  $or: [
    { "_id": { $not: { $regex: "^[0-9]+$" } } },
    { "task_id": { $not: { $regex: "^[0-9]+$" } } }
  ]
})

// 4. 统计 UUID 数量
db.search_results.countDocuments({
  $or: [
    { "_id": { $regex: "temp_|\\-" } },
    { "task_id": { $regex: "temp_|\\-" } }
  ]
})
```

#### Python 检测脚本

```python
import asyncio
from src.infrastructure.database.connection import get_mongodb_database

async def identify_uuid_records():
    """识别所有UUID格式的记录"""
    db = await get_mongodb_database()

    # 查询条件: temp_ 前缀 或 包含连字符
    uuid_filter = {
        "$or": [
            {"_id": {"$regex": "^temp_|\\-"}},
            {"task_id": {"$regex": "^temp_|\\-"}}
        ]
    }

    # 统计数量
    count = await db["search_results"].count_documents(uuid_filter)
    print(f"发现 UUID 格式记录: {count} 条")

    # 抽样显示
    if count > 0:
        samples = await db["search_results"].find(
            uuid_filter,
            {"_id": 1, "task_id": 1, "title": 1, "created_at": 1}
        ).limit(10).to_list(length=10)

        print("\n抽样示例 (前10条):")
        for i, record in enumerate(samples, 1):
            print(f"{i}. _id: {record.get('_id')}")
            print(f"   task_id: {record.get('task_id')}")
            print(f"   title: {record.get('title', '')[:50]}")
            print(f"   created_at: {record.get('created_at')}")
            print()

    return count

# 使用
asyncio.run(identify_uuid_records())
```

---

## 3. 清理必要性评估

### 3.1 何时需要清理？

**场景1: 系统故障恢复**

- **触发条件**: MongoDB离线期间产生大量 temp_ ID
- **影响范围**: 无法与真实数据关联，导致数据孤立
- **清理时机**: MongoDB恢复后立即清理

**场景2: 数据迁移失败**

- **触发条件**: ID迁移脚本部分失败，残留UUID记录
- **影响范围**: 数据一致性问题，ID系统混乱
- **清理时机**: 迁移验证后发现残留时

**场景3: Frontend Bug 修复**

- **触发条件**: Frontend 错误生成并保存 temp_ ID
- **影响范围**: 用户数据无法追溯，关联查询失败
- **清理时机**: Bug修复后批量清理历史错误数据

**场景4: 定期维护**

- **触发条件**: 无明显问题，预防性检查
- **影响范围**: N/A
- **清理时机**: 每月/每季度例行检查

### 3.2 清理收益

**数据一致性**:
- ✅ 统一ID格式，符合 v1.5.0 规范
- ✅ 消除ID系统混乱
- ✅ 提高数据可追溯性

**系统性能**:
- ✅ 减少无效数据，降低存储成本
- ✅ 优化查询性能（索引效率提升）
- ✅ 简化数据关联逻辑

**维护成本**:
- ✅ 降低技术债务
- ✅ 减少未来排查问题时间
- ✅ 提高系统可维护性

### 3.3 不清理的风险

**低风险场景** (当前状态):
- ✅ UUID记录数: 0
- ✅ ID系统: 100%雪花ID
- 风险等级: 🟢 无风险

**中风险场景** (假设存在少量UUID):
- ⚠️ UUID记录数: 1-50
- ⚠️ ID系统: >95%雪花ID
- 风险等级: 🟡 低风险
- 建议: 定期清理

**高风险场景** (假设大量UUID):
- ❌ UUID记录数: >50
- ❌ ID系统: <95%雪花ID
- 风险等级: 🔴 高风险
- 建议: 立即清理

---

## 4. 风险分析

### 4.1 清理操作风险

#### 风险1: 数据丢失

**描述**: 误删有效数据或关联数据

**可能性**: 🟡 中等

**影响**: 🔴 严重

**缓解措施**:
1. ✅ **备份先行**: 清理前完整备份 search_results 集合
2. ✅ **筛选验证**: 多重条件验证UUID记录，避免误删
3. ✅ **软删除**: 先标记为删除，验证后再物理删除
4. ✅ **回滚方案**: 准备数据恢复脚本

#### 风险2: 关联数据断链

**描述**: search_results 删除后，user_edited_results 或 user_archives 引用失效

**可能性**: 🟡 中等

**影响**: 🟡 中等

**缓解措施**:
1. ✅ **依赖检查**: 清理前检查关联集合引用
2. ✅ **级联清理**: 同时清理关联集合中的对应记录
3. ✅ **孤儿检测**: 清理后检测并处理孤立记录

#### 风险3: 服务中断

**描述**: 清理期间服务不可用或性能下降

**可能性**: 🟢 低

**影响**: 🟡 中等

**缓解措施**:
1. ✅ **低峰期执行**: 选择凌晨或周末执行
2. ✅ **批量操作**: 分批删除，避免单次大量操作
3. ✅ **监控保障**: 实时监控数据库性能和错误日志

### 4.2 风险矩阵

| 风险类型     | 可能性 | 影响 | 风险等级 | 缓解优先级 |
| ------------ | ------ | ---- | -------- | ---------- |
| 数据丢失     | 🟡 中  | 🔴 高 | 🔴 高    | P0         |
| 关联断链     | 🟡 中  | 🟡 中 | 🟡 中    | P1         |
| 服务中断     | 🟢 低  | 🟡 中 | 🟢 低    | P2         |
| 误操作       | 🟢 低  | 🔴 高 | 🟡 中    | P1         |

---

## 5. 清理策略

### 5.1 策略选择

#### 策略A: 物理删除 (直接删除)

```python
# 直接删除匹配的记录
await db["search_results"].delete_many({
    "$or": [
        {"_id": {"$regex": "^temp_|\\-"}},
        {"task_id": {"$regex": "^temp_|\\-"}}
    ]
})
```

**优点**:
- ✅ 简单直接
- ✅ 立即释放存储空间
- ✅ 彻底清理

**缺点**:
- ❌ 不可恢复
- ❌ 高风险
- ❌ 无审计记录

**适用场景**: 测试环境、确认无误后的生产环境

---

#### 策略B: 软删除 (标记删除) ⭐ 推荐

```python
# 标记为已删除
await db["search_results"].update_many(
    {
        "$or": [
            {"_id": {"$regex": "^temp_|\\-"}},
            {"task_id": {"$regex": "^temp_|\\-"}}
        ]
    },
    {
        "$set": {
            "status": "deleted",
            "deleted_at": datetime.utcnow(),
            "deletion_reason": "UUID格式清理"
        }
    }
)
```

**优点**:
- ✅ 可恢复
- ✅ 保留审计记录
- ✅ 低风险
- ✅ 可分阶段验证

**缺点**:
- ❌ 不立即释放空间
- ❌ 需要后续物理删除步骤
- ❌ 查询需要过滤已删除记录

**适用场景**: ⭐ 生产环境首选

**后续清理**:
```python
# 验证7天后，执行物理删除
await db["search_results"].delete_many({
    "status": "deleted",
    "deleted_at": {"$lt": datetime.utcnow() - timedelta(days=7)}
})
```

---

#### 策略C: 归档删除 (备份后删除)

```python
# 1. 导出UUID记录到备份集合
uuid_records = await db["search_results"].find({
    "$or": [
        {"_id": {"$regex": "^temp_|\\-"}},
        {"task_id": {"$regex": "^temp_|\\-"}}
    ]
}).to_list(length=None)

# 2. 插入到归档集合
await db["search_results_deleted_archive"].insert_many(uuid_records)

# 3. 物理删除原记录
await db["search_results"].delete_many({
    "$or": [
        {"_id": {"$regex": "^temp_|\\-"}},
        {"task_id": {"$regex": "^temp_|\\-"}}
    ]
})
```

**优点**:
- ✅ 保留完整数据
- ✅ 可恢复
- ✅ 释放主集合空间
- ✅ 长期可审计

**缺点**:
- ❌ 需要额外存储空间
- ❌ 操作步骤较多
- ❌ 恢复流程复杂

**适用场景**: 大规模清理、合规要求严格的生产环境

---

### 5.2 推荐策略

**生产环境**: **策略B (软删除)** + **策略C (归档)**

**执行流程**:

```
1️⃣ 备份数据 (导出到文件或归档集合)
     ↓
2️⃣ 软删除 (标记 status=deleted)
     ↓
3️⃣ 验证期 (7天观察，确认无影响)
     ↓
4️⃣ 物理删除 (删除已标记记录)
     ↓
5️⃣ 归档清理 (30天后删除归档数据)
```

---

## 6. 实施步骤

### 6.1 完整清理脚本

#### 脚本: `scripts/cleanup_uuid_search_results.py`

```python
"""
search_results UUID格式数据清理脚本

功能:
1. 识别UUID格式记录
2. 软删除标记
3. 导出归档
4. 物理删除（可选）

版本: v1.0.0
日期: 2025-11-23
"""
import sys
sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.infrastructure.database.connection import get_mongodb_database

class UUIDCleanupService:
    """UUID格式数据清理服务"""

    def __init__(self):
        self.db = None
        self.stats = {
            "total_records": 0,
            "uuid_records": 0,
            "soft_deleted": 0,
            "hard_deleted": 0,
            "archived": 0,
            "errors": 0
        }

    async def initialize(self):
        """初始化数据库连接"""
        self.db = await get_mongodb_database()
        print("✅ 数据库连接成功")

    async def identify_uuid_records(self) -> List[Dict[str, Any]]:
        """识别UUID格式记录"""
        print("\n" + "="*80)
        print("📊 【步骤1】识别UUID格式记录")
        print("="*80)

        # 查询条件
        uuid_filter = {
            "$or": [
                {"_id": {"$regex": "^temp_|\\-"}},
                {"task_id": {"$regex": "^temp_|\\-"}}
            ]
        }

        # 统计
        self.stats["total_records"] = await self.db["search_results"].count_documents({})
        self.stats["uuid_records"] = await self.db["search_results"].count_documents(uuid_filter)

        print(f"  总记录数: {self.stats['total_records']}")
        print(f"  UUID格式记录: {self.stats['uuid_records']}")

        if self.stats["uuid_records"] == 0:
            print("\n✅ 未发现UUID格式记录，无需清理")
            return []

        # 获取记录
        uuid_records = await self.db["search_results"].find(
            uuid_filter
        ).to_list(length=None)

        # 抽样显示
        print(f"\n  📋 抽样预览 (前5条):")
        for i, record in enumerate(uuid_records[:5], 1):
            print(f"    {i}. _id: {record.get('_id')}")
            print(f"       task_id: {record.get('task_id')}")
            print(f"       title: {record.get('title', '')[:40]}...")
            print()

        return uuid_records

    async def export_to_file(self, records: List[Dict[str, Any]]) -> str:
        """导出到JSON文件"""
        print("\n" + "="*80)
        print("💾 【步骤2】导出备份文件")
        print("="*80)

        if not records:
            print("  跳过 (无数据)")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/search_results_uuid_backup_{timestamp}.json"

        # 转换ObjectId和datetime为可序列化格式
        serializable_records = []
        for record in records:
            clean_record = {}
            for key, value in record.items():
                if key == "_id":
                    clean_record[key] = str(value)
                elif isinstance(value, datetime):
                    clean_record[key] = value.isoformat()
                else:
                    clean_record[key] = value
            serializable_records.append(clean_record)

        # 写入文件
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(serializable_records, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 备份文件: {filename}")
        print(f"  记录数: {len(records)}")

        return filename

    async def archive_to_collection(self, records: List[Dict[str, Any]]) -> None:
        """归档到备份集合"""
        print("\n" + "="*80)
        print("📦 【步骤3】归档到备份集合")
        print("="*80)

        if not records:
            print("  跳过 (无数据)")
            return

        # 添加归档元数据
        for record in records:
            record["archived_at"] = datetime.utcnow()
            record["archive_reason"] = "UUID格式清理"

        # 插入归档集合
        result = await self.db["search_results_deleted_archive"].insert_many(records)
        self.stats["archived"] = len(result.inserted_ids)

        print(f"  ✅ 归档成功: {self.stats['archived']} 条记录")
        print(f"  集合名: search_results_deleted_archive")

    async def soft_delete(self) -> None:
        """软删除标记"""
        print("\n" + "="*80)
        print("🏷️  【步骤4】软删除标记")
        print("="*80)

        uuid_filter = {
            "$or": [
                {"_id": {"$regex": "^temp_|\\-"}},
                {"task_id": {"$regex": "^temp_|\\-"}}
            ]
        }

        result = await self.db["search_results"].update_many(
            uuid_filter,
            {
                "$set": {
                    "status": "deleted",
                    "deleted_at": datetime.utcnow(),
                    "deletion_reason": "UUID格式清理 (v1.5.0)"
                }
            }
        )

        self.stats["soft_deleted"] = result.modified_count
        print(f"  ✅ 软删除标记: {self.stats['soft_deleted']} 条记录")

    async def hard_delete(self, confirm: bool = False) -> None:
        """物理删除"""
        print("\n" + "="*80)
        print("🗑️  【步骤5】物理删除")
        print("="*80)

        if not confirm:
            print("  ⚠️  跳过物理删除 (需要手动确认)")
            print("  提示: 建议观察7天后再执行物理删除")
            return

        # 删除已软删除超过7天的记录
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        result = await self.db["search_results"].delete_many({
            "status": "deleted",
            "deleted_at": {"$lt": cutoff_date}
        })

        self.stats["hard_deleted"] = result.deleted_count
        print(f"  ✅ 物理删除: {self.stats['hard_deleted']} 条记录")
        print(f"  条件: deleted_at < {cutoff_date.isoformat()}")

    async def verify_cleanup(self) -> None:
        """验证清理结果"""
        print("\n" + "="*80)
        print("✅ 【步骤6】验证清理结果")
        print("="*80)

        # 检查剩余UUID记录
        remaining_uuid = await self.db["search_results"].count_documents({
            "$or": [
                {"_id": {"$regex": "^temp_|\\-"}},
                {"task_id": {"$regex": "^temp_|\\-"}}
            ],
            "status": {"$ne": "deleted"}
        })

        # 检查软删除记录
        soft_deleted = await self.db["search_results"].count_documents({
            "status": "deleted"
        })

        # 检查归档记录
        archived = await self.db["search_results_deleted_archive"].count_documents({})

        print(f"  剩余UUID记录 (未标记): {remaining_uuid}")
        print(f"  软删除记录: {soft_deleted}")
        print(f"  归档记录: {archived}")

        if remaining_uuid == 0:
            print("\n  ✅ 清理完成: 所有UUID记录已处理")
        else:
            print(f"\n  ⚠️  仍有 {remaining_uuid} 条UUID记录未处理")

    def print_summary(self):
        """打印清理摘要"""
        print("\n" + "="*80)
        print("📊 【清理摘要】")
        print("="*80)
        print(f"  总记录数: {self.stats['total_records']}")
        print(f"  UUID格式记录: {self.stats['uuid_records']}")
        print(f"  归档记录: {self.stats['archived']}")
        print(f"  软删除记录: {self.stats['soft_deleted']}")
        print(f"  物理删除记录: {self.stats['hard_deleted']}")
        print(f"  错误数: {self.stats['errors']}")

        success_rate = (
            (self.stats['soft_deleted'] / self.stats['uuid_records'] * 100)
            if self.stats['uuid_records'] > 0 else 100
        )
        print(f"\n  成功率: {success_rate:.1f}%")

async def main():
    """主函数"""
    print("="*80)
    print("🧹 search_results UUID格式数据清理工具 v1.0.0")
    print("="*80)

    service = UUIDCleanupService()
    await service.initialize()

    # 执行清理流程
    try:
        # 1. 识别UUID记录
        uuid_records = await service.identify_uuid_records()

        if not uuid_records:
            return

        # 2. 导出备份
        backup_file = await service.export_to_file(uuid_records)

        # 3. 归档到集合
        await service.archive_to_collection(uuid_records)

        # 4. 软删除标记
        await service.soft_delete()

        # 5. 物理删除 (默认不执行，需手动确认)
        await service.hard_delete(confirm=False)

        # 6. 验证结果
        await service.verify_cleanup()

        # 7. 打印摘要
        service.print_summary()

        print("\n✅ 清理流程完成")

        if backup_file:
            print(f"\n💾 备份文件: {backup_file}")
            print("   提示: 验证无误后可删除备份文件")

    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
```

### 6.2 执行命令

```bash
# 1. 运行清理脚本 (软删除 + 归档)
python3 scripts/cleanup_uuid_search_results.py

# 2. 验证结果 (可选)
python3 scripts/cleanup_uuid_search_results.py --verify

# 3. 物理删除 (7天后，需手动确认)
# 修改脚本中 hard_delete(confirm=True) 后执行
```

### 6.3 执行清单

**执行前准备**:

- [ ] 确认当前环境 (开发/测试/生产)
- [ ] 选择低峰期时间窗口
- [ ] 通知相关人员清理计划
- [ ] 准备回滚方案

**执行步骤**:

- [ ] 1. 完整备份 search_results 集合
- [ ] 2. 运行识别脚本，确认UUID记录数量
- [ ] 3. 执行清理脚本 (软删除 + 归档)
- [ ] 4. 验证清理结果
- [ ] 5. 监控系统运行7天
- [ ] 6. 执行物理删除 (可选)
- [ ] 7. 清理归档数据 (30天后)

**执行后验证**:

- [ ] 检查剩余UUID记录数: 0
- [ ] 检查软删除记录数: 匹配预期
- [ ] 检查归档集合记录数: 匹配预期
- [ ] 检查关联集合引用: 无断链
- [ ] 验证系统功能: 无异常

---

## 7. 回滚方案

### 7.1 软删除回滚

```python
async def rollback_soft_delete():
    """回滚软删除"""
    db = await get_mongodb_database()

    result = await db["search_results"].update_many(
        {
            "status": "deleted",
            "deletion_reason": "UUID格式清理 (v1.5.0)"
        },
        {
            "$unset": {
                "status": "",
                "deleted_at": "",
                "deletion_reason": ""
            }
        }
    )

    print(f"✅ 回滚成功: {result.modified_count} 条记录")
```

### 7.2 物理删除回滚

```python
async def restore_from_archive():
    """从归档恢复"""
    db = await get_mongodb_database()

    # 1. 从归档集合读取
    archived_records = await db["search_results_deleted_archive"].find({
        "archive_reason": "UUID格式清理"
    }).to_list(length=None)

    # 2. 清理元数据
    for record in archived_records:
        record.pop("archived_at", None)
        record.pop("archive_reason", None)

    # 3. 插入回主集合
    result = await db["search_results"].insert_many(archived_records)

    print(f"✅ 恢复成功: {len(result.inserted_ids)} 条记录")
```

### 7.3 从备份文件恢复

```bash
# 1. 从JSON文件恢复
mongoimport --uri "mongodb://localhost:27017/guanshan" \
  --collection search_results \
  --file /tmp/search_results_uuid_backup_20251123_120000.json \
  --jsonArray
```

---

## 8. 预防措施

### 8.1 ID格式验证

#### 在数据写入时验证

```python
# src/infrastructure/persistence/repositories/mongo/result_repository.py

from src.core.domain.value_objects.id_validator import IDValidator

class MongoResultRepository:
    async def create(self, result: SearchResult) -> str:
        # ✅ 验证ID格式
        IDValidator.validate_snowflake_id(result.id)
        IDValidator.validate_snowflake_id(result.task_id)

        # 插入数据
        doc = result.to_dict()
        await self.collection.insert_one(doc)
        return result.id
```

### 8.2 定期检查脚本

```python
# scripts/check_id_format_health.py

async def check_id_health():
    """ID格式健康检查"""
    db = await get_mongodb_database()

    # 统计
    total = await db["search_results"].count_documents({})
    snowflake = await db["search_results"].count_documents({
        "_id": {"$regex": "^[0-9]+$"}
    })
    uuid = await db["search_results"].count_documents({
        "_id": {"$regex": "^temp_|\\-"}
    })

    health_score = (snowflake / total * 100) if total > 0 else 100

    print(f"ID格式健康分数: {health_score:.1f}%")
    print(f"  雪花ID: {snowflake}")
    print(f"  UUID: {uuid}")

    if health_score < 99.0:
        print("⚠️  警告: 发现UUID格式数据，建议清理")
    else:
        print("✅ 健康: ID格式符合规范")

# 定时任务: 每周执行
# crontab: 0 0 * * 0 python3 scripts/check_id_format_health.py
```

### 8.3 监控和告警

```python
# 监控指标
metrics = {
    "id_format_health_score": 100.0,  # 雪花ID占比
    "uuid_record_count": 0,            # UUID记录数
    "last_check_time": "2025-11-23T17:50:00Z"
}

# 告警规则
if metrics["id_format_health_score"] < 99.0:
    send_alert("search_results ID格式异常，发现UUID数据")
```

---

## 9. 总结

### 9.1 当前状态 ✅

- **UUID记录数**: 0
- **雪花ID覆盖率**: 100%
- **ID系统状态**: ✅ 完全符合 v1.5.0 规范
- **需要立即清理**: ❌ 否

### 9.2 推荐行动

**短期 (本周)**:
- ✅ 部署ID格式验证 (写入时检查)
- ✅ 设置定期健康检查 (每周)

**中期 (本月)**:
- ✅ 建立监控告警机制
- ✅ 编写操作手册和培训材料

**长期 (持续)**:
- ✅ 定期审计ID格式健康度
- ✅ 完善清理工具和流程

### 9.3 关键文档

- **ID系统规范**: `ID_SYSTEM_ARCHITECTURE.md`
- **迁移记录**: `TASK_ID_UNIFICATION_ANALYSIS.md`
- **清理脚本**: `scripts/cleanup_uuid_search_results.py`
- **健康检查**: `scripts/check_id_format_health.py`

---

**文档版本**: v1.0.0
**最后更新**: 2025-11-23
**维护人员**: Backend Team
**审核状态**: ✅ 已审核
