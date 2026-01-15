"""Feature Flags 配置模块 (v4.7.0)

提供新旧架构切换的 Feature Flag 配置和验证。

## Feature Flags 说明

### OSINT 架构迁移 (v4.7.0)

**新架构 (OSINT)**: 将查询��析拆分为两个独立阶段
1. IntentParserNode: 解析用户意图（提取 investigation_target, source_type_constraint）
2. KeywordGeneratorNode: 基于 investigation_target 生成分层关键词

**旧架构 (Legacy v4.6.0)**: 单节点查询分析
- UnifiedQueryAnalyzer: 一次性完成意图解析和关键词生��

### Feature Flag 列表

| Flag | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| use_osint_architecture | bool | True | 使用 OSINT 新架构 |
| enable_layer_0 | bool | True | 启用官方来源层 |
| enable_layer_1 | bool | True | 启用主流媒体层 |
| enable_layer_2 | bool | True | 启用周边地区层 |
| enable_layer_3 | bool | True | 启用国际权威层 |
| enable_layer_4 | bool | True | 启用智库分析层 |
| enable_validation | bool | True | 启用结果验证 |
| enable_quality_gate | bool | True | 启用质量门控 |
| enable_checkpointing | bool | True | 启用检查点持久化 |
| enable_parallel_layers | bool | True | 启用并行层级搜索 |

### 使用方法

#### 通过 API 参数
```python
result = await service.execute_search(
    query="西方媒体对某事件的报道",
    user_id="123",
    options={
        "use_osint_architecture": True,  # 使用新架构
        "enable_layer_0": True,
        "enable_layer_2": False,  # 禁用周边地区层
    }
)
```

#### 通过环境变量
```bash
export USE_OSINT_ARCHITECTURE=true
export ENABLE_LAYER_0=true
export ENABLE_LAYER_2=false
```

#### 通过配置对象
```python
from src.services.langgraph_search.config import LangGraphSearchConfig

config = LangGraphSearchConfig(
    enable_layer_0=True,
    enable_layer_1=True,
    enable_layer_2=False,  # 禁用第2层
)
```

## 架构切换逻辑

### 自动检测逻辑

1. **显式指定**: 通过 `search_options["use_osint_architecture"]` 明确指定
2. **版本标记**: State 中存在 `osint_migration_version` 字段
3. **默认行为**: v4.7.0+ 默认使用新架构

### 降级策略

- 新架构失败时，自动降级到旧架构
- 旧架构��持可用，用于兼容性测试

## 兼容性保证

### State 字段兼容

新架构保留旧字段以确保向后兼容：

```python
# 新架构字段
"parsed_intent": {...}      # ParsedIntent 对象
"keyword_groups": [...]     # KeywordGroup 列表
"source_type_constraint": "西方媒体"

# 兼容旧字段（自动填充）
"keywords": [...]           # 从 keyword_groups 提取
"keywords_en": [...]        # 从 keyword_groups 提取
"analysis": {...}           # 兼容 v4.6.0 格式
```

### API 响应兼容

新架构返回格式与旧架构保持一致：

```python
{
    "success": True,
    "results": [...],
    "statistics": {
        "total_results": 100,
        "layer_distribution": {...}
    }
}
```
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class ArchitectureVersion(Enum):
    """架构版本枚举"""
    LEGACY = "4.6.0"       # 旧架构（单节点分析）
    OSINT = "4.7.0"        # 新架构（两阶段分析）


@dataclass
class FeatureFlags:
    """Feature Flags 配置

    控制搜索系统的各种功能开关。
    """

    # ===== 架构选择 =====
    use_osint_architecture: bool = True  # 使用 OSINT 新架构（v4.7.0）

    # ===== 分层搜索开关 =====
    enable_layer_0: bool = True    # 官方来源
    enable_layer_1: bool = True    # 主流媒体
    enable_layer_2: bool = True    # 周边地区
    enable_layer_3: bool = True    # 国际权威
    enable_layer_4: bool = True    # 智库分析

    # ===== 功能开关 =====
    enable_validation: bool = True        # 启用结果验证
    enable_quality_gate: bool = True      # 启用质量门控
    enable_checkpointing: bool = True     # 启用检查点持久化
    enable_parallel_layers: bool = True   # 启用并行层级搜索

    # ===== 实验性功能 =====
    enable_llm_fallback: bool = True      # 启用 LLM 降级到规则
    enable_source_discovery: bool = True  # 启用动态源发现
    enable_human_review: bool = False     # 启用人工审核

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        """从环境变量加载 Feature Flags"""
        return cls(
            use_osint_architecture=os.getenv("USE_OSINT_ARCHITECTURE", "true").lower() == "true",
            enable_layer_0=os.getenv("ENABLE_LAYER_0", "true").lower() == "true",
            enable_layer_1=os.getenv("ENABLE_LAYER_1", "true").lower() == "true",
            enable_layer_2=os.getenv("ENABLE_LAYER_2", "true").lower() == "true",
            enable_layer_3=os.getenv("ENABLE_LAYER_3", "true").lower() == "true",
            enable_layer_4=os.getenv("ENABLE_LAYER_4", "true").lower() == "true",
            enable_validation=os.getenv("ENABLE_VALIDATION", "true").lower() == "true",
            enable_quality_gate=os.getenv("ENABLE_QUALITY_GATE", "true").lower() == "true",
            enable_checkpointing=os.getenv("ENABLE_CHECKPOINTING", "true").lower() == "true",
            enable_parallel_layers=os.getenv("ENABLE_PARALLEL_LAYERS", "true").lower() == "true",
            enable_llm_fallback=os.getenv("ENABLE_LLM_FALLBACK", "true").lower() == "true",
            enable_source_discovery=os.getenv("ENABLE_SOURCE_DISCOVERY", "true").lower() == "true",
            enable_human_review=os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true",
        )

    @classmethod
    def from_search_options(cls, options: Optional[Dict[str, Any]]) -> "FeatureFlags":
        """从搜索选项创建 Feature Flags

        Args:
            options: 搜索选项字典，可能包含 feature flag 覆盖

        Returns:
            FeatureFlags 实例
        """
        if not options:
            return cls.from_env()

        flags = cls.from_env()

        # 应用选项中的覆盖
        if "use_osint_architecture" in options:
            flags.use_osint_architecture = options["use_osint_architecture"]
        if "enable_layer_0" in options:
            flags.enable_layer_0 = options["enable_layer_0"]
        if "enable_layer_1" in options:
            flags.enable_layer_1 = options["enable_layer_1"]
        if "enable_layer_2" in options:
            flags.enable_layer_2 = options["enable_layer_2"]
        if "enable_layer_3" in options:
            flags.enable_layer_3 = options["enable_layer_3"]
        if "enable_layer_4" in options:
            flags.enable_layer_4 = options["enable_layer_4"]
        if "enable_validation" in options:
            flags.enable_validation = options["enable_validation"]
        if "enable_quality_gate" in options:
            flags.enable_quality_gate = options["enable_quality_gate"]

        return flags

    def get_enabled_layers(self) -> List[int]:
        """获取启用的搜索层级

        Returns:
            启用的层级 ID 列表
        """
        layers = []
        if self.enable_layer_0:
            layers.append(0)
        if self.enable_layer_1:
            layers.append(1)
        if self.enable_layer_2:
            layers.append(2)
        if self.enable_layer_3:
            layers.append(3)
        if self.enable_layer_4:
            layers.append(4)
        return layers

    def get_architecture_version(self) -> ArchitectureVersion:
        """获取当前使用的架构版本

        Returns:
            ArchitectureVersion 枚举值
        """
        return ArchitectureVersion.OSINT if self.use_osint_architecture else ArchitectureVersion.LEGACY

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Feature Flags 字典表示
        """
        return {
            "architecture": self.get_architecture_version().value,
            "use_osint_architecture": self.use_osint_architecture,
            "enabled_layers": self.get_enabled_layers(),
            "enable_layer_0": self.enable_layer_0,
            "enable_layer_1": self.enable_layer_1,
            "enable_layer_2": self.enable_layer_2,
            "enable_layer_3": self.enable_layer_3,
            "enable_layer_4": self.enable_layer_4,
            "enable_validation": self.enable_validation,
            "enable_quality_gate": self.enable_quality_gate,
            "enable_checkpointing": self.enable_checkpointing,
            "enable_parallel_layers": self.enable_parallel_layers,
            "enable_llm_fallback": self.enable_llm_fallback,
            "enable_source_discovery": self.enable_source_discovery,
            "enable_human_review": self.enable_human_review,
        }


def validate_feature_flags(flags: FeatureFlags) -> List[str]:
    """验证 Feature Flags 配置

    Args:
        flags: FeatureFlags 实例

    Returns:
        警告消息列表（空表示无警告）
    """
    warnings = []

    # 检查是否禁用了所有层级
    if not flags.get_enabled_layers():
        warnings.append("所有搜索层级都被禁用，搜索可能无法返回结果")

    # 检查架构降级
    if not flags.use_osint_architecture:
        warnings.append("使用旧架构（v4.6.0），部分新功能不可用")

    # 检查质量门控与验证的依赖关系
    if flags.enable_quality_gate and not flags.enable_validation:
        warnings.append("质量门控需要启用结果验证")

    return warnings


def merge_feature_flags(
    base: FeatureFlags,
    override: Optional[Dict[str, Any]]
) -> FeatureFlags:
    """合并 Feature Flags

    Args:
        base: 基础 FeatureFlags
        override: 覆盖的配置字典

    Returns:
        合并后的 FeatureFlags
    """
    if not override:
        return base

    return FeatureFlags(
        use_osint_architecture=override.get("use_osint_architecture", base.use_osint_architecture),
        enable_layer_0=override.get("enable_layer_0", base.enable_layer_0),
        enable_layer_1=override.get("enable_layer_1", base.enable_layer_1),
        enable_layer_2=override.get("enable_layer_2", base.enable_layer_2),
        enable_layer_3=override.get("enable_layer_3", base.enable_layer_3),
        enable_layer_4=override.get("enable_layer_4", base.enable_layer_4),
        enable_validation=override.get("enable_validation", base.enable_validation),
        enable_quality_gate=override.get("enable_quality_gate", base.enable_quality_gate),
        enable_checkpointing=override.get("enable_checkpointing", base.enable_checkpointing),
        enable_parallel_layers=override.get("enable_parallel_layers", base.enable_parallel_layers),
        enable_llm_fallback=override.get("enable_llm_fallback", base.enable_llm_fallback),
        enable_source_discovery=override.get("enable_source_discovery", base.enable_source_discovery),
        enable_human_review=override.get("enable_human_review", base.enable_human_review),
    )
