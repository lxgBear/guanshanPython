# NL Search OSINT 增强功能

**版本**: v2.1.0 (claude_client) / v3.1.0 (nl_search_service)
**日期**: 2025-12-24
**参考**: Tool-for-osint 项目最佳实践

---

## 概述

借鉴 OSINT (开源情报) 系统的验证和分类方法，为 NL Search 搜索结果增加三个维度的元数据增强：

1. **Source Tier** - 来源层级分类 (6级)
2. **Credibility** - 可信度评分 (5级)
3. **Time Verification** - 时间验证置信度 (4级)

---

## 功能详情

### 1. Source Tier 来源层级 (6级)

根据 URL 域名自动分类来源的权威程度。

| 层级 | 标签 | 评分 | 域名示例 |
|------|------|------|----------|
| `official` | 官方 | 1.0 | .gov, .gov.cn, .edu, .mil |
| `authoritative` | 权威 | 0.9 | reuters.com, bbc.com, xinhuanet.com |
| `mainstream` | 主流 | 0.8 | nytimes.com, cnn.com, sina.com.cn |
| `specialized` | 专业 | 0.75 | cfr.org, nature.com, arxiv.org |
| `general` | 一般 | 0.6 | medium.com, wordpress.com |
| `social` | 社交 | 0.4 | twitter.com, weibo.com, zhihu.com |

**API 响应字段**:
```json
"source_tier": {
    "tier": "authoritative",
    "tier_score": 0.9,
    "tier_label": "权威",
    "tier_description": "国际通讯社、权威媒体"
}
```

### 2. Credibility 可信度评分 (5级)

综合评估信息的可信程度，基于多个因素加权计算：
- Claude 相关性评分 (40%)
- 来源层级评分 (40%)
- 时间验证 (10%)
- 多源验证 (10%)

| 等级 | 符号 | 分数范围 | 描述 |
|------|------|----------|------|
| `confirmed` | ✅ | 0.9-1.0 | 多源证实，高度可信 |
| `reliable` | 🟢 | 0.7-0.9 | 权威来源，基本可信 |
| `unverified` | 🟡 | 0.5-0.7 | 单一来源，需谨慎 |
| `questionable` | 🟠 | 0.3-0.5 | 来源不明，有矛盾 |
| `unreliable` | 🔴 | 0.0-0.3 | 无法验证，可能错误 |

**API 响应字段**:
```json
"credibility": {
    "score": 0.85,
    "level": "reliable",
    "symbol": "🟢",
    "label": "可信",
    "description": "权威来源，基本可信"
}
```

### 3. Time Verification 时间验证 (4级)

验证发布日期的置信程度。

| 等级 | 符号 | 匹配模式 | 加分 |
|------|------|----------|------|
| `high` | 🕐 | ISO格式、中文日期、美式日期 | +0.1 |
| `medium` | 🕑 | 相对时间 (2小时前、yesterday) | +0.05 |
| `low` | 🕒 | 格式不明确 | 0 |
| `none` | ❓ | 无日期信息 | 0 |

**支持的日期格式**:
- ISO: `2025-12-24`, `2025-12-24T10:30:00`
- 中文: `2025年12月24日`
- 美式: `December 24, 2025`
- 相对: `2 hours ago`, `3天前`, `yesterday`, `刚刚`

**API 响应字段**:
```json
"time_verification": {
    "confidence": "high",
    "parsed_date": "2025-12-24",
    "symbol": "🕐",
    "label": "高置信度",
    "description": "有明确发布日期，格式标准",
    "score_bonus": 0.1
}
```

---

## 完整响应示例

```json
{
    "title": "Japan Defense White Paper 2025",
    "url": "https://www.mod.go.jp/j/publication/wp/wp2025/",
    "description": "...",
    "rerank_score": 0.95,
    "rerank_reason": "高度相关",
    "source_tier": {
        "tier": "official",
        "tier_score": 1.0,
        "tier_label": "官方",
        "tier_description": "政府官网、教育机构"
    },
    "time_verification": {
        "confidence": "high",
        "parsed_date": "2025-07-15",
        "symbol": "🕐",
        "label": "高置信度",
        "score_bonus": 0.1
    },
    "credibility": {
        "score": 0.92,
        "level": "confirmed",
        "symbol": "✅",
        "label": "确认",
        "description": "多源证实，高度可信"
    }
}
```

---

## 代码位置

| 文件 | 版本 | 说明 |
|------|------|------|
| `src/infrastructure/llm/claude_client.py` | v2.1.0 | 核心实现 |
| `src/services/nl_search/nl_search_service.py` | v3.1.0 | 服务集成 |

### 主要函数

```python
# 来源分类
def classify_source_tier(url: str) -> Dict[str, Any]

# 时间验证
def verify_publish_date(date_str: Optional[str]) -> Dict[str, Any]

# 可信度计算
def calculate_credibility(
    rerank_score: float,
    tier_score: float,
    has_date: bool = False,
    multiple_sources: bool = False
) -> Dict[str, Any]
```

---

## 配置常量

### SOURCE_TIER_RULES

```python
SOURCE_TIER_RULES = {
    "official": {
        "domains": [".gov", ".gov.cn", ".edu", ".edu.cn", ".mil"],
        "tier_score": 1.0,
        "label": "官方"
    },
    # ... 其他层级
}
```

### CREDIBILITY_LEVELS

```python
CREDIBILITY_LEVELS = {
    "confirmed": {"symbol": "✅", "range": (0.9, 1.0), "label": "确认"},
    "reliable": {"symbol": "🟢", "range": (0.7, 0.9), "label": "可信"},
    # ... 其他级别
}
```

### TIME_CONFIDENCE_LEVELS

```python
TIME_CONFIDENCE_LEVELS = {
    "high": {"symbol": "🕐", "score_bonus": 0.1},
    "medium": {"symbol": "🕑", "score_bonus": 0.05},
    # ... 其他级别
}
```

---

## 使用场景

1. **情报分析** - 快速识别权威来源
2. **新闻聚合** - 过滤低质量内容
3. **学术研究** - 优先显示学术来源
4. **事实核查** - 评估信息可信度

---

## 后续计划

- [ ] P2: 多语言搜索流程集成 (`search_mode="multilang"`)
- [ ] 多源交叉验证 (`multiple_sources=True`)
- [ ] 时间范围过滤增强

---

**参考来源**: `Downloads/Tool for osint/_agents/validator_agent.md`
