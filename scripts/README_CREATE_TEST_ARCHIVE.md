# 测试存档数据创建脚本使用说明

## 概述

`create_test_archive.py` 是一个用于快速创建测试存档数据的独立脚本，主要用于前端调试和开发测试。

**特点**：
- ✅ 无需启动FastAPI服务器
- ✅ 直接连接MongoDB数据库
- ✅ 支持多种创建模式（交互式、命令行、批量、快速）
- ✅ 自动创建完整的数据源和存档关系
- ✅ 支持三级分类和自定义标签
- ✅ 提供查询和清理功能

## 快速开始

### 1. 快速创建测试数据（推荐）

最简单的方式，创建带默认值的测试数据：

```bash
# 创建1条测试数据
python scripts/create_test_archive.py --quick 1

# 创建5条测试数据
python scripts/create_test_archive.py --quick 5
```

### 2. 命令行参数创建

使用命令行参数指定详细信息：

```bash
python scripts/create_test_archive.py \
  --title "人工智能技术突破" \
  --url "https://example.com/ai-breakthrough" \
  --content "人工智能在2025年取得了重大突破，深度学习模型性能显著提升..." \
  --creator "test_user" \
  --description "AI技术新闻" \
  --primary-category "科技" \
  --secondary-category "人工智能" \
  --tertiary-category "深度学习" \
  --tags "AI,深度学习,技术突破"
```

### 3. 交互式创建

运行脚本后按提示输入信息：

```bash
python scripts/create_test_archive.py
```

按照提示输入：
- 标题
- URL
- 内容（输入多行，最后输入 `END` 结束）
- 创建者
- 描述
- 分类信息
- 标签

### 4. 批量创建（从JSON文件）

准备一个JSON文件（参考 `test_archive_data_example.json`），然后：

```bash
python scripts/create_test_archive.py --batch scripts/test_archive_data_example.json
```

JSON文件格式：

```json
[
  {
    "title": "新闻标题",
    "url": "https://example.com/news",
    "content": "完整的新闻内容...",
    "creator": "editor_name",
    "description": "数据源描述",
    "primary_category": "科技",
    "secondary_category": "人工智能",
    "tertiary_category": "深度学习",
    "custom_tags": ["AI", "技术"]
  }
]
```

## 管理功能

### 查看最近的存档

```bash
# 查看最近10条存档
python scripts/create_test_archive.py --list 10

# 查看最近20条存档
python scripts/create_test_archive.py --list 20
```

输出示例：

```
📋 最近 10 条存档:
--------------------------------------------------------------------------------
1. [252328892051845122] 测试新闻 #1
   URL: https://example.com/test-news-1
   创建时间: 2025-11-27 07:04:55.909000
   数据源ID: 252328892051845121
```

### 清理测试数据

删除所有测试数据（标记为 `metadata.test=true` 的记录）：

```bash
python scripts/create_test_archive.py --cleanup
```

**注意**：会要求确认，输入 `yes` 才会执行删除。

## 参数说明

### 基础参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--title` | 标题 | - |
| `--url` | URL | - |
| `--content` | 完整内容 | - |
| `--creator` | 创建者 | test_user |
| `--description` | 数据源描述 | - |
| `--snippet` | 摘要（自动生成） | content前150字符 |
| `--data-type` | 数据类型 | instant |

### 分类参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--primary-category` | 一级分类 | 科技、金融、能源 |
| `--secondary-category` | 二级分类 | 人工智能、区块链 |
| `--tertiary-category` | 三级分类 | 深度学习、金融科技 |
| `--tags` | 自定义标签（逗号分隔） | AI,技术,创新 |

### 模式参数

| 参数 | 说明 |
|------|------|
| `--quick N` | 快速创建N条测试数据 |
| `--batch FILE` | 从JSON文件批量创建 |
| `--list N` | 列出最近N条存档 |
| `--cleanup` | 清理所有测试数据 |

## 使用场景

### 场景1：前端开发测试

前端开发者需要测试存档列表显示：

```bash
# 快速创建10条测试数据
python scripts/create_test_archive.py --quick 10

# 前端可以通过API查询这些数据进行测试
# GET http://localhost:8000/api/v1/archives?limit=10
```

### 场景2：测试搜索功能

创建不同分类的数据用于测试搜索：

```bash
# 创建科技类新闻
python scripts/create_test_archive.py \
  --title "AI技术突破" \
  --url "https://example.com/ai" \
  --content "AI技术内容..." \
  --primary-category "科技" \
  --secondary-category "人工智能"

# 创建金融类新闻
python scripts/create_test_archive.py \
  --title "区块链应用" \
  --url "https://example.com/blockchain" \
  --content "区块链内容..." \
  --primary-category "金融" \
  --secondary-category "区块链"
```

### 场景3：批量导入示例数据

使用准备好的JSON文件批量导入：

```bash
python scripts/create_test_archive.py --batch scripts/test_archive_data_example.json
```

### 场景4：测试完成后清理

```bash
python scripts/create_test_archive.py --cleanup
```

## 数据结构

脚本会自动创建：

### 1. DataSource（数据源）

- **状态**：CONFIRMED（已确定）
- **包含字段**：
  - 标题、描述
  - 三级分类系统
  - 自定义标签
  - 原始数据引用列表

### 2. ArchivedData（存档数据）

- **包含字段**：
  - 完整内容（不截断）
  - 标题、URL、摘要
  - 数据源ID和原始数据ID
  - 存档元信息（时间、原因、操作者）
  - 元数据标记（`test: true`）

## 注意事项

1. **测试数据标记**：所有通过此脚本创建的数据都会被标记为 `metadata.test = true`，方便后续清理。

2. **数据类型**：默认创建 `instant` 类型的数据，可以通过 `--data-type scheduled` 指定为定时任务类型。

3. **自动关联**：脚本会自动创建 DataSource 和 ArchivedData 的完整关联关系，无需手动处理。

4. **ID生成**：使用雪花算法生成全局唯一ID，与生产数据一致。

5. **MongoDB连接**：脚本直接使用项目的数据库配置（`src/infrastructure/database/connection.py`），无需额外配置。

## 常见问题

### Q: 如何验证数据是否创建成功？

A: 使用 `--list` 参数查看最近创建的存档：

```bash
python scripts/create_test_archive.py --list 10
```

或通过API查询：

```bash
curl http://localhost:8000/api/v1/archives?limit=10
```

### Q: 如何删除单条测试数据？

A: 可以通过MongoDB直接删除，或者使用 `--cleanup` 清理所有测试数据。

### Q: 能否创建已确定状态的数据源？

A: 脚本创建的数据源默认为 CONFIRMED 状态，符合存档数据的要求。

### Q: 批量创建时遇到错误怎么办？

A: 脚本会记录详细的错误日志，检查：
1. JSON文件格式是否正确
2. 必填字段（title、url、content）是否提供
3. MongoDB连接是否正常

## 技术细节

- **直接数据库操作**：不通过API，直接写入MongoDB
- **完整实体创建**：使用项目的Entity类（DataSource、ArchivedData）
- **事务支持**：虽然脚本未使用事务，但创建逻辑保证了数据一致性
- **ID生成**：使用 `generate_string_id()` 生成雪花算法ID
- **异步操作**：使用 asyncio 和 Motor 驱动进行异步数据库操作

## 示例工作流

完整的测试工作流示例：

```bash
# 1. 快速创建10条测试数据
python scripts/create_test_archive.py --quick 10

# 2. 查看创建的数据
python scripts/create_test_archive.py --list 10

# 3. 前端进行测试...

# 4. 测试完成后清理
python scripts/create_test_archive.py --cleanup
```

## 获取帮助

查看完整的命令行帮助：

```bash
python scripts/create_test_archive.py --help
```
