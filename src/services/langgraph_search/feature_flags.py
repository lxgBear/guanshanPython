"""Feature Flags 配置模块 (v4.11.0)

提供搜索系统的各种功能开关配置。

## 架构版本说明

### v4.11.0 两步架构（推荐，默认启用）
流程: START → keyword_generator → firecrawl_config → simplified_search → output → END
- KeywordGeneratorNode: 5 步关键词分析（理解意图 → 确认事件 → 提取关键词 → 理解关键词 → 组合搜索词）
- FirecrawlConfigNode: 根据分层关键词(Tier 1/2/3)生成 Firecrawl 搜索配置

### v4.8.0 完整架构（5 层并行搜索，备用）
流程: START → query_analyzer → source_discovery → [5 层并行搜索] → aggregator → validator → output → END

## Feature Flag 列表
| Flag | 类型 | 默认值 | 说明 |
|------|--------|--------|------|
| use_two_step_architecture | bool | True | 使用两步架构 (v4.11.0，推荐) |
| enable_llm_interpreter | bool | True | 启用 LLM 查询理解 |
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
    query="中美贸易谈判",
    user_id="123",
    options={
        "enable_layer_2": False,  # 禁用周边地区层
        "enable_layer_3": False,  # 禁用国际权威层
    }
)
```

#### 通过环境变量
```bash
export USE_OSINT_ARCHITECTURE=true
export ENABLE_LAYER_0=true
export ENABLE_LAYER_1=true
export ENABLE_LAYER_2=false
export ENABLE_LAYER_3=false
export ENABLE_LAYER_4=true
export ENABLE_VALIDATION=true
export ENABLE_QUALITY_GATE=true
export ENABLE_CHECKPOINTING=true
export ENABLE_PARALLEL_LAYERS=true
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
3. **默认行为**: v4.8.0+ 默认使用新架构

### 降级策略
- 新架构失败时，提供规则基础的查询处理
- 确保核心功能始终可用

## 兼容性保证

### State 字段兼容
新架构保持必要字段以确保向后兼容：
```python
# 分析字段
"analysis": {...}
"keywords": [...]         # 从 layer_search_config 提取
"keywords_en": [...]     # 从 layer_search_config 提取
"time_range": "qdr:m"
"target_languages": [...]
"search_domains": [...]

# 搜索配置字段
"layer_search_config": {
    "layer_0": {"language": "zh", "keywords": [...], "enabled": true},
    "layer_1": {"language": "zh", "keywords": [...], "enabled": true},
    ...
}

# 架构版本字段
"osint_migration_version": "4.8.0"
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
    RULES_BASED = "4.8.0"    # 基于规则的完整架构（5层并行搜索，备用）
    TWO_STEP = "4.11.0"      # 两步关键词生成架构（v4.11.0，推荐）


@dataclass
class FeatureFlags:
    """Feature Flags 配置

    控制搜索系统的各种功能开关。
    """
    # ===== 架构选择 =====
    use_rules_based_architecture: bool = True  # 使用完整架构（5层并行搜索，备用）
    enable_llm_interpreter: bool = True        # 启用 LLM 查询理解
    # v4.11.0: 两步关键词生成架构（推荐）
    use_two_step_architecture: bool = True     # 使用两步架构（默认开启，推荐）

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
    enable_source_discovery: bool = True  # 启用动态源发现
    enable_human_review: bool = False    # 启用人工审核

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        """从环境变量加载 Feature Flags"""
        return cls(
            use_rules_based_architecture=os.getenv(
                "USE_RULES_BASED_ARCHITECTURE", "true"
            ).lower() == "true",
            enable_llm_interpreter=os.getenv(
                "ENABLE_LLM_INTERPRETER", "true"
            ).lower() == "true",
            use_two_step_architecture=os.getenv(
                "USE_TWO_STEP_ARCHITECTURE", "true"
            ).lower() == "true",
            enable_layer_0=os.getenv("ENABLE_LAYER_0", "true").lower() == "true",
            enable_layer_1=os.getenv("ENABLE_LAYER_1", "true").lower() == "true",
            enable_layer_2=os.getenv("ENABLE_LAYER_2", "true").lower() == "true",
            enable_layer_3=os.getenv("ENABLE_LAYER_3", "true").lower() == "true",
            enable_layer_4=os.getenv("ENABLE_LAYER_4", "true").lower() == "true",
            enable_validation=os.getenv("ENABLE_VALIDATION", "true").lower() == "true",
            enable_quality_gate=os.getenv("ENABLE_QUALITY_GATE", "true").lower() == "true",
            enable_checkpointing=os.getenv("ENABLE_CHECKPOINTING", "true").lower() == "true",
            enable_parallel_layers=os.getenv("ENABLE_PARALLEL_LAYERS", "true").lower() == "true",
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
        if "use_two_step_architecture" in options:
            flags.use_two_step_architecture = options["use_two_step_architecture"]
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

    def get_architecture_version(self) -> str:
        """获取当前使用的架构版本

        优先级: two_step > rules_based

        Returns:
            架构版本字符串
        """
        if self.use_two_step_architecture:
            return ArchitectureVersion.TWO_STEP.value
        return ArchitectureVersion.RULES_BASED.value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Feature Flags 字典表示
        """
        return {
            "architecture": self.get_architecture_version(),
            "use_rules_based_architecture": self.use_rules_based_architecture,
            "use_two_step_architecture": self.use_two_step_architecture,
            "enable_llm_interpreter": self.enable_llm_interpreter,
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
        use_rules_based_architecture=override.get(
            "use_rules_based_architecture", base.use_rules_based_architecture
        ),
        enable_llm_interpreter=override.get(
            "enable_llm_interpreter", base.enable_llm_interpreter
        ),
        use_two_step_architecture=override.get(
            "use_two_step_architecture", base.use_two_step_architecture
        ),
        enable_layer_0=override.get("enable_layer_0", base.enable_layer_0),
        enable_layer_1=override.get("enable_layer_1", base.enable_layer_1),
        enable_layer_2=override.get("enable_layer_2", base.enable_layer_2),
        enable_layer_3=override.get("enable_layer_3", base.enable_layer_3),
        enable_layer_4=override.get("enable_layer_4", base.enable_layer_4),
        enable_validation=override.get("enable_validation", base.enable_validation),
        enable_quality_gate=override.get("enable_quality_gate", base.enable_quality_gate),
        enable_checkpointing=override.get("enable_checkpointing", base.enable_checkpointing),
        enable_parallel_layers=override.get("enable_parallel_layers", base.enable_parallel_layers),
        enable_source_discovery=override.get("enable_source_discovery", base.enable_source_discovery),
        enable_human_review=override.get("enable_human_review", base.enable_human_review),
    )
