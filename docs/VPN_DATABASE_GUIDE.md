# VPN连接线上数据库操作指南

## 📋 目录

1. [系统架构](#系统架构)
2. [前置要求](#前置要求)
3. [安装OpenVPN](#安装openvpn)
4. [快速开始](#快速开始)
5. [详细操作步骤](#详细操作步骤)
6. [数据库配置](#数据库配置)
7. [故障排查](#故障排查)
8. [最佳实践](#最佳实践)
9. [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  本地开发环境    │         │  VPN服务器    │         │  线上数据库服务器 │
│                 │         │              │         │                 │
│  macOS          │◄────────┤ hancens.top  ├────────►│ hancens.top     │
│  localhost      │  VPN    │  :1194 (UDP) │  内网   │  :27017 (MongoDB)│
│                 │         │              │         │                 │
└─────────────────┘         └──────────────┘         └─────────────────┘
        ▲                                                      ▲
        │                                                      │
        │  1. 连接VPN                                          │
        │  2. 获取VPN内网IP (10.0.0.x)                        │
        └──────────────────────────────────────────────────────┘
           3. 通过VPN访问数据库

VPN网络段:
- 10.0.0.0/8     VPN内部网络
- 192.168.0.0/24 服务器内网段
```

## 前置要求

### ✅ 系统要求

- **操作系统**: macOS (Darwin 24.5.0 或更高)
- **Python**: 3.10+
- **网络**: 稳定的互联网连接
- **权限**: sudo权限（用于创建VPN接口）

### ✅ 必需文件

1. **VPN配置文件**: `vpn/lxg.ovpn`
   - 服务器地址: `hancens.top:1194`
   - 协议: UDP
   - 包含客户端证书和密钥

2. **数据库凭据**:
   - MongoDB用户名和密码
   - 数据库名称: `intelligent_system`

---

## 安装OpenVPN

### 方法1: 使用Homebrew（推荐命令行使用）

```bash
# 安装Homebrew（如果未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装OpenVPN
brew install openvpn

# 验证安装
openvpn --version
```

### 方法2: 使用Tunnelblick（推荐图形界面）

1. 下载Tunnelblick: https://tunnelblick.net/
2. 安装应用程序
3. 将 `vpn/lxg.ovpn` 拖放到Tunnelblick
4. 点击"连接"按钮

**注意**: 本指南主要使用命令行方式（方法1），方便自动化和脚本集成。

---

## 快速开始

### 🚀 三步快速连接

```bash
# 1. 连接VPN
cd /Users/lanxionggao/Documents/guanshanPython
./scripts/vpn_connect.sh connect

# 2. 检查VPN状态
./scripts/vpn_connect.sh status

# 3. 测试数据库连接
./scripts/test_vpn_database.py
```

### 📊 预期输出

```bash
# VPN连接成功
[SUCCESS] VPN连接成功!
[INFO] VPN信息:
  本地IP: 10.0.0.5

# 数据库测试成功
[SUCCESS] MongoDB连接成功!
[INFO] 服务器信息:
  - MongoDB版本: 7.0.x
  - 服务器时间: 2025-10-20 19:30:00
[INFO] 可用数据库 (4):
  - admin
  - config
  - intelligent_system
  - local
```

---

## 详细操作步骤

### 步骤1: 检查环境

```bash
# 检查Python版本
python3 --version  # 应该 >= 3.10

# 检查OpenVPN是否安装
openvpn --version

# 如果未安装OpenVPN
brew install openvpn

# 检查VPN配置文件
ls -lh vpn/lxg.ovpn
```

### 步骤2: 连接VPN

#### 使用自动化脚本（推荐）

```bash
# 连接VPN
./scripts/vpn_connect.sh connect

# 输出示例:
# [INFO] 检查OpenVPN安装状态...
# [SUCCESS] OpenVPN已安装: OpenVPN 2.6.x
# [INFO] 检查VPN配置文件...
# [SUCCESS] 配置文件有效
#   服务器: hancens.top:1194
#   协议: udp
# [INFO] 正在连接VPN...
# [INFO] 启动OpenVPN客户端...
# [WARNING] 需要sudo权限以创建VPN接口
# Password: [输入sudo密码]
# [INFO] 等待VPN连接建立...
# ................
# [SUCCESS] VPN连接成功!
# [INFO] VPN信息:
#   本地IP: 10.0.0.5
```

#### 手动连接（高级用户）

```bash
# 直接使用OpenVPN命令
sudo openvpn --config vpn/lxg.ovpn --daemon --log /tmp/openvpn.log

# 检查进程
ps aux | grep openvpn

# 检查VPN接口
ifconfig | grep utun
```

### 步骤3: 验证VPN连接

```bash
# 方法1: 使用脚本
./scripts/vpn_connect.sh status

# 方法2: 手动检查
ifconfig | grep -A 5 utun

# 方法3: 检查路由
netstat -rn | grep utun

# 预期输出:
# 10/8               10.0.0.1           UGSc           utun3
# 192.168.0/24       10.0.0.1           UGSc           utun3
```

### 步骤4: 测试网络连通性

```bash
# 测试VPN服务器可达性
ping -c 3 hancens.top

# 测试MongoDB端口
nc -zv hancens.top 27017

# 预期输出:
# Connection to hancens.top port 27017 [tcp/mongod] succeeded!
```

### 步骤5: 测试数据库连接

```bash
# 运行数据库连接测试
./scripts/test_vpn_database.py

# 测试流程:
# 1. 检查VPN连接状态 ✓
# 2. 测试本地数据库（可选）
# 3. 测试VPN线上数据库 ✓
# 4. 列出可用数据库和集合
```

### 步骤6: 配置应用程序

#### 更新.env文件

```bash
# 编辑.env文件
nano .env

# 或使用示例配置
cp .env.baota.example .env
```

#### 数据库连接配置

```bash
# .env文件内容
# 线上MongoDB配置（通过VPN访问）
MONGODB_URL=mongodb://app_user:MyStrongPassword123!@hancens.top:27017/intelligent_system?authSource=intelligent_system

# 注意事项:
# 1. 使用正确的用户名和密码
# 2. authSource应该与数据库名称匹配
# 3. 确保VPN已连接
```

### 步骤7: 启动应用程序

```bash
# 确保VPN已连接
./scripts/vpn_connect.sh status

# 启动应用
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 测试API
curl http://localhost:8000/api/v1/health
```

### 步骤8: 断开VPN（可选）

```bash
# 使用脚本断开
./scripts/vpn_connect.sh disconnect

# 手动断开
sudo killall openvpn
```

---

## 数据库配置

### MongoDB连接字符串格式

```
mongodb://[username]:[password]@[host]:[port]/[database]?[options]
```

### 可用的连接选项

#### 选项1: app_user（应用程序用户 - 推荐）

```bash
mongodb://app_user:MyStrongPassword123!@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**权限**: 读写 `intelligent_system` 数据库

#### 选项2: ai_analyst（AI分析用户 - 只读）

```bash
mongodb://ai_analyst:AnalystPass456!@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**权限**: 只读 `intelligent_system` 数据库

#### 选项3: admin（管理员 - 慎用）

```bash
mongodb://admin:AdminPassword789!@hancens.top:27017/admin?authSource=admin
```

**权限**: 完全权限

### URL编码说明

如果密码包含特殊字符，需要URL编码:

```python
from urllib.parse import quote_plus

password = "MyPass@123!"
encoded = quote_plus(password)  # MyPass%40123%21

# 使用编码后的密码
mongodb_url = f"mongodb://app_user:{encoded}@hancens.top:27017/intelligent_system?authSource=intelligent_system"
```

常见特殊字符编码:
- `@` → `%40`
- `!` → `%21`
- `#` → `%23`
- `$` → `%24`
- `%` → `%25`

---

## 故障排查

### 问题1: OpenVPN连接超时

**症状**:
```
[ERROR] VPN连接超时
```

**解决方案**:
1. 检查网络连接
2. 确认服务器地址和端口正确
3. 检查防火墙设置
4. 查看详细日志:
   ```bash
   ./scripts/vpn_connect.sh log
   ```

### 问题2: 数据库连接失败

**症状**:
```
[ERROR] 连接超时: ServerSelectionTimeoutError
```

**解决方案**:
1. 确认VPN已连接:
   ```bash
   ./scripts/vpn_connect.sh status
   ```

2. 检查VPN路由:
   ```bash
   netstat -rn | grep utun
   # 应该看到 192.168.0.0/24 和 10.0.0.0/8
   ```

3. 测试端口可达性:
   ```bash
   nc -zv hancens.top 27017
   ```

4. 确认数据库凭据正确

### 问题3: VPN连接成功但无法访问数据库

**症状**:
VPN显示已连接，但数据库测试失败

**解决方案**:
1. 检查路由表:
   ```bash
   netstat -rn | grep utun
   ```

2. 确认VPN配置的路由:
   ```bash
   grep "route " vpn/lxg.ovpn
   # 应该包含:
   # route 192.168.0.0 255.255.255.0
   # route 10.0.0.0 255.0.0.0
   ```

3. 手动添加路由（如果缺失）:
   ```bash
   sudo route add -net 192.168.0.0/24 -interface utun3
   ```

### 问题4: 权限不足

**症状**:
```
[ERROR] Permission denied
```

**解决方案**:
```bash
# OpenVPN需要root权限
sudo openvpn --config vpn/lxg.ovpn

# 或使用sudo运行脚本
sudo ./scripts/vpn_connect.sh connect
```

### 问题5: 认证失败

**症状**:
```
pymongo.errors.OperationFailure: Authentication failed
```

**解决方案**:
1. 检查用户名和密码
2. 确认authSource正确
3. 测试不同的用户凭据
4. 检查用户是否有权限访问该数据库

---

## 最佳实践

### 🔒 安全建议

1. **凭据管理**:
   - 不要提交 `.env` 文件到Git
   - 使用环境变量存储密码
   - 定期更换数据库密码

2. **VPN配置**:
   - 保护 `.ovpn` 文件安全
   - 不要共享私钥
   - 定期更新证书

3. **网络安全**:
   - 只在必要时连接VPN
   - 使用完毕后断开VPN
   - 监控VPN连接日志

### ⚡ 性能优化

1. **连接池配置**:
   ```python
   # src/infrastructure/database/connection.py
   client = AsyncIOMotorClient(
       mongodb_url,
       maxPoolSize=50,        # 最大连接数
       minPoolSize=10,        # 最小连接数
       serverSelectionTimeoutMS=5000,  # 连接超时
       connectTimeoutMS=5000  # Socket连接超时
   )
   ```

2. **超时设置**:
   ```python
   # 合理的超时时间
   serverSelectionTimeoutMS=10000  # 10秒
   connectTimeoutMS=10000          # 10秒
   socketTimeoutMS=30000           # 30秒
   ```

3. **连接检查**:
   ```bash
   # 定期检查VPN状态
   watch -n 30 './scripts/vpn_connect.sh status'
   ```

### 🔄 自动化建议

1. **启动时自动连接**:
   ```bash
   # 在应用启动脚本中添加
   if ! ./scripts/vpn_connect.sh status > /dev/null 2>&1; then
       echo "VPN未连接，正在连接..."
       ./scripts/vpn_connect.sh connect
   fi

   # 启动应用
   python -m uvicorn src.main:app --reload
   ```

2. **健康检查**:
   ```bash
   # cron任务每5分钟检查VPN
   */5 * * * * /path/to/scripts/vpn_connect.sh status || /path/to/scripts/vpn_connect.sh connect
   ```

3. **日志轮转**:
   ```bash
   # 清理旧日志
   find /tmp -name "openvpn_*.log" -mtime +7 -delete
   ```

---

## 常见问题

### Q1: 如何查看VPN日志？

```bash
./scripts/vpn_connect.sh log

# 或直接查看
tail -f /tmp/openvpn_hancens_vpn.log
```

### Q2: VPN断开后如何自动重连？

创建守护进程或使用系统级VPN管理:

```bash
# 使用launchd (macOS)
# 创建 ~/Library/LaunchAgents/com.guanshan.vpn.plist
```

### Q3: 可以同时连接多个VPN吗？

可以，但需要注意路由冲突。建议一次只连接一个VPN。

### Q4: 如何在Docker中使用VPN？

Docker容器需要使用宿主机的VPN连接:

```yaml
# docker-compose.yml
services:
  app:
    network_mode: host  # 使用宿主机网络
```

### Q5: VPN连接很慢怎么办？

1. 检查本地网络质量
2. 尝试不同的DNS服务器
3. 检查VPN服务器负载
4. 考虑使用TCP协议（修改.ovpn文件）

### Q6: 如何在生产环境中使用？

1. 使用专用的VPN服务器
2. 配置防火墙规则
3. 启用日志审计
4. 使用监控告警
5. 准备备用连接方案

---

## 脚本参考

### VPN管理脚本

```bash
# 连接VPN
./scripts/vpn_connect.sh connect

# 断开VPN
./scripts/vpn_connect.sh disconnect

# 查看状态
./scripts/vpn_connect.sh status

# 测试数据库
./scripts/vpn_connect.sh test

# 查看日志
./scripts/vpn_connect.sh log

# 帮助信息
./scripts/vpn_connect.sh help
```

### 数据库测试脚本

```bash
# 完整测试
./scripts/test_vpn_database.py

# Python交互式测试
python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient('mongodb://...')
    print(await client.server_info())

asyncio.run(test())
"
```

---

## 技术支持

### 相关文档

- [OpenVPN官方文档](https://openvpn.net/community-resources/)
- [MongoDB连接字符串](https://www.mongodb.com/docs/manual/reference/connection-string/)
- [Motor异步驱动](https://motor.readthedocs.io/)

### 联系方式

- **项目文档**: `/docs/`
- **问题追踪**: 项目Issue
- **日志路径**: `/tmp/openvpn_*.log`

---

## 附录

### A. VPN配置文件说明

```ovpn
client                  # 客户端模式
dev tun                 # TUN设备（路由模式）
proto udp               # UDP协议（更快）
remote hancens.top 1194 # VPN服务器地址
route-nopull            # 不接受服务器推送的所有路由
route 192.168.0.0 255.255.255.0  # 手动添加内网路由
route 10.0.0.0 255.0.0.0         # VPN内部网络路由
```

### B. 网络诊断命令

```bash
# 检查VPN接口
ifconfig | grep utun

# 检查路由表
netstat -rn

# 测试连通性
ping hancens.top

# 测试端口
nc -zv hancens.top 27017

# DNS查询
nslookup hancens.top

# 追踪路由
traceroute hancens.top
```

### C. 性能监控

```bash
# 监控网络流量
nettop -m route

# 监控VPN连接
watch -n 5 'ifconfig | grep -A 10 utun'

# 监控数据库连接
watch -n 5 'netstat -an | grep 27017'
```

---

**最后更新**: 2025-10-20
**版本**: 1.0.0
**维护者**: 关山智能系统团队
