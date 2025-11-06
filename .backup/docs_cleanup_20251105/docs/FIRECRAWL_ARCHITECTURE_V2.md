# Firecrawl 模块化架构文档 v2.0.0

## 📋 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [核心组件](#核心组件)
4. [任务类型](#任务类型)
5. [使用指南](#使用指南)
6. [配置说明](#配置说明)
7. [扩展开发](#扩展开发)
8. [迁移指南](#迁移指南)

---

## 概述

### 设计目标

Firecrawl v2.0.0 采用模块化架构重构，实现以下目标：

- ✅ **职责分离**：每个执行器专注于单一任务类型
- ✅ **高可维护性**：清晰的代码组织和依赖关系
- ✅ **易扩展性**：通过工厂模式轻松添加新执行器
- ✅ **类型安全**：配置类和接口提供类型检查
- ✅ **标准化**：统一的执行流程和错误处理

### 核心改进

| 方面 | v1.x (旧版本) | v2.0.0 (新版本) |
|------|---------------|-----------------|
| **代码组织** | 集中在 TaskScheduler | 模块化分离 |
| **任务类型** | 隐式判断 (crawl_url vs query) | 显式枚举 (TaskType) |
| **执行器** | 内联方法 | 独立执行器类 |
| **配置管理** | 字典配置 | 类型安全的配置类 |
| **扩展性** | 修改核心代码 | 注册新执行器 |
| **可测试性** | 难以单元测试 | 每个执行器独立测试 |

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      TaskScheduler                          │
│  (调度器 - 负责任务调度和生命周期管理)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ 委托执行
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   ExecutorFactory                           │
│  (工厂 - 根据任务类型创建对应执行器)                        │
└─────────────┬───────────────┬───────────────┬───────────────┘
              │               │               │
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │   Search    │  │    Crawl    │  │   Scrape    │
    │  Executor   │  │  Executor   │  │  Executor   │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                │                │
           │ 使用           │ 使用           │ 使用
           ▼                ▼                ▼
    ┌─────────────────────────────────────────────┐
    │          Firecrawl Adapters                 │
    │  - FirecrawlSearchAdapter (Search API)      │
    │  - FirecrawlAdapter (Scrape/Crawl API)      │
    └─────────────────────────────────────────────┘
```

### 设计模式

#### 1. 策略模式 (Strategy Pattern)

不同的执行器实现相同的接口，提供不同的执行策略：

```python
class TaskExecutor(ABC):
    @abstractmethod
    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行任务的策略方法"""
        pass
```

#### 2. 工厂模式 (Factory Pattern)

根据任务类型动态创建执行器实例：

```python
executor = ExecutorFactory.create(task_type)
result = await executor.execute(task)
```

#### 3. 模板方法模式 (Template Method Pattern)

基类定义通用的执行流程，子类实现具体细节：

```python
class TaskExecutor(ABC):
    async def execute(self, task: SearchTask):
        # 1. 验证配置
        self.validate_config(task)
        # 2. 执行任务（子类实现）
        # 3. 记录日志
        # 4. 返回结果
```

#### 4. 适配器模式 (Adapter Pattern)

封装 Firecrawl API 调用，提供统一接口：

```python
class FirecrawlAdapter:
    async def scrape(self, url: str, **options) -> CrawlResult:
        """适配 Firecrawl Scrape API"""
        pass

    async def crawl(self, url: str, **options) -> List[CrawlResult]:
        """适配 Firecrawl Crawl API"""
        pass
```

---

## 核心组件

### 1. TaskExecutor (基类)

**位置**: `src/services/firecrawl/base.py`

**职责**:
- 定义执行器接口
- 提供通用辅助方法
- 统一异常处理

**关键方法**:

```python
class TaskExecutor(ABC):
    @abstractmethod
    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行任务并返回结果批次"""
        pass

    @abstractmethod
    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置"""
        pass

    def _create_result_batch(self, task: SearchTask, query: str) -> SearchResultBatch:
        """创建结果批次对象"""
        pass
```

### 2. SearchExecutor (关键词搜索执行器)

**位置**: `src/services/firecrawl/executors/search_executor.py`

**职责**:
- 执行关键词搜索 (Search API)
- 批量爬取详情页 (Scrape API)
- 并发控制和错误处理

**工作流程**:

```
┌──────────────────────────────────────────────────────────┐
│  阶段1: Search API                                        │
│  - 输入: 关键词 (query)                                   │
│  - 输出: 搜索结果列表 (标题、URL、摘要)                  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────┐
│  阶段2: Scrape API (批量并发)                             │
│  - 输入: 搜索结果中的 URL 列表                            │
│  - 输出: 每个 URL 的完整内容 (正文、Markdown、HTML)      │
│  - 特性:                                                  │
│    • 并发控制 (Semaphore)                                │
│    • 部分失败容忍                                         │
│    • 可配置延迟                                           │
└──────────────────────────────────────────────────────────┘
```

**关键配置**:

```python
SearchConfig(
    limit=10,                     # 搜索结果数量
    language="zh",                # 搜索语言
    enable_detail_scrape=True,    # 是否启用详情页爬取
    max_concurrent_scrapes=3,     # 最大并发数
    scrape_delay=1.0              # 爬取间隔（秒）
)
```

### 3. CrawlExecutor (网站爬取执行器)

**位置**: `src/services/firecrawl/executors/crawl_executor.py`

**职责**:
- 递归爬取整个网站 (Crawl API)
- 深度控制和路径过滤
- 大量页面处理

**工作流程**:

```
┌──────────────────────────────────────────────────────────┐
│  Crawl API (异步递归爬取)                                 │
│  - 输入: 起始 URL                                         │
│  - 递归爬取所有子页面                                     │
│  - 应用路径过滤和深度限制                                 │
│  - 输出: 所有页面的完整内容                               │
└──────────────────────────────────────────────────────────┘
```

**关键配置**:

```python
CrawlConfig(
    limit=100,                    # 最大页面数
    max_depth=3,                  # 最大爬取深度
    include_paths=["/blog/*"],    # 包含的路径模式
    exclude_paths=["/admin/*"],   # 排除的路径模式
    allow_backward_links=False    # 是否允许向后链接
)
```

### 4. ScrapeExecutor (单页面爬取执行器)

**位置**: `src/services/firecrawl/executors/scrape_executor.py`

**职责**:
- 爬取单个页面内容 (Scrape API)
- 适用于定期监控特定页面

**工作流程**:

```
┌──────────────────────────────────────────────────────────┐
│  Scrape API (单页面爬取)                                  │
│  - 输入: 单个 URL                                         │
│  - 输出: 页面完整内容                                     │
│  - 用途: 定期监控特定页面变化                             │
└──────────────────────────────────────────────────────────┘
```

**关键配置**:

```python
ScrapeConfig(
    only_main_content=True,       # 只提取主要内容
    wait_for=1000,                # 等待页面加载时间（毫秒）
    exclude_tags=["nav", "footer"] # 排除的HTML标签
)
```

### 5. ExecutorFactory (执行器工厂)

**位置**: `src/services/firecrawl/factory.py`

**职责**:
- 根据任务类型创建执行器
- 支持自定义执行器注册
- 验证执行器类型

**使用示例**:

```python
# 创建执行器
executor = ExecutorFactory.create(TaskType.SEARCH_KEYWORD)

# 从字符串创建（兼容性）
executor = ExecutorFactory.create_from_string("search_keyword")

# 注册自定义执行器
ExecutorFactory.register_executor(
    task_type=TaskType.CUSTOM,
    executor_class=MyCustomExecutor
)

# 获取支持的类型
supported = ExecutorFactory.get_supported_types()
```

---

## 任务类型

### TaskType 枚举

**位置**: `src/core/domain/entities/search_task.py`

```python
class TaskType(str, Enum):
    SEARCH_KEYWORD = "search_keyword"  # 关键词搜索 + 详情页爬取
    CRAWL_WEBSITE = "crawl_website"    # 网站递归爬取
    SCRAPE_URL = "scrape_url"          # 单页面爬取
```

### 任务类型对比

| 任务类型 | 输入 | API使用 | 输出 | 适用场景 |
|---------|------|---------|------|----------|
| **SEARCH_KEYWORD** | 关键词 | Search + Scrape | 搜索结果 + 详情页 | 行业资讯、竞品分析 |
| **CRAWL_WEBSITE** | 起始URL | Crawl | 整站页面内容 | 网站归档、知识库构建 |
| **SCRAPE_URL** | 单个URL | Scrape | 单页面内容 | 页面监控、数据更新 |

### 任务类型判断逻辑

**SearchTask 实体**提供自动判断方法：

```python
class SearchTask:
    def get_task_type(self) -> TaskType:
        """自动判断任务类型"""
        # 优先级: task_type字段 > crawl_url > query
        if self.task_type:
            return TaskType(self.task_type)
        elif self.crawl_url:
            return TaskType.SCRAPE_URL
        else:
            return TaskType.SEARCH_KEYWORD

    def is_search_keyword_mode(self) -> bool:
        return self.get_task_type() == TaskType.SEARCH_KEYWORD

    def is_crawl_website_mode(self) -> bool:
        return self.get_task_type() == TaskType.CRAWL_WEBSITE

    def is_scrape_url_mode(self) -> bool:
        return self.get_task_type() == TaskType.SCRAPE_URL
```

---

## 使用指南

### 创建搜索任务

#### 1. 关键词搜索任务

```python
from src.core.domain.entities.search_task import SearchTask, TaskType

task = SearchTask(
    name="Python 最新技术动态",
    query="Python 3.12 新特性",
    task_type=TaskType.SEARCH_KEYWORD,  # 明确指定任务类型
    search_config={
        "limit": 10,
        "language": "zh",
        "enable_detail_scrape": True,
        "max_concurrent_scrapes": 3,
        "scrape_delay": 1.0
    }
)
```

#### 2. 网站爬取任务

```python
task = SearchTask(
    name="技术博客归档",
    crawl_url="https://example.com/blog",
    task_type=TaskType.CRAWL_WEBSITE,  # 明确指定任务类型
    crawl_config={
        "limit": 100,
        "max_depth": 3,
        "include_paths": ["/blog/*", "/articles/*"],
        "exclude_paths": ["/admin/*"],
        "only_main_content": True
    }
)
```

#### 3. 单页面爬取任务

```python
task = SearchTask(
    name="首页监控",
    crawl_url="https://example.com",
    task_type=TaskType.SCRAPE_URL,  # 明确指定任务类型
    search_config={  # 注意：ScrapeExecutor 使用 search_config
        "only_main_content": True,
        "wait_for": 2000,
        "exclude_tags": ["nav", "footer", "header"]
    }
)
```

### 手动执行任务

```python
from src.services.firecrawl import ExecutorFactory

# 创建执行器
task_type = task.get_task_type()
executor = ExecutorFactory.create(task_type)

# 执行任务
result_batch = await executor.execute(task)

# 处理结果
for result in result_batch.results:
    print(f"标题: {result.title}")
    print(f"URL: {result.url}")
    print(f"内容: {result.markdown_content[:200]}...")
```

### 通过调度器执行

```python
from src.services.task_scheduler import get_scheduler

# 获取调度器实例
scheduler = await get_scheduler()

# 启动调度器
await scheduler.start()

# 添加任务（会自动根据任务类型执行）
await scheduler.add_task(task)

# 立即执行
await scheduler.execute_task_now(str(task.id))
```

---

## 配置说明

### SearchConfig (关键词搜索配置)

```python
@dataclass
class SearchConfig:
    # 搜索参数
    limit: int = 10                      # 搜索结果数量
    language: str = "zh"                 # 搜索语言
    include_domains: Optional[List[str]] = None  # 限制域名
    strict_language_filter: bool = True  # 严格语言过滤

    # 详情页爬取控制
    enable_detail_scrape: bool = True    # 是否启用详情页爬取
    max_concurrent_scrapes: int = 3      # 最大并发爬取数
    scrape_delay: float = 1.0            # 爬取间隔（秒）

    # Scrape 选项（用于详情页爬取）
    only_main_content: bool = True       # 只提取主要内容
    wait_for: int = 2000                 # 等待时间（毫秒）
    exclude_tags: List[str] = field(     # 排除的HTML标签
        default_factory=lambda: ["nav", "footer", "header", "aside"]
    )
    timeout: int = 90                    # 超时时间（秒）
```

### CrawlConfig (网站爬取配置)

```python
@dataclass
class CrawlConfig:
    # 爬取限制
    limit: int = 100                     # 最大页面数
    max_depth: int = 3                   # 最大爬取深度

    # 路径过滤
    include_paths: List[str] = field(default_factory=list)  # 包含路径
    exclude_paths: List[str] = field(default_factory=list)  # 排除路径
    allow_backward_links: bool = False   # 是否允许向后链接

    # Scrape 选项（用于每个爬取的页面）
    only_main_content: bool = True       # 只提取主要内容
    wait_for: int = 1000                 # 等待时间（毫秒）
    exclude_tags: List[str] = field(     # 排除的HTML标签
        default_factory=lambda: ["nav", "footer", "header"]
    )

    # 超时设置
    timeout: int = 300                   # 整体爬取超时（秒）
    poll_interval: int = 10              # 状态轮询间隔（秒）
```

### ScrapeConfig (单页面爬取配置)

```python
@dataclass
class ScrapeConfig:
    # 内容提取
    only_main_content: bool = True       # 只提取主要内容
    wait_for: int = 1000                 # 等待时间（毫秒）

    # 标签过滤
    include_tags: Optional[List[str]] = None  # 包含的HTML标签
    exclude_tags: List[str] = field(     # 排除的HTML标签
        default_factory=lambda: ["nav", "footer", "header"]
    )

    # 超时设置
    timeout: int = 90                    # 超时时间（秒）
```

### 配置创建方法

```python
from src.services.firecrawl.config import ConfigFactory

# 从字典创建配置
search_config = ConfigFactory.create_search_config({
    "limit": 20,
    "language": "en",
    "enable_detail_scrape": True
})

crawl_config = ConfigFactory.create_crawl_config({
    "limit": 50,
    "max_depth": 2,
    "include_paths": ["/blog/*"]
})

scrape_config = ConfigFactory.create_scrape_config({
    "only_main_content": True,
    "timeout": 60
})
```

---

## 扩展开发

### 添加自定义执行器

#### 1. 创建执行器类

```python
from src.services.firecrawl.base import TaskExecutor, ExecutionError
from src.core.domain.entities.search_result import SearchResultBatch

class MyCustomExecutor(TaskExecutor):
    """自定义执行器"""

    def validate_config(self, task: SearchTask) -> bool:
        """验证任务配置"""
        if not task.custom_field:
            self.logger.error("缺少必要的 custom_field")
            return False
        return True

    async def execute(self, task: SearchTask) -> SearchResultBatch:
        """执行自定义任务"""
        start_time = datetime.utcnow()
        self._log_execution_start(task)

        # 1. 验证配置
        if not self.validate_config(task):
            raise ConfigValidationError(f"配置无效: {task.id}")

        # 2. 执行自定义逻辑
        try:
            # 你的自定义逻辑
            results = await self._my_custom_logic(task)

            # 3. 创建结果批次
            batch = self._create_result_batch(task, query="自定义任务")
            for result in results:
                batch.add_result(result)

            # 4. 记录执行时间
            end_time = datetime.utcnow()
            batch.execution_time_ms = int(
                (end_time - start_time).total_seconds() * 1000
            )

            self._log_execution_end(task, len(results), batch.execution_time_ms)
            return batch

        except Exception as e:
            self.logger.error(f"执行失败: {e}")
            raise ExecutionError(f"自定义任务执行失败: {str(e)}")

    async def _my_custom_logic(self, task: SearchTask):
        """你的自定义逻辑"""
        # 实现你的逻辑
        pass
```

#### 2. 注册执行器

```python
from src.services.firecrawl import ExecutorFactory
from src.core.domain.entities.search_task import TaskType

# 添加新的任务类型（如果需要）
class TaskType(str, Enum):
    SEARCH_KEYWORD = "search_keyword"
    CRAWL_WEBSITE = "crawl_website"
    SCRAPE_URL = "scrape_url"
    CUSTOM = "custom"  # 新增

# 注册执行器
ExecutorFactory.register_executor(
    task_type=TaskType.CUSTOM,
    executor_class=MyCustomExecutor
)
```

#### 3. 使用自定义执行器

```python
# 创建任务
task = SearchTask(
    name="自定义任务",
    task_type=TaskType.CUSTOM,
    custom_field="some_value"
)

# 执行
executor = ExecutorFactory.create(TaskType.CUSTOM)
result = await executor.execute(task)
```

---

## 迁移指南

### 从 v1.x 迁移到 v2.0.0

#### 1. 数据库兼容性

**向后兼容**: v2.0.0 完全兼容现有数据库中的任务数据。

- 旧任务（没有 `task_type` 字段）会自动判断类型：
  - 有 `crawl_url` → `SCRAPE_URL`
  - 有 `query` → `SEARCH_KEYWORD`

- 新任务应明确指定 `task_type` 字段

#### 2. API 端点更新

**添加任务时指定类型**:

```python
# 旧方式（仍然兼容）
task_data = {
    "name": "测试任务",
    "query": "Python",
    "crawl_url": None
}

# 新方式（推荐）
task_data = {
    "name": "测试任务",
    "query": "Python",
    "task_type": "search_keyword"  # 明确指定类型
}
```

#### 3. 配置迁移

**search_config vs crawl_config**:

```python
# 旧方式：所有配置放在 search_config
task = SearchTask(
    crawl_url="https://example.com",
    search_config={
        "only_main_content": True,
        "wait_for": 2000
    }
)

# 新方式：使用专用配置字段
task = SearchTask(
    crawl_url="https://example.com",
    task_type=TaskType.CRAWL_WEBSITE,
    crawl_config={  # 使用 crawl_config
        "limit": 100,
        "max_depth": 3
    }
)
```

#### 4. 代码迁移

**调度器代码无需修改**:

v2.0.0 的 TaskScheduler 已经完全集成新架构，现有代码无需修改即可使用。

```python
# 这段代码在 v1.x 和 v2.0.0 中都能正常工作
scheduler = await get_scheduler()
await scheduler.start()
await scheduler.add_task(task)
```

---

## 最佳实践

### 1. 任务类型选择

- **关键词搜索 (SEARCH_KEYWORD)**: 需要获取多个来源的信息时
- **网站爬取 (CRAWL_WEBSITE)**: 需要归档整个网站时
- **单页面爬取 (SCRAPE_URL)**: 需要监控特定页面变化时

### 2. 配置优化

**关键词搜索优化**:
```python
{
    "enable_detail_scrape": True,   # 启用详情页爬取
    "max_concurrent_scrapes": 3,    # 平衡速度和资源
    "scrape_delay": 1.0,            # 避免请求过快
    "only_main_content": True       # 减少噪音
}
```

**网站爬取优化**:
```python
{
    "limit": 50,                    # 合理的页面限制
    "max_depth": 2,                 # 避免爬取过深
    "exclude_paths": ["/admin/*"],  # 排除不相关路径
    "timeout": 300                  # 足够的超时时间
}
```

### 3. 错误处理

所有执行器都遵循统一的错误处理：

```python
try:
    executor = ExecutorFactory.create(task_type)
    result = await executor.execute(task)
except ConfigValidationError as e:
    # 配置验证失败
    logger.error(f"配置错误: {e}")
except ExecutionError as e:
    # 执行过程错误
    logger.error(f"执行失败: {e}")
except Exception as e:
    # 未预期的错误
    logger.error(f"未知错误: {e}")
```

### 4. 性能监控

```python
# 查看执行器性能
logger.info(f"执行时间: {result_batch.execution_time_ms}ms")
logger.info(f"结果数量: {result_batch.returned_count}")
logger.info(f"积分消耗: {result_batch.credits_used}")
```

---

## 故障排查

### 常见问题

#### 1. 任务类型判断错误

**症状**: 任务使用了错误的执行器

**解决方案**:
```python
# 明确指定 task_type
task.task_type = TaskType.SEARCH_KEYWORD

# 或者使用辅助方法验证
print(f"任务类型: {task.get_task_type()}")
```

#### 2. 详情页爬取失败

**症状**: SearchExecutor 完成搜索但详情页内容为空

**解决方案**:
```python
# 检查配置
config = {
    "enable_detail_scrape": True,     # 确保启用
    "max_concurrent_scrapes": 3,      # 降低并发数
    "scrape_delay": 2.0,              # 增加延迟
    "timeout": 120                    # 增加超时
}
```

#### 3. 网站爬取超时

**症状**: CrawlExecutor 超时失败

**解决方案**:
```python
# 调整配置
config = {
    "limit": 20,          # 减少页面数
    "max_depth": 2,       # 减少深度
    "timeout": 600,       # 增加超时
    "poll_interval": 15   # 增加轮询间隔
}
```

---

## 附录

### 目录结构

```
src/services/firecrawl/
├── __init__.py              # 模块导出
├── base.py                  # TaskExecutor 基类
├── factory.py               # ExecutorFactory 工厂类
├── config/
│   ├── __init__.py
│   └── task_config.py       # 配置类定义
└── executors/
    ├── __init__.py
    ├── search_executor.py   # 关键词搜索执行器
    ├── crawl_executor.py    # 网站爬取执行器
    └── scrape_executor.py   # 单页面爬取执行器
```

### 相关文档

- [Firecrawl API 文档](https://docs.firecrawl.dev/)
- [Firecrawl Crawl API](https://docs.firecrawl.dev/features/crawl)
- [Firecrawl Search API](https://docs.firecrawl.dev/features/search)
- [Firecrawl Scrape API](https://docs.firecrawl.dev/features/scrape)

### 更新日志

#### v2.0.0 (当前版本)

- ✅ 模块化架构重构
- ✅ 新增 TaskType 枚举
- ✅ 实现三种执行器（Search, Crawl, Scrape）
- ✅ 类型安全的配置管理
- ✅ 工厂模式支持扩展
- ✅ 向后兼容 v1.x 数据

#### v1.x (旧版本)

- 集中式调度器实现
- 隐式任务类型判断
- 字典配置管理

---

**文档版本**: v2.0.0
**最后更新**: 2025-01-XX
**维护者**: Development Team
