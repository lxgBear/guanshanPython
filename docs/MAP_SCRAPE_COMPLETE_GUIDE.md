# Map + Scrape 完整使用指南

**文档版本**: v2.0.0
**创建日期**: 2025-11-06
**最后更新**: 2025-11-14
**适用版本**: v2.1.0 - v2.1.2

---

## 📋 目录

1. [功能概述](#功能概述)
2. [Map API 详解](#map-api-详解)
3. [API 使用示例](#api-使用示例)
4. [使用场景](#使用场景)
5. [配置参数说明](#配置参数说明)
6. [最佳实践](#最佳实践)
7. [常见问题](#常见问题)

---

## 功能概述

### 什么是 Map + Scrape 模式

Map + Scrape 是一种基于 Firecrawl Map API + Scrape API 的新型网站爬取模式，它将 **URL 发现** 和 **内容获取** 分离，提供比传统 Crawl API 更精确、更高效、更低成本的内容获取能力。

### 核心优势

| 优势 | 说明 | 对比传统Crawl |
|------|------|--------------|
| **精确控制** | 只爬取真正需要的页面 | 节省 35-92% 积分 |
| **时间过滤** | 按发布日期过滤内容 | 避免爬取历史内容 |
| **URL过滤** (v2.1.2) | 智能过滤无用链接 | 减少 40% 无效爬取 |
| **成本透明** | Map (1 credit) + Scrape (N credits) | 可预测的成本 |
| **灵活配置** | 并发控制、延迟控制、错误容忍 | 适应不同网站 |

### 工作流程

```
1. Map API 发现 URL
   ├─ 使用sitemap
   ├─ 智能爬取补充
   └─ 返回URL列表 (固定1 credit)
   ↓
2. URL 过滤 (v2.1.2)
   ├─ 规范化URL
   ├─ 过滤路径关键词 (login, admin, etc.)
   ├─ 过滤文件类型 (pdf, jpg, etc.)
   ├─ 过滤外部链接
   └─ URL去重
   ↓
3. 时间范围过滤 (v2.1.0)
   └─ 按 publishedDate 字段过滤
   ↓
4. 批量并发 Scrape
   ├─ 并发控制 (max_concurrent_scrapes)
   ├─ 请求延迟 (scrape_delay)
   └─ 获取页面内容 (N credits)
   ↓
5. 保存结果
   └─ 返回爬取结果
```

---

## Map API 详解

### Map API 概述

Firecrawl **Map API** 是一个快速发现网站所有可访问URL的工具。

**核心特点**:

| 特点 | 说明 |
|------|------|
| **速度** | 通常<5秒完成整个网站的URL发现 |
| **准确性** | 结合sitemap和智能爬取，发现率>95% |
| **成本** | 固定1 credit，无论网站大小 |
| **输出** | URL列表 + 基本元数据（title, description） |
| **限制** | 默认返回5000个URL |

### 与 Crawl API 对比

| 维度 | Map API | Crawl API |
|------|---------|-----------|
| **目的** | 发现URL | 爬取内容 |
| **速度** | 极快（<5秒） | 较慢（分钟级） |
| **输出** | URL列表 + 元数据 | 完整页面内容 |
| **内容** | ❌ 无页面内容 | ✅ Markdown + HTML |
| **时间信息** | ❌ 无发布时间 | ✅ 完整metadata |
| **积分** | 1 credit | N credits（N=页面数） |
| **适用场景** | URL发现 | 内容获取 |

### 使用决策树

```
需要获取页面内容？
├─ 是 → 使用Crawl API或Map+Scrape
└─ 否 → 使用Map API

需要精确控制爬取哪些页面？
├─ 是 → 使用Map API + Scrape API
└─ 否 → 使用Crawl API

需要节省积分？
├─ 是，只需要部分页面 → Map API + Scrape
└─ 否，需要全部内容 → Crawl API

网站有大量无用链接？ (v2.1.2)
├─ 是 → Map API + URL过滤 + Scrape
└─ 否 → Crawl API或简单Map+Scrape
```

### Map API 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 网站起始URL |
| `search` | string | ❌ | null | 搜索关键词（URL过滤） |
| `limit` | integer | ❌ | 5000 | 返回URL数量限制 |

### Map API 响应格式

```json
{
  "success": true,
  "links": [
    {
      "url": "https://example.com/blog/post-1",
      "title": "First Blog Post",
      "description": "This is my first blog post about..."
    },
    {
      "url": "https://example.com/blog/post-2",
      "title": "Second Blog Post",
      "description": "In this post, I discuss..."
    }
  ]
}
```

---

## API 使用示例

### 创建 Map+Scrape 任务

#### 基础配置

```bash
curl -X POST http://localhost:8000/api/v1/search-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "西藏邮报新闻爬取",
    "description": "使用 Map+Scrape 模式爬取新闻内容",
    "crawl_url": "https://www.thetibetpost.com/",
    "task_type": "map_scrape_website",
    "crawl_config": {
      "map_limit": 5000,
      "max_concurrent_scrapes": 5,
      "scrape_delay": 0.5,
      "only_main_content": false,
      "exclude_tags": [],
      "enable_dedup": true
    },
    "schedule_interval": "HOURLY_1",
    "is_active": true,
    "execute_immediately": true
  }'
```

#### 带时间过滤的配置

```bash
curl -X POST http://localhost:8000/api/v1/search-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "最近30天新闻爬取",
    "crawl_url": "https://example.com",
    "task_type": "map_scrape_website",
    "crawl_config": {
      "map_limit": 5000,
      "start_date": "2025-10-15T00:00:00",
      "end_date": "2025-11-14T23:59:59",
      "max_concurrent_scrapes": 5,
      "scrape_delay": 0.5,
      "only_main_content": false,
      "exclude_tags": [],
      "enable_dedup": true
    }
  }'
```

### 响应示例

```json
{
  "id": "244879584026255360",
  "name": "西藏邮报新闻爬取",
  "task_type": "map_scrape_website",
  "task_mode": "Map + Scrape 组合模式",
  "crawl_url": "https://www.thetibetpost.com/",
  "crawl_config": {
    "only_main_content": false,
    "exclude_tags": [],
    "enable_dedup": true
  },
  "is_active": true,
  "status": "active",
  "execution_count": 0,
  "total_results": 0
}
```

### Python SDK 示例

```python
from firecrawl import FirecrawlApp
from datetime import datetime, timedelta

app = FirecrawlApp(api_key="fc-YOUR_API_KEY")

# 设置时间范围：最近30天
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

# 创建Map+Scrape任务
task = {
    "name": "近期新闻爬取",
    "task_type": "map_scrape_website",
    "crawl_url": "https://example.com",
    "crawl_config": {
        # Map API 配置
        "search": "news",
        "map_limit": 100,

        # 时间过滤
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),

        # Scrape API 配置
        "max_concurrent_scrapes": 5,
        "scrape_delay": 0.5,
        "only_main_content": False,
        "wait_for": 3000,
        "timeout": 90,

        # 错误处理
        "allow_partial_failure": True,
        "min_success_rate": 0.8,

        # v2.1.1: 去重配置
        "enable_dedup": True
    }
}

# 执行任务
result = await execute_task(task)
print(f"爬取成功: {result['total_count']} 个页面")
print(f"积分消耗: {result['credits_used']}")
```

### 任务执行日志示例

```
2025-11-07 01:44:02 - MapScrapeExecutor - INFO - 🚀 开始执行任务: 西藏邮报 Map+Scrape
2025-11-07 01:44:02 - MapScrapeExecutor - INFO - 🗺️  Step 1: 使用 Map API 发现 URL
2025-11-07 01:44:10 - MapScrapeExecutor - INFO - ✅ 发现 195 个URL

2025-11-07 01:44:10 - MapScrapeExecutor - INFO - 🔍 开始URL过滤 (v2.1.2)
2025-11-07 01:44:11 - FilterChain - INFO - ✅ URL过滤完成: 195 → 100 (过滤 95, 48.7%)

2025-11-07 01:44:11 - MapScrapeExecutor - INFO - 🔍 检查已爬取URL去重 (v2.1.1)
2025-11-07 01:44:11 - MapScrapeExecutor - INFO - ✅ URL去重: 发现100个, 已存在10个, 待爬取90个

2025-11-07 01:44:30 - MapScrapeExecutor - INFO - 🔥 Step 2: 批量 Scrape 获取内容（90个URL，并发5）
2025-11-07 01:45:30 - MapScrapeExecutor - INFO - ✅ Scrape 完成: 成功88个, 失败2个

2025-11-07 01:45:30 - SearchResultRepository - INFO - 保存搜索结果成功: 新增88条, 跳过重复0条
2025-11-07 01:45:30 - MapScrapeExecutor - INFO - ✅ 任务执行完成 | 结果数: 88 | 耗时: 88000ms
```

---

## 使用场景

### 场景1: 精确爬取特定内容

**需求**: 只爬取博客文章，不需要其他页面

**方案**:
```python
# 1. 使用Map API发现所有URL，搜索"blog"
map_result = app.map_url("https://example.com", params={"search": "blog"})

# 2. 批量scrape这些URL
for link in map_result['links']:
    content = app.scrape_url(link['url'])
    # 保存内容
```

**优势**:
- 只爬取博客页面，节省积分
- 快速发现所有博客URL
- 避免爬取不相关页面

### 场景2: 时间范围爬取

**需求**: 只获取最近30天的文章

**方案**:
```python
from datetime import datetime, timedelta

# 1. Map发现所有URL
map_result = app.map_url("https://example.com/blog")

# 2. Scrape并过滤
cutoff_date = datetime.now() - timedelta(days=30)
recent_articles = []

for link in map_result['links']:
    content = app.scrape_url(link['url'])

    # 检查发布时间
    pub_date_str = content['metadata'].get('publishedDate')
    if pub_date_str:
        pub_date = datetime.fromisoformat(pub_date_str)
        if pub_date >= cutoff_date:
            recent_articles.append(content)

print(f"发现 {len(recent_articles)} 篇最近30天的文章")
```

**积分对比**:
- Crawl全站: 1000 credits
- Map+Scrape: 1 + 50 = 51 credits（假设50篇符合条件）
- **节省**: 95%

### 场景3: 增量爬取

**需求**: 定期爬取，只获取新增页面

**方案**:
```python
# 首次爬取
initial_urls = set(link['url'] for link in app.map_url("https://example.com")['links'])
save_to_db(initial_urls)

# 后续爬取（7天后）
current_urls = set(link['url'] for link in app.map_url("https://example.com")['links'])
new_urls = current_urls - initial_urls

print(f"发现 {len(new_urls)} 个新页面")

# 只scrape新页面
for url in new_urls:
    content = app.scrape_url(url)
    save_to_db(content)
```

### 场景4: 网站结构分析

**需求**: 分析网站的URL结构

**方案**:
```python
from urllib.parse import urlparse
from collections import Counter

# 获取所有URL
map_result = app.map_url("https://example.com")

# 分析URL路径
paths = [urlparse(link['url']).path for link in map_result['links']]
path_segments = [p.split('/')[1] for p in paths if len(p.split('/')) > 1]

# 统计
counter = Counter(path_segments)
print("URL结构分析:")
for segment, count in counter.most_common(10):
    print(f"  /{segment}/: {count} 个页面")
```

**输出示例**:
```
URL结构分析:
  /blog/: 150 个页面
  /docs/: 80 个页面
  /products/: 30 个页面
  /about/: 5 个页面
```

---

## 配置参数说明

### Map API 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `search` | string | null | URL/标题过滤关键词 |
| `map_limit` | integer | 5000 | 返回URL数量限制 (最大5000) |

### 时间过滤配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start_date` | datetime | null | 开始日期 (ISO 8601格式) |
| `end_date` | datetime | null | 结束日期 (ISO 8601格式) |

### Scrape API 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_concurrent_scrapes` | integer | 5 | 最大并发Scrape数量 (1-10) |
| `scrape_delay` | float | 0.5 | Scrape请求间隔(秒) |
| `only_main_content` | boolean | false | 只获取主要内容 (v2.1.1: 默认false) |
| `exclude_tags` | array | [] | 排除的HTML标签 (v2.1.1: 默认空) |
| `wait_for` | integer | 500 | 页面等待时间(毫秒) (v2.1.1: 500ms) |
| `timeout` | integer | 90 | 单个Scrape超时(秒) |

### 错误处理配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `allow_partial_failure` | boolean | true | 允许部分Scrape失败 |
| `min_success_rate` | float | 0.8 | 最低成功率要求 (0.0-1.0) |

### 去重配置 (v2.1.1)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_dedup` | boolean | true | 启用URL去重 |

### 与其他任务类型的对比

| 任务类型 | task_type | 使用的配置字段 |
|---------|-----------|--------------|
| 关键词搜索 | `search_keyword` | `search_config` |
| 网站爬取 | `crawl_website` | `crawl_config` |
| 单页面爬取 | `scrape_url` | `search_config` |
| **Map+Scrape** | `map_scrape_website` | `crawl_config` ✅ |

---

## 最佳实践

### 1. 合理使用 search 参数

**推荐**:
```python
# 明确的过滤条件
map_result = app.map_url("https://example.com", params={"search": "blog"})
```

**不推荐**:
```python
# 过于宽泛的搜索
map_result = app.map_url("https://example.com", params={"search": "a"})
```

### 2. 设置合理的 limit

**场景判断**:
```python
# 小型网站（<1000页）
params = {"limit": 1000}

# 中型网站（<5000页）
params = {"limit": 5000}  # 默认值

# 大型网站（>5000页）
# 分批map不同section
params = {"limit": 5000, "search": "blog"}
params = {"limit": 5000, "search": "docs"}
```

### 3. 缓存 Map 结果

```python
import json
from pathlib import Path
import time

def get_urls_with_cache(url: str, cache_file: str = "map_cache.json"):
    """使用缓存的Map结果"""
    cache_path = Path(cache_file)

    # 检查缓存
    if cache_path.exists():
        with open(cache_path) as f:
            cached = json.load(f)
            # 检查是否过期（例如：24小时）
            if time.time() - cached['timestamp'] < 86400:
                return cached['links']

    # 重新Map
    result = app.map_url(url)

    # 保存缓存
    with open(cache_path, 'w') as f:
        json.dump({
            'timestamp': time.time(),
            'links': result['links']
        }, f)

    return result['links']
```

### 4. 错误处理

```python
from firecrawl import MapAPIError

try:
    result = app.map_url("https://example.com")
except MapAPIError as e:
    logger.error(f"Map API失败: {e}")
    # Fallback: 使用Crawl API
    result = app.crawl_url("https://example.com")
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

### 5. 并发控制优化

**根据网站响应速度调整**:
```python
# 快速响应的网站
config = {
    "max_concurrent_scrapes": 10,
    "scrape_delay": 0.2
}

# 一般网站
config = {
    "max_concurrent_scrapes": 5,
    "scrape_delay": 0.5
}

# 慢速或有限流保护的网站
config = {
    "max_concurrent_scrapes": 2,
    "scrape_delay": 1.0
}
```

### 6. 完整HTML获取 (v2.1.1)

**推荐配置**:
```json
{
  "only_main_content": false,
  "exclude_tags": []
}
```

这样可以获取完整的HTML内容，为AI处理提供更多上下文。

---

## 常见问题

### Q1: Map API为什么不返回页面内容？

**A**: Map API的设计目标是**快速发现URL**，而不是获取内容。这样可以：
- 极快的响应速度（<5秒）
- 固定的低成本（1 credit）
- 让用户精确控制后续爬取哪些页面

如果需要内容，使用**Map + Scrape**或**Crawl API**。

### Q2: Map API能发现所有页面吗？

**A**: Map API结合了sitemap和智能爬取，发现率通常>95%，但以下情况可能遗漏：
- JavaScript动态生成的链接
- 需要登录才能访问的页面
- 隐藏在复杂交互后的链接

对于完整性要求极高的场景，建议使用**Crawl API**。

### Q3: search 参数如何工作？

**A**: `search`参数会过滤URL和标题中包含关键词的页面：

```python
# 只返回URL或标题包含"blog"的页面
result = app.map_url("https://example.com", params={"search": "blog"})

# 示例结果:
# ✅ https://example.com/blog/post-1
# ✅ https://example.com/about (标题包含"blog")
# ❌ https://example.com/products
```

### Q4: limit 参数如何设置？

**A**: 根据网站规模设置：

| 网站规模 | 推荐limit | 说明 |
|----------|-----------|------|
| 小型 | 1000 | 个人博客、小网站 |
| 中型 | 5000 | 企业网站、中型媒体 |
| 大型 | 分批map | 分section多次调用 |

### Q5: Map API的积分成本如何计算？

**A**: 非常简单：
```
每次Map调用 = 1 credit
```

无论网站大小，无论返回多少URL，都是固定1 credit。

### Q6: 什么时候用Map+Scrape，什么时候用Crawl？

**决策表**:

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 只需要部分页面 | Map+Scrape | 节省积分 |
| 需要时间过滤 | Map+Scrape | 精确控制 |
| 网站有大量无用链接 (v2.1.2) | Map+Scrape | 智能过滤 |
| 完整网站归档 | Crawl | 简单直接 |
| 不确定需要哪些页面 | Crawl | 全面覆盖 |
| 网站结构规则 | Map+Scrape | 高效准确 |
| 网站结构复杂 | Crawl | 更全面 |

### Q7: URL过滤系统 (v2.1.2) 会过滤掉哪些链接？

**A**: 过滤系统会自动过滤以下类型的无用链接：
- **用户操作页面**: login, signup, cart, checkout 等
- **系统功能页面**: admin, api, dashboard, search 等
- **文件下载**: PDF, 图片, 视频, 压缩包等
- **外部链接**: 不在同一域名下的链接
- **重复URL**: 完全相同或规范化后相同的URL

**预计过滤率**: 35-65% (保守估计 40%)

### Q8: 如何验证完整HTML获取？

**A**: 创建任务后，检查结果的HTML内容：

```bash
# 获取任务结果
curl http://localhost:8000/api/v1/search-tasks/{task_id}/results?page=1&page_size=1

# 检查响应中的 html_content 字段
# 应该包含完整的 HTML，包括 <nav>, <footer>, <header> 等标签
```

**验证点**:
1. ✅ `html_content` 字段长度应该比过滤版本更长
2. ✅ 包含 `<nav>`, `<footer>`, `<header>` 等标签
3. ✅ 包含完整的页面结构
4. ✅ `content_hash` 字段已生成（v2.1.1 去重功能）

### Q9: 任务创建失败，提示 422 错误？

**A**: v2.1.1之前版本存在API验证bug，已修复。确保：
- 使用 `task_type: "map_scrape_website"`
- 使用 `crawl_config` 而不是 `search_config`
- 提供必需的 `crawl_url` 字段

### Q10: Scrape 全部失败，提示 waitFor 错误？

**A**: v2.1.1 已修复 timeout 参数问题。确保：
- `wait_for` 使用默认值 500ms
- `timeout` 使用默认值 90秒
- 系统会自动转换单位（秒→毫秒）

---

## 总结

### Map + Scrape 的核心价值

1. **快速发现**: 几秒内获取所有URL
2. **成本固定**: 1 credit无论网站大小
3. **精确控制**: 与Scrape组合实现精确爬取
4. **节省积分**: 避免不必要的页面爬取
5. **智能过滤** (v2.1.2): 自动过滤无用链接

### 最佳使用模式

```
Map API (发现) → URL过滤 (v2.1.2) → 时间/内容过滤 → Scrape API (获取)
```

这种模式在以下场景最有价值：
- 定期监控网站更新
- 只需要特定时间范围的内容
- 网站包含大量无用链接
- 需要精确控制爬取目标
- 关注API积分成本

### 成本优化效果

| 优化阶段 | 积分节省 | 累计节省 |
|---------|---------|---------|
| v2.1.0 基础 | 时间过滤: 最高84% | 84% |
| v2.1.2 URL过滤 | 再节省40% | 最高92% |

---

**文档维护者**: Development Team
**最后更新**: 2025-11-14
**版本**: v2.0.0
