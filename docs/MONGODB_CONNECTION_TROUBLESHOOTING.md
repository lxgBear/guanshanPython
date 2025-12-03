# MongoDB 连接问题排查报告

## 📋 问题描述

**症状**: Python 应用无法连接到 MongoDB (192.168.0.3:27017)，但 Navicat 可以正常连接。

**错误信息**:
```
pymongo.errors.ServerSelectionTimeoutError: 192.168.0.3:27017: timed out
(configured timeouts: socketTimeoutMS: 10000.0ms, connectTimeoutMS: 10000.0ms)
```

## 🔍 根因分析

### 1. 初步假设：代理干扰

**分析过程**:
- 检查 `.env` 文件：发现 `NO_PROXY=192.168.0.3,localhost,127.0.0.1,192.168.0.0/24`
- 测试 Python 环境变量：`NO_PROXY=localhost,127.0.0.1,::1` (缺少 192.168.0.3)
- **结论**: 环境变量未正确加载

### 2. 配置修复：加载 NO_PROXY

**实施的修改** (src/config.py:10-14):
```python
from dotenv import load_dotenv

# 预先加载 .env 文件中的 NO_PROXY 配置（必须在 Settings 初始化之前）
# 这样可以确保 .env 中的值优先于系统环境变量
load_dotenv(override=True)
```

**添加 NO_PROXY 字段** (src/config.py:39-40):
```python
# 网络代理配置（VPN绕过内网IP，避免代理干扰MongoDB连接）
NO_PROXY: Optional[str] = Field(default=None, env="NO_PROXY")
no_proxy: Optional[str] = Field(default=None, env="no_proxy")
```

**设置环境变量** (src/config.py:116-122):
```python
# 设置 NO_PROXY 环境变量（避免代理干扰 MongoDB 内网连接）
if settings.NO_PROXY:
    os.environ['NO_PROXY'] = settings.NO_PROXY
    os.environ['no_proxy'] = settings.NO_PROXY
elif settings.no_proxy:
    os.environ['NO_PROXY'] = settings.no_proxy
    os.environ['no_proxy'] = settings.no_proxy
```

**验证结果**:
```bash
$ python3 -c "from src.config import settings; import os; print('NO_PROXY:', os.environ.get('NO_PROXY'))"
NO_PROXY: 192.168.0.3,localhost,127.0.0.1,192.168.0.0/24
```
✅ NO_PROXY 已正确加载

### 3. 深入诊断：网络连接测试

**TCP 连接测试**:
```bash
$ python3 -c "import socket; sock = socket.socket(); sock.settimeout(5); result = sock.connect_ex(('192.168.0.3', 27017)); print(f'Result: {result}')"
Result: 35  # Connection refused / No route to host
```

❌ **根本原因**: 端口 27017 在 192.168.0.3 上不可访问

## 🎯 最终结论

**问题性质**: 网络/基础设施问题，非 Python 配置问题

**可能原因**:
1. ✅ **MongoDB 服务未运行** - 需要在 192.168.0.3 上启动 MongoDB
2. ✅ **防火墙阻止连接** - 需要开放端口 27017
3. ✅ **MongoDB 未监听该 IP** - 需要配置 `bindIp: 0.0.0.0` 或 `bindIp: 192.168.0.3`

## ✅ 已完成的修复

尽管 MongoDB 服务本身存在问题，但已实施以下配置优化：

1. **✅ 环境变量加载优化**
   - 使用 `load_dotenv(override=True)` 强制加载 .env 配置
   - 确保 NO_PROXY 正确传递给所有 Python 子进程

2. **✅ 图片文件过滤**
   - 从文件上传配置中移除所有图片类型支持
   - 更新文档说明不支持图片上传

## 🔧 待解决问题

### 需要基础设施团队处理:

1. **确认 MongoDB 服务状态**
   ```bash
   # 在 192.168.0.3 服务器上执行
   sudo systemctl status mongod
   ```

2. **检查 MongoDB 配置** (`/etc/mongod.conf`):
   ```yaml
   net:
     port: 27017
     bindIp: 0.0.0.0  # 或 192.168.0.3
   ```

3. **验证防火墙规则**:
   ```bash
   # 在 192.168.0.3 服务器上执行
   sudo ufw status
   sudo ufw allow 27017/tcp
   ```

4. **测试连接性**:
   ```bash
   # 从应用服务器测试
   telnet 192.168.0.3 27017
   nc -zv 192.168.0.3 27017
   ```

## 📌 Navicat 连接成功的可能解释

1. **不同的连接配置** - Navicat 可能使用了不同的主机名或IP地址
2. **SSH 隧道** - Navicat 可能通过 SSH 隧道连接
3. **本地 MongoDB** - Navicat 实际连接的是 localhost 而非 192.168.0.3

**建议**: 请确认 Navicat 的实际连接配置（主机、端口、连接方式）

## 📝 修改文件清单

1. `src/config.py` - NO_PROXY 环境变量加载
2. `src/core/domain/entities/file_upload.py` - 移除图片类型支持
3. `docs/FILE_UPLOAD_SYSTEM.md` - 更新文件类型说明

## 🔄 后续步骤

1. **立即**: 联系基础设施团队检查 MongoDB 服务
2. **测试**: 服务恢复后重启应用验证连接
3. **监控**: 添加 MongoDB 连接健康检查

---

**报告时间**: 2025-12-03
**状态**: 配置已优化，等待基础设施修复
