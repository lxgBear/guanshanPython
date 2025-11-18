# 档案管理系统 - 数据库环境准备指南

**日期**: 2025-11-17
**状态**: ⚠️ MariaDB 服务未启动，需要手动配置

---

## 问题诊断

当前系统状态检查结果：

```bash
✅ MongoDB: 运行中 (连接正常)
❌ MariaDB/MySQL: 未运行 (端口 3306 无响应)
❌ Docker: 守护进程未运行
❌ Redis: 未运行 (端口 6379 无响应，非必需)
```

**错误信息**:
```
Can't connect to MySQL server on 'localhost' (port 3306)
```

---

## 解决方案

### 方案 1: 使用 Docker 启动 MariaDB（推荐）

#### 1.1 启动 Docker Desktop

```bash
# 打开 Docker Desktop 应用
open -a Docker

# 等待 Docker 启动完成（约 10-30 秒）
docker ps
```

#### 1.2 启动 MariaDB 容器

```bash
# 如果已有容器，启动现有容器
docker start mariadb

# 或者创建新容器
docker run -d \\
  --name mariadb \\
  -p 3306:3306 \\
  -e MYSQL_ROOT_PASSWORD=rootpass123 \\
  -e MYSQL_DATABASE=intelligent_system \\
  -e MYSQL_USER=app_user \\
  -e MYSQL_PASSWORD=apppass123 \\
  mariadb:latest

# 验证容器运行
docker ps | grep mariadb
```

#### 1.3 执行表创建脚本

```bash
# 等待 MariaDB 完全启动（约 5-10 秒）
sleep 10

# 执行 Python 脚本创建表
python scripts/setup_archive_tables.py
```

---

### 方案 2: 使用 Homebrew 安装 MariaDB

```bash
# 安装 MariaDB
brew install mariadb

# 启动 MariaDB 服务
brew services start mariadb

# 或手动启动
mysql.server start

# 创建数据库和用户
mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS intelligent_system;
CREATE USER IF NOT EXISTS 'app_user'@'localhost' IDENTIFIED BY 'apppass123';
GRANT ALL PRIVILEGES ON intelligent_system.* TO 'app_user'@'localhost';
FLUSH PRIVILEGES;
EOF

# 执行表创建脚本
python scripts/setup_archive_tables.py
```

---

### 方案 3: 手动执行 SQL（如果已有数据库访问权限）

如果您通过其他方式可以访问 MariaDB（如远程数据库、GUI 工具等）：

#### 3.1 使用 MySQL 命令行

```bash
mysql -u app_user -papppass123 -h localhost intelligent_system < scripts/create_nl_archive_tables.sql
```

#### 3.2 使用 GUI 工具

可以使用以下工具：
- **MySQL Workbench**
- **DBeaver**
- **DataGrip**
- **phpMyAdmin**

直接打开 `scripts/create_nl_archive_tables.sql` 文件并执行。

#### 3.3 分步执行 SQL

```sql
-- 1. 创建 nl_user_archives 表
CREATE TABLE IF NOT EXISTS nl_user_archives (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '档案唯一ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    archive_name VARCHAR(255) NOT NULL COMMENT '档案名称',
    description TEXT NULL COMMENT '档案描述',
    tags JSON NULL COMMENT '档案标签',
    search_log_id BIGINT NULL COMMENT '关联搜索记录ID',
    items_count INT DEFAULT 0 COMMENT '档案条目数量',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_search_log_id (search_log_id),
    INDEX idx_created_at (created_at DESC),
    FOREIGN KEY (search_log_id) REFERENCES nl_search_logs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 创建 nl_user_selections 表
CREATE TABLE IF NOT EXISTS nl_user_selections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '条目唯一ID',
    archive_id BIGINT NOT NULL COMMENT '所属档案ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    news_result_id VARCHAR(255) NOT NULL COMMENT '新闻结果ID',
    edited_title VARCHAR(500) NULL,
    edited_summary TEXT NULL,
    user_notes TEXT NULL,
    user_rating INT NULL,
    snapshot_data JSON NOT NULL COMMENT '原始数据快照',
    display_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_archive_id (archive_id),
    INDEX idx_user_id (user_id),
    INDEX idx_news_result_id (news_result_id),
    INDEX idx_display_order (archive_id, display_order),
    FOREIGN KEY (archive_id) REFERENCES nl_user_archives(id) ON DELETE CASCADE,
    UNIQUE KEY uk_archive_news (archive_id, news_result_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 创建 INSERT 触发器
DELIMITER $$
CREATE TRIGGER trg_archive_items_insert
AFTER INSERT ON nl_user_selections
FOR EACH ROW
BEGIN
    UPDATE nl_user_archives
    SET items_count = items_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.archive_id;
END$$
DELIMITER ;

-- 4. 创建 DELETE 触发器
DELIMITER $$
CREATE TRIGGER trg_archive_items_delete
AFTER DELETE ON nl_user_selections
FOR EACH ROW
BEGIN
    UPDATE nl_user_archives
    SET items_count = items_count - 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.archive_id;
END$$
DELIMITER ;
```

---

## 验证数据库表创建

### 方法 1: 使用 Python 脚本验证

```bash
python scripts/setup_archive_tables.py
```

成功输出示例：
```
✅ nl_user_archives 表创建成功
✅ nl_user_selections 表创建成功
✅ INSERT 触发器创建成功
✅ DELETE 触发器创建成功
✅ 表结构验证完成！
```

### 方法 2: 使用 SQL 验证

```sql
-- 查看表结构
DESCRIBE nl_user_archives;
DESCRIBE nl_user_selections;

-- 查看索引
SHOW INDEX FROM nl_user_archives;
SHOW INDEX FROM nl_user_selections;

-- 查看触发器
SHOW TRIGGERS LIKE 'nl_user_%';

-- 统计记录数（应为 0）
SELECT COUNT(*) FROM nl_user_archives;
SELECT COUNT(*) FROM nl_user_selections;
```

---

## 下一步

数据库表创建完成后，继续执行：

### 1. 运行 API 测试

```bash
# 启动服务器（如果未运行）
uvicorn src.main:app --reload

# 访问 API 文档
open http://localhost:8000/api/docs

# 测试档案管理 API
curl -X GET "http://localhost:8000/api/v1/nl-search/archives?user_id=1001&limit=10"
```

### 2. 编写单元测试

```bash
# 创建测试文件
mkdir -p tests/nl_search

# 运行测试
pytest tests/nl_search/ -v --cov=src/services/nl_search
```

### 3. 集成测试

测试完整的档案创建流程：
1. 创建档案 (POST /archives)
2. 查询档案列表 (GET /archives)
3. 获取档案详情 (GET /archives/{id})
4. 更新档案 (PUT /archives/{id})
5. 删除档案 (DELETE /archives/{id})

---

## 常见问题

### Q1: 触发器创建失败？

**原因**: 可能已存在同名触发器

**解决**:
```sql
-- 删除已存在的触发器
DROP TRIGGER IF EXISTS trg_archive_items_insert;
DROP TRIGGER IF EXISTS trg_archive_items_delete;

-- 重新创建触发器（参考上方 SQL）
```

### Q2: 外键约束失败？

**原因**: nl_search_logs 表不存在

**解决**:
```sql
-- 选项 1: 先创建 nl_search_logs 表
-- （如果有创建脚本，先执行）

-- 选项 2: 暂时移除外键约束
ALTER TABLE nl_user_archives
DROP FOREIGN KEY nl_user_archives_ibfk_1;

-- 选项 3: 修改表定义，移除 FOREIGN KEY 行
```

### Q3: JSON 字段不支持？

**原因**: MySQL/MariaDB 版本过低（需要 5.7.8+ 或 MariaDB 10.2.7+）

**解决**:
```sql
-- 升级数据库版本，或使用 TEXT 类型替代 JSON
ALTER TABLE nl_user_archives MODIFY tags TEXT NULL;
ALTER TABLE nl_user_selections MODIFY snapshot_data TEXT NOT NULL;
```

---

## 配置信息

当前项目使用的数据库配置（来自 `.env`）：

```bash
MARIADB_URL=mysql+aiomysql://app_user:apppass123@localhost:3306/intelligent_system
MARIADB_POOL_SIZE=20
MARIADB_MAX_OVERFLOW=10
MARIADB_POOL_TIMEOUT=30
```

**数据库连接参数**:
- **Host**: localhost
- **Port**: 3306
- **Database**: intelligent_system
- **User**: app_user
- **Password**: apppass123

---

## 技术支持

如果遇到其他问题，请检查：

1. **日志文件**: `/tmp/uvicorn.log`
2. **MariaDB 日志**: `/usr/local/var/mysql/*.err` (Homebrew)
3. **Docker 日志**: `docker logs mariadb`

**项目文档**:
- 设计文档: `claudedocs/NL_SEARCH_ARCHIVE_SYSTEM_DESIGN.md`
- SQL 脚本: `scripts/create_nl_archive_tables.sql`
- Python 创建脚本: `scripts/setup_archive_tables.py`
