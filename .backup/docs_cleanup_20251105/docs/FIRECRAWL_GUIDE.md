# Firecrawl API 集成指南

**API版本**: v2 | **官网**: https://firecrawl.dev

---

## 快速开始

### 获取API密钥

1. 注册账号: https://firecrawl.dev/app/sign-up
2. 获取API Key: Dashboard → API Keys
3. 配置环境变量:

```bash
# .env
FIRECRAWL_API_KEY=your_api_key_here
FIRECRAWL_BASE_URL=https://api.firecrawl.dev
```

---

## API功能

### 1. Search API (关键词搜索)

**用途**: 基于关键词搜索网页内容

**请求格式**:
```python
POST https://api.firecrawl.dev/v2/search
{
  "query": "特朗普 贸易战",
  "limit": 10,
  "lang": "zh",
  "tbs": "qdr:m",  # 时间范围: 最近一月
  "scrapeOptions": {
    "formats": ["markdown", "html", "links"],
    "onlyMainContent": true
  }
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "web": [
      {
        "title": "标题",
        "url": "https://...",
        "markdown": "内容...",
        "html": "<html>...",
        "description": "摘要",
        "metadata": {...}
      }
    ]
  },
  "creditsUsed": 1
}
```

### 2. Scrape API (URL爬取)

**用途**: 爬取指定URL的完整内容

**请求格式**:
```python
POST https://api.firecrawl.dev/v2/scrape
{
  "url": "https://example.com/article",
  "formats": ["markdown", "html"],
  "onlyMainContent": true,
  "waitFor": 1000  # 等待时间(ms)
}
```

---

## 系统集成

### 适配器架构

```python
# src/infrastructure/search/firecrawl_search_adapter.py

class FirecrawlSearchAdapter:
    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = settings.FIRECRAWL_BASE_URL

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(480))
    async def search(self, query: str, user_config: UserSearchConfig):
        # 构建请求
        request_body = self._build_request_body(query, config)

        # 调用API
        async with httpx.AsyncClient(proxies={}) as client:
            response = await client.post(
                f"{self.base_url}/v2/search",
                headers=self.headers,
                json=request_body
            )

        # 解析结果
        results = self._parse_search_results(response.json())
        return results
```

### 配置参数

```python
# 搜索配置
search_config = {
    "limit": 10,              # 结果数量(1-100)
    "time_range": "month",    # day/week/month/year
    "language": "zh",         # zh/en/auto
    "include_domains": [],    # 限定域名
    "scrape_formats": ["markdown", "html", "links"],
    "only_main_content": True
}
```

### 时间范围映射

| 配置值 | Firecrawl参数 | 说明 |
|--------|--------------|------|
| `day` | `qdr:d` | 最近24小时 |
| `week` | `qdr:w` | 最近一周 |
| `month` | `qdr:m` | 最近一月 |
| `year` | `qdr:y` | 最近一年 |

---

## 数据处理

### 内容优化

**Markdown截断**:
```python
# 限制最大5000字符
markdown_full = item.get('markdown', '')
if len(markdown_full) > 5000:
    markdown_content = markdown_full[:5000]
else:
    markdown_content = markdown_full
```

**元数据精简**:
```python
# 仅保留有用字段
filtered_metadata = {
    'language': item_metadata.get('language'),
    'og_type': item_metadata.get('og:type'),
}
# 移除None值
filtered_metadata = {k: v for k, v in filtered_metadata.items() if v is not None}
```

### 搜索结果实体

```python
SearchResult(
    task_id=task_id,
    title=title,
    url=url,
    content=content,                      # 主内容
    snippet=description,                  # 摘要
    markdown_content=markdown_content,    # Markdown格式
    html_content=html_content,            # HTML格式
    published_date=published_date,
    language=language,
    relevance_score=score,
    metadata=filtered_metadata
)
```

---

## 故障处理

### 重试机制

```python
@retry(
    stop=stop_after_attempt(3),      # 最多3次
    wait=wait_fixed(480),             # 间隔8分钟
    retry=retry_if_exception_type((
        httpx.ConnectError,           # DNS/网络错误
        httpx.TimeoutException,       # 超时
        httpx.HTTPStatusError         # HTTP错误
    ))
)
```

### 常见错误

**1. 认证失败 (401)**
```json
{
  "error": "Invalid API key"
}
```
**解决**: 检查 `FIRECRAWL_API_KEY` 配置

**2. 配额超限 (429)**
```json
{
  "error": "Rate limit exceeded"
}
```
**解决**: 等待或升级套餐

**3. 请求超时**
```
httpx.TimeoutException
```
**解决**: 增加 `timeout` 配置或启用重试

---

## 最佳实践

### 1. 代理配置

```python
# 禁用代理(直连Firecrawl)
client_config = {
    "proxies": {},  # 空字典禁用代理
    "timeout": 30
}
```

### 2. 域名限定

```python
# 使用site:操作符限定域名
if config.get('include_domains'):
    domains = config['include_domains']
    site_operators = ' OR '.join([f'site:{domain}' for domain in domains])
    final_query = f"({site_operators}) {query}"
```

**示例**:
```python
query = "人工智能"
domains = ["nytimes.com", "reuters.com"]
# 结果: "(site:nytimes.com OR site:reuters.com) 人工智能"
```

### 3. 结果数量控制

| 场景 | 建议值 |
|------|--------|
| 快速扫描 | 10 |
| 常规监控 | 20-30 |
| 深度采集 | 50-100 |

### 4. 成本优化

- 每次Search请求消耗1个credit
- 批量搜索使用并发控制
- 合理设置缓存避免重复请求

---

## 监控指标

### API调用日志

```bash
# 成功调用
✅ 解析得到 10 条搜索结果

# 失败重试
🔄 搜索请求失败，第 1 次重试 (共3次)，将在 8 分钟后重试...

# API响应
📡 API 响应状态码: 200
📦 响应数据结构: ['success', 'data', 'creditsUsed']
```

### 性能指标

- **响应时间**: 通常3-7秒
- **成功率**: >99% (含重试)
- **Credits消耗**: 每次搜索1 credit

---

## 测试模式

### 启用测试模式

```bash
# .env
TEST_MODE=true
```

**行为**:
- 生成10条模拟搜索结果
- 不消耗API credits
- 响应时间<100ms
- 适用于开发和测试

```python
result = SearchResult(
    title=f"测试结果 {i+1}: {query}",
    url=f"https://example.com/test/{i+1}",
    content=f"测试内容...",
    is_test_data=True
)
```

---

## 相关文档

- [API使用指南](API_GUIDE.md)
- [重试机制](RETRY_MECHANISM.md)
- [系统架构](SYSTEM_ARCHITECTURE.md)

**官方文档**: https://docs.firecrawl.dev
**维护者**: Backend Team
