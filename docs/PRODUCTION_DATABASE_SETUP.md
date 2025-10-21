# 生产数据库配置指南
# Production Database Setup Guide

## 📋 概述

本文档说明如何配置和连接到线上生产MongoDB数据库。

**数据库信息：**
- **主机**: hancens.top
- **端口**: 40717 (非标准端口)
- **用户名**: guanshan
- **数据库**: guanshan
- **认证数据库**: guanshan

## ✅ 已完成的配置

### 1. 环境配置文件已更新

`.env` 文件已更新为使用生产数据库：

```bash
# MongoDB配置（线上生产数据库）
MONGODB_URL=mongodb://guanshan:YOUR_PASSWORD_HERE@hancens.top:40717/?authSource=guanshan
MONGODB_DB_NAME=guanshan
```

### 2. 创建的文件

| 文件 | 说明 |
|------|------|
| `.env.production.example` | 生产环境配置模板，包含完整的配置说明 |
| `scripts/test_production_database.py` | 数据库连接测试脚本 |
| `docs/PRODUCTION_DATABASE_SETUP.md` | 本文档 |

## ⚠️ 需要您完成的步骤

### 步骤 1: 填写MongoDB密码

编辑 `.env` 文件，将 `YOUR_PASSWORD_HERE` 替换为实际的MongoDB密码：

```bash
# 修改前:
MONGODB_URL=mongodb://guanshan:YOUR_PASSWORD_HERE@hancens.top:40717/?authSource=guanshan

# 修改后（示例）:
MONGODB_URL=mongodb://guanshan:ActualPassword123@hancens.top:40717/?authSource=guanshan
```

**重要提示：密码特殊字符处理**

如果密码包含特殊字符，需要进行URL编码：

| 字符 | 编码后 |
|------|--------|
| @ | %40 |
| : | %3A |
| / | %2F |
| ? | %3F |
| # | %23 |
| & | %26 |
| 空格 | %20 |

**示例：**
```bash
# 原始密码: MyPass@2024
# 编码后密码: MyPass%402024
MONGODB_URL=mongodb://guanshan:MyPass%402024@hancens.top:40717/?authSource=guanshan
```

### 步骤 2: 测试数据库连接

填写密码后，运行测试脚本验证连接：

```bash
python scripts/test_production_database.py
```

**测试内容：**
1. ✓ 基本连接测试
2. ✓ 服务器信息获取
3. ✓ 数据库访问权限验证
4. ✓ 写入权限测试
5. ✓ 读取权限测试
6. ✓ 测试数据清理
7. ✓ 数据库统计信息

**成功输出示例：**
```
==================================================================
                    生产数据库连接测试
==================================================================

ℹ 连接字符串: mongodb://guanshan:****@hancens.top:40717/?authSource=guanshan
ℹ 数据库名称: guanshan

步骤 1/6: 测试基本连接
✓ MongoDB连接成功

步骤 2/6: 获取服务器信息
✓ MongoDB版本: 5.0.x

...

==================================================================
                         测试完成
==================================================================

✓ 所有测试通过！生产数据库连接正常
ℹ 可以开始使用应用程序
```

### 步骤 3: 启动应用

测试通过后，启动FastAPI应用：

```bash
# 方式1: 开发模式（自动重载）
python src/main.py

# 方式2: 使用uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 方式3: 生产模式（多进程）
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 🔍 故障排查

### 问题 1: 连接超时

**症状：**
```
✗ 连接超时（10秒）
```

**可能原因及解决方案：**

1. **防火墙未开放端口**
   ```bash
   # 测试端口连通性
   nc -zv hancens.top 40717

   # 或使用telnet
   telnet hancens.top 40717
   ```
   - 如果无法连接，需要在服务器防火墙中开放40717端口

2. **MongoDB服务未启动**
   - 联系服务器管理员确认MongoDB服务状态

3. **网络连接问题**
   ```bash
   # 测试服务器连通性
   ping hancens.top
   ```

### 问题 2: 认证失败

**症状：**
```
✗ 连接失败: Authentication failed
```

**解决方案：**

1. **检查密码是否正确**
   - 确认密码没有拼写错误
   - 确认密码中的特殊字符已正确URL编码

2. **检查用户名和数据库名**
   - 用户名: guanshan
   - 认证数据库: guanshan (authSource参数)

3. **验证用户权限**
   - 联系数据库管理员确认用户 `guanshan` 是否存在
   - 确认用户是否有数据库 `guanshan` 的读写权限

### 问题 3: 数据库访问被拒绝

**症状：**
```
✗ 数据库访问失败: not authorized
```

**解决方案：**

1. **检查authSource配置**
   ```bash
   # 确保authSource参数正确
   ?authSource=guanshan
   ```

2. **验证用户权限**
   - 用户需要对数据库 `guanshan` 有 `readWrite` 权限
   - 联系管理员分配正确的角色

### 问题 4: 密码包含特殊字符导致解析错误

**症状：**
```
✗ 连接失败: Invalid connection string
```

**解决方案：**

使用Python进行URL编码：

```python
from urllib.parse import quote_plus

password = "MyPass@2024#"
encoded_password = quote_plus(password)
print(f"编码后的密码: {encoded_password}")
# 输出: MyPass%402024%23
```

然后更新 `.env` 文件：
```bash
MONGODB_URL=mongodb://guanshan:MyPass%402024%23@hancens.top:40717/?authSource=guanshan
```

## 📊 连接字符串格式说明

### 标准格式

```
mongodb://[username]:[password]@[host]:[port]/[database]?[options]
```

### 当前配置解析

```
mongodb://guanshan:PASSWORD@hancens.top:40717/?authSource=guanshan
│         │         │        │           │      │
│         │         │        │           │      └─ 认证数据库
│         │         │        │           └─ 端口号(非标准)
│         │         │        └─ 服务器地址
│         │         └─ 密码(需要URL编码)
│         └─ 用户名
└─ 协议
```

### 常用选项参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `authSource` | 认证数据库 | `?authSource=guanshan` |
| `ssl` | 启用SSL | `?ssl=true` |
| `replicaSet` | 副本集名称 | `?replicaSet=rs0` |
| `retryWrites` | 自动重试写操作 | `?retryWrites=true` |
| `w` | 写关注级别 | `?w=majority` |

## 🔐 安全建议

### 1. 密码强度

生产环境的MongoDB密码应该：
- 长度至少16个字符
- 包含大小写字母、数字和特殊符号
- 不使用字典词汇
- 定期更换（建议3-6个月）

### 2. 环境变量保护

```bash
# .env文件权限设置
chmod 600 .env

# 确保.env在.gitignore中
echo ".env" >> .gitignore
```

### 3. 连接池配置

当前配置：
```bash
MONGODB_MAX_POOL_SIZE=100  # 最大连接数
MONGODB_MIN_POOL_SIZE=10   # 最小连接数
```

根据实际负载调整：
- 低负载: 10-50
- 中等负载: 50-100
- 高负载: 100-200

## 📚 相关文档

- [MongoDB连接字符串官方文档](https://docs.mongodb.com/manual/reference/connection-string/)
- [Motor (异步驱动) 文档](https://motor.readthedocs.io/)
- [项目启动指南](../STARTUP_GUIDE.md)
- [MongoDB配置指南](./MONGODB_GUIDE.md)

## 🆘 获取帮助

如果遇到无法解决的问题：

1. **查看应用日志**
   ```bash
   tail -f logs/app.log
   ```

2. **运行诊断脚本**
   ```bash
   python scripts/test_production_database.py
   ```

3. **检查MongoDB服务器日志**
   - 联系服务器管理员查看MongoDB日志
   - 检查认证失败记录

4. **联系技术支持**
   - 提供错误信息和日志
   - 说明已尝试的解决方案

## ✨ 配置完成检查清单

完成以下检查后，即可开始使用生产数据库：

- [ ] 1. 已在 `.env` 文件中填写正确的MongoDB密码
- [ ] 2. 密码中的特殊字符已进行URL编码
- [ ] 3. 运行 `python scripts/test_production_database.py` 测试通过
- [ ] 4. 防火墙已开放40717端口
- [ ] 5. 应用程序启动时能成功连接数据库
- [ ] 6. `.env` 文件权限设置为600
- [ ] 7. `.env` 已添加到 `.gitignore`

---

**版本**: 1.0.0
**更新日期**: 2025-01-XX
**维护者**: 关山智能系统团队
