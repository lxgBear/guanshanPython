# SSH 隧道连接测试指南

**日期**: 2025-12-03
**目的**: 验证 SSH 隧道方案的可行性
**状态**: 📋 测试准备中

---

## 🎯 测试目标

验证通过 SSH 隧道连接 MongoDB 是否可以解决认证失败问题。

---

## 📋 前提条件检查

### 1. SSH 服务器访问权限

**目标服务器**: `47.108.154.217`

**需要确认的信息**:
```bash
# 1. SSH 用户名
# 常见用户名: root, ubuntu, centos, admin, 或自定义用户名

# 2. SSH 端口（默认 22，可能被修改）
# 默认: 22

# 3. 认证方式
# - 密码认证
# - SSH 密钥认证
```

**测试命令**:
```bash
# 测试 SSH 连接（请替换 YOUR_USERNAME）
ssh YOUR_USERNAME@47.108.154.217

# 如果端口不是 22
ssh -p 2222 YOUR_USERNAME@47.108.154.217

# 如果使用密钥认证
ssh -i ~/.ssh/id_rsa YOUR_USERNAME@47.108.154.217
```

**预期结果**:
- ✅ 成功：进入服务器命令行
- ❌ 失败：Connection refused, Permission denied, 或 Timeout

---

## 🧪 测试步骤

### 步骤 1: 验证 SSH 基础连接

**目的**: 确认可以通过 SSH 访问目标服务器

```bash
# 1. 测试 SSH 连接（详细模式）
ssh -v YOUR_USERNAME@47.108.154.217

# 观察输出，确认：
# - SSH 协议版本
# - 认证方式
# - 连接是否成功
```

**成功标志**:
```
OpenSSH_X.X
debug1: Authentication succeeded
Welcome to Ubuntu XX.XX LTS
```

**失败处理**:
- 如果提示 "Connection refused" → 检查 SSH 服务是否运行，端口是否正确
- 如果提示 "Permission denied" → 检查用户名、密码或密钥
- 如果提示 "Connection timeout" → 检查网络连接和防火墙

---

### 步骤 2: 创建 SSH 隧道

**目的**: 建立从本地到 MongoDB 的 SSH 隧道

```bash
# 创建 SSH 隧道（后台运行）
ssh -fN -L 27017:localhost:27017 YOUR_USERNAME@47.108.154.217

# 参数说明:
# -f: 后台运行
# -N: 不执行远程命令
# -L 27017:localhost:27017: 本地端口转发
#    本地27017 → SSH服务器 → MongoDB的localhost:27017
```

**验证隧道创建**:
```bash
# 检查本地 27017 端口是否监听
lsof -i :27017

# 预期输出应包含 SSH 进程
# COMMAND   PID   USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
# ssh       XXXXX  user   3u  IPv4  XXXXXX      0t0  TCP localhost:27017 (LISTEN)
```

**成功标志**:
- ✅ lsof 显示 SSH 进程监听 27017 端口
- ✅ 无错误消息

---

### 步骤 3: 测试本地端口连通性

**目的**: 验证本地 27017 端口可以访问

```bash
# 使用 netcat 测试端口
nc -zv localhost 27017

# 预期输出:
# Connection to localhost port 27017 [tcp/*] succeeded!
```

**成功标志**:
- ✅ 输出 "Connection succeeded"

---

### 步骤 4: 测试 MongoDB 连接（Python）

**目的**: 验证 Python 应用可以通过隧道连接 MongoDB

**创建测试脚本**: `test_ssh_tunnel.py`

```python
#!/usr/bin/env python3
"""
SSH 隧道 MongoDB 连接测试
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_mongodb_connection():
    """测试 MongoDB 连接"""

    print("=" * 60)
    print("MongoDB SSH 隧道连接测试")
    print("=" * 60)

    # 通过 SSH 隧道连接（连接本地 27017）
    mongodb_url = "mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27017/?authSource=admin"

    print(f"\n🔍 测试连接: localhost:27017")
    print(f"   (通过 SSH 隧道到 47.108.154.217)")

    try:
        # 创建客户端
        client = AsyncIOMotorClient(
            mongodb_url,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000
        )

        # 1. 测试 ping
        print("\n📡 步骤 1: 测试 ping...")
        result = await client.admin.command('ping')
        print(f"   ✅ Ping 成功: {result}")

        # 2. 列出数据库
        print("\n📊 步骤 2: 列出数据库...")
        databases = await client.list_database_names()
        print(f"   ✅ 数据库列表: {databases}")

        # 3. 检查目标数据库
        print("\n🎯 步骤 3: 检查 guanshan 数据库...")
        if 'guanshan' in databases:
            db = client.guanshan
            collections = await db.list_collection_names()
            print(f"   ✅ guanshan 数据库存在")
            print(f"   ✅ 集合数量: {len(collections)}")
            if collections:
                print(f"   ✅ 集合列表: {collections[:5]}...")  # 只显示前5个
        else:
            print(f"   ⚠️  guanshan 数据库不存在")

        # 4. 测试写入权限（可选）
        print("\n✍️  步骤 4: 测试写入权限...")
        test_db = client.guanshan
        test_collection = test_db.test_ssh_tunnel

        test_doc = {
            "test_type": "ssh_tunnel_connection",
            "timestamp": "2025-12-03",
            "status": "success"
        }

        result = await test_collection.insert_one(test_doc)
        print(f"   ✅ 写入测试成功: {result.inserted_id}")

        # 清理测试数据
        await test_collection.delete_one({"_id": result.inserted_id})
        print(f"   ✅ 测试数据已清理")

        # 关闭连接
        client.close()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！SSH 隧道连接成功！")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 连接失败!")
        print(f"   错误类型: {type(e).__name__}")
        print(f"   错误详情: {str(e)}")
        print("\n" + "=" * 60)
        print("❌ 测试失败")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mongodb_connection())
    exit(0 if success else 1)
```

**运行测试**:
```bash
# 运行测试脚本
python3 test_ssh_tunnel.py
```

**预期输出（成功）**:
```
============================================================
MongoDB SSH 隧道连接测试
============================================================

🔍 测试连接: localhost:27017
   (通过 SSH 隧道到 47.108.154.217)

📡 步骤 1: 测试 ping...
   ✅ Ping 成功: {'ok': 1.0}

📊 步骤 2: 列出数据库...
   ✅ 数据库列表: ['admin', 'config', 'guanshan', 'local']

🎯 步骤 3: 检查 guanshan 数据库...
   ✅ guanshan 数据库存在
   ✅ 集合数量: 10
   ✅ 集合列表: ['collection1', 'collection2', ...]

✍️  步骤 4: 测试写入权限...
   ✅ 写入测试成功: 675e...
   ✅ 测试数据已清理

============================================================
✅ 所有测试通过！SSH 隧道连接成功！
============================================================
```

---

### 步骤 5: 更新应用配置并测试

**目的**: 验证应用可以使用 SSH 隧道连接

**5.1 备份当前配置**:
```bash
# 备份 .env 文件
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

**5.2 更新配置**:
```bash
# 编辑 .env 文件
# 将 MONGODB_URL 修改为 localhost

# 修改前:
# MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@47.108.154.217:27017/?authSource=admin

# 修改后:
# MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27017/?authSource=admin
```

**5.3 重启应用**:
```bash
# 停止现有服务
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 启动服务
./start_server.sh
```

**5.4 检查日志**:
```bash
# 查看启动日志
tail -f server.log

# 期望看到:
# ✅ MongoDB连接成功: guanshan
# ✅ 系统启动成功
```

---

## 📊 测试结果记录

### 测试环境

| 项目 | 信息 |
|------|------|
| 测试日期 | 2025-12-03 |
| 本地环境 | macOS Darwin 24.5.0 |
| Python 版本 | 3.13.0 |
| SSH 目标 | 47.108.154.217 |
| MongoDB 版本 | 8.2.2 (Docker) |

### 测试结果

| 步骤 | 测试项 | 结果 | 备注 |
|------|--------|------|------|
| 1 | SSH 基础连接 | ⬜ 待测试 | |
| 2 | SSH 隧道创建 | ⬜ 待测试 | |
| 3 | 本地端口连通性 | ⬜ 待测试 | |
| 4 | MongoDB Python 连接 | ⬜ 待测试 | |
| 5 | 应用集成测试 | ⬜ 待测试 | |

**结果说明**:
- ✅ 通过
- ❌ 失败
- ⚠️ 部分通过
- ⬜ 待测试

---

## 🐛 故障排查

### 问题 1: SSH 连接失败

**症状**: `Connection refused` 或 `Connection timeout`

**排查步骤**:
```bash
# 1. 检查网络连接
ping 47.108.154.217

# 2. 检查 SSH 端口
nc -zv 47.108.154.217 22

# 3. 尝试不同端口
nc -zv 47.108.154.217 2222
```

**可能原因**:
- SSH 服务未运行
- 防火墙阻止连接
- 端口号错误

---

### 问题 2: SSH 认证失败

**症状**: `Permission denied`

**排查步骤**:
```bash
# 1. 确认用户名正确
# 联系服务器管理员确认

# 2. 如果使用密钥认证，检查密钥权限
chmod 600 ~/.ssh/id_rsa
ls -la ~/.ssh/id_rsa

# 3. 检查 SSH 密钥是否正确
ssh-keygen -l -f ~/.ssh/id_rsa
```

---

### 问题 3: 端口已被占用

**症状**: `bind: Address already in use`

**解决方案**:
```bash
# 1. 找到占用端口的进程
lsof -i :27017

# 2. 停止该进程
kill -9 <PID>

# 3. 或使用不同的本地端口
ssh -fN -L 27018:localhost:27017 YOUR_USERNAME@47.108.154.217

# 相应修改 .env:
# MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27018/?authSource=admin
```

---

### 问题 4: MongoDB 仍然认证失败

**症状**: `Authentication failed (code 18)`

**可能原因**:
1. MongoDB 未监听 127.0.0.1
2. Docker 容器网络配置问题

**排查步骤**:
```bash
# 在 SSH 服务器上检查 MongoDB 配置
ssh YOUR_USERNAME@47.108.154.217

# 检查 MongoDB 是否监听 localhost
docker exec mongodb_zh5s-mongodb_zh5s-1 netstat -tlnp | grep 27017

# 应该看到:
# tcp        0      0 127.0.0.1:27017         0.0.0.0:*               LISTEN

# 检查 MongoDB 配置
docker exec mongodb_zh5s-mongodb_zh5s-1 cat /etc/mongod.conf | grep bindIp

# 应该包含 127.0.0.1:
# bindIp: 127.0.0.1,0.0.0.0
```

---

## ✅ 成功标准

SSH 隧道方案测试成功需满足以下条件：

1. ✅ SSH 连接成功建立
2. ✅ SSH 隧道正常运行（本地 27017 端口监听）
3. ✅ Python 脚本可以连接 MongoDB
4. ✅ 可以列出数据库和集合
5. ✅ 具有读写权限
6. ✅ 应用启动成功并正常运行

---

## 📝 下一步行动

### 如果测试成功

1. **记录 SSH 凭据** - 安全存储 SSH 连接信息
2. **创建自动化脚本** - 使用提供的 `start_ssh_tunnel.sh`
3. **配置开机自启** - 设置 systemd 或 launchd 服务
4. **计划永久方案** - 与服务器管理员协调配置 IP 白名单

### 如果测试失败

1. **分析失败原因** - 查看详细错误日志
2. **尝试替代方案** - 考虑其他连接方式
3. **联系服务器管理员** - 请求 IP 白名单配置
4. **考虑其他方案** - VPN、跳板机等

---

## 📚 相关文档

- [SSH 隧道完整解决方案](./SSH_TUNNEL_SOLUTION.md)
- [MongoDB 连接问题最终方案](./MONGODB_CONNECTION_FIX_FINAL.md)
- [Navicat 连接配置分析](./NAVICAT_CONNECTION_ANALYSIS.md)

---

**创建时间**: 2025-12-03
**测试状态**: 📋 等待执行
**优先级**: ⚠️ 高
