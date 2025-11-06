# POST /api/v1/search-tasks API 字段文档

## 版本信息

- **API版本**: v2.0.2
- **最后更新**: 2025-11-05
- **端点**: `POST /api/v1/search-tasks`
- **用途**: 创建搜索任务（支持关键词搜索、网站爬取、单页爬取）

---

## 字段验证结果

✅ **所有前端请求字段均已验证有效**，后端完全支持，无需修改代码。

---

## 一、顶层字段（Top-Level Fields）

### 必填字段

| 字段名 | 类型 | 说明 | 验证规则 | 示例 |
|--------|------|------|----------|------|
| `name` | string | 任务名称 | 1-100字符，必填 | `"美国科技公司新闻"` |

### 可选字段

| 字段名 | 类型 | 默认值 | 说明 | 验证规则 | 示例 |
|--------|------|--------|------|----------|------|
| `description` | string | `null` | 任务描述 | 最多500字符 | `"抓取美国科技新闻网站"` |
| `query` | string | `null` | 搜索关键词 | 1-200字符；task_type为search_keyword时必填 | `"OpenAI"` |
| `crawl_url` | string | `null` | 爬取的URL | 最多500字符；task_type为crawl_website或scrape_url时必填 | `"https://example.com"` |
| `target_website` | string | `null` | 主要目标网站 | 最多200字符 | `"openai.com"` |
| `task_type` | string | 自动识别 | 任务类型 | 可选值：`search_keyword`、`crawl_website`、`scrape_url` | `"search_keyword"` |
| `schedule_interval` | string | `"DAILY"` | 调度间隔 | 固定值：`DAILY` | `"DAILY"` |
| `is_active` | boolean | `true` | 是否启用 | true/false | `true` |
| `execute_immediately` | boolean | `true` | 创建后立即执行 | true/false | `true` |

### 任务类型说明（task_type）

| 值 | 说明 | 必填字段 | 配置字段 |
|----|------|----------|----------|
| `search_keyword` | 关键词搜索 | `query` | `search_config` |
| `crawl_website` | 网站爬取 | `crawl_url` | `crawl_config` |
| `scrape_url` | 单页爬取 | `crawl_url` | `search_config` |

**自动识别规则**（v2.0.0）:
- 提供 `query` → `search_keyword`
- 提供 `crawl_url` + `crawl_config` → `crawl_website`
- 提供 `crawl_url` + `search_config` → `scrape_url`

---

## 二、搜索配置字段（search_config）

适用于 `task_type` 为 `search_keyword` 或 `scrape_url` 的任务。

### 基础搜索参数

| 字段名 | 类型 | 默认值 | 说明 | 验证规则 | 示例 |
|--------|------|--------|------|----------|------|
| `limit` | integer | `20` | 搜索结果数量 | 正整数 | `10` |
| `sources` | array[string] | `[]` | 搜索来源 | 字符串数组 | `["google", "bing"]` |
| `categories` | array[string] | `[]` | 搜索类别 | 字符串数组 | `["news", "tech"]` |
| `language` | string | `"zh"` | 搜索语言 | 语言代码 | `"zh"`, `"en"` |

### 域名过滤

| 字段名 | 类型 | 默认值 | 说明 | 示例 |
|--------|------|--------|------|------|
| `include_domains` | array[string] | `[]` | 仅包含的域名 | `["openai.com", "anthropic.com"]` |
| `exclude_domains` | array[string] | `[]` | 排除的域名 | `["example.com"]` |

### 时间范围

| 字段名 | 类型 | 默认值 | 说明 | 可选值 |
|--------|------|--------|------|--------|
| `time_range` | string | `null` | 搜索时间范围 | `"day"`, `"week"`, `"month"`, `"year"` |

### 高级选项

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_ai_summary` | boolean | `false` | 启用AI摘要 |
| `extract_metadata` | boolean | `true` | 提取元数据 |
| `follow_links` | boolean | `false` | 跟踪链接 |
| `max_depth` | integer | `1` | 最大爬取深度 |

### HTML清理选项

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `only_main_content` | boolean | `true` | 仅提取主要内容 |
| `remove_base64_images` | boolean | `false` | 移除base64图片 |
| `block_ads` | boolean | `true` | 屏蔽广告 |
| `scrape_formats` | array[string] | `["markdown", "html", "links"]` | 爬取格式 |
| `include_tags` | array[string] | `null` | 包含的HTML标签 |
| `exclude_tags` | array[string] | `null` | 排除的HTML标签 |
| `wait_for` | integer | `null` | 等待时间（毫秒） |
| `strict_language_filter` | boolean | `true` | 严格语言过滤 |

---

## 三、爬取配置字段（crawl_config）

适用于 `task_type` 为 `crawl_website` 的任务。

### 爬取限制

| 字段名 | 类型 | 默认值 | 说明 | 验证规则 |
|--------|------|--------|------|----------|
| `limit` | integer | `100` | 最大爬取页面数 | 正整数 |
| `max_depth` | integer | `3` | 最大爬取深度 | 正整数 |

### 路径过滤

| 字段名 | 类型 | 默认值 | 说明 | 示例 |
|--------|------|--------|------|------|
| `include_paths` | array[string] | `[]` | 包含的路径模式 | `["/blog/*", "/news/*"]` |
| `exclude_paths` | array[string] | `[]` | 排除的路径模式 | `["/admin/*", "/api/*"]` |
| `allow_backward_links` | boolean | `false` | 允许向后链接 | `true`/`false` |

### 页面爬取选项

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `only_main_content` | boolean | `true` | 仅提取主要内容 |
| `wait_for` | integer | `1000` | 页面加载等待时间（毫秒） |
| `exclude_tags` | array[string] | `["nav", "footer", "header"]` | 排除的HTML标签 |

### 超时设置

| 字段名 | 类型 | 默认值 | 说明 | 单位 |
|--------|------|--------|------|------|
| `timeout` | integer | `300` | 整体爬取超时 | 秒 |
| `poll_interval` | integer | `10` | 状态轮询间隔 | 秒 |

---

## 四、完整请求示例

### 示例 1：网站爬取任务（crawl_website）

```json
{
  "name": "OpenAI 官网爬取",
  "description": "抓取 OpenAI 官方网站内容",
  "crawl_url": "https://openai.com",
  "target_website": "openai.com",
  "task_type": "crawl_website",
  "schedule_interval": "DAILY",
  "is_active": true,
  "crawl_config": {
    "limit": 100,
    "max_depth": 5,
    "include_paths": ["/blog/*", "/research/*"],
    "exclude_paths": ["/api/*"],
    "allow_backward_links": false,
    "only_main_content": true,
    "wait_for": 1000,
    "exclude_tags": ["nav", "footer", "header"],
    "timeout": 300,
    "poll_interval": 10
  }
}
```

### 示例 2：关键词搜索任务（search_keyword）

```json
{
  "name": "AI 技术新闻搜索",
  "description": "搜索人工智能相关的最新技术新闻",
  "query": "artificial intelligence technology news",
  "target_website": "techcrunch.com",
  "task_type": "search_keyword",
  "schedule_interval": "DAILY",
  "is_active": true,
  "search_config": {
    "limit": 10,
    "language": "en",
    "include_domains": ["techcrunch.com", "wired.com"],
    "time_range": "week",
    "enable_ai_summary": true,
    "extract_metadata": true,
    "follow_links": false,
    "max_depth": 1,
    "only_main_content": true,
    "strict_language_filter": true
  }
}
```

### 示例 3：单页爬取任务（scrape_url）

```json
{
  "name": "特定文章爬取",
  "description": "爬取单个文章页面内容",
  "crawl_url": "https://techcrunch.com/2024/01/15/ai-breakthrough",
  "task_type": "scrape_url",
  "schedule_interval": "DAILY",
  "is_active": true,
  "search_config": {
    "only_main_content": true,
    "extract_metadata": true,
    "wait_for": 2000,
    "exclude_tags": ["nav", "footer", "header", "aside"]
  }
}
```

---

## 五、字段使用注意事项

### 1. 任务类型自动识别

系统会根据提供的字段自动识别任务类型：

- 提供 `query` → 自动识别为 `search_keyword`
- 提供 `crawl_url` + `crawl_config` → 自动识别为 `crawl_website`
- 提供 `crawl_url` + `search_config` → 自动识别为 `scrape_url`

### 2. 配置字段互斥

- `search_config` 适用于 `search_keyword` 和 `scrape_url`
- `crawl_config` 适用于 `crawl_website`
- 同时提供两者时，系统根据 `task_type` 选择使用

### 3. 必填字段规则

| task_type | 必填字段 | 配置字段 |
|-----------|----------|----------|
| `search_keyword` | `name`, `query` | `search_config` |
| `crawl_website` | `name`, `crawl_url` | `crawl_config` |
| `scrape_url` | `name`, `crawl_url` | `search_config` |

### 4. 语言代码支持

支持的 `language` 值：
- `zh` - 中文
- `en` - 英文
- `ja` - 日文
- `ko` - 韩文
- `es` - 西班牙文
- `fr` - 法文
- `de` - 德文

### 5. 时间范围说明

`time_range` 字段值及含义：
- `day` - 最近一天
- `week` - 最近一周
- `month` - 最近一个月
- `year` - 最近一年
- `null` - 不限制时间

### 6. 深度爬取说明

- `max_depth` 值说明：
  - `1` - 仅爬取起始页面
  - `2` - 爬取起始页面 + 链接页面
  - `3+` - 递归爬取更深层级
- 建议值：1-5，过深可能导致性能问题

### 7. 域名过滤优先级

- `include_domains` 和 `exclude_domains` 同时存在时：
  - 先应用 `include_domains`（白名单）
  - 再应用 `exclude_domains`（黑名单）
- 建议：优先使用 `include_domains` 限定范围

### 8. HTML清理选项

- `only_main_content=true`：自动移除导航、广告、页脚等噪声
- `exclude_tags`：额外排除特定HTML标签
- `include_tags`：仅保留特定HTML标签（优先级高于exclude_tags）

---

## 六、响应格式

### 成功响应（200 OK）

```json
{
  "status": "success",
  "message": "搜索任务创建成功",
  "data": {
    "task_id": "240011812325298176",
    "name": "AI 技术新闻搜索",
    "task_type": "search_keyword",
    "status": "pending",
    "created_at": "2025-11-05T10:30:00Z"
  }
}
```

### 错误响应（4xx/5xx）

```json
{
  "status": "error",
  "message": "字段验证失败",
  "errors": [
    {
      "field": "query",
      "message": "search_keyword 模式下 query 字段必填"
    }
  ]
}
```

---

## 七、版本历史

### v2.0.2 (2025-11-05)
- ✅ 完整字段文档生成
- ✅ 所有前端请求字段验证通过

### v2.0.0 (2024-10-30)
- 新增 `task_type` 字段支持三种任务类型
- 自动任务类型识别
- 配置字段分离：`search_config` 和 `crawl_config`

### v1.5.x
- 基础搜索任务支持
- 单一配置字段

---

## 八、相关文档

- [API 使用指南 v2](./API_USAGE_GUIDE_V2.md)
- [Firecrawl 架构 v2.0](./FIRECRAWL_ARCHITECTURE_V2.md)
- [搜索配置系统](./SEARCH_CONFIG_SYSTEM.md)
- [系统架构文档](./SYSTEM_ARCHITECTURE.md)

---

**文档维护**: Claude Code
**最后验证**: 2025-11-05
**状态**: ✅ 已验证所有字段有效
