# MongoDB 远程访问指南

**目标用户**: 需要远程访问MongoDB进行AI分析的团队成员

**最后更新**: 2025-10-16

---

## 📋 快速连接信息

### 连接字符串

```bash
# 生产环境连接（只读分析用户）
mongodb://ai_analyst:your_password@your_server_ip:37017/intelligent_system?authSource=intelligent_system

# 应用程序连接（读写用户）
mongodb://app_user:your_password@your_server_ip:37017/intelligent_system?authSource=intelligent_system
```

**参数说明**:
- `your_server_ip`: 宝塔服务器IP地址（向管理员获取）
- `37017`: 外部访问端口
- `intelligent_system`: 数据库名称
- `authSource=intelligent_system`: 认证数据库

---

## 🔧 连接工具设置

### 1. MongoDB Compass（推荐）

**下载地址**: https://www.mongodb.com/try/download/compass

**连接步骤**:

1. 打开 MongoDB Compass
2. 点击 "New Connection"
3. 填写连接信息:
   ```
   Connection String:
   mongodb://ai_analyst:your_password@your_server_ip:37017/intelligent_system?authSource=intelligent_system
   ```
4. 点击 "Connect"

**界面说明**:
- **左侧面板**: 数据库和集合列表
- **中间区域**: 文档浏览和查询界面
- **右侧面板**: 索引和性能统计

### 2. Python 连接

#### 安装依赖

```bash
pip install pymongo pandas
```

#### 基础连接示例

```python
from pymongo import MongoClient
import pandas as pd

# 连接数据库
client = MongoClient(
    "mongodb://ai_analyst:your_password@your_server_ip:37017/intelligent_system?authSource=intelligent_system"
)
db = client['intelligent_system']

# 查看所有集合
print("可用集合:", db.list_collection_names())

# 查询示例：获取搜索任务
tasks = db['search_tasks'].find().limit(10)
df = pd.DataFrame(list(tasks))
print(df.head())

# 记得关闭连接
client.close()
```

### 3. Studio 3T（可选）

**下载地址**: https://studio3t.com/download/

**连接步骤**:
1. 新建连接 → Manual Configuration
2. Server tab:
   - Server: `your_server_ip`
   - Port: `37017`
3. Authentication tab:
   - Mode: Username / Password
   - Database: `intelligent_system`
   - Username: `ai_analyst`
   - Password: `your_password`
4. 测试连接 → 保存

---

## 📊 数据库结构说明

### 主要集合（Collections）

| 集合名称 | 说明 | 主要字段 |
|---------|------|---------|
| `search_tasks` | 搜索任务 | `task_id`, `query`, `crawl_url`, `status`, `created_at` |
| `instant_search_tasks` | 即时搜索任务 | `task_id`, `query`, `target_website`, `status` |
| `instant_search_results` | 即时搜索结果 | `task_id`, `url`, `title`, `markdown_content` |
| `search_results` | 搜索结果 | `url`, `title`, `content`, `task_id` |
| `scheduler_tasks` | 调度器任务 | `task_id`, `status`, `next_execution_time` |

### 字段说明

**SearchTask（搜索任务）**:
```python
{
    "task_id": "uuid字符串",
    "query": "搜索关键词",
    "crawl_url": "爬取URL（可选）",
    "target_website": "目标网站",
    "search_config": {
        "include_domains": ["domain1.com", "domain2.com"],
        "max_results": 10
    },
    "schedule_config": {
        "enabled": true,
        "interval": "0 0 * * *"  # cron表达式
    },
    "status": "pending|running|completed|failed",
    "created_at": "2025-10-16T10:00:00",
    "updated_at": "2025-10-16T10:30:00"
}
```

**InstantSearchResult（即时搜索结果）**:
```python
{
    "task_id": "关联的任务ID",
    "url": "结果URL",
    "title": "页面标题",
    "markdown_content": "Markdown格式内容",
    "created_at": "2025-10-16T10:00:00"
}
```

---

## 💡 AI分析常见用例

### 1. Pandas 数据分析

```python
from pymongo import MongoClient
import pandas as pd
import matplotlib.pyplot as plt

# 连接数据库
client = MongoClient("mongodb://ai_analyst:password@ip:37017/intelligent_system?authSource=intelligent_system")
db = client['intelligent_system']

# 分析任务状态分布
tasks = list(db['search_tasks'].find({}, {'status': 1, 'created_at': 1}))
df = pd.DataFrame(tasks)

# 统计各状态数量
status_counts = df['status'].value_counts()
print("任务状态分布:")
print(status_counts)

# 可视化
status_counts.plot(kind='bar', title='任务状态分布')
plt.show()

# 分析每日任务创建趋势
df['date'] = pd.to_datetime(df['created_at']).dt.date
daily_tasks = df.groupby('date').size()
print("\n每日任务创建数:")
print(daily_tasks)
```

### 2. LangChain + MongoDB RAG

```python
from langchain.vectorstores import MongoDBAtlasVectorSearch
from langchain.embeddings import OpenAIEmbeddings
from pymongo import MongoClient

# 连接MongoDB
client = MongoClient("mongodb://ai_analyst:password@ip:37017/intelligent_system?authSource=intelligent_system")
db = client['intelligent_system']

# 获取搜索结果内容
results = db['instant_search_results'].find({}, {'markdown_content': 1, 'title': 1, 'url': 1})

# 构建文档列表
documents = []
for result in results:
    documents.append({
        'content': result.get('markdown_content', ''),
        'metadata': {
            'title': result.get('title', ''),
            'url': result.get('url', '')
        }
    })

print(f"已加载 {len(documents)} 个文档用于RAG分析")

# 后续可以使用向量数据库进行语义搜索
# embeddings = OpenAIEmbeddings()
# vector_store = ... (根据需求配置)
```

### 3. Jupyter Notebook 分析

```python
# 在Jupyter Notebook中运行

import pymongo
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 连接数据库
client = pymongo.MongoClient("mongodb://ai_analyst:password@ip:37017/intelligent_system?authSource=intelligent_system")
db = client['intelligent_system']

# 1. 查看数据库概况
print("=== 数据库概况 ===")
for collection_name in db.list_collection_names():
    count = db[collection_name].count_documents({})
    print(f"{collection_name}: {count} 条记录")

# 2. 分析最近7天的任务趋势
seven_days_ago = datetime.now() - timedelta(days=7)
recent_tasks = list(db['search_tasks'].find(
    {'created_at': {'$gte': seven_days_ago.isoformat()}},
    {'status': 1, 'created_at': 1, 'query': 1}
))
df_recent = pd.DataFrame(recent_tasks)
print(f"\n最近7天创建任务: {len(df_recent)} 个")

# 3. 分析搜索关键词词频
all_tasks = list(db['search_tasks'].find({}, {'query': 1}))
queries = [task.get('query', '') for task in all_tasks if task.get('query')]
print(f"\n总搜索关键词数: {len(queries)}")

# 4. 分析目标网站分布
websites = list(db['search_tasks'].find({}, {'target_website': 1}))
website_df = pd.DataFrame(websites)
website_counts = website_df['target_website'].value_counts().head(10)
print("\n前10个目标网站:")
print(website_counts)
```

### 4. 数据导出（CSV/Excel）

```python
from pymongo import MongoClient
import pandas as pd

# 连接
client = MongoClient("mongodb://ai_analyst:password@ip:37017/intelligent_system?authSource=intelligent_system")
db = client['intelligent_system']

# 导出搜索任务到CSV
tasks = list(db['search_tasks'].find())
df = pd.DataFrame(tasks)

# 保存为CSV
df.to_csv('search_tasks_export.csv', index=False, encoding='utf-8-sig')
print(f"已导出 {len(df)} 条任务到 search_tasks_export.csv")

# 保存为Excel（需要安装 openpyxl）
df.to_excel('search_tasks_export.xlsx', index=False, engine='openpyxl')
print(f"已导出 {len(df)} 条任务到 search_tasks_export.xlsx")
```

---

## ⚠️ 注意事项

### 权限限制

**ai_analyst 用户权限（只读）**:
- ✅ 可以查询所有集合
- ✅ 可以导出数据
- ✅ 可以创建临时索引（用于分析）
- ❌ 不能插入、更新、删除数据
- ❌ 不能创建或删除集合

**app_user 用户权限（读写）**:
- ✅ 所有读取权限
- ✅ 可以插入、更新、删除文档
- ✅ 可以创建索引
- ❌ 不能删除集合或数据库

### 安全提醒

1. **不要分享密码**: 连接字符串包含密码，请妥善保管
2. **IP白名单**: 确认您的IP已添加到服务器白名单（联系管理员）
3. **只读分析**: 使用 `ai_analyst` 用户进行数据分析，避免误操作
4. **SSL连接**: 生产环境建议使用SSL加密连接（联系管理员配置）
5. **数据安全**: 导出的数据文件请加密保存，不要上传公开仓库

### 性能建议

1. **限制查询结果**: 使用 `.limit()` 限制返回文档数量
2. **使用投影**: 只查询需要的字段，例如 `.find({}, {'field1': 1, 'field2': 1})`
3. **避免全表扫描**: 查询时尽量使用索引字段（`task_id`, `status`, `created_at`）
4. **批量操作**: 大量数据处理时使用游标（cursor）而不是一次性加载

---

## 🔍 常用查询示例

### 查询指定状态的任务

```python
# 查询所有pending状态的任务
pending_tasks = db['search_tasks'].find({'status': 'pending'})
print(f"待处理任务: {db['search_tasks'].count_documents({'status': 'pending'})} 个")
```

### 按时间范围查询

```python
from datetime import datetime, timedelta

# 查询最近24小时的任务
yesterday = (datetime.now() - timedelta(days=1)).isoformat()
recent_tasks = db['search_tasks'].find({
    'created_at': {'$gte': yesterday}
})
```

### 查询包含特定关键词的任务

```python
# 查询包含"Myanmar"的搜索任务
myanmar_tasks = db['search_tasks'].find({
    'query': {'$regex': 'Myanmar', '$options': 'i'}  # i表示不区分大小写
})
```

### 聚合统计

```python
# 统计每个网站的任务数量
pipeline = [
    {'$group': {
        '_id': '$target_website',
        'count': {'$sum': 1}
    }},
    {'$sort': {'count': -1}},
    {'$limit': 10}
]

result = list(db['search_tasks'].aggregate(pipeline))
for item in result:
    print(f"{item['_id']}: {item['count']} 个任务")
```

---

## 🆘 故障排查

### 连接失败

**错误**: `ServerSelectionTimeoutError`

**可能原因**:
1. 服务器IP地址错误
2. 端口未开放（检查防火墙）
3. 您的IP未加入白名单
4. MongoDB服务未启动

**解决方法**:
```bash
# 1. 测试网络连通性
ping your_server_ip

# 2. 测试端口连通性
telnet your_server_ip 37017

# 3. 联系管理员确认白名单配置
```

### 认证失败

**错误**: `Authentication failed`

**可能原因**:
1. 用户名或密码错误
2. 认证数据库错误
3. 用户权限未配置

**解决方法**:
- 确认连接字符串中包含 `?authSource=intelligent_system`
- 向管理员确认用户名和密码
- 检查用户是否已在正确的数据库中创建

### 权限不足

**错误**: `not authorized on intelligent_system to execute command`

**原因**: `ai_analyst` 用户尝试执行写操作

**解决方法**:
- 仅执行查询操作（`.find()`, `.aggregate()`）
- 如需写入权限，联系管理员使用 `app_user` 账户

---

## 📞 技术支持

**遇到问题时**:
1. 查看本文档的"故障排查"部分
2. 联系系统管理员获取连接信息
3. 查看完整部署文档: `docs/DEPLOYMENT_BAOTA_MONGODB.md`

**管理员联系方式**: （请管理员填写）
- 姓名: ___________
- 邮箱: ___________
- 企业微信: ___________

---

## 📚 相关文档

- **部署文档**: `docs/DEPLOYMENT_BAOTA_MONGODB.md` - MongoDB宝塔部署完整指南
- **API文档**: `docs/API_USAGE_GUIDE.md` - 系统API使用说明
- **字段参考**: `claudedocs/SEARCH_TASK_FIELDS_GUIDE.md` - 搜索任务字段详解

---

**文档版本**: v1.0
**更新日期**: 2025-10-16
**维护者**: 技术团队
