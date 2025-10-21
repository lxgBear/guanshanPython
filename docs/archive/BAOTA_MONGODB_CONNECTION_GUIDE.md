# 宝塔MongoDB连接配置指南

**服务器信息**:
- 宝塔面板地址: https://hancens.top:18314/cbece14e
- 宝塔用户名: mbjqhmkm
- 宝塔密码: asjklquio1z
- 服务器域名: hancens.top

**文档版本**: v1.0
**最后更新**: 2025-10-16

---

## ⚠️ 重要说明

**宝塔面板密码 ≠ MongoDB数据库密码**

- 宝塔面板凭据（mbjqhmkm/asjklquio1z）：仅用于登录宝塔Web管理界面
- MongoDB凭据：需要在MongoDB中单独创建，用于应用程序连接数据库

---

## 📋 配置流程概览

```
步骤1: 登录宝塔面板 (2分钟)
   ↓
步骤2: 检查MongoDB安装和运行状态 (1分钟)
   ↓
步骤3: 配置MongoDB远程访问 (5分钟)
   ↓
步骤4: 创建数据库和用户 (3分钟)
   ↓
步骤5: 配置防火墙规则 (3分钟)
   ↓
步骤6: 测试连接 (2分钟)
   ↓
步骤7: 配置项目环境变量 (2分钟)

总计: 约20分钟
```

---

## 步骤1: 登录宝塔面板

### 1.1 访问宝塔面板

在浏览器中打开：
```
https://hancens.top:18314/cbece14e
```

**说明**:
- `18314`: 宝塔面板访问端口（非默认8888，已自定义）
- `/cbece14e`: 安全入口路径（防止暴力破解）

### 1.2 输入登录凭据

```
用户名: mbjqhmkm
密码: asjklquio1z
```

### 1.3 验证登录成功

登录后应看到宝塔面板主界面，包含：
- 系统资源使用情况
- 已安装软件列表
- 网站、数据库、FTP等管理入口

---

## 步骤2: 检查MongoDB安装状态

### 2.1 进入软件商店

点击左侧菜单：**软件商店** → **已安装**

### 2.2 查找MongoDB

在已安装列表中找到 **MongoDB**，检查：
- ✅ 运行状态: 应显示"运行中"
- ✅ 版本信息: 记录版本号（如 5.0.x, 6.0.x）
- ✅ 安装路径: 通常在 `/www/server/mongodb/`

### 2.3 查看MongoDB设置

点击MongoDB右侧的 **设置** 按钮，查看：
- **运行状态**: 确认"运行中"
- **端口**: 默认27017（记录此端口号）
- **配置文件**: `/www/server/mongodb/config.conf`
- **启动参数**: 查看是否启用认证（--auth）

---

## 步骤3: 配置MongoDB远程访问

### 3.1 修改MongoDB配置文件

在宝塔面板中：
1. 点击 **文件** 菜单
2. 导航到 `/www/server/mongodb/`
3. 编辑 `config.conf` 文件

### 3.2 修改bindIp配置

找到 `net` 部分，修改 `bindIp`:

**修改前**:
```yaml
net:
  port: 27017
  bindIp: 127.0.0.1  # 仅允许本地访问
```

**修改后**:
```yaml
net:
  port: 27017
  bindIp: 0.0.0.0    # 允许所有IP访问
  # 或指定具体IP
  # bindIp: 127.0.0.1,your_client_ip
```

### 3.3 启用认证（如果未启用）

确保 `security` 部分启用了认证：

```yaml
security:
  authorization: enabled
```

### 3.4 重启MongoDB服务

在宝塔面板MongoDB设置中，点击 **重启** 按钮。

**验证重启成功**:
- 状态显示"运行中"
- 无错误日志

---

## 步骤4: 创建数据库和用户

### 4.1 连接MongoDB Shell

在宝塔面板MongoDB设置中，点击 **终端** 或使用SSH连接服务器：

```bash
/www/server/mongodb/bin/mongo
```

或如果已启用认证（使用admin用户）：
```bash
/www/server/mongodb/bin/mongo -u admin -p --authenticationDatabase admin
```

### 4.2 创建管理员用户（如果没有）

在MongoDB Shell中执行：

```javascript
use admin

db.createUser({
  user: "admin",
  pwd: "your_strong_admin_password",  // 设置强密码
  roles: [
    { role: "root", db: "admin" }
  ]
})
```

**记录**:
- Admin用户名: `admin`
- Admin密码: `your_strong_admin_password`（自己设置）

### 4.3 创建应用数据库

```javascript
use intelligent_system
```

### 4.4 创建应用用户

**选项A: 读写权限用户（应用程序使用）**

```javascript
use intelligent_system

db.createUser({
  user: "app_user",
  pwd: "your_app_password",  // 设置强密码
  roles: [
    { role: "readWrite", db: "intelligent_system" }
  ]
})
```

**选项B: 只读权限用户（数据分析使用）**

```javascript
use intelligent_system

db.createUser({
  user: "ai_analyst",
  pwd: "your_analyst_password",  // 设置强密码
  roles: [
    { role: "read", db: "intelligent_system" }
  ]
})
```

**记录创建的用户信息**:
```
数据库: intelligent_system
应用用户: app_user / your_app_password
分析用户: ai_analyst / your_analyst_password
```

### 4.5 验证用户创建

```javascript
use intelligent_system
db.getUsers()
```

应该看到刚创建的用户列表。

### 4.6 测试用户权限

退出并使用新用户重新连接：
```bash
/www/server/mongodb/bin/mongo \
  -u app_user \
  -p your_app_password \
  --authenticationDatabase intelligent_system \
  intelligent_system
```

测试插入数据：
```javascript
db.test_collection.insertOne({test: "data"})
db.test_collection.find()
db.test_collection.deleteOne({test: "data"})
```

---

## 步骤5: 配置防火墙规则

### 5.1 在宝塔面板配置防火墙

1. 点击 **安全** 菜单
2. 找到 **防火墙** 设置
3. 点击 **添加规则**

### 5.2 添加MongoDB端口

**配置如下**:
```
端口: 27017
协议: TCP
策略: 放行
备注: MongoDB数据库端口
```

### 5.3 配置IP白名单（推荐）

**选项A: 限制特定IP访问（推荐）**
```
端口: 27017
协议: TCP
来源IP: your_office_ip  # 你的办公室或家庭IP
策略: 放行
备注: MongoDB - 限制IP访问
```

**选项B: 开放所有IP（不推荐生产环境）**
```
端口: 27017
协议: TCP
来源IP: 0.0.0.0/0
策略: 放行
备注: MongoDB - 所有IP可访问
```

### 5.4 验证防火墙规则

在你的本地电脑测试端口连通性：

```bash
# 方法1: telnet
telnet hancens.top 27017

# 方法2: nc (netcat)
nc -zv hancens.top 27017

# 方法3: nmap
nmap -p 27017 hancens.top
```

**成功输出示例**:
```
Connection to hancens.top port 27017 [tcp/*] succeeded!
```

---

## 步骤6: 测试连接

### 6.1 使用MongoDB Compass测试

**下载MongoDB Compass**: https://www.mongodb.com/try/download/compass

**连接字符串**:
```
mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**连接步骤**:
1. 打开MongoDB Compass
2. 粘贴连接字符串
3. 点击 **Connect**
4. 验证能看到 `intelligent_system` 数据库

### 6.2 使用Python测试

创建测试脚本 `test_connection.py`:

```python
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# 连接字符串
MONGODB_URL = "mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system"

try:
    # 连接MongoDB
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)

    # 测试连接
    client.admin.command('ping')
    print("✅ MongoDB连接成功!")

    # 获取数据库
    db = client['intelligent_system']

    # 测试写入
    test_collection = db['connection_test']
    result = test_collection.insert_one({'test': 'connection', 'timestamp': 'now'})
    print(f"✅ 写入测试成功! ID: {result.inserted_id}")

    # 测试读取
    doc = test_collection.find_one({'test': 'connection'})
    print(f"✅ 读取测试成功! 数据: {doc}")

    # 清理测试数据
    test_collection.delete_one({'_id': result.inserted_id})
    print("✅ 清理测试数据成功!")

    # 关闭连接
    client.close()
    print("✅ 所有测试通过!")

except ConnectionFailure:
    print("❌ 连接失败: 无法连接到MongoDB服务器")
    print("   请检查:")
    print("   1. 服务器地址和端口是否正确")
    print("   2. 防火墙是否开放27017端口")
    print("   3. MongoDB服务是否运行")

except OperationFailure as e:
    print(f"❌ 认证失败: {e}")
    print("   请检查:")
    print("   1. 用户名和密码是否正确")
    print("   2. authSource参数是否正确")
    print("   3. 用户权限是否已配置")

except Exception as e:
    print(f"❌ 未知错误: {e}")
```

运行测试：
```bash
python test_connection.py
```

### 6.3 使用项目辅助脚本测试

```bash
python scripts/mongodb_connection_helper.py \
  --connection "mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system" \
  --overview
```

---

## 步骤7: 配置项目环境变量

### 7.1 更新.env文件

编辑项目根目录的 `.env` 文件：

```bash
# MongoDB配置
MONGODB_URL=mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system
MONGODB_DB_NAME=intelligent_system
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10
```

**参数说明**:
- `MONGODB_URL`: 完整的连接字符串
  - 格式: `mongodb://[用户名]:[密码]@[主机]:[端口]/[数据库]?authSource=[认证数据库]`
  - 用户名: `app_user`（步骤4.4创建的）
  - 密码: `your_app_password`（步骤4.4设置的）
  - 主机: `hancens.top`
  - 端口: `27017`
  - 数据库: `intelligent_system`
  - authSource: `intelligent_system`（用户创建时的数据库）

- `MONGODB_DB_NAME`: 数据库名称
- `MONGODB_MAX_POOL_SIZE`: 最大连接池大小（默认100）
- `MONGODB_MIN_POOL_SIZE`: 最小连接池大小（默认10）

### 7.2 验证配置

启动应用程序：
```bash
uvicorn src.main:app --reload
```

检查启动日志：
```
MongoDB连接成功: intelligent_system
数据库索引创建完成
✅ 即时搜索任务索引创建完成
✅ 即时搜索结果索引创建完成
```

### 7.3 测试API端点

访问健康检查端点：
```bash
curl http://localhost:8000/health
```

应该返回：
```json
{
  "status": "ok",
  "database": "connected"
}
```

---

## 🔐 安全最佳实践

### 1. 密码管理

✅ **强密码要求**:
- 至少16个字符
- 包含大小写字母、数字、特殊符号
- 不使用常见密码或字典词汇

❌ **不要**:
- 使用简单密码（如123456、password）
- 在代码中硬编码密码
- 提交.env文件到Git仓库

### 2. 网络安全

✅ **IP白名单**:
```
只允许特定IP访问MongoDB端口
```

✅ **非标准端口**（可选）:
```
将MongoDB端口从27017改为自定义端口（如37017）
在防火墙中配置端口映射
```

✅ **SSL/TLS加密**（推荐生产环境）:
```yaml
# MongoDB配置文件
net:
  ssl:
    mode: requireSSL
    PEMKeyFile: /path/to/mongodb.pem
```

连接字符串添加参数：
```
mongodb://user:pass@host:port/db?authSource=db&ssl=true
```

### 3. 权限管理

✅ **最小权限原则**:
- 应用用户: 只授予readWrite权限
- 分析用户: 只授予read权限
- 不使用root用户连接应用

✅ **定期审计**:
```javascript
// 查看所有用户
use intelligent_system
db.getUsers()

// 查看用户权限
db.getUser("app_user")
```

### 4. 监控和日志

✅ **启用MongoDB日志**:
```yaml
# MongoDB配置文件
systemLog:
  destination: file
  path: /www/server/mongodb/logs/mongodb.log
  logAppend: true
```

✅ **监控连接**:
```javascript
// 查看当前连接
db.currentOp()

// 查看服务器状态
db.serverStatus()
```

---

## 🚨 故障排查

### 问题1: 无法连接到MongoDB

**错误信息**:
```
ConnectionFailure: [Errno 111] Connection refused
或
ServerSelectionTimeoutError
```

**可能原因及解决方案**:

1. **MongoDB服务未运行**
   - 在宝塔面板检查MongoDB运行状态
   - 点击"启动"按钮
   - 查看日志：`/www/server/mongodb/logs/mongodb.log`

2. **防火墙未开放端口**
   - 宝塔面板 → 安全 → 防火墙
   - 添加27017端口规则
   - 检查服务器云平台安全组规则

3. **bindIp配置错误**
   - 检查 `config.conf` 中的 `bindIp`
   - 应设置为 `0.0.0.0` 或包含客户端IP
   - 修改后重启MongoDB

4. **网络连通性问题**
   - 测试: `telnet hancens.top 27017`
   - 测试: `ping hancens.top`
   - 检查本地网络和DNS

### 问题2: 认证失败

**错误信息**:
```
OperationFailure: Authentication failed
```

**可能原因及解决方案**:

1. **用户名或密码错误**
   - 确认用户名拼写正确
   - 确认密码没有多余空格
   - 区分大小写

2. **authSource参数错误**
   - 应与创建用户时的数据库一致
   - 通常是 `admin` 或 `intelligent_system`
   - 示例: `?authSource=intelligent_system`

3. **用户不存在或权限不足**
   ```javascript
   // 检查用户是否存在
   use intelligent_system
   db.getUsers()

   // 重新创建用户
   db.createUser({
     user: "app_user",
     pwd: "your_password",
     roles: [{role: "readWrite", db: "intelligent_system"}]
   })
   ```

4. **认证未启用**
   - 检查MongoDB配置文件
   - 确认 `security.authorization: enabled`
   - 重启MongoDB服务

### 问题3: 连接超时

**错误信息**:
```
pymongo.errors.ServerSelectionTimeoutError: timed out
```

**可能原因及解决方案**:

1. **防火墙规则配置不完整**
   - 检查宝塔面板防火墙
   - 检查云平台安全组（阿里云、腾讯云等）
   - 两者都需要开放端口

2. **MongoDB服务响应慢**
   - 检查服务器资源使用情况
   - 增加连接超时时间:
     ```python
     MongoClient(url, serverSelectionTimeoutMS=10000)
     ```

3. **DNS解析问题**
   - 测试域名解析: `nslookup hancens.top`
   - 尝试使用IP地址代替域名
   - 检查本地DNS设置

### 问题4: 权限不足

**错误信息**:
```
not authorized on intelligent_system to execute command
```

**解决方案**:

```javascript
// 连接到admin数据库（使用admin用户）
use admin
db.auth("admin", "admin_password")

// 切换到目标数据库
use intelligent_system

// 更新用户权限
db.grantRolesToUser("app_user", [
  {role: "readWrite", db: "intelligent_system"}
])

// 验证权限
db.getUser("app_user")
```

### 问题5: 连接字符串格式错误

**常见错误**:

❌ 错误示例:
```
# 缺少authSource
mongodb://user:pass@host:port/db

# 密码包含特殊字符未编码
mongodb://user:p@ss@host:port/db

# 端口号错误
mongodb://user:pass@host:8080/db
```

✅ 正确示例:
```
# 完整格式
mongodb://user:pass@host:27017/db?authSource=db

# 密码URL编码
mongodb://user:p%40ss@host:27017/db?authSource=db

# 正确端口
mongodb://user:pass@host:27017/db?authSource=db
```

**密码特殊字符编码表**:
| 字符 | 编码 |
|------|------|
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `?` | `%3F` |
| `#` | `%23` |
| `&` | `%26` |

---

## 📊 连接信息速查表

### 当前配置

| 项目 | 值 | 说明 |
|------|-----|------|
| **宝塔面板** | | |
| 面板地址 | https://hancens.top:18314/cbece14e | Web管理界面 |
| 面板用户名 | mbjqhmkm | 仅用于登录面板 |
| 面板密码 | asjklquio1z | 仅用于登录面板 |
| **MongoDB服务** | | |
| 服务器地址 | hancens.top | 域名或IP |
| MongoDB端口 | 27017 | 默认端口（需在宝塔确认） |
| 数据库名 | intelligent_system | 应用数据库 |
| **MongoDB用户** | | |
| Admin用户 | admin | 管理员账户 |
| Admin密码 | your_strong_admin_password | 步骤4.2设置 |
| 应用用户 | app_user | 应用程序使用 |
| 应用密码 | your_app_password | 步骤4.4设置 |
| 分析用户 | ai_analyst | 数据分析使用 |
| 分析密码 | your_analyst_password | 步骤4.4设置 |

### 连接字符串模板

**应用程序连接（读写）**:
```
mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**数据分析连接（只读）**:
```
mongodb://ai_analyst:your_analyst_password@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**管理员连接**:
```
mongodb://admin:your_strong_admin_password@hancens.top:27017/admin?authSource=admin
```

### 项目.env配置

```bash
# MongoDB配置
MONGODB_URL=mongodb://app_user:your_app_password@hancens.top:27017/intelligent_system?authSource=intelligent_system
MONGODB_DB_NAME=intelligent_system
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10
```

---

## 📚 相关文档

- **部署指南**: `docs/DEPLOYMENT_BAOTA_MONGODB.md` - 完整的宝塔MongoDB部署文档
- **访问指南**: `docs/MONGODB_ACCESS_GUIDE.md` - 团队成员数据库访问说明
- **连接脚本**: `scripts/mongodb_connection_helper.py` - Python连接测试工具

---

## 📞 技术支持

**配置过程中遇到问题？**

1. 查看本文档的"故障排查"部分
2. 检查MongoDB日志: `/www/server/mongodb/logs/mongodb.log`
3. 参考完整部署文档: `docs/DEPLOYMENT_BAOTA_MONGODB.md`
4. 联系系统管理员

---

**文档版本**: v1.0
**创建日期**: 2025-10-16
**适用环境**: 宝塔面板 + MongoDB
**维护者**: 技术团队
