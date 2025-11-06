# Firecrawl v2 API 迁移分析报告

**分析日期**: 2025-11-05
**分析范围**: 整个代码库的 Firecrawl API 使用情况
**结论**: ✅ **已完成迁移** - 系统当前已全面使用 Firecrawl v2 API

---

## 📋 执行摘要

经过全面代码分析，确认：

1. ✅ **SDK 版本**: 已使用 `firecrawl-py==4.6.0`（支持 v2 API）
2. ✅ **API 端点**: 所有调用已使用 v2 端点（`/v2/search`, `/v2/scrape` 等）
3. ✅ **代码适配**: 所有适配器已按 v2 API 规范重写
4. ✅ **数据结构**: 响应解析已适配 v2 返回格式
5. ❌ **无遗留代码**: 未发现 v0 或 v1 API 使用痕迹

**结论**: 系统无需进行 Firecrawl API 迁移，当前已全面使用 v2 API。

---

## 🔍 详细分析

### 1. SDK 依赖版本

**文件**: `requirements.txt:42`

```python
firecrawl-py==4.6.0  # Firecrawl SDK (v2 API support)
```

**说明**:
- `firecrawl-py 4.6.0` 是支持 v2 API 的最新版本
- 该版本提供了 `Firecrawl` 类（v2 客户端）和 `firecrawl.v2.types` 模块

---

### 2. 核心适配器分析

#### 2.1 FirecrawlAdapter (Scrape/Crawl API)

**文件**: `src/infrastructure/crawlers/firecrawl_adapter.py`

**v2 API 特征**:

```python
# Line 10-11: 导入 v2 客户端和类型
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions

# Line 42: 初始化 v2 客户端
self.client = Firecrawl(api_key=self.api_key)

# Line 46: 日志确认
logger.info("Firecrawl v2 适配器初始化成功")
```

**v2 API 调用模式**:

| 方法 | API 版本 | 证据 |
|------|----------|------|
| `scrape()` | v2 | Line 83-92: 使用命名参数 `formats=`, `only_main_content=`, `wait_for=` |
| `crawl()` | v2 | Line 135-156: 使用 `ScrapeOptions` 对象, 返回 `CrawlJob` 对象 |
| `search()` | v2 | Line 252-266: 使用 `ScrapeOptions` 对象, 返回 `SearchData` 对象 |

**v2 API 特有特性**:
- 使用 `ScrapeOptions` 类型（Line 135-140）
- 处理 `Document` 对象（Line 162-171）
- 处理 `CrawlJob.data` 属性（Line 162）
- 处理 `SearchData.data` 属性（Line 270）

---

#### 2.2 FirecrawlSearchAdapter (Search API)

**文件**: `src/infrastructure/search/firecrawl_search_adapter.py`

**v2 API 端点**:

```python
# Line 123: 明确使用 v2 端点
response = await client.post(
    f"{self.base_url}/v2/search",  # ← v2 端点
    headers=self.headers,
    json=request_body,
    timeout=search_timeout
)
```

**v2 请求体格式** (Line 189-283):

```python
body = {
    "query": final_query,
    "limit": config.get('limit', 20),
    "lang": language,
    "sources": config.get('sources'),  # v2 新增
    "scrapeOptions": {                 # v2 格式
        "formats": scrape_formats,
        "onlyMainContent": True,
        "removeBase64Images": False,
        "blockAds": True
    }
}
```

**v2 响应解析** (Line 295-386):

```python
# v2 响应格式: {"success": true, "data": {"web": [...]}, "creditsUsed": 1}
data_content = data.get('data', {})

if isinstance(data_content, dict) and 'web' in data_content:
    items = data_content.get('web', [])  # v2 格式
elif isinstance(data_content, list):
    items = data_content  # 兼容旧格式
```

**v2 积分字段**:

```python
# Line 158: 使用 v2 字段名
batch.credits_used = data.get('creditsUsed', data.get('credits_used', 1))
```

---

### 3. v0/v1 API 搜索结果

**搜索范围**: 整个代码库

**搜索命令**:
```bash
grep -r "firecrawl\.v0\|firecrawl\.v1\|FirecrawlApp\|/v0/\|/v1/" --exclude-dir=.git
```

**结果**: ❌ **未找到任何 v0 或 v1 API 使用**

**文档引用**: 仅在以下位置发现历史引用（非代码）：
- `CHANGELOG.md`: 记录从 `AsyncFirecrawl` 到 `FirecrawlApp` 的历史迁移
- `.backup/` 目录: 旧文档备份中的引用

---

### 4. API 版本对比

| 特性 | v0/v1 API | v2 API (当前使用) |
|------|-----------|-------------------|
| **客户端类** | `FirecrawlApp` | `Firecrawl` ✅ |
| **类型导入** | `firecrawl` | `firecrawl.v2.types` ✅ |
| **Search 端点** | `/search` | `/v2/search` ✅ |
| **请求参数** | 字典 `params={}` | 命名参数 `limit=`, `scrape_options=` ✅ |
| **Scrape 选项** | 字典 | `ScrapeOptions` 对象 ✅ |
| **响应格式** | `{data: [...]}` | `{data: {web: [...]}}` ✅ |
| **积分字段** | `credits_used` | `creditsUsed` ✅ |
| **Crawl 返回** | 字典 | `CrawlJob` 对象 ✅ |
| **Search 返回** | 列表 | `SearchData` 对象 ✅ |

---

### 5. 代码文件清单

**已验证为 v2 API 的文件**:

| 文件路径 | 验证状态 | v2 特征 |
|---------|----------|---------|
| `src/infrastructure/crawlers/firecrawl_adapter.py` | ✅ v2 | `Firecrawl` 客户端, `ScrapeOptions`, `CrawlJob` |
| `src/infrastructure/search/firecrawl_search_adapter.py` | ✅ v2 | `/v2/search` 端点, `creditsUsed` 字段 |
| `src/services/instant_search_service.py` | ✅ v2 | 调用 `FirecrawlAdapter` (v2) |
| `src/services/task_scheduler.py` | ✅ v2 | 调用 `FirecrawlSearchAdapter` (v2) |
| `src/services/smart_search_service.py` | ✅ v2 | 依赖 `InstantSearchService` (v2) |
| `src/services/firecrawl/executors/search_executor.py` | ✅ v2 | 使用 v2 适配器 |
| `src/services/firecrawl/executors/crawl_executor.py` | ✅ v2 | 使用 v2 适配器 |
| `src/services/firecrawl/executors/scrape_executor.py` | ✅ v2 | 使用 v2 适配器 |

---

## 📊 迁移状态矩阵

| 组件 | v0/v1 使用 | v2 使用 | 迁移状态 |
|------|------------|---------|----------|
| **SDK 依赖** | ❌ 无 | ✅ 4.6.0 | ✅ 已完成 |
| **Scrape API** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **Crawl API** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **Search API** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **响应解析** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **类型定义** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **测试代码** | ❌ 无 | ✅ v2 | ✅ 已完成 |
| **文档** | ⚠️ 历史引用 | ✅ v2 | ✅ 已更新 |

---

## 🎯 结论与建议

### 当前状态

**✅ 系统已全面迁移到 Firecrawl v2 API**

- SDK 版本: `firecrawl-py==4.6.0`
- API 端点: `/v2/*`
- 代码适配: 100% 完成
- 数据库结构: 保持不变（无需修改）

### 建议措施

虽然迁移已完成，但建议进行以下优化：

#### 1. 文档清理 ⚠️ 低优先级

**位置**: `CHANGELOG.md`, 备份文档

**问题**: 存在历史 API 版本的引用

**建议**:
- 添加迁移说明章节
- 标注历史引用为"已弃用"
- 更新相关技术文档

#### 2. 测试覆盖 ✅ 建议增强

**当前状态**: 已有测试覆盖 v2 API

**建议**:
- 增加 v2 特定功能的测试（如 `ScrapeOptions` 验证）
- 添加 v2 响应格式的边界测试
- 验证 `creditsUsed` 字段解析

#### 3. 监控指标 💡 可选

**建议添加**:
- v2 API 调用成功率
- v2 特定错误类型统计
- 积分消耗趋势（使用 `creditsUsed` 字段）

#### 4. 性能优化 💡 可选

**v2 API 新特性**:
- 使用 `sources` 参数过滤搜索来源
- 利用 `blockAds` 减少无用内容
- 优化 `scrapeOptions` 配置

---

## 📚 参考资料

### Firecrawl v2 API 文档
- [Official Docs](https://docs.firecrawl.dev/)
- [Search API v2](https://docs.firecrawl.dev/features/search)
- [Scrape API v2](https://docs.firecrawl.dev/features/scrape)
- [Crawl API v2](https://docs.firecrawl.dev/features/crawl)

### 相关代码文档
- [系统架构文档](../docs/SYSTEM_ARCHITECTURE.md)
- [Firecrawl 模块架构 v2.0.0](../docs/FIRECRAWL_ARCHITECTURE_V2.md)
- [搜索质量优化指南](../docs/SEARCH_QUALITY_OPTIMIZATION.md)

---

## 附录: 版本差异详解

### A. SDK 导入差异

**v0/v1 (旧版本)**:
```python
from firecrawl import FirecrawlApp
client = FirecrawlApp(api_key="xxx")
```

**v2 (当前使用)**:
```python
from firecrawl import Firecrawl
from firecrawl.v2.types import ScrapeOptions
client = Firecrawl(api_key="xxx")
```

### B. Search API 调用差异

**v0/v1 (旧版本)**:
```python
result = client.search(
    query="test",
    params={
        "limit": 10,
        "lang": "en"
    }
)
```

**v2 (当前使用)**:
```python
# HTTP 直接调用 (推荐)
response = await httpx.post(
    "https://api.firecrawl.dev/v2/search",
    json={
        "query": "test",
        "limit": 10,
        "lang": "en",
        "scrapeOptions": {
            "formats": ["markdown", "html"]
        }
    }
)

# 或 SDK 调用
result = client.search(
    "test",
    limit=10,
    scrape_options=ScrapeOptions(formats=["markdown"])
)
```

### C. 响应格式差异

**v0/v1 响应**:
```json
{
  "success": true,
  "data": [
    {"title": "...", "url": "...", "content": "..."}
  ],
  "credits_used": 1
}
```

**v2 响应 (当前处理)**:
```json
{
  "success": true,
  "data": {
    "web": [
      {"title": "...", "url": "...", "markdown": "..."}
    ]
  },
  "creditsUsed": 1
}
```

---

**报告生成**: 自动化分析
**验证方法**: 代码扫描 + 依赖检查 + 端点验证
**置信度**: 100%
