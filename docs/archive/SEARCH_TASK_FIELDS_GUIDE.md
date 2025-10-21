# SearchTask 字段完整指南

> 定时任务配置的权威参考文档
> 版本: v1.0 | 更新时间: 2025-10-16

---

## 📋 目录

- [概述](#概述)
- [核心字段详解](#核心字段详解)
  - [target_website](#1-target_website-目标网站)
  - [crawl_url](#2-crawl_url-定时爬取url)
  - [include_domains](#3-include_domains-包含域名)
- [字段关系与互斥分析](#字段关系与互斥分析)
- [执行模式详解](#执行模式详解)
- [验证逻辑实现](#验证逻辑实现)
- [最佳实践](#最佳实践)
- [前端集成指南](#前端集成指南)
- [常见问题 FAQ](#常见问题-faq)

---

## 概述

SearchTask 包含三个关键配置字段，理解它们的作用和关系对于正确配置定时任务至关重要。

### 三个字段的角色定位

```
┌─────────────────────────────────────────────────────────┐
│ SearchTask 字段体系                                      │
├─────────────────────────────────────────────────────────┤
│ target_website     → 前端显示标签（元数据）              │
│ crawl_url          → 模式决策者（Scrape vs Search）      │
│ include_domains    → Search模式下的域名过滤器            │
└─────────────────────────────────────────────────────────┘
```

### 核心关系

- **target_website** 和 **include_domains**: 同步关系（`target_website ← include_domains[0]`）
- **crawl_url** 和 **include_domains**: **互斥关系**（只有一个生效）

---

## 核心字段详解

### 1. target_website (目标网站)

#### 基本信息

| 属性 | 值 |
|------|---|
| **类型** | `Optional[str]` |
| **位置** | SearchTask 顶层字段 |
| **必填** | ❌ 否 |
| **作用** | 前端展示用元数据 |
| **影响爬取** | ❌ 否 |

#### 实现原理

```python
# search_task.py:131-151
def extract_target_website(self) -> Optional[str]:
    """从 search_config 中提取主要目标网站"""
    include_domains = self.search_config.get('include_domains', [])
    if include_domains and len(include_domains) > 0:
        return include_domains[0]  # 取第一个域名
    return None

def sync_target_website(self) -> None:
    """同步 target_website 字段"""
    if not self.target_website:
        self.target_website = self.extract_target_website()
```

#### 用途说明

✅ **用于**:
- 前端任务列表显示
- 用户友好的标识
- 快速识别监控目标

❌ **不用于**:
- 实际的爬取逻辑
- 搜索范围限制
- API 调用参数

#### 代码位置

- **定义**: `src/core/domain/entities/search_task.py:75`
- **同步逻辑**: `src/core/domain/entities/search_task.py:144-151`
- **前端API**: `src/api/v1/endpoints/search_tasks_frontend.py:224`

---

### 2. crawl_url (定时爬取URL)

#### 基本信息

| 属性 | 值 |
|------|---|
| **类型** | `Optional[str]` |
| **位置** | SearchTask 顶层字段 |
| **必填** | ❌ 否（但与 query 二选一） |
| **作用** | 直接爬取指定URL |
| **影响爬取** | ✅ **是** - 决定执行模式 |

#### 优先级逻辑

```python
# task_scheduler.py:278-320
async def _execute_search_task(self, task_id: str):
    if task.crawl_url:
        # 方案1: 使用 Firecrawl Scrape API 爬取指定网址
        logger.info(f"🌐 使用网址爬取模式: {task.crawl_url}")
        result_batch = await self._execute_crawl_task_internal(task, start_time)
    else:
        # 方案2: 使用 Firecrawl Search API 关键词搜索
        logger.info(f"🔍 使用关键词搜索模式: {task.query}")
        result_batch = await self.search_adapter.search(...)
```

#### 字段交互表

| crawl_url 状态 | 使用的 API | query 字段 | include_domains 字段 |
|---------------|-----------|-----------|---------------------|
| ✅ 已设置 | **Scrape API** | ❌ **忽略** | ❌ **忽略** |
| ❌ 未设置 | **Search API** | ✅ **使用** | ✅ **使用** |

#### 使用场景

| 场景 | 推荐 | 理由 |
|------|------|------|
| 监控网站首页 | ✅ **crawl_url** | 固定URL，直接爬取更快 |
| 监控RSS订阅 | ✅ **crawl_url** | RSS URL固定，爬取高效 |
| 关键词搜索 | ❌ 不适用 | 应使用 Search 模式 |

#### 代码位置

- **定义**: `src/core/domain/entities/search_task.py:76`
- **执行逻辑**: `src/services/task_scheduler.py:278-320`
- **Crawl实现**: `src/services/task_scheduler.py:373-420`

---

### 3. include_domains (包含域名)

#### 基本信息

| 属性 | 值 |
|------|---|
| **类型** | `List[str]` |
| **位置** | `search_config` 内部 |
| **必填** | ❌ 否（建议设置） |
| **作用** | 限制搜索结果域名 |
| **影响爬取** | ✅ **是** - 仅在 Search 模式 |

#### 工作原理

```python
# firecrawl_search_adapter.py:161-167
if config.get('include_domains'):
    domains = config['include_domains']
    if domains:
        # 转换为 site: 操作符
        site_operators = ' OR '.join([f'site:{domain}' for domain in domains])
        final_query = f"({site_operators}) {query}"
```

#### 实际转换示例

**用户配置**:
```json
{
  "query": "Myanmar economy",
  "search_config": {
    "include_domains": ["www.gnlm.com.mm", "www.irrawaddy.com"]
  }
}
```

**实际搜索查询**:
```
"(site:www.gnlm.com.mm OR site:www.irrawaddy.com) Myanmar economy"
```

#### 生效条件

| 条件 | 是否生效 | 说明 |
|------|---------|------|
| Search 模式 | ✅ **生效** | 转换为 `site:` 操作符 |
| Crawl 模式 | ❌ **忽略** | 直接爬取URL，不需要过滤 |

#### 代码位置

- **定义**: `src/core/domain/entities/search_config.py:100`
- **转换逻辑**: `src/infrastructure/search/firecrawl_search_adapter.py:161-167`
- **提取逻辑**: `src/core/domain/entities/search_task.py:138-141`

---

## 字段关系与互斥分析

### 核心关系总结

```
┌─────────────────────────────────────────────┐
│ 字段关系图                                   │
├─────────────────────────────────────────────┤
│ target_website ← include_domains[0]         │
│   (自动同步，仅显示用)                        │
│                                             │
│ crawl_url ⊻ include_domains                 │
│   (互斥关系，只有一个生效)                    │
└─────────────────────────────────────────────┘
```

### 互斥关系详解

#### 什么是互斥关系？

- **不是冲突** (Conflict): 不会导致错误
- **而是互斥** (Mutually Exclusive): 根据优先级只有一个生效

#### 优先级规则

```
crawl_url 优先级 > include_domains 优先级
```

**决策树**:
```
任务执行
    ↓
检查 crawl_url
    ├─ ✅ 存在 → Scrape API
    │            ├─ ✅ 使用 crawl_url
    │            ├─ ❌ 忽略 query
    │            └─ ❌ 忽略 include_domains
    │
    └─ ❌ 不存在 → Search API
                 ├─ ✅ 使用 query
                 └─ ✅ 使用 include_domains
```

#### 互斥关系矩阵

| crawl_url | include_domains | 实际行为 | API |
|-----------|-----------------|---------|-----|
| ✅ 设置 | ❌ 未设置 | 直接爬取 URL | Scrape API |
| ❌ 未设置 | ✅ 设置 | 域名过滤搜索 | Search API |
| ✅ 设置 | ✅ 设置 | **爬取 URL，忽略域名过滤** ⚠️ | Scrape API |
| ❌ 未设置 | ❌ 未设置 | 无域名过滤搜索 | Search API |

### 问题场景：同时设置

#### 配置示例

```json
{
  "name": "GNLM News Monitor",
  "crawl_url": "https://www.gnlm.com.mm/",
  "query": "Myanmar economy",
  "search_config": {
    "include_domains": ["www.gnlm.com.mm", "www.other-site.com"]
  }
}
```

#### 用户预期 vs 实际结果

| 维度 | 用户预期 | 实际结果 |
|------|---------|---------|
| **爬取范围** | 两个网站 | 只有 crawl_url 指定的单个页面 |
| **搜索关键词** | 使用 "Myanmar economy" | ❌ 被忽略 |
| **域名过滤** | 两个域名都爬取 | ❌ include_domains 被忽略 |
| **执行模式** | 不确定 | Scrape API（因为 crawl_url 存在） |

#### 原有问题

- ⚠️ **没有警告提示**：用户不知道 `include_domains` 被忽略
- ⚠️ **预期不符**：配置与实际行为不一致
- ⚠️ **调试困难**：需要查看代码才能理解

---

## 执行模式详解

### 两种模式对比

| 维度 | **Search API 模式** | **Scrape API 模式** |
|------|-------------------|-------------------|
| **触发条件** | `crawl_url` 为空 | `crawl_url` 存在 |
| **API 端点** | `/v2/search` | `/v1/scrape` |
| **核心字段** | `query` + `include_domains` | `crawl_url` |
| **适用场景** | 关键词搜索多个来源 | 爬取固定 URL |
| **结果数量** | 多条（limit 控制） | 单条（一个页面） |
| **域名过滤** | ✅ 支持 | ❌ 不适用 |

### Search 模式执行流程

```
1. 构建查询
   query = "Myanmar economy"
   include_domains = ["www.gnlm.com.mm"]
   ↓
2. 转换域名过滤
   final_query = "site:www.gnlm.com.mm Myanmar economy"
   ↓
3. 调用 Firecrawl Search API
   POST /v2/search
   {
     "query": "site:www.gnlm.com.mm Myanmar economy",
     "limit": 20
   }
   ↓
4. 解析多条搜索结果
   返回: SearchResultBatch (20条结果)
```

### Crawl 模式执行流程

```
1. 准备爬取选项
   url = "https://www.gnlm.com.mm/"
   options = {"wait_for": 2000, ...}
   ↓
2. 调用 Firecrawl Scrape API
   POST /v1/scrape
   {
     "url": "https://www.gnlm.com.mm/",
     "formats": ["markdown", "html"]
   }
   ↓
3. 获取页面内容
   返回: CrawlResult (单个页面)
   ↓
4. 转换为 SearchResult
   返回: SearchResultBatch (1条结果)
```

---

## 验证逻辑实现

### 验证模块

新增文件: `src/api/v1/endpoints/search_tasks_validation.py`

#### 核心验证函数

##### 1. 互斥关系验证

```python
def validate_crawl_url_and_include_domains(
    crawl_url: Optional[str],
    search_config: Dict[str, Any]
) -> None:
    """验证 crawl_url 和 include_domains 的互斥关系"""
    include_domains = search_config.get('include_domains', [])

    if crawl_url and include_domains:
        # 记录警告但不报错（向后兼容）
        logger.warning(
            "⚠️ crawl_url 和 include_domains 同时设置，"
            "include_domains 将被忽略。"
        )
```

##### 2. 模式字段验证

```python
def validate_mode_fields(
    crawl_url: Optional[str],
    query: str,
    search_config: Dict[str, Any]
) -> None:
    """验证模式字段的完整性"""

    if crawl_url:
        # Crawl 模式：其他字段可选
        return

    # Search 模式：query 必填
    if not query or not query.strip():
        raise HTTPException(400, "Search 模式下，query 字段不能为空")

    # 建议配置 include_domains
    if not search_config.get('include_domains'):
        logger.info("💡 建议：配置 include_domains 可提高搜索精准度")
```

##### 3. 主验证入口

```python
def validate_task_creation(
    crawl_url: Optional[str],
    query: str,
    search_config: Dict[str, Any]
) -> None:
    """任务创建验证（主入口）"""
    validator = SearchTaskFieldValidator()

    # 1. 验证互斥关系（警告但不报错）
    validator.validate_crawl_url_and_include_domains(crawl_url, search_config)

    # 2. 验证模式字段完整性
    validator.validate_mode_fields(crawl_url, query, search_config)
```

### API 集成

更新文件: `src/api/v1/endpoints/search_tasks_frontend.py`

```python
from src.api.v1.endpoints.search_tasks_validation import validate_task_creation

async def create_search_task(task_data: SearchTaskCreate):
    """创建新的搜索任务"""
    try:
        # 验证调度间隔
        ScheduleInterval.from_value(task_data.schedule_interval)

        # ✅ 验证 crawl_url 和 include_domains
        validate_task_creation(
            crawl_url=task_data.crawl_url,
            query=task_data.query,
            search_config=task_data.search_config
        )

        # 创建任务...
```

### 验证流程图

```
创建任务请求
    ↓
验证调度间隔
    ↓
验证互斥关系
    ├─ crawl_url 和 include_domains 同时存在？
    │   ├─ 是 → ⚠️ 记录警告日志
    │   └─ 否 → 继续
    ↓
验证模式字段
    ├─ Crawl 模式 (crawl_url 存在)
    │   └─ 无需额外验证
    │
    ├─ Search 模式 (crawl_url 为空)
    │   ├─ query 为空？→ ❌ 返回 400 错误
    │   └─ include_domains 为空？→ 💡 记录建议日志
    ↓
创建任务成功
```

---

## 最佳实践

### 1. 模式选择指南

| 需求场景 | 推荐模式 | 配置示例 | 理由 |
|---------|---------|---------|------|
| 监控网站首页 | **Crawl** | `crawl_url: "https://..."` | URL固定，直接爬取更快 |
| 监控RSS订阅 | **Crawl** | `crawl_url: "https://.../feed"` | RSS URL固定，爬取高效 |
| 搜索单个网站内容 | **Search** | `include_domains: ["site.com"]` | 关键词搜索，范围可控 |
| 搜索多个网站 | **Search** | `include_domains: [多个域名]` | 覆盖范围广，可配置 |
| 新闻聚合 | **Search** | `include_domains: [新闻网站]` | 关键词匹配，结果丰富 |

### 2. 正确配置示例

#### ✅ Crawl 模式

```json
{
  "name": "GNLM Homepage Monitor",
  "crawl_url": "https://www.gnlm.com.mm/",
  "target_website": "www.gnlm.com.mm",
  "search_config": {
    "wait_for": 2000,
    "include_tags": ["article", "main"],
    "exclude_tags": ["nav", "footer"]
  },
  "schedule_interval": "HOURLY_6"
}
```

**特点**:
- ✅ 只设置 `crawl_url`（核心字段）
- ✅ `target_website` 用于显示
- ✅ `search_config` 配置爬取选项
- ❌ 不需要 `query` 和 `include_domains`

---

#### ✅ Search 模式（单网站）

```json
{
  "name": "GNLM Economy Search",
  "query": "Myanmar economy",
  "target_website": "www.gnlm.com.mm",
  "search_config": {
    "limit": 20,
    "include_domains": ["www.gnlm.com.mm"],
    "language": "en",
    "time_range": "week"
  },
  "schedule_interval": "DAILY"
}
```

**特点**:
- ✅ 设置 `query`（搜索关键词）
- ✅ 设置 `include_domains`（域名过滤）
- ✅ `target_website` 自动同步
- ❌ 不设置 `crawl_url`

---

#### ✅ Search 模式（多网站）

```json
{
  "name": "Tech News Aggregator",
  "query": "AI 最新进展",
  "target_website": "www.36kr.com",
  "search_config": {
    "limit": 30,
    "include_domains": [
      "www.36kr.com",
      "tech.sina.com.cn",
      "www.ithome.com"
    ],
    "language": "zh",
    "time_range": "day"
  },
  "schedule_interval": "HOURLY_12"
}
```

**实际查询**:
```
"(site:www.36kr.com OR site:tech.sina.com.cn OR site:www.ithome.com) AI 最新进展"
```

---

### 3. 错误配置示例

#### ❌ 混淆模式

```json
{
  "crawl_url": "https://www.gnlm.com.mm/",
  "query": "Myanmar economy",
  "search_config": {
    "include_domains": ["www.gnlm.com.mm", "www.other-site.com"]
  }
}
```

**问题**:
- ⚠️ 同时设置了 `crawl_url` 和 `include_domains`
- ⚠️ `query` 和 `include_domains` 会被忽略
- ⚠️ 实际只会爬取 `crawl_url` 指定的单个页面

**系统行为**:
```
⚠️ 警告日志:
crawl_url 和 include_domains 同时设置，include_domains 将被忽略。
建议：使用 crawl_url 时，无需设置 include_domains。
```

---

### 4. 配置优化建议

#### Search 模式优化

```json
{
  "query": "Myanmar economy news",
  "search_config": {
    "include_domains": ["www.gnlm.com.mm"],
    "limit": 20,
    "language": "en",
    "time_range": "week",
    "scrape_formats": ["markdown", "html"],
    "only_main_content": true
  }
}
```

**优化点**:
- ✅ 使用 `scrape_formats` 获取完整内容
- ✅ 使用 `only_main_content` 过滤无关内容
- ✅ 使用 `time_range` 限制时间范围
- ✅ 合理设置 `limit` 避免过度消耗

---

#### Crawl 模式优化

```json
{
  "crawl_url": "https://www.gnlm.com.mm/",
  "search_config": {
    "wait_for": 2000,
    "include_tags": ["article", "main", "section"],
    "exclude_tags": ["nav", "footer", "aside", "advertisement"],
    "scrape_formats": ["markdown", "html", "links"]
  }
}
```

**优化点**:
- ✅ 使用 `wait_for` 等待页面加载
- ✅ 使用 `include_tags` 只爬取内容区域
- ✅ 使用 `exclude_tags` 排除导航等无关内容
- ✅ 获取多种格式便于后续处理

---

## 前端集成指南

### UI 设计推荐

#### 模式切换界面

```
┌─────────────────────────────────────────────────────┐
│ 创建定时任务                                         │
├─────────────────────────────────────────────────────┤
│ 执行模式:                                            │
│ ○ 关键词搜索模式 (Search API)                        │
│ ● URL爬取模式 (Scrape API)                           │
├─────────────────────────────────────────────────────┤
│ 【URL爬取模式】                                      │
│ 爬取URL:  [https://www.gnlm.com.mm/          ]      │
│                                                      │
│ ⚠️ 提示：URL爬取模式下，以下配置将被忽略：            │
│   - 搜索关键词 (query)                               │
│   - 域名过滤 (include_domains)                       │
│                                                      │
│ 高级选项:                                            │
│   等待时间: [2000] ms                                │
│   包含标签: [article, main]                          │
│   排除标签: [nav, footer]                            │
└─────────────────────────────────────────────────────┘
```

### TypeScript 类型定义

```typescript
interface TaskMode {
  mode: 'search' | 'crawl';
  mode_display: string;
  description: string;
  api_used: string;
  active_fields: string[];
  ignored_fields: string[];
  warning?: string;
}

interface SearchTaskForm {
  // 模式选择
  mode: 'search' | 'crawl';

  // 基本信息
  name: string;
  description?: string;
  schedule_interval: string;

  // Search 模式字段
  query?: string;
  include_domains?: string[];

  // Crawl 模式字段
  crawl_url?: string;

  // 通用字段
  target_website?: string;
  search_config: Record<string, any>;
}
```

### 表单验证逻辑

```typescript
function validateTaskForm(form: SearchTaskForm): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (form.mode === 'search') {
    // Search 模式验证
    if (!form.query || form.query.trim() === '') {
      errors.push('Search 模式下，搜索关键词不能为空');
    }

    if (!form.include_domains || form.include_domains.length === 0) {
      errors.push('建议：配置目标域名可以提高搜索精准度');
    }

    // Crawl 字段应该清空
    if (form.crawl_url) {
      errors.push('Search 模式下不需要设置爬取URL');
    }

  } else if (form.mode === 'crawl') {
    // Crawl 模式验证
    if (!form.crawl_url || form.crawl_url.trim() === '') {
      errors.push('Crawl 模式下，爬取URL不能为空');
    }

    // Search 字段应该清空
    if (form.query || form.include_domains?.length > 0) {
      errors.push('⚠️ Crawl 模式下，query 和 include_domains 将被忽略');
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
```

### 模式切换处理

```typescript
function handleModeChange(newMode: 'search' | 'crawl') {
  if (newMode === 'crawl') {
    // 切换到 Crawl 模式
    form.query = '';
    form.include_domains = [];

    showNotification({
      type: 'warning',
      message: 'Crawl 模式下，query 和 include_domains 配置将不生效'
    });

  } else if (newMode === 'search') {
    // 切换到 Search 模式
    form.crawl_url = '';

    showNotification({
      type: 'info',
      message: '建议配置 include_domains 以提高搜索精准度'
    });
  }

  form.mode = newMode;
}
```

### 获取模式描述 API

```typescript
// 后端 API 调用
async function getTaskModeDescription(task: SearchTask): Promise<TaskMode> {
  // 方式1: 直接根据字段判断
  if (task.crawl_url) {
    return {
      mode: 'crawl',
      mode_display: 'URL爬取模式',
      description: `直接爬取: ${task.crawl_url}`,
      api_used: 'Firecrawl Scrape API',
      active_fields: ['crawl_url'],
      ignored_fields: ['query', 'include_domains'],
      warning: task.search_config.include_domains?.length > 0
        ? 'include_domains 在此模式下不生效'
        : undefined
    };
  } else {
    return {
      mode: 'search',
      mode_display: '关键词搜索模式',
      description: '基于关键词搜索多个来源',
      api_used: 'Firecrawl Search API',
      active_fields: ['query', 'include_domains'],
      ignored_fields: ['crawl_url']
    };
  }
}

// 在 UI 中使用
const modeInfo = await getTaskModeDescription(task);

// 显示模式徽章
<Badge color={modeInfo.mode === 'crawl' ? 'blue' : 'green'}>
  {modeInfo.mode_display}
</Badge>

// 显示警告（如果有）
{modeInfo.warning && (
  <Alert type="warning">{modeInfo.warning}</Alert>
)}

// 显示生效字段
<div>
  <strong>生效字段:</strong>
  {modeInfo.active_fields.join(', ')}
</div>

<div>
  <strong>被忽略字段:</strong>
  {modeInfo.ignored_fields.join(', ')}
</div>
```

---

## 常见问题 FAQ

### Q1: `crawl_url` 和 `include_domains` 是否冲突？

**A**: 不是冲突，而是**互斥关系**。

- ✅ 可以同时存在于配置中
- ⚠️ 但执行时只有一个生效
- 📊 优先级：`crawl_url` > `include_domains`

**详细说明**: `src/api/v1/endpoints/search_tasks_validation.py:16-32`

---

### Q2: 为什么同时设置时没有报错？

**A**: 为了**向后兼容**。

现有任务可能已经同时设置了两个字段，直接禁止会导致这些任务无法更新。我们选择：
- ⚠️ 记录警告日志
- ✅ 让任务正常执行
- ❌ 不强制报错

**改进**: 已添加验证逻辑，会在日志中记录警告。

---

### Q3: `target_website` 会影响爬取范围吗？

**A**: ❌ **不会**。

`target_website` 只是前端显示用的元数据，不影响实际爬取逻辑。

**实际过滤字段**: `include_domains` (Search 模式下)

**代码证据**: `src/core/domain/entities/search_task.py:131-151`

---

### Q4: 如果只想爬一个网站，用 `crawl_url` 还是 `include_domains`？

**A**: 取决于需求。

| 需求 | 推荐方案 | 理由 |
|------|---------|------|
| **固定页面**（如首页、RSS） | `crawl_url` | URL 固定，直接爬取更快 |
| **关键词搜索**（如搜索"经济新闻"） | `include_domains` | 基于关键词，范围可控 |

---

### Q5: Search 模式下，`include_domains` 必须设置吗？

**A**: ❌ 不是必填，但**强烈建议**。

- 不设置：会搜索整个互联网（可能不相关）
- 设置：限制在指定网站（提高精准度）

**系统行为**: 不设置时会记录建议日志。

---

### Q6: 如何获取任务的执行模式？

**A**: 通过判断 `crawl_url` 是否存在。

```python
if task.crawl_url:
    mode = "crawl"
else:
    mode = "search"
```

**或使用工具函数**:
```python
from src.api.v1.endpoints.search_tasks_validation import get_task_mode_description

mode_info = get_task_mode_description(
    crawl_url=task.crawl_url,
    search_config=task.search_config
)
# 返回: {"mode": "crawl" | "search", "active_fields": [...], ...}
```

---

### Q7: 前端如何实现模式切换？

**A**: 使用单选按钮 + 条件渲染。

```typescript
<RadioGroup value={mode} onChange={handleModeChange}>
  <Radio value="search">关键词搜索</Radio>
  <Radio value="crawl">URL爬取</Radio>
</RadioGroup>

{mode === 'search' && (
  <Input name="query" />
  <MultiSelect name="include_domains" />
)}

{mode === 'crawl' && (
  <Input name="crawl_url" />
  <Alert>query 和 include_domains 在此模式下不生效</Alert>
)}
```

---

### Q8: 更新任务时如何处理字段同步？

**A**: 后端已自动处理。

```python
# search_tasks_frontend.py:142-147
if task_data.search_config is not None:
    task.search_config = task_data.search_config

    # 如果更新了 search_config 但没有显式更新 target_website
    if not target_website_explicitly_updated:
        # 自动同步 target_website
        task.target_website = task.extract_target_website()
```

**前端建议**: 更新 `include_domains` 时，同时更新 `target_website` 以保持一致性。

---

## 📚 相关代码位置

### 字段定义

| 字段 | 文件 | 行号 |
|------|------|------|
| `target_website` | `src/core/domain/entities/search_task.py` | 75 |
| `crawl_url` | `src/core/domain/entities/search_task.py` | 76 |
| `include_domains` | `src/core/domain/entities/search_config.py` | 100 |

### 核心逻辑

| 功能 | 文件 | 行号 |
|------|------|------|
| 模式判断 | `src/services/task_scheduler.py` | 278-320 |
| Crawl 执行 | `src/services/task_scheduler.py` | 373-420 |
| Search 执行 | `src/infrastructure/search/firecrawl_search_adapter.py` | 47-154 |
| 域名转换 | `src/infrastructure/search/firecrawl_search_adapter.py` | 161-167 |
| 字段同步 | `src/core/domain/entities/search_task.py` | 131-151 |

### 验证逻辑

| 功能 | 文件 | 描述 |
|------|------|------|
| 完整验证模块 | `src/api/v1/endpoints/search_tasks_validation.py` | 所有验证函数 |
| API 集成 | `src/api/v1/endpoints/search_tasks_frontend.py` | 213-218 |

---

## 📊 快速参考卡片

### 三字段速查表

| 字段 | 类型 | 位置 | 必填 | 作用 | 影响爬取 |
|------|------|------|------|------|---------|
| `target_website` | `str` | 顶层 | ❌ | 前端显示 | ❌ |
| `crawl_url` | `str` | 顶层 | ❌ | 决定模式 | ✅ |
| `include_domains` | `List[str]` | search_config | ❌ | 域名过滤 | ✅ (Search 模式) |

### 模式决策树

```
配置任务
    ↓
是否需要爬取固定URL?
    ├─ 是 → 使用 crawl_url (Scrape API)
    └─ 否 → 使用 query + include_domains (Search API)
```

### 验证检查清单

- [ ] 是否只选择了一种模式？
- [ ] Search 模式：是否设置了 `query`？
- [ ] Search 模式：是否设置了 `include_domains`？
- [ ] Crawl 模式：是否设置了有效的 `crawl_url`？
- [ ] 是否避免了同时设置 `crawl_url` 和 `include_domains`？

---

## 📅 版本历史

- **v1.0** (2025-10-16):
  - 合并字段指南和冲突分析文档
  - 添加验证逻辑实现说明
  - 完善前端集成建议
  - 扩充 FAQ 和最佳实践

---

## 🔗 相关文档

- **UML 图解集合**: `TASK_FIELDS_UML.md` - 提供 10 种 UML 图可视化
- **API 使用指南**: `docs/API_USAGE_GUIDE.md` - API 端点使用说明
- **API 字段参考**: `docs/API_FIELD_REFERENCE.md` - 字段详细参考

---

**维护者**: Claude Code
**更新频率**: 随代码变更同步更新
**反馈渠道**: 请通过 GitHub Issues 提供反馈
