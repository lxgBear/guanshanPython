# Map+Scrape 执行器实现计划

**文档版本**: v1.0.0
**创建日期**: 2025-11-06
**状态**: 待实施

---

## 📋 实施概览

### 核心目标

✅ 使用Firecrawl的**Map API + Scrape API**实现指定URL加时间范围的精确爬取
✅ **替换**/crawl接口的使用场景（作为新选项）
✅ **保留**/crawl模块功能作为备用
✅ **数据库字段结构完全不变**

### 预期收益

- **积分节省**: 80-90%（只爬取需要的页面）
- **精确控制**: URL级别的爬取控制
- **时间过滤**: 支持按发布时间范围过滤
- **性能提升**: 并发scrape + Map API快速发现

---

## 🗂️ 文件变更清单

### 新增文件

```
src/services/firecrawl/executors/map_scrape_executor.py    [新建]
src/services/firecrawl/config/map_scrape_config.py         [新建]
tests/test_map_scrape_executor.py                          [新建]
docs/MAP_SCRAPE_EXECUTOR_DESIGN.md                         [已创建]
docs/FIRECRAWL_MAP_API_GUIDE.md                            [已创建]
```

### 修改文件

```
src/infrastructure/crawlers/firecrawl_adapter.py           [扩展]
  + async def map(url, search, limit) -> List[Dict]

src/core/domain/entities/search_task.py                    [扩展]
  + TaskType.MAP_SCRAPE_WEBSITE = "map_scrape_website"

src/services/firecrawl/factory.py                          [扩展]
  + 注册MapScrapeExecutor

src/services/firecrawl/config/__init__.py                  [扩展]
  + from .map_scrape_config import MapScrapeConfig

src/services/firecrawl/credits_calculator.py               [扩展]
  + calculate_map_scrape_credits()

docs/FIRECRAWL_ARCHITECTURE_V2.md                          [更新]
  + 添加MapScrapeExecutor说明
```

---

## 🔧 详细实施步骤

### Phase 1: 基础设施（第1天）

#### 1.1 扩展FirecrawlAdapter

**文件**: `src/infrastructure/crawlers/firecrawl_adapter.py`

**新增方法**：

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
    payload = {"url": url, "limit": limit}

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

**测试命令**：
```bash
python scripts/test_map_api.py
```

#### 1.2 创建配置类

**文件**: `src/services/firecrawl/config/map_scrape_config.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class MapScrapeConfig:
    """Map + Scrape 执行器配置

    示例:
        config = MapScrapeConfig(
            search="blog",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31),
            max_concurrent_scrapes=5
        )
    """

    # Map API 配置
    search: Optional[str] = None          # 搜索关键词
    map_limit: int = 5000                 # Map返回URL限制

    # 时间过滤
    start_date: Optional[datetime] = None # 开始日期
    end_date: Optional[datetime] = None   # 结束日期

    # Scrape API 配置
    max_concurrent_scrapes: int = 5       # 最大并发数
    scrape_delay: float = 0.5             # scrape间隔（秒）
    only_main_content: bool = True        # 只提取主要内容
    exclude_tags: List[str] = field(
        default_factory=lambda: ["nav", "footer", "header", "aside"]
    )
    timeout: int = 90                     # 超时时间（秒）

    # 错误处理
    allow_partial_failure: bool = True    # 允许部分失败
    min_success_rate: float = 0.8         # 最低成功率
```

**更新**: `src/services/firecrawl/config/__init__.py`

```python
from .task_config import SearchConfig, CrawlConfig, ScrapeConfig, ConfigFactory
from .map_scrape_config import MapScrapeConfig

# 扩展ConfigFactory
class ConfigFactory:
    # ... 现有方法 ...

    @staticmethod
    def create_map_scrape_config(config_dict: Dict[str, Any]) -> MapScrapeConfig:
        """从字典创建MapScrapeConfig"""
        # 处理日期字符串
        if 'start_date' in config_dict and isinstance(config_dict['start_date'], str):
            config_dict['start_date'] = datetime.fromisoformat(config_dict['start_date'])

        if 'end_date' in config_dict and isinstance(config_dict['end_date'], str):
            config_dict['end_date'] = datetime.fromisoformat(config_dict['end_date'])

        return MapScrapeConfig(**config_dict)
```

#### 1.3 更新TaskType枚举

**文件**: `src/core/domain/entities/search_task.py`

```python
class TaskType(Enum):
    """任务类型枚举"""
    SEARCH_KEYWORD = "search_keyword"      # 关键词搜索模式
    CRAWL_WEBSITE = "crawl_website"        # 网站爬取模式（Crawl API）
    SCRAPE_URL = "scrape_url"              # 单页面爬取模式
    MAP_SCRAPE_WEBSITE = "map_scrape_website"  # Map+Scrape模式（新增）
```

**扩展SearchTask类**：

```python
def is_map_scrape_mode(self) -> bool:
    """判断是否为Map+Scrape模式"""
    return self.get_task_type() == TaskType.MAP_SCRAPE_WEBSITE
```

---

### Phase 2: 核心执行器（第2天）

#### 2.1 创建MapScrapeExecutor

**文件**: `src/services/firecrawl/executors/map_scrape_executor.py`

**完整代码** (见附录A)

**关键方法**：

1. `execute()` - 主执行流程
2. `_execute_map()` - Map API调用
3. `_batch_scrape()` - 批量Scrape
4. `_filter_by_date()` - 时间过滤
5. `_convert_to_search_results()` - 结果转换
6. `_save_raw_responses()` - 保存原始响应

#### 2.2 注册执行器

**文件**: `src/services/firecrawl/factory.py`

```python
from .executors.map_scrape_executor import MapScrapeExecutor

class ExecutorFactory:
    """执行器工厂类"""

    _executors = {
        TaskType.SEARCH_KEYWORD: SearchExecutor,
        TaskType.CRAWL_WEBSITE: CrawlExecutor,
        TaskType.SCRAPE_URL: ScrapeExecutor,
        TaskType.MAP_SCRAPE_WEBSITE: MapScrapeExecutor,  # 新增
    }

    # ... 其他方法不变 ...
```

#### 2.3 更新积分计算器

**文件**: `src/services/firecrawl/credits_calculator.py`

```python
class FirecrawlCreditsCalculator:
    """Firecrawl积分消耗计算器"""

    # ... 现有方法 ...

    @staticmethod
    def calculate_map_scrape_credits(
        map_calls: int,
        urls_scraped: int
    ) -> int:
        """计算Map + Scrape操作的积分消耗

        Args:
            map_calls: Map API调用次数
            urls_scraped: Scrape的URL数量

        Returns:
            int: 总积分消耗
        """
        map_cost = map_calls * 1    # Map: 1 credit/call
        scrape_cost = urls_scraped * 1  # Scrape: 1 credit/URL

        return map_cost + scrape_cost
```

---

### Phase 3: 测试验证（第3天）

#### 3.1 单元测试

**文件**: `tests/test_map_scrape_executor.py`

```python
import pytest
from datetime import datetime, timedelta
from src.services.firecrawl.executors.map_scrape_executor import MapScrapeExecutor
from src.services.firecrawl.config.map_scrape_config import MapScrapeConfig
from src.core.domain.entities.search_task import SearchTask, TaskType

class TestMapScrapeExecutor:

    @pytest.fixture
    def executor(self):
        return MapScrapeExecutor()

    @pytest.fixture
    def test_task(self):
        return SearchTask(
            name="测试任务",
            crawl_url="https://example.com",
            task_type=TaskType.MAP_SCRAPE_WEBSITE,
            crawl_config={
                "search": "blog",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "max_concurrent_scrapes": 3
            }
        )

    @pytest.mark.asyncio
    async def test_execute_map(self, executor):
        """测试Map API调用"""
        config = MapScrapeConfig(search="blog")

        urls = await executor._execute_map("https://example.com", config)

        assert len(urls) > 0
        assert all('url' in link for link in urls)
        assert all('title' in link for link in urls)

    @pytest.mark.asyncio
    async def test_batch_scrape(self, executor):
        """测试批量Scrape"""
        config = MapScrapeConfig(max_concurrent_scrapes=2)
        urls = [
            {"url": "https://example.com/page1"},
            {"url": "https://example.com/page2"}
        ]

        results = await executor._batch_scrape(urls, config)

        assert len(results) == 2
        assert all(r.markdown is not None for r in results)

    def test_filter_by_date(self, executor):
        """测试时间过滤"""
        config = MapScrapeConfig(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31)
        )

        # 创建测试数据
        from src.core.domain.interfaces.crawler_interface import CrawlResult

        results = [
            CrawlResult(
                url="https://example.com/1",
                metadata={"publishedDate": "2025-06-15"}
            ),
            CrawlResult(
                url="https://example.com/2",
                metadata={"publishedDate": "2024-06-15"}  # 超出范围
            ),
        ]

        filtered = executor._filter_by_date(results, config)

        assert len(filtered) == 1
        assert filtered[0].url == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_full_execute(self, executor, test_task):
        """测试完整执行流程"""
        batch = await executor.execute(test_task)

        assert batch.returned_count > 0
        assert batch.credits_used > 0
        assert all(r.source == "map_scrape" for r in batch.results)
```

**运行测试**：
```bash
pytest tests/test_map_scrape_executor.py -v
```

#### 3.2 集成测试

**创建测试脚本**: `scripts/test_map_scrape_integration.py`

```python
#!/usr/bin/env python3
"""Map+Scrape执行器集成测试"""

import asyncio
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/lanxionggao/Documents/guanshanPython')

from src.core.domain.entities.search_task import SearchTask, TaskType
from src.services.firecrawl import ExecutorFactory

async def test_map_scrape():
    """测试Map+Scrape完整流程"""

    # 创建测试任务
    task = SearchTask(
        name="测试Map+Scrape",
        crawl_url="https://news.ycombinator.com",  # Hacker News
        task_type=TaskType.MAP_SCRAPE_WEBSITE,
        crawl_config={
            "search": "show",  # 只要Show HN的帖子
            "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "max_concurrent_scrapes": 5,
            "map_limit": 100
        }
    )

    # 创建执行器
    executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)

    print("=== 开始执行Map+Scrape ===\n")

    # 执行
    batch = await executor.execute(task)

    # 输出结果
    print(f"\n=== 执行结果 ===")
    print(f"发现URL数量: {batch.total_count}")
    print(f"返回结果数量: {batch.returned_count}")
    print(f"积分消耗: {batch.credits_used}")
    print(f"执行时间: {batch.execution_time_ms}ms")

    print(f"\n=== 前5条结果 ===")
    for i, result in enumerate(batch.results[:5], 1):
        print(f"\n[{i}] {result.title}")
        print(f"    URL: {result.url}")
        print(f"    发布时间: {result.published_date}")
        print(f"    内容预览: {result.snippet}")

    return batch

if __name__ == "__main__":
    batch = asyncio.run(test_map_scrape())
    print(f"\n✅ 测试完成！")
```

**运行集成测试**：
```bash
python scripts/test_map_scrape_integration.py
```

---

### Phase 4: 文档更新（第4天）

#### 4.1 更新架构文档

**文件**: `docs/FIRECRAWL_ARCHITECTURE_V2.md`

**新增章节**：

```markdown
### 5. MapScrapeExecutor (Map+Scrape执行器)

**位置**: `src/services/firecrawl/executors/map_scrape_executor.py`

**职责**:
- 使用Map API快速发现URL
- 批量Scrape指定URL
- 按发布时间过滤结果
- 精确控制爬取目标

**工作流程**:

```
┌──────────────────────────────────────────────────────────┐
│  阶段1: Map API - 发现URL                                 │
│  输入: 起始URL, search参数                                │
│  输出: URL列表                                            │
│  时间: ~5秒                                               │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段2: Batch Scrape - 爬取内容                           │
│  输入: URL列表                                             │
│  输出: 页面内容 + metadata                                │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段3: 时间过滤                                           │
│  过滤: 根据publishedDate                                  │
│  输出: 符合条件的结果                                      │
└──────────────────────────────────────────────────────────┘
```

**关键配置**:

```python
MapScrapeConfig(
    search="blog",                    # 搜索关键词
    map_limit=5000,                   # Map返回限制
    start_date=datetime(2025, 1, 1),  # 开始日期
    end_date=datetime(2025, 12, 31),  # 结束日期
    max_concurrent_scrapes=5,         # 并发数
)
```

**适用场景**:
- 只需要特定时间范围的内容
- 需要精确控制爬取目标
- 关注API积分成本
- 定期监控网站更新
```

**更新任务类型表格**：

| 任务类型 | 输入 | API使用 | 输出 | 适用场景 |
|---------|------|---------|------|----------|
| **SEARCH_KEYWORD** | 关键词 | Search + Scrape | 搜索结果 + 详情 | 行业资讯 |
| **CRAWL_WEBSITE** | 起始URL | Crawl | 整站内容 | 完整归档 |
| **SCRAPE_URL** | 单个URL | Scrape | 单页内容 | 页面监控 |
| **MAP_SCRAPE_WEBSITE** | 起始URL + 时间 | Map + Scrape | 过滤后内容 | 精确爬取 |

#### 4.2 创建使用示例

**文件**: `docs/MAP_SCRAPE_USAGE_EXAMPLES.md`

```markdown
# Map+Scrape 使用示例

## 示例1: 爬取最近30天的博客文章

```python
from datetime import datetime, timedelta
from src.core.domain.entities.search_task import SearchTask, TaskType

# 创建任务
task = SearchTask(
    name="技术博客最近文章",
    crawl_url="https://example.com/blog",
    task_type=TaskType.MAP_SCRAPE_WEBSITE,
    crawl_config={
        "search": "python",  # 只要包含python的文章
        "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
        "end_date": datetime.now().isoformat(),
        "max_concurrent_scrapes": 5
    }
)

# 执行
executor = ExecutorFactory.create(TaskType.MAP_SCRAPE_WEBSITE)
batch = await executor.execute(task)

print(f"获取 {batch.returned_count} 篇最近文章")
print(f"消耗 {batch.credits_used} 积分")
```

## 示例2: 只爬取特定分类的页面

```python
task = SearchTask(
    name="产品文档爬取",
    crawl_url="https://docs.example.com",
    task_type=TaskType.MAP_SCRAPE_WEBSITE,
    crawl_config={
        "search": "/api/",  # 只要API文档
        "map_limit": 1000,
        "max_concurrent_scrapes": 10
    }
)
```
```

---

## 📊 实施检查清单

### ✅ 代码实现

- [ ] FirecrawlAdapter.map()方法
- [ ] MapScrapeConfig配置类
- [ ] MapScrapeExecutor执行器
- [ ] TaskType.MAP_SCRAPE_WEBSITE枚举
- [ ] ExecutorFactory注册
- [ ] 积分计算器更新

### ✅ 测试验证

- [ ] 单元测试（test_map_scrape_executor.py）
- [ ] 集成测试（test_map_scrape_integration.py）
- [ ] Map API测试
- [ ] 时间过滤测试
- [ ] 并发Scrape测试
- [ ] 真实场景验证

### ✅ 文档完善

- [x] MAP_SCRAPE_EXECUTOR_DESIGN.md（详细设计）
- [x] FIRECRAWL_MAP_API_GUIDE.md（API指南）
- [x] MAP_SCRAPE_IMPLEMENTATION_PLAN.md（本文档）
- [ ] FIRECRAWL_ARCHITECTURE_V2.md（架构更新）
- [ ] MAP_SCRAPE_USAGE_EXAMPLES.md（使用示例）

### ✅ 部署准备

- [ ] 代码审查
- [ ] 性能测试
- [ ] 错误处理验证
- [ ] 日志完善
- [ ] 监控配置

---

## 📈 预期成果

### 功能验收标准

1. ✅ Map API正常调用并返回URL列表
2. ✅ Batch Scrape成功爬取所有URL
3. ✅ 时间过滤正确筛选结果
4. ✅ 数据库字段完全兼容
5. ✅ 积分消耗计算准确
6. ✅ 错误处理健壮

### 性能指标

- **Map API响应**: <5秒
- **Scrape并发**: 5个/次
- **成功率**: >80%
- **积分节省**: 80-90%（vs Crawl API）

### 文档完整性

- [x] 设计文档完整
- [x] API指南清晰
- [x] 使用示例丰富
- [ ] 架构文档更新
- [ ] 故障排查指南

---

## 🚀 下一步行动

### 立即执行

1. **实现Map API调用**
   ```bash
   # 编辑 firecrawl_adapter.py
   # 实现 map() 方法
   # 运行测试: python scripts/test_map_api.py
   ```

2. **创建配置类**
   ```bash
   # 创建 map_scrape_config.py
   # 定义 MapScrapeConfig
   ```

3. **实现执行器**
   ```bash
   # 创建 map_scrape_executor.py
   # 实现核心逻辑
   ```

### 后续计划

- **Week 1**: 核心功能实现 + 单元测试
- **Week 2**: 集成测试 + 文档完善
- **Week 3**: 真实场景验证 + 性能优化
- **Week 4**: 代码审查 + 生产部署

---

**文档维护者**: Development Team
**最后更新**: 2025-11-06
**实施状态**: 设计完成，待开发
