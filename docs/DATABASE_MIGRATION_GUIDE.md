# 数据库迁移指南
# Database Migration Guide

## 📋 概述

本指南说明如何将数据从本地MongoDB数据库迁移到生产MongoDB数据库。

**迁移流程：**
```
本地数据库                    生产数据库
localhost:27017   ─────→   hancens.top:40717
intelligent_system          guanshan
```

## ✅ 前置条件

### 1. 环境准备

- [x] Python 3.8+ 已安装
- [x] 项目依赖已安装 (`pip install -r requirements.txt`)
- [x] 本地MongoDB服务运行中
- [x] 生产数据库密码已获取
- [x] 网络可以访问生产服务器

### 2. 配置检查

确保 `.env` 文件已配置生产数据库连接：

```bash
MONGODB_URL=mongodb://guanshan:YOUR_ACTUAL_PASSWORD@hancens.top:40717/?authSource=guanshan
MONGODB_DB_NAME=guanshan
```

**⚠️ 重要：** 将 `YOUR_ACTUAL_PASSWORD` 替换为实际密码！

## 🚀 完整迁移流程

### 步骤 1: 测试生产数据库连接 (必需)

在迁移前，先确保可以连接到生产数据库：

```bash
python scripts/test_production_database.py
```

**预期输出：**
```
==================================================================
                    生产数据库连接测试
==================================================================

✓ MongoDB连接成功
✓ MongoDB版本: 5.0.x
✓ 成功访问数据库: guanshan
✓ 写入测试成功
✓ 读取测试成功
✓ 清理完成

==================================================================
                         测试完成
==================================================================

✓ 所有测试通过！生产数据库连接正常
```

**如果测试失败：**
- 检查密码是否正确
- 检查特殊字符是否已URL编码
- 验证防火墙是否开放40717端口
- 确认网络连接正常

### 步骤 2: 备份本地数据 (强烈推荐)

在迁移前备份本地数据，以防万一：

```bash
# 备份所有集合
python scripts/backup_database.py

# 备份到指定目录
python scripts/backup_database.py --output ./backups/before_migration
```

**备份文件位置：** `./backups/`

**备份内容：**
- 所有集合的JSON.GZ压缩文件
- 备份清单文件 (包含时间戳和统计信息)

### 步骤 3: 预览迁移计划 (推荐)

使用干运行模式预览迁移操作：

```bash
# 预览全量迁移
python scripts/migrate_database.py --all --dry-run
```

**输出示例：**
```
==================================================================
                        数据库迁移工具
==================================================================

[1/6] 连接数据库
✓ 源数据库连接成功: intelligent_system
✓ 目标数据库连接成功: guanshan

[2/6] 分析源数据库
ℹ 源数据库集合:
  • search_tasks: 15 文档
  • search_results: 120 文档
  • instant_search_tasks: 8 文档
  • instant_search_results: 45 文档
ℹ 总计: 4 集合, 188 文档

[4/6] 执行数据迁移 [DRY RUN]
ℹ [DRY RUN] 将迁移 15 文档
...
```

### 步骤 4: 执行实际迁移

确认迁移计划无误后，执行实际迁移：

```bash
# 全量迁移（所有集合）
python scripts/migrate_database.py --all

# 或迁移指定集合
python scripts/migrate_database.py --collections search_tasks search_results
```

**迁移过程：**
1. 连接源和目标数据库
2. 分析源数据库集合
3. 检查目标数据库（如有数据会提示确认）
4. 批量迁移文档（每批1000条）
5. 复制索引定义
6. 验证迁移结果

**成功输出示例：**
```
[4/6] 执行数据迁移
ℹ 迁移 search_tasks (15 文档)
  进度: 15/15 (100%)
✓ 完成迁移 15 文档
✓ 创建了 5 个索引

[5/6] 迁移总结

迁移统计:
  集合数量: 4
  文档数量: 188
  索引数量: 18
  耗时: 3.45 秒

[6/6] 验证迁移结果
✓ search_tasks: 15 文档 ✓
✓ search_results: 120 文档 ✓
✓ instant_search_tasks: 8 文档 ✓
✓ instant_search_results: 45 文档 ✓

✓ 所有集合验证通过！

==================================================================
                         迁移完成
==================================================================

✓ 数据库迁移成功！
ℹ 可以开始使用生产数据库
```

### 步骤 5: 验证迁移结果

迁移完成后，验证数据完整性：

```bash
# 使用MongoDB连接工具查看数据
python scripts/mongodb_connection_helper.py --overview

# 或手动验证
python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient('mongodb://guanshan:PASSWORD@hancens.top:40717/?authSource=guanshan')
    db = client['guanshan']
    collections = await db.list_collection_names()
    for coll in collections:
        count = await db[coll].count_documents({})
        print(f'{coll}: {count} documents')
    client.close()

asyncio.run(check())
"
```

### 步骤 6: 启动应用测试

使用生产数据库启动应用并测试：

```bash
# 启动应用
python src/main.py

# 访问API文档
open http://localhost:8000/api/docs

# 测试主要功能
curl http://localhost:8000/health
```

## 📊 迁移脚本详解

### migrate_database.py

**主要功能：**
- 数据迁移（文档和索引）
- 批量处理（1000条/批）
- 进度显示
- 自动验证
- 错误处理

**常用命令：**

```bash
# 全量迁移
python scripts/migrate_database.py --all

# 迁移指定集合
python scripts/migrate_database.py --collections search_tasks search_results

# 干运行（预览）
python scripts/migrate_database.py --all --dry-run

# 跳过备份提醒
python scripts/migrate_database.py --all --skip-backup

# 使用自定义连接字符串
python scripts/migrate_database.py --all \
  --source-url "mongodb://localhost:27017" \
  --target-url "mongodb://guanshan:PASS@hancens.top:40717"
```

### backup_database.py

**主要功能：**
- 导出为JSON格式
- GZIP压缩
- 生成备份清单
- 支持增量备份

**常用命令：**

```bash
# 备份本地数据库
python scripts/backup_database.py

# 备份生产数据库
python scripts/backup_database.py --production

# 备份指定集合
python scripts/backup_database.py --collections search_tasks

# 指定输出目录
python scripts/backup_database.py --output /path/to/backups
```

## 🔍 故障排查

### 问题 1: 源数据库连接失败

**症状：**
```
✗ 源数据库连接失败: [Errno 61] Connection refused
```

**解决方案：**
```bash
# 启动本地MongoDB
# macOS
brew services start mongodb-community

# 或使用Docker
docker-compose -f docker-compose.mongodb.yml up -d

# 验证服务
mongo --eval "db.version()"
```

### 问题 2: 目标数据库认证失败

**症状：**
```
✗ 目标数据库连接失败: Authentication failed
```

**解决方案：**
1. 检查密码是否正确
2. 确认特殊字符已URL编码
3. 验证authSource参数（应为guanshan）

```bash
# 测试连接
python scripts/test_production_database.py
```

### 问题 3: 目标数据库已有数据

**症状：**
```
⚠ 目标数据库已有 4 个集合:
  • search_tasks: 10 文档
  ...
⚠ 继续迁移将覆盖现有数据，是否继续? (yes/no):
```

**解决方案：**

**方案A: 清空目标数据库** (谨慎！)
```python
# 手动清空
python -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def clear():
    client = AsyncIOMotorClient('mongodb://guanshan:PASS@hancens.top:40717/?authSource=guanshan')
    db = client['guanshan']
    collections = await db.list_collection_names()
    for coll in collections:
        await db[coll].drop()
        print(f'Dropped {coll}')
    client.close()

asyncio.run(clear())
"
```

**方案B: 备份后覆盖**
```bash
# 先备份生产数据库
python scripts/backup_database.py --production --output ./backups/production_before_migration

# 然后执行迁移
python scripts/migrate_database.py --all --skip-backup
```

### 问题 4: 迁移验证失败

**症状：**
```
✗ search_tasks: 源=15, 目标=12 ✗
```

**解决方案：**
1. 检查迁移日志中的错误信息
2. 重新迁移失败的集合：
```bash
python scripts/migrate_database.py --collections search_tasks
```

### 问题 5: 网络超时

**症状：**
```
✗ 目标数据库连接失败: timed out
```

**解决方案：**
```bash
# 测试网络连通性
ping hancens.top

# 测试端口
nc -zv hancens.top 40717

# 检查防火墙
# 确保服务器防火墙开放了40717端口
```

## 🔐 安全建议

### 1. 迁移前后备份

```bash
# 迁移前备份本地数据
python scripts/backup_database.py --output ./backups/before_migration

# 迁移后备份生产数据（作为基准）
python scripts/backup_database.py --production --output ./backups/after_migration
```

### 2. 分批迁移（大数据量）

如果数据量很大，建议分批迁移：

```bash
# 先迁移关键集合
python scripts/migrate_database.py --collections search_tasks search_results

# 验证后再迁移其他集合
python scripts/migrate_database.py --collections instant_search_tasks instant_search_results
```

### 3. 保留迁移日志

```bash
# 重定向日志到文件
python scripts/migrate_database.py --all 2>&1 | tee migration_log_$(date +%Y%m%d_%H%M%S).txt
```

## 📚 数据恢复

如果需要从备份恢复数据：

```bash
# 查看备份清单
cat backups/backup_manifest_20250121_120000.json

# 手动恢复（使用Python）
python -c "
import asyncio
import json
import gzip
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

async def restore():
    client = AsyncIOMotorClient('mongodb://guanshan:PASS@hancens.top:40717/?authSource=guanshan')
    db = client['guanshan']

    # 读取备份文件
    with gzip.open('backups/search_tasks_20250121_120000.json.gz', 'rt') as f:
        documents = json.load(f)

    # 恢复ObjectId
    for doc in documents:
        doc['_id'] = ObjectId(doc['_id'])

    # 插入数据
    if documents:
        await db.search_tasks.insert_many(documents)
        print(f'Restored {len(documents)} documents')

    client.close()

asyncio.run(restore())
"
```

## ✅ 迁移完成检查清单

完成以下检查后，迁移工作即告完成：

- [ ] 1. 生产数据库连接测试通过
- [ ] 2. 本地数据已备份
- [ ] 3. 迁移计划已预览（dry-run）
- [ ] 4. 数据迁移已完成
- [ ] 5. 迁移结果验证通过
- [ ] 6. 应用使用生产数据库测试正常
- [ ] 7. API接口功能正常
- [ ] 8. 迁移日志已保存
- [ ] 9. 生产数据已备份（作为基准）
- [ ] 10. 更新部署文档

## 🆘 获取帮助

遇到问题时：

1. **查看详细错误信息**
   - 迁移脚本会显示详细的堆栈跟踪
   - 检查MongoDB日志

2. **运行诊断工具**
   ```bash
   python scripts/test_production_database.py
   python scripts/mongodb_connection_helper.py --overview
   ```

3. **查看相关文档**
   - [生产数据库配置指南](./PRODUCTION_DATABASE_SETUP.md)
   - [MongoDB连接指南](./MONGODB_GUIDE.md)

4. **联系技术支持**
   - 提供迁移日志
   - 提供错误截图
   - 说明已尝试的解决方案

---

**版本**: 1.0.0
**更新日期**: 2025-01-21
**维护者**: 关山智能系统团队
