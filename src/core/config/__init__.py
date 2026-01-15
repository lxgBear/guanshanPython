"""配置系统模块

提供层架构和服务的配置管理。
"""

from .layer_config import (
    LayerSystemConfig,
    get_layer_config,
    load_layer_config,
)

__all__ = [
    "LayerSystemConfig",
    "get_layer_config",
    "load_layer_config",
]
