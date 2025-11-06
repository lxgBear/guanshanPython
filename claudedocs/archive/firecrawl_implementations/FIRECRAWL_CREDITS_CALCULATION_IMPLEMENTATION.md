# Firecrawl API 积分计算系统实现

**日期**: 2025-11-06
**版本**: v2.1.3
**状态**: ✅ 已完成

---

## 目录

1. [概述](#概述)
2. [Firecrawl API 定价规则](#firecrawl-api-定价规则)
3. [实现架构](#实现架构)
4. [核心组件](#核心组件)
5. [使用示例](#使用示例)
6. [API 接口](#api-接口)
7. [测试验证](#测试验证)
8. [未来优化](#未来优化)

---

## 概述

### 需求背景

用户需要了解每次 Firecrawl API 调用消耗的积分数量，以便：
1. 预估任务成本
2. 优化任务配置
3. 监控积分使用情况
4. 避免超额消费

### 实现目标

1. ✅ 创建准确的积分计算工具
2. ✅ 集成到所有 Executor 中
3. ✅ 提供 API 端点用于积分估算
4. ✅ 记录实际消耗的积分

---

## Firecrawl API 定价规则

基于 **Firecrawl v2 API 官方定价（2025年）**: https://www.firecrawl.dev/pricing

### 基础操作积分消耗

| 操作 | 积分消耗 | 说明 |
|------|---------|------|
| **Scrape API** | 1 积分/页面 | 爬取单个页面 |
| **Crawl API** | 1 积分/页面 | 递归爬取网站，每个发现的页面消耗1积分 |
| **Search API** | 2 积分/10条结果 | 仅搜索不爬取 (0.2积分/条) |
| **Search + Scrape** | 2积分 + N积分 | 搜索2积分 + 爬取N条 × 1积分/条 |

### 附加功能积分消耗

| 功能 | 额外积分 | 说明 |
|------|---------|------|
| **PDF 解析** | +1 积分/PDF页 | 解析 PDF 文档的每一页 |
| **Stealth 代理模式** | +4 积分/结果 | 使用隐身代理绕过检测 |
| **JSON 模式** | +4 积分/结果 | 结构化 JSON 数据提取 |

### 典型任务积分估算

#### 关键词搜索任务

**场景 1**: 搜索10条结果，爬取详情页
```
积分 = 2 (搜索) + 10 (爬取) = 12 积分
```

**场景 2**: 搜索20条结果，爬取详情页
```
积分 = 4 (搜索: ceil(20/10) × 2) + 20 (爬取) = 24 积分
```

**场景 3**: 搜索10条结果，不爬取详情页
```
积分 = 2 (搜索) = 2 积分
```

#### 网站爬取任务

**场景 1**: 爬取10个页面
```
积分 = 10 × 1 = 10 积分
```

**场景 2**: 爬取100个页面
```
积分 = 100 × 1 = 100 积分
```

#### 单页面爬取任务

**场景 1**: 爬取普通网页
```
积分 = 1 积分
```

**场景 2**: 爬取包含10页PDF的页面
```
积分 = 1 (页面) + 10 (PDF) = 11 积分
```

---

## 实现架构

### 架构图

```
┌────────────────────────────────────────────────────────────────┐
│                 Firecrawl Credits Calculation                  │
└────────────────────────┬───────────────────────────────────────┘
                         │
         ┌───────────────┴──────────────┐
         │                              │
         ▼                              ▼
┌────────────────────┐         ┌───────────────────┐
│  Credits           │         │  API Endpoints    │
│  Calculator        │         │  (Estimation)     │
└────────┬───────────┘         └─────────┬─────────┘
         │                               │
         │ 被调用                         │ 提供估算
         │                               │
         ▼                               ▼
┌──────────────────────────────────────────────────┐
│            Task Executors                         │
│  - SearchExecutor  (搜索 + 爬取)                  │
│  - CrawlExecutor   (网站爬取)                     │
│  - ScrapeExecutor  (单页面爬取)                   │
└──────────────────────────────────────────────────┘
         │
         │ 记录积分
         ▼
┌──────────────────────────────────────────────────┐
│            SearchResultBatch                      │
│            credits_used: int                      │
└──────────────────────────────────────────────────┘
```

### 设计模式

**策略模式**: 不同操作类型有不同的积分计算策略
- `calculate_actual_credits(operation, **kwargs)`
- 根据 operation 类型("search", "crawl", "scrape")选择计算方法

**工厂模式**: 积分估算对象创建
- `estimate_search_credits(...) -> CreditEstimate`
- `estimate_crawl_credits(...) -> CreditEstimate`
- `estimate_scrape_credits(...) -> CreditEstimate`

---

## 核心组件

### 1. FirecrawlCreditsCalculator

**位置**: `src/services/firecrawl/credits_calculator.py`

**职责**: 积分计算和估算核心逻辑

**关键方法**:

```python
class FirecrawlCreditsCalculator:
    # 估算方法（事前）
    @classmethod
    def estimate_search_credits(...) -> CreditEstimate

    @classmethod
    def estimate_crawl_credits(...) -> CreditEstimate

    @classmethod
    def estimate_scrape_credits(...) -> CreditEstimate

    # 实际计算方法（事后）
    @classmethod
    def calculate_actual_credits(operation: str, **kwargs) -> int

    # 定价信息
    @classmethod
    def get_pricing_info() -> Dict[str, Any]
```

**常量定义**:
```python
CREDIT_PER_SCRAPE = 1              # Scrape API: 1积分/页面
CREDIT_PER_CRAWL_PAGE = 1          # Crawl API: 1积分/页面
CREDIT_SEARCH_BASE = 2             # Search API: 2积分/10条结果
CREDIT_PER_SCRAPED_RESULT = 1      # 搜索结果爬取: 1积分/条
CREDIT_PDF_PER_PAGE = 1            # PDF解析: +1积分/PDF页
CREDIT_STEALTH_MODE = 4            # Stealth代理: +4积分/结果
CREDIT_JSON_MODE = 4               # JSON模式: +4积分/结果
```

### 2. Task Executors 集成

#### SearchExecutor 更新

**文件**: `src/services/firecrawl/executors/search_executor.py`

**关键改动**:

1. 导入积分计算器:
```python
from ..credits_calculator import FirecrawlCreditsCalculator
```

2. 返回成功爬取数量:
```python
async def _enrich_with_details(...) -> int:
    # ...
    return success_count  # 返回成功爬取的页面数
```

3. 计算实际积分消耗:
```python
# 计算实际积分消耗
actual_credits = FirecrawlCreditsCalculator.calculate_actual_credits(
    operation="search",
    results_count=len(search_batch.results),
    scraped_count=scraped_count
)
search_batch.credits_used = actual_credits

self.logger.info(
    f"💰 积分消耗: 搜索={search_batch.credits_used - scraped_count}, "
    f"爬取={scraped_count}, 总计={actual_credits}"
)
```

#### ScrapeExecutor 更新

**文件**: `src/services/firecrawl/executors/scrape_executor.py`

**关键改动**:

```python
# 计算实际积分消耗
batch.credits_used = FirecrawlCreditsCalculator.calculate_actual_credits(
    operation="scrape",
    urls_scraped=1
)
self.logger.info(f"💰 积分消耗: {batch.credits_used}")
```

#### CrawlExecutor 更新

**文件**: `src/services/firecrawl/executors/crawl_executor.py`

**关键改动**:

```python
# 计算实际积分消耗
batch.credits_used = FirecrawlCreditsCalculator.calculate_actual_credits(
    operation="crawl",
    pages_crawled=len(search_results)
)
self.logger.info(f"💰 积分消耗: {batch.credits_used} ({len(search_results)} 个页面)")
```

### 3. API 端点

**文件**: `src/api/v1/endpoints/firecrawl_utils.py`

**提供的接口**:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/firecrawl/estimate/search` | GET | 估算关键词搜索任务积分 |
| `/api/v1/firecrawl/estimate/crawl` | GET | 估算网站爬取任务积分 |
| `/api/v1/firecrawl/estimate/scrape` | GET | 估算单页面爬取任务积分 |
| `/api/v1/firecrawl/pricing` | GET | 获取积分定价信息 |

**路由注册**: `src/api/v1/router.py`
```python
api_router.include_router(
    firecrawl_utils.router,
    tags=["💰 Firecrawl 工具"]
)
```

---

## 使用示例

### Python 代码示例

#### 1. 估算搜索任务积分

```python
from src.services.firecrawl.credits_calculator import FirecrawlCreditsCalculator

# 估算搜索10条结果并爬取详情页
estimate = FirecrawlCreditsCalculator.estimate_search_credits(
    num_results=10,
    enable_detail_scrape=True
)

print(f"总积分: {estimate.total_credits}")  # 12
print(f"明细: {estimate.breakdown}")  # {'search_api': 2, 'detail_scrape': 10}
print(f"说明: {estimate.description}")
# 输出: 搜索 10 条结果: 2 积分 + 爬取详情页: 10 积分 = 12 积分
```

#### 2. 计算实际积分消耗

```python
# 在 Executor 中使用
actual_credits = FirecrawlCreditsCalculator.calculate_actual_credits(
    operation="search",
    results_count=10,  # 搜索返回10条结果
    scraped_count=8    # 成功爬取8条详情页
)

print(f"实际消耗: {actual_credits} 积分")  # 10 积分 (2 + 8)
```

#### 3. 获取定价信息

```python
pricing = FirecrawlCreditsCalculator.get_pricing_info()
print(pricing)
# {
#   "基础操作": {
#     "scrape_api": "1 积分/页面",
#     "crawl_api": "1 积分/页面",
#     "search_api_base": "2 积分/10条结果",
#     "search_result_scrape": "1 积分/条"
#   },
#   "附加功能": {...},
#   "说明": "基于 Firecrawl v2 API 官方定价（2025年）",
#   "参考链接": "https://www.firecrawl.dev/pricing"
# }
```

### API 调用示例

#### 1. 估算搜索任务积分

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/firecrawl/estimate/search?num_results=10&enable_detail_scrape=true"
```

**响应**:
```json
{
  "total_credits": 12,
  "breakdown": {
    "search_api": 2,
    "detail_scrape": 10
  },
  "description": "搜索 10 条结果: 2 积分 + 爬取详情页: 10 积分 = 12 积分"
}
```

#### 2. 估算网站爬取积分

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/firecrawl/estimate/crawl?limit=10&max_depth=3"
```

**响应**:
```json
{
  "total_credits": 10,
  "breakdown": {
    "crawl_pages": 10
  },
  "description": "爬取 10 个页面（限制: 10, 深度: 3）= 10 积分"
}
```

#### 3. 获取定价信息

**请求**:
```bash
curl -X GET "http://localhost:8000/api/v1/firecrawl/pricing"
```

**响应**:
```json
{
  "basic_operations": {
    "scrape_api": "1 积分/页面",
    "crawl_api": "1 积分/页面",
    "search_api_base": "2 积分/10条结果",
    "search_result_scrape": "1 积分/条"
  },
  "additional_features": {
    "pdf_parsing": "+1 积分/PDF页",
    "stealth_mode": "+4 积分/结果",
    "json_mode": "+4 积分/结果"
  },
  "note": "基于 Firecrawl v2 API 官方定价（2025年）",
  "reference_url": "https://www.firecrawl.dev/pricing"
}
```

---

## API 接口

### 完整 API 文档

#### GET /api/v1/firecrawl/estimate/search

估算关键词搜索任务积分消耗

**Query Parameters**:
- `num_results` (int, 必需): 搜索结果数量 [1-100]，默认10
- `enable_detail_scrape` (bool): 是否启用详情页爬取，默认true
- `use_stealth_mode` (bool): 是否使用Stealth代理模式，默认false
- `use_json_mode` (bool): 是否使用JSON模式，默认false

**Response**: `CreditEstimateResponse`

#### GET /api/v1/firecrawl/estimate/crawl

估算网站爬取任务积分消耗

**Query Parameters**:
- `limit` (int, 必需): 最大页面数限制 [1-500]，默认10
- `max_depth` (int): 最大爬取深度 [1-10]，默认3
- `estimated_pages` (int, 可选): 预估实际爬取页面数

**Response**: `CreditEstimateResponse`

#### GET /api/v1/firecrawl/estimate/scrape

估算单页面爬取任务积分消耗

**Query Parameters**:
- `num_urls` (int, 必需): URL数量 [1-100]，默认1
- `has_pdf` (bool): 是否包含PDF，默认false
- `pdf_pages` (int): PDF页数 [0-1000]，默认0

**Response**: `CreditEstimateResponse`

#### GET /api/v1/firecrawl/pricing

获取 Firecrawl API 积分定价信息

**Response**: `PricingInfoResponse`

---

## 测试验证

### 单元测试示例

创建测试文件: `tests/test_credits_calculator.py`

```python
import pytest
from src.services.firecrawl.credits_calculator import FirecrawlCreditsCalculator


class TestFirecrawlCreditsCalculator:
    """Firecrawl 积分计算器测试"""

    def test_estimate_search_credits_with_scrape(self):
        """测试搜索 + 爬取积分估算"""
        estimate = FirecrawlCreditsCalculator.estimate_search_credits(
            num_results=10,
            enable_detail_scrape=True
        )

        assert estimate.total_credits == 12
        assert estimate.breakdown["search_api"] == 2
        assert estimate.breakdown["detail_scrape"] == 10

    def test_estimate_search_credits_without_scrape(self):
        """测试仅搜索积分估算"""
        estimate = FirecrawlCreditsCalculator.estimate_search_credits(
            num_results=10,
            enable_detail_scrape=False
        )

        assert estimate.total_credits == 2
        assert estimate.breakdown["search_api"] == 2
        assert "detail_scrape" not in estimate.breakdown

    def test_calculate_actual_credits_search(self):
        """测试实际搜索积分计算"""
        credits = FirecrawlCreditsCalculator.calculate_actual_credits(
            operation="search",
            results_count=10,
            scraped_count=8
        )

        assert credits == 10  # 2 (搜索) + 8 (爬取)

    def test_calculate_actual_credits_crawl(self):
        """测试实际爬取积分计算"""
        credits = FirecrawlCreditsCalculator.calculate_actual_credits(
            operation="crawl",
            pages_crawled=25
        )

        assert credits == 25

    def test_calculate_actual_credits_scrape(self):
        """测试实际单页爬取积分计算"""
        credits = FirecrawlCreditsCalculator.calculate_actual_credits(
            operation="scrape",
            urls_scraped=1
        )

        assert credits == 1

    def test_estimate_crawl_credits(self):
        """测试网站爬取积分估算"""
        estimate = FirecrawlCreditsCalculator.estimate_crawl_credits(
            limit=100,
            max_depth=3,
            estimated_pages=50
        )

        assert estimate.total_credits == 50
        assert estimate.breakdown["crawl_pages"] == 50
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_search_executor_credits_calculation():
    """测试 SearchExecutor 积分计算"""
    from src.services.firecrawl.executors.search_executor import SearchExecutor
    from src.core.domain.entities.search_task import SearchTask

    executor = SearchExecutor()
    task = SearchTask(
        query="Python 新特性",
        search_config={
            "limit": 10,
            "enable_detail_scrape": True
        }
    )

    result_batch = await executor.execute(task)

    # 验证积分消耗被正确计算
    assert result_batch.credits_used > 0
    assert result_batch.credits_used >= 2  # 至少有搜索消耗
```

---

## 未来优化

### 1. 动态定价更新

**问题**: Firecrawl 定价可能变化

**解决方案**:
- 定期从 Firecrawl API 获取最新定价
- 支持配置文件覆盖定价规则
- 提供管理后台更新定价

### 2. 积分使用统计

**功能**:
- 每日/每月积分消耗统计
- 任务类型积分分布分析
- 积分消耗趋势预测

### 3. 积分配额管理

**功能**:
- 设置每日/每月积分配额
- 超额告警
- 自动暂停任务

### 4. 积分优化建议

**功能**:
- 分析任务配置
- 提供积分节省建议
- 自动优化任务参数

---

## 总结

### 实现成果

✅ **已完成**:
1. 创建 `FirecrawlCreditsCalculator` 积分计算工具
2. 更新所有 Executor 集成积分计算
3. 提供 4 个 API 端点用于积分估算和定价查询
4. 记录实际消耗的积分到 `SearchResultBatch`
5. 创建完整的文档和使用示例

### 关键特性

1. **准确性**: 基于 Firecrawl 官方定价（2025年）
2. **完整性**: 覆盖所有 API 操作类型
3. **可扩展性**: 支持未来新增的附加功能
4. **易用性**: 提供简洁的 API 和 Python 接口

### 技术亮点

1. **分离关注点**: 计算逻辑独立于 Executor
2. **类方法设计**: 无需实例化即可使用
3. **数据结构**: 使用 `CreditEstimate` dataclass 封装结果
4. **详细日志**: 记录积分消耗明细

---

**文档版本**: v1.0
**最后更新**: 2025-11-06
**作者**: Claude Code
**状态**: ✅ 实现完成并验证
