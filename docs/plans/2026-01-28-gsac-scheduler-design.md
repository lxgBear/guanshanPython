# gsac-scheduler 设计文档

> 将 gs-ai-crawl (gsac) 迁移为定时搜索专用版本
>
> 创建日期: 2026-01-28
> 状态: 待实施

---

## 1. 项目背景

### 1.1 当前架构

系统中存在两个独立的搜索引擎:

| 引擎 | 位置 | 用途 | 特点 |
|------|------|------|------|
| **Firecrawl 执行器** | `src/services/firecrawl/executors/` | 定时搜索任务 | 简单关键词搜索 + 详情页爬取 |
| **gsac** | `src/gsac/` | 聊天/即时搜索 | LangGraph AI 智能搜索 |

### 1.2 gsac 核心能力

```
parse_intent → generate_keywords → execute_search → merge_deduplicate 
→ scrape → validate_relevance → classify_sources
```

- **AI 关键词生成**: LLM 根据意图生成分层关键词 (Layer 0-5)
- **AI 结果验证**: LLM 验证搜索结果的相关性
- **AI 来源分类**: LLM 对结果进行分类和可信度评分

### 1.3 目标

让定时搜索获得 gsac 的完整智能搜索能力。

---

## 2. 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 获得的能力 | 完整 gsac 能力 | 统一搜索质量 |
| 用户交互 | **完全移除** | 定时任务是后台执行，无法交互 |
| 代码组织 | 复制到 `src/gsac_scheduler/` | 独立演进，不影响原有功能 |
| 迁移策略 | **渐进迁移** | 先并存测试，稳定后再替换 |

---

## 3. 架构设计

### 3.1 目录结构

```
src/gsac_scheduler/
├── __init__.py              # 公开 API: run_scheduled_search()
├── agent/
│   ├── __init__.py
│   ├── graph.py             # LangGraph 定义 (简化版，无交互)
│   └── nodes.py             # 节点实现 (移除交互逻辑)
├── config/
│   ├── __init__.py
│   └── settings.py          # 配置管理
├── llm/
│   ├── __init__.py
│   ├── provider.py          # LLM 提供者
│   └── prompts.py           # Prompt 模板
├── models/
│   ├── __init__.py
│   ├── schemas.py           # 数据模型
│   └── state.py             # LangGraph 状态 (简化版)
├── processors/
│   ├── __init__.py
│   ├── cleaner.py           # 内容清洗
│   ├── deduplicator.py      # 去重处理
│   └── formatter.py         # 格式化输出
├── tools/
│   ├── __init__.py
│   ├── client.py            # Firecrawl 客户端
│   ├── scrape.py            # 抓取工具
│   └── search.py            # 搜索工具
└── utils/
    ├── __init__.py
    ├── errors.py            # 错误定义
    └── logging.py           # 日志工具
```

### 3.2 简化的工作流

原 gsac 工作流:
```
START → parse_intent → generate_keywords → [fan_out_search]
    → execute_single_search → merge_deduplicate
    → [route_by_source_count] → expand_search / scrape
    → validate_relevance → classify_sources → END
```

gsac_scheduler 工作流 (移除交互):
```
START → parse_intent → generate_keywords → [fan_out_search]
    → execute_single_search → merge_deduplicate
    → [route_by_source_count] → expand_search / scrape
    → validate_relevance → classify_sources → END
```

**关键变更**: 状态初始化时强制 `skip_element_clarification=True`

### 3.3 状态定义简化

移除以下交互相关字段:

```python
# 移除
clarification_needed: bool
clarification_questions: list[str] | None
missing_elements: MissingElements | None

# 保留但始终设为 True
skip_element_clarification: bool = True

# 保留但改为从任务配置读取
user_provided_elements: UserProvidedElements | None
```

---

## 4. 集成设计

### 4.1 新增任务类型

```python
# src/core/domain/entities/search_task.py
class TaskType(str, Enum):
    SEARCH_KEYWORD = "search_keyword"      # 现有: 简单关键词搜索
    SEARCH_MULTILANG = "search_multilang"  # 现有: 多语言搜索
    SEARCH_GSAC = "search_gsac"            # 新增: AI 智能搜索
    CRAWL_WEBSITE = "crawl_website"
    SCRAPE_URL = "scrape_url"
```

### 4.2 新增执行器

```python
# src/services/firecrawl/executors/gsac_search_executor.py

from src.gsac_scheduler import run_scheduled_search

class GsacSearchExecutor(TaskExecutor):
    """AI 智能搜索执行器"""
    
    async def execute(self, task: SearchTask) -> SearchResultBatch:
        # 1. 从任务配置提取要素
        elements = self._extract_elements(task)
        
        # 2. 调用 gsac_scheduler
        result = await run_scheduled_search(
            query=task.query,
            user_provided_elements=elements,
            config=self._build_config(task)
        )
        
        # 3. 转换为 SearchResultBatch
        return self._convert_to_batch(result, task)
```

### 4.3 注册到工厂

```python
# src/services/firecrawl/factory.py

class ExecutorFactory:
    _executor_map: dict[TaskType, type[TaskExecutor]] = {
        TaskType.SEARCH_KEYWORD: SearchExecutor,
        TaskType.SEARCH_MULTILANG: MultilangSearchExecutor,
        TaskType.SEARCH_GSAC: GsacSearchExecutor,  # 新增
        TaskType.CRAWL_WEBSITE: CrawlExecutor,
        TaskType.SCRAPE_URL: ScrapeExecutor,
    }
```

---

## 5. 实施计划

### 第一阶段: 代码迁移 (本次)

- [x] 设计文档
- [ ] 复制 `src/gsac/` → `src/gsac_scheduler/`
- [ ] 移除交互相关代码
- [ ] 修改状态初始化逻辑
- [ ] 添加 `run_scheduled_search()` API
- [ ] 基础测试

### 第二阶段: 集成 (后续)

- [ ] 新增 `TaskType.SEARCH_GSAC`
- [ ] 创建 `GsacSearchExecutor`
- [ ] 注册到 `ExecutorFactory`
- [ ] 扩展任务配置字段 (可选)
- [ ] 集成测试

### 第三阶段: 验证与切换 (后续)

- [ ] 生产环境测试
- [ ] 性能对比
- [ ] 渐进切换现有任务
- [ ] 移除旧执行器 (可选)

---

## 6. 需要移除/修改的代码

### 6.1 需要移除的代码

| 文件 | 移除内容 |
|------|----------|
| `models/state.py` | `MissingElements` 类型 (可选保留) |
| `models/state.py` | `clarification_needed`, `clarification_questions`, `missing_elements` 字段 |
| `agent/nodes.py` | 任何 clarification 相关逻辑 (如有) |

### 6.2 需要修改的代码

| 文件 | 修改内容 |
|------|----------|
| `__init__.py` | 新增 `run_scheduled_search()` 函数 |
| `agent/graph.py` | `create_osint_initial_state()` 强制设置 `skip_element_clarification=True` |
| `models/state.py` | 简化 `OSINTSearchState` 定义 |

---

## 7. 公开 API 设计

```python
# src/gsac_scheduler/__init__.py

async def run_scheduled_search(
    query: str,
    *,
    user_provided_elements: dict | None = None,
    max_keywords: int = 5,
    max_results_per_keyword: int = 10,
    enable_deep_scrape: bool = False,
    max_scrape_urls: int = 3,
    similarity_threshold: float = 0.8,
) -> ScheduledSearchResult:
    """
    执行定时搜索任务 (无交互版本)
    
    Args:
        query: 搜索查询
        user_provided_elements: 预配置的搜索要素
            - time_range: 时间范围
            - location: 地点
            - entity_name: 实体名称
            - source_type: 来源类型
        max_keywords: 最大关键词数
        max_results_per_keyword: 每关键词最大结果数
        enable_deep_scrape: 是否深度抓取
        max_scrape_urls: 深度抓取 URL 数
        similarity_threshold: 去重阈值
        
    Returns:
        ScheduledSearchResult: 搜索结果
    """
    ...
```

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM 调用成本增加 | 中 | 可配置关闭某些 AI 功能 |
| 执行时间变长 | 中 | 并行优化，可配置超时 |
| 代码重复 | 低 | 后续可抽取公共模块 |

---

*文档作者: Claude Code*
*最后更新: 2026-01-28*
