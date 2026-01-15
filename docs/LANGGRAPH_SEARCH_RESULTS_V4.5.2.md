# LangGraph 搜索结果表 (v4.5.2)

## 概述

v4.5.2 新增 `langgraph_search_results` 表，用于存储 LangGraph 智能搜索系统的搜索结果。

与 `search_results` 表的关系：
- **数据隔离**：LangGraph 结果存储在独立集合中，与 NL Search 结果分离
- **字段继承**：继承 `search_results` 的所有基础字段
- **扩展字段**：新增 LangGraph 特定的评分、分类和层级字段

## 表结构

### 集合名称
- MongoDB 集合：`langgraph_search_results`

### 字段定义

#### 基础字段（继承自 SearchResult）

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | str | 主键（雪花ID） |
| `task_id` | str | 关联的任务ID |
| `user_id` | str | 所属用户ID |
| `created_by` | str | 创建者用户ID |
| `title` | str | 结果标题 |
| `url` | str | 结果URL |
| `snippet` | str | 结果摘要 |
| `source` | str | 来源 |
| `markdown_content` | str | Markdown格式内容 |
| `html_content` | str | HTML格式内容 |
| `article_tag` | str | 文章标签 |
| `article_published_time` | str | 文章发布时间 |
| `source_url` | str | 原始URL |
| `http_status_code` | int | HTTP状态码 |
| `search_position` | int | 搜索结果排名 |
| `content_hash` | str | 内容哈希（去重） |
| `relevance_score` | float | 相关性分数 (0.0-1.0) |
| `quality_score` | float | 质量分数 (0.0-1.0) |
| `status` | str | 状态 (pending/archived/deleted) |
| `created_at` | datetime | 创建时间 |
| `processed_at` | datetime | 处理时间 |
| `is_test_data` | bool | 是否为测试数据 |

#### LangGraph 特定字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `layer` | int | 搜索层级 (0-4) |
| `layer_name` | str | 层级名称 |
| `source_tier` | int | 来源可信度等级 (1-6) |
| `credibility_score` | float | 可信度分数 (0.0-1.0) |
| `final_score` | float | 综合分数 |
| `category` | dict | 分类信息 |
| `multi_source_bonus` | float | 多来源加分 |
| `recency_bonus` | float | 时效性加分 |
| `layer_weight` | float | 层级权重 |

### 搜索层级 (layer)

| layer | layer_name | 权重 | 说明 |
|-------|------------|------|------|
| 0 | 官方来源 | 1.0 | 政府网站、官方机构、中央通讯社 |
| 1 | 主流媒体 | 0.9 | 国家级主流媒体、权威新闻机构 |
| 2 | 区域媒体 | 0.8 | 地区性媒体、行业媒体 |
| 3 | 国际媒体 | 0.7 | 国际新闻机构、外国媒体 |
| 4 | 智库机构 | 0.85 | 研究机构、智库、学术组织 |

### 来源可信度 (source_tier)

| tier | 可信度 | 说明 |
|------|--------|------|
| 1 | 最高 | 官方政府、顶级通讯社 |
| 2 | 很高 | 国家级主流媒体 |
| 3 | 高 | 区域性权威媒体 |
| 4 | 中等 | 一般新闻网站 |
| 5 | 较低 | 社交媒体、博客 |
| 6 | 最低 | 未验证来源 |

### 分类信息 (category)

```json
{
  "大类": "政治|经济|社会|科技|文化|体育|军事|其他",
  "类别": "具体分类",
  "地域": "国家/地区"
}
```

## 代码结构

### 实体类

```python
# src/core/domain/entities/langgraph_search_result.py

@dataclass
class LangGraphSearchResult(SearchResult):
    """LangGraph 智能搜索结果实体"""

    # LangGraph 特定字段
    layer: int = 0
    layer_name: str = ""
    source_tier: int = 1
    credibility_score: float = 0.0
    final_score: float = 0.0
    category: Optional[Dict[str, str]] = None
    multi_source_bonus: float = 0.0
    recency_bonus: float = 0.0
    layer_weight: float = 0.0
```

### 仓储类

```python
# src/infrastructure/persistence/repositories/mongo/langgraph_result_repository.py

class MongoLangGraphResultRepository:
    """MongoDB LangGraph 搜索结果 Repository 实现"""

    collection_name = "langgraph_search_results"

    # 主要方法
    async def save_results(results, enable_dedup=True)
    async def find_by_task_id(task_id, limit=None)
    async def find_by_task_and_layer(task_id, layer, limit=None)
    async def get_task_statistics(task_id)
    async def count_by_task_and_layer(task_id)
```

### 服务层集成

```python
# src/services/langgraph_search/service.py

async def _save_results_to_search_results(
    self,
    results: List[Dict[str, Any]],
    user_id: str,
    task_id: Optional[str] = None,
) -> None:
    """保存搜索结果到 langgraph_search_results 表"""
    from src.core.domain.entities.langgraph_search_result import LangGraphSearchResult
    from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
        MongoLangGraphResultRepository
    )

    repo = MongoLangGraphResultRepository()
    # ... 保存逻辑
```

## 数据库索引

### 基础索引
- `task_id` - 任务查询
- `user_id` - 用户隔离查询
- `created_by` - 创建者查询
- `created_at` - 时间排序
- `status` - 状态查询

### LangGraph 特定索引
- `layer` - 层级查询
- `source_tier` - 可信度查询
- `final_score` - 评分排序

### 复合索引
- `task_id + layer` - 按任务和层级查询
- `task_id + final_score` - 按任务和评分排序
- `user_id + created_at` - 用户历史查询

### 去重索引
- `content_hash` - 内容去重
- `task_id + url` - URL去重

## 使用示例

### 保存 LangGraph 搜索结果

```python
from src.core.domain.entities.langgraph_search_result import LangGraphSearchResult
from src.infrastructure.persistence.repositories.mongo.langgraph_result_repository import (
    MongoLangGraphResultRepository
)

# 创建结果实体
result = LangGraphSearchResult(
    task_id="task_123",
    user_id="user_456",
    title="示例新闻",
    url="https://example.com/news",
    snippet="新闻摘要",
    source="example.com",
    layer=0,
    layer_name="官方来源",
    source_tier=1,
    credibility_score=0.95,
    final_score=0.90,
    category={"大类": "政治", "类别": "外交", "地域": "中国"},
)

# 保存到数据库
repo = MongoLangGraphResultRepository()
stats = await repo.save_results([result], enable_dedup=True)
# stats = {"saved": 1, "duplicates": 0, "total": 1}
```

### 按任务和层级查询

```python
# 查询任务的所有结果
results = await repo.find_by_task_id("task_123")

# 查询任务的特定层级结果
layer_0_results = await repo.find_by_task_and_layer("task_123", layer=0)
```

### 获取统计信息

```python
# 获取任务统计
stats = await repo.get_task_statistics("task_123")
# {
#     "total": 50,
#     "by_layer": {0: 5, 1: 15, 2: 10, 3: 12, 4: 8},
#     "avg_scores": {"relevance": 0.75, "credibility": 0.80, "final": 0.78},
#     "top_sources": [{"source": "xinhuanet.com", "count": 10}, ...]
# }
```

## 版本历史

- **v4.5.2** (2026-01-13)
  - 新增 `langgraph_search_results` 表
  - 实现 LangGraph 搜索结果与 NL Search 结果的数据隔离
  - 新增 layer, layer_name, source_tier, credibility_score, final_score, category 等字段
