# Firecrawl Map API 使用指南

**文档版本**: v1.0.0
**创建日期**: 2025-11-06

---

## 📋 目录

1. [Map API 概述](#map-api-概述)
2. [与Crawl API对比](#与crawl-api对比)
3. [API详细说明](#api详细说明)
4. [使用场景](#使用场景)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## Map API 概述

### 什么是Map API

Firecrawl **Map API** 是一个快速发现网站所有可访问URL的工具，它可以：

- 🗺️ **快速扫描**：几秒内获取网站的完整URL列表
- 🎯 **智能发现**：使用sitemap + 智能爬取算法
- 🔍 **关键词过滤**：可选的search参数进行URL过滤
- 💰 **固定成本**：每次调用只消耗1个积分

### 核心特点

| 特点 | 说明 |
|------|------|
| **速度** | 通常<5秒完成整个网站的URL发现 |
| **准确性** | 结合sitemap和智能爬取，发现率>95% |
| **成本** | 固定1 credit，无论网站大小 |
| **输出** | URL列表 + 基本元数据（title, description） |
| **限制** | 默认返回5000个URL |

### 工作原理

```
输入: 网站起始URL
   ↓
[优先使用Sitemap]
   ↓
[智能爬取补充]
   ↓
[去重和排序]
   ↓
输出: URL列表 + 元数据
```

---

## 与Crawl API对比

### 功能对比表

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

网站有明确的URL结构？
├─ 是 → Map API效果好
└─ 否 → Crawl API更全面
```

### 组合使用策略

**Map + Scrape（推荐）**：
```
场景: 只需要最近30天的文章
成本: 1 (map) + 100 (scrape) = 101 credits
优势: 精确控制 + 节省积分
```

**Crawl API（传统）**：
```
场景: 需要完整归档
成本: 500-1000 credits
优势: 简单直接
```

---

## API详细说明

### 端点信息

```
POST https://api.firecrawl.dev/v2/map
```

### 请求格式

#### 基本请求

```bash
curl -X POST https://api.firecrawl.dev/v2/map \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -d '{
      "url": "https://example.com"
    }'
```

#### 带搜索过滤

```bash
curl -X POST https://api.firecrawl.dev/v2/map \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -d '{
      "url": "https://example.com",
      "search": "blog",
      "limit": 1000
    }'
```

### 请求参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 网站起始URL |
| `search` | string | ❌ | null | 搜索关键词（URL过滤） |
| `limit` | integer | ❌ | 5000 | 返回URL数量限制 |

### 响应格式

#### 成功响应

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
    },
    {
      "url": "https://example.com/about",
      "title": "About Us",
      "description": "Learn more about our company..."
    }
  ]
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 请求是否成功 |
| `links` | array | URL列表 |
| `links[].url` | string | 完整URL |
| `links[].title` | string | 页面标题 |
| `links[].description` | string | 页面描述 |

### Python SDK 示例

```python
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key="fc-YOUR_API_KEY")

# 基本使用
result = app.map_url("https://example.com")
print(f"发现 {len(result['links'])} 个URL")

# 带搜索过滤
result = app.map_url(
    "https://example.com",
    params={"search": "blog", "limit": 1000}
)

# 处理结果
for link in result['links']:
    print(f"{link['title']}: {link['url']}")
```

### JavaScript SDK 示例

```javascript
import Firecrawl from '@mendable/firecrawl-js';

const app = new Firecrawl({ apiKey: 'fc-YOUR_API_KEY' });

// 基本使用
const result = await app.map('https://example.com');
console.log(`发现 ${result.links.length} 个URL`);

// 带搜索过滤
const blogResult = await app.map('https://example.com', {
  search: 'blog',
  limit: 1000
});

// 处理结果
blogResult.links.forEach(link => {
  console.log(`${link.title}: ${link.url}`);
});
```

---

## 使用场景

### 场景1: 精确爬取特定内容

**需求**：只爬取博客文章，不需要其他页面

**方案**：
```python
# 1. 使用Map API发现所有URL，搜索"blog"
map_result = app.map_url("https://example.com", params={"search": "blog"})

# 2. 批量scrape这些URL
for link in map_result['links']:
    content = app.scrape_url(link['url'])
    # 保存内容
```

**优势**：
- 只爬取博客页面，节省积分
- 快速发现所有博客URL
- 避免爬取不相关页面

### 场景2: 时间范围爬取

**需求**：只获取最近30天的文章

**方案**：
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

**积分对比**：
- Crawl全站：1000 credits
- Map+Scrape：1 + 50 = 51 credits（假设50篇符合条件）
- 节省：95%

### 场景3: 网站结构分析

**需求**：分析网站的URL结构

**方案**：
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

**输出示例**：
```
URL结构分析:
  /blog/: 150 个页面
  /docs/: 80 个页面
  /products/: 30 个页面
  /about/: 5 个页面
```

### 场景4: 增量爬取

**需求**：定期爬取，只获取新增页面

**方案**：
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

---

## 最佳实践

### 1. 合理使用search参数

**推荐**：
```python
# 明确的过滤条件
map_result = app.map_url("https://example.com", params={"search": "blog"})
```

**不推荐**：
```python
# 过于宽泛的搜索
map_result = app.map_url("https://example.com", params={"search": "a"})
```

### 2. 设置合理的limit

**场景判断**：
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

### 3. 缓存Map结果

```python
import json
from pathlib import Path

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

### 5. 结合其他API

**Map + Scrape（精确控制）**：
```python
# 1. Map发现URL
urls = [link['url'] for link in app.map_url("https://example.com")['links']]

# 2. 批量Scrape
results = []
for url in urls[:100]:  # 限制数量
    try:
        content = app.scrape_url(url)
        results.append(content)
    except Exception as e:
        logger.warning(f"Scrape失败 {url}: {e}")

print(f"成功爬取 {len(results)} 个页面")
```

**Map + Crawl（混合方案）**：
```python
# 1. Map分析结构
map_result = app.map_url("https://example.com")
blog_urls = [l['url'] for l in map_result['links'] if '/blog/' in l['url']]

# 2. Crawl特定section
for url in blog_urls[:10]:  # 前10个博客分类
    crawl_result = app.crawl_url(url, limit=50)
    # 处理结果
```

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

### Q3: search参数如何工作？

**A**: `search`参数会过滤URL和标题中包含关键词的页面：

```python
# 只返回URL或标题包含"blog"的页面
result = app.map_url("https://example.com", params={"search": "blog"})

# 示例结果:
# ✅ https://example.com/blog/post-1
# ✅ https://example.com/about (标题包含"blog")
# ❌ https://example.com/products
```

### Q4: limit参数如何设置？

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

**决策表**：

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 只需要部分页面 | Map+Scrape | 节省积分 |
| 需要时间过滤 | Map+Scrape | 精确控制 |
| 完整网站归档 | Crawl | 简单直接 |
| 不确定需要哪些页面 | Crawl | 全面覆盖 |
| 网站结构规则 | Map+Scrape | 高效准确 |
| 网站结构复杂 | Crawl | 更全面 |

---

## 总结

### Map API 的核心价值

1. **快速发现**：几秒内获取所有URL
2. **成本固定**：1 credit无论网站大小
3. **精确控制**：与Scrape组合实现精确爬取
4. **节省积分**：避免不必要的页面爬取

### 最佳使用模式

```
Map API (发现) → 时间/内容过滤 → Scrape API (获取)
```

这种模式在以下场景最有价值：
- 定期监控网站更新
- 只需要特定时间范围的内容
- 需要精确控制爬取目标
- 关注API积分成本

---

**文档维护者**: Development Team
**最后更新**: 2025-11-06
