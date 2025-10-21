# MongoDB启动故障排查指南

**错误**: `MongoNetworkError: connect ECONNREFUSED 127.0.0.1:27017`
**原因**: MongoDB服务未运行
**解决时间**: 2-5分钟

---

## 🚨 你当前的问题

```
MongoNetworkError: connect ECONNREFUSED 127.0.0.1:27017
```

这个错误表示：**MongoDB服务没有启动**

---

## ✅ 解决方案（按顺序尝试）

### 方案1: 启动MongoDB服务（最常用）

在宝塔终端执行：

```bash
# 启动MongoDB
systemctl start mongod

# 检查状态
systemctl status mongod
```

**成功标志**：
```
● mongod.service - MongoDB Database Server
   Loaded: loaded
   Active: active (running)
```

按 `q` 退出状态查看。

**设置开机自启动**：
```bash
systemctl enable mongod
```

**然后再次尝试连接**：
```bash
/www/server/mongodb/bin/mongosh
```

---

### 方案2: 通过宝塔面板启动（推荐新手）

1. **进入宝塔面板**: https://hancens.top:18314/cbece14e
2. **点击左侧菜单**: 软件商店 → 已安装
3. **找到MongoDB**: 在列表中找到MongoDB
4. **点击右侧**: 启动 按钮
5. **等待**: 直到状态显示"运行中"
6. **回到终端**: 再次尝试连接

---

### 方案3: 检查MongoDB配置文件

如果启动失败，可能是配置文件有错误。

```bash
# 查看MongoDB日志
tail -50 /var/log/mongodb/mongod.log

# 或宝塔MongoDB日志路径
tail -50 /www/server/mongodb/logs/mongod.log
```

**常见错误**：

#### 错误1: 权限问题
```
Permission denied
```

**解决**：
```bash
# 修复数据目录权限
chown -R mongodb:mongodb /var/lib/mongo
chown -R mongodb:mongodb /var/log/mongodb

# 或宝塔路径
chown -R mongodb:mongodb /www/server/mongodb/data
chown -R mongodb:mongodb /www/server/mongodb/logs
```

#### 错误2: 端口被占用
```
Address already in use
```

**检查并释放端口**：
```bash
# 查看占用27017端口的进程
netstat -tuln | grep 27017
lsof -i :27017

# 如果有旧进程，杀掉它
kill -9 $(lsof -t -i:27017)

# 重新启动
systemctl start mongod
```

#### 错误3: 磁盘空间不足
```
No space left on device
```

**检查磁盘空间**：
```bash
df -h
```

**解决**：清理磁盘空间或增加磁盘。

---

### 方案4: 手动启动MongoDB（调试模式）

```bash
# 使用配置文件手动启动
/www/server/mongodb/bin/mongod --config /www/server/mongodb/config.conf

# 或者
mongod --config /etc/mongod.conf
```

**观察输出**，看是否有错误信息。

**如果成功启动**，按 `Ctrl + C` 停止，然后使用systemctl正常启动：
```bash
systemctl start mongod
```

---

### 方案5: 重新安装MongoDB（最后手段）

如果以上方法都失败，可能需要重新安装。

#### 通过宝塔重装

1. 宝塔面板 → 软件商店 → 已安装
2. 找到MongoDB → 卸载
3. 重新搜索MongoDB → 安装
4. 等待安装完成

#### 手动重装（Ubuntu/Debian）

```bash
# 卸载旧版本
apt-get purge mongodb-org*
rm -rf /var/lib/mongo
rm -rf /var/log/mongodb

# 安装新版本
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-6.0.list
apt-get update
apt-get install -y mongodb-org

# 启动服务
systemctl start mongod
systemctl enable mongod
```

---

## 🔍 完整诊断流程

按顺序执行以下命令，记录每一步的输出：

```bash
# 1. 检查MongoDB服务状态
systemctl status mongod

# 2. 检查MongoDB进程
ps aux | grep mongod

# 3. 检查MongoDB端口
netstat -tuln | grep 27017

# 4. 检查MongoDB日志
tail -100 /www/server/mongodb/logs/mongod.log

# 5. 检查配置文件
cat /www/server/mongodb/config.conf

# 6. 检查数据目录权限
ls -la /www/server/mongodb/data

# 7. 检查磁盘空间
df -h

# 8. 尝试启动
systemctl start mongod

# 9. 再次检查状态
systemctl status mongod

# 10. 测试连接
/www/server/mongodb/bin/mongosh
```

---

## 📋 快速命令参考

### 服务管理命令

```bash
# 启动MongoDB
systemctl start mongod

# 停止MongoDB
systemctl stop mongod

# 重启MongoDB
systemctl restart mongod

# 查看状态
systemctl status mongod

# 开机自启
systemctl enable mongod

# 禁用自启
systemctl disable mongod
```

### 日志查看命令

```bash
# 查看最新日志
tail -f /www/server/mongodb/logs/mongod.log

# 查看最后100行
tail -100 /www/server/mongodb/logs/mongod.log

# 查看完整日志
less /www/server/mongodb/logs/mongod.log

# 搜索错误
grep -i error /www/server/mongodb/logs/mongod.log
```

### 连接测试命令

```bash
# 本地连接
/www/server/mongodb/bin/mongosh

# 指定主机和端口
/www/server/mongodb/bin/mongosh --host 127.0.0.1 --port 27017

# 测试端口
telnet 127.0.0.1 27017
nc -zv 127.0.0.1 27017
```

---

## ✅ 成功启动后的步骤

一旦MongoDB成功启动，继续配置：

```bash
# 1. 连接MongoDB
/www/server/mongodb/bin/mongosh

# 2. 创建管理员用户
use admin
db.createUser({
  user: "admin",
  pwd: "Admin@Guanshan2024!",
  roles: [{ role: "root", db: "admin" }]
})

# 3. 继续按照 BAOTA_TERMINAL_MONGODB_SETUP.md 操作
```

---

## 🆘 如果仍然无法启动

**收集以下信息**：

1. **系统信息**：
   ```bash
   cat /etc/os-release
   uname -a
   ```

2. **MongoDB版本**：
   ```bash
   /www/server/mongodb/bin/mongod --version
   ```

3. **错误日志**：
   ```bash
   tail -100 /www/server/mongodb/logs/mongod.log
   ```

4. **配置文件**：
   ```bash
   cat /www/server/mongodb/config.conf
   ```

5. **systemctl详细状态**：
   ```bash
   systemctl status mongod -l
   journalctl -u mongod -n 50
   ```

把这些信息发给我，我可以帮你进一步诊断。

---

## 常见问题FAQ

### Q1: 为什么MongoDB没有自动启动？

**原因**：
- 首次安装后可能默认不启动
- 配置文件有错误导致启动失败
- 没有设置开机自启

**解决**：
```bash
systemctl start mongod
systemctl enable mongod
```

### Q2: 启动后立即停止怎么办？

**检查日志**：
```bash
journalctl -u mongod -n 100
tail -100 /www/server/mongodb/logs/mongod.log
```

通常是配置文件错误或权限问题。

### Q3: 宝塔面板显示运行中，但终端连接失败？

**可能原因**：
- 宝塔和系统的MongoDB是两个不同实例
- 端口冲突

**解决**：
```bash
# 确认正在运行的MongoDB进程
ps aux | grep mongod

# 查看监听端口
netstat -tuln | grep mongod
```

---

**创建时间**: 2025-10-16
**适用系统**: Ubuntu/Debian + 宝塔面板
