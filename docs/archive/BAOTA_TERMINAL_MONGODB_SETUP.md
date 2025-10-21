# 宝塔终端创建MongoDB用户指南

**适用场景**: 通过宝塔面板终端快速配置MongoDB
**前提**: 已在宝塔面板安装MongoDB并且服务运行中
**时间**: 5-10分钟

---

## 📋 操作步骤

### 步骤1: 进入宝塔终端

1. **登录宝塔面板**
   ```
   https://hancens.top:18314/cbece14e
   用户名: mbjqhmkm
   密码: asjklquio1z
   ```

2. **打开终端**
   - 方式A: 左侧菜单 → **终端**
   - 方式B: 软件商店 → MongoDB → 设置 → **终端**

---

### 步骤2: 连接MongoDB（首次无需密码）

在终端中输入：

```bash
# 如果MongoDB在宝塔默认路径
/www/server/mongodb/bin/mongosh

# 或者使用系统路径（如果添加到PATH）
mongosh

# 旧版MongoDB使用
mongo
```

**成功标志**：
```
Current Mongosh Log ID: xxx
Connecting to: mongodb://127.0.0.1:27017/
Using MongoDB: 6.0.x
test>
```

---

### 步骤3: 创建管理员用户

在MongoDB Shell中复制粘贴以下命令：

```javascript
// 切换到admin数据库



// 创建超级管理员（复制整个代码块，一次性粘贴）
db.createUser({
  user: "admin",
  pwd: "Admin@Guanshan2024!",  // ⚠️ 建议修改为你的强密码
  roles: [
    { role: "root", db: "admin" }
  ]
})
```

**成功输出**：
```javascript
{ ok: 1 }
```

**记录信息**：
```
管理员用户名: admin
管理员密码: Admin@Guanshan2024!  (或你自己设置的密码)
```

---

### 步骤4: 创建应用数据库和用户

继续在MongoDB Shell中执行：

```javascript
// 切换到应用数据库
use intelligent_system

// 创建应用读写用户（完整代码块）
db.createUser({
  user: "app_user",
  pwd: "AppUser@Guanshan2024!",  // ⚠️ 建议修改为你的强密码
  roles: [
    { role: "readWrite", db: "intelligent_system" }
  ]
})
```

**成功输出**：
```javascript
{ ok: 1 }
```

**创建只读用户（供数据分析）**：

```javascript
// 仍在 intelligent_system 数据库中
db.createUser({
  user: "ai_analyst",
  pwd: "Analyst@Guanshan2024!",  // ⚠️ 建议修改为你的强密码
  roles: [
    { role: "read", db: "intelligent_system" }
  ]
})
```

**成功输出**：
```javascript
{ ok: 1 }
```

---

### 步骤5: 验证用户创建

查看创建的用户：

```javascript
// 查看当前数据库的所有用户
db.getUsers()
```

**预期输出**：
```javascript
{
  users: [
    {
      _id: 'intelligent_system.app_user',
      userId: UUID("..."),
      user: 'app_user',
      db: 'intelligent_system',
      roles: [ { role: 'readWrite', db: 'intelligent_system' } ]
    },
    {
      _id: 'intelligent_system.ai_analyst',
      userId: UUID("..."),
      user: 'ai_analyst',
      db: 'intelligent_system',
      roles: [ { role: 'read', db: 'intelligent_system' } ]
    }
  ],
  ok: 1
}
```

退出MongoDB Shell：
```javascript
exit
```

---

### 步骤6: 修改MongoDB配置启用认证

在宝塔终端执行：

```bash
# 编辑MongoDB配置文件
vi /www/server/mongodb/config.conf
```

**找到并修改以下配置**：

```yaml
# 网络配置 - 允许远程访问
net:
  port: 27017
  bindIp: 0.0.0.0  # 修改这行，从 127.0.0.1 改为 0.0.0.0

# 安全配置 - 启用认证
security:
  authorization: enabled  # 添加或确认这两行存在
```

**vi编辑器操作提示**：
- 按 `i` 进入编辑模式
- 使用方向键移动光标
- 修改完成后按 `Esc`
- 输入 `:wq` 回车保存退出
- 如果不保存退出输入 `:q!`

**或者使用nano编辑器（更友好）**：
```bash
nano /www/server/mongodb/config.conf
```
- 修改后按 `Ctrl + O` 保存
- 按 `Enter` 确认
- 按 `Ctrl + X` 退出

---

### 步骤7: 重启MongoDB服务

在宝塔终端执行：

```bash
# 方法1: 使用systemctl
systemctl restart mongod

# 方法2: 如果上面失败，用宝塔MongoDB管理
# 在面板: 软件商店 → MongoDB → 设置 → 重启

# 验证服务运行
systemctl status mongod
```

**成功标志**：
```
● mongod.service - MongoDB Database Server
   Loaded: loaded
   Active: active (running)
```

按 `q` 退出状态查看。

---

### 步骤8: 测试认证登录

在终端测试新创建的用户：

```bash
# 测试管理员用户
/www/server/mongodb/bin/mongosh -u admin -p "Admin@Guanshan2024!" --authenticationDatabase admin

# 测试应用用户
/www/server/mongodb/bin/mongosh -u app_user -p "AppUser@Guanshan2024!" --authenticationDatabase intelligent_system

# 测试分析用户
/www/server/mongodb/bin/mongosh -u ai_analyst -p "Analyst@Guanshan2024!" --authenticationDatabase intelligent_system
```

**成功登录标志**：
```
Current Mongosh Log ID: xxx
Connecting to: mongodb://127.0.0.1:27017/?authSource=intelligent_system
Using MongoDB: 6.0.x
intelligent_system>
```

在MongoDB Shell中测试权限：

```javascript
// 测试app_user（应该可以写入）
db.test_collection.insertOne({test: "data"})
// 输出: { acknowledged: true, insertedId: ObjectId("...") }

db.test_collection.find()
// 输出: [ { _id: ObjectId("..."), test: 'data' } ]

db.test_collection.deleteOne({test: "data"})
// 输出: { acknowledged: true, deletedCount: 1 }

// 测试ai_analyst（只读，写入应该失败）
db.test_collection.insertOne({test: "data"})
// 输出: MongoServerError: not authorized on intelligent_system to execute command

exit
```

---

### 步骤9: 配置防火墙开放端口

在宝塔终端执行：

```bash
# 检查MongoDB端口是否监听
netstat -tuln | grep 27017
```

**预期输出**：
```
tcp        0      0 0.0.0.0:27017           0.0.0.0:*               LISTEN
```

**在宝塔面板配置防火墙**：

1. 左侧菜单 → **安全**
2. 点击 **添加规则**
3. 填写：
   ```
   端口: 27017
   协议: TCP
   策略: 放行
   备注: MongoDB数据库
   ```
4. 点击 **提交**

**（可选）配置IP白名单**：

如果要限制只有特定IP访问（推荐）：
```bash
# 在终端使用iptables
iptables -A INPUT -p tcp --dport 27017 -s YOUR_OFFICE_IP -j ACCEPT
iptables -A INPUT -p tcp --dport 27017 -j DROP

# 保存规则
service iptables save
```

或在宝塔面板安全设置中，为27017端口指定允许的IP地址。

---

### 步骤10: 测试远程连接

从你的本地电脑测试连接：

#### 方法1: 使用telnet测试端口

```bash
# 在你的本地电脑终端执行
telnet hancens.top 27017
```

**成功输出**：
```
Trying xxx.xxx.xxx.xxx...
Connected to hancens.top.
```

按 `Ctrl + ]` 然后输入 `quit` 退出。

#### 方法2: 使用Python测试

创建文件 `test_baota_mongodb.py`：

```python
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# 连接信息
HOST = "hancens.top"
PORT = 27017
USERNAME = "app_user"
PASSWORD = "AppUser@Guanshan2024!"  # 使用你设置的密码
DATABASE = "intelligent_system"

# 连接字符串
MONGODB_URL = f"mongodb://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}?authSource={DATABASE}"

print(f"正在连接MongoDB...")
print(f"服务器: {HOST}:{PORT}")
print(f"数据库: {DATABASE}")
print(f"用户: {USERNAME}")
print("-" * 60)

try:
    # 连接
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)

    # 测试连接
    client.admin.command('ping')
    print("✅ 连接成功!")

    # 获取数据库
    db = client[DATABASE]

    # 测试写入
    print("\n测试写入权限...")
    result = db.connection_test.insert_one({
        'test': 'remote_connection',
        'from': 'local_computer',
        'timestamp': 'now'
    })
    print(f"✅ 写入成功! ID: {result.inserted_id}")

    # 测试读取
    print("\n测试读取权限...")
    doc = db.connection_test.find_one({'test': 'remote_connection'})
    print(f"✅ 读取成功! 数据: {doc}")

    # 清理测试数据
    db.connection_test.delete_one({'_id': result.inserted_id})
    print("✅ 清理测试数据成功!")

    # 显示数据库信息
    print("\n数据库信息:")
    print(f"可用集合: {db.list_collection_names()}")

    client.close()
    print("\n✅ 所有测试通过! MongoDB远程连接配置成功!")

except ConnectionFailure:
    print("❌ 连接失败!")
    print("\n可能的原因:")
    print("1. 防火墙未开放27017端口")
    print("2. MongoDB bindIp配置错误")
    print("3. 服务器安全组规则未配置")
    print("4. 网络连通性问题")

except OperationFailure as e:
    print(f"❌ 认证失败: {e}")
    print("\n可能的原因:")
    print("1. 用户名或密码错误")
    print("2. authSource参数错误")
    print("3. 用户权限未正确配置")

except Exception as e:
    print(f"❌ 未知错误: {e}")
```

运行测试：
```bash
python test_baota_mongodb.py
```

#### 方法3: 使用MongoDB Compass

1. 下载 [MongoDB Compass](https://www.mongodb.com/try/download/compass)
2. 连接字符串：
   ```
   mongodb://app_user:AppUser@Guanshan2024!@hancens.top:27017/intelligent_system?authSource=intelligent_system
   ```

   **注意**: 如果密码包含特殊字符，需要URL编码：
   - `@` → `%40`
   - `!` → `%21`

   编码后：
   ```
   mongodb://app_user:AppUser%40Guanshan2024%21@hancens.top:27017/intelligent_system?authSource=intelligent_system
   ```

3. 点击 **Connect**
4. 成功后应该看到 `intelligent_system` 数据库

---

## 📊 配置信息汇总

### 创建的用户信息

| 用户名 | 密码 | 权限 | 用途 |
|--------|------|------|------|
| `admin` | `Admin@Guanshan2024!` | root | 数据库管理 |
| `app_user` | `AppUser@Guanshan2024!` | readWrite | 应用程序连接 |
| `ai_analyst` | `Analyst@Guanshan2024!` | read | 数据分析 |

⚠️ **安全提醒**: 请修改为你自己的强密码！

### 连接字符串

**应用程序连接**：
```
mongodb://app_user:AppUser@Guanshan2024!@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**数据分析连接**：
```
mongodb://ai_analyst:Analyst@Guanshan2024!@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**管理员连接**：
```
mongodb://admin:Admin@Guanshan2024!@hancens.top:27017/admin?authSource=admin
```

### 项目环境变量配置

编辑项目的 `.env` 文件：

```bash
# MongoDB配置
MONGODB_URL=mongodb://app_user:AppUser@Guanshan2024!@hancens.top:27017/intelligent_system?authSource=intelligent_system
MONGODB_DB_NAME=intelligent_system
MONGODB_MAX_POOL_SIZE=100
MONGODB_MIN_POOL_SIZE=10
```

---

## 🔍 故障排查

### 问题1: 找不到mongosh命令

**原因**: MongoDB路径未添加到PATH

**解决**：
```bash
# 使用完整路径
/www/server/mongodb/bin/mongosh

# 或添加到PATH
echo 'export PATH=$PATH:/www/server/mongodb/bin' >> ~/.bashrc
source ~/.bashrc
```

### 问题2: 创建用户失败 - 需要认证

**错误信息**：
```
MongoServerError: command createUser requires authentication
```

**原因**: 已启用认证但未以管理员身份登录

**解决**：
```bash
# 先用管理员登录
mongosh -u admin -p "Admin@Guanshan2024!" --authenticationDatabase admin

# 然后切换数据库创建用户
use intelligent_system
db.createUser({...})
```

### 问题3: 远程连接失败

**错误信息**：
```
ServerSelectionTimeoutError: connection refused
```

**检查清单**：
```bash
# 1. 检查MongoDB运行状态
systemctl status mongod

# 2. 检查bindIp配置
grep "bindIp" /www/server/mongodb/config.conf
# 应该显示: bindIp: 0.0.0.0

# 3. 检查防火墙
netstat -tuln | grep 27017

# 4. 测试端口开放（从本地电脑）
telnet hancens.top 27017
```

### 问题4: 认证失败

**错误信息**：
```
Authentication failed
```

**解决步骤**：
```bash
# 1. 重新连接MongoDB确认用户
mongosh -u admin -p "Admin@Guanshan2024!" --authenticationDatabase admin

# 2. 切换数据库
use intelligent_system

# 3. 检查用户是否存在
db.getUsers()

# 4. 测试密码
db.auth("app_user", "AppUser@Guanshan2024!")
# 返回 { ok: 1 } 表示密码正确

# 5. 如果密码错误，重置密码
db.updateUser("app_user", {
  pwd: "NewPassword@2024!"
})
```

---

## ✅ 配置完成检查清单

- [ ] 成功登录宝塔终端
- [ ] 创建admin管理员用户
- [ ] 创建app_user应用用户
- [ ] 创建ai_analyst分析用户
- [ ] 验证用户创建成功（db.getUsers()）
- [ ] 修改bindIp为0.0.0.0
- [ ] 启用认证（authorization: enabled）
- [ ] 重启MongoDB服务
- [ ] 测试本地认证登录成功
- [ ] 开放防火墙27017端口
- [ ] 测试远程端口连通性（telnet）
- [ ] 测试远程认证连接成功
- [ ] 更新项目.env文件
- [ ] 启动应用验证连接正常

---

## 📚 下一步

配置完成后，你可以：

1. **启动应用程序**
   ```bash
   cd /path/to/guanshanPython
   uvicorn src.main:app --reload
   ```

2. **使用MongoDB Compass** 可视化管理数据库

3. **团队成员访问** 参考 `docs/MONGODB_ACCESS_GUIDE.md`

4. **AI分析工具集成** 参考 `docs/DEPLOYMENT_BAOTA_MONGODB.md` 的AI工具示例

---

**配置时间**: 5-10分钟
**难度**: ⭐⭐ (简单)
**创建日期**: 2025-10-16
