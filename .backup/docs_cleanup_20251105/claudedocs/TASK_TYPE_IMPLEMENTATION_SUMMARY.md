# 定时任务类型实现总结

## 📋 实施日期
2025-11-04

## 🎯 需求说明

实现两种定时任务模式：
1. **网站爬取模式**：使用 Firecrawl Crawl API 递归爬取整个网站
2. **关键词搜索模式**：Search API 获取搜索结果后，对每个结果使用 Scrape API 爬取详情页内容

## ✅ 已完成的工作

### 1. 数据模型设计 (`search_task.py`)

#### 添加 TaskType 枚举
```python
class TaskType(Enum):
    """任务类型枚举"""
    SEARCH_KEYWORD = "search_keyword"  # 关键词搜索模式（Search API + Scrape API 详情页）
    CRAWL_WEBSITE = "crawl_website"    # 网站爬取模式（Crawl API 递归爬取整个网站）
    SCRAPE_URL = "scrape_url"          # 单页面爬取模式（Scrape API 爬取单个页面）
```

#### 更新 SearchTask 实体字段
```python
@dataclass
class SearchTask:
    # 任务类型和目标
    task_type: str = "search_keyword"  # 任务类型
    query: str = ""  # 搜索关键词（SEARCH_KEYWORD 模式）
    crawl_url: Optional[str] = None  # 爬取URL（CRAWL_WEBSITE 和 SCRAPE_URL 模式）

    # 配置
    search_config: Dict[str, Any] = field(default_factory=dict)  # 搜索配置
    crawl_config: Dict[str, Any] = field(default_factory=dict)  # 爬取配置（CRAWL_WEBSITE 模式）
```

#### 添加辅助方法
```python
def get_task_type(self) -> TaskType
def is_search_keyword_mode(self) -> bool
def is_crawl_website_mode(self) -> bool
def is_scrape_url_mode(self) -> bool
```

### 2. 数据库支持 (`repositories.py`)

#### 更新 _task_to_dict 方法
```python
def _task_to_dict(self, task: SearchTask) -> Dict[str, Any]:
    return {
        "task_type": task.task_type,  # v2.0.0: 任务类型
        "crawl_config": task.crawl_config,  # v2.0.0: 爬取配置
        # ... 其他字段
    }
```

#### 更新 _dict_to_task 方法
```python
def _dict_to_task(self, data: Dict[str, Any]) -> SearchTask:
    task = SearchTask(
        task_type=data.get("task_type", "search_keyword"),  # 向后兼容
        crawl_config=data.get("crawl_config", {}),  # 向后兼容
        # ... 其他字段
    )
```

### 3. Firecrawl Crawl API 适配器

**现有实现** (`firecrawl_adapter.py:108-154`):
- 已有 `crawl()` 方法基础实现
- 支持 limit, maxDepth, includePaths, excludePaths 等参数
- 使用 FirecrawlApp SDK 处理异步爬取

**待完善**:
- 异步轮询和状态检查
- 大规模网站的分批处理
- 错误恢复和重试机制

## ⏳ 待完成的工作

### 1. 任务调度器修改 (`task_scheduler.py`)

**需要修改 `_execute_search_task` 方法**：

```python
async def _execute_search_task(self, task_id: str):
    """执行搜索任务 - 支持三种模式"""
    task = await repo.get_by_id(task_id)

    # 根据任务类型选择执行方式
    if task.is_crawl_website_mode():
        # 模式1: 网站爬取（Crawl API）
        result_batch = await self._execute_crawl_website_task(task)
    elif task.is_search_keyword_mode():
        # 模式2: 关键词搜索 + 详情页爬取（Search API + Scrape API）
        result_batch = await self._execute_search_with_scrape_task(task)
    else:  # SCRAPE_URL
        # 模式3: 单页面爬取（Scrape API）
        result_batch = await self._execute_crawl_task_internal(task, start_time)
```

### 2. 实现网站爬取方法

```python
async def _execute_crawl_website_task(self, task: SearchTask) -> SearchResultBatch:
    """执行网站爬取任务（Crawl API）

    Args:
        task: 搜索任务（task_type = "crawl_website"）

    Returns:
        SearchResultBatch: 爬取结果批次
    """
    crawler = FirecrawlAdapter()

    # 从 crawl_config 提取配置
    crawl_options = {
        'limit': task.crawl_config.get('limit', 10),
        'max_depth': task.crawl_config.get('max_depth', 3),
        'include_paths': task.crawl_config.get('include_paths', []),
        'exclude_paths': task.crawl_config.get('exclude_paths', []),
        'allow_backward_links': task.crawl_config.get('allow_backward_links', False)
    }

    # 调用 Crawl API
    crawl_results = await crawler.crawl(task.crawl_url, **crawl_options)

    # 转换为 SearchResult 列表
    search_results = []
    for crawl_result in crawl_results:
        search_result = SearchResult(
            task_id=str(task.id),
            title=crawl_result.metadata.get("title", crawl_result.url),
            url=crawl_result.url,
            markdown_content=crawl_result.markdown or crawl_result.content,
            html_content=crawl_result.html,
            metadata=crawl_result.metadata,
            status=ResultStatus.PENDING
        )
        search_results.append(search_result)

    # 创建批次
    batch = SearchResultBatch(
        task_id=str(task.id),
        query=f"网站爬取: {task.crawl_url}",
        search_config=task.crawl_config
    )
    for result in search_results:
        batch.add_result(result)

    return batch
```

### 3. 实现关键词搜索 + 详情页爬取方法

```python
async def _execute_search_with_scrape_task(self, task: SearchTask) -> SearchResultBatch:
    """执行关键词搜索 + 详情页爬取任务（Search API + Scrape API）

    两阶段处理：
    1. Search API 获取搜索结果（首页链接）
    2. 对每个搜索结果使用 Scrape API 爬取详情页

    Args:
        task: 搜索任务（task_type = "search_keyword"）

    Returns:
        SearchResultBatch: 包含详情页内容的搜索结果批次
    """
    # 第一阶段：关键词搜索
    user_config = UserSearchConfig.from_json(task.search_config)
    search_batch = await self.search_adapter.search(
        query=task.query,
        user_config=user_config,
        task_id=str(task.id)
    )

    if not search_batch.results:
        logger.warning(f"搜索无结果: {task.query}")
        return search_batch

    # 第二阶段：爬取详情页
    crawler = FirecrawlAdapter()

    # 配置爬取选项
    scrape_options = {
        "only_main_content": task.search_config.get("only_main_content", True),
        "wait_for": task.search_config.get("wait_for", 2000),
        "exclude_tags": task.search_config.get("exclude_tags", ["nav", "footer", "header", "aside"]),
        "timeout": task.search_config.get("timeout", 30)
    }

    # 批量爬取详情页
    enriched_results = []
    for search_result in search_batch.results:
        try:
            logger.info(f"🔍 爬取详情页: {search_result.url}")

            # 爬取详情页
            crawl_result = await crawler.scrape(search_result.url, **scrape_options)

            # 更新搜索结果的内容
            search_result.markdown_content = crawl_result.markdown or crawl_result.content
            search_result.html_content = crawl_result.html
            search_result.metadata.update(crawl_result.metadata or {})

            enriched_results.append(search_result)

            # 避免过快请求（速率限制）
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ 爬取详情页失败 {search_result.url}: {e}")
            # 保留原始搜索结果
            enriched_results.append(search_result)

    # 更新批次结果
    search_batch.results = enriched_results
    logger.info(f"✅ 详情页爬取完成: {len(enriched_results)}/{len(search_batch.results)}")

    return search_batch
```

### 4. API 更新

**前端 API** (`search_tasks_frontend.py`):
- 更新 `SearchTaskCreate` 模型添加 `task_type` 字段
- 更新 `SearchTaskResponse` 模型返回 `task_type` 和 `crawl_config`
- 添加 `TaskTypeEnum` 用于前端选择

**验证逻辑** (`search_tasks_validation.py`):
- 根据 `task_type` 验证必填字段
- CRAWL_WEBSITE: 必须提供 `crawl_url`
- SEARCH_KEYWORD: 必须提供 `query`
- SCRAPE_URL: 必须提供 `crawl_url`

### 5. 测试

**单元测试**:
- 测试三种任务类型的创建
- 测试任务类型判断方法
- 测试数据库序列化/反序列化

**集成测试**:
- 测试网站爬取模式
- 测试关键词搜索 + 详情页爬取模式
- 测试单页面爬取模式
- 测试错误恢复和重试

## 📊 配置示例

### 网站爬取任务
```json
{
  "name": "爬取官网所有页面",
  "task_type": "crawl_website",
  "crawl_url": "https://example.com",
  "crawl_config": {
    "limit": 100,
    "max_depth": 3,
    "include_paths": ["/blog/", "/docs/"],
    "exclude_paths": ["/admin/", "/api/"],
    "allow_backward_links": false
  },
  "schedule_interval": "DAILY"
}
```

### 关键词搜索任务
```json
{
  "name": "搜索并爬取详情页",
  "task_type": "search_keyword",
  "query": "人工智能新闻",
  "search_config": {
    "limit": 10,
    "language": "zh",
    "only_main_content": true,
    "wait_for": 2000,
    "exclude_tags": ["nav", "footer", "aside"]
  },
  "schedule_interval": "HOURLY_6"
}
```

### 单页面爬取任务
```json
{
  "name": "爬取特定页面",
  "task_type": "scrape_url",
  "crawl_url": "https://example.com/article/123",
  "search_config": {
    "only_main_content": true,
    "wait_for": 1000
  },
  "schedule_interval": "DAILY"
}
```

## ⚠️ 注意事项

### 1. 性能考虑
- **网站爬取**: Crawl API 可能需要较长时间（几分钟到几小时），考虑异步处理和状态通知
- **详情页爬取**: 批量爬取需要控制并发数和速率限制，避免被封禁
- **超时设置**: 不同模式需要不同的超时配置

### 2. 资源管理
- **API 配额**: Firecrawl API 有配额限制，需要监控使用量
- **存储空间**: 大规模爬取会产生大量数据，考虑存储优化
- **内存使用**: 批量处理时注意内存管理

### 3. 错误处理
- **部分失败**: 详情页爬取时部分失败不应影响整体任务
- **重试策略**: 网络错误应有重试机制
- **降级策略**: 爬取失败时保留搜索结果的基本信息

## 🔄 迁移计划

### 现有任务兼容性
- 旧任务默认 `task_type = "search_keyword"`
- 有 `crawl_url` 但无 `task_type` 的任务自动识别为 `"scrape_url"`
- 数据库查询自动填充默认值

### 数据库索引
```javascript
// MongoDB 索引建议
db.search_tasks.createIndex({ "task_type": 1, "is_active": 1 })
db.search_tasks.createIndex({ "task_type": 1, "status": 1, "next_run_time": 1 })
```

## 📝 下一步工作

1. ✅ 数据模型设计 - 已完成
2. ✅ 数据库支持 - 已完成
3. ⏳ 任务调度器修改 - 待完成
4. ⏳ 网站爬取方法实现 - 待完成
5. ⏳ 关键词搜索 + 详情页爬取实现 - 待完成
6. ⏳ API 更新 - 待完成
7. ⏳ 测试 - 待完成
8. ⏳ 文档更新 - 待完成

## 总结

本次实现完成了定时任务类型系统的**核心基础架构**，包括：
- 任务类型枚举和数据模型
- 数据库序列化支持
- 向后兼容的迁移逻辑

**待完成的主要工作**是实现三种任务类型的具体执行逻辑，特别是：
1. 网站爬取的异步处理
2. 关键词搜索的二阶段处理（搜索 + 详情页爬取）

建议优先实现关键词搜索的二阶段处理，因为这是用户明确提出的需求。
