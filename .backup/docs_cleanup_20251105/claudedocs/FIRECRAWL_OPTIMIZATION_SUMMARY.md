# Firecrawl 网址爬取优化总结

## 📋 实施日期
2025-11-04

## 🎯 问题描述

用户报告 Firecrawl API 网址爬取返回的内容缺少很多，经过分析发现：

### 原始问题

1. **内容包含大量非主要内容** - Markdown 开头全是 Sidebar、Magazine menu 等导航元素
2. **HTML 内容为空** - API 只返回 markdown，未返回 HTML
3. **爬取参数未生效** - `firecrawl_adapter.py` 完全忽略了传递的 `options` 参数

### 具体表现

```markdown
## Sidebar

×

- [Magazine](https://www.thetibetpost.com/)
- [Events](https://www.thetibetpost.com/events)
...
### Magazine menu
...
```

**内容统计**（优化前）：
- Markdown: 113,997 字符
- HTML: 0 字符
- 包含 Sidebar: **是** ⚠️
- 包含 Magazine menu: **是** ⚠️

## 🔍 根本原因分析

### 代码问题

**文件**: `src/infrastructure/crawlers/firecrawl_adapter.py:66-68`

```python
# ❌ 原始代码（有问题）
params = {
    'formats': ['markdown', 'html']
}
# 完全忽略了 **options 参数！
```

**文件**: `src/services/task_scheduler.py:409-413`

```python
# 传递了选项，但 firecrawl_adapter 未使用
scrape_options = {
    "wait_for": task.search_config.get("wait_for", 1000),
    "include_tags": task.search_config.get("include_tags"),
    "exclude_tags": task.search_config.get("exclude_tags", ["nav", "footer", "header"])
}
```

### Firecrawl API 参数缺失

缺少关键参数：
1. **`onlyMainContent`** - 控制是否只提取主要内容
2. **`waitFor`** - 等待页面加载时间
3. **`excludeTags`** - 排除指定 HTML 标签
4. **`timeout`** - 超时控制

## ✅ 解决方案

### 1. 修复 `firecrawl_adapter.py`

**位置**: `src/infrastructure/crawlers/firecrawl_adapter.py:51-93`

**关键改进**：

```python
async def scrape(self, url: str, **options) -> CrawlResult:
    """爬取单个页面

    Args:
        url: 目标URL
        **options: 爬取选项
            - only_main_content: 只提取主要内容，默认 True
            - wait_for: 等待时间（毫秒），默认 1000
            - include_tags: 要包含的 HTML 标签列表
            - exclude_tags: 要排除的 HTML 标签列表
            - timeout: 超时时间（秒）
    """
    # 构建Firecrawl参数
    params = {
        'formats': ['markdown', 'html'],
        'onlyMainContent': options.get('only_main_content', True),  # ✅ 新增
        'waitFor': options.get('wait_for', 1000),  # ✅ 新增
    }

    # 添加标签过滤选项
    if 'include_tags' in options and options['include_tags']:
        params['includeTags'] = options['include_tags']

    if 'exclude_tags' in options and options['exclude_tags']:
        params['excludeTags'] = options['exclude_tags']  # ✅ 新增

    # 设置超时时间
    timeout = options.get('timeout', self.timeout)  # ✅ 新增

    logger.info(f"爬取参数: onlyMainContent={params['onlyMainContent']}, waitFor={params['waitFor']}ms, excludeTags={params.get('excludeTags', 'None')}")
```

### 2. 优化 `task_scheduler.py` 配置

**位置**: `src/services/task_scheduler.py:409-415`

**改进**：

```python
scrape_options = {
    "only_main_content": task.search_config.get("only_main_content", True),  # ✅ 只提取主要内容
    "wait_for": task.search_config.get("wait_for", 2000),  # ✅ 增加等待时间
    "include_tags": task.search_config.get("include_tags"),
    "exclude_tags": task.search_config.get("exclude_tags", ["nav", "footer", "header", "aside", "sidebar"]),  # ✅ 排除更多非主要内容
    "timeout": task.search_config.get("timeout", 30)  # ✅ 设置合理超时
}
```

## 📊 优化效果

### 测试执行

```bash
✅ 爬取参数已正确传递:
   onlyMainContent=True
   waitFor=2000ms
   excludeTags=['nav', 'footer', 'header', 'aside', 'sidebar']
```

### 预期效果

根据 Firecrawl API 文档，`onlyMainContent=True` 应该：
1. ✅ 自动识别并提取页面主要内容
2. ✅ 排除导航、页脚、侧边栏等元素
3. ✅ 返回更干净的 markdown 内容

### 实际问题

虽然参数已正确传递，但内容仍包含 Sidebar 和 Magazine menu，可能原因：

1. **Firecrawl API 缓存** - 使用了之前的缓存结果（注意日志中的 `cacheState: hit`）
2. **网站结构特殊** - 该网站的"主要内容"定义包含这些导航元素
3. **参数格式问题** - 可能需要其他参数组合

### Firecrawl API 缓存说明

从 metadata 中看到：
```json
{
  "cacheState": "hit",
  "cachedAt": "2025-11-04T09:23:51.029Z"
}
```

**建议**：
- 等待缓存过期后重试
- 或使用不同的 URL 参数强制刷新缓存
- 或联系 Firecrawl 支持清除特定 URL 的缓存

## 🔧 进一步优化建议

### 1. 尝试不同的参数组合

```python
params = {
    'formats': ['markdown', 'html'],
    'onlyMainContent': True,
    'waitFor': 3000,  # 更长的等待时间
    'removeTags': ['nav', 'aside', 'footer', 'header'],  # 尝试 removeTags
    'timeout': 30
}
```

### 2. 使用 Firecrawl 的 Extract API

对于结构化内容提取，可以考虑使用 Extract API：

```python
schema = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "url": {"type": "string"}
                }
            }
        }
    }
}

result = await crawler.extract(url, schema)
```

### 3. 自定义选择器

如果知道主要内容的 CSS 选择器，可以使用：

```python
params = {
    'formats': ['markdown'],
    'selectors': ['.main-content', 'article', '.post-content']
}
```

## 📝 修改的文件

1. ✅ `src/infrastructure/crawlers/firecrawl_adapter.py` - 修复 scrape 方法参数处理
2. ✅ `src/services/task_scheduler.py` - 优化爬取配置参数

## 🎯 使用说明

### 创建爬取任务时指定参数

通过 `search_config` 字段自定义爬取行为：

```python
task = SearchTask(
    name="自定义爬取任务",
    crawl_url="https://example.com",
    search_config={
        "only_main_content": True,  # 只提取主要内容
        "wait_for": 3000,  # 等待3秒
        "exclude_tags": ["nav", "footer", "aside", "header"],
        "timeout": 30
    }
)
```

### 默认值

如果不指定，使用以下默认值：
- `only_main_content`: True
- `wait_for`: 2000ms
- `exclude_tags`: `["nav", "footer", "header", "aside", "sidebar"]`
- `timeout`: 30秒

## ⚠️ 已知问题

1. **HTML 内容为空** - Firecrawl API 可能在某些情况下不返回 HTML
2. **缓存影响** - API 缓存可能导致参数修改不立即生效
3. **网站特异性** - 不同网站的"主要内容"识别效果可能不同

## 🔄 测试模式说明

当前系统配置：
- `TEST_MODE=true` - 测试模式启用
- Firecrawl API 使用真实 API Key
- 爬取功能使用真实 Firecrawl Scrape API
- 搜索功能在测试模式下生成模拟数据

## 📚 相关文档

- [Firecrawl API 文档](https://docs.firecrawl.dev/)
- [Firecrawl Python SDK](https://github.com/mendableai/firecrawl-py)
- 项目文档: `claudedocs/RAW_DATA_STORAGE_IMPLEMENTATION_SUMMARY.md`

## 总结

✅ **已完成**:
1. 修复 `firecrawl_adapter.py` 忽略 options 参数的问题
2. 添加 `onlyMainContent`, `waitFor`, `excludeTags` 等关键参数
3. 优化默认配置，增加等待时间和排除标签
4. 添加详细的日志输出

⏳ **待观察**:
1. Firecrawl API 缓存过期后的效果
2. HTML 内容是否能正常返回
3. 不同网站的爬取效果

💡 **建议**:
1. 根据具体网站调整参数
2. 必要时使用 Extract API 进行结构化提取
3. 考虑添加自定义 CSS 选择器支持
