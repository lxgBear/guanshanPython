# SSH 隧道临时解决方案

**日期**: 2025-12-03
**目的**: 通过 SSH 隧道绕过 MongoDB IP 白名单限制
**状态**: ⚠️ 临时方案（推荐用于开发测试）

---

## 📋 问题回顾

### 当前状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 网络连接 | ✅ 成功 | 47.108.154.217:27017 可达 |
| Navicat 认证 | ✅ 成功 | 使用相同凭据可连接 |
| Python Motor 认证 | ❌ 失败 | Authentication failed (code 18) |

### 根本原因

**IP 白名单限制**: MongoDB 服务器配置了 IP 白名单，允许 Navicat 的连接源 IP，但不允许当前 Python 客户端的 IP。

---

## 🔧 SSH 隧道解决方案

### 方案原理

```
┌─────────────┐    SSH隧道    ┌──────────────┐    直连    ┌──────────────┐
│ Python 应用 │ ──────────→ │ SSH 跳板机   │ ────────→ │ MongoDB      │
│ localhost   │              │ 47.108.154.217│           │ 127.0.0.1    │
│ :27017      │              │              │           │ :27017       │
└─────────────┘              └──────────────┘           └──────────────┘
```

**工作流程**：
1. 在本地机器创建 SSH 隧道到 MongoDB 服务器
2. 本地 27017 端口映射到远程 MongoDB 的 127.0.0.1:27017
3. Python 应用连接本地 localhost:27017
4. 流量通过 SSH 加密传输到 MongoDB 服务器
5. MongoDB 看到的连接来自 127.0.0.1（本地回环），必定在白名单中

---

## 🚀 实施步骤

### 前提条件

1. **SSH 访问权限**: 拥有 MongoDB 服务器（47.108.154.217）的 SSH 访问权限
2. **MongoDB 凭据**: username=mongodb, password=hhLBknn7dEhzJK78
3. **本地端口**: 本地 27017 端口未被占用

### 步骤 1: 检查 SSH 访问

```bash
# 测试 SSH 连接
ssh user@47.108.154.217

# 如果需要指定端口
ssh -p 22 user@47.108.154.217

# 如果使用密钥认证
ssh -i ~/.ssh/id_rsa user@47.108.154.217
```

**常见 SSH 用户名**:
- `root`
- `ubuntu`（Ubuntu 系统）
- `centos`（CentOS 系统）
- `admin`
- 自定义用户名

### 步骤 2: 创建 SSH 隧道

#### 方式 1: 手动创建（推荐用于测试）

```bash
# 创建 SSH 隧道
ssh -L 27017:localhost:27017 user@47.108.154.217

# 解释:
# -L 27017:localhost:27017
#    本地端口:远程主机:远程端口
#    将本地 27017 映射到远程的 localhost:27017
```

**参数说明**:
- `-L`: 本地端口转发
- `27017`: 本地监听端口
- `localhost:27017`: 远程 MongoDB 地址（从 SSH 服务器视角）
- `user@47.108.154.217`: SSH 服务器地址

#### 方式 2: 后台运行（推荐用于长期使用）

```bash
# 后台运行 SSH 隧道
ssh -fN -L 27017:localhost:27017 user@47.108.154.217

# 参数说明:
# -f: 后台运行
# -N: 不执行远程命令（只转发端口）
# -L: 本地端口转发
```

#### 方式 3: 使用 autossh（推荐用于生产环境）

```bash
# 安装 autossh (macOS)
brew install autossh

# 使用 autossh 创建自动重连的隧道
autossh -M 0 -fN -L 27017:localhost:27017 user@47.108.154.217

# 参数说明:
# -M 0: 监控端口（0 表示不使用额外的监控端口）
# -f: 后台运行
# -N: 不执行远程命令
# -L: 本地端口转发
```

**autossh 优势**:
- 自动检测连接断开
- 自动重新建立连接
- 适合长期稳定运行

### 步骤 3: 验证隧道连接

```bash
# 测试本地端口是否监听
nc -zv localhost 27017

# 预期输出:
# Connection to localhost port 27017 [tcp/*] succeeded!
```

### 步骤 4: 修改 Python 应用配置

**编辑 `.env` 文件**:

```bash
# 原配置（直连远程）
# MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@47.108.154.217:27017/?authSource=admin

# 新配置（通过 SSH 隧道）
MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27017/?authSource=admin

# 注意:
# 1. 主机地址改为 localhost
# 2. 端口保持 27017
# 3. 凭据和参数保持不变
```

### 步骤 5: 测试 MongoDB 连接

```bash
# 测试 Python 连接
python3 -c "
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def test():
    client = AsyncIOMotorClient('mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27017/?authSource=admin')
    result = await client.admin.command('ping')
    print('✅ MongoDB 连接成功:', result)

    # 列出数据库
    dbs = await client.list_database_names()
    print('✅ 数据库列表:', dbs)

    client.close()

asyncio.run(test())
"
```

### 步骤 6: 启动应用

```bash
# 重启应用服务
./start_server.sh

# 检查日志
tail -f server.log
```

---

## 🛡️ 安全考虑

### SSH 密钥认证（推荐）

**生成 SSH 密钥**:
```bash
# 生成 SSH 密钥对
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 复制公钥到服务器
ssh-copy-id user@47.108.154.217
```

**配置 SSH 免密登录**:
```bash
# 编辑 ~/.ssh/config
cat >> ~/.ssh/config <<EOF
Host mongodb-server
    HostName 47.108.154.217
    User your_username
    IdentityFile ~/.ssh/id_rsa
    LocalForward 27017 localhost:27017
EOF

# 使用配置连接
ssh -fN mongodb-server
```

### 防火墙配置

**本地防火墙**:
```bash
# macOS - 允许本地 27017 端口
# 系统偏好设置 → 安全性与隐私 → 防火墙 → 防火墙选项
# 添加 Python 和应用到允许列表
```

**SSH 服务器防火墙**:
```bash
# 在 SSH 服务器上，确保 MongoDB 端口仅允许本地连接
sudo ufw status
sudo ufw allow from 127.0.0.1 to any port 27017
```

---

## 🔍 故障排查

### 问题 1: SSH 连接失败

**错误**: `Connection refused` 或 `Permission denied`

**解决方案**:
```bash
# 1. 检查 SSH 服务状态
ssh -v user@47.108.154.217

# 2. 确认用户名和密码/密钥
ssh -i ~/.ssh/id_rsa user@47.108.154.217

# 3. 检查 SSH 端口（可能不是默认的 22）
ssh -p 2222 user@47.108.154.217
```

### 问题 2: 端口已被占用

**错误**: `bind: Address already in use`

**解决方案**:
```bash
# 1. 查找占用端口的进程
lsof -i :27017

# 2. 杀死占用端口的进程
kill -9 <PID>

# 3. 或使用不同的本地端口
ssh -L 27018:localhost:27017 user@47.108.154.217

# 相应修改 .env
# MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27018/?authSource=admin
```

### 问题 3: 隧道断开

**错误**: Python 应用连接超时

**解决方案**:
```bash
# 1. 检查 SSH 隧道进程
ps aux | grep ssh

# 2. 使用 autossh 自动重连
autossh -M 0 -fN -L 27017:localhost:27017 user@47.108.154.217

# 3. 配置 SSH 保持连接
cat >> ~/.ssh/config <<EOF
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF
```

### 问题 4: MongoDB 认证仍然失败

**错误**: `Authentication failed (code 18)`

**可能原因**:
- MongoDB 配置 `bindIp` 不包含 127.0.0.1
- MongoDB 用户仅允许特定 IP 连接

**解决方案**:
```bash
# 在 MongoDB 服务器上检查配置
ssh user@47.108.154.217

# 检查 MongoDB 配置
sudo cat /etc/mongod.conf | grep bindIp

# 应该包含:
# net:
#   bindIp: 127.0.0.1,0.0.0.0

# 检查 MongoDB 用户配置
docker exec -it mongodb_zh5s-mongodb_zh5s-1 mongosh -u mongodb -p hhLBknn7dEhzJK78 --authenticationDatabase admin

# 在 mongosh 中:
use admin
db.getUser("mongodb")

# 检查是否有 authenticationRestrictions
# 如果有，移除或添加 127.0.0.1
```

---

## ⚙️ 自动化部署

### 创建启动脚本

**文件**: `start_ssh_tunnel.sh`

```bash
#!/bin/bash

# SSH 隧道配置
SSH_USER="your_username"
SSH_HOST="47.108.154.217"
LOCAL_PORT=27017
REMOTE_HOST="localhost"
REMOTE_PORT=27017

# 检查隧道是否已运行
if lsof -i :${LOCAL_PORT} > /dev/null 2>&1; then
    echo "⚠️  端口 ${LOCAL_PORT} 已被占用"
    read -p "是否关闭现有连接? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PID=$(lsof -ti :${LOCAL_PORT})
        kill -9 $PID
        echo "✅ 已关闭端口 ${LOCAL_PORT} 的进程"
        sleep 2
    else
        exit 1
    fi
fi

# 创建 SSH 隧道
echo "🔄 正在创建 SSH 隧道..."
ssh -fN -L ${LOCAL_PORT}:${REMOTE_HOST}:${REMOTE_PORT} ${SSH_USER}@${SSH_HOST}

# 验证隧道
sleep 2
if lsof -i :${LOCAL_PORT} > /dev/null 2>&1; then
    echo "✅ SSH 隧道已成功创建"
    echo "📊 本地端口: ${LOCAL_PORT}"
    echo "🔗 远程地址: ${SSH_HOST}:${REMOTE_PORT}"
else
    echo "❌ SSH 隧道创建失败"
    exit 1
fi
```

**使用方法**:
```bash
# 添加执行权限
chmod +x start_ssh_tunnel.sh

# 启动隧道
./start_ssh_tunnel.sh
```

### systemd 服务（Linux 生产环境）

**文件**: `/etc/systemd/system/mongodb-tunnel.service`

```ini
[Unit]
Description=MongoDB SSH Tunnel
After=network.target

[Service]
Type=simple
User=your_username
ExecStart=/usr/bin/ssh -N -L 27017:localhost:27017 user@47.108.154.217
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**管理服务**:
```bash
# 启动服务
sudo systemctl start mongodb-tunnel

# 设置开机自启
sudo systemctl enable mongodb-tunnel

# 查看状态
sudo systemctl status mongodb-tunnel
```

---

## 📈 性能考虑

### 延迟影响

| 连接方式 | 平均延迟 | 适用场景 |
|---------|---------|---------|
| 直连 | 5-20ms | 生产环境 |
| SSH 隧道（本地网络） | 10-30ms | 开发测试 |
| SSH 隧道（跨网络） | 50-200ms | 远程开发 |

### 带宽消耗

**SSH 加密开销**: ~10-15% CPU 和带宽
**适用场景**:
- ✅ 低频数据库操作
- ✅ 开发测试环境
- ⚠️ 高频查询（需评估性能）
- ❌ 大数据量传输（不推荐）

---

## 🎯 推荐使用场景

### ✅ 适用场景

1. **开发测试环境**: 临时访问生产数据库
2. **调试排查**: 需要快速连接数据库定位问题
3. **跨网络访问**: 本地开发机无法直接访问 MongoDB
4. **安全隔离**: 数据库不对公网开放

### ⚠️ 不适用场景

1. **生产环境**: 应该配置正确的 IP 白名单
2. **高并发场景**: SSH 加密会增加延迟和 CPU 开销
3. **大数据传输**: 不适合大量数据导入导出
4. **长期运行**: 应该作为临时方案，不是长期架构

---

## 🔄 从临时方案迁移到永久方案

### 永久解决方案

**最佳实践**: 在 MongoDB 服务器上配置 IP 白名单

```bash
# 1. 确定 Python 应用的公网 IP
curl ifconfig.me

# 2. 在 MongoDB 服务器上配置用户 IP 限制
docker exec -it mongodb_zh5s-mongodb_zh5s-1 mongosh -u mongodb -p hhLBknn7dEhzJK78 --authenticationDatabase admin

# 3. 在 mongosh 中更新用户配置
use admin
db.updateUser("mongodb", {
    authenticationRestrictions: [
        {
            clientSource: ["<your_public_ip>", "127.0.0.1"]
        }
    ]
})
```

### 迁移步骤

1. **配置 IP 白名单** 在 MongoDB 服务器端
2. **测试直连** 验证 Python 应用可以直接连接
3. **更新 .env** 恢复使用 47.108.154.217
4. **关闭隧道** 停止 SSH 隧道进程
5. **验证应用** 确保应用正常运行

---

## 📚 相关文档

- [MongoDB 连接问题最终解决方案](./MONGODB_CONNECTION_FIX_FINAL.md)
- [Navicat 连接配置分析](./NAVICAT_CONNECTION_ANALYSIS.md)
- [MongoDB 连接问题排查报告](./MONGODB_CONNECTION_TROUBLESHOOTING.md)

---

**创建时间**: 2025-12-03
**更新时间**: 2025-12-03
**方案类型**: ⚠️ 临时解决方案
**推荐持续时间**: 24-48 小时（尽快迁移到永久方案）
