# Chat 端点架构改进方案

## 当前问题诊断

### 现状分析

**当前 `/chat` 端点实现**（`src/api/v1/endpoints/chat.py:104-308`）：

```
用户请求
  ↓
nl_search_service.create_search()  # 完成 sonar-pro + firecrawl + 入库
  ↓
查询 news_results 表补充完整内容
  ↓
返回给前端
```

**缺失的关键步骤**：
- ❌ 没有调用远程 AI 服务 `http://192.168.0.5:8035/chat`
- ❌ 没有利用 AI 服务的处理结果

### 正确的业务流程

```
1. 用户自然语言搜索
   ↓
2. 调用 sonar-pro 接口返回 URL
   ↓
3. 筛选 URL（去重、黑名单过滤）
   ↓
4. 调用 Firecrawl 抓取内容入库（news_results）
   ↓
5. 调用 http://192.168.0.5:8035/chat 进行 AI 处理  # ❌ 缺失
   ↓
6. AI 服务返回结果（包含 answer_chunk + sources + mongo_id）
   ↓
7. 使用 mongo_id 从 news_results 查询完整内容  # ✅ 已实现
   ↓
8. 合并数据返回给前端  # ✅ 已实现
```

## 解决方案

### 方案概述

修改 `/chat` 端点，在 `nl_search_service.create_search()` 之后：
1. 调用远程 AI 服务 `http://192.168.0.5:8035/chat`
2. 接收 SSE 流式响应
3. 实时解析响应中的 `sources` 事件
4. 使用 `mongo_id` 查询 `news_results` 表
5. 增强数据后转发给前端

### 核心实现逻辑

```python
async def event_generator():
    # 1. 数据准备（现有逻辑）
    yield status_event("正在分析您的问题...")

    result = await nl_search_service.create_search(
        query_text=request.question,
        user_id=request.user_id,
        search_mode=request.search_mode
    )

    # 2. 调用远程 AI 服务（新增）
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            "http://192.168.0.5:8035/chat",
            json={"question": request.question, ...}
        ) as ai_response:

            # 3. 实时处理 AI 服务的 SSE 流
            async for line in ai_response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                event = json.loads(line[6:])  # 去除 "data: " 前缀

                # 4. 检测 sources 事件，进行数据增强
                if event["type"] == "sources":
                    enhanced_sources = []

                    for source in event["data"]:
                        mongo_id = source["mongo_id"]

                        # 5. 查询 news_results 获取完整数据
                        news_result = await db["news_results"].find_one(
                            {"_id": mongo_id},
                            {
                                "url": 1,
                                "markdown_content": 1,
                                "news_results.title_zh": 1,
                                "news_results.summary_zh": 1,
                                "news_results.content_zh": 1
                            }
                        )

                        # 6. 合并数据
                        enhanced_source = {
                            **source,  # AI 服务返回的基础字段
                            "url": news_result.get("url"),
                            "markdown_content": news_result.get("markdown_content"),
                            "title_zh": news_result.get("news_results", {}).get("title_zh"),
                            "summary_zh": news_result.get("news_results", {}).get("summary_zh"),
                            "content_zh": news_result.get("news_results", {}).get("content_zh")
                        }
                        enhanced_sources.append(enhanced_source)

                    # 7. 返回增强后的 sources 事件
                    yield sse_event("sources", enhanced_sources)

                else:
                    # 其他事件（answer_chunk, stream_end）直接转发
                    yield line
```

## 关键优势

### 1. 利用 AI 服务能力
- ✅ 使用 AI 服务的答案生成能力（answer_chunk）
- ✅ 利用 AI 服务对搜索结果的相关性排序
- ✅ 保留 AI 服务的实时流式响应体验

### 2. 数据完整性
- ✅ 通过 mongo_id 获取完整的 URL 和内容
- ✅ 补充 AI 翻译后的中文字段（title_zh, summary_zh, content_zh）
- ✅ 提供完整的 markdown_content 用于前端渲染

### 3. 架构合理性
- ✅ 数据准备层（本地服务）
- ✅ AI 处理层（远程 AI 服务）
- ✅ 数据增强层（本地服务）
- ✅ 前端展示层

## 技术实现细节

### 依赖添加

```python
import httpx  # 用于 HTTP 客户端调用
```

### 配置管理

```python
# 添加到配置文件或环境变量
REMOTE_AI_SERVICE_URL = "http://192.168.0.5:8035/chat"
REMOTE_AI_SERVICE_TIMEOUT = 120.0  # 秒
```

### 错误处理

```python
try:
    async with client.stream(...) as ai_response:
        if ai_response.status_code != 200:
            # 回退策略：使用本地直接返回
            yield fallback_response()
            return

        # 正常流程
        async for line in ai_response.aiter_lines():
            ...

except httpx.RequestError as e:
    # AI 服务不可用，使用本地数据
    logger.warning(f"远程 AI 服务不可用: {e}")
    yield fallback_response()
```

## 数据流示例

### AI 服务返回格式

```json
data: {"type": "answer_chunk", "data": "抱歉，"}
data: {"type": "answer_chunk", "data": "无法提"}
data: {"type": "sources", "data": [
  {
    "id": "95f00ff1-751c-4542-a673-ec3ac8a68ccd",
    "mongo_id": "252303599785443332",
    "title": "妙瓦底镇_百度百科",
    "source": "baike.baidu.com",
    "category": {"大类": "安全情报", "类别": "反恐", "地域": "东南亚"},
    "score": 0.0036,
    "publish_time": "未知时间",
    "preview": "4月，克伦边防军脱离政府军..."
  }
]}
data: {"type": "stream_end", "data": {"status": "success_from_cache"}}
```

### 增强后返回格式

```json
data: {"type": "answer_chunk", "data": "抱歉，"}
data: {"type": "answer_chunk", "data": "无法提"}
data: {"type": "sources", "data": [
  {
    "id": "95f00ff1-751c-4542-a673-ec3ac8a68ccd",
    "mongo_id": "252303599785443332",
    "title": "妙瓦底镇_百度百科",
    "source": "baike.baidu.com",
    "category": {"大类": "安全情报", "类别": "反恐", "地域": "东南亚"},
    "score": 0.0036,
    "publish_time": "未知时间",
    "preview": "4月，克伦边防军脱离政府军...",
    "url": "https://baike.baidu.com/item/妙瓦底镇/61895621",
    "markdown_content": "# 妙瓦底镇\\n\\n妙瓦底镇是缅甸...",
    "title_zh": "妙瓦底镇概况",
    "summary_zh": "妙瓦底镇位于缅甸克伦邦...",
    "content_zh": "妙瓦底镇详细介绍..."
  }
]}
data: {"type": "stream_end", "data": {"status": "success_from_cache"}}
```

## 实施步骤

### 步骤 1：备份现有代码
```bash
cp src/api/v1/endpoints/chat.py src/api/v1/endpoints/chat.py.backup.$(date +%Y%m%d_%H%M%S)
```

### 步骤 2：安装依赖
```bash
pip install httpx==0.27.0
```

### 步骤 3：修改代码
- 在 `event_generator()` 中添加远程 AI 服务调用逻辑
- 实现 SSE 流解析和数据增强
- 添加错误处理和回退策略

### 步骤 4：测试验证
```bash
# 测试本地端点
curl -N -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "请介绍关于西藏的新闻"}'

# 验证数据完整性
./scripts/verify_remote_service.sh http://localhost:8000/api/v1/chat
```

### 步骤 5：性能优化
- 添加 AI 服务调用超时控制
- 实现连接池复用
- 添加缓存机制（可选）

## 风险评估

### 高风险
- ❌ AI 服务不可用 → 需要实现回退策略

### 中风险
- ⚠️ SSE 流解析失败 → 添加异常处理
- ⚠️ MongoDB 查询延迟 → 考虑批量查询优化

### 低风险
- ✅ 数据格式不兼容 → 已有格式验证

## 监控指标

- AI 服务响应时间
- MongoDB 查询时间
- 端到端响应时间
- 错误率和回退率
- 数据完整性（字段缺失率）

## 回滚策略

如果新实现出现问题：
```bash
cp src/api/v1/endpoints/chat.py.backup.YYYYMMDD_HHMMSS src/api/v1/endpoints/chat.py
./start_server.sh
```

---

**总结**：该方案通过在现有实现中**插入** AI 服务调用层，实现了完整的业务流程，同时保留了现有的 news_results 数据增强逻辑。
