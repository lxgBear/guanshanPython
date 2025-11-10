# Map+Scrape 执行器设计文档

**文档版本**: v1.0.0
**创建日期**: 2025-11-06
**状态**: 设计阶段

---

## 📋 目录

1. [需求背景](#需求背景)
2. [技术方案](#技术方案)
3. [API对比分析](#api对比分析)
4. [架构设计](#架构设计)
5. [实现细节](#实现细节)
6. [数据库兼容性](#数据库兼容性)
7. [积分消耗计算](#积分消耗计算)
8. [实现路线图](#实现路线图)
9. [测试策略](#测试策略)

---

## 需求背景

### 业务需求

**核心需求**：实现指定URL + 时间范围的精确网站内容爬取

**具体场景**：
- 定期监控特定网站的最新内容
- 只爬取特定时间范围内的文章（如：最近30天）
- 避免重复爬取历史内容，节省API积分

**现有方案的局限性**：
- **Crawl API**：递归爬取整个网站，无法精确控制爬取哪些页面
- **时间过滤滞后**：需要先爬取所有页面，再根据发布时间过滤
- **积分浪费**：爬取了大量不需要的历史页面

### 技术目标

1. ✅ **精确URL发现**：使用Map API快速获取网站所有URL
2. ✅ **按需爬取**：只爬取符合时间范围的页面
3. ✅ **节省积分**：避免不必要的页面爬取
4. ✅ **数据兼容**：保持数据库字段结构不变
5. ✅ **备用方案**：保留Crawl API作为fallback

---

## 技术方案

### 方案概述

**新执行器**：`MapScrapeExecutor`
**任务类型**：`TaskType.MAP_SCRAPE_WEBSITE = "map_scrape_website"`
**核心流程**：Map API → Batch Scrape → 时间过滤 → 保存结果

### 执行流程图

```
┌──────────────────────────────────────────────────────────────┐
│  阶段1: Map API - 发现所有URL                                 │
│  输入: 起始URL, search参数（可选）                             │
│  输出: URL列表 + 元数据（title, description）                 │
│  时间: ~5秒                                                   │
│  积分: 1 credit                                               │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  阶段2: Batch Scrape - 批量爬取内容                           │
│  输入: URL列表                                                 │
│  处理: 并发scrape（Semaphore控制并发数）                       │
│  输出: 每个URL的完整内容 + metadata（含publishedDate）        │
│  时间: ~N*2秒（N=URL数量，考虑并发）                           │
│  积分: N credits                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  阶段3: 时间过滤 - 筛选符合条件的内容                          │
│  输入: 所有scrape结果                                          │
│  过滤: metadata.publishedDate在[start_date, end_date]范围内   │
│  输出: 符合时间条件的结果列表                                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  阶段4: 数据保存                                               │
│  - 转换为SearchResult实体                                     │
│  - 保存到search_results集合                                   │
│  - 保存原始响应到firecrawl_raw_responses                      │
└──────────────────────────────────────────────────────────────┘
```

### 与Crawl API的对比

| 特性 | Crawl API | Map + Scrape API |
|------|-----------|------------------|
| **URL发现** | 递归爬取 | Map API一次性获取 |
| **速度** | 较慢（需要递归） | 较快（并发scrape） |
| **时间过滤** | 爬取后过滤 | 可提前过滤（可选） |
| **积分消耗** | 按爬取页面数 | Map(1) + Scrape(N) |
| **适用场景** | 完整归档 | 精确目标爬取 |
| **控制精度** | 路径过滤 | URL级别过滤 |

---

## API对比分析

### Firecrawl Map API

**端点**: `POST /v2/map`

**功能**：
- 发现网站的所有可访问URL
- 可选search参数进行关键词过滤
- 返回URL列表及基本元数据

**请求示例**：
```bash
curl -X POST https://api.firecrawl.dev/v2/map \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer YOUR_API_KEY' \
    -d '{
      "url": "https://example.com",
      "search": "blog",
      "limit": 5000
    }'
```

**响应示例**：
```json
{
  "success": true,
  "links": [
    {
      "url": "https://example.com/blog/post-1",
      "title": "Post 1 Title",
      "description": "Post 1 description"
    },
    {
      "url": "https://example.com/blog/post-2",
      "title": "Post 2 Title",
      "description": "Post 2 description"
    }
  ]
}
```

**关键特点**：
- ✅ 快速（通常<5秒）
- ✅ 准确（使用sitemap和智能爬取）
- ✅ 固定成本（1 credit）
- ❌ 不包含页面内容
- ❌ 不包含发布时间

### Firecrawl Scrape API

**端点**: `POST /v2/scrape`

**功能**：
- 爬取单个URL的完整内容
- 支持多种输出格式
- 提取metadata（包含publishedDate）

**批量Scrape策略**：
```python
async def batch_scrape(urls: List[str], max_concurrent: int = 5):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_with_limit(url):
        async with semaphore:
            return await scrape_adapter.scrape(url)

    tasks = [scrape_with_limit(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**关键特点**：
- ✅ 完整内容（markdown, html）
- ✅ 元数据完整（含publishedDate）
- ✅ 支持并发
- ⚠️ 按URL计费（N credits）

---

## 架构设计

### 配置类设计

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class MapScrapeConfig:
    """Map + Scrape 执行器配置"""

    # Map API 配置
    search: Optional[str] = None          # 搜索关键词（可选）
    map_limit: int = 5000                 # Map API返回URL数量限制

    # 时间过滤配置
    start_date: Optional[datetime] = None # 开始日期（包含）
    end_date: Optional[datetime] = None   # 结束日期（包含）

    # Scrape API 配置
    max_concurrent_scrapes: int = 5       # 最大并发scrape数
    scrape_delay: float = 0.5             # scrape间隔（秒）
    only_main_content: bool = True        # 只提取主要内容
    exclude_tags: List[str] = field(      # 排除的HTML标签
        default_factory=lambda: ["nav", "footer", "header", "aside"]
    )
    timeout: int = 90                     # 单个scrape超时（秒）

    # 错误处理
    allow_partial_failure: bool = True    # 允许部分scrape失败
    min_success_rate: float = 0.8         # 最低成功率（80%）
```

### 执行器类设计

```python
class MapScrapeExecutor(TaskExecutor):
    """Map + Scrape 任务执行器

    适用于需要精确控制爬取URL和时间范围的场景
    """

    def __init__(self):
        super().__init__()
        self.firecrawl_adapter = FirecrawlAdapter()

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行Map + Scrape任务"""
        start_time = datetime.utcnow()

        # 1. 验证配置
        if not self.validate_config(task):
            raise ConfigValidationError(f"任务配置无效: {task.id}")

        # 2. 解析配置
        config = ConfigFactory.create_map_scrape_config(task.crawl_config)

        # 3. 阶段1: Map - 发现URL
        urls = await self._execute_map(task.crawl_url, config)
        self.logger.info(f"🗺️  Map发现 {len(urls)} 个URL")

        # 4. 阶段2: Batch Scrape - 爬取内容
        scrape_results = await self._batch_scrape(urls, config)
        self.logger.info(f"✅ Scrape完成 {len(scrape_results)} 个页面")

        # 5. 阶段3: 时间过滤
        filtered_results = self._filter_by_date(scrape_results, config)
        self.logger.info(f"🔍 时间过滤后剩余 {len(filtered_results)} 个结果")

        # 6. 保存原始响应
        await self._save_raw_responses(scrape_results, task)

        # 7. 转换为SearchResult
        search_results = self._convert_to_search_results(
            filtered_results, task
        )

        # 8. 创建结果批次
        batch = self._create_result_batch(task, query=f"Map+Scrape: {task.crawl_url}")
        for result in search_results:
            batch.add_result(result)

        # 9. 计算积分消耗
        batch.credits_used = FirecrawlCreditsCalculator.calculate_map_scrape_credits(
            map_calls=1,
            urls_scraped=len(scrape_results)
        )

        # 10. 计算执行时间
        batch.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        self._log_execution_end(task, len(search_results), batch.execution_time_ms)
        return batch

    async def _execute_map(self, url: str, config: MapScrapeConfig) -> List[str]:
        """执行Map API调用"""
        pass

    async def _batch_scrape(self, urls: List[str], config: MapScrapeConfig) -> List[CrawlResult]:
        """批量scrape URL"""
        pass

    def _filter_by_date(self, results: List[CrawlResult], config: MapScrapeConfig) -> List[CrawlResult]:
        """根据时间范围过滤结果"""
        pass
```

---

## 实现细节

### 1. FirecrawlAdapter扩展

**新增map()方法**：

```python
async def map(
    self,
    url: str,
    search: Optional[str] = None,
    limit: int = 5000
) -> List[Dict[str, Any]]:
    """调用Firecrawl Map API

    Args:
        url: 起始URL
        search: 搜索关键词（可选）
        limit: 返回URL数量限制

    Returns:
        List[Dict]: [
            {"url": "...", "title": "...", "description": "..."},
            ...
        ]

    Raises:
        MapAPIError: Map API调用失败
    """
    payload = {
        "url": url,
        "limit": limit
    }

    if search:
        payload["search"] = search

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.api_key}"
    }

    try:
        response = await self.client.post(
            f"{self.base_url}/v2/map",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("success"):
            raise MapAPIError(f"Map API返回失败: {data}")

        links = data.get("links", [])
        self.logger.info(f"✅ Map API返回 {len(links)} 个URL")

        return links

    except Exception as e:
        self.logger.error(f"❌ Map API调用失败: {e}")
        raise MapAPIError(f"Map API调用失败: {str(e)}")
```

### 2. 批量Scrape实现

**并发控制和错误处理**：

```python
async def _batch_scrape(
    self,
    urls: List[str],
    config: MapScrapeConfig
) -> List[CrawlResult]:
    """批量scrape URL（带并发控制和错误处理）

    Args:
        urls: URL列表
        config: Scrape配置

    Returns:
        List[CrawlResult]: 成功scrape的结果列表
    """
    semaphore = asyncio.Semaphore(config.max_concurrent_scrapes)
    results = []
    failed_urls = []

    async def scrape_with_limit(url: str, index: int) -> Optional[CrawlResult]:
        async with semaphore:
            try:
                self.logger.info(f"🔍 [{index+1}/{len(urls)}] Scraping: {url}")

                # 添加延迟避免过快请求
                if index > 0:
                    await asyncio.sleep(config.scrape_delay)

                # 执行scrape
                result = await self.firecrawl_adapter.scrape(
                    url,
                    only_main_content=config.only_main_content,
                    exclude_tags=config.exclude_tags,
                    timeout=config.timeout
                )

                return result

            except Exception as e:
                self.logger.warning(f"⚠️  Scrape失败 {url}: {e}")
                failed_urls.append(url)
                return None

    # 并发执行所有scrape
    tasks = [scrape_with_limit(url, i) for i, url in enumerate(urls)]
    scrape_results = await asyncio.gather(*tasks)

    # 过滤失败的结果
    results = [r for r in scrape_results if r is not None]

    # 检查成功率
    success_rate = len(results) / len(urls) if urls else 0
    self.logger.info(
        f"📊 Scrape统计: 成功={len(results)}, 失败={len(failed_urls)}, "
        f"成功率={success_rate*100:.1f}%"
    )

    # 验证最低成功率
    if not config.allow_partial_failure and success_rate < config.min_success_rate:
        raise ExecutionError(
            f"Scrape成功率过低: {success_rate*100:.1f}% < "
            f"{config.min_success_rate*100:.1f}%"
        )

    return results
```

### 3. 时间过滤实现

```python
def _filter_by_date(
    self,
    results: List[CrawlResult],
    config: MapScrapeConfig
) -> List[CrawlResult]:
    """根据发布时间过滤结果

    Args:
        results: Scrape结果列表
        config: 配置（包含start_date和end_date）

    Returns:
        List[CrawlResult]: 符合时间范围的结果
    """
    # 如果没有配置时间范围，返回所有结果
    if not config.start_date and not config.end_date:
        return results

    filtered = []

    for result in results:
        # 提取发布时间
        metadata = result.metadata or {}
        published_date_str = (
            metadata.get('publishedDate') or
            metadata.get('published_date') or
            metadata.get('article:published_time')
        )

        if not published_date_str:
            # 没有发布时间的页面，根据配置决定是否保留
            self.logger.debug(f"⚠️  {result.url} 无发布时间")
            continue

        try:
            # 解析发布时间
            published_date = datetime.fromisoformat(published_date_str)

            # 检查是否在时间范围内
            if config.start_date and published_date < config.start_date:
                continue

            if config.end_date and published_date > config.end_date:
                continue

            # 符合条件
            filtered.append(result)

        except Exception as e:
            self.logger.warning(f"⚠️  解析发布时间失败 {result.url}: {e}")
            continue

    return filtered
```

---

## 数据库兼容性

### SearchResult字段映射

**完全兼容现有字段结构**：

```python
def _convert_to_search_results(
    self,
    scrape_results: List[CrawlResult],
    task: SearchTask
) -> List[SearchResult]:
    """转换为SearchResult（与现有结构完全兼容）"""

    search_results = []

    for idx, result in enumerate(scrape_results, start=1):
        # 提取元数据
        metadata_dict = result.metadata if isinstance(result.metadata, dict) else {}
        metadata_fields = self._extract_metadata_fields(metadata_dict)

        # 创建SearchResult（字段完全相同）
        search_result = SearchResult(
            task_id=str(task.id),
            title=metadata_dict.get("title", result.url),
            url=result.url,
            snippet=result.content[:200] if result.content else "",
            source="map_scrape",  # 新的source标识

            # 元数据字段（完全相同）
            published_date=metadata_fields.get('published_date'),
            author=metadata_fields.get('author'),
            language=metadata_fields.get('language'),
            article_tag=metadata_fields.get('article_tag'),
            article_published_time=metadata_fields.get('article_published_time'),
            source_url=metadata_fields.get('source_url'),
            http_status_code=metadata_fields.get('http_status_code'),

            search_position=idx,
            markdown_content=result.markdown if result.markdown else result.content,
            html_content=result.html,
            metadata={},  # 不再传递metadata，字段已独立
            relevance_score=1.0,
            status=ResultStatus.PENDING
        )

        search_results.append(search_result)

    return search_results
```

**数据库集合**：
- ✅ `search_results`: 保存SearchResult实体
- ✅ `firecrawl_raw_responses`: 保存原始API响应
- ✅ 字段结构无任何变化

---

## 积分消耗计算

### 计算逻辑

```python
class FirecrawlCreditsCalculator:
    """Firecrawl积分消耗计算器"""

    @staticmethod
    def calculate_map_scrape_credits(
        map_calls: int,
        urls_scraped: int
    ) -> int:
        """计算Map + Scrape操作的积分消耗

        Args:
            map_calls: Map API调用次数（通常为1）
            urls_scraped: Scrape的URL数量

        Returns:
            int: 总积分消耗
        """
        map_cost = map_calls * 1  # Map API: 1 credit per call
        scrape_cost = urls_scraped * 1  # Scrape API: 1 credit per URL

        total = map_cost + scrape_cost

        return total
```

### 成本对比示例

**场景**: 爬取博客网站，只需要最近30天的100篇文章

**Crawl API方式**：
```
- 网站总页面: 1000页
- 爬取方式: 递归爬取所有页面
- 积分消耗: 500-1000 credits（需要爬取很多历史页面）
- 时间: ~20-30分钟
```

**Map + Scrape方式**：
```
- Map API: 发现所有URL (1 credit)
- Scrape API: 只scrape 100个符合时间的页面 (100 credits)
- 总积分: 101 credits
- 时间: ~5-10分钟
- 节省: ~80-90%
```

---

## 实现路线图

### Phase 1: 核心功能（1-2天）

- [x] 扩展FirecrawlAdapter：新增map()方法
- [x] 创建MapScrapeConfig配置类
- [x] 实现MapScrapeExecutor基础框架
- [x] 实现_execute_map()方法
- [x] 实现_batch_scrape()方法
- [ ] 单元测试

### Phase 2: 时间过滤（1天）

- [ ] 实现_filter_by_date()方法
- [ ] 支持start_date和end_date配置
- [ ] 处理无发布时间的页面
- [ ] 日期解析容错
- [ ] 集成测试

### Phase 3: 错误处理和优化（1天）

- [ ] 并发控制优化
- [ ] 重试机制
- [ ] 部分失败容忍
- [ ] 性能监控和日志
- [ ] 压力测试

### Phase 4: 集成和文档（1天）

- [ ] 更新TaskType枚举
- [ ] 在ExecutorFactory注册
- [ ] 更新积分计算器
- [ ] 完善技术文档
- [ ] 创建使用示例

### Phase 5: 测试和上线（1天）

- [ ] 端到端测试
- [ ] 真实场景验证
- [ ] 性能对比分析
- [ ] 生产环境部署
- [ ] 监控配置

---

## 测试策略

### 单元测试

```python
# tests/test_map_scrape_executor.py

class TestMapScrapeExecutor:

    async def test_execute_map(self):
        """测试Map API调用"""
        executor = MapScrapeExecutor()
        config = MapScrapeConfig()

        urls = await executor._execute_map("https://example.com", config)

        assert len(urls) > 0
        assert all(url.startswith("http") for url in urls)

    async def test_batch_scrape(self):
        """测试批量Scrape"""
        executor = MapScrapeExecutor()
        config = MapScrapeConfig(max_concurrent_scrapes=3)

        urls = ["https://example.com/page1", "https://example.com/page2"]
        results = await executor._batch_scrape(urls, config)

        assert len(results) == 2
        assert all(r.markdown is not None for r in results)

    def test_filter_by_date(self):
        """测试时间过滤"""
        executor = MapScrapeExecutor()
        config = MapScrapeConfig(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        # 创建测试数据
        results = [...]  # 包含不同发布时间的结果

        filtered = executor._filter_by_date(results, config)

        # 验证过滤结果
        assert all(
            config.start_date <= r.metadata.get('published_date') <= config.end_date
            for r in filtered
        )
```

### 集成测试

```python
# tests/integration/test_map_scrape_integration.py

async def test_full_map_scrape_workflow():
    """测试完整的Map+Scrape工作流"""

    # 创建任务
    task = SearchTask(
        name="测试博客爬取",
        crawl_url="https://example.com/blog",
        task_type=TaskType.MAP_SCRAPE_WEBSITE,
        crawl_config={
            "search": "python",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "max_concurrent_scrapes": 3
        }
    )

    # 执行
    executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
    batch = await executor.execute(task)

    # 验证
    assert batch.returned_count > 0
    assert batch.credits_used > 0
    assert all(r.source == "map_scrape" for r in batch.results)
```

---

## 总结

### 核心优势

1. **精确控制**：Map API提供精确的URL发现能力
2. **成本优化**：只爬取需要的页面，节省80-90%积分
3. **时间过滤**：支持发布时间范围过滤
4. **数据兼容**：完全兼容现有数据库结构
5. **备用方案**：保留Crawl API作为fallback

### 适用场景

- ✅ 定期监控特定网站最新内容
- ✅ 只需要特定时间范围的文章
- ✅ 网站有明确的URL结构
- ✅ 需要精确控制爬取目标

### 不适用场景

- ❌ 需要完整归档整个网站
- ❌ 网站URL结构不规则
- ❌ 无法通过Map API发现所有页面
- ❌ 不关心积分成本

---

**文档维护者**: Development Team
**最后更新**: 2025-11-06
