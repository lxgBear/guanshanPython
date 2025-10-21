# MongoDB 宝塔部署与远程访问指南

> **目标**: 在宝塔面板部署MongoDB，并配置安全的远程访问供团队AI分析使用
> **版本**: v1.0 | **更新时间**: 2025-10-16

---

## 🚀 快速开始

如果你已经有宝塔服务器信息，想快速配置连接，请参考：
- **📘 [宝塔MongoDB连接配置指南](BAOTA_MONGODB_CONNECTION_GUIDE.md)** - 快速连接已有宝塔MongoDB
- **📝 [快速配置模板](.env.baota.example)** - 环境变量配置示例

本文档提供完整的从零部署流程。如果已部署MongoDB，跳转到快速指南更高效。

---

## 📋 目录

- [部署概述](#部署概述)
- [第一步：宝塔安装MongoDB](#第一步宝塔安装mongodb)
- [第二步：配置远程访问](#第二步配置远程访问)
- [第三步：创建数据库和用户](#第三步创建数据库和用户)
- [第四步：安全加固](#第四步安全加固)
- [第五步：连接测试](#第五步连接测试)
- [第六步：团队远程访问](#第六步团队远程访问)
- [AI分析工具连接示例](#ai分析工具连接示例)
- [故障排查](#故障排查)
- [安全最佳实践](#安全最佳实践)

---

## 部署概述

### 架构图

```
┌─────────────────────────────────────────────────────┐
│ 宝塔服务器 (公网IP: xxx.xxx.xxx.xxx)                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ MongoDB 服务                              │     │
│  │ - 端口: 27017 (内网)                      │     │
│  │ - 端口: 37017 (外网映射)                  │     │
│  │ - 认证: 启用                              │     │
│  └──────────────────────────────────────────┘     │
│                      ↓                              │
│  ┌──────────────────────────────────────────┐     │
│  │ 防火墙规则                                │     │
│  │ - 只允许特定IP访问37017                   │     │
│  │ - 启用SSL/TLS加密                         │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
                       ↓
        ┌──────────────────────────────┐
        │ 远程访问（同事 + AI工具）      │
        ├──────────────────────────────┤
        │ - MongoDB Compass             │
        │ - Python (pymongo/motor)      │
        │ - AI分析工具                  │
        └──────────────────────────────┘
```

### 安全策略

| 层级 | 措施 | 说明 |
|------|------|------|
| **网络层** | 非标准端口 | 使用37017而非27017 |
| **网络层** | IP白名单 | 只允许特定IP访问 |
| **网络层** | SSL/TLS | 加密传输通道 |
| **认证层** | 强密码 | 16+字符，包含特殊字符 |
| **认证层** | 角色权限 | 最小权限原则 |
| **数据层** | 只读用户 | AI分析用户仅读权限 |

---

## 第一步：宝塔安装MongoDB

### 1.1 通过宝塔软件商店安装

#### 方式A: 使用宝塔MongoDB管理器（推荐）

1. **登录宝塔面板**
   ```
   https://your-server-ip:8000
   ```

2. **进入软件商店**
   - 点击左侧菜单 `软件商店`
   - 搜索 `MongoDB`

3. **安装MongoDB**
   - 选择版本：`MongoDB 5.0` 或 `MongoDB 6.0`（推荐6.0）
   - 点击 `安装`
   - 等待安装完成（约5-10分钟）

4. **验证安装**
   ```bash
   # SSH登录服务器
   mongosh --version
   # 或
   mongo --version
   ```

#### 方式B: 手动安装（如果宝塔没有MongoDB插件）

```bash
# SSH登录服务器

# 1. 添加MongoDB仓库
cat > /etc/yum.repos.d/mongodb-org-6.0.repo <<EOF
[mongodb-org-6.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/6.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-6.0.asc
EOF

# 2. 安装MongoDB
yum install -y mongodb-org

# 3. 启动MongoDB服务
systemctl start mongod
systemctl enable mongod

# 4. 检查状态
systemctl status mongod
```

---

## 第二步：配置远程访问

### 2.1 修改MongoDB配置文件

```bash
# 编辑配置文件
vi /etc/mongod.conf
```

#### 配置内容

```yaml
# mongod.conf

# 网络配置
net:
  port: 27017
  bindIp: 0.0.0.0  # 允许所有IP访问（通过防火墙控制）
  # bindIp: 127.0.0.1,xxx.xxx.xxx.xxx  # 或指定特定IP

# 安全配置
security:
  authorization: enabled  # 启用认证

# 存储配置
storage:
  dbPath: /var/lib/mongo
  journal:
    enabled: true

# 日志配置
systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true

# 进程管理
processManagement:
  fork: true
  pidFilePath: /var/run/mongodb/mongod.pid
```

### 2.2 重启MongoDB服务

```bash
systemctl restart mongod

# 验证服务运行
systemctl status mongod

# 查看日志
tail -f /var/log/mongodb/mongod.log
```

---

## 第三步：创建数据库和用户

### 3.1 创建管理员用户

```bash
# 连接到MongoDB（初次无需密码）
mongosh

# 或使用旧版命令
mongo
```

```javascript
// 切换到admin数据库
use admin

// 创建超级管理员
db.createUser({
  user: "admin",
  pwd: "YOUR_STRONG_PASSWORD_HERE",  // ⚠️ 请使用强密码
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" },
    { role: "dbAdminAnyDatabase", db: "admin" },
    { role: "clusterAdmin", db: "admin" }
  ]
})

// 验证用户创建
db.getUsers()

// 退出
exit
```

### 3.2 创建应用数据库和用户

```bash
# 使用管理员身份登录
mongosh -u admin -p YOUR_STRONG_PASSWORD_HERE --authenticationDatabase admin
```

```javascript
// 切换到应用数据库
use intelligent_system

// 创建应用读写用户
db.createUser({
  user: "app_user",
  pwd: "APP_USER_STRONG_PASSWORD",
  roles: [
    { role: "readWrite", db: "intelligent_system" }
  ]
})

// 创建只读用户（供AI分析使用）
db.createUser({
  user: "ai_analyst",
  pwd: "AI_ANALYST_STRONG_PASSWORD",
  roles: [
    { role: "read", db: "intelligent_system" }
  ]
})

// 验证用户
db.getUsers()
```

### 3.3 测试认证

```bash
# 测试管理员用户
mongosh -u admin -p YOUR_STRONG_PASSWORD_HERE --authenticationDatabase admin

# 测试应用用户
mongosh -u app_user -p APP_USER_STRONG_PASSWORD --authenticationDatabase intelligent_system

# 测试AI分析用户
mongosh -u ai_analyst -p AI_ANALYST_STRONG_PASSWORD --authenticationDatabase intelligent_system
```

---

## 第四步：安全加固

### 4.1 配置宝塔防火墙

1. **进入宝塔面板 → 安全**

2. **添加防火墙规则**

   | 端口 | 协议 | 允许的IP | 说明 |
   |------|------|---------|------|
   | 37017 | TCP | `your.team.ip.1` | 团队成员1 |
   | 37017 | TCP | `your.team.ip.2` | 团队成员2 |
   | 37017 | TCP | `your.team.ip.3` | AI工具服务器 |

3. **端口映射（如果需要）**

   ```bash
   # 使用iptables将37017映射到27017
   iptables -t nat -A PREROUTING -p tcp --dport 37017 -j REDIRECT --to-port 27017

   # 保存规则
   service iptables save
   ```

### 4.2 启用SSL/TLS加密（推荐）

#### 生成SSL证书

```bash
# 创建证书目录
mkdir -p /etc/ssl/mongodb
cd /etc/ssl/mongodb

# 生成自签名证书（有效期10年）
openssl req -newkey rsa:2048 -new -x509 -days 3650 -nodes \
  -out mongodb-cert.crt -keyout mongodb-cert.key

# 合并证书和密钥
cat mongodb-cert.key mongodb-cert.crt > mongodb.pem

# 设置权限
chmod 600 mongodb.pem
chown mongod:mongod mongodb.pem
```

#### 更新MongoDB配置

```yaml
# /etc/mongod.conf

net:
  port: 27017
  bindIp: 0.0.0.0
  ssl:
    mode: requireSSL
    PEMKeyFile: /etc/ssl/mongodb/mongodb.pem
```

#### 重启服务

```bash
systemctl restart mongod
```

### 4.3 配置云服务器安全组

如果使用阿里云/腾讯云等，需要在云控制台配置安全组：

1. **进入云控制台 → 安全组**
2. **添加入站规则**
   - 协议: TCP
   - 端口: 37017（或27017）
   - 授权对象: 特定IP地址

---

## 第五步：连接测试

### 5.1 本地测试（服务器内）

```bash
# 基本连接测试
mongosh mongodb://admin:YOUR_PASSWORD@localhost:27017/admin

# SSL连接测试
mongosh "mongodb://admin:YOUR_PASSWORD@localhost:27017/admin?ssl=true&sslAllowInvalidCertificates=true"
```

### 5.2 远程测试（从本地电脑）

#### 使用mongosh

```bash
# 基本连接
mongosh "mongodb://ai_analyst:AI_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system"

# SSL连接
mongosh "mongodb://ai_analyst:AI_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system&ssl=true&tlsAllowInvalidCertificates=true"
```

#### 使用Python

```python
from pymongo import MongoClient

# 基本连接
client = MongoClient(
    host="your-server-ip",
    port=37017,
    username="ai_analyst",
    password="AI_PASSWORD",
    authSource="intelligent_system",
    authMechanism="SCRAM-SHA-256"
)

# 测试连接
db = client.intelligent_system
print(db.list_collection_names())
```

---

## 第六步：团队远程访问

### 6.1 更新应用配置

更新 `.env` 文件：

```bash
# 生产环境MongoDB连接（宝塔服务器）
MONGODB_URL=mongodb://app_user:APP_USER_STRONG_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system
MONGODB_DB_NAME=intelligent_system
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10
```

### 6.2 创建团队访问文档

为团队成员创建 `MONGODB_ACCESS_GUIDE.md`：

```markdown
# MongoDB远程访问指南（团队内部）

## 连接信息

| 项目 | 值 |
|------|---|
| **服务器地址** | `your-server-ip` |
| **端口** | `37017` |
| **数据库名** | `intelligent_system` |
| **用户名** | `ai_analyst` |
| **密码** | `AI_ANALYST_PASSWORD` |
| **认证数据库** | `intelligent_system` |

## 连接字符串

\`\`\`
mongodb://ai_analyst:AI_ANALYST_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system
\`\`\`

## 使用MongoDB Compass连接

1. 下载安装 [MongoDB Compass](https://www.mongodb.com/products/compass)
2. 打开Compass，点击 "New Connection"
3. 粘贴连接字符串（见上）
4. 点击 "Connect"

## Python连接示例

\`\`\`python
from pymongo import MongoClient

client = MongoClient(
    "mongodb://ai_analyst:AI_ANALYST_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system"
)

db = client.intelligent_system
\`\`\`

## 注意事项

⚠️ **安全提示**:
- 此账号仅有读权限，无法修改数据
- 请勿分享给外部人员
- 如需写权限，请联系管理员

## 可用集合

- `search_tasks` - 定时搜索任务
- `search_results` - 搜索结果
- `instant_search_tasks` - 即时搜索任务
- `instant_search_results` - 即时搜索结果
- `instant_search_result_mappings` - 搜索结果映射
\`\`\`

---

## AI分析工具连接示例

### 使用Pandas + PyMongo

```python
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

# 连接MongoDB
client = MongoClient(
    "mongodb://ai_analyst:AI_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system"
)
db = client.intelligent_system

# 1. 读取搜索任务数据
tasks_cursor = db.search_tasks.find(
    {"is_active": True},
    {"name": 1, "query": 1, "execution_count": 1, "success_rate": 1}
)
tasks_df = pd.DataFrame(list(tasks_cursor))
print(tasks_df.head())

# 2. 读取搜索结果数据
results_cursor = db.search_results.find(
    {"execution_time": {"$gte": datetime(2025, 1, 1)}},
    limit=1000
)
results_df = pd.DataFrame(list(results_cursor))
print(results_df.head())

# 3. 统计分析
task_stats = tasks_df.groupby('name').agg({
    'execution_count': 'sum',
    'success_rate': 'mean'
})
print(task_stats)
```

### 使用LangChain + MongoDB

```python
from langchain.document_loaders import MongoDBLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

# 1. 从MongoDB加载数据
loader = MongoDBLoader(
    connection_string="mongodb://ai_analyst:AI_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system",
    db_name="intelligent_system",
    collection_name="search_results",
    field_names=["title", "content", "url"]
)
documents = loader.load()

# 2. 创建向量索引
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(documents, embeddings)

# 3. 创建问答链
qa_chain = RetrievalQA.from_chain_type(
    llm=OpenAI(temperature=0),
    chain_type="stuff",
    retriever=vectorstore.as_retriever()
)

# 4. 提问
question = "Myanmar经济新闻的主要趋势是什么？"
answer = qa_chain.run(question)
print(answer)
```

### 使用Jupyter Notebook

```python
# Notebook: mongodb_analysis.ipynb

import pymongo
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 连接配置
MONGO_URI = "mongodb://ai_analyst:AI_PASSWORD@your-server-ip:37017/intelligent_system?authSource=intelligent_system"
client = pymongo.MongoClient(MONGO_URI)
db = client.intelligent_system

# 数据探索
print("可用集合:", db.list_collection_names())

# 任务执行趋势分析
tasks = pd.DataFrame(list(db.search_tasks.find()))
tasks['created_at'] = pd.to_datetime(tasks['created_at'])

plt.figure(figsize=(12, 6))
tasks.groupby(tasks['created_at'].dt.date)['execution_count'].sum().plot()
plt.title('Daily Task Execution Trend')
plt.xlabel('Date')
plt.ylabel('Execution Count')
plt.show()

# 成功率分析
plt.figure(figsize=(10, 6))
sns.barplot(data=tasks, x='name', y='success_rate')
plt.xticks(rotation=45, ha='right')
plt.title('Task Success Rate')
plt.tight_layout()
plt.show()
```

---

## 故障排查

### 问题1: 无法连接到MongoDB

**症状**: `pymongo.errors.ServerSelectionTimeoutError`

**解决方案**:

```bash
# 1. 检查MongoDB服务状态
systemctl status mongod

# 2. 检查防火墙规则
firewall-cmd --list-ports
# 或
iptables -L -n | grep 37017

# 3. 检查端口监听
netstat -tuln | grep 27017

# 4. 测试端口连通性（从本地电脑）
telnet your-server-ip 37017
# 或
nc -zv your-server-ip 37017
```

### 问题2: 认证失败

**症状**: `pymongo.errors.OperationFailure: Authentication failed`

**解决方案**:

```javascript
// 登录MongoDB检查用户
mongosh -u admin -p YOUR_PASSWORD --authenticationDatabase admin

use intelligent_system
db.getUsers()

// 验证用户密码
db.auth("ai_analyst", "AI_PASSWORD")

// 重置密码
db.updateUser("ai_analyst", {
  pwd: "NEW_PASSWORD"
})
```

### 问题3: 权限不足

**症状**: `not authorized on intelligent_system to execute command`

**解决方案**:

```javascript
// 检查用户权限
use intelligent_system
db.getUser("ai_analyst")

// 授予读权限
db.grantRolesToUser("ai_analyst", [
  { role: "read", db: "intelligent_system" }
])
```

### 问题4: 防火墙阻止

**检查防火墙**:

```bash
# CentOS/RHEL
firewall-cmd --zone=public --add-port=37017/tcp --permanent
firewall-cmd --reload

# Ubuntu
ufw allow 37017/tcp
ufw reload

# 宝塔面板
# 进入 安全 → 添加端口规则
```

---

## 安全最佳实践

### 1. 密码安全

✅ **推荐做法**:
- 使用16+字符的强密码
- 包含大小写字母、数字、特殊字符
- 定期更换密码（每3个月）
- 使用密码管理器存储

❌ **避免做法**:
- 使用弱密码（如 `123456`, `password`）
- 将密码写在代码中
- 在不安全的渠道分享密码

### 2. 网络安全

✅ **推荐做法**:
- 使用非标准端口（如37017）
- 配置IP白名单
- 启用SSL/TLS加密
- 使用VPN或堡垒机

❌ **避免做法**:
- 对所有IP开放访问
- 使用未加密的连接
- 暴露在公网

### 3. 权限管理

✅ **推荐做法**:
- 最小权限原则
- AI分析用户只给读权限
- 定期审计用户权限
- 移除不再使用的用户

❌ **避免做法**:
- 所有人使用admin账号
- 给予过多权限
- 不删除离职人员账号

### 4. 审计日志

```javascript
// 启用审计日志
// /etc/mongod.conf
auditLog:
  destination: file
  format: JSON
  path: /var/log/mongodb/audit.json

// 查看审计日志
tail -f /var/log/mongodb/audit.json
```

### 5. 备份策略

```bash
# 自动备份脚本
#!/bin/bash
# /root/scripts/mongodb_backup.sh

BACKUP_DIR="/data/mongodb_backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="intelligent_system"

# 创建备份
mongodump \
  --host localhost \
  --port 27017 \
  --username admin \
  --password YOUR_PASSWORD \
  --authenticationDatabase admin \
  --db $DB_NAME \
  --out "$BACKUP_DIR/$DATE"

# 压缩备份
tar -czf "$BACKUP_DIR/$DATE.tar.gz" "$BACKUP_DIR/$DATE"
rm -rf "$BACKUP_DIR/$DATE"

# 删除30天前的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/$DATE.tar.gz"
```

```bash
# 添加到crontab（每天凌晨2点备份）
crontab -e
0 2 * * * /root/scripts/mongodb_backup.sh >> /var/log/mongodb_backup.log 2>&1
```

---

## 监控和维护

### 监控指标

```javascript
// 数据库状态
db.serverStatus()

// 连接数
db.currentOp()

// 数据库大小
db.stats()

// 慢查询
db.system.profile.find().sort({ts:-1}).limit(10)
```

### 性能优化

```javascript
// 查看索引
db.search_results.getIndexes()

// 分析查询性能
db.search_results.find({task_id: "xxx"}).explain("executionStats")

// 创建复合索引
db.search_results.createIndex({task_id: 1, execution_time: -1})
```

---

## 📚 相关文档

- **MongoDB官方文档**: https://docs.mongodb.com/
- **宝塔面板文档**: https://www.bt.cn/bbs/
- **PyMongo文档**: https://pymongo.readthedocs.io/
- **安全配置指南**: https://docs.mongodb.com/manual/security/

---

## 📅 维护记录

| 日期 | 操作 | 执行人 |
|------|------|-------|
| 2025-10-16 | 初始部署 | Admin |
| | 创建ai_analyst用户 | Admin |
| | 配置防火墙规则 | Admin |

---

**维护者**: DevOps Team
**紧急联系**: devops@company.com
**最后更新**: 2025-10-16
