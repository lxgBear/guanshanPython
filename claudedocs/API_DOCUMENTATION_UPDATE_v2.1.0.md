# API 文档更新记录 v2.1.0

**更新日期**: 2025-11-06
**文档**: `docs/API_USAGE_GUIDE_V2.md`
**版本**: v2.0.0 → v2.1.0

---

## 📝 更新内容

### 1. 新增任务类型

在 TaskType 枚举表格中添加了第4种任务类型：

| 类型值 | 显示名称 | 说明 |
|--------|---------|------|
| `map_scrape_website` | Map + Scrape 智能爬取 | 先发现URL结构，再选择性爬取内容（支持时间过滤） |

### 2. 更新任务类型对比表

扩展对比表，添加 MAP_SCRAPE_WEBSITE 列：

| 特性 | 新增内容 |
|------|---------|
| **输入** | 起始URL |
| **输出** | 筛选后的内容 |
| **API** | Map + Scrape |
| **数据量** | 可控（10-100页） |
| **速度** | 快-中等 |
| **成本效率** | **极高（按需爬取）** ⭐ |
| **适用场景** | 增量更新、时间范围爬取 |

### 3. 新增完整使用示例

添加 "示例 4: 创建 Map + Scrape 智能爬取任务"：

```json
{
  "name": "近期新闻爬取",
  "task_type": "map_scrape_website",
  "crawl_url": "https://example.com/news",
  "crawl_config": {
    "search": "news",
    "map_limit": 100,
    "start_date": "2025-01-07T00:00:00Z",
    "end_date": "2025-02-06T00:00:00Z",
    "max_concurrent_scrapes": 5,
    "scrape_delay": 0.5,
    "wait_for": 3000,
    "timeout": 90,
    "allow_partial_failure": true,
    "min_success_rate": 0.8
  }
}
```

**亮点**: 包含完整的成本对比示例（节省 79% 积分）

### 4. 新增配置参数文档

添加 `MapScrapeConfig (map_scrape_website)` 完整配置说明：

**核心字段**:
- `search`: URL/标题搜索关键词
- `map_limit`: Map API 返回数量限制（最大 5000）
- `start_date` / `end_date`: 时间范围过滤（ISO 格式）
- `max_concurrent_scrapes`: 最大并发数（默认 5）
- `scrape_delay`: 请求间隔秒数（默认 0.5）
- `wait_for`: 页面加载等待时间（默认 3000ms）
- `allow_partial_failure`: 部分失败容忍（默认 true）
- `min_success_rate`: 最低成功率（默认 0.8）

**配置说明**包含：
1. 核心优势 - 时间过滤
2. URL 过滤
3. 并发控制
4. 容错机制
5. 使用场景建议

### 5. 更新最佳实践

**任务类型选择部分**:
- 新增 "Map + Scrape 智能爬取" 推荐场景
- 标注 🆕 和 ✅/❌ 适用/不适用场景

**配置优化部分**:
- 添加 "Map + Scrape 优化" 配置示例
- 新增 "成本优化决策树"，帮助用户选择最优任务类型

### 6. 更新版本历史

添加 v2.1.0 版本记录：

```markdown
#### v2.1.0 (当前版本) - 2025-11-06

- 🆕 **新增任务类型**: `map_scrape_website` (Map + Scrape 智能爬取)
- 🆕 **新增配置**: `MapScrapeConfig` 支持时间范围过滤
- 🆕 **成本优化**: 相比传统 Crawl 节省 58-84% 积分
- 🆕 **智能过滤**: 支持按 `publishedDate` 时间范围筛选
- 🆕 **并发控制**: 可配置并发数和请求延迟
- ✅ 向后兼容 v2.0.0
```

### 7. 更新文档标题和概述

- 文档标题: `v2.0.0` → `v2.1.0`
- 添加 "v2.1.0 最新更新" 章节，突出新功能
- 更新文档版本号和最后更新日期

---

## 🎯 关键信息点

### 成本优势（核心卖点）
- 相比 Crawl API 节省 **58-84%** 积分
- 时间过滤比例越高，节省越多
- 示例：100 个 URL 过滤后爬取 20 个 = 节省 79 积分（79%）

### 适用场景
✅ **推荐使用**:
- 增量更新（只爬取最近 N 天）
- 定期爬取新增内容
- 成本敏感场景
- URL 结构清晰的网站

❌ **不推荐使用**:
- 首次全量爬取
- 网站无发布日期信息

### 技术特点
1. **URL 发现 + 内容获取分离**: Map API (1 积分) + Scrape API (N 积分)
2. **时间过滤**: 按 `publishedDate` 筛选
3. **并发控制**: 可配置并发数和延迟
4. **容错机制**: 部分失败容忍

---

## 📊 文档变更统计

| 变更类型 | 数量 | 说明 |
|---------|-----|------|
| 新增章节 | 3 | TaskType 枚举项、配置说明、使用示例 |
| 更新表格 | 2 | 任务类型对比表、最佳实践 |
| 新增代码示例 | 2 | 完整请求示例、配置示例 |
| 更新版本信息 | 1 | v2.1.0 版本记录 |

---

## ✅ 验证清单

- [x] TaskType 枚举表添加 map_scrape_website
- [x] 任务类型对比表扩展
- [x] 完整使用示例（示例 4）
- [x] MapScrapeConfig 配置文档
- [x] 最佳实践更新
- [x] 成本优化决策树
- [x] 版本变更记录
- [x] 文档标题和版本号更新

---

## 📚 相关文档

- 实现文档: `claudedocs/MAP_SCRAPE_IMPLEMENTATION_SUMMARY.md`
- 实现计划: `docs/MAP_SCRAPE_IMPLEMENTATION_PLAN.md`
- Map API 指南: `docs/FIRECRAWL_MAP_API_GUIDE.md`

---

**文档维护者**: Development Team
**审核状态**: ✅ 已完成
**生效日期**: 2025-11-06
