# 项目里程碑

## 待完成任务

### 📦 线上数据库连接配置（已归档）

**优先级**: 中
**状态**: 📦 已归档
**负责**: 后端团队
**创建时间**: 2025-10-20
**归档时间**: 2025-10-20
**归档原因**: 优先开发新功能，待后续配置

#### 任务描述

配置并测试与宝塔服务器 MongoDB 的远程连接，确保 VPN 管理功能可以正常使用线上数据库。

#### 数据库信息

- **服务器**: hancens.top:27017
- **数据库名**: guanshan
- **用户名**: guanshan
- **密码**: 5iSFspPkCLG5cRiD

#### 待完成步骤

- [ ] **步骤1**: 在宝塔服务器配置 MongoDB 允许远程连接
  ```bash
  # 查找配置文件
  sudo find / -name "mongod.conf" 2>/dev/null

  # 修改 bindIp 为 0.0.0.0
  sudo sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/g' /etc/mongod.conf

  # 重启 MongoDB
  sudo systemctl restart mongod

  # 验证端口监听
  netstat -tuln | grep 27017
  ```

- [ ] **步骤2**: 验证防火墙端口已开放
  ```bash
  # 应该看到 27017 端口开放
  sudo ufw status | grep 27017
  ```

- [ ] **步骤3**: 测试远程连接
  ```bash
  # 在本地运行测试脚本
  python scripts/test_new_mongodb.py
  ```

- [ ] **步骤4**: 创建 VPN 数据库索引
  - 脚本会自动创建 `vpn_connections` 和 `vpn_connection_logs` 集合索引

- [ ] **步骤5**: 更新项目 .env 文件
  ```env
  MONGODB_URL=mongodb://guanshan:5iSFspPkCLG5cRiD@hancens.top:27017/guanshan?authSource=guanshan
  MONGODB_DB_NAME=guanshan
  ```

- [ ] **步骤6**: 测试 VPN API 功能
  ```bash
  # 启动应用
  python main.py

  # 测试API
  python scripts/test_vpn_api.py
  ```

#### 技术细节

**当前问题**:
- MongoDB 配置为 `bindIp: 127.0.0.1`，只允许本地连接
- 需要修改为 `bindIp: 0.0.0.0` 以允许远程连接

**相关文件**:
- 配置脚本: `scripts/configure_mongodb_remote.sh`
- 测试脚本: `scripts/test_new_mongodb.py`
- API测试: `scripts/test_vpn_api.py`

**预期结果**:
```bash
# 成功连接后应看到:
✅ MongoDB 连接成功
✅ VPN 索引创建完成
✅ 读写测试通过
```

#### 依赖项

- 宝塔面板访问权限
- SSH 或终端访问权限
- MongoDB 服务运行正常

#### 验收标准

1. ✅ 能够从本地成功连接到线上 MongoDB
2. ✅ VPN 相关集合和索引已创建
3. ✅ 能够正常读写 VPN 数据
4. ✅ VPN API 端点正常工作
5. ✅ 应用可以正常启动并连接数据库

#### 参考文档

- [MongoDB 配置指南](./MONGODB_GUIDE.md)
- [VPN 功能实现](./README.md)
- [归档详情](./archive/MONGODB_REMOTE_CONNECTION_ARCHIVE.md) ⭐

#### 归档说明

此任务已归档至 `docs/archive/MONGODB_REMOTE_CONNECTION_ARCHIVE.md`，包含：
- 完整的配置步骤
- 数据库连接信息
- 诊断结果和解决方案
- 归档的配置脚本位置

**恢复路径**: 查看归档文档 → 使用 `scripts/archive/` 中的脚本 → 按步骤执行

---

## 已完成任务

### ✅ VPN 管理功能实现（已完成）

**状态**: ✅ 已完成
**完成时间**: 2025-10-20

#### 完成内容

1. ✅ 创建 VPN 实体模型 (`src/core/domain/entities/vpn_connection.py`)
2. ✅ 实现 VPN 仓储层 (`src/infrastructure/database/vpn_repositories.py`)
3. ✅ 实现 VPN 服务层 (`src/services/vpn_service.py`)
4. ✅ 创建 VPN API 端点 (`src/api/v1/endpoints/vpn_management.py`)
5. ✅ 更新数据库索引配置 (`src/infrastructure/database/connection.py`)
6. ✅ 注册 VPN 路由 (`src/api/v1/router.py`)
7. ✅ 创建测试脚本 (`scripts/test_vpn_api.py`, `scripts/test_new_mongodb.py`)

#### API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/vpn/connections` | POST | 创建 VPN 连接 |
| `/api/v1/vpn/connections` | GET | 列出所有连接 |
| `/api/v1/vpn/connections/{id}` | GET | 获取连接详情 |
| `/api/v1/vpn/connect` | POST | 连接 VPN |
| `/api/v1/vpn/disconnect` | POST | 断开 VPN |
| `/api/v1/vpn/connections/{id}/logs` | GET | 查询日志 |
| `/api/v1/vpn/connections/{id}/stats` | GET | 获取统计 |

---

## 更新日志

- **2025-10-20**: 归档线上数据库连接任务，优先开发新功能
- **2025-10-20**: 创建里程碑文档，添加线上数据库连接任务
- **2025-10-20**: VPN 管理功能代码实现完成
