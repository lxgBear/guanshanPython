# Firecrawl 集成完整指南

> **文档状态**: 统一指南 (合并自 FIRECRAWL_INTEGRATION.md 和 FIRECRAWL_API_CONFIGURATION.md)
> **最后更新**: 2025-10-14
> **API版本**: v2 (已升级完成)

---

## 目录

1. [快速开始](#1-快速开始)
2. [API配置](#2-api配置)
3. [测试模式与生产模式](#3-测试模式与生产模式)
4. [集成架构设计](#4-集成架构设计)
5. [核心实现](#5-核心实现)
6. [高级功能](#6-高级功能)
7. [故障排查](#7-故障排查)
8. [成本优化](#8-成本优化)
9. [安全与监控](#9-安全与监控)
10. [测试策略](#10-测试策略)
11. [API v2升级记录](#11-api-v2升级记录)

---

## 1. 快速开始

### 1.1 当前状态

✅ **已完成**: Firecrawl API v2 升级
✅ **API密钥**: 已配置到 `.env`
✅ **测试通过**: 基本爬取功能正常
✅ **集成就绪**: 可立即在项目中使用

### 1.2 获取API密钥

#### 方法1: 官网注册 (推荐)
1. 访问 [Firecrawl官网](https://firecrawl.dev)
2. 注册账号并登录
3. 进入Dashboard → API Keys
4. 创建新的API密钥并复制

#### 方法2: 使用测试密钥
```bash
# 用于开发和测试 (有请求限制)
FIRECRAWL_API_KEY=fc-test-your-test-key-here
```

### 1.3 基本使用示例

```python
from firecrawl import FirecrawlApp

# 初始化客户端
app = FirecrawlApp(api_key="your-api-key")

# 抓取单个页面
result = app.scrape(
    url="https://example.com",
    formats=['markdown', 'html']
)

print(result['markdown'])
```

---

## 2. API配置

### 2.1 环境变量配置

在项目根目录创建或编辑 `.env` 文件:

```bash
# Firecrawl API Configuration
FIRECRAWL_API_KEY=fc-your-api-key-here
FIRECRAWL_API_URL=https://api.firecrawl.dev/v2
FIRECRAWL_TIMEOUT=30
FIRECRAWL_MAX_RETRIES=3

# 可选配置
FIRECRAWL_TEST_MODE=false
FIRECRAWL_LOG_LEVEL=INFO
```

### 2.2 配置参数说明

| 参数 | 说明 | 默认值 | 必需 |
|------|------|--------|------|
| `FIRECRAWL_API_KEY` | API密钥 | - | ✅ |
| `FIRECRAWL_API_URL` | API端点URL | `https://api.firecrawl.dev/v2` | ❌ |
| `FIRECRAWL_TIMEOUT` | 请求超时时间(秒) | `30` | ❌ |
| `FIRECRAWL_MAX_RETRIES` | 最大重试次数 | `3` | ❌ |
| `FIRECRAWL_TEST_MODE` | 是否使用测试模式 | `false` | ❌ |

### 2.3 代码中使用配置

```python
from src.config import settings

# 从配置中读取API密钥
api_key = settings.FIRECRAWL_API_KEY
api_url = settings.FIRECRAWL_API_URL

# 初始化Firecrawl客户端
app = FirecrawlApp(
    api_key=api_key,
    api_url=api_url
)
```

---

## 3. 测试模式与生产模式

### 3.1 测试模式

**使用场景**: 开发和测试阶段

```bash
# .env配置
FIRECRAWL_TEST_MODE=true
FIRECRAWL_API_KEY=fc-test-your-test-key
```

**特点**:
- ✅ 无需付费API密钥
- ⚠️ 每日请求限制较低 (通常100-500次)
- ⚠️ 速度可能较慢
- ⚠️ 不适合生产环境

### 3.2 生产模式

**使用场景**: 正式环境部署

```bash
# .env配置
FIRECRAWL_TEST_MODE=false
FIRECRAWL_API_KEY=fc-prod-your-production-key
```

**特点**:
- ✅ 更高的请求配额
- ✅ 更快的响应速度
- ✅ 稳定可靠
- ⚠️ 需要付费订阅

### 3.3 模式切换

```python
from src.config import settings

if settings.FIRECRAWL_TEST_MODE:
    print("⚠️ 当前运行在测试模式")
    # 使用测试密钥
    api_key = settings.FIRECRAWL_TEST_API_KEY
else:
    print("✅ 当前运行在生产模式")
    # 使用生产密钥
    api_key = settings.FIRECRAWL_API_KEY
```

---

## 4. 集成架构设计

### 4.1 六边形架构 (端口-适配器模式)

```
┌─────────────────────────────────────────┐
│        Application Layer (应用层)        │
│  ┌────────────────────────────────────┐ │
│  │  CrawlerApplicationService         │ │
│  │  - 业务逻辑协调                     │ │
│  │  - 用例实现                         │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
              ↓           ↑
┌─────────────────────────────────────────┐
│        Domain Layer (领域层)             │
│  ┌────────────────────────────────────┐ │
│  │  CrawlerInterface (端口)            │ │
│  │  - scrape() / crawl() / search()   │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
              ↓           ↑
┌─────────────────────────────────────────┐
│     Infrastructure Layer (基础设施层)    │
│  ┌────────────────────────────────────┐ │
│  │  FirecrawlAdapter (适配器)          │ │
│  │  - 实现CrawlerInterface             │ │
│  │  - 调用Firecrawl API                │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 4.2 核心组件职责

#### 4.2.1 领域接口 (CrawlerInterface)

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class CrawlResult:
    """爬取结果统一数据结构"""
    url: str
    markdown: str
    html: str
    metadata: Dict[str, Any]
    success: bool
    error: str | None = None

class CrawlerInterface(ABC):
    """爬虫抽象接口"""

    @abstractmethod
    async def scrape(self, url: str, **options) -> CrawlResult:
        """抓取单个URL"""
        pass

    @abstractmethod
    async def crawl(self, url: str, **options) -> List[CrawlResult]:
        """深度爬取网站"""
        pass

    @abstractmethod
    async def search(self, query: str, **options) -> List[CrawlResult]:
        """搜索模式爬取"""
        pass
```

#### 4.2.2 Firecrawl适配器 (FirecrawlAdapter)

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class FirecrawlAdapter(CrawlerInterface):
    """Firecrawl爬虫适配器"""

    def __init__(self, api_key: str, api_url: str | None = None):
        self.client = FirecrawlApp(api_key=api_key, api_url=api_url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def scrape(self, url: str, **options) -> CrawlResult:
        """抓取单个页面 (自动重试)"""
        try:
            scrape_options = {
                'formats': options.get('formats', ['markdown', 'html']),
                'includeTags': options.get('include_tags', []),
                'excludeTags': options.get('exclude_tags', ['nav', 'footer']),
                'waitFor': options.get('wait_for', 1000),
                'actions': options.get('actions', [])
            }

            result = await self.client.scrape(url, **scrape_options)

            return CrawlResult(
                url=url,
                markdown=result.get('markdown', ''),
                html=result.get('html', ''),
                metadata=result.get('metadata', {}),
                success=True
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                markdown='',
                html='',
                metadata={},
                success=False,
                error=str(e)
            )

    async def crawl(self, url: str, **options) -> List[CrawlResult]:
        """深度爬取网站"""
        crawl_options = {
            'limit': options.get('limit', 100),
            'scrapeOptions': {
                'formats': ['markdown', 'html'],
                'excludeTags': ['nav', 'footer', 'aside']
            }
        }

        results = []
        async for page in self.client.crawl(url, **crawl_options):
            results.append(CrawlResult(
                url=page.get('url', ''),
                markdown=page.get('markdown', ''),
                html=page.get('html', ''),
                metadata=page.get('metadata', {}),
                success=True
            ))

        return results

    async def search(self, query: str, **options) -> List[CrawlResult]:
        """搜索模式爬取"""
        search_options = {
            'limit': options.get('limit', 10),
            'scrapeOptions': {
                'formats': ['markdown']
            }
        }

        results = await self.client.search(query, **search_options)

        return [
            CrawlResult(
                url=item.get('url', ''),
                markdown=item.get('markdown', ''),
                html='',
                metadata=item.get('metadata', {}),
                success=True
            )
            for item in results
        ]
```

#### 4.2.3 应用服务层 (CrawlerApplicationService)

```python
class CrawlerApplicationService:
    """爬虫应用服务"""

    def __init__(self, crawler: CrawlerInterface):
        self.crawler = crawler

    async def scrape_page(self, url: str, options: Dict[str, Any]) -> CrawlResult:
        """抓取单页 (业务用例)"""
        # 添加业务规则验证
        if not self._is_valid_url(url):
            raise ValueError(f"无效的URL: {url}")

        # 执行爬取
        result = await self.crawler.scrape(url, **options)

        # 业务逻辑处理
        if result.success:
            await self._save_to_database(result)
            await self._notify_completion(result)

        return result

    async def scrape_multiple_pages(
        self,
        urls: List[str],
        options: Dict[str, Any]
    ) -> List[CrawlResult]:
        """批量抓取 (业务用例)"""
        tasks = [self.scrape_page(url, options) for url in urls]
        return await asyncio.gather(*tasks)
```

---

## 5. 核心实现

### 5.1 基本爬取实现

```python
from src.infrastructure.crawler.firecrawl_adapter import FirecrawlAdapter
from src.config import settings

# 初始化适配器
crawler = FirecrawlAdapter(
    api_key=settings.FIRECRAWL_API_KEY,
    api_url=settings.FIRECRAWL_API_URL
)

# 爬取单个页面
result = await crawler.scrape(
    url="https://example.com",
    formats=['markdown', 'html'],
    include_tags=['article', 'main'],
    exclude_tags=['nav', 'footer', 'aside'],
    wait_for=2000
)

if result.success:
    print(f"✅ 成功: {result.url}")
    print(f"内容长度: {len(result.markdown)} 字符")
else:
    print(f"❌ 失败: {result.error}")
```

### 5.2 API端点集成

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/api/v1/crawler", tags=["Crawler"])

class ScrapeRequest(BaseModel):
    url: HttpUrl
    formats: List[str] = ['markdown']
    include_tags: List[str] = []
    exclude_tags: List[str] = ['nav', 'footer']

@router.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    """抓取单个URL"""
    crawler = FirecrawlAdapter(
        api_key=settings.FIRECRAWL_API_KEY
    )

    result = await crawler.scrape(
        url=str(request.url),
        formats=request.formats,
        include_tags=request.include_tags,
        exclude_tags=request.exclude_tags
    )

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=f"爬取失败: {result.error}"
        )

    return {
        "url": result.url,
        "markdown": result.markdown,
        "metadata": result.metadata
    }
```

---

## 6. 高级功能

### 6.1 动态内容处理

```python
# 等待JavaScript渲染
result = await crawler.scrape(
    url="https://spa-website.com",
    wait_for=5000,  # 等待5秒
    actions=[
        {
            'type': 'click',
            'selector': '#load-more-button'
        },
        {
            'type': 'wait',
            'milliseconds': 2000
        }
    ]
)
```

### 6.2 智能内容提取

```python
# 使用AI提取结构化数据
result = await crawler.scrape(
    url="https://product-page.com",
    formats=['markdown'],
    extract_schema={
        'type': 'object',
        'properties': {
            'product_name': {'type': 'string'},
            'price': {'type': 'number'},
            'description': {'type': 'string'},
            'reviews': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'author': {'type': 'string'},
                        'rating': {'type': 'number'},
                        'comment': {'type': 'string'}
                    }
                }
            }
        }
    }
)
```

### 6.3 批量爬取优化

```python
import asyncio
from typing import List

async def batch_scrape(
    urls: List[str],
    batch_size: int = 5,
    delay: float = 1.0
) -> List[CrawlResult]:
    """批量爬取 (并发控制)"""
    results = []

    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]

        # 并发执行批次
        batch_results = await asyncio.gather(*[
            crawler.scrape(url) for url in batch
        ])

        results.extend(batch_results)

        # 批次间延迟
        if i + batch_size < len(urls):
            await asyncio.sleep(delay)

    return results
```

### 6.4 增量爬取策略

```python
from datetime import datetime, timedelta

class IncrementalCrawler:
    """增量爬取器"""

    def __init__(self, crawler: CrawlerInterface):
        self.crawler = crawler
        self.last_crawl_cache = {}

    async def crawl_if_updated(
        self,
        url: str,
        cache_hours: int = 24
    ) -> CrawlResult | None:
        """仅在内容更新时爬取"""

        # 检查缓存
        if url in self.last_crawl_cache:
            last_crawl_time = self.last_crawl_cache[url]['time']
            if datetime.now() - last_crawl_time < timedelta(hours=cache_hours):
                print(f"⚡ 使用缓存: {url}")
                return None

        # 执行爬取
        result = await self.crawler.scrape(url)

        # 更新缓存
        self.last_crawl_cache[url] = {
            'time': datetime.now(),
            'content_hash': hash(result.markdown)
        }

        return result
```

---

## 7. 故障排查

### 7.1 常见错误及解决方案

#### 错误1: API密钥无效

```
FirecrawlError: Invalid API key
```

**原因**: API密钥配置错误或已过期

**解决方案**:
1. 检查 `.env` 文件中的 `FIRECRAWL_API_KEY`
2. 确认密钥格式: `fc-` 开头
3. 验证密钥是否过期 (登录Dashboard查看)
4. 测试模式: 使用 `fc-test-` 开头的测试密钥

```bash
# 验证密钥
curl -X GET "https://api.firecrawl.dev/v2/account/info" \
  -H "Authorization: Bearer fc-your-api-key"
```

#### 错误2: 请求超时

```
TimeoutError: Request timed out after 30 seconds
```

**原因**: 网页加载时间过长或网络问题

**解决方案**:
1. 增加超时时间配置
```python
FIRECRAWL_TIMEOUT=60  # 增加到60秒
```

2. 使用重试机制
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=10))
async def scrape_with_retry(url: str):
    return await crawler.scrape(url)
```

3. 检查目标网站是否可访问
```bash
curl -I https://target-website.com
```

#### 错误3: 配额超限

```
FirecrawlError: Rate limit exceeded (429 Too Many Requests)
```

**原因**: 超过API配额限制

**解决方案**:
1. 检查当前配额使用情况
```python
account_info = await app.get_account_info()
print(f"剩余配额: {account_info['credits_remaining']}")
```

2. 实现请求限流
```python
import asyncio
from asyncio import Semaphore

async def rate_limited_scrape(
    urls: List[str],
    max_concurrent: int = 3,
    delay: float = 1.0
):
    semaphore = Semaphore(max_concurrent)

    async def scrape_with_limit(url: str):
        async with semaphore:
            result = await crawler.scrape(url)
            await asyncio.sleep(delay)  # 请求间延迟
            return result

    return await asyncio.gather(*[scrape_with_limit(url) for url in urls])
```

3. 升级订阅计划 (生产环境)

#### 错误4: 爬取失败 (403/404/500)

```
FirecrawlError: Failed to scrape URL (HTTP 403)
```

**原因**: 目标网站阻止爬取或页面不存在

**解决方案**:
1. 检查URL有效性
```python
import requests

def validate_url(url: str) -> bool:
    try:
        response = requests.head(url, timeout=5)
        return response.status_code < 400
    except:
        return False
```

2. 添加User-Agent和Headers
```python
result = await crawler.scrape(
    url="https://example.com",
    headers={
        'User-Agent': 'Mozilla/5.0 (compatible; YourBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml'
    }
)
```

3. 处理反爬虫机制
   - 使用代理IP
   - 增加请求间隔
   - 遵守robots.txt规则

#### 错误5: 内容解析失败

```
FirecrawlError: Failed to parse content
```

**原因**: 网页结构异常或编码问题

**解决方案**:
1. 尝试不同的格式
```python
result = await crawler.scrape(
    url="https://example.com",
    formats=['markdown', 'html', 'rawHtml']  # 多种格式
)
```

2. 指定编码
```python
result = await crawler.scrape(
    url="https://example.com",
    encoding='utf-8'
)
```

3. 使用更宽松的解析选项
```python
result = await crawler.scrape(
    url="https://example.com",
    exclude_tags=[],  # 不排除任何标签
    include_tags=[]   # 不限制标签
)
```

### 7.2 诊断工具

#### 连接测试脚本

```python
import asyncio
from src.infrastructure.crawler.firecrawl_adapter import FirecrawlAdapter
from src.config import settings

async def diagnose_firecrawl():
    """诊断Firecrawl连接和配置"""

    print("🔍 Firecrawl诊断工具\n")

    # 1. 检查配置
    print("1. 检查配置:")
    print(f"   API Key: {settings.FIRECRAWL_API_KEY[:10]}...")
    print(f"   API URL: {settings.FIRECRAWL_API_URL}")
    print(f"   Timeout: {settings.FIRECRAWL_TIMEOUT}s\n")

    # 2. 测试连接
    print("2. 测试API连接:")
    try:
        crawler = FirecrawlAdapter(settings.FIRECRAWL_API_KEY)
        result = await crawler.scrape("https://firecrawl.dev")

        if result.success:
            print("   ✅ 连接成功")
            print(f"   ✅ 内容长度: {len(result.markdown)} 字符\n")
        else:
            print(f"   ❌ 爬取失败: {result.error}\n")
    except Exception as e:
        print(f"   ❌ 连接失败: {str(e)}\n")

    # 3. 检查配额
    print("3. 检查API配额:")
    try:
        app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        info = await app.get_account_info()
        print(f"   剩余配额: {info.get('credits_remaining', 'N/A')}")
        print(f"   总配额: {info.get('credits_total', 'N/A')}")
    except Exception as e:
        print(f"   ⚠️ 无法获取配额信息: {str(e)}")

if __name__ == "__main__":
    asyncio.run(diagnose_firecrawl())
```

### 7.3 日志配置

```python
import logging

# 配置Firecrawl日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 启用详细日志
logger = logging.getLogger('firecrawl')
logger.setLevel(logging.DEBUG)
```

---

## 8. 成本优化

### 8.1 配额监控

```python
class CreditMonitor:
    """API配额监控"""

    def __init__(self, app: FirecrawlApp, threshold: int = 100):
        self.app = app
        self.threshold = threshold

    async def check_credits(self) -> bool:
        """检查剩余配额"""
        info = await self.app.get_account_info()
        remaining = info.get('credits_remaining', 0)

        if remaining < self.threshold:
            logger.warning(
                f"⚠️ API配额不足: 剩余 {remaining} credits"
            )
            return False

        return True
```

### 8.2 缓存策略

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedCrawler:
    """带缓存的爬虫"""

    def __init__(self, crawler: CrawlerInterface):
        self.crawler = crawler
        self.cache = {}

    async def scrape_cached(
        self,
        url: str,
        cache_ttl: int = 3600  # 1小时
    ) -> CrawlResult:
        """带缓存的爬取"""

        # 检查缓存
        if url in self.cache:
            cached_time, cached_result = self.cache[url]
            if (datetime.now() - cached_time).seconds < cache_ttl:
                logger.info(f"⚡ 缓存命中: {url}")
                return cached_result

        # 执行爬取
        result = await self.crawler.scrape(url)

        # 更新缓存
        self.cache[url] = (datetime.now(), result)

        return result
```

### 8.3 选择性爬取

```python
async def smart_scrape(url: str, priority: str = 'low') -> CrawlResult:
    """根据优先级选择爬取策略"""

    if priority == 'high':
        # 高优先级: 完整爬取
        return await crawler.scrape(
            url=url,
            formats=['markdown', 'html'],
            wait_for=5000
        )
    elif priority == 'medium':
        # 中优先级: 仅Markdown
        return await crawler.scrape(
            url=url,
            formats=['markdown'],
            wait_for=2000
        )
    else:
        # 低优先级: 最小配置
        return await crawler.scrape(
            url=url,
            formats=['markdown'],
            exclude_tags=['script', 'style', 'nav', 'footer']
        )
```

---

## 9. 安全与监控

### 9.1 API密钥安全

```python
# ✅ 正确: 使用环境变量
api_key = os.getenv('FIRECRAWL_API_KEY')

# ❌ 错误: 硬编码密钥
api_key = 'fc-1234567890abcdef'  # 永远不要这样做!

# ✅ 正确: 密钥验证
def validate_api_key(key: str) -> bool:
    if not key or not key.startswith('fc-'):
        raise ValueError("无效的API密钥格式")
    if len(key) < 20:
        raise ValueError("API密钥长度不足")
    return True
```

### 9.2 监控指标

```python
from prometheus_client import Counter, Histogram

# 定义监控指标
scrape_requests = Counter(
    'firecrawl_scrape_requests_total',
    'Total Firecrawl scrape requests',
    ['status']
)

scrape_duration = Histogram(
    'firecrawl_scrape_duration_seconds',
    'Firecrawl scrape duration'
)

@scrape_duration.time()
async def monitored_scrape(url: str) -> CrawlResult:
    """带监控的爬取"""
    try:
        result = await crawler.scrape(url)
        scrape_requests.labels(status='success').inc()
        return result
    except Exception as e:
        scrape_requests.labels(status='error').inc()
        raise
```

### 9.3 合规性

```python
import robots_txt_parser

class ComplianceCrawler:
    """遵守robots.txt的爬虫"""

    def __init__(self, crawler: CrawlerInterface):
        self.crawler = crawler
        self.robots_parser = robots_txt_parser.RobotsTxtParser()

    async def scrape_compliant(self, url: str) -> CrawlResult:
        """检查robots.txt后再爬取"""

        # 检查是否允许爬取
        if not self.robots_parser.can_fetch('*', url):
            raise PermissionError(
                f"robots.txt禁止爬取: {url}"
            )

        return await self.crawler.scrape(url)
```

---

## 10. 测试策略

### 10.1 单元测试

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_firecrawl_adapter_scrape_success():
    """测试成功爬取"""

    # Mock Firecrawl响应
    mock_result = {
        'markdown': '# Test Content',
        'html': '<h1>Test Content</h1>',
        'metadata': {'title': 'Test Page'}
    }

    with patch('firecrawl.FirecrawlApp.scrape', return_value=mock_result):
        crawler = FirecrawlAdapter(api_key='test-key')
        result = await crawler.scrape('https://test.com')

        assert result.success is True
        assert result.markdown == '# Test Content'
        assert result.metadata['title'] == 'Test Page'

@pytest.mark.asyncio
async def test_firecrawl_adapter_scrape_failure():
    """测试爬取失败"""

    with patch('firecrawl.FirecrawlApp.scrape', side_effect=Exception('Network error')):
        crawler = FirecrawlAdapter(api_key='test-key')
        result = await crawler.scrape('https://test.com')

        assert result.success is False
        assert 'Network error' in result.error
```

### 10.2 集成测试

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_firecrawl_scrape():
    """集成测试: 真实API调用"""

    api_key = os.getenv('FIRECRAWL_TEST_API_KEY')
    if not api_key:
        pytest.skip("未配置测试API密钥")

    crawler = FirecrawlAdapter(api_key=api_key)
    result = await crawler.scrape('https://firecrawl.dev')

    assert result.success is True
    assert len(result.markdown) > 0
    assert result.url == 'https://firecrawl.dev'
```

### 10.3 性能测试

```python
import time
import statistics

@pytest.mark.performance
@pytest.mark.asyncio
async def test_scrape_performance():
    """性能测试: 爬取速度"""

    crawler = FirecrawlAdapter(api_key='test-key')
    urls = [f'https://test.com/page{i}' for i in range(10)]

    start_time = time.time()
    results = await asyncio.gather(*[
        crawler.scrape(url) for url in urls
    ])
    end_time = time.time()

    duration = end_time - start_time
    avg_time = duration / len(urls)

    print(f"\n性能指标:")
    print(f"总耗时: {duration:.2f}秒")
    print(f"平均每个URL: {avg_time:.2f}秒")

    assert avg_time < 5.0  # 平均每个URL不超过5秒
```

---

## 11. API v2升级记录

### 11.1 升级时间线

- **2025-10-11**: Firecrawl官方发布v2 API
- **2025-10-12**: 项目开始评估升级
- **2025-10-13**: 完成v2 API集成测试
- **2025-10-14**: 生产环境正式切换到v2

### 11.2 主要变更

#### v1 → v2 API差异

| 功能 | v1 API | v2 API | 变更说明 |
|------|--------|--------|----------|
| 端点URL | `/v1/scrape` | `/v2/scrape` | URL路径变更 |
| 响应格式 | `{content: ...}` | `{markdown: ..., html: ...}` | 结构化响应 |
| 格式选项 | 单一格式 | 多格式支持 | 可同时返回markdown和html |
| 认证方式 | Header: `x-api-key` | Header: `Authorization: Bearer` | 标准Bearer Token |
| 速率限制 | 60 req/min | 100 req/min | 提升了限制 |
| 超时时间 | 30秒 | 60秒 | 更宽松的超时 |

#### 代码迁移示例

```python
# ========== v1 API (已废弃) ==========
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key=api_key)
result = app.scrape_url(url)  # v1方法
content = result['content']   # v1响应格式

# ========== v2 API (当前版本) ==========
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key=api_key)
result = app.scrape(url, formats=['markdown', 'html'])  # v2方法
markdown = result['markdown']  # v2响应格式
html = result['html']
```

### 11.3 升级影响评估

✅ **已完成验证**:
- 基本爬取功能正常
- 响应格式兼容
- 性能无明显下降
- 错误处理机制有效

⚠️ **需要注意**:
- 旧的v1端点将在2025-12-31后失效
- 部分高级功能API有所变化
- 配额计算方式略有不同

### 11.4 回滚计划

如果v2出现严重问题,可临时回滚到v1:

```python
# 回滚配置
FIRECRAWL_API_URL=https://api.firecrawl.dev/v1  # 使用v1端点
FIRECRAWL_USE_LEGACY=true                       # 启用兼容模式

# 兼容性适配器
class LegacyFirecrawlAdapter(FirecrawlAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_version = 'v1'

    async def scrape(self, url: str, **options) -> CrawlResult:
        # 使用v1 API调用
        result = await self.client.scrape_url(url)

        return CrawlResult(
            url=url,
            markdown=result.get('content', ''),  # v1格式转换
            html='',
            metadata=result.get('metadata', {}),
            success=True
        )
```

---

## 附录

### A. 完整配置参考

```bash
# .env.example - Firecrawl完整配置模板

# ========== 必需配置 ==========
FIRECRAWL_API_KEY=fc-your-api-key-here

# ========== 可选配置 ==========
FIRECRAWL_API_URL=https://api.firecrawl.dev/v2
FIRECRAWL_TIMEOUT=30
FIRECRAWL_MAX_RETRIES=3
FIRECRAWL_TEST_MODE=false

# ========== 高级配置 ==========
FIRECRAWL_LOG_LEVEL=INFO
FIRECRAWL_ENABLE_CACHE=true
FIRECRAWL_CACHE_TTL=3600
FIRECRAWL_MAX_CONCURRENT_REQUESTS=5
FIRECRAWL_REQUEST_DELAY=1.0

# ========== 监控配置 ==========
FIRECRAWL_ENABLE_METRICS=true
FIRECRAWL_CREDIT_ALERT_THRESHOLD=100
```

### B. 常用命令

```bash
# 验证配置
python -m src.infrastructure.crawler.diagnose

# 运行测试
pytest tests/crawler/ -v

# 性能测试
pytest tests/crawler/ -v -m performance

# 集成测试
pytest tests/crawler/ -v -m integration
```

### C. 相关资源

- **官方文档**: https://docs.firecrawl.dev
- **API参考**: https://docs.firecrawl.dev/api-reference
- **Python SDK**: https://github.com/mendableai/firecrawl-py
- **社区支持**: https://discord.gg/firecrawl
- **问题反馈**: https://github.com/mendableai/firecrawl/issues

### D. 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2025-10-14 | 2.0 | 合并FIRECRAWL_INTEGRATION.md和FIRECRAWL_API_CONFIGURATION.md |
| 2025-10-13 | 1.2 | 完成API v2升级和测试 |
| 2025-10-12 | 1.1 | 添加故障排查章节 |
| 2025-10-11 | 1.0 | 初始版本创建 |

---

**文档维护者**: Backend Development Team
**最后更新**: 2025-10-14
**状态**: ✅ 当前版本
