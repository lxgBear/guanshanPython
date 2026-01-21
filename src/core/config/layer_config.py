"""层架构配置

提供层架构的统一配置管理，支持从环境变量和配置文件加载。

配置优先级：
1. 环境变量 (最高)
2. 配置文件
3. 默认值 (最低)

环境变量前缀：
- LAYER_SEARCH_*: 搜索引擎层配置
- LAYER_AI_*: AI处理层配置
- LAYER_ORCHESTRATOR_*: 协调器配置
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchLayerConfig:
    """搜索引擎层配置"""
    engine: str = "langgraph"  # "langgraph" | "nl_search"
    fallback_engine: str = "nl_search"
    enable_fallback: bool = True
    max_results: int = 100
    save_to_db: bool = True
    timeout: float = 300.0

    @classmethod
    def from_env(cls) -> "SearchLayerConfig":
        """从环境变量加载配置"""
        return cls(
            engine=os.getenv("LAYER_SEARCH_ENGINE", "langgraph"),
            fallback_engine=os.getenv("LAYER_SEARCH_FALLBACK_ENGINE", "nl_search"),
            enable_fallback=os.getenv("LAYER_SEARCH_ENABLE_FALLBACK", "true").lower() == "true",
            max_results=int(os.getenv("LAYER_SEARCH_MAX_RESULTS", "100")),
            save_to_db=os.getenv("LAYER_SEARCH_SAVE_TO_DB", "true").lower() == "true",
            timeout=float(os.getenv("LAYER_SEARCH_TIMEOUT", "300.0")),
        )


@dataclass
class AILayerConfig:
    """AI处理层配置"""
    service_url: str = "http://localhost:8035/chat"  # 本地化默认值
    service_timeout: float = 300.0
    search_poll_interval: float = 1.0
    search_poll_max_retries: int = 300
    save_history: bool = True
    enhance_sources: bool = True

    @classmethod
    def from_env(cls) -> "AILayerConfig":
        """从环境变量加载配置"""
        return cls(
            service_url=os.getenv("LAYER_AI_SERVICE_URL", "http://localhost:8035/chat"),
            service_timeout=float(os.getenv("LAYER_AI_SERVICE_TIMEOUT", "300.0")),
            search_poll_interval=float(os.getenv("LAYER_AI_SEARCH_POLL_INTERVAL", "1.0")),
            search_poll_max_retries=int(os.getenv("LAYER_AI_SEARCH_POLL_MAX_RETRIES", "300")),
            save_history=os.getenv("LAYER_AI_SAVE_HISTORY", "true").lower() == "true",
            enhance_sources=os.getenv("LAYER_AI_ENHANCE_SOURCES", "true").lower() == "true",
        )


@dataclass
class OrchestratorConfig:
    """协调器配置"""
    parallel_execution: bool = True
    max_concurrent_layers: int = 5
    global_timeout: int = 600
    retry_failed_layers: bool = True
    skip_on_error: bool = False
    default_mode: str = "parallel"  # "sequential" | "parallel" | "hybrid"

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        """从环境变量加载配置"""
        return cls(
            parallel_execution=os.getenv("LAYER_ORCHESTRATOR_PARALLEL", "true").lower() == "true",
            max_concurrent_layers=int(os.getenv("LAYER_ORCHESTRATOR_MAX_CONCURRENT", "5")),
            global_timeout=int(os.getenv("LAYER_ORCHESTRATOR_GLOBAL_TIMEOUT", "600")),
            retry_failed_layers=os.getenv("LAYER_ORCHESTRATOR_RETRY_FAILED", "true").lower() == "true",
            skip_on_error=os.getenv("LAYER_ORCHESTRATOR_SKIP_ON_ERROR", "false").lower() == "true",
            default_mode=os.getenv("LAYER_ORCHESTRATOR_DEFAULT_MODE", "parallel"),
        )


@dataclass
class LayerSystemConfig:
    """层系统总配置

    包含搜索层、AI层和协调器的所有配置。

    Example:
        # 从环境变量加载
        config = LayerSystemConfig.from_env()

        # 手动创建
        config = LayerSystemConfig(
            search=SearchLayerConfig(engine="langgraph"),
            ai=AILayerConfig(service_url="http://localhost:8035/chat"),
            orchestrator=OrchestratorConfig(parallel_execution=True),
        )
    """
    search: SearchLayerConfig = field(default_factory=SearchLayerConfig)
    ai: AILayerConfig = field(default_factory=AILayerConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)

    # 元信息
    version: str = "5.0.0"
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "LayerSystemConfig":
        """从环境变量加载所有配置"""
        return cls(
            search=SearchLayerConfig.from_env(),
            ai=AILayerConfig.from_env(),
            orchestrator=OrchestratorConfig.from_env(),
            environment=os.getenv("ENVIRONMENT", "development"),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerSystemConfig":
        """从字典加载配置"""
        search_data = data.get("search", {})
        ai_data = data.get("ai", {})
        orchestrator_data = data.get("orchestrator", {})

        return cls(
            search=SearchLayerConfig(**search_data) if search_data else SearchLayerConfig(),
            ai=AILayerConfig(**ai_data) if ai_data else AILayerConfig(),
            orchestrator=OrchestratorConfig(**orchestrator_data) if orchestrator_data else OrchestratorConfig(),
            version=data.get("version", "5.0.0"),
            environment=data.get("environment", "development"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "search": {
                "engine": self.search.engine,
                "fallback_engine": self.search.fallback_engine,
                "enable_fallback": self.search.enable_fallback,
                "max_results": self.search.max_results,
                "save_to_db": self.search.save_to_db,
                "timeout": self.search.timeout,
            },
            "ai": {
                "service_url": self.ai.service_url,
                "service_timeout": self.ai.service_timeout,
                "search_poll_interval": self.ai.search_poll_interval,
                "search_poll_max_retries": self.ai.search_poll_max_retries,
                "save_history": self.ai.save_history,
                "enhance_sources": self.ai.enhance_sources,
            },
            "orchestrator": {
                "parallel_execution": self.orchestrator.parallel_execution,
                "max_concurrent_layers": self.orchestrator.max_concurrent_layers,
                "global_timeout": self.orchestrator.global_timeout,
                "retry_failed_layers": self.orchestrator.retry_failed_layers,
                "skip_on_error": self.orchestrator.skip_on_error,
                "default_mode": self.orchestrator.default_mode,
            },
            "version": self.version,
            "environment": self.environment,
        }


# 全局配置实例
_layer_config: Optional[LayerSystemConfig] = None


def get_layer_config() -> LayerSystemConfig:
    """获取层系统配置（单例）

    Returns:
        LayerSystemConfig: 层系统配置实例
    """
    global _layer_config
    if _layer_config is None:
        _layer_config = LayerSystemConfig.from_env()
        logger.info(
            f"Layer config loaded: env={_layer_config.environment}, "
            f"search_engine={_layer_config.search.engine}, "
            f"parallel={_layer_config.orchestrator.parallel_execution}"
        )
    return _layer_config


def load_layer_config(config_path: Optional[str] = None) -> LayerSystemConfig:
    """加载层系统配置

    Args:
        config_path: 配置文件路径（可选）

    Returns:
        LayerSystemConfig: 层系统配置实例
    """
    global _layer_config

    if config_path:
        path = Path(config_path)
        if path.exists():
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _layer_config = LayerSystemConfig.from_dict(data)
            logger.info(f"Layer config loaded from file: {config_path}")
        else:
            logger.warning(f"Config file not found: {config_path}, using env config")
            _layer_config = LayerSystemConfig.from_env()
    else:
        _layer_config = LayerSystemConfig.from_env()

    return _layer_config


def reset_layer_config() -> None:
    """重置配置（用于测试）"""
    global _layer_config
    _layer_config = None
