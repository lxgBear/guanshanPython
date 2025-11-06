# MongoDB 部署与配置指南

**版本**: MongoDB 5.0+ | **环境**: 宝塔面板

---

## 快速开始

### 安装MongoDB (宝塔面板)

```bash
# 1. 通过宝塔软件商店安装MongoDB
软件商店 → 搜索 "MongoDB" → 安装

# 2. 启动服务
systemctl start mongod
systemctl enable mongod

# 3. 验证安装
mongosh --version
```

---

## 配置方式

### 方案1: 本地连接 (默认)

**连接字符串**:
```python
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB_NAME = "intelligent_system"
```

**特点**:
- ✅ 无需认证,开发便捷
- ✅ 性能最优(本地连接)
- ⚠️ 仅限本机访问

### 方案2: 终端远程连接

```bash
# 1. 安装MongoDB客户端工具
brew install mongosh  # macOS
apt install mongodb-mongosh  # Linux

# 2. SSH隧道连接
ssh -L 27017:localhost:27017 user@server_ip

# 3. 本地连接
mongosh mongodb://localhost:27017
```

### 方案3: 公网IP直连

```python
MONGODB_URL = "mongodb://admin:password@your_ip:27017/intelligent_system?authSource=admin"
```

**配置步骤**:
```bash
# 1. 修改MongoDB配置
sudo nano /etc/mongod.conf

# 修改为:
net:
  port: 27017
  bindIp: 0.0.0.0  # 允许所有IP访问

# 2. 重启服务
sudo systemctl restart mongod

# 3. 防火墙开放端口
sudo ufw allow 27017
# 或宝塔面板: 安全 → 放行端口 27017
```

---

## 数据库初始化

### 自动初始化

应用启动时自动执行:

```python
# src/infrastructure/database/connection.py
await initialize_database()
```

**初始化内容**:
1. 创建数据库 `intelligent_system`
2. 创建集合索引:
   - `search_tasks`: task_id, is_active
   - `search_results`: task_id, content_hash (唯一)
   - `task_result_mapping`: task_id + result_id (唯一)

### 手动初始化

```bash
mongosh mongodb://localhost:27017

use intelligent_system

# 创建索引
db.search_tasks.createIndex({ "id": 1 }, { unique: true })
db.search_tasks.createIndex({ "is_active": 1 })
db.search_results.createIndex({ "task_id": 1 })
db.search_results.createIndex({ "content_hash": 1 }, { unique: true })
```

---

## 数据库迁移

### 执行迁移

```bash
python scripts/run_migrations.py migrate
```

**输出示例**:
```
🚀 开始执行数据库迁移...
============================================================
✅ 001_add_is_active_field: 为搜索任务添加is_active字段
   已处理文档: 5
   已更新文档: 5
============================================================
✅ 迁移执行完成
   已执行: 1 个迁移
   已跳过: 0 个迁移
```

### 查看迁移状态

```bash
python scripts/run_migrations.py status
```

### 回滚迁移

```bash
python scripts/run_migrations.py rollback 001
```

### 创建新迁移

```python
# migrations/002_add_new_field.py
class Migration002:
    version = "002"
    description = "添加新字段"

    async def upgrade(self, db):
        await db.search_tasks.update_many(
            {},
            {"$set": {"new_field": "default_value"}}
        )
        return {"updated": result.modified_count}

    async def downgrade(self, db):
        await db.search_tasks.update_many(
            {},
            {"$unset": {"new_field": ""}}
        )
```

---

## 故障排查

### 问题1: 连接失败

**症状**:
```
ERROR: Failed to connect to MongoDB
```

**解决方案**:
```bash
# 1. 检查服务状态
systemctl status mongod

# 2. 查看日志
tail -f /var/log/mongodb/mongod.log

# 3. 测试连接
mongosh mongodb://localhost:27017 --eval "db.adminCommand('ping')"

# 4. 重启服务
systemctl restart mongod
```

### 问题2: 认证失败

**症状**:
```
MongoServerError: Authentication failed
```

**解决方案**:
```bash
# 1. 确认用户存在
mongosh mongodb://localhost:27017
use admin
db.getUsers()

# 2. 重置密码
db.changeUserPassword("admin", "new_password")

# 3. 更新配置文件
# .env
MONGODB_URL = "mongodb://admin:new_password@localhost:27017"
```

### 问题3: 端口冲突

**症状**:
```
ERROR: Address already in use: 27017
```

**解决方案**:
```bash
# 1. 查找占用端口的进程
lsof -i :27017

# 2. 终止进程
kill -9 <PID>

# 3. 或修改MongoDB端口
# /etc/mongod.conf
net:
  port: 27018  # 修改为其他端口
```

### 问题4: 磁盘空间不足

**症状**:
```
ERROR: No space left on device
```

**解决方案**:
```bash
# 1. 检查磁盘空间
df -h

# 2. 清理日志文件
sudo rm /var/log/mongodb/mongod.log.*

# 3. 压缩数据库
mongosh mongodb://localhost:27017
db.adminCommand({ compact: 'search_results' })

# 4. 增加磁盘空间
```

---

## 性能优化

### 索引优化

```javascript
// 查看慢查询
db.setProfilingLevel(1, { slowms: 100 })
db.system.profile.find().sort({ ts: -1 }).limit(5)

// 分析查询计划
db.search_results.find({ task_id: "xxx" }).explain("executionStats")

// 创建复合索引
db.search_results.createIndex({
  task_id: 1,
  created_at: -1
})
```

### 连接池配置

```python
# src/config.py
MONGODB_SETTINGS = {
    "maxPoolSize": 50,
    "minPoolSize": 10,
    "maxIdleTimeMS": 30000,
    "serverSelectionTimeoutMS": 5000
}
```

### 数据清理

```bash
# 删除30天前的搜索结果
mongosh mongodb://localhost:27017

use intelligent_system

db.search_results.deleteMany({
  created_at: {
    $lt: new Date(Date.now() - 30*24*60*60*1000)
  }
})
```

---

## 备份与恢复

### 数据备份

```bash
# 完整备份
mongodump --uri="mongodb://localhost:27017/intelligent_system" \
  --out=/backup/mongodb_$(date +%Y%m%d)

# 压缩备份
tar -czf mongodb_backup.tar.gz /backup/mongodb_*
```

### 数据恢复

```bash
# 恢复数据
mongorestore --uri="mongodb://localhost:27017/intelligent_system" \
  /backup/mongodb_20251017

# 恢复特定集合
mongorestore --uri="mongodb://localhost:27017/intelligent_system" \
  --nsInclude="intelligent_system.search_tasks" \
  /backup/mongodb_20251017
```

### 自动备份脚本

```bash
#!/bin/bash
# /scripts/backup_mongodb.sh

BACKUP_DIR="/backup/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)

mongodump --uri="mongodb://localhost:27017/intelligent_system" \
  --out="$BACKUP_DIR/$DATE"

# 保留最近7天备份
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

echo "✅ 备份完成: $BACKUP_DIR/$DATE"
```

**定时任务** (crontab):
```bash
# 每天凌晨2点备份
0 2 * * * /scripts/backup_mongodb.sh
```

---

## 监控命令

### 数据库状态

```javascript
// 连接信息
db.serverStatus().connections

// 存储占用
db.stats()

// 集合统计
db.search_results.stats()

// 当前操作
db.currentOp()
```

### 宝塔面板监控

```
软件商店 → MongoDB → 设置 → 性能监控
```

显示:
- CPU使用率
- 内存占用
- 连接数
- 操作数

---

## 相关文档

- [数据库迁移](DATABASE_MIGRATIONS.md)
- [系统架构](SYSTEM_ARCHITECTURE.md)
- [项目配置](PROJECT_SETUP.md)

**维护者**: Backend Team | **MongoDB版本**: 5.0+
