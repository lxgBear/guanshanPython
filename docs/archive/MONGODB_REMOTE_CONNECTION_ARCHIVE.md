# MongoDB 远程连接配置任务归档

**归档日期**: 2025-10-20
**状态**: 暂停（待后续配置）
**原因**: 优先开发新功能

---

## 📋 任务概述

配置宝塔服务器 MongoDB 允许远程连接，以支持 VPN 管理功能使用线上数据库。

---

## 🔑 数据库信息

- **服务器**: hancens.top:27017
- **数据库名**: guanshan
- **用户名**: guanshan
- **密码**: 5iSFspPkCLG5cRiD
- **认证数据库**: guanshan

**连接字符串**:
```
mongodb://guanshan:5iSFspPkCLG5cRiD@hancens.top:27017/guanshan?authSource=guanshan
```

---

## ⚠️ 当前问题

### 问题描述
MongoDB 配置为 `bindIp: 127.0.0.1`，只监听本地连接，无法从外部访问。

### 诊断结果
```bash
# Ping测试
hancens.top (116.52.81.199): 100% 丢包

# 端口测试
27017: 连接超时

# MongoDB状态
监听: 127.0.0.1 (仅本地)
需要: 0.0.0.0 (允许远程)
```

---

## 🔧 待完成配置步骤

### 步骤1：修改 MongoDB 配置

1. **查找配置文件**
   ```bash
   sudo find / -name "mongod.conf" 2>/dev/null
   ```

2. **备份配置**
   ```bash
   sudo cp /etc/mongod.conf /etc/mongod.conf.backup
   ```

3. **修改 bindIp**
   ```bash
   sudo sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/g' /etc/mongod.conf
   ```

4. **验证修改**
   ```bash
   grep bindIp /etc/mongod.conf
   # 应显示: bindIp: 0.0.0.0
   ```

### 步骤2：重启 MongoDB

```bash
sudo systemctl restart mongod
```

### 步骤3：验证端口监听

```bash
netstat -tuln | grep 27017
# 应显示: 0.0.0.0:27017
```

### 步骤4：测试远程连接

```bash
# 在本地执行
python scripts/archive/test_new_mongodb.py
```

### 步骤5：创建 VPN 索引

脚本会自动创建：
- `vpn_connections` 集合及索引
- `vpn_connection_logs` 集合及索引

---

## 📁 归档文件位置

### 配置脚本
- `scripts/archive/configure_mongodb_remote.sh` - MongoDB 配置自动化脚本
- `scripts/archive/test_new_mongodb.py` - 连接和索引创建测试脚本

### 文档
- `docs/MILESTONES.md` - 里程碑文档（包含此任务）
- `docs/MONGODB_GUIDE.md` - MongoDB 使用指南

---

## ✅ 已完成工作

1. ✅ VPN 管理功能代码实现
   - 实体模型 (`vpn_connection.py`)
   - 仓储层 (`vpn_repositories.py`)
   - 服务层 (`vpn_service.py`)
   - API 端点 (`vpn_management.py`)

2. ✅ 数据库索引配置
   - 已在 `connection.py` 中添加索引创建代码

3. ✅ 路由注册
   - VPN 路由已注册到主路由

4. ✅ 测试脚本准备
   - API 测试脚本 (`test_vpn_api.py`)
   - 数据库连接测试脚本（已归档）

---

## 🚀 恢复步骤

当需要恢复此任务时：

1. 查看 `docs/MILESTONES.md` 中的完整步骤
2. 使用 `scripts/archive/` 中的配置脚本
3. 按照上述"待完成配置步骤"执行
4. 测试并验证连接

---

## 📝 注意事项

1. **安全性**:
   - 建议配置 IP 白名单而不是开放所有 IP
   - 使用强密码
   - 启用 TLS/SSL（生产环境）

2. **防火墙**:
   - 确保宝塔安全组已开放 27017 端口
   - 云服务商安全组也需要配置

3. **备份**:
   - 修改配置前务必备份
   - 保留回滚方案

---

## 📊 技术栈

- **数据库**: MongoDB
- **Python驱动**: Motor (异步)
- **服务器**: Ubuntu (宝塔面板)
- **网络**: hancens.top

---

## 🔗 相关资源

- [MongoDB 官方文档](https://docs.mongodb.com/)
- [Motor 文档](https://motor.readthedocs.io/)
- [宝塔面板文档](https://www.bt.cn/bbs/)

---

**归档原因**: 优先开发其他功能，此任务可后续配置
**预计恢复时间**: 待定
**负责人**: 后端团队
