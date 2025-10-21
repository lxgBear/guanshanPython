# VPN连接测试报告

**测试日期**: 2025-10-20
**测试环境**: macOS
**VPN类型**: OpenVPN
**目标**: 验证VPN连接并测试数据库访问

---

## 📊 测试摘要

### 测试结果总览

| 测试项 | 状态 | 详情 |
|--------|------|------|
| VPN连接状态 | ✅ 成功 | VPN已连接，接口utun4正常工作 |
| VPN网络接口 | ✅ 正常 | 已获取IP: 10.8.0.3 |
| VPN路由配置 | ✅ 正确 | 192.168.0.0/24 和 10.0.0.0/8 路由已配置 |
| VPN网关连通性 | ✅ 可达 | 网关10.8.0.1可以ping通 |
| DNS解析 | ✅ 成功 | hancens.top -> 116.52.81.199 |
| 数据库端口连通性 | ❌ 失败 | 无法连接到MongoDB端口27017 |
| 数据库连接 | ❌ 失败 | 连接超时 |

### 结论

**VPN连接本身是成功的**，但无法访问数据库服务。这不是VPN连接问题，而是数据库访问配置问题。

---

## 🔍 详细测试结果

### 1. VPN接口状态 ✅

```
接口名称: utun4
本地IP: 10.8.0.3
网关IP: 10.8.0.1
子网掩码: 255.255.255.0
状态: UP, RUNNING
```

**验证方法**:
```bash
ifconfig utun4
```

**结果**: VPN隧道接口已成功创建并分配IP地址。

### 2. VPN路由配置 ✅

```
目标网络              网关              接口
10.0.0.0/8           10.8.0.1          utun4
10.8.0.0/24          10.8.0.3          utun4
192.168.0.0/24       10.8.0.1          utun4
```

**验证方法**:
```bash
netstat -rn | grep utun
```

**结果**: 所有必要的路由已正确配置，符合VPN配置文件中的设置。

### 3. VPN网关连通性 ✅

```
PING 10.8.0.1 (10.8.0.1): 56 data bytes
64 bytes from 10.8.0.1: icmp_seq=0 ttl=64 time=4.494 ms
64 bytes from 10.8.0.1: icmp_seq=1 ttl=64 time=4.857 ms
64 bytes from 10.8.0.1: icmp_seq=2 ttl=64 time=5.082 ms

--- 10.8.0.1 ping statistics ---
3 packets transmitted, 3 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 4.494/4.811/5.082/0.242 ms
```

**验证方法**:
```bash
ping -c 3 10.8.0.1
```

**结果**: VPN网关响应正常，延迟约5ms，连接稳定。

### 4. DNS解析测试 ✅

```
域名: hancens.top
解析IP: 116.52.81.199 (公网IP)
```

**验证方法**:
```bash
nslookup hancens.top
```

**结果**: DNS解析正常，但解析到的是公网IP地址。

**问题**: 数据库服务器可能在内网IP上，不在公网IP上提供服务。

### 5. 数据库端口测试 ❌

#### 5.1 公网IP测试

```bash
nc -zv 116.52.81.199 27017
# 结果: 连接超时
```

**问题**: 公网IP的27017端口不可访问。

#### 5.2 常见内网IP测试

测试了以下IP地址的27017端口：
- 10.8.0.1 (VPN网关) - ❌ 不可访问
- 192.168.0.1 - ❌ 超时
- 192.168.0.10 - ❌ 超时
- 192.168.0.100 - ❌ 超时
- 10.0.0.1 - ❌ 超时

**结果**: 在常见内网IP地址上未找到MongoDB服务。

### 6. MongoDB连接测试 ❌

#### 6.1 测试连接字符串

```
mongodb://app_user:密码@hancens.top:27017/intelligent_system?authSource=intelligent_system
```

**错误信息**:
```
NetworkTimeout: hancens.top:27017: timed out
(configured timeouts: socketTimeoutMS: 10000.0ms, connectTimeoutMS: 10000.0ms)
```

**结果**: 连接超时，无法建立TCP连接。

---

## 🔧 问题分析

### 根本原因

VPN连接是成功的，但数据库服务器的**实际内网IP地址未知**。

### 可能的情况

1. **数据库在未扫描到的内网IP上**
   - 可能在192.168.0.x或10.x.x.x的其他地址
   - 需要服务器管理员提供准确IP

2. **数据库服务器有防火墙规则**
   - 可能只允许特定IP访问
   - 可能只允许特定VPN用户访问

3. **VPN路由配置不完整**
   - VPN配置使用了`route-nopull`
   - 可能缺少到数据库服务器的路由

4. **数据库未运行或端口不是27017**
   - 服务器上MongoDB可能未启动
   - 可能使用了非标准端口

---

## 💡 解决方案

### 方案1: 获取准确的数据库IP地址（推荐）

**联系服务器管理员，获取以下信息**：

1. **数据库服务器的内网IP地址**
   ```
   例如: 192.168.0.50 或 10.0.0.20
   ```

2. **MongoDB服务端口**（如果不是默认的27017）
   ```
   例如: 27018 或其他端口
   ```

3. **VPN用户的访问权限**
   - 确认您的VPN账号有访问数据库的权限
   - 确认数据库服务器防火墙允许您的VPN IP

**获得IP后，更新连接字符串**：
```bash
# .env 文件
MONGODB_URL=mongodb://app_user:密码@<实际IP>:27017/intelligent_system?authSource=intelligent_system
```

### 方案2: 通过VPN服务器中转访问

如果无法直接获取数据库IP，可以尝试通过VPN服务器访问：

1. **SSH登录到VPN服务器**:
   ```bash
   ssh admin@10.8.0.1
   # 或
   ssh admin@hancens.top
   ```

2. **在VPN服务器上测试数据库连接**:
   ```bash
   # 查找MongoDB服务
   netstat -tlnp | grep 27017

   # 或使用mongosh连接
   mongosh "mongodb://app_user:密码@localhost:27017/intelligent_system"
   ```

3. **设置端口转发**（临时方案）:
   ```bash
   # 在本地执行
   ssh -L 27017:数据库内网IP:27017 admin@10.8.0.1

   # 然后连接到localhost:27017
   ```

### 方案3: 更新VPN路由配置

如果数据库在特定子网，可能需要添加路由：

1. **编辑VPN配置文件** `vpn/lxg.ovpn`:
   ```
   # 添加到数据库服务器的路由
   route 数据库子网 子网掩码
   ```

2. **重新连接VPN**:
   ```bash
   ./scripts/vpn_connect.sh disconnect
   ./scripts/vpn_connect.sh connect
   ```

### 方案4: 检查VPN服务器配置

联系VPN管理员检查：

1. **服务器端路由推送配置**
   - 确认VPN服务器是否正确推送了到数据库的路由

2. **客户端配置证书权限**
   - 确认您的VPN证书有访问数据库网段的权限

3. **防火墙规则**
   - 确认VPN服务器和数据库服务器之间没有防火墙阻止

---

## 📝 下一步操作建议

### 立即执行

1. **联系服务器管理员**，请求以下信息：
   - [ ] 数据库服务器的内网IP地址
   - [ ] MongoDB服务端口号
   - [ ] 您的VPN账号是否有数据库访问权限
   - [ ] 数据库服务器防火墙规则

2. **使用诊断脚本**持续监控：
   ```bash
   ./scripts/diagnose_vpn_database.sh
   ```

### 获得IP地址后

1. **测试端口连通性**:
   ```bash
   nc -zv <数据库IP> 27017
   ```

2. **更新环境变量**:
   ```bash
   # .env 文件
   MONGODB_URL=mongodb://app_user:密码@<实际IP>:27017/intelligent_system?authSource=intelligent_system
   ```

3. **运行数据库连接测试**:
   ```bash
   ./scripts/test_vpn_database.py
   ```

4. **验证应用程序连接**:
   ```bash
   python -m uvicorn src.main:app --reload
   ```

---

## 🛠️ 可用的诊断工具

### 1. VPN连接管理脚本
```bash
# 查看VPN状态
./scripts/vpn_connect.sh status

# 连接VPN
./scripts/vpn_connect.sh connect

# 断开VPN
./scripts/vpn_connect.sh disconnect

# 查看日志
./scripts/vpn_connect.sh log
```

### 2. 数据库连接测试脚本
```bash
# 运行完整测试
./scripts/test_vpn_database.py
```

### 3. VPN诊断脚本（新）
```bash
# 运行全面诊断
./scripts/diagnose_vpn_database.sh
```

这个脚本会自动检查：
- VPN接口状态
- 路由配置
- 网关连通性
- DNS解析
- 数据库端口扫描
- VPN配置分析

---

## 📞 需要管理员提供的信息模板

您可以使用以下模板向服务器管理员询问：

```
您好，

我正在通过OpenVPN (lxg.ovpn) 连接到 hancens.top VPN服务器。
VPN连接本身是成功的（已获取IP: 10.8.0.3），但无法访问MongoDB数据库。

请提供以下信息：

1. MongoDB数据库服务器的内网IP地址
2. MongoDB服务端口（如果不是默认的27017）
3. 我的VPN账号(lxg)是否有访问数据库的权限
4. 数据库服务器是否有防火墙规则限制访问

当前测试结果：
- VPN网关 10.8.0.1 可访问 ✓
- hancens.top 解析到 116.52.81.199 (公网IP)
- 116.52.81.199:27017 无法连接
- 已测试常见内网IP，未找到MongoDB服务

谢谢！
```

---

## 📚 相关文档

- [VPN数据库连接完整指南](./VPN_DATABASE_GUIDE.md)
- VPN配置文件: `vpn/lxg.ovpn`
- 测试脚本目录: `scripts/`

---

## 总结

**VPN连接测试**: ✅ **成功**
- VPN隧道已建立
- 路由配置正确
- 网关可访问

**数据库访问测试**: ❌ **失败**
- 原因: 数据库服务器实际IP地址未知
- 解决: 需要联系管理员获取准确的内网IP地址

**下一步**: 联系服务器管理员获取数据库内网IP地址后重新测试。
