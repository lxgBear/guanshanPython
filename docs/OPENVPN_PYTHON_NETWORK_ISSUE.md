# OpenVPN 与 Python 网络连接问题

## 问题描述

在 macOS 上启用 OpenVPN 后，Python 应用程序无法连接到内网 MongoDB 服务器（192.168.0.3:27017），但系统命令（如 `nc`, `ping`）可以正常连接。

## 症状

### ✅ 成功的连接
```bash
# netcat 连接成功
$ nc -zv 192.168.0.3 27017
Connection to 192.168.0.3 port 27017 [tcp/*] succeeded!

# ping 成功
$ ping -c 3 192.168.0.3
3 packets transmitted, 3 packets received, 0.0% packet loss
```

### ❌ 失败的连接
```bash
# Python socket 连接失败
$ python3 -c "import socket; s=socket.socket(); s.connect(('192.168.0.3', 27017))"
OSError: [Errno 65] No route to host

# Python Motor/PyMongo 连接失败
pymongo.errors.ServerSelectionTimeoutError: 192.168.0.3:27017: [Errno 65] No route to host
```

## 根本原因

**OpenVPN 在 macOS 系统层面实施了应用程序级网络过滤**：

1. **Network Extension Framework** - macOS VPN 应用使用系统级网络扩展
2. **应用程序筛选** - VPN 区分不同应用程序的网络流量
3. **默认阻止策略** - Python 进程的连接被视为"不安全"而阻止
4. **系统命令白名单** - 系统工具（`nc`, `ping`）在白名单中

### 技术细节

- **VPN 接口**: utun5 (10.8.0.3)
- **影响的应用**: Python, Node.js等脚本语言运行时
- **不受影响**: 系统命令, GUI 应用程序

## 解决方案

### 方案 1: 临时禁用 VPN（开发环境）

**适用场景**: 本地开发测试

```bash
# 断开 OpenVPN
# （具体方法取决于 VPN 客户端）

# 验证连接
python3 -c "import socket; s=socket.socket(); s.connect(('192.168.0.3', 27017)); print('✅ 成功')"

# 重启应用
./start_server.sh
```

**优点**:
- 立即生效，无需配置
- 100% 解决问题

**缺点**:
- 失去 VPN 保护
- 无法访问 VPN 专用资源

### 方案 2: SSH 隧道（生产环境推荐）

**适用场景**: 需要保持 VPN 连接

```bash
# 创建 SSH 隧道
ssh -fN -L 27017:192.168.0.3:27017 jump-server.example.com

# 或使用 autossh 保持连接
autossh -M 0 -fN -L 27017:192.168.0.3:27017 jump-server.example.com
```

**修改 .env 配置**:
```env
# 连接本地隧道端口
MONGODB_URL=mongodb://mongodb:hhLBknn7dEhzJK78@localhost:27017/?authSource=admin&directConnection=true
```

**优点**:
- VPN 保持连接
- 加密传输
- 稳定可靠

**缺点**:
- 需要跳板机
- 额外的 SSH 配置

### 方案 3: VPN 分流配置

**适用场景**: 长期使用，自动化

在 VPN 客户端中配置路由规则：

```conf
# OpenVPN 配置文件添加
route-nopull
route 192.168.0.0 255.255.255.0 net_gateway

# 或使用 VPN 客户端 GUI 配置
# 添加分流规则: 192.168.0.0/24 → 直连
```

**macOS 防火墙配置**:
```bash
# 系统偏好设置 → 安全性与隐私 → 防火墙
# 添加 Python 到允许列表
```

### 方案 4: 使用云 MongoDB 服务

**适用场景**: 简化部署，提高可靠性

使用 MongoDB Atlas 或其他云服务：

```env
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
```

**优点**:
- 不受 VPN 影响
- 高可用性
- 自动备份

**缺点**:
- 额外费用
- 数据传输延迟

## 验证步骤

### 1. 确认 VPN 状态
```bash
# 检查 VPN 接口
ifconfig | grep -A 5 "utun"

# 检查路由表
netstat -rn | grep 192.168.0
```

### 2. 测试 Python 连接
```bash
# 直接 socket 测试
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect(('192.168.0.3', 27017))
print('✅ 连接成功')
s.close()
"
```

### 3. 测试 MongoDB 连接
```bash
# 使用 Motor 测试
python3 -c "
from src.config import settings
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    await client.admin.command('ping')
    print('✅ MongoDB 连接成功')
    client.close()

asyncio.run(test())
"
```

## 常见问题

### Q: 为什么 Navicat 可以连接？
**A**: Navicat 是 GUI 应用程序，可能在 VPN 白名单中，或使用了 SSH 隧道连接。

### Q: 设置 NO_PROXY 有用吗？
**A**: NO_PROXY 只影响 HTTP/HTTPS 代理，对 VPN 的应用级过滤无效。

### Q: 如何永久解决？
**A**: 使用 SSH 隧道（方案 2）或 VPN 分流配置（方案 3）是永久方案。

## 相关文件

- `start_server.sh` - 已优化代理环境变量清理
- `src/config.py` - 已添加 NO_PROXY 配置支持
- `.env` - NO_PROXY 配置

## 参考资料

- [macOS Network Extension Framework](https://developer.apple.com/documentation/networkextension)
- [OpenVPN Routing](https://openvpn.net/community-resources/reference-manual-for-openvpn-2-4/)
- [MongoDB Connection Troubleshooting](https://www.mongodb.com/docs/manual/reference/connection-string/)

---

**创建时间**: 2025-12-03
**问题类型**: OpenVPN 应用级网络过滤
**推荐方案**: SSH 隧道（方案 2）
