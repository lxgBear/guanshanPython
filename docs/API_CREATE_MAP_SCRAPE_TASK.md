# 创建 Map+Scrape 任务 API 示例

## v2.1.1 完整 HTML 配置

创建 Map+Scrape 任务时，使用以下配置获取完整 HTML：

### 正确的 API 请求

```bash
curl -X POST http://localhost:8000/api/v1/search-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "西藏邮报 Map+Scrape",
    "description": "使用 Map+Scrape 模式爬取西藏邮报网站",
    "crawl_url": "https://www.thetibetpost.com/",
    "task_type": "map_scrape_website",
    "crawl_config": {
      "limit": 10,
      "max_depth": 2,
      "only_main_content": false,
      "wait_for": 3000,
      "exclude_tags": [],
      "timeout": 300,
      "poll_interval": 10,
      "map_limit": 5000,
      "max_concurrent_scrapes": 5,
      "scrape_delay": 0.5,
      "enable_dedup": true
    },
    "schedule_interval": "HOURLY_1",
    "is_active": true,
    "execute_immediately": true
  }'
```

### 关键配置说明

#### v2.1.1 完整 HTML 配置
```json
{
  "only_main_content": false,  // ✅ 获取完整 HTML（不仅提取主要内容）
  "exclude_tags": []           // ✅ 不排除任何 HTML 标签
}
```

#### Map+Scrape 专用配置
```json
{
  "map_limit": 5000,              // Map API 返回的 URL 数量上限（最大 5000）
  "max_concurrent_scrapes": 5,    // 最大并发 Scrape 数量
  "scrape_delay": 0.5,            // Scrape 请求间隔（秒）
  "enable_dedup": true            // 启用 URL 去重（v2.1.1 新增）
}
```

#### 时间过滤配置（可选）
```json
{
  "start_date": "2025-01-01T00:00:00",  // 只保留此日期之后的内容
  "end_date": "2025-12-31T23:59:59"     // 只保留此日期之前的内容
}
```

### 响应示例

成功创建任务后，API 返回：

```json
{
  "id": "244879584026255360",
  "name": "西藏邮报 Map+Scrape",
  "task_type": "map_scrape_website",
  "task_mode": "Map + Scrape 组合模式",
  "crawl_url": "https://www.thetibetpost.com/",
  "crawl_config": {
    "only_main_content": false,
    "exclude_tags": [],
    // ... 其他配置
  },
  "is_active": true,
  "status": "active",
  "execution_count": 0,
  "total_results": 0,
  // ... 其他字段
}
```

### 任务执行日志示例

```
2025-11-07 01:44:02 - MapScrapeExecutor - INFO - 🚀 开始执行任务: 西藏邮报 Map+Scrape
2025-11-07 01:44:02 - MapScrapeExecutor - INFO - 🗺️  Step 1: 使用 Map API 发现 URL
2025-11-07 01:44:10 - MapScrapeExecutor - INFO - ✅ 发现 50 个URL
2025-11-07 01:44:10 - MapScrapeExecutor - INFO - 🔍 检查已爬取URL去重
2025-11-07 01:44:10 - MapScrapeExecutor - INFO - ✅ URL去重: 发现50个, 已存在10个, 待爬取40个
2025-11-07 01:44:30 - MapScrapeExecutor - INFO - 🔥 Step 2: 批量 Scrape 获取内容（40个URL，并发5）
2025-11-07 01:45:00 - MapScrapeExecutor - INFO - ✅ Scrape 完成: 成功38个, 失败2个
2025-11-07 01:45:00 - SearchResultRepository - INFO - 保存搜索结果成功: 新增38条, 跳过重复0条
2025-11-07 01:45:00 - MapScrapeExecutor - INFO - ✅ 任务执行完成 | 结果数: 38 | 耗时: 58000ms
```

## 与其他任务类型的对比

### 1. 关键词搜索任务 (search_keyword)
使用 `search_config`：
```json
{
  "task_type": "search_keyword",
  "query": "Tibet news",
  "search_config": {
    "limit": 10,
    "language": "zh",
    "only_main_content": false,
    "exclude_tags": []
  }
}
```

### 2. 网站爬取任务 (crawl_website)
使用 `crawl_config`：
```json
{
  "task_type": "crawl_website",
  "crawl_url": "https://example.com",
  "crawl_config": {
    "limit": 100,
    "max_depth": 3,
    "only_main_content": false,
    "exclude_tags": []
  }
}
```

### 3. 单页面爬取任务 (scrape_url)
使用 `search_config`：
```json
{
  "task_type": "scrape_url",
  "crawl_url": "https://example.com/article",
  "search_config": {
    "only_main_content": false,
    "exclude_tags": [],
    "wait_for": 2000
  }
}
```

### 4. Map+Scrape 任务 (map_scrape_website) ✅
使用 `crawl_config`：
```json
{
  "task_type": "map_scrape_website",
  "crawl_url": "https://example.com",
  "crawl_config": {
    "limit": 10,
    "only_main_content": false,
    "exclude_tags": [],
    "map_limit": 5000,
    "enable_dedup": true
  }
}
```

## ✅ v2.1.1 Hotfix: API Validation 修复

**问题**: 之前创建 `map_scrape_website` 任务会返回 422 错误
**原因**: Pydantic 验证规则缺少 `map_scrape_website` 类型
**状态**: ✅ 已修复 (2025-11-07 02:14)

### 修复前（❌ 错误）
```
HTTP 422 Unprocessable Entity
"string does not match regex \"^(search_keyword|crawl_website|scrape_url)$\""
```

### 修复后（✅ 正确）
```json
{
  "id": "244879584026255360",
  "task_type": "map_scrape_website",
  "task_mode": "Map + Scrape 组合模式",
  "status": "active"
}
```

---

## 常见错误

### 错误 1: 使用旧的过滤配置
```json
❌ "only_main_content": true,
❌ "exclude_tags": ["nav", "footer", "header"]

✅ "only_main_content": false,
✅ "exclude_tags": []
```

### 错误 2: 配置字段不匹配任务类型
```json
❌ task_type: "map_scrape_website" + search_config
✅ task_type: "map_scrape_website" + crawl_config
```

### 错误 3: 缺少必需字段
```json
❌ 缺少 crawl_url
✅ 必须提供 crawl_url 用于 Map API
```

## 验证完整 HTML 获取

创建任务后，检查结果的 HTML 内容：

```bash
# 获取任务结果
curl http://localhost:8000/api/v1/search-tasks/{task_id}/results?page=1&page_size=1

# 检查响应中的 html_content 字段
# 应该包含完整的 HTML，包括 <nav>, <footer>, <header> 等标签
```

### 验证点
1. ✅ `html_content` 字段长度应该比过滤版本更长
2. ✅ 包含 `<nav>`, `<footer>`, `<header>` 等标签
3. ✅ 包含完整的页面结构
4. ✅ `content_hash` 字段已生成（v2.1.1 去重功能）
