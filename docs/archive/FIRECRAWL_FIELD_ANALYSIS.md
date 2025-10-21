# Firecrawl API 字段分析与优化方案

**生成日期**: 2025-10-14
**目的**: 分析Firecrawl API返回字段,筛选有效字段存入数据库,优化前端响应数据

---

## 📊 当前问题分析

### 问题描述

1. **存储问题**: `raw_data`字段存储所有Firecrawl原始响应,包含大量冗余数据
2. **传输问题**: 前端API返回所有字段,包括巨大的HTML/Markdown内容和链接数组
3. **性能问题**: 单条结果可达850KB+,严重影响API响应速度和数据库性能

### 实际字段大小

从数据库检查结果显示:

| 字段 | 类型 | 大小 | 说明 |
|------|------|------|------|
| `url` | string | ~66字符 | ✅ 必需 |
| `title` | string | ~18字符 | ✅ 必需 |
| `description` | string | ~67字符 | ✅ 必需(摘要) |
| `position` | integer | 4字节 | ⚠️ 可选(搜索排名) |
| `markdown` | string | **274,638字符** | ❌ 过大(274KB) |
| `html` | string | **577,597字符** | ❌ 过大(577KB) |
| `links` | array | **数百个URL** | ❌ 冗余(几十KB) |
| `metadata` | object | ~2-5KB | ⚠️ 部分有用 |

**总计**: 单条结果原始数据 ~850KB+

---

## 🔍 Firecrawl API v2 字段完整清单

### 1. 核心字段 (必需保留)

| 字段名 | 类型 | 描述 | 用途 | 优先级 |
|--------|------|------|------|--------|
| `url` | string | 网页URL地址 | 唯一标识,跳转链接 | 🔴 必需 |
| `title` | string | 网页标题 | 显示标题,搜索结果 | 🔴 必需 |
| `description` | string | 网页描述/摘要 | 搜索结果预览 | 🔴 必需 |

**存储策略**: 全部保留,映射到SearchResult核心字段

---

### 2. 内容字段 (需优化处理)

| 字段名 | 类型 | 大小 | 当前使用 | 优化建议 |
|--------|------|------|----------|----------|
| `markdown` | string | 274KB | ✅ 存储 | ⚠️ **截断前5000字符** |
| `html` | string | 577KB | ✅ 存储 | ❌ **不存储** |
| `content` | string | 0-10KB | ❌ 不存在 | N/A |

**问题分析**:
- Firecrawl /search API 返回完整网页的markdown和html
- markdown平均274KB,html更大(577KB)
- 前端只需要预览内容(前200-500字符),不需要完整内容

**优化策略**:
```python
# 截断markdown内容
markdown_content = item.get('markdown', '')
if len(markdown_content) > 5000:
    markdown_content = markdown_content[:5000] + '...'

# HTML不存储(可通过URL按需爬取)
html_content = None  # 不存储html字段
```

**预期效果**: 内容字段从851KB降至~5KB (-99.4%)

---

### 3. 元数据字段 (metadata对象)

#### 3.1 有用字段 (保留)

| 字段名 | 类型 | 描述 | 用途 |
|--------|------|------|------|
| `metadata.language` | string | 语言代码(zh, en) | 语言过滤 |
| `metadata.title` | string | OpenGraph标题 | 备用标题 |
| `metadata.og:type` | string | 内容类型 | 内容分类 |
| `metadata.statusCode` | integer | HTTP状态码 | 爬取状态 |
| `metadata.sourceURL` | string | 原始URL | 重定向跟踪 |
| `metadata.article:tag` | string | 文章标签 | 内容分类 |
| `metadata.article:published_time` | string | 发布时间 | 时间过滤 |

**存储策略**: 提取到独立字段或过滤后的metadata字段

#### 3.2 冗余字段 (可删除)

| 字段名 | 说明 | 删除原因 |
|--------|------|----------|
| `metadata.favicon` | 网站图标URL | 前端不需要 |
| `metadata.og:image` | OpenGraph图片 | 前端可选择性加载 |
| `metadata.og:image:width` | 图片宽度 | 不需要 |
| `metadata.og:image:height` | 图片高度 | 不需要 |
| `metadata.viewport` | 视口设置 | 技术细节,无用 |
| `metadata.generator` | 生成器(MediaWiki) | 技术细节,无用 |
| `metadata.scrapeId` | Firecrawl内部ID | 内部标识,无用 |
| `metadata.proxyUsed` | 使用的代理 | 技术细节,无用 |
| `metadata.cacheState` | 缓存状态 | 技术细节,无用 |
| `metadata.cachedAt` | 缓存时间 | 技术细节,无用 |
| `metadata.referrer` | 引用策略 | 技术细节,无用 |

**优化策略**:
```python
# 只保留有用的metadata字段
useful_metadata = {
    'language': metadata.get('language'),
    'og_type': metadata.get('og:type'),
    'status_code': metadata.get('statusCode'),
    'source_url': metadata.get('sourceURL'),
}
```

**预期效果**: metadata从2-5KB降至~200字节 (-96%)

---

### 4. 链接字段 (links数组)

**当前状态**:
- 字段名: `links`
- 类型: `array[string]`
- 大小: 数百个URL,总计几十KB
- 内容示例: 维基百科页面所有内部/外部链接

**问题分析**:
- 包含页面所有链接(导航、脚注、相关链接等)
- 前端基本不使用此字段
- 占用大量存储和传输带宽

**优化策略**:
```python
# 方案1: 完全不存储 (推荐)
links = None

# 方案2: 只保留前10个链接 (如需要)
links = item.get('links', [])[:10]

# 方案3: 完全删除raw_data中的links
if 'links' in raw_data:
    del raw_data['links']
```

**推荐**: **完全不存储** - 前端无使用场景

**预期效果**: 节省几十KB存储 (-100%)

---

### 5. 技术字段 (可选)

| 字段名 | 类型 | 描述 | 建议 |
|--------|------|------|------|
| `position` | integer | 搜索结果排名 | ⚠️ 可保留(用于排序) |
| `score` | float | 相关性评分 | ✅ 保留(映射到relevance_score) |

**存储策略**: 映射到SearchResult的独立字段

---

## ✅ 优化方案

### 方案A: 激进优化 (推荐)

**目标**: 最小化存储,只保留前端必需字段

```python
# 1. 核心字段 - 直接映射
title = item.get('title', '')
url = item.get('url', '')
snippet = item.get('description', '')

# 2. 内容字段 - 截断markdown,不存储html
markdown_full = item.get('markdown', '')
markdown_content = markdown_full[:5000] if len(markdown_full) > 5000 else markdown_full
html_content = None  # 不存储

# 3. 元数据 - 只保留有用字段
metadata = item.get('metadata', {})
filtered_metadata = {
    'language': metadata.get('language'),
    'status_code': metadata.get('statusCode'),
    'source_url': metadata.get('sourceURL'),
}

# 4. 文章字段 - 提取到独立字段
article_tag = metadata.get('article:tag')
article_published_time = metadata.get('article:published_time')

# 5. 链接字段 - 不存储
# links字段完全删除

# 6. raw_data - 不存储或存储最小化版本
raw_data = {}  # 完全不存储
# 或
raw_data = {
    'url': url,
    'title': title,
    'description': snippet,
    'position': item.get('position'),
}  # 只存储核心字段

# 7. 相关性评分
relevance_score = item.get('score', 0.0)
```

**预期效果**:
- 存储大小: 850KB → **~8KB** (-99.1%)
- API响应: 850KB → **~5KB** (-99.4%)
- 数据库查询速度: **提升50-80%**
- 前端加载速度: **提升80-95%**

---

### 方案B: 保守优化

**目标**: 平衡存储与功能需求

```python
# 保留完整raw_data,但删除巨大字段
raw_data = item.copy()

# 删除巨大字段
if 'html' in raw_data:
    del raw_data['html']  # -577KB

if 'markdown' in raw_data:
    # 截断markdown
    if len(raw_data['markdown']) > 10000:
        raw_data['markdown'] = raw_data['markdown'][:10000] + '...'

if 'links' in raw_data:
    # 只保留前20个链接
    raw_data['links'] = raw_data['links'][:20]

# 清理metadata冗余字段
if 'metadata' in raw_data:
    meta = raw_data['metadata']
    # 删除冗余字段
    for key in ['favicon', 'og:image:width', 'og:image:height',
                'viewport', 'generator', 'scrapeId', 'proxyUsed',
                'cacheState', 'cachedAt', 'referrer']:
        if key in meta:
            del meta[key]
```

**预期效果**:
- 存储大小: 850KB → **~30KB** (-96.5%)
- API响应: 需进一步优化前端响应模型
- 数据库查询速度: **提升30-50%**

---

## 🎯 推荐实施方案

### 阶段1: SearchResult模型优化

**目标**: 优化实体模型,移除或优化raw_data字段

```python
@dataclass
class SearchResult:
    """搜索结果实体 - 优化版"""
    # ... 现有字段保持不变 ...

    # ❌ 删除或重构raw_data字段
    # raw_data: Dict[str, Any] = field(default_factory=dict)

    # ✅ 添加精简的原始数据字段(可选)
    source_metadata: Dict[str, Any] = field(default_factory=dict)  # 只存储有用元数据

    # ✅ 优化内容字段
    markdown_content: Optional[str] = None  # 限制最大5000字符
    html_content: Optional[str] = None  # 不再存储

    # ✅ 提取的关键字段
    article_tag: Optional[str] = None
    article_published_time: Optional[str] = None
    source_url: Optional[str] = None  # 原始URL(重定向场景)
    http_status_code: Optional[int] = None  # HTTP状态码
```

---

### 阶段2: Firecrawl适配器优化

**文件**: `src/infrastructure/search/firecrawl_search_adapter.py`

```python
def _parse_search_results(self, data: Dict[str, Any], task_id: Optional[str]) -> List[SearchResult]:
    """解析搜索结果 - 优化版"""

    # ... 现有解析逻辑 ...

    for item in items:
        # 1. 核心字段提取
        title = item.get('title', '')
        url = item.get('url', '')
        description = item.get('description', item.get('snippet', ''))

        # 2. 内容字段优化
        markdown_full = item.get('markdown', '')
        markdown_content = markdown_full[:5000] if len(markdown_full) > 5000 else markdown_full

        # 3. 元数据提取
        item_metadata = item.get('metadata', {})

        # 4. 构建精简的source_metadata
        source_metadata = {
            'language': item_metadata.get('language'),
            'status_code': item_metadata.get('statusCode'),
            'source_url': item_metadata.get('sourceURL'),
            'position': item.get('position'),
        }

        # 5. 提取文章字段
        article_tag = item_metadata.get('article:tag')
        article_published_time = item_metadata.get('article:published_time')

        # 6. 创建SearchResult - 不使用raw_data
        result = SearchResult(
            task_id=task_id,
            title=title,
            url=url,
            content=markdown_content,  # 使用截断的markdown作为content
            snippet=description,
            source='web',
            language=item_metadata.get('language'),
            markdown_content=markdown_content,  # 截断版本
            html_content=None,  # 不存储HTML
            article_tag=article_tag,
            article_published_time=article_published_time,
            source_url=item_metadata.get('sourceURL'),
            http_status_code=item_metadata.get('statusCode'),
            source_metadata=source_metadata,  # 精简版元数据
            relevance_score=item.get('score', 0.0),
            status=ResultStatus.PENDING
        )

        results.append(result)

    return results
```

---

### 阶段3: 前端API响应优化

**文件**: `src/api/v1/endpoints/search_results_frontend.py`

#### 3.1 创建精简响应模型

```python
class SearchResultSummaryResponse(BaseModel):
    """搜索结果摘要响应 - 用于列表展示"""
    id: str
    task_id: str
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float
    published_date: Optional[datetime] = None
    language: Optional[str] = None
    created_at: datetime
    is_test_data: bool
    # 不包含: raw_data, markdown_content, html_content, links

class SearchResultDetailResponse(BaseModel):
    """搜索结果详情响应 - 用于单个结果查看"""
    id: str
    task_id: str
    title: str
    url: str
    content: str  # 截断的markdown内容
    snippet: str
    source: str
    published_date: Optional[datetime] = None
    author: Optional[str] = None
    language: Optional[str] = None
    article_tag: Optional[str] = None
    article_published_time: Optional[str] = None
    source_url: Optional[str] = None
    relevance_score: float
    quality_score: float
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    is_test_data: bool
    # 仅包含必要的元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

#### 3.2 修改API端点返回模型

```python
# 列表API - 使用精简响应
@router.get(
    "/{task_id}/results",
    response_model=SearchResultListResponse,  # 内部items改为SearchResultSummaryResponse
)
async def get_task_results(...):
    # 返回精简版结果
    return SearchResultListResponse(
        items=[result_to_summary_response(r) for r in page_results],
        # ...
    )

# 详情API - 使用完整响应(但不包含raw_data)
@router.get(
    "/{task_id}/results/{result_id}",
    response_model=SearchResultDetailResponse,
)
async def get_search_result_detail(...):
    # 返回详情,但不包含raw_data
    return result_to_detail_response(result)
```

---

## 📈 预期优化效果对比

| 指标 | 优化前 | 方案A(激进) | 方案B(保守) |
|------|--------|-------------|-------------|
| **单条结果存储大小** | ~850KB | ~8KB | ~30KB |
| **列表API响应(20条)** | ~17MB | ~100KB | ~600KB |
| **详情API响应** | ~850KB | ~5KB | ~30KB |
| **数据库查询速度** | 基准 | +70% | +40% |
| **前端加载速度** | 基准 | +90% | +60% |
| **存储成本(10万条)** | ~85GB | ~800MB | ~3GB |
| **功能完整性** | 100% | 95% | 98% |

---

## ⚠️ 注意事项与风险

### 风险1: 内容截断可能影响内容分析

**问题**: 截断markdown到5000字符可能丢失重要内容

**缓解方案**:
1. 如需完整内容,通过URL使用Firecrawl /scrape API按需获取
2. 对于重要结果,标记并保留完整内容
3. 提供"查看完整内容"功能,按需加载

### 风险2: 删除HTML字段可能影响特定用例

**问题**: 某些场景可能需要HTML进行特定解析

**缓解方案**:
1. 正常情况下markdown已足够
2. 如确实需要HTML,通过URL重新爬取
3. 评估是否需要提供HTML访问接口

### 风险3: 删除links数组可能影响链接分析功能

**问题**: 如果未来需要分析页面链接关系

**缓解方案**:
1. 当前前端无此需求
2. 未来如需要,可实现专门的链接分析服务
3. 或在特定任务中选择性保留links

---

## 🚀 实施计划

### Step 1: 备份与测试 (1天)

- [ ] 备份当前数据库
- [ ] 创建测试环境
- [ ] 运行现有测试确保baseline

### Step 2: 模型优化 (1-2天)

- [ ] 修改SearchResult实体模型
- [ ] 更新数据库repository
- [ ] 添加数据迁移脚本(处理现有数据)

### Step 3: 适配器优化 (1天)

- [ ] 修改Firecrawl适配器解析逻辑
- [ ] 实现字段过滤和截断
- [ ] 添加单元测试

### Step 4: API响应优化 (1天)

- [ ] 创建精简响应模型
- [ ] 修改API端点
- [ ] 更新API文档

### Step 5: 测试与验证 (1-2天)

- [ ] 功能测试
- [ ] 性能测试(响应时间、数据库负载)
- [ ] 前端集成测试
- [ ] 数据完整性验证

### Step 6: 生产部署 (半天)

- [ ] 数据迁移
- [ ] 灰度发布
- [ ] 监控关键指标
- [ ] 回滚方案准备

**预计总时间**: 5-7个工作日

---

## 📚 相关文档

- [Firecrawl API文档](https://docs.firecrawl.dev/api-reference)
- [FIRECRAWL_GUIDE.md](./FIRECRAWL_GUIDE.md) - Firecrawl集成指南
- [API_FIELD_REFERENCE.md](./API_FIELD_REFERENCE.md) - API字段参考
- [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) - 系统架构文档

---

**文档版本**: 1.0
**最后更新**: 2025-10-14
**维护人员**: Backend Team
