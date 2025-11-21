# GPT-5 Search API 配置分析报告

**生成时间**: 2025-11-20
**分析对象**: `src/services/nl_search/gpt5_search_adapter.py`
**文档来源**: OpenAI Platform Documentation

---

## 问题1: GPT-5 Search API 有没有配置提示词字段？

### 答案：❌ 没有独立的提示词配置字段

### 当前实现分析

**位置**: `gpt5_search_adapter.py:279-346` (`_build_search_payload` 方法)

```python
def _build_search_payload(self, query: str, language: str) -> Dict[str, Any]:
    # 构建搜索提示词 - 动态生成，无配置字段
    if "gemini" in self.search_model.lower():
        # Gemini模型：添加特殊指令
        search_prompt = f"""请搜索以下问题，并在回答中明确标注每个信息的来源URL：
{query}
要求：
1. 提供详细的回答
2. 在每个关键信息后用 [来源: URL] 的格式标注来源链接
3. 至少提供3-5个不同来源的URL"""
    else:
        # gpt-5-search-api 模型：直接使用查询文本
        search_prompt = query
```

### 提示词处理逻辑

| 模型类型 | 提示词处理 | 代码位置 |
|---------|-----------|---------|
| **gpt-5-search-api** | 直接使用 `query` 原文 | 第310行 |
| **gemini-3-pro-preview-search** | 添加 URL 引用指令 | 第298-307行 |
| **其他模型** | 直接使用 `query` 原文 | 第310行 |

### 改进建议

如果需要为 GPT-5 Search API 添加系统提示词，可以考虑：

#### 方案A：添加环境变量配置
```python
# config.py 添加
search_system_prompt: Optional[str] = Field(
    default=None,
    description="搜索模型的系统提示词（可选）",
    env="NL_SEARCH_SYSTEM_PROMPT"
)
```

#### 方案B：使用 system message（Chat Completions API）
```python
# 当前使用的是 Chat Completions API
payload = {
    "model": self.search_model,
    "messages": [
        {
            "role": "system",  # 添加系统消息
            "content": "You are a search assistant. Provide URLs with citations."
        },
        {
            "role": "user",
            "content": search_prompt
        }
    ],
    "max_tokens": self.max_tokens,
    "temperature": 0.3
}
```

---

## 问题2: response_format 参数是干什么的？

### 答案：✅ 控制模型输出格式的参数（支持结构化 JSON 输出）

### 官方文档说明

**来源**: OpenAI Platform Documentation - `/websites/platform_openai`

### 功能概述

`response_format` 是 OpenAI Chat Completions API 的参数，用于指定模型响应的格式，主要用于**结构化 JSON 输出**。

### 支持的格式类型

#### 1. **json_schema** (推荐方式)
严格的 JSON Schema 验证，确保输出符合指定的数据结构。

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "person",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "minLength": 1},
          "age": {"type": "number", "minimum": 0, "maximum": 130}
        },
        "required": ["name", "age"],
        "additionalProperties": false
      }
    }
  }
}
```

#### 2. **json_object** (旧版模式)
通用 JSON 输出，确保返回有效的 JSON，但不强制特定结构。

```json
{
  "response_format": {
    "type": "json_object"
  }
}
```

### 使用场景

| 场景 | 使用 response_format 的好处 |
|------|---------------------------|
| **数据提取** | 强制模型返回结构化数据，避免解析失败 |
| **API 集成** | 确保返回格式符合后端数据模型 |
| **搜索结果聚合** | 统一多个搜索源的数据格式 |
| **表单验证** | 确保提取的数据符合验证规则 |

### 在当前项目中的应用潜力

#### 当前状态：❌ 未使用 `response_format`

**代码位置**: `gpt5_search_adapter.py:327-344`

```python
# 当前 payload 不包含 response_format
payload = {
    "model": self.search_model,
    "messages": [
        {"role": "user", "content": search_prompt}
    ],
    "max_tokens": self.max_tokens,
    "temperature": 0.3
}
# ❌ 缺少 response_format 参数
```

#### 改进方案：✅ 添加结构化输出

**用例场景**: 用户需求提到的社交媒体搜索结果分类

根据用户在 `20251120_150924_40b91fdf.json` 中的要求：
```
输出格式：
{
  "topic": "<用户主题>",
  "adopted_sources": [
    {
      "title": "",
      "url": "",
      "type": "",  // twitter/reddit/youtube/web/news
      "publish_time": "",
      "summary": ""
    }
  ],
  "non_adopted_sources": [...]
}
```

**实现建议**:

```python
# 1. 在 config.py 添加配置
use_structured_output: bool = Field(
    default=False,
    description="是否使用 response_format 强制结构化输出",
    env="NL_SEARCH_USE_STRUCTURED_OUTPUT"
)

# 2. 在 gpt5_search_adapter.py 修改
def _build_search_payload(self, query: str, language: str) -> Dict[str, Any]:
    payload = {
        "model": self.search_model,
        "messages": [{"role": "user", "content": query}],
        "max_tokens": self.max_tokens,
        "temperature": 0.3
    }

    # 添加结构化输出支持
    if nl_search_config.use_structured_output:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "search_results",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "adopted_sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": "string", "format": "uri"},
                                    "type": {"type": "string", "enum": ["twitter", "reddit", "youtube", "web", "news", "forum"]},
                                    "publish_time": {"type": "string"},
                                    "summary": {"type": "string"}
                                },
                                "required": ["title", "url", "type"],
                                "additionalProperties": False
                            }
                        },
                        "non_adopted_sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": "string", "format": "uri"},
                                    "type": {"type": "string"}
                                },
                                "required": ["title", "url"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["topic", "adopted_sources", "non_adopted_sources"],
                    "additionalProperties": False
                }
            }
        }

    return payload
```

### response_format 的重要注意事项

#### ⚠️ 错误处理

从官方文档中提取的最佳实践：

```python
# 检查响应状态
if response.choices[0].message.finish_reason == "length":
    # JSON 可能不完整（超出 max_tokens）
    raise Exception("Response truncated - increase max_tokens")

if response.choices[0].message.get("refusal"):
    # 模型拒绝生成（安全过滤）
    raise Exception(f"Model refused: {response.choices[0].message.refusal}")

if response.choices[0].message.finish_reason == "content_filter":
    # 内容被过滤（可能部分 JSON）
    raise Exception("Content filtered - JSON may be partial")

if response.choices[0].message.finish_reason == "stop":
    # 正常完成
    content = response.choices[0].message.content
    result = json.loads(content)  # 安全解析
```

#### ⚠️ 兼容性问题

| API 类型 | response_format 支持 | 参数位置 |
|---------|---------------------|---------|
| **Chat Completions API** (`/v1/chat/completions`) | ✅ 支持 | 顶层参数 `response_format` |
| **Responses API** (`/v1/responses`) | ✅ 支持（推荐） | `text.format` 字段 |

**当前项目使用**: Chat Completions API (可配置切换)

```python
# .env 配置
NL_SEARCH_USE_RESPONSES_API=false  # 当前使用 Chat Completions
```

---

## 总结与建议

### 当前状态

| 功能 | 状态 | 位置 |
|------|------|------|
| **提示词配置** | ❌ 无独立配置字段 | 硬编码在 `_build_search_payload` |
| **response_format** | ❌ 未使用 | N/A |
| **结构化输出** | ⚠️ 依赖模型自然输出 | 无强制验证 |

### 优先级建议

#### 🔴 高优先级：添加 response_format 支持
**原因**: 用户明确要求结构化 JSON 输出（社交媒体分类）

**实施步骤**:
1. 在 `config.py` 添加 `use_structured_output` 配置
2. 在 `gpt5_search_adapter.py` 实现 JSON Schema
3. 更新响应解析逻辑 `_parse_gpt5_search_response`
4. 添加错误处理（length/refusal/content_filter）

#### 🟡 中优先级：添加系统提示词配置
**原因**: 灵活控制搜索行为，无需修改代码

**实施步骤**:
1. 在 `config.py` 添加 `search_system_prompt` 可选字段
2. 在 `_build_search_payload` 使用 system message
3. 支持环境变量覆盖

#### 🟢 低优先级：优化 Gemini 提示词处理
**原因**: Gemini 已切换回 GPT-5，优先级降低

---

## 参考资料

- OpenAI Platform Documentation: https://platform.openai.com/docs/api-reference/chat
- Structured Outputs Guide: https://platform.openai.com/docs/guides/structured-outputs
- JSON Schema Specification: https://json-schema.org/
- Project Config: `src/services/nl_search/config.py`
- Search Adapter: `src/services/nl_search/gpt5_search_adapter.py`
