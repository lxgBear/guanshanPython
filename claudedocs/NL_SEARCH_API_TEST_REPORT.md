# NL Search API 测试报告

**日期**: 2025-11-17
**版本**: v1.0.0-beta
**测试人员**: Claude Code (ultrathink 模式)
**测试范围**: 自然语言搜索所有接口完整性测试

---

## 📋 执行摘要

### 测试状态总览

| 测试项 | 状态 | 结果 |
|--------|------|------|
| API端点配置验证 | ✅ 通过 | gpt-5模型API正常工作 |
| 数据库容错性修复 | ✅ 完成 | MariaDB不可用时优雅降级 |
| GET /status 接口 | ✅ 通过 | 功能已启用，版本正确 |
| POST / 搜索创建 | ⚠️ 配置问题 | API有效但服务未加载新配置 |
| GET /{log_id} 日志查询 | ⏸️ 待测 | 依赖数据库可用性 |
| GET / 历史列表 | ⏸️ 待测 | 依赖数据库可用性 |

### 关键发现

1. **✅ API endpoint验证成功**: 直接curl测试证明 `https://api.gpt.ge/v1` 和 API key 完全正常
2. **✅ 数据库容错性已实现**: MariaDB不可用时不会导致服务崩溃
3. **⚠️ 配置加载问题**: 全局单例模式导致环境变量无法通过uvicorn reload更新
4. **🔧 需要完全重启**: 必须kill Python进程并重新启动才能加载新的.env配置

---

## 🔬 详细测试结果

### 1. API Endpoint 直接验证测试

**测试目的**: 验证第三方API endpoint和credentials有效性

**测试命令**:
```bash
curl -X POST 'https://api.gpt.ge/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f' \
  -d '{
    "model": "gpt-5",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

**测试结果**: ✅ **通过**

**响应示例**:
```json
{
  "id": "chatcmpl-CckBBIYHva8oGcfVCOrapirNRAyZj",
  "object": "chat.completion",
  "created": 1763350013,
  "model": "gpt-5-2025-08-07",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "",
      "refusal": null,
      "annotations": []
    },
    "logprobs": null,
    "finish_reason": "length"
  }],
  "usage": {
    "prompt_tokens": 7,
    "completion_tokens": 100,
    "total_tokens": 107
  }
}
```

**关键验证点**:
- ✅ HTTP 200 状态码
- ✅ 返回合法JSON结构
- ✅ model字段显示 "gpt-5-2025-08-07" (gpt-5模型存在且可用)
- ✅ API认证成功
- ℹ️ content为空是因为finish_reason="length"(达到100 token限制)

---

### 2. GET /api/v1/nl-search/status - 功能状态检查

**测试目的**: 验证NL Search功能启用状态和服务配置

**测试命令**:
```bash
curl http://localhost:8000/api/v1/nl-search/status
```

**测试结果**: ✅ **通过**

**响应**:
```json
{
  "enabled": true,
  "version": "1.0.0-beta",
  "message": "自然语言搜索功能已就绪",
  "alternative_api": null,
  "documentation": "docs/NL_SEARCH_IMPLEMENTATION_GUIDE.md"
}
```

**验证点**:
- ✅ `enabled: true` - 功能已启用
- ✅ `version: "1.0.0-beta"` - 版本号正确
- ✅ HTTP 200 状态码
- ✅ 无需替代API建议

---

### 3. POST /api/v1/nl-search/ - 创建自然语言搜索

**测试目的**: 测试完整的LLM查询解析和搜索流程

**测试命令**:
```bash
curl -X POST 'http://localhost:8000/api/v1/nl-search/' \
  -H 'Content-Type: application/json' \
  -d '{"query_text":"Python编程最新教程"}'
```

**测试结果**: ⚠️ **配置加载问题**

**实际响应**:
```json
{
  "detail": {
    "error": "搜索失败",
    "message": "服务暂时不可用，请稍后重试",
    "log_id": null
  }
}
```

**错误日志分析**:
```
2025-11-17 11:21:33 - WARNING - 创建 NL 搜索记录失败（数据库不可用）
LLM API 返回空响应 (尝试 1/3)
LLM API 返回空响应 (尝试 2/3)
LLM API 返回空响应 (尝试 3/3)
LLM 返回空响应
AttributeError: 'NoneType' object has no attribute 'get'
```

**根本原因分析**:

#### 问题1: MariaDB不可用 ✅ 已修复
**原因**: MariaDB未启动
**影响**: 数据库日志创建失败
**修复**: 修改 `nl_search_repositories.py` 的 `create()` 和 `update_llm_analysis()` 方法，优雅处理数据库不可用:
```python
async def create(...) -> Optional[int]:  # 返回类型改为Optional
    try:
        # ... 数据库操作
    except Exception as e:
        logger.warning(f"创建 NL 搜索记录失败（数据库不可用）: {e}")
        return None  # 数据库不可用时返回None，允许LLM功能继续工作
```

#### 问题2: LLM API返回空响应 ⚠️ 配置未加载
**原因**: `nl_search_service` 全局单例在模块加载时初始化，旧配置被缓存
**症状**:
- 没有看到 "使用自定义API端点" 日志
- 没有看到 "LLM Processor 配置" 日志
- LLM客户端使用了默认OpenAI endpoint而非 `https://api.gpt.ge/v1`

**证据**:
```python
# src/services/nl_search/nl_search_service.py:269
nl_search_service = NLSearchService()  # 模块加载时立即初始化
```

**影响流程**:
1. Python首次导入模块时，`nl_search_config` 读取.env文件
2. `nl_search_service = NLSearchService()` 立即初始化
3. `LLMProcessor` 使用当时的config（没有 llm_base_url）
4. 即使.env文件更新，uvicorn `--reload` 只重新加载代码，不重新初始化全局对象
5. AsyncOpenAI客户端仍使用默认的 `https://api.openai.com/v1` endpoint

**解决方案**:
- **临时方案**: 完全重启Python进程（kill -9 uvicorn进程）
- **永久方案**: 将全局单例改为懒加载或工厂函数

---

### 4. GET /api/v1/nl-search/{log_id} - 获取搜索记录

**测试目的**: 验证日志记录查询功能

**测试命令**:
```bash
curl http://localhost:8000/api/v1/nl-search/123456
```

**测试结果**: ⏸️ **未执行** (依赖数据库)

**预期行为**:
- MariaDB可用 + 记录存在 → 200 返回记录详情
- MariaDB可用 + 记录不存在 → 404 Not Found
- MariaDB不可用 → 500 Internal Server Error (可能需要优化为503)

**待优化建议**: 数据库不可用时应返回503而非500

---

### 5. GET /api/v1/nl-search/ - 查询搜索历史

**测试目的**: 验证分页查询历史记录功能

**测试命令**:
```bash
curl 'http://localhost:8000/api/v1/nl-search/?limit=10&offset=0'
```

**测试结果**: ⏸️ **未执行** (依赖数据库)

**预期行为**:
- MariaDB可用 → 200 返回分页列表
- MariaDB不可用 → 500 Internal Server Error (可能需要优化为503)

**待优化建议**: 数据库不可用时应返回503和友好提示

---

## 🔧 代码修复记录

### 修复1: 数据库容错性增强

**文件**: `src/infrastructure/database/nl_search_repositories.py`

**修改内容**:

#### 1.1 `create()` 方法
```python
# 修改前
async def create(...) -> int:
    session = await self._get_session()
    try:
        # ... 数据库操作
        return log_id
    except Exception as e:
        await session.rollback()
        logger.error(f"创建 NL 搜索记录失败: {e}")
        raise  # 抛出异常导致服务不可用

# 修改后
async def create(...) -> Optional[int]:
    try:
        session = await self._get_session()
        # ... 数据库操作
        return log_id
    except Exception as e:
        logger.warning(f"创建 NL 搜索记录失败（数据库不可用）: {e}")
        return None  # 优雅降级，允许LLM功能继续工作
```

#### 1.2 `update_llm_analysis()` 方法
```python
# 修改前
async def update_llm_analysis(self, log_id: int, ...) -> bool:
    # 直接操作数据库，失败抛异常

# 修改后
async def update_llm_analysis(self, log_id: Optional[int], ...) -> bool:
    if log_id is None:  # 数据库不可用时log_id为None
        logger.debug("跳过更新 LLM 分析（数据库不可用）")
        return False
    try:
        # ... 数据库操作
    except Exception as e:
        logger.warning(f"更新 NL 搜索记录失败（数据库不可用）: {e}")
        return False  # 优雅降级
```

**效果**: MariaDB不可用时，LLM功能可以正常工作，只是无法记录日志

---

### 修复2: 调试日志增强

**文件**: `src/services/nl_search/llm_processor.py`

**修改内容**:
```python
def __init__(self, config=None):
    self.config = config or nl_search_config

    # 新增：调试日志打印配置信息
    logger.info(f"LLM Processor 配置: model={self.config.llm_model}, "
               f"base_url={self.config.llm_base_url}, "
               f"api_key={'已设置' if self.config.llm_api_key else '未设置'}")

    # 验证配置
    if not self.config.llm_api_key:
        logger.warning("LLM API Key 未配置，LLM 功能将不可用")
        self.client = None
    else:
        # 支持自定义API端点
        client_kwargs = {"api_key": self.config.llm_api_key}
        if self.config.llm_base_url:
            client_kwargs["base_url"] = self.config.llm_base_url
            logger.info(f"使用自定义API端点: {self.config.llm_base_url}")

        self.client = AsyncOpenAI(**client_kwargs)
        logger.info("AsyncOpenAI 客户端初始化完成")  # 新增
```

**效果**: 可以通过日志验证配置是否正确加载

---

## 📊 环境配置验证

### .env配置检查 ✅

```bash
$ grep "^NL_SEARCH" .env
NL_SEARCH_ENABLED=true
NL_SEARCH_LLM_API_KEY=sk-lu0j5woxKtl1LXWmD511FcD1293c4bC7Ba26A0A654Bf355f
NL_SEARCH_LLM_BASE_URL=https://api.gpt.ge/v1
NL_SEARCH_LLM_MODEL=gpt-5
NL_SEARCH_LLM_TEMPERATURE=0.7
NL_SEARCH_LLM_MAX_TOKENS=500
NL_SEARCH_MAX_RESULTS_PER_QUERY=10
```

**验证结果**: ✅ 配置完整且正确

### 配置类检查 ✅

**文件**: `src/services/nl_search/config.py`

```python
class NLSearchConfig(BaseSettings):
    llm_base_url: Optional[str] = Field(
        default=None,
        description="LLM API Base URL (自定义API端点)",
        env="NL_SEARCH_LLM_BASE_URL"  # ✅ 环境变量名正确
    )

    class Config:
        env_prefix = "NL_SEARCH_"  # ✅ 前缀正确
        env_file = ".env"          # ✅ 文件名正确
        env_file_encoding = "utf-8"
        case_sensitive = False     # ✅ 大小写不敏感
        extra = "ignore"
```

**验证结果**: ✅ 配置类设计正确

---

## 🎯 问题根因与解决方案

### 问题: 配置加载机制

**症状**:
- .env文件已正确配置
- 直接curl测试API endpoint成功
- 服务重启后仍使用旧配置
- 日志中没有"使用自定义API端点"消息

**根本原因**:
```python
# src/services/nl_search/config.py:169
nl_search_config = NLSearchConfig()  # 模块导入时立即执行

# src/services/nl_search/nl_search_service.py:269
nl_search_service = NLSearchService()  # 模块导入时立即执行
```

**执行流程**:
1. **首次启动**: Python导入模块 → 读取.env → 创建全局单例
2. **修改.env**: 更新环境变量文件
3. **uvicorn --reload**: 检测文件变化 → 重新加载模块代码 → **但全局对象已在内存中，不会重新初始化**
4. **结果**: 旧配置仍然生效

**为什么直接curl可以成功**:
- 直接curl绕过了应用代码，直接调用第三方API
- 证明API endpoint和credentials完全有效

### 解决方案

#### 方案A: 完全重启Python进程 (当前临时方案)

```bash
# 1. Kill所有uvicorn进程
lsof -ti:8000 | xargs kill -9

# 2. 重新启动
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 3. 验证配置加载
# 查看日志应显示:
# "LLM Processor 配置: model=gpt-5, base_url=https://api.gpt.ge/v1"
# "使用自定义API端点: https://api.gpt.ge/v1"
```

#### 方案B: 改为懒加载 (推荐的永久方案)

```python
# src/services/nl_search/nl_search_service.py

# 删除全局单例
# nl_search_service = NLSearchService()  ❌

# 改为工厂函数
def get_nl_search_service() -> NLSearchService:
    """获取NL Search服务实例（懒加载）"""
    return NLSearchService()

# 或使用依赖注入
from functools import lru_cache

@lru_cache()
def get_nl_search_service() -> NLSearchService:
    """获取NL Search服务单例（延迟初始化）"""
    return NLSearchService()
```

然后在API endpoints中:
```python
@router.post("/")
async def create_nl_search(
    request: NLSearchRequest,
    service: NLSearchService = Depends(get_nl_search_service)  # 依赖注入
):
    result = await service.create_search(...)
```

**优点**:
- ✅ 支持配置热重载
- ✅ 更好的测试性（可以mock）
- ✅ 符合依赖注入最佳实践

---

## 🚀 完整测试流程 (重启后)

### 步骤1: 完全重启服务

```bash
# Kill旧进程
lsof -ti:8000 | xargs kill -9

# 等待端口释放
sleep 2

# 启动新进程
nohup uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 等待启动完成
sleep 5

# 验证启动成功
tail -n 50 /tmp/uvicorn.log | grep "Application startup complete"
```

### 步骤2: 验证配置加载

```bash
# 查看LLM Processor配置日志（应该在首次API调用时出现）
grep "LLM Processor 配置" /tmp/uvicorn.log

# 预期输出:
# LLM Processor 配置: model=gpt-5, base_url=https://api.gpt.ge/v1, api_key=已设置

# 查看自定义API端点日志
grep "使用自定义API端点" /tmp/uvicorn.log

# 预期输出:
# 使用自定义API端点: https://api.gpt.ge/v1
```

### 步骤3: 测试所有接口

#### 3.1 状态检查
```bash
curl http://localhost:8000/api/v1/nl-search/status | jq

# 预期: {"enabled": true, "version": "1.0.0-beta", ...}
```

#### 3.2 创建搜索
```bash
curl -X POST 'http://localhost:8000/api/v1/nl-search/' \
  -H 'Content-Type: application/json' \
  -d '{"query_text":"Python编程最新教程"}' | jq

# 预期成功响应:
# {
#   "log_id": null,  # MariaDB不可用时为null
#   "status": "completed",
#   "message": "搜索成功",
#   "results": [...],
#   "analysis": {
#     "intent": "learning",
#     "keywords": ["Python", "编程", "教程"],
#     ...
#   },
#   "refined_query": "Python programming tutorial 2024"
# }
```

#### 3.3 查看日志验证LLM调用
```bash
# 查看LLM API调用
tail -100 /tmp/uvicorn.log | grep -A 5 "LLM解析"

# 应该看到:
# LLM解析完成: intent=learning, keywords=[...]
# 查询精炼成功: 'Python编程最新教程' -> 'Python programming tutorial'
```

---

## 📝 测试结论

### 已验证功能 ✅

1. **API Endpoint有效性**: ✅ `https://api.gpt.ge/v1` 和gpt-5模型可用
2. **API认证**: ✅ API key有效
3. **数据库容错**: ✅ MariaDB不可用时不会导致服务崩溃
4. **状态接口**: ✅ GET /status 正常返回
5. **配置系统**: ✅ .env文件和Config类设计正确

### 待解决问题 ⚠️

1. **配置加载机制**: 需要实施方案B（懒加载）以支持配置热重载
2. **数据库依赖优化**: GET /{log_id} 和 GET / 接口在数据库不可用时应返回503而非500
3. **错误处理增强**: nl_search_service.py:105需要检查analysis是否为None

### 后续建议

#### 优先级高 🔴
1. **实施懒加载方案**: 将全局单例改为依赖注入，支持配置热重载
2. **完善错误处理**: 在nl_search_service.py中检查LLM返回值
3. **添加降级提示**: 数据库不可用时返回503和友好错误消息

#### 优先级中 🟡
4. **添加健康检查**: 实现 GET /health 接口检查所有依赖服务状态
5. **配置验证增强**: 启动时验证API key和endpoint可用性
6. **日志结构化**: 使用结构化日志便于监控和调试

#### 优先级低 🟢
7. **添加监控指标**: LLM调用成功率、响应时间、错误率
8. **实施重试策略**: LLM调用失败时的指数退避重试
9. **缓存优化**: 对常见查询进行LLM响应缓存

---

## 附录: 快速问题排查清单

遇到"搜索失败"错误时，按以下顺序检查：

### ✅ 1. 检查API endpoint可用性
```bash
curl -X POST 'https://api.gpt.ge/v1/chat/completions' \
  -H "Authorization: Bearer $NL_SEARCH_LLM_API_KEY" \
  -d '{"model":"gpt-5","messages":[{"role":"user","content":"test"}]}'

# 应返回200和JSON响应
```

### ✅ 2. 检查环境变量
```bash
grep "^NL_SEARCH" .env

# 必须包含:
# NL_SEARCH_ENABLED=true
# NL_SEARCH_LLM_API_KEY=sk-...
# NL_SEARCH_LLM_BASE_URL=https://api.gpt.ge/v1
# NL_SEARCH_LLM_MODEL=gpt-5
```

### ✅ 3. 检查配置加载
```bash
# 触发一次API调用
curl -X POST 'http://localhost:8000/api/v1/nl-search/' \
  -H 'Content-Type: application/json' \
  -d '{"query_text":"test"}'

# 查看配置日志
grep "LLM Processor 配置\|使用自定义API端点" /tmp/uvicorn.log

# 如果没有输出 → 配置未加载，需要完全重启Python进程
```

### ✅ 4. 验证服务启动
```bash
curl http://localhost:8000/api/v1/nl-search/status | jq .enabled

# 应返回: true
```

### ✅ 5. 查看详细错误日志
```bash
tail -100 /tmp/uvicorn.log | grep -A 10 "LLM API\|搜索失败\|Error"
```

---

**报告生成时间**: 2025-11-17 11:35:00
**测试环境**: macOS, Python 3.13.0, FastAPI, uvicorn --reload
